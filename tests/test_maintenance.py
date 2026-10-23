"""Guarded unlink proofs, exact state, interruption, writers and backup recovery."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

import prosper.maintenance as maintenance
import prosper.recovery as recovery
from prosper.evidence import STORAGE_VERSION, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.imports import ImportService
from prosper.inspection import inspect_recovery
from prosper.maintenance import maintain_runtime, recover_from_backup
from prosper.persistence import DATABASE_NAME, RESTORE_MARKER, CheckpointStore
from prosper.recovery import MANIFEST_NAME, backup, restore

SOURCE = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]


def boundary(root: Path) -> RuntimeBoundary:
    return RuntimeBoundary(root, SOURCE, "synthetic")


def app(root: Path) -> ImportService:
    return ImportService(CheckpointStore(EvidenceStore(boundary(root))))


def document() -> Document:
    data = cast(Document, json.loads((SOURCE / "examples/synthetic/F001.json").read_bytes()))
    data["lots"][0]["basis"]["value"] = "1000.00"
    return data


def seed(root: Path) -> tuple[ImportService, str]:
    service = app(root)
    identity = service.previews.stage(json.dumps(document()).encode()).receipt.raw_sha256
    assert service.commit(identity, "first", 0).outcome == "committed"
    return service, identity


def rows(root: Path) -> tuple[list[tuple[object, ...]], ...]:
    with closing(sqlite3.connect(root / DATABASE_NAME)) as connection:
        return tuple(
            connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in ("checkpoints", "import_previews", "import_activations", "import_commands")
        )


def payloads(root: Path) -> dict[str, tuple[str, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_nlink,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def check_values(service: ImportService) -> None:
    state = service.current()
    assert state.generation == 1 and state.checkpoint is not None
    inspected = state.checkpoint.inspection
    for actual, expected in (
        (inspected.positions[0].quantity, "12"),
        (inspected.positions[1].quantity, "5"),
        (inspected.cash[0].settled, "319"),
        (inspected.settled_cash_nav, "2399"),
        (inspected.total_basis, "2181"),
    ):
        assert isinstance(actual, ExactValue) and actual.canonical == expected
    basis = inspected.source.document.lots[0].basis.value
    assert (
        basis is not None
        and basis.original_text == "1000.00"
        and str(basis.source_quantum) == "0.01"
    )
    assert not inspected.readiness.planning_ready


def test_complete_state_cleanup_reopen_retry_backup_restore(tmp_path: Path) -> None:
    live = tmp_path / "live"
    service, identity = seed(live)
    legacy = service.previews.stage((SOURCE / "examples/synthetic/F000.json").read_bytes())
    assert legacy.inspection is not None and legacy.inspection.validated is not None
    service.store.append(legacy.inspection.validated)
    rejected = service.previews.stage(b"{").receipt.raw_sha256
    service.previews.reject(rejected)
    original_receipt = service.commit(rejected, "reject", 1)
    data = document()
    data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    unknown = service.previews.stage(json.dumps(data).encode()).receipt.raw_sha256
    orphan = service.store.evidence.publish(b"synthetic complete orphan")
    before = rows(live)
    result = maintain_runtime(boundary(live))
    assert result.status == "verified" and not result.planning_ready
    assert len(result.actions) == 1 and result.actions[0].kind == "removed_unreferenced_object"
    assert result.actions[0].reference == orphan.relative_reference
    assert not (live / orphan.relative_reference).exists() and rows(live) == before
    assert maintain_runtime(boundary(live)).actions == ()
    reopened = app(live)
    assert reopened.commit(rejected, "reject", 1) == original_receipt
    assert reopened.commit(identity, "first", 0).generation == 1
    incomplete = reopened.previews.get(unknown).inspection
    assert incomplete is not None and incomplete.total_basis == UnknownValue(("source_missing",))
    check_values(reopened)
    backup(reopened.store, boundary(tmp_path / "backup"), candidate_id="maintenance")
    restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    assert rows(tmp_path / "restored") == before
    check_values(app(tmp_path / "restored"))


@pytest.mark.parametrize("required", [True, False])
@pytest.mark.parametrize("links", [1, 2])
def test_only_proven_staging_aliases_are_removed_and_required_object_survives(
    tmp_path: Path, required: bool, links: int
) -> None:
    service, identity = seed(tmp_path / "live")
    if not required:
        identity = service.store.evidence.publish(b"synthetic aliased orphan").raw_sha256
    obj = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{identity}.bin")
    original = obj.read_bytes()
    for number in range(links):
        staged = service.store.evidence.runtime.path(
            f"{STORAGE_VERSION}/staging/{number:032x}.part"
        )
        os.link(obj, staged)
    before = rows(tmp_path / "live")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "verified", result.retained
    assert len([a for a in result.actions if a.kind == "removed_staging_alias"]) == links
    if required:
        assert obj.read_bytes() == original and obj.stat().st_nlink == 1
    else:
        assert not obj.exists()
    assert rows(tmp_path / "live") == before
    check_values(app(tmp_path / "live"))


def test_standalone_staging_is_preserved_without_inventing_intent(tmp_path: Path) -> None:
    service, _ = seed(tmp_path / "live")
    orphan = service.store.evidence.publish(b"known canonical orphan")
    staged = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part")
    staged.write_bytes(b"unbound or incomplete synthetic staging")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "retained" and result.after.status == "verified"
    assert {f.code for f in result.retained} == {"unbound_staging_preserved"}
    assert staged.read_bytes() == b"unbound or incomplete synthetic staging"
    assert not (tmp_path / "live" / orphan.relative_reference).exists()


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "corrupt",
        "external_link",
        "extra_link",
        "schema",
        "metadata",
        "unknown",
        "marker",
        "empty",
    ],
)
def test_uncertain_state_never_authorizes_any_cleanup(tmp_path: Path, damage: str) -> None:
    live = tmp_path / "live"
    service, identity = seed(live)
    orphan = service.store.evidence.publish(b"orphan must be retained on bad state")
    obj = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{identity}.bin")
    if damage == "missing":
        obj.unlink()
    elif damage == "corrupt":
        obj.write_bytes(b"damaged")
    elif damage in ("external_link", "extra_link"):
        os.link(obj, tmp_path / "external")
        if damage == "extra_link":
            os.link(
                obj,
                service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part"),
            )
    elif damage in ("schema", "metadata"):
        with closing(sqlite3.connect(live / DATABASE_NAME)) as connection:
            connection.execute(
                "PRAGMA user_version=2"
                if damage == "schema"
                else "UPDATE checkpoints SET canonical_text='{}'"
            )
            connection.commit()
    elif damage == "empty":
        (live / DATABASE_NAME).write_bytes(b"")
    else:
        (live / (RESTORE_MARKER if damage == "marker" else "unknown")).write_bytes(b"retain")
    before = payloads(live)
    result = maintain_runtime(boundary(live))
    assert result.status == "retained" and result.actions == ()
    assert payloads(live) == before and (live / orphan.relative_reference).exists()


def test_missing_runtime_is_not_created(tmp_path: Path) -> None:
    result = maintain_runtime(boundary(tmp_path / "missing"))
    assert result.status == "retained" and not (tmp_path / "missing").exists()


def test_current_references_after_old_inspection_protect_the_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = seed(tmp_path / "live")
    data = document()
    data["metadata"]["source_version"] = "new"
    raw = json.dumps(data).encode()
    receipt = service.store.evidence.publish(raw)
    old = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    assert next(n for n in old.files if n.reference == receipt.relative_reference).required is False

    def commit(step: str) -> None:
        if step == "before_lock":
            identity = service.previews.stage(raw).receipt.raw_sha256
            assert service.commit(identity, "new", 1).generation == 2

    monkeypatch.setattr(maintenance, "_step", commit)
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "verified" and result.actions == ()
    assert service.store.evidence.read(receipt) == raw and service.current().generation == 2


def test_last_reference_check_is_inside_action_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = seed(tmp_path / "live")
    data = document()
    data["metadata"]["source_version"] = "unactivated"
    receipt = service.store.evidence.publish(json.dumps(data).encode())
    from prosper.persistence import _inspect

    inspected = _inspect(service.store.evidence.read(receipt))

    def reference(connection: sqlite3.Connection, relative: str) -> None:
        if relative == receipt.relative_reference:
            service.store._append_in_transaction(connection, inspected, receipt)

    monkeypatch.setattr(maintenance, "_before_unlink", reference)
    before = rows(tmp_path / "live")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "retained" and result.actions == ()
    assert "recovery_reference_now_required" in {f.code for f in result.retained}
    assert (tmp_path / "live" / receipt.relative_reference).exists()
    assert rows(tmp_path / "live") == before  # Test-only SQL insertion rolled back.


def test_failed_second_unlink_reports_partial_and_retry_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = seed(tmp_path / "live")
    for raw in (b"synthetic orphan 1", b"synthetic orphan 2"):
        service.store.evidence.publish(raw)
    calls = 0

    def fail(connection: sqlite3.Connection, relative: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic failure with no path disclosure")

    monkeypatch.setattr(maintenance, "_before_unlink", fail)
    before = rows(tmp_path / "live")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "partial" and len(result.actions) == 1
    assert "recovery_operation_failed" in {f.code for f in result.retained}
    assert rows(tmp_path / "live") == before
    monkeypatch.undo()
    assert maintain_runtime(boundary(tmp_path / "live")).status == "verified"
    check_values(app(tmp_path / "live"))


@pytest.mark.parametrize(
    "phase", ["locked", "state_proven", "validated_unlink", "after_unlink", "state_reverified"]
)
def test_abrupt_cleanup_exit_preserves_committed_state_and_is_repeatable(
    tmp_path: Path, phase: str
) -> None:
    service, identity = seed(tmp_path / "live")
    obj = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{identity}.bin")
    os.link(obj, service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part"))
    service.store.evidence.publish(b"synthetic orphan")
    before = rows(tmp_path / "live")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sys
from pathlib import Path
import prosper.maintenance as maintenance
from prosper.evidence import RuntimeBoundary
root, source, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def fail(step):
    if step == phase: os._exit(81)
maintenance._step = fail
maintenance.maintain_runtime(RuntimeBoundary(root, source, 'synthetic'))
""",
            str(tmp_path / "live"),
            str(SOURCE),
            phase,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 81, result.stderr
    assert rows(tmp_path / "live") == before and obj.read_bytes() == json.dumps(document()).encode()
    retried = maintain_runtime(boundary(tmp_path / "live"))
    assert retried.status == "verified", retried.retained
    assert maintain_runtime(boundary(tmp_path / "live")).actions == ()
    check_values(app(tmp_path / "live"))


