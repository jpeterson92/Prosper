"""Atomic synthetic activation: independent outcomes, real rollback and process races."""

import copy
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

import prosper.imports as imports
import prosper.persistence as persistence
from prosper.evidence import EvidenceError, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.imports import ImportError, ImportService
from prosper.persistence import DATABASE_NAME, CheckpointStore, PersistenceError
from prosper.previews import PreviewError

SOURCE = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]


def document() -> Document:
    return cast(Document, json.loads((SOURCE / "examples/synthetic/F001.json").read_bytes()))


def raw(data: Document) -> bytes:
    return json.dumps(data).encode()


@pytest.fixture
def service(tmp_path: Path) -> ImportService:
    return ImportService(
        CheckpointStore(EvidenceStore(RuntimeBoundary(tmp_path / "runtime", SOURCE, "synthetic")))
    )


def db(service: ImportService) -> sqlite3.Connection:
    return sqlite3.connect(service.store.evidence.runtime.path(DATABASE_NAME))


def stage(service: ImportService, data: Document | None = None) -> str:
    return service.previews.stage(raw(document() if data is None else data)).receipt.raw_sha256


def reopen(service: ImportService) -> ImportService:
    return ImportService(CheckpointStore(EvidenceStore(service.store.evidence.runtime)))


def counts(service: ImportService) -> tuple[int, ...]:
    with closing(db(service)) as connection:
        return tuple(
            connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in ("checkpoints", "import_activations", "import_commands")
        )


def test_f001_once_reopen_old_retries_and_duplicates_do_not_restore_history(
    service: ImportService,
) -> None:
    assert service.current().generation == 0 and service.current().checkpoint is None
    first = stage(service)
    receipt = service.commit(first, "first", 0)
    assert receipt.outcome == "committed" and receipt.generation == 1
    state = reopen(service).current()
    assert state.generation == 1 and state.checkpoint is not None
    inspected = state.checkpoint.inspection
    for value, expected in (
        (inspected.positions[0].quantity, "12"),
        (inspected.positions[1].quantity, "5"),
        (inspected.cash[0].settled, "319"),
        (inspected.settled_cash_nav, "2399"),
        (inspected.total_basis, "2181"),
    ):
        assert isinstance(value, ExactValue) and value.canonical == expected
    assert not inspected.readiness.planning_ready
    assert service.previews.get(first).state == "committed"
    assert service.previews.stage(raw(document())).state == "committed"
    with pytest.raises(PreviewError, match="committed_preview_cannot_reject"):
        service.previews.reject(first)
    data = document()
    data["metadata"]["source_version"] = "2"
    second = stage(service, data)
    assert service.commit(second, "second", 1).generation == 2
    assert reopen(service).commit(first, "first", 0) == receipt
    stale = service.commit(first, "old-distinct", 0)
    assert stale.outcome == "stale_generation" and stale.generation == 2
    duplicate = service.commit(first, "duplicate", 2)
    assert duplicate.outcome == "duplicate" and duplicate.activation_generation == 1
    assert duplicate.generation == 2 and counts(service) == (2, 2, 4)
    assert reopen(service).commit(first, "duplicate", 2) == duplicate
    assert service.current().checkpoint == service.store.get(second)
    for identity, retry_generation in ((second, 0), (first, 2)):
        with pytest.raises(ImportError, match="command_payload_mismatch"):
            service.commit(identity, "first", retry_generation)


@pytest.mark.parametrize("kind", ["F002", "F003", "F006", "malformed", "rejected"])
def test_ineligible_preview_receipts_preserve_active_state(
    service: ImportService, kind: str
) -> None:
    service.commit(stage(service), "base", 0)
    before = service.current()
    data = document()
    if kind == "F002":
        data["metadata"]["inclusion"] = {"value": None, "reason": "not_proven"}
    elif kind == "F003":
        data["lots"][0]["quantity"]["value"] = "11"
    elif kind == "F006":
        data["quotes"][0]["price"]["value"] = "0.1000000000001"
    else:
        data["metadata"]["source_version"] = "reject-me"
    identity = service.previews.stage(b"{" if kind == "malformed" else raw(data)).receipt.raw_sha256
    if kind == "rejected":
        service.previews.reject(identity)
    receipt = service.commit(identity, "blocked", 1)
    assert receipt.outcome == ("preview_rejected" if kind == "rejected" else "preview_invalid")
    assert reopen(service).commit(identity, "blocked", 1) == receipt
    assert service.current() == before and counts(service) == (1, 1, 2)


