"""Synthetic SQLite integration: exact state, provenance, and real rollback."""

import json
import os
import sqlite3
import subprocess
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import prosper.persistence as persistence
from prosper.bundle import parse_bundle
from prosper.checkpoint import ValidatedCheckpoint, inspect_checkpoint
from prosper.evidence import EvidenceError, EvidenceReceipt, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, UnknownValue
from prosper.persistence import DATABASE_NAME, CheckpointStore, PersistenceError

SOURCE = Path(__file__).resolve().parents[1]
FIXTURES = SOURCE / "examples/synthetic"
type Document = dict[str, Any]


def document(name: str = "F001") -> Document:
    return json.loads((FIXTURES / f"{name}.json").read_bytes())  # type: ignore[no-any-return]


def valid(value: Document | bytes) -> ValidatedCheckpoint:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    parsed = parse_bundle(raw).parsed
    assert parsed is not None
    checkpoint = inspect_checkpoint(parsed).validated
    assert checkpoint is not None
    return checkpoint


@pytest.fixture
def store(tmp_path: Path) -> CheckpointStore:
    return CheckpointStore(
        EvidenceStore(RuntimeBoundary(tmp_path / "runtime", SOURCE, "synthetic"))
    )


def db(store: CheckpointStore) -> sqlite3.Connection:
    return sqlite3.connect(store.evidence.runtime.path(DATABASE_NAME))


def error(code: str) -> pytest.RaisesExc[PersistenceError]:
    return pytest.raises(PersistenceError, match=f"^{code}$")


def test_f000_f001_reopen_independent_values_and_sql_types(store: CheckpointStore) -> None:
    old = store.append(valid((FIXTURES / "F000.json").read_bytes()))
    current = store.append(valid((FIXTURES / "F001.json").read_bytes()))
    assert old.sequence == 1 and current.sequence == 2
    reopened = CheckpointStore(EvidenceStore(store.evidence.runtime))
    assert reopened.list_ids() == (old.receipt.raw_sha256, current.receipt.raw_sha256)
    assert reopened.get(old.receipt.raw_sha256) == old
    restored = reopened.get(current.receipt.raw_sha256)
    assert restored == current
    inspection = restored.inspection
    assert inspection.validated is not None and not inspection.readiness.planning_ready
    for value, expected in (
        (inspection.positions[0].quantity, "12"),
        (inspection.positions[1].quantity, "5"),
        (inspection.cash[0].settled, "319"),
        (inspection.settled_cash_nav, "2399"),
        (inspection.total_basis, "2181"),
        (inspection.market_minus_basis, "-101"),
    ):
        assert isinstance(value, ExactValue) and value.value == Decimal(expected)
    with db(store) as connection:
        row = connection.execute(
            """SELECT typeof(canonical_text),
            typeof(json_extract(canonical_text, '$.document.lots[0].basis.value')),
            json_extract(canonical_text, '$.document.lots[0].basis.value'),
            typeof(json_extract(canonical_text, '$.document.positions[0].quantity.value')),
            json_extract(canonical_text, '$.document.positions[0].quantity.value'),
            effective_at, recorded_at FROM checkpoints WHERE raw_sha256=?""",
            (current.receipt.raw_sha256,),
        ).fetchone()
        assert row[:5] == ("text", "text", "181", "text", "12")
        assert row[5] == "2026-10-22T16:00:00-04:00"
        assert row[6] == current.recorded_at and row[5] != row[6]
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
    ignored = subprocess.run(
        ["git", "check-ignore", str(store.evidence.runtime.root)], cwd=SOURCE, capture_output=True
    )
    assert ignored.returncode == 0


def test_duplicate_raw_and_new_source_version_keep_first_record(store: CheckpointStore) -> None:
    checkpoint = valid(document())
    first = store.append(checkpoint)
    assert store.append(checkpoint) == first
    changed = document()
    changed["metadata"]["source_version"] = "synthetic-revision-2"
    second = store.append(valid(changed))
    assert second.sequence == first.sequence + 1
    assert second.recorded_at != first.recorded_at
    assert datetime.fromisoformat(second.recorded_at) >= datetime.fromisoformat(first.recorded_at)
    assert (
        second.inspection.source.document.metadata.cutoff
        == checkpoint.source.document.metadata.cutoff
    )
    assert store.get(first.receipt.raw_sha256) == first
    assert store.get(second.receipt.raw_sha256) == second
    assert len(store.list_ids()) == 2


