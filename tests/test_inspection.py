"""Truthful read-only recovery observations, real interruptions and process races."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

import prosper.inspection as inspection
from prosper.evidence import STORAGE_VERSION, EvidenceError, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.imports import ImportService
from prosper.inspection import ArtifactRole, inspect_recovery
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


def seeded(root: Path) -> tuple[ImportService, str]:
    service = app(root)
    identity = service.previews.stage(json.dumps(document()).encode()).receipt.raw_sha256
    assert service.commit(identity, "first", 0).outcome == "committed"
    return service, identity


def payloads(root: Path) -> dict[str, tuple[str, int]]:
    # Test oracle only, called on known synthetic, non-redirected layouts.
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_nlink,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def codes(report: inspection.RecoveryInspection) -> set[str]:
    return {finding.code for finding in report.findings}


def test_full_state_exact_values_unknowns_and_receipts_are_unchanged(tmp_path: Path) -> None:
    live = tmp_path / "live"
    service, identity = seeded(live)
    legacy = service.previews.stage((SOURCE / "examples/synthetic/F000.json").read_bytes())
    assert legacy.inspection is not None and legacy.inspection.validated is not None
    service.store.append(legacy.inspection.validated)
    rejected = service.previews.stage(b"{").receipt.raw_sha256
    service.previews.reject(rejected)
    receipt = service.commit(rejected, "rejected", 1)
    data = document()
    data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    unknown = service.previews.stage(json.dumps(data).encode()).receipt.raw_sha256
    before = payloads(live)
    report = inspect_recovery(boundary(live), "runtime")
    assert report.status == "verified" and not report.planning_ready
    database = report.databases[0]
    assert database.status == "verified" and database.state is not None
    assert database.state.generation == 1 and database.state.checkpoints == 2
    assert database.state.previews == 4 and database.state.commands == 2
    assert database.required is not None and len(database.required) == 4
    assert {node.classification for node in report.files if node.kind == "object"} == {
        "required_verified"
    }
    assert payloads(live) == before
    assert inspect_recovery(boundary(live), "runtime") == report
    assert service.commit(rejected, "rejected", 1) == receipt
    assert service.commit(identity, "first", 0).generation == 1
    current = service.current().checkpoint
    assert current is not None
    for actual, expected in (
        (current.inspection.positions[0].quantity, "12"),
        (current.inspection.positions[1].quantity, "5"),
        (current.inspection.cash[0].settled, "319"),
        (current.inspection.settled_cash_nav, "2399"),
        (current.inspection.total_basis, "2181"),
    ):
        assert isinstance(actual, ExactValue) and actual.canonical == expected
    basis = current.inspection.source.document.lots[0].basis.value
    assert (
        basis is not None
        and basis.original_text == "1000.00"
        and str(basis.source_quantum) == "0.01"
    )
    incomplete = service.previews.get(unknown).inspection
    assert incomplete is not None and incomplete.total_basis == UnknownValue(("source_missing",))


def test_unreferenced_object_and_staging_never_gain_import_or_cleanup_authority(
    tmp_path: Path,
) -> None:
    service, _ = seeded(tmp_path / "live")
    orphan = service.store.evidence.publish(b"synthetic unreferenced")
    staging = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part")
    staging.write_bytes(b"partial synthetic staging")
    before = payloads(tmp_path / "live")
    report = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    files = {node.reference: node for node in report.files}
    assert files[orphan.relative_reference].classification == "unreferenced_object"
    assert files[orphan.relative_reference].required is False
    assert (
        files[staging.relative_to(tmp_path / "live").as_posix()].classification
        == "unreferenced_staging"
    )
    assert report.databases[0].state is not None and report.databases[0].state.generation == 1
    assert payloads(tmp_path / "live") == before


@pytest.mark.parametrize(
    "damage", ["missing", "corrupt", "external_link", "local_alias", "extra_link"]
)
def test_required_objects_never_become_ready_when_damaged_or_linked(
    tmp_path: Path, damage: str
) -> None:
    service, identity = seeded(tmp_path / "live")
    reference = f"{STORAGE_VERSION}/objects/{identity}.bin"
    path = service.store.evidence.runtime.path(reference)
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(b"synthetic damage")
    else:
        alias = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'a' * 32}.part")
        os.link(path, alias if damage != "external_link" else tmp_path / "outside")
        if damage == "extra_link":
            os.link(path, tmp_path / "extra")
    before = payloads(tmp_path / "live")
    report = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    assert report.status == "non_ready" and report.databases[0].state is None
    if damage == "local_alias":
        linked = [node for node in report.files if node.links == 2]
        assert len(linked) == 2 and all(
            node.classification == "local_publication_alias" for node in linked
        )
        assert "local_publication_alias" in codes(report)
    elif damage in ("external_link", "extra_link"):
        assert "unexplained_links" in codes(report)
    elif damage == "missing":
        assert "required_evidence_missing" in codes(report)
    assert payloads(tmp_path / "live") == before


@pytest.mark.parametrize(
    "kind", ["missing", "empty", "foreign", "schema_two", "corrupt", "metadata", "receipt"]
)
def test_unqualified_database_is_not_initialized_upgraded_or_repaired(
    tmp_path: Path, kind: str
) -> None:
    live = tmp_path / "live"
    service, _ = seeded(live)
    path = live / DATABASE_NAME
    if kind == "missing":
        path.unlink()
    elif kind in ("empty", "corrupt"):
        path.write_bytes(b"" if kind == "empty" else b"not a database")
    else:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                {
                    "foreign": "PRAGMA application_id=1",
                    "schema_two": "PRAGMA user_version=2",
                    "metadata": "UPDATE checkpoints SET canonical_text='{}'",
                    "receipt": "DELETE FROM import_commands",
                }[kind]
            )
            connection.commit()
    before = payloads(live)
    report = inspect_recovery(boundary(live), "runtime")
    assert report.status == "non_ready" and report.databases[0].state is None
    assert payloads(live) == before
    assert (
        service is not None
    )  # Keep the original adapter alive; inspection never uses its initializer.


@pytest.mark.parametrize(
    "target",
    [
        DATABASE_NAME,
        DATABASE_NAME + "-wal",
        DATABASE_NAME + "-journal",
        STORAGE_VERSION + "/objects",
    ],
)
def test_redirects_are_not_followed_even_for_sqlite_sidecars(tmp_path: Path, target: str) -> None:
    live = tmp_path / "live"
    seeded(live)
    path = live / target
    moved = tmp_path / "redirected"
    directory = path.is_dir()
    if path.exists():
        path.rename(moved)
    else:
        moved.write_bytes(b"synthetic outside sidecar")
    path.symlink_to(moved, target_is_directory=directory)
    before = moved.stat()
    report = inspect_recovery(boundary(live), "runtime")
    assert report.status == "non_ready" and report.databases[0].state is None
    assert any("redirected_path" in code for code in codes(report))
    assert moved.stat().st_mtime_ns == before.st_mtime_ns
    assert path.is_symlink()


@pytest.mark.parametrize("name", ["unknown", "bad name", "unknown-dir", "bad-name.bin"])
def test_unknown_entries_are_preserved_without_arbitrary_traversal(
    tmp_path: Path, name: str
) -> None:
    live = tmp_path / "live"
    seeded(live)
    path = live / name
    if name == "unknown-dir":
        path.mkdir()
        (path / "private-do-not-read").write_bytes(b"synthetic retained")
    else:
        path.write_bytes(b"synthetic retained")
    before = payloads(live)
    report = inspect_recovery(boundary(live), "runtime")
    assert report.status == "non_ready"
    assert not any("private-do-not-read" in node.reference for node in report.files)
    assert not any("bad name" in finding.reference for finding in report.findings)
    assert payloads(live) == before


def test_backup_role_verifies_manifest_complete_state_and_leaves_hashes_unchanged(
    tmp_path: Path,
) -> None:
    service, _ = seeded(tmp_path / "live")
    saved = boundary(tmp_path / "backup")
    backup(service.store, saved, candidate_id="inspection-synthetic")
    before = payloads(saved.root)
    report = inspect_recovery(saved, "backup")
    assert report.status == "verified" and report.databases[0].state is not None
    assert report.databases[0].state.generation == 1
    assert payloads(saved.root) == before
    assert "artifact_role_mismatch" in codes(inspect_recovery(saved, "runtime"))
    restore(saved, boundary(tmp_path / "restored"))
    assert inspect_recovery(boundary(tmp_path / "restored"), "runtime").status == "verified"
    # The known empty work directory left by a complete restore is harmless.


@pytest.mark.parametrize(
    "damage",
    [
        "missing_manifest",
        "corrupt_manifest",
        "incompatible",
        "db_hash",
        "object",
        "state",
        "references",
    ],
)
def test_incomplete_or_incompatible_backup_is_never_verified(tmp_path: Path, damage: str) -> None:
    service, identity = seeded(tmp_path / "live")
    saved = boundary(tmp_path / "backup")
    backup(service.store, saved, candidate_id="damaged-backup")
    path = saved.root / MANIFEST_NAME
    if damage == "missing_manifest":
        path.unlink()
    elif damage == "corrupt_manifest":
        path.write_bytes(b"{")
    elif damage == "object":
        saved.path(f"{STORAGE_VERSION}/objects/{identity}.bin").unlink()
    else:
        data = json.loads(path.read_bytes())
        if damage == "incompatible":
            data["implementation_sha256"] = "0" * 64
        elif damage == "db_hash":
            data["database"]["sha256"] = "0" * 64
        elif damage == "state":
            data["state"]["generation"] = 99
        else:
            data["evidence"] = []
        path.write_text(json.dumps(data), encoding="utf-8")
    before = payloads(saved.root)
    assert inspect_recovery(saved, "backup").status == "non_ready"
    assert payloads(saved.root) == before


@pytest.mark.parametrize("limit", ["MAX_ENTRIES", "MAX_TOTAL_BYTES", "MAX_ROWS"])
def test_inspection_has_bounded_work_and_cannot_turn_limits_into_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    seeded(tmp_path / "live")
    monkeypatch.setattr(inspection, limit, 1)
    report = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    assert report.status == "non_ready" and any("limit" in code for code in codes(report))


def test_missing_root_and_invalid_role_do_not_create_state(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    assert "runtime_missing" in codes(inspect_recovery(boundary(root), "runtime"))
    assert not root.exists()
    with pytest.raises(EvidenceError, match="invalid_artifact_role"):
        inspect_recovery(boundary(root), cast(ArtifactRole, "from-imported-text"))
    with pytest.raises(EvidenceError, match="runtime_missing"):
        EvidenceStore.existing(boundary(root))
    assert not root.exists()


@pytest.mark.parametrize(
    "phase", ["before_link", "after_link", "before_commit", "after_commit", "initialization"]
)
def test_actual_original_process_interruptions_are_observed_without_repair(
    tmp_path: Path, phase: str
) -> None:
    live = tmp_path / "live"
    if phase != "initialization":
        seeded(live)
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
from prosper.imports import ImportService
root, source, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
boundary = evidence.RuntimeBoundary(root, source, 'synthetic')
if phase == 'initialization':
    old = persistence.sqlite3.connect
    def fail(*args, **kwargs): os._exit(71)
    persistence.sqlite3.connect = fail
store = persistence.CheckpointStore(evidence.EvidenceStore(boundary))
app = ImportService(store)
data = json.loads((source / 'examples/synthetic/F001.json').read_bytes())
data['metadata']['source_version'] = 'interrupted'
def fail_publish(staged, final):
    if phase == 'after_link': os.link(staged, final)
    os._exit(71)
if phase in ('before_link', 'after_link'): evidence._publish = fail_publish
if phase == 'before_commit': previews._before_preview_commit = lambda connection: os._exit(71)
app.previews.stage(json.dumps(data).encode())
os._exit(71)
""",
            str(live),
            str(SOURCE),
            phase,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 71, result.stderr
    before = payloads(live)
    report = inspect_recovery(boundary(live), "runtime")
    if phase == "initialization":
        assert report.status == "non_ready" and report.databases[0].state is None
    elif phase == "after_link":
        assert "local_publication_alias" in codes(report)
    elif phase == "before_link":
        assert any(node.classification == "unreferenced_staging" for node in report.files)
    elif phase == "before_commit":
        assert any(node.classification == "unreferenced_object" for node in report.files)
    else:
        assert report.databases[0].state is not None and report.databases[0].state.previews == 2
    assert payloads(live) == before


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
def test_each_backup_restore_crash_boundary_is_preserved_and_non_ready(
    tmp_path: Path, phase: str
) -> None:
    service, _ = seeded(tmp_path / "live")
    if phase.startswith("restore"):
        backup(service.store, boundary(tmp_path / "backup"), candidate_id="crash")
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
def boundary(name): return RuntimeBoundary(root / name, source, 'synthetic')
def fail(step):
    if step == phase: os._exit(72)