@pytest.mark.parametrize("kind", ["F004", "F009"])
def test_incomplete_facts_can_activate_without_financial_readiness(
    service: ImportService, kind: str
) -> None:
    data = document()
    if kind == "F004":
        data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    else:
        data["coverage"][0]["status"] = "unknown"
        data["coverage"][0]["evidence"] = {"value": None, "reason": "coverage_unknown"}
    assert service.commit(stage(service, data), "incomplete", 0).outcome == "committed"
    current = reopen(service).current().checkpoint
    assert current is not None and not current.inspection.readiness.planning_ready
    if kind == "F004":
        assert current.inspection.total_basis == UnknownValue(("source_missing",))
    else:
        assert current.inspection.readiness.coverage == "incomplete"


@pytest.mark.parametrize("change", ["quantity", "fees", "source_ref", "basis_treatment"])
def test_f005_conflict_against_older_committed_events_even_if_omitted_now(
    service: ImportService, change: str
) -> None:
    original = stage(service)
    service.commit(original, "original", 0)
    omitted = document()
    omitted["activity"] = []
    omitted["metadata"]["included_activity_ids"] = []
    latest = stage(service, omitted)
    service.commit(latest, "omitted", 1)
    data = document()
    data["metadata"]["source_version"] = "changed-version-cannot-bypass"
    event = data["activity"][0]
    if change == "quantity":
        event["quantity"]["value"] = "3"
        event["principal"]["value"] = "270"
        event["cash_movement"]["value"] = "-271"
    elif change == "fees":
        event["fees"]["value"] = "2"
        event["cash_movement"]["value"] = "-182"
    elif change == "source_ref":
        event["source_ref"] = "CHANGED-SOURCE-REF"
    else:
        event["basis_treatment"]["value"] = "changed treatment"
    identity = stage(service, data)
    assert service.previews.get(identity).inspection.validated is not None  # type: ignore[union-attr]
    result = service.commit(identity, "conflict", 2)
    assert result.outcome == "source_conflict" and result.activation_generation is None
    assert reopen(service).commit(identity, "conflict", 2) == result
    assert counts(service) == (2, 2, 3)
    assert service.current().checkpoint == service.store.get(latest)
    assert service.store.evidence.read(service.previews.get(identity).receipt) == raw(data)


@pytest.mark.parametrize(
    "change", ["profile", "account", "source", "account_mapping", "security_mapping"]
)
def test_identity_changes_require_review(service: ImportService, change: str) -> None:
    service.commit(stage(service), "base", 0)
    data = document()
    if change == "profile":
        data["metadata"]["profile_id"] = "OTHER-PROFILE"
        data["accounts"][0]["profile_id"] = "OTHER-PROFILE"
    elif change == "account":
        old = data["accounts"][0]["id"]
        data = cast(Document, json.loads(raw(data).replace(old.encode(), b"OTHER-ACCOUNT")))
    elif change == "source":
        data["metadata"]["source_id"] = "OTHER-SOURCE"
    elif change == "account_mapping":
        data["accounts"][0]["source_ref"] = "OTHER-MAPPING"
    else:
        data["securities"][0]["source_ref"] = "OTHER-MAPPING"
    assert service.commit(stage(service, data), "changed", 1).outcome == "identity_review_required"
    assert counts(service) == (1, 1, 2)