@pytest.mark.parametrize(
    "phase", ["before_link", "after_link", "before_commit", "after_commit", "initialization"]
)
def test_original_operation_interruptions_have_conservative_dispositions(
    tmp_path: Path, phase: str
) -> None:
    live = tmp_path / "live"
    if phase != "initialization":
        seed(live)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json, os, sys
from pathlib import Path
import prosper.evidence as evidence
import prosper.previews as previews
import prosper.persistence as persistence
root, source, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if phase == 'initialization':
    persistence.sqlite3.connect = lambda *args, **kwargs: os._exit(82)
runtime = evidence.RuntimeBoundary(root, source, 'synthetic')
store = persistence.CheckpointStore(evidence.EvidenceStore(runtime))
data = json.loads((source / 'examples/synthetic/F001.json').read_bytes())
data['metadata']['source_version'] = 'crashed'
def failed(staged, final):
    if phase == 'after_link': os.link(staged, final)
    os._exit(82)
if phase in ('before_link', 'after_link'): evidence._publish = failed
if phase == 'before_commit': previews._before_preview_commit = lambda connection: os._exit(82)
previews.PreviewService(store).stage(json.dumps(data).encode())
os._exit(82)
""",
            str(live),
            str(SOURCE),
            phase,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 82, result.stderr
    before = payloads(live)
    report = maintain_runtime(boundary(live))
    if phase in ("initialization", "before_link"):
        assert report.status == "retained" and report.actions == ()
        assert payloads(live) == before
    else:
        assert report.status == "verified", report.retained
        check_values(app(live))
        if phase == "after_commit":
            assert report.after.databases[0].state is not None
            assert report.after.databases[0].state.previews == 2


@pytest.mark.parametrize(
    "phase",
    [
        "backup_snapshot",
        "backup_evidence",
        "backup_verified",
        "restore_copied",
        "restore_verified",
        "restore_evidence_published",
        "restore_database_linked",
        "restore_database_published",
    ],
)
def test_interrupted_backup_restore_is_preserved_and_recovered_to_new_destination(
    tmp_path: Path, phase: str
) -> None:
    service, _ = seed(tmp_path / "live")
    backup(service.store, boundary(tmp_path / "safe"), candidate_id="fallback")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sys
from pathlib import Path
import prosper.recovery as recovery
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.persistence import CheckpointStore
root, source, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def b(name): return RuntimeBoundary(root / name, source, 'synthetic')
def fail(step):
    if step == phase: os._exit(83)
recovery._step = fail
if phase.startswith('backup'):
    recovery.backup(CheckpointStore(EvidenceStore(b('live'))), b('broken'), candidate_id='broken')
else:
    recovery.restore(b('safe'), b('broken'))
""",
            str(tmp_path),
            str(SOURCE),
            phase,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 83, result.stderr
    broken = tmp_path / "broken"
    before = payloads(broken)
    recovered = recover_from_backup(
        boundary(broken),
        "backup" if phase.startswith("backup") else "interrupted_restore",
        boundary(tmp_path / "safe"),
        boundary(tmp_path / "new"),
    )
    assert recovered.status == "restored", recovered.retained
    assert payloads(broken) == before
    assert rows(tmp_path / "new") == rows(tmp_path / "live")
    check_values(app(tmp_path / "new"))