@pytest.mark.parametrize(
    "price", ["0.000000000001", "9999999999999999999999999999", "00090.500000000000"]
)
def test_decimal_extremes_preserve_original_quantum_and_text(
    store: CheckpointStore, price: str
) -> None:
    data = document()
    data["quotes"][0]["price"]["value"] = price
    data["positions"][1]["quantity"]["value"] = "5.125000000000"
    data["lots"][2]["quantity"]["value"] = "5.125000000000"
    data["activity"][0]["cash_movement"]["value"] = "-000181.000000000000"
    data["cash"][0]["available"]["value"] = "000.000000000000"
    original = valid(data)
    saved = store.append(original)
    restored = CheckpointStore(store.evidence).get(saved.receipt.raw_sha256).inspection.source
    quote = restored.document.quotes[0].price.value
    assert quote is not None and quote.original_text == price
    assert (
        quote.source_quantum == Decimal("0.000000000001")
        if "." in price
        else quote.source_quantum == 1
    )
    assert restored.raw_bytes == original.source.raw_bytes
    assert restored.canonical_bytes == original.source.canonical_bytes
    quantity = restored.document.lots[2].quantity.value
    assert quantity is not None and quantity.canonical == "5.125"
    assert quantity.original_text == "5.125000000000" and quantity.source_quantum == Decimal(
        "1e-12"
    )
    with db(store) as connection:
        assert connection.execute(
            """SELECT typeof(json_extract(canonical_text, '$.document.quotes[0].price.value')),
            json_extract(canonical_text, '$.document.quotes[0].price.value'),
            json_extract(canonical_text, '$.document.activity[0].cash_movement.value'),
            json_extract(canonical_text, '$.document.cash[0].available.value')
            FROM checkpoints"""
        ).fetchone() == ("text", quote.canonical, "-181", "0")
    if len(price) == 28:
        assert isinstance(saved.inspection.settled_cash_nav, UnknownValue)
        assert any(f.code == "derived_value_unsupported" for f in saved.inspection.findings)


def test_unknown_pairs_survive_without_zero_or_planning_claim(store: CheckpointStore) -> None:
    data = document()
    data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    data["coverage"][0]["status"] = "unknown"
    data["coverage"][0]["evidence"] = {"value": None, "reason": "household_unknown"}
    saved = store.append(valid(data))
    restored = CheckpointStore(store.evidence).get(saved.receipt.raw_sha256).inspection
    assert restored.total_basis == UnknownValue(("source_missing",))
    assert restored.readiness.basis == restored.readiness.coverage == "incomplete"
    assert not restored.readiness.planning_ready
    # Canonical sorting places LOT-A-NEW before LOT-A-OLD.
    with db(store) as connection:
        row = connection.execute(
            """SELECT json_type(canonical_text, '$.document.lots[0].basis.value'),
            typeof(json_extract(canonical_text, '$.document.lots[0].basis.value')),
            json_extract(canonical_text, '$.document.lots[0].basis.reason') FROM checkpoints"""
        ).fetchone()
        assert row == ("null", "null", "source_missing")


@pytest.mark.parametrize(
    "change", ["raw_hash", "canonical", "document", "account", "invalid_input"]
)
def test_fabricated_validated_input_never_creates_row(store: CheckpointStore, change: str) -> None:
    checkpoint = valid(document())
    source = checkpoint.source
    expected = "checkpoint_identity_mismatch"
    if change == "raw_hash":
        source = replace(source, raw_sha256="0" * 64)
    elif change == "canonical":
        source = replace(source, canonical_bytes=b"{}")
    elif change == "document":
        source = replace(source, document=valid(document("F000")).source.document)
    elif change == "account":
        checkpoint = replace(checkpoint, traded_account_id="fictional-wrong-account")
    else:
        source = replace(source, raw_bytes=b"invalid synthetic json")
        expected = "stored_input_invalid"
    with error(expected):
        store.append(replace(checkpoint, source=source))
    assert store.list_ids() == ()
    assert not list(store.evidence.runtime.root.rglob("*.bin"))