def test_account_namespace_and_uncommitted_events_do_not_conflict(service: ImportService) -> None:
    data = document()
    data["activity"][0]["source_ref"] = "unaccepted-change"
    ignored = stage(service, data)
    preview = service.previews.get(ignored)
    assert preview.inspection is not None and preview.inspection.validated is not None
    service.store.append(preview.inspection.validated)  # Immutable storage is not activation.
    service.previews.reject(ignored)
    service.commit(stage(service), "base", 0)
    data = document()
    monitor = copy.deepcopy(data["accounts"][0])
    monitor.update(id="MONITOR-2", source_ref="SRC-MONITOR-2", role="monitor_only")
    data["accounts"].append(monitor)
    data["activity"][0]["account_id"] = "MONITOR-2"
    data["activity"][0]["lot_ids"] = []
    data["activity"][0]["source_ref"] = "different-account-event"
    assert service.commit(stage(service, data), "monitor", 1).outcome == "committed"
    assert service.current().generation == 2


@pytest.mark.parametrize("failure", ["sql", "interrupt", "evidence_loss"])
def test_f007_actual_writes_roll_back_every_reference(
    service: ImportService, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    service.commit(stage(service), "base", 0)
    data = document()
    data["metadata"]["source_version"] = "next"
    identity = stage(service, data)
    evidence_path = service.store.evidence.runtime.path(
        service.previews.get(identity).receipt.relative_reference
    )

    def fail(connection: sqlite3.Connection) -> None:
        assert connection.execute("SELECT count(*) FROM checkpoints").fetchone() == (2,)
        assert connection.execute("SELECT max(generation) FROM import_activations").fetchone() == (
            2,
        )
        assert connection.execute("SELECT count(*) FROM import_commands").fetchone() == (2,)
        if failure == "sql":
            raise sqlite3.OperationalError("synthetic failure")
        if failure == "interrupt":
            raise KeyboardInterrupt()
        evidence_path.unlink()

    with monkeypatch.context() as patch:
        patch.setattr(imports, "_before_activation_commit", fail)
        with pytest.raises((ImportError, KeyboardInterrupt, EvidenceError)):
            service.commit(identity, "next", 1)
    assert counts(reopen(service)) == (1, 1, 1)
    assert reopen(service).current().generation == 1
    if failure == "evidence_loss":
        with pytest.raises(EvidenceError):
            service.commit(identity, "next", 1)
        # Explicit restoration for this test, never an implicit service repair.
        service.store.evidence.publish(raw(data))
    assert service.previews.get(identity).state == "staged"
    assert reopen(service).commit(identity, "next", 1).generation == 2


PROCESS = """
import json, os, sys
from pathlib import Path
import prosper.imports as imports
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.persistence import CheckpointStore
root, source, identity, key, mode = sys.argv[1:]
boundary = RuntimeBoundary(Path(root), Path(source), 'synthetic')
service = imports.ImportService(CheckpointStore(EvidenceStore(boundary)))
if mode == 'exit':
    imports._before_activation_commit = lambda connection: os._exit(23)
if mode == 'race':
    print('ready', flush=True)
    sys.stdin.readline()
try:
    result = service.commit(identity, key, 0)
    print(json.dumps([result.outcome, result.generation, result.activation_generation]))
except imports.ImportError as error:
    print(json.dumps([error.code]))
"""


def args(service: ImportService, identity: str, key: str, mode: str) -> list[str]:
    return [
        sys.executable,
        "-I",
        "-c",
        PROCESS,
        str(service.store.evidence.runtime.root),
        str(SOURCE),
        identity,
        key,
        mode,
    ]


def test_process_exit_before_commit_leaves_no_partial_state_and_restart_once(
    service: ImportService,
) -> None:
    identity = stage(service)
    failed = subprocess.run(
        args(service, identity, "restart", "exit"), capture_output=True, timeout=30
    )
    assert failed.returncode == 23, failed.stderr.decode()
    assert counts(reopen(service)) == (0, 0, 0)
    assert service.previews.get(identity).state == "staged"
    for _ in range(2):
        result = subprocess.run(
            args(service, identity, "restart", "normal"), capture_output=True, timeout=30
        )
        assert result.returncode == 0, result.stderr.decode()
        assert json.loads(result.stdout) == ["committed", 1, 1]
    assert counts(service) == (1, 1, 1)


@pytest.mark.parametrize("mode", ["distinct", "same", "collision"])
def test_f008_competing_processes_serialize_and_same_key_retries_share_outcome(
    service: ImportService, mode: str
) -> None:
    first = stage(service)
    data = document()
    data["metadata"]["source_version"] = "second"
    second = first if mode == "same" else stage(service, data)
    processes = [
        subprocess.Popen(
            args(service, identity, key, "race"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for identity, key in ((first, "a"), (second, "b" if mode == "distinct" else "a"))
    ]
    try:
        for process in processes:
            assert process.stdout is not None and process.stdout.readline().strip() == "ready"
        for process in processes:
            assert process.stdin is not None
            process.stdin.write("go\n")
            process.stdin.flush()
        outcomes = []
        for process in processes:
            output, error = process.communicate(timeout=30)
            assert process.returncode == 0, error
            outcomes.append(json.loads(output)[0])
        expected = {
            "same": ["committed", "committed"],
            "distinct": ["committed", "stale_generation"],
            "collision": ["command_payload_mismatch", "committed"],
        }
        assert sorted(outcomes) == expected[mode]
        assert counts(reopen(service)) == ((1, 1, 2) if mode == "distinct" else (1, 1, 1))
        assert service.current().generation == 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_evidence_damage_never_returns_clean_active_state_or_success_retry(
    service: ImportService, committed: bool, damage: str
) -> None:
    identity = stage(service)
    if committed:
        service.commit(identity, "base", 0)
    path = service.store.evidence.runtime.path(
        service.previews.get(identity).receipt.relative_reference
    )
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"corrupt")
    with pytest.raises(EvidenceError):
        service.commit(identity, "base", 0)
    if committed:
        with pytest.raises(EvidenceError):
            service.current()
    assert counts(service) == ((1, 1, 1) if committed else (0, 0, 0))


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM import_commands",
        "DELETE FROM import_activations",
        "UPDATE import_commands SET payload_sha256='wrong'",
        "UPDATE import_activations SET generation=3",
        "UPDATE import_previews SET state='staged'",
        "DELETE FROM checkpoints",
    ],
)
def test_corrupt_relational_state_is_explicit(service: ImportService, sql: str) -> None:
    service.commit(stage(service), "base", 0)
    with closing(db(service)) as connection, connection:
        connection.execute(sql)
    with pytest.raises(PersistenceError):
        service.current()


