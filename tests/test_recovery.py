"""Application recovery: independent values, complete references and real interruption."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

import prosper.recovery as recovery
from prosper.evidence import STORAGE_VERSION, EvidenceError, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.imports import ImportService
from prosper.persistence import DATABASE_NAME, RESTORE_MARKER, CheckpointStore, PersistenceError
from prosper.recovery import MANIFEST_NAME, RecoveryError, backup, restore

SOURCE = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]


def document() -> Document:
    return cast(Document, json.loads((SOURCE / "examples/synthetic/F001.json").read_bytes()))


def raw(data: Document) -> bytes:
    return json.dumps(data).encode()


def boundary(root: Path) -> RuntimeBoundary:
    return RuntimeBoundary(root, SOURCE, "synthetic")


def service(root: Path) -> ImportService:
    return ImportService(CheckpointStore(EvidenceStore(boundary(root))))


def seed(root: Path) -> tuple[ImportService, dict[str, str]]:
    app = service(root)
    # An inactive legacy checkpoint must survive without becoming active.
    legacy_raw = (SOURCE / "examples/synthetic/F000.json").read_bytes()
    legacy = app.previews.stage(legacy_raw)
    assert legacy.inspection is not None and legacy.inspection.validated is not None
    app.store.append(legacy.inspection.validated)
    ids = {"legacy": legacy.receipt.raw_sha256}
    first = app.previews.stage(raw(document()))
    ids["first"] = first.receipt.raw_sha256
    assert app.commit(ids["first"], "first", 0).outcome == "committed"
    data = document()
    data["metadata"]["source_version"] = "v2"
    ids["second"] = app.previews.stage(raw(data)).receipt.raw_sha256
    assert app.commit(ids["second"], "second", 1).outcome == "committed"
    assert app.commit(ids["first"], "duplicate", 2).outcome == "duplicate"
    assert app.commit(ids["first"], "stale", 0).outcome == "stale_generation"
    ids["rejected"] = app.previews.stage(b"{").receipt.raw_sha256
    app.previews.reject(ids["rejected"])
    assert app.commit(ids["rejected"], "rejected", 2).outcome == "preview_rejected"
    ids["invalid"] = app.previews.stage(b"[]").receipt.raw_sha256
    assert app.commit(ids["invalid"], "invalid", 2).outcome == "preview_invalid"
    data["metadata"]["source_version"] = "incomplete"
    data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    ids["incomplete"] = app.previews.stage(raw(data)).receipt.raw_sha256
    return app, ids


def rows(root: Path) -> tuple[list[tuple[object, ...]], ...]:
    with closing(sqlite3.connect(root / DATABASE_NAME)) as connection:
        return tuple(
            connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in ("checkpoints", "import_previews", "import_activations", "import_commands")
        )


def edit_manifest(root: Path, change: str, value: object) -> None:
    path = root / MANIFEST_NAME
    data = json.loads(path.read_bytes())
    data[change] = value
    path.write_text(json.dumps(data), encoding="utf-8")


def rehash_database(root: Path) -> None:
    path = root / DATABASE_NAME
    edit_manifest(
        root,
        "database",
        {
            "reference": DATABASE_NAME,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_length": path.stat().st_size,
        },
    )


def test_complete_restore_preserves_all_rows_values_source_quantum_and_retries(
    tmp_path: Path,
) -> None:
    app, ids = seed(tmp_path / "live")
    # This complete object is unreferenced; it is deliberately not a required backup input.
    orphan = app.store.evidence.publish(b"unreferenced synthetic evidence")
    manifest = backup(app.store, boundary(tmp_path / "backup"), candidate_id="synthetic-test-v1")
    assert manifest.state.generation == 2
    assert manifest.state.checkpoints == 3 and manifest.state.previews == 6
    assert manifest.state.commands == 6 and len(manifest.evidence) == 6
    assert not (tmp_path / "backup" / orphan.relative_reference).exists()
    assert restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored")) == manifest
    assert rows(tmp_path / "live") == rows(tmp_path / "restored")
    reopened = service(tmp_path / "restored")
    current = reopened.current()
    assert current.generation == 2 and current.checkpoint is not None
    inspected = current.checkpoint.inspection
    for actual, expected in (
        (inspected.positions[0].quantity, "12"),
        (inspected.positions[1].quantity, "5"),
        (inspected.cash[0].settled, "319"),
        (inspected.settled_cash_nav, "2399"),
        (inspected.total_basis, "2181"),
    ):
        assert isinstance(actual, ExactValue) and actual.canonical == expected
    source = inspected.source.document.lots[0].basis
    original = app.current().checkpoint
    assert original is not None and source == original.inspection.source.document.lots[0].basis
    assert inspected.source.raw_bytes == raw(
        {**document(), "metadata": {**document()["metadata"], "source_version": "v2"}}
    )
    assert not inspected.readiness.planning_ready
    incomplete = reopened.previews.get(ids["incomplete"])
    assert incomplete.inspection is not None
    assert incomplete.inspection.total_basis == UnknownValue(("source_missing",))
    assert reopened.previews.get(ids["rejected"]).state == "rejected"
    for identity, key, expected_generation in (
        ("first", "first", 0),
        ("second", "second", 1),
        ("first", "duplicate", 2),
        ("first", "stale", 0),
        ("rejected", "rejected", 2),
        ("invalid", "invalid", 2),
    ):
        assert reopened.commit(ids[identity], key, expected_generation) == app.commit(
            ids[identity], key, expected_generation
        )
    assert reopened.current() == current
    assert not (tmp_path / "restored" / RESTORE_MARKER).exists()


@pytest.mark.parametrize("kind", ["empty", "legacy", "unknown"])
def test_empty_inactive_and_unknown_states_do_not_gain_readiness(tmp_path: Path, kind: str) -> None:
    app = service(tmp_path / "live")
    if kind != "empty":
        data = document()
        if kind == "unknown":
            data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
        preview = app.previews.stage(raw(data))
        assert preview.inspection is not None and preview.inspection.validated is not None
        if kind == "legacy":
            app.store.append(preview.inspection.validated)
        else:
            app.commit(preview.receipt.raw_sha256, "unknown", 0)
    backup(app.store, boundary(tmp_path / "backup"), candidate_id="empty-or-inactive")
    restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    assert service(tmp_path / "restored").current() == app.current()
    assert rows(tmp_path / "live") == rows(tmp_path / "restored")


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_snapshot_is_consistent_when_another_process_commits_and_rejects_after_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journal: str
) -> None:
    live = tmp_path / "live"
    app, ids = seed(live)
    before = rows(live)
    with closing(sqlite3.connect(live / DATABASE_NAME)) as connection:
        assert connection.execute(f"PRAGMA journal_mode={journal}").fetchone()[0] == journal.lower()

    def mutate(step: str) -> None:
        if step == "backup_snapshot":
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    """
import json, sys
from pathlib import Path
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.persistence import CheckpointStore
from prosper.imports import ImportService
root, source, legacy = sys.argv[1:]
runtime = RuntimeBoundary(Path(root), Path(source), 'synthetic')
app = ImportService(CheckpointStore(EvidenceStore(runtime)))
data = json.loads((Path(source) / 'examples/synthetic/F001.json').read_bytes())
data['metadata']['source_version'] = 'after-snapshot'
identity = app.previews.stage(json.dumps(data).encode()).receipt.raw_sha256
assert app.commit(identity, 'after-snapshot', 2).generation == 3
app.previews.reject(legacy)
""",
                    str(live),
                    str(SOURCE),
                    ids["legacy"],
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr

    monkeypatch.setattr(recovery, "_step", mutate)
    manifest = backup(app.store, boundary(tmp_path / "backup"), candidate_id="concurrent")
    assert app.current().generation == 3 and manifest.state.generation == 2
    restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    assert rows(tmp_path / "restored") == before
    assert service(tmp_path / "restored").previews.get(ids["legacy"]).state == "staged"


@pytest.mark.parametrize("operation", ["backup", "restore"])
@pytest.mark.parametrize("existing", ["empty", "populated", "file"])
def test_existing_destinations_are_never_overwritten(
    tmp_path: Path, operation: str, existing: str
) -> None:
    app = service(tmp_path / "live")
    backup(app.store, boundary(tmp_path / "backup"), candidate_id="existing")
    target = tmp_path / "target"
    if existing == "file":
        target.write_bytes(b"retain")
        with pytest.raises(EvidenceError):
            boundary(target)
        assert target.read_bytes() == b"retain"
        return
    target.mkdir()
    if existing == "populated":
        (target / "retain").write_bytes(b"original")
    before = list(target.iterdir())
    with pytest.raises(RecoveryError, match="destination_exists"):
        if operation == "backup":
            backup(app.store, boundary(target), candidate_id="existing")
        else:
            restore(boundary(tmp_path / "backup"), boundary(target))
    assert list(target.iterdir()) == before
    if existing == "populated":
        assert (target / "retain").read_bytes() == b"original"


@pytest.mark.parametrize("relationship", ["same", "child", "parent"])
def test_overlapping_boundaries_are_rejected(tmp_path: Path, relationship: str) -> None:
    app = service(tmp_path / "live")
    target = {"same": tmp_path / "live", "child": tmp_path / "live/child", "parent": tmp_path}
    with pytest.raises(RecoveryError, match="recovery_boundary_overlap_or_mode"):
        backup(app.store, boundary(target[relationship]), candidate_id="overlap")


@pytest.mark.parametrize("which", ["legacy", "first", "rejected", "incomplete"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_backup_requires_evidence_for_every_referenced_lifecycle(
    tmp_path: Path, which: str, damage: str
) -> None:
    app, ids = seed(tmp_path / "live")
    path = app.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{ids[which]}.bin")
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"corrupt synthetic object")
    with pytest.raises(RecoveryError):
        backup(app.store, boundary(tmp_path / "backup"), candidate_id="missing-required")
    assert not (tmp_path / "backup" / MANIFEST_NAME).exists()


@pytest.mark.parametrize("which", ["manifest", "database", "evidence"])
@pytest.mark.parametrize("damage", ["missing", "corrupt", "hardlink", "symlink"])
def test_restore_rejects_missing_corrupt_or_aliased_files(
    tmp_path: Path, which: str, damage: str
) -> None:
    app, _ = seed(tmp_path / "live")
    saved = boundary(tmp_path / "backup")
    manifest = backup(app.store, saved, candidate_id="damaged")
    path = saved.path(
        {
            "manifest": MANIFEST_NAME,
            "database": DATABASE_NAME,
            "evidence": manifest.evidence[0].reference,
        }[which]
    )
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(b"corrupt")
    elif damage == "hardlink":
        os.link(path, tmp_path / "alias")
    else:
        moved = tmp_path / "moved"
        path.rename(moved)
        path.symlink_to(moved)
    with pytest.raises(RecoveryError):
        restore(saved, boundary(tmp_path / "restored"))
    assert not (tmp_path / "restored" / DATABASE_NAME).exists()
    assert app.current().generation == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("format", "future-backup"),
        ("schema_version", 2),
        ("application_version", "99.0"),
        ("implementation_sha256", "0" * 64),
        ("candidate_id", "../escape"),
        ("created_at", "invalid"),
        ("unknown", "field"),
        ("schema_version", True),
    ],
)
def test_incompatible_or_invalid_manifests_fail_before_destination_creation(
    tmp_path: Path, field: str, value: object
) -> None:
    app = service(tmp_path / "live")
    backup(app.store, boundary(tmp_path / "backup"), candidate_id="incompatible")
    edit_manifest(tmp_path / "backup", field, value)
    with pytest.raises(RecoveryError):
        restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    assert not (tmp_path / "restored").exists()


@pytest.mark.parametrize(
    "mutation", ["duplicate_key", "duplicate_object", "traversal", "omitted", "extra", "state"]
)
def test_manifest_must_match_complete_database_references(tmp_path: Path, mutation: str) -> None:
    app, _ = seed(tmp_path / "live")
    saved = tmp_path / "backup"
    manifest = backup(app.store, boundary(saved), candidate_id="manifest")
    if mutation == "duplicate_key":
        path = saved / MANIFEST_NAME
        path.write_bytes(path.read_bytes().replace(b"{", b'{"schema_version":3,', 1))
    elif mutation == "state":
        edit_manifest(saved, "state", {**manifest.state.model_dump(), "generation": 1})
    else:
        evidence = [item.model_dump() for item in manifest.evidence]
        if mutation == "duplicate_object":
            evidence.insert(0, evidence[0])
        elif mutation == "traversal":
            evidence[0]["reference"] = "../escape"
        elif mutation == "omitted":
            evidence.pop()
        else:
            orphan = app.store.evidence.publish(b"unreferenced")
            path = saved / orphan.relative_reference
            path.write_bytes(b"unreferenced")
            evidence.append(
                {
                    "reference": orphan.relative_reference,
                    "sha256": orphan.raw_sha256,
                    "byte_length": orphan.byte_length,
                }
            )
            evidence.sort(key=lambda item: item["reference"])
        edit_manifest(saved, "evidence", evidence)
    with pytest.raises(RecoveryError):
        restore(boundary(saved), boundary(tmp_path / "restored"))
    assert not (tmp_path / "restored" / DATABASE_NAME).exists()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE import_commands SET generation=99 WHERE command_key='stale'",
        "UPDATE import_commands SET preview_sha256='bad' WHERE command_key='invalid'",
        "DELETE FROM import_commands WHERE command_key='first'",
        "UPDATE import_activations SET generation=3 WHERE generation=2",
        "UPDATE checkpoints SET canonical_text='{}' WHERE sequence=1",
        "UPDATE import_previews SET rejected_at='invalid' WHERE state='rejected'",
        "PRAGMA user_version=2",
    ],
)
def test_database_hash_is_not_a_substitute_for_full_state_validation(
    tmp_path: Path, sql: str
) -> None:
    app, _ = seed(tmp_path / "live")
    saved = tmp_path / "backup"
    backup(app.store, boundary(saved), candidate_id="relational")
    with closing(sqlite3.connect(saved / DATABASE_NAME)) as connection:
        connection.execute(sql)
        connection.commit()
    rehash_database(saved)
    with pytest.raises(RecoveryError):
        restore(boundary(saved), boundary(tmp_path / "restored"))
    assert not (tmp_path / "restored" / DATABASE_NAME).exists()
    assert app.current().generation == 2


@pytest.mark.parametrize(
    "step",
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
def test_abrupt_process_exit_never_exposes_an_incomplete_backup_or_ready_restore(
    tmp_path: Path, step: str
) -> None:
    live = tmp_path / "live"
    app, _ = seed(live)
    before = rows(live)
    if step.startswith("restore"):
        backup(app.store, boundary(tmp_path / "backup"), candidate_id="crash")
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
root, source, step = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def boundary(name): return RuntimeBoundary(root / name, source, 'synthetic')
def fail(name):
    if name == step: os._exit(73)
recovery._step = fail
if step.startswith('backup'):
    store = CheckpointStore(EvidenceStore(boundary('live')))
    recovery.backup(store, boundary('backup'), candidate_id='crash')
else:
    recovery.restore(boundary('backup'), boundary('restored'))
""",
            str(tmp_path),
            str(SOURCE),
            step,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 73, result.stderr
    assert rows(live) == before and app.current().generation == 2
    if step.startswith("backup"):
        with pytest.raises(RecoveryError):
            restore(boundary(tmp_path / "backup"), boundary(tmp_path / "new-restore"))
        assert not (tmp_path / "backup" / MANIFEST_NAME).exists()
    else:
        assert (tmp_path / "restored" / RESTORE_MARKER).is_file()
        with pytest.raises(PersistenceError, match="restore_incomplete"):
            service(tmp_path / "restored")
        # Valid backup remains reusable at a new isolated destination.
        restore(boundary(tmp_path / "backup"), boundary(tmp_path / "another-restore"))
        assert rows(tmp_path / "another-restore") == before