@pytest.mark.parametrize("kind", ["empty", "marker", "corrupt"])
def test_failed_source_is_not_repaired_in_place_and_backup_recovery_is_exact(
    tmp_path: Path, kind: str
) -> None:
    service, _ = seed(tmp_path / "live")
    backup(service.store, boundary(tmp_path / "safe"), candidate_id="failed-state")
    failed = tmp_path / "failed"
    failed.mkdir()
    if kind == "marker":
        (failed / RESTORE_MARKER).write_bytes(b"isolated-restore-v1\n")
    else:
        (failed / DATABASE_NAME).write_bytes(b"" if kind == "empty" else b"damaged")
    before = payloads(failed)
    result = recover_from_backup(
        boundary(failed),
        "interrupted_restore" if kind == "marker" else "runtime",
        boundary(tmp_path / "safe"),
        boundary(tmp_path / "new"),
    )
    assert result.status == "restored" and payloads(failed) == before
    check_values(app(tmp_path / "new"))


@pytest.mark.parametrize(
    "kind",
    [
        "existing_destination",
        "overlap",
        "backup_overlap",
        "incompatible_backup",
        "missing_evidence",
    ],
)
def test_backup_recovery_refuses_unsafe_or_unqualified_targets(tmp_path: Path, kind: str) -> None:
    service, _ = seed(tmp_path / "live")
    saved = boundary(tmp_path / "safe")
    manifest = backup(service.store, saved, candidate_id="refuse")
    destination = boundary(tmp_path / "new")
    if kind == "existing_destination":
        destination.root.mkdir()
        (destination.root / "retain").write_bytes(b"retain")
    elif kind == "overlap":
        destination = boundary(tmp_path / "live/child")
    elif kind == "backup_overlap":
        destination = boundary(tmp_path / "safe/child")
    elif kind == "missing_evidence":
        saved.path(manifest.evidence[0].reference).unlink()
    else:
        path = saved.path(MANIFEST_NAME)
        data = json.loads(path.read_bytes())
        data["implementation_sha256"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
    before = payloads(tmp_path / "live")
    result = recover_from_backup(boundary(tmp_path / "live"), "runtime", saved, destination)
    assert result.status == "retained" and result.retained
    assert payloads(tmp_path / "live") == before
    if kind == "existing_destination":
        assert (destination.root / "retain").read_bytes() == b"retain"
    else:
        assert not destination.root.exists()


def wait_for(path: Path, worker: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while not path.exists():
        assert worker.poll() is None, "synthetic worker exited before synchronization"
        assert time.monotonic() < deadline, "synthetic synchronization timeout"
        time.sleep(0.01)


@pytest.mark.parametrize("mode", ["commit", "maintain"])
@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_competing_process_writer_or_recovery_revalidates_after_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, journal: str
) -> None:
    live = tmp_path / "live"
    service, _ = seed(live)
    with closing(sqlite3.connect(live / DATABASE_NAME)) as keeper:
        assert keeper.execute(f"PRAGMA journal_mode={journal}").fetchone()[0] == journal.lower()
        data = document()
        data["metadata"]["source_version"] = "new"
        raw = json.dumps(data).encode()
        orphan = service.store.evidence.publish(raw)
        payload = tmp_path / "payload.json"
        payload.write_bytes(raw)
        attempt = tmp_path / "attempt"
        workers: list[subprocess.Popen[str]] = []

        def start(step: str) -> None:
            if step == "locked":
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        """
import sys
from pathlib import Path
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.persistence import CheckpointStore
from prosper.imports import ImportService
from prosper.maintenance import maintain_runtime
root, source, payload, attempt = map(Path, sys.argv[1:5])
mode = sys.argv[5]
runtime = RuntimeBoundary(root, source, 'synthetic')
Path(attempt).touch()
if mode == 'maintain':
    result = maintain_runtime(runtime)
    assert result.status == 'verified', result.retained
else:
    app = ImportService(CheckpointStore(EvidenceStore(runtime)))
    identity = app.previews.stage(payload.read_bytes()).receipt.raw_sha256
    assert app.commit(identity, 'new', 1).generation == 2
""",
                        str(live),
                        str(SOURCE),
                        str(payload),
                        str(attempt),
                        mode,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                workers.append(worker)
                wait_for(attempt, worker)
                time.sleep(0.05)
                assert worker.poll() is None  # Cannot finish while writer lock is held.

        monkeypatch.setattr(maintenance, "_step", start)
        try:
            result = maintain_runtime(boundary(live))
            assert result.status == "verified", result.retained
            assert [a.reference for a in result.actions] == [orphan.relative_reference]
            assert result.after.databases[0].state is not None
            assert result.after.databases[0].state.generation == 1
            out, err = workers[0].communicate(timeout=20)
            assert workers[0].returncode == 0, (out, err)
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate()
        if mode == "commit":
            assert service.current().generation == 2
            assert service.store.evidence.read(orphan) == raw
        else:
            assert service.current().generation == 1
            assert not (live / orphan.relative_reference).exists()


def test_direct_raw_publisher_race_fails_safely_and_retry_can_commit(tmp_path: Path) -> None:
    live = tmp_path / "live"
    service, _ = seed(live)
    data = document()
    data["metadata"]["source_version"] = "direct-publication"
    raw = json.dumps(data).encode()
    payload = tmp_path / "payload.json"
    payload.write_bytes(raw)
    published, release = tmp_path / "published", tmp_path / "release"
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            """
import os, sys, time
from pathlib import Path
import prosper.evidence as evidence
root, source, payload, published, release = map(Path, sys.argv[1:])
def pause(staged, final):
    os.link(staged, final)
    published.touch()
    until = time.monotonic() + 15
    while not release.exists():
        assert time.monotonic() < until
        time.sleep(0.01)
    staged.unlink()
evidence._publish = pause
store = evidence.EvidenceStore(evidence.RuntimeBoundary(root, source, 'synthetic'))
try:
    store.publish(payload.read_bytes())
except evidence.EvidenceError as error:
    assert error.code == 'evidence_publication_failed'
else:
    raise AssertionError('Expected safe publication failure after cleanup')
""",
            str(live),
            str(SOURCE),
            str(payload),
            str(published),
            str(release),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(published, worker)
        result = maintain_runtime(boundary(live))
        assert result.status == "verified", result.retained
        assert {a.kind for a in result.actions} == {
            "removed_staging_alias",
            "removed_unreferenced_object",
        }
        release.touch()
        out, err = worker.communicate(timeout=20)
        assert worker.returncode == 0, (out, err)
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.communicate()
    assert service.current().generation == 1
    identity = service.previews.stage(raw).receipt.raw_sha256
    assert service.commit(identity, "retry-direct", 1).generation == 2
    assert service.store.evidence.read(service.previews.get(identity).receipt) == raw


def test_changed_path_before_final_unlink_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = seed(tmp_path / "live")
    orphan = service.store.evidence.publish(b"synthetic orphan to redirect")
    moved = tmp_path / "retain-outside"

    def redirect(connection: sqlite3.Connection, reference: str) -> None:
        path = service.store.evidence.runtime.path(reference)
        path.rename(moved)
        path.symlink_to(moved)

    monkeypatch.setattr(maintenance, "_before_unlink", redirect)
    before = rows(tmp_path / "live")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "retained" and result.actions == ()
    assert moved.read_bytes() == b"synthetic orphan to redirect"
    assert (tmp_path / "live" / orphan.relative_reference).is_symlink()
    assert rows(tmp_path / "live") == before


def test_aliased_bytes_do_not_hide_bad_financial_metadata(tmp_path: Path) -> None:
    service, identity = seed(tmp_path / "live")
    obj = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{identity}.bin")
    os.link(obj, service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part"))
    with closing(sqlite3.connect(tmp_path / "live" / DATABASE_NAME)) as connection:
        connection.execute("UPDATE checkpoints SET canonical_text='{}'")
        connection.commit()
    before = payloads(tmp_path / "live")
    result = maintain_runtime(boundary(tmp_path / "live"))
    assert result.status == "retained" and result.actions == ()
    assert "stored_metadata_mismatch" in {f.code for f in result.retained}
    assert payloads(tmp_path / "live") == before


def test_hot_journal_is_preserved_before_writable_open(tmp_path: Path) -> None:
    live = tmp_path / "live"
    seed(live)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json, os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
connection.execute('PRAGMA cache_size=1')
connection.execute('BEGIN IMMEDIATE')
payload = json.dumps({'synthetic': 'x' * 100000})
connection.execute('UPDATE checkpoints SET canonical_text=?', (payload,))
os._exit(84)
""",
            str(live / DATABASE_NAME),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 84, result.stderr
    before = payloads(live)
    report = maintain_runtime(boundary(live))
    assert report.status == "retained" and report.actions == ()
    assert payloads(live) == before


def test_private_mode_cleanup_uses_only_synthetic_scratch(tmp_path: Path) -> None:
    fake_source = tmp_path / "source"
    fake_source.mkdir()
    runtime = RuntimeBoundary(tmp_path / "private", fake_source, "private")
    service = ImportService(CheckpointStore(EvidenceStore(runtime)))
    identity = service.previews.stage(json.dumps(document()).encode()).receipt.raw_sha256
    service.commit(identity, "first", 0)
    receipt = service.store.evidence.publish(b"synthetic private-mode orphan")
    result = maintain_runtime(runtime)
    assert result.status == "verified" and not (runtime.root / receipt.relative_reference).exists()
    check_values(service)


@pytest.mark.parametrize("phase", ["restore_copied", "restore_database_linked"])
def test_backup_recovery_failure_reports_partial_and_preserves_reusable_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    service, _ = seed(tmp_path / "live")
    backup(service.store, boundary(tmp_path / "safe"), candidate_id="partial")
    failed = tmp_path / "failed"
    failed.mkdir()
    (failed / RESTORE_MARKER).write_bytes(b"isolated-restore-v1\n")
    source_before = payloads(failed)
    backup_before = payloads(tmp_path / "safe")

    def fail(step: str) -> None:
        if step == phase:
            raise OSError("synthetic restore failure")

    monkeypatch.setattr(recovery, "_step", fail)
    result = recover_from_backup(
        boundary(failed),
        "interrupted_restore",
        boundary(tmp_path / "safe"),
        boundary(tmp_path / "partial"),
    )
    assert result.status == "partial" and result.after.status == "non_ready"
    assert (tmp_path / "partial" / RESTORE_MARKER).is_file()
    assert payloads(failed) == source_before
    assert payloads(tmp_path / "safe") == backup_before
    monkeypatch.undo()
    retried = recover_from_backup(
        boundary(failed),
        "interrupted_restore",
        boundary(tmp_path / "safe"),
        boundary(tmp_path / "new"),
    )
    assert retried.status == "restored"
    check_values(app(tmp_path / "new"))