def test_contradictory_input_and_nonvalidated_object_rejected(store: CheckpointStore) -> None:
    data = document()
    data["lots"][0]["quantity"]["value"] = "11"
    parsed = parse_bundle(json.dumps(data).encode()).parsed
    assert parsed is not None
    with error("checkpoint_not_validated"):
        store.append(ValidatedCheckpoint(parsed, "DEMO-TAXABLE-1"))
    with error("validated_checkpoint_required"):
        store.append(parsed)  # type: ignore[arg-type]
    assert store.list_ids() == ()


def test_real_transaction_rollback_keeps_prior_and_retains_unreferenced_evidence(
    store: CheckpointStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = store.append(valid(document("F000")))

    def fail_after_insert(connection: sqlite3.Connection) -> None:
        assert connection.execute("SELECT count(*) FROM checkpoints").fetchone() == (2,)
        raise sqlite3.OperationalError("synthetic private SQL failure")

    monkeypatch.setattr(persistence, "_before_commit", fail_after_insert)
    with error("database_append_failed") as caught:
        store.append(valid(document()))
    assert caught.value.__suppress_context__
    reopened = CheckpointStore(store.evidence)
    assert reopened.list_ids() == (prior.receipt.raw_sha256,)
    assert reopened.get(prior.receipt.raw_sha256) == prior
    assert len(list(store.evidence.runtime.root.rglob("*.bin"))) == 2


def test_publication_failure_and_wrong_receipts_leave_database_unchanged(
    store: CheckpointStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = store.append(valid(document("F000")))
    checkpoint = valid(document())
    with error("evidence_checkpoint_mismatch"):
        store.append(checkpoint, prior.receipt)
    missing = EvidenceReceipt(
        checkpoint.source.raw_sha256,
        len(checkpoint.source.raw_bytes),
        f"evidence-bytes-v1/objects/{checkpoint.source.raw_sha256}.bin",
    )
    with pytest.raises(EvidenceError, match="^evidence_missing$"):
        store.append(checkpoint, missing)

    def fail(raw: bytes) -> EvidenceReceipt:
        raise EvidenceError("evidence_publication_failed")

    monkeypatch.setattr(store.evidence, "publish", fail)
    with pytest.raises(EvidenceError, match="^evidence_publication_failed$"):
        store.append(checkpoint)
    assert store.list_ids() == (prior.receipt.raw_sha256,)
    assert store.get(prior.receipt.raw_sha256) == prior


def test_evidence_lost_after_insert_rolls_back_reference(
    store: CheckpointStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = store.append(valid(document("F000")))
    checkpoint = valid(document())

    def lose_evidence(connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT evidence_reference FROM checkpoints WHERE raw_sha256=?",
            (checkpoint.source.raw_sha256,),
        ).fetchone()
        store.evidence.runtime.path(row[0]).unlink()

    monkeypatch.setattr(persistence, "_before_commit", lose_evidence)
    with pytest.raises(EvidenceError, match="^evidence_missing$"):
        store.append(checkpoint)
    assert CheckpointStore(store.evidence).list_ids() == (prior.receipt.raw_sha256,)
    assert store.get(prior.receipt.raw_sha256) == prior


def test_canonical_json_constraint_and_corruption_check(store: CheckpointStore) -> None:
    saved = store.append(valid(document()))
    with db(store) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE checkpoints SET canonical_text='invalid synthetic JSON'")
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute("UPDATE checkpoints SET canonical_text='invalid synthetic JSON'")
    with error("stored_metadata_mismatch"):
        store.get(saved.receipt.raw_sha256)


def test_schema_guard_does_not_ignore_similar_internal_name(store: CheckpointStore) -> None:
    with db(store) as connection:
        connection.execute("CREATE TABLE sqliteXunexpected (value TEXT)")
    with error("incompatible_database_schema"):
        store.list_ids()


def test_private_mode_database_uses_same_validated_runtime(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-source"
    source.mkdir()
    runtime = tmp_path / "synthetic-private-runtime"
    boundary = RuntimeBoundary(runtime, source, "private")
    private_mode_store = CheckpointStore(EvidenceStore(boundary))
    saved = private_mode_store.append(valid(document()))
    assert CheckpointStore(EvidenceStore(boundary)).get(saved.receipt.raw_sha256) == saved
    assert (runtime / DATABASE_NAME).is_file()
    assert not list(source.iterdir())


@pytest.mark.parametrize("mutation", ["missing", "changed", "multiple_links"])
def test_changed_evidence_after_close_blocks_load_and_duplicate(
    store: CheckpointStore, mutation: str
) -> None:
    checkpoint = valid(document())
    saved = store.append(checkpoint)
    path = store.evidence.runtime.path(saved.receipt.relative_reference)
    if mutation == "missing":
        path.unlink()
        expected = "evidence_missing"
    elif mutation == "changed":
        path.write_bytes(b"synthetic changed evidence")
        expected = "evidence_identity_mismatch"
    else:
        os.link(path, store.evidence.runtime.root / "synthetic-link.bin")
        expected = "untrusted_file_type_or_links"
    reopened = CheckpointStore(store.evidence)
    with pytest.raises(EvidenceError, match=f"^{expected}$"):
        reopened.get(saved.receipt.raw_sha256)
    # Explicit missing receipt cannot be healed silently by a duplicate append.
    with pytest.raises(EvidenceError, match=f"^{expected}$"):
        reopened.append(checkpoint, saved.receipt)
    with pytest.raises(EvidenceError, match=f"^{expected}$"):
        reopened.append(checkpoint)


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_text", "{}"),
        ("canonical_sha256", "0" * 64),
        ("source_version", "wrong-version"),
        ("effective_at", "wrong-time"),
        ("recorded_at", "2026-10-22"),
        ("inspection_version", "future-inspection"),
    ],
)
def test_stored_payload_or_metadata_tampering_is_not_trusted(
    store: CheckpointStore, field: str, value: str
) -> None:
    saved = store.append(valid(document()))
    with db(store) as connection:
        connection.execute(f"UPDATE checkpoints SET {field}=?", (value,))
    code = "stored_recorded_time_invalid" if field == "recorded_at" else "stored_metadata_mismatch"
    with error(code):
        CheckpointStore(store.evidence).get(saved.receipt.raw_sha256)


@pytest.mark.parametrize("mutation", ["version", "application", "schema", "empty", "foreign"])
def test_incompatible_database_never_migrates_or_initializes_silently(
    store: CheckpointStore, mutation: str
) -> None:
    path = store.evidence.runtime.path(DATABASE_NAME)
    if mutation == "empty":
        path.write_bytes(b"")
    elif mutation == "foreign":
        path.write_bytes(b"synthetic not SQLite")
    else:
        with db(store) as connection:
            connection.execute(
                {
                    "version": "PRAGMA user_version=2",
                    "application": "PRAGMA application_id=0",
                    "schema": "CREATE TABLE unexpected (x TEXT)",
                }[mutation]
            )
    before = path.read_bytes()
    code = (
        "database_initialization_failed"
        if mutation == "foreign"
        else "incompatible_database_schema"
    )
    with error(code):
        CheckpointStore(store.evidence)
    assert path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_database_and_sidecar_symlinks_rejected_before_access(
    store: CheckpointStore, tmp_path: Path, suffix: str
) -> None:
    target = tmp_path / "synthetic-target"
    target.write_bytes(b"synthetic must remain unchanged")
    path = store.evidence.runtime.root / (DATABASE_NAME + suffix)
    if not suffix:
        path.unlink()
    try:
        path.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Host lacks Windows symlink privilege; runtime junction tests are separate")
        raise
    with pytest.raises(EvidenceError, match="^redirected_path$"):
        store.list_ids()
    assert target.read_bytes() == b"synthetic must remain unchanged"


def test_hardlinked_database_and_invalid_or_missing_id_fail(store: CheckpointStore) -> None:
    for identity in ("", "../escape", "A" * 64):
        with error("invalid_checkpoint_identity"):
            store.get(identity)
    with error("checkpoint_missing"):
        store.get("a" * 64)
    os.link(
        store.evidence.runtime.root / DATABASE_NAME, store.evidence.runtime.root / "alias.sqlite3"
    )
    with error("untrusted_database_file"):
        store.list_ids()