def test_backup_manifest_interrupted_between_link_and_unlink_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = service(tmp_path / "live")

    def half_publish(staged: Path, final: Path) -> None:
        os.link(staged, final)
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(recovery, "_publish", half_publish)
    with pytest.raises(RecoveryError):
        backup(app.store, boundary(tmp_path / "backup"), candidate_id="link-failure")
    with pytest.raises(RecoveryError):
        restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_io_failure_is_coded_and_preserves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    app, _ = seed(tmp_path / "live")
    backup(app.store, boundary(tmp_path / "backup"), candidate_id="io-failure")
    before = rows(tmp_path / "live")

    def fail(step: str) -> None:
        raise OSError("private path must not leak")

    monkeypatch.setattr(recovery, "_step", fail)
    with pytest.raises(RecoveryError, match=f"^{operation}_failed$"):
        if operation == "backup":
            backup(app.store, boundary(tmp_path / "new-backup"), candidate_id="io-failure")
        else:
            restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    assert rows(tmp_path / "live") == before


def test_private_boundary_qualification_uses_only_synthetic_scratch(tmp_path: Path) -> None:
    # This fake source/root arrangement exercises private-mode path separation;
    # every byte is still synthetic and remains in ignored test scratch.
    fake_source = tmp_path / "source"
    fake_source.mkdir()

    def private(name: str) -> RuntimeBoundary:
        return RuntimeBoundary(tmp_path / name, fake_source, "private")

    app = ImportService(CheckpointStore(EvidenceStore(private("live"))))
    identity = app.previews.stage(raw(document())).receipt.raw_sha256
    receipt = app.commit(identity, "first", 0)
    saved = backup(app.store, private("backup"), candidate_id="synthetic-private-qualification")
    assert restore(private("backup"), private("restored")) == saved
    reopened = ImportService(CheckpointStore(EvidenceStore(private("restored"))))
    assert reopened.current() == app.current()
    assert reopened.commit(identity, "first", 0) == receipt
    with pytest.raises(EvidenceError, match="private_source_overlap"):
        RuntimeBoundary(fake_source / "private", fake_source, "private")