recovery._step = fail
if phase.startswith('backup'):
    store = CheckpointStore(EvidenceStore(boundary('live')))
    recovery.backup(store, boundary('backup'), candidate_id='crash')
else:
    recovery.restore(boundary('backup'), boundary('restored'))
""",
            str(tmp_path),
            str(SOURCE),
            phase,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 72, result.stderr
    root = tmp_path / ("backup" if phase.startswith("backup") else "restored")
    before = payloads(root)
    report = inspect_recovery(
        boundary(root), "backup" if phase.startswith("backup") else "interrupted_restore"
    )
    assert report.status == "non_ready"
    if phase.startswith("restore"):
        assert "unbound_restore_requires_verified_recovery" in codes(report)
        assert (root / RESTORE_MARKER).is_file()
    assert payloads(root) == before


def test_wal_snapshot_and_changed_inventory_are_truthful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live = tmp_path / "live"
    service, _ = seeded(live)
    with closing(sqlite3.connect(live / DATABASE_NAME)) as keeper:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        service.previews.stage(b"{")
        # A cold read may create SQLite engine sidecars, truthfully reported as
        # inventory change. Once present, normal reader locks do not vary the report.
        inspect_recovery(boundary(live), "runtime")
        baseline = inspect_recovery(boundary(live), "runtime")
        assert baseline.status == "verified"
        assert inspect_recovery(boundary(live), "runtime") == baseline
        assert baseline.databases[0].state is not None and baseline.databases[0].state.previews == 2

        def mutate(step: str) -> None:
            if step == "snapshot_read":
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        """
import sys
from pathlib import Path
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.persistence import CheckpointStore
from prosper.previews import PreviewService
root, source = map(Path, sys.argv[1:])
runtime = RuntimeBoundary(root, source, 'synthetic')
PreviewService(CheckpointStore(EvidenceStore(runtime))).stage(b'[]')
""",
                        str(live),
                        str(SOURCE),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert result.returncode == 0, result.stderr

        monkeypatch.setattr(inspection, "_step", mutate)
        report = inspect_recovery(boundary(live), "runtime")
        assert report.status == "non_ready"
        assert report.databases[0].state is not None and report.databases[0].state.previews == 2
        assert "snapshot_changed" in codes(report) or "inventory_changed" in codes(report)
        assert report.databases[0].snapshot_sha256 == baseline.databases[0].snapshot_sha256
    assert service.previews.get(hashlib.sha256(b"[]").hexdigest()).state == "staged"


def test_private_mode_uses_synthetic_scratch_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    private = RuntimeBoundary(tmp_path / "private", source, "private")
    service = ImportService(CheckpointStore(EvidenceStore(private)))
    identity = service.previews.stage(json.dumps(document()).encode()).receipt.raw_sha256
    service.commit(identity, "private-synthetic", 0)
    assert inspect_recovery(private, "runtime").status == "verified"


def test_hot_journal_is_not_rolled_back_by_inspection(tmp_path: Path) -> None:
    live = tmp_path / "live"
    seeded(live)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json, os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
connection.execute('PRAGMA cache_size=1')
connection.execute('PRAGMA cache_spill=ON')
connection.execute('BEGIN IMMEDIATE')
payload = json.dumps({'synthetic': 'x' * 100000})
connection.execute('UPDATE checkpoints SET canonical_text=?', (payload,))
os._exit(74)
""",
            str(live / DATABASE_NAME),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 74, result.stderr
    assert (live / (DATABASE_NAME + "-journal")).stat().st_size > 0
    before = payloads(live)
    report = inspect_recovery(boundary(live), "runtime")
    assert report.status == "non_ready" and report.databases[0].state is None
    assert "database_unreadable" in codes(report)
    assert payloads(live) == before