@pytest.mark.parametrize(
    "key,expected",
    [("", 0), ("x" * 129, 0), ("a/b", 0), ("key", -1), ("key", True), ("key", 2**63)],
)
def test_bounded_command_inputs(service: ImportService, key: str, expected: int) -> None:
    with pytest.raises(ImportError):
        service.commit(stage(service), key, expected)
    assert counts(service) == (0, 0, 0)


def version_two(
    service: ImportService,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with closing(db(service)) as connection, connection:
        connection.execute("DROP TABLE import_activations")
        connection.execute("DROP TABLE import_commands")
        connection.execute("ALTER TABLE import_previews RENAME TO new_previews")
        connection.execute(persistence._PREVIEW_SCHEMA_V2)
        connection.execute("INSERT INTO import_previews SELECT * FROM new_previews")
        connection.execute("DROP TABLE new_previews")
        connection.execute("PRAGMA user_version=2")
        CheckpointStore._check_schema(connection, version=2)
        return (
            connection.execute("SELECT * FROM checkpoints").fetchall(),
            connection.execute("SELECT * FROM import_previews").fetchall(),
        )


@pytest.mark.parametrize("interrupted", [False, True])
def test_schema_two_upgrade_preserves_rows_and_rolls_back(
    service: ImportService, monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    identity = stage(service)
    preview = service.previews.get(identity)
    assert preview.inspection is not None and preview.inspection.validated is not None
    service.store.append(preview.inspection.validated)
    data = document()
    data["metadata"]["source_version"] = "rejected"
    rejected = service.previews.reject(stage(service, data))
    checkpoints, previews = version_two(service)
    if interrupted:

        def fail(connection: sqlite3.Connection) -> None:
            raise sqlite3.OperationalError("synthetic upgrade failure")

        with monkeypatch.context() as patch:
            patch.setattr(persistence, "_before_upgrade_commit", fail)
            with pytest.raises(PersistenceError):
                reopen(service)
        with closing(db(service)) as connection:
            CheckpointStore._check_schema(connection, version=2)
            assert connection.execute("SELECT * FROM import_previews").fetchall() == previews
    restored = reopen(service)
    with closing(db(service)) as connection:
        assert connection.execute("SELECT * FROM checkpoints").fetchall() == checkpoints
        assert connection.execute("SELECT * FROM import_previews").fetchall() == previews
    assert restored.previews.get(identity) == preview
    assert restored.previews.get(rejected.receipt.raw_sha256) == rejected
    assert restored.current().generation == 0
    assert restored.commit(identity, "activate-preexisting", 0).generation == 1


def test_failed_receipt_retry_retains_original_outcome_after_later_commit(
    service: ImportService,
) -> None:
    identity = stage(service)
    failed = service.commit(identity, "too-early", 1)
    assert failed.outcome == "stale_generation" and failed.generation == 0
    assert service.commit(identity, "valid", 0).generation == 1
    assert reopen(service).commit(identity, "too-early", 1) == failed
    assert counts(service) == (1, 1, 2)


def test_missing_preview_does_not_record_outcome(service: ImportService) -> None:
    with pytest.raises(PreviewError, match="preview_missing"):
        service.commit("a" * 64, "missing", 0)
    assert counts(service) == (0, 0, 0)


def test_process_exit_during_schema_two_upgrade_is_atomic(service: ImportService) -> None:
    identity = stage(service)
    _, previews = version_two(service)
    script = PROCESS.replace(
        "service = imports.ImportService(CheckpointStore(EvidenceStore(boundary)))",
        "import prosper.persistence as p\np._before_upgrade_commit = lambda c: os._exit(24)\n"
        "service = imports.ImportService(CheckpointStore(EvidenceStore(boundary)))",
    )
    command = args(service, identity, "unused", "normal")
    command[3] = script
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 24, result.stderr.decode()
    with closing(db(service)) as connection:
        CheckpointStore._check_schema(connection, version=2)
        assert connection.execute("SELECT * FROM import_previews").fetchall() == previews
    assert reopen(service).commit(identity, "after-upgrade", 0).generation == 1


def test_changed_snapshot_basis_is_not_automatically_accepted_as_correction(
    service: ImportService,
) -> None:
    service.commit(stage(service), "base", 0)
    data = document()
    data["metadata"]["source_version"] = "basis-correction"
    data["lots"][0]["basis"]["value"] = "182"
    identity = stage(service, data)
    preview = service.previews.get(identity)
    assert preview.inspection is not None and preview.inspection.validated is not None
    assert service.commit(identity, "correction", 1).outcome == "source_conflict"
    assert counts(service) == (1, 1, 2)


def test_normalized_event_spelling_and_new_snapshots_are_allowed(service: ImportService) -> None:
    service.commit(stage(service), "base", 0)
    data = document()
    data["activity"][0]["quantity"]["value"] = "0002.000000000000"
    data["metadata"]["source_version"] = "new-format"
    data["metadata"]["cutoff"] = "2026-10-23T16:00:00-04:00"
    for quote in data["quotes"]:
        quote["as_of"]["value"] = data["metadata"]["cutoff"]
    assert service.commit(stage(service, data), "next-day", 1).outcome == "committed"
    assert service.current().generation == 2