@pytest.mark.parametrize("kind", ["database", "manifest", "objects"])
def test_resource_bounds_fail_without_publishing_ready_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    app, _ = seed(tmp_path / "live")
    if kind == "manifest":
        backup(app.store, boundary(tmp_path / "backup"), candidate_id="bounds")
        monkeypatch.setattr(recovery, "MAX_MANIFEST_BYTES", 16)
        with pytest.raises(RecoveryError, match="backup_size_exceeded"):
            restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
        assert not (tmp_path / "restored").exists()
    else:
        monkeypatch.setattr(
            recovery, "MAX_DATABASE_BYTES" if kind == "database" else "MAX_OBJECTS", 1
        )
        with pytest.raises(RecoveryError, match="backup_size_exceeded"):
            backup(app.store, boundary(tmp_path / "backup"), candidate_id="bounds")
        assert not (tmp_path / "backup" / MANIFEST_NAME).exists()


@pytest.mark.parametrize("candidate", ["", "../escape", "a" * 129])
def test_invalid_candidate_labels_fail_before_mutation(tmp_path: Path, candidate: str) -> None:
    app = service(tmp_path / "live")
    with pytest.raises(RecoveryError, match="invalid_candidate_identity"):
        backup(app.store, boundary(tmp_path / "backup"), candidate_id=candidate)
    assert not (tmp_path / "backup").exists()