def test_alias_with_contradictory_required_length_is_not_recoverable(tmp_path: Path) -> None:
    service, identity = seeded(tmp_path / "live")
    obj = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{identity}.bin")
    staged = service.store.evidence.runtime.path(f"{STORAGE_VERSION}/staging/{'b' * 32}.part")
    os.link(obj, staged)
    with closing(sqlite3.connect(tmp_path / "live" / DATABASE_NAME)) as connection:
        for table in ("checkpoints", "import_previews"):
            connection.execute(f"UPDATE {table} SET evidence_length=evidence_length+1")
        connection.commit()
    before = payloads(tmp_path / "live")
    report = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    assert all(
        node.classification == "unexplained_links" for node in report.files if node.links == 2
    )
    assert "required_evidence_mismatch" in codes(report)
    assert payloads(tmp_path / "live") == before


def test_windows_junction_is_retained_and_not_traversed(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction qualification only")
    service, identity = seeded(tmp_path / "live")
    objects = service.store.evidence.runtime.path(STORAGE_VERSION + "/objects")
    outside = tmp_path / "junction-target"
    assert objects.resolve().is_relative_to(tmp_path.resolve())
    assert outside.resolve().is_relative_to(tmp_path.resolve())
    objects.rename(outside)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(objects), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "synthetic junction creation failed"
    original = (outside / (identity + ".bin")).read_bytes()
    report = inspect_recovery(boundary(tmp_path / "live"), "runtime")
    assert report.status == "non_ready"
    assert any("redirected_path" in code for code in codes(report))
    assert (outside / (identity + ".bin")).read_bytes() == original
    assert objects.lstat().st_file_attributes & 0x400
