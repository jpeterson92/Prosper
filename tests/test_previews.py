"""Durable synthetic previews: independently specified values and actual rollback."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

import prosper.persistence as persistence
import prosper.previews as previews
from prosper.bundle import MAX_BYTES, parse_bundle
from prosper.checkpoint import inspect_checkpoint
from prosper.evidence import EvidenceError, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.persistence import DATABASE_NAME, CheckpointStore, PersistenceError
from prosper.previews import ImportPreview, PreviewError, PreviewService

SOURCE = Path(__file__).resolve().parents[1]
FIXTURES = SOURCE / "examples/synthetic"
type Document = dict[str, Any]


def document() -> Document:
    return cast(Document, json.loads((FIXTURES / "F001.json").read_bytes()))


def raw(data: Document) -> bytes:
    return json.dumps(data).encode()


@pytest.fixture
def service(tmp_path: Path) -> PreviewService:
    evidence = EvidenceStore(RuntimeBoundary(tmp_path / "runtime", SOURCE, "synthetic"))
    return PreviewService(CheckpointStore(evidence))


def connect(service: PreviewService) -> sqlite3.Connection:
    return sqlite3.connect(service.store.evidence.runtime.path(DATABASE_NAME))


def seed(service: PreviewService, data: bytes) -> None:
    parsed = parse_bundle(data).parsed
    assert parsed is not None
    validated = inspect_checkpoint(parsed).validated
    assert validated is not None
    service.store.append(validated)


def count(service: PreviewService) -> int:
    with closing(connect(service)) as connection:
        return cast(int, connection.execute("SELECT count(*) FROM import_previews").fetchone()[0])


def legacy(service: PreviewService) -> list[tuple[object, ...]]:
    # Exact prior schema: the unchanged checkpoint table, application marker,
    # user_version=1, and no workflow tables. Preserve populated rows verbatim.
    with closing(connect(service)) as connection, connection:
        connection.execute("DROP TABLE import_previews")
        connection.execute("DROP TABLE import_activations")
        connection.execute("DROP TABLE import_commands")
        connection.execute("PRAGMA user_version=1")
        persistence.CheckpointStore._check_schema(connection, version=1)
        return connection.execute("SELECT * FROM checkpoints").fetchall()


def test_f001_preview_reject_repeat_reopen_preserves_checkpoint_inventory(
    service: PreviewService,
) -> None:
    seed(service, (FIXTURES / "F000.json").read_bytes())
    prior = tuple(service.store.get(i) for i in service.store.list_ids())
    data = (FIXTURES / "F001.json").read_bytes()
    staged = service.stage(data)
    assert staged.state == "staged" and staged.rejected_at is None
    assert staged.inspection is not None
    inspection = staged.inspection
    for value, expected in (
        (inspection.positions[0].quantity, "12"),
        (inspection.positions[1].quantity, "5"),
        (inspection.cash[0].settled, "319"),
        (inspection.settled_cash_nav, "2399"),
        (inspection.total_basis, "2181"),
    ):
        assert isinstance(value, ExactValue) and value.canonical == expected
    assert not inspection.readiness.planning_ready
    assert service.stage(data) == staged and count(service) == 1
    rejected = service.reject(staged.receipt.raw_sha256)
    assert rejected.state == "rejected" and rejected.rejected_at is not None
    assert rejected.recorded_at == staged.recorded_at
    reopened = PreviewService(CheckpointStore(EvidenceStore(service.store.evidence.runtime)))
    assert reopened.get(staged.receipt.raw_sha256) == rejected
    assert reopened.reject(staged.receipt.raw_sha256) == rejected
    assert reopened.stage(data) == rejected and count(service) == 1
    assert tuple(service.store.get(i) for i in service.store.list_ids()) == prior
    assert reopened.store.evidence.read(rejected.receipt) == data


@pytest.mark.parametrize("variant", ["F002", "F003", "F004", "F006", "F009"])
def test_invalid_and_incomplete_variants_remain_review_evidence(
    service: PreviewService, variant: str
) -> None:
    data = document()
    if variant == "F002":
        data["metadata"]["inclusion"] = {"value": None, "reason": "inclusion_unproven"}
    elif variant == "F003":
        data["lots"][0]["quantity"]["value"] = "11"
    elif variant == "F004":
        data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    elif variant == "F006":
        data["quotes"][0]["price"]["value"] = "0.1000000000001"
    else:
        data["coverage"][0]["status"] = "unknown"
        data["coverage"][0]["evidence"] = {"value": None, "reason": "household_unknown"}
    preview = service.stage(raw(data))
    assert service.get(preview.receipt.raw_sha256) == preview
    assert service.store.list_ids() == ()
    if variant == "F006":
        assert preview.inspection is None and preview.parsing.issues
        assert any(issue.path[:2] == ("quotes", 0) for issue in preview.parsing.issues)
    else:
        inspection = preview.inspection
        assert inspection is not None and not inspection.readiness.planning_ready
        if variant in ("F002", "F003"):
            assert inspection.validated is None
            assert any(f.blocking and f.path for f in inspection.findings)
        elif variant == "F004":
            assert inspection.validated is not None
            assert inspection.total_basis == UnknownValue(("source_missing",))
            assert inspection.readiness.basis == "incomplete"
        else:
            assert inspection.readiness.coverage == "incomplete"


@pytest.mark.parametrize("data", [b"", b"\xff", b"{", b'{"x":1,"x":2}', b"[]"])
def test_bounded_malformed_bytes_survive_rejection(service: PreviewService, data: bytes) -> None:
    saved = service.stage(data)
    assert saved.inspection is None and saved.parsing.issues
    rejected = service.reject(saved.receipt.raw_sha256)
    assert service.get(saved.receipt.raw_sha256) == rejected
    assert service.store.evidence.read(saved.receipt) == data
    assert service.store.list_ids() == ()


def test_size_type_rejection_precedes_publication(
    service: PreviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(data: bytes) -> None:
        pytest.fail("unbounded input reached publication")

    monkeypatch.setattr(service.store.evidence, "publish", forbidden)
    for data, code in (
        (b"x" * (MAX_BYTES + 1), "byte_limit_exceeded"),
        ("x", "byte_payload_required"),
    ):
        with pytest.raises(PreviewError, match="^preview_input_rejected$") as caught:
            service.stage(cast(bytes, data))
        assert caught.value.issues[0].code == code
    assert count(service) == 0


def test_changed_source_spelling_keeps_distinct_evidence(service: PreviewService) -> None:
    data = document()
    first = service.stage(raw(data))
    data["quotes"][0]["price"]["value"] = "00090.000000000000"
    second = service.stage(raw(data))
    assert first.receipt.raw_sha256 != second.receipt.raw_sha256
    assert first.parsing.parsed is not None and second.parsing.parsed is not None
    assert first.parsing.parsed.canonical_sha256 == second.parsing.parsed.canonical_sha256
    value = second.parsing.parsed.document.quotes[0].price.value
    assert value is not None and value.original_text == "00090.000000000000"
    assert count(service) == 2


@pytest.mark.parametrize("operation", ["get", "reject"])
@pytest.mark.parametrize("identity", ["bad", "A" * 64, "0" * 64])
def test_invalid_or_missing_identity(
    service: PreviewService, operation: str, identity: str
) -> None:
    expected = "preview_missing" if identity == "0" * 64 else "invalid_preview_identity"
    with pytest.raises(PreviewError, match=f"^{expected}$"):
        getattr(service, operation)(identity)
    assert count(service) == 0


@pytest.mark.parametrize("operation", ["stage", "reject"])
@pytest.mark.parametrize("failure", [sqlite3.OperationalError, KeyboardInterrupt])
def test_actual_write_rollback_preserves_prior_state(
    service: PreviewService,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    failure: type[BaseException],
) -> None:
    prior = service.stage((FIXTURES / "F000.json").read_bytes())

    def fail(connection: sqlite3.Connection) -> None:
        assert connection.in_transaction
        raise failure()

    with monkeypatch.context() as patch:
        patch.setattr(previews, "_before_preview_commit", fail)
        expected = PreviewError if issubclass(failure, sqlite3.Error) else failure
        with pytest.raises(expected):
            if operation == "stage":
                service.stage(raw(document()))
            else:
                service.reject(prior.receipt.raw_sha256)
    reopened = PreviewService(CheckpointStore(service.store.evidence))
    assert reopened.get(prior.receipt.raw_sha256) == prior and count(service) == 1
    assert reopened.store.list_ids() == ()
    if operation == "stage":
        data = raw(document())
        digest = hashlib.sha256(data).hexdigest()
        orphan = service.store.evidence.runtime.path(f"evidence-bytes-v1/objects/{digest}.bin")
        assert orphan.read_bytes() == data


def test_publication_failure_creates_no_reference(
    service: PreviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(data: bytes) -> None:
        raise EvidenceError("synthetic_publication_failure")

    monkeypatch.setattr(service.store.evidence, "publish", fail)
    with pytest.raises(EvidenceError, match="synthetic_publication_failure"):
        service.stage(raw(document()))
    assert count(service) == 0


@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_broken_evidence_blocks_get_reject_and_duplicate_without_repair(
    service: PreviewService, mutation: str
) -> None:
    data = raw(document())
    saved = service.stage(data)
    path = service.store.evidence.runtime.path(saved.receipt.relative_reference)
    if mutation == "missing":
        path.unlink()
    else:
        path.write_bytes(b"synthetic corruption")
    operations: tuple[Callable[[], ImportPreview], ...] = (
        lambda: service.get(saved.receipt.raw_sha256),
        lambda: service.reject(saved.receipt.raw_sha256),
        lambda: service.stage(data),
    )
    for operation in operations:
        with pytest.raises(EvidenceError):
            operation()
    with closing(connect(service)) as connection:
        assert connection.execute("SELECT state FROM import_previews").fetchone() == ("staged",)


def test_staging_cannot_repair_missing_checkpoint_evidence(service: PreviewService) -> None:
    data = raw(document())
    seed(service, data)
    stored = service.store.get(service.store.list_ids()[0])
    path = service.store.evidence.runtime.path(stored.receipt.relative_reference)
    path.unlink()
    with pytest.raises(EvidenceError, match="evidence_missing"):
        service.stage(data)
    assert not path.exists() and count(service) == 0


def test_loss_after_insert_rolls_back_reference(
    service: PreviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def lose(connection: sqlite3.Connection) -> None:
        reference = connection.execute("SELECT evidence_reference FROM import_previews").fetchone()[
            0
        ]
        service.store.evidence.runtime.path(reference).unlink()

    monkeypatch.setattr(previews, "_before_preview_commit", lose)
    with pytest.raises(EvidenceError, match="evidence_missing"):
        service.stage(raw(document()))
    assert count(service) == 0


def test_backward_clock_cannot_record_rejection_before_staging(
    service: PreviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = service.stage(raw(document()))
    monkeypatch.setattr(previews, "_now", lambda: "1900-01-01T00:00:00.000000Z")
    with pytest.raises(PreviewError, match="stored_preview_transition_invalid"):
        service.reject(saved.receipt.raw_sha256)
    assert service.get(saved.receipt.raw_sha256) == saved


def test_sql_lifecycle_constraints_reject_inconsistent_states(service: PreviewService) -> None:
    service.stage(raw(document()))
    with closing(connect(service)) as connection, connection:
        for sql in (
            "UPDATE import_previews SET state='unsupported'",
            "UPDATE import_previews SET state='committed', rejected_at='invalid'",
            "UPDATE import_previews SET state='rejected'",
            "UPDATE import_previews SET rejected_at='2026-10-23T00:00:00.000000Z'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(sql)


@pytest.mark.parametrize(
    "field,value",
    [
        ("preview_version", "future-preview"),
        ("recorded_at", "2026-10-22"),
        ("state", "committed"),
        ("rejected_at", "2026-10-23T00:00:00.000000Z"),
        ("evidence_length", 1),
        ("evidence_reference", "../synthetic-escape"),
    ],
)
def test_metadata_corruption_never_returns_clean_preview(
    service: PreviewService, field: str, value: str | int
) -> None:
    saved = service.stage(raw(document()))
    with closing(connect(service)) as connection, connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"UPDATE import_previews SET {field}=?", (value,))
    with pytest.raises((PersistenceError, EvidenceError)):
        service.get(saved.receipt.raw_sha256)


def test_upgrade_preserves_all_checkpoint_rows_and_append_behavior(service: PreviewService) -> None:
    for name in ("F000", "F001"):
        seed(service, (FIXTURES / f"{name}.json").read_bytes())
    data = document()
    data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    data["quotes"][0]["price"]["value"] = "00090.000000000000"
    seed(service, raw(data))
    old = tuple(service.store.get(i) for i in service.store.list_ids())
    rows = legacy(service)
    reopened = PreviewService(CheckpointStore(service.store.evidence))
    with closing(connect(service)) as connection:
        assert connection.execute("SELECT * FROM checkpoints").fetchall() == rows
        assert connection.execute("PRAGMA user_version").fetchone() == (3,)
    assert tuple(reopened.store.get(i) for i in reopened.store.list_ids()) == old
    seed(reopened, raw(data))
    assert len(reopened.store.list_ids()) == 3
    assert reopened.stage(raw(data)).inspection == old[-1].inspection


def test_failed_upgrade_restores_exact_prior_schema_and_rows(
    service: PreviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(service, raw(document()))
    rows = legacy(service)

    def fail(connection: sqlite3.Connection) -> None:
        assert connection.in_transaction
        assert connection.execute("PRAGMA user_version").fetchone() == (3,)
        raise sqlite3.OperationalError("synthetic upgrade interruption")

    with monkeypatch.context() as patch:
        patch.setattr(persistence, "_before_upgrade_commit", fail)
        with pytest.raises(PersistenceError, match="database_initialization_failed"):
            CheckpointStore(service.store.evidence)
    with closing(connect(service)) as connection:
        persistence.CheckpointStore._check_schema(connection, version=1)
        assert connection.execute("SELECT * FROM checkpoints").fetchall() == rows
    assert CheckpointStore(service.store.evidence).list_ids()


@pytest.mark.parametrize("version", [1, 2])
def test_altered_schema_cannot_be_upgraded_or_opened(service: PreviewService, version: int) -> None:
    if version == 1:
        legacy(service)
    with closing(connect(service)) as connection, connection:
        connection.execute("CREATE TABLE unexpected (value TEXT)")
    path = service.store.evidence.runtime.path(DATABASE_NAME)
    before = path.read_bytes()
    with pytest.raises(PersistenceError, match="incompatible_database_schema"):
        CheckpointStore(service.store.evidence)
    assert path.read_bytes() == before


def test_process_exit_during_upgrade_leaves_v1_recoverable(service: PreviewService) -> None:
    seed(service, raw(document()))
    rows = legacy(service)
    script = """
import os, sys
from pathlib import Path
import prosper.persistence as p
from prosper.evidence import EvidenceStore, RuntimeBoundary
p._before_upgrade_commit = lambda connection: os._exit(23)
p.CheckpointStore(EvidenceStore(RuntimeBoundary(Path(sys.argv[1]), Path(sys.argv[2]), 'synthetic')))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(service.store.evidence.runtime.root), str(SOURCE)],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 23, result.stderr.decode()
    with closing(connect(service)) as connection:
        persistence.CheckpointStore._check_schema(connection, version=1)
        assert connection.execute("SELECT * FROM checkpoints").fetchall() == rows
    assert CheckpointStore(service.store.evidence).list_ids()