def test_restore_does_not_mutate_backup_or_require_original_runtime(tmp_path: Path) -> None:
    app, ids = seed(tmp_path / "live")
    saved = tmp_path / "backup"
    manifest = backup(app.store, boundary(saved), candidate_id="independent")
    files = (manifest.database, *manifest.evidence)
    # Original evidence becomes unavailable. Restore must use only the backup.
    original = app.store.evidence.runtime.path(f"{STORAGE_VERSION}/objects/{ids['first']}.bin")
    original.unlink()
    restore(boundary(saved), boundary(tmp_path / "restored"))
    for item in files:
        data = (saved / item.reference).read_bytes()
        assert len(data) == item.byte_length and hashlib.sha256(data).hexdigest() == item.sha256
    assert service(tmp_path / "restored").current().generation == 2


def test_noncanonical_decimal_source_spelling_and_quantum_survive(tmp_path: Path) -> None:
    app = service(tmp_path / "live")
    data = document()
    data["lots"][0]["basis"]["value"] = "1000.00"
    data["positions"][0]["quantity"]["value"] = "12.000"
    original = raw(data)
    identity = app.previews.stage(original).receipt.raw_sha256
    assert app.commit(identity, "source-quantum", 0).outcome == "committed"
    backup(app.store, boundary(tmp_path / "backup"), candidate_id="source-quantum")
    restore(boundary(tmp_path / "backup"), boundary(tmp_path / "restored"))
    checkpoint = service(tmp_path / "restored").current().checkpoint
    assert checkpoint is not None and checkpoint.inspection.source.raw_bytes == original
    basis = checkpoint.inspection.source.document.lots[0].basis.value
    quantity = checkpoint.inspection.source.document.positions[0].quantity.value
    assert basis is not None and quantity is not None
    assert basis.original_text == "1000.00" and basis.source_quantum == Decimal("0.01")
    assert quantity.original_text == "12.000" and quantity.source_quantum == Decimal("0.001")
    assert basis.canonical == "1000" and quantity.canonical == "12"
