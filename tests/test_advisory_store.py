"""Advisory user-work preservation, safe retries and explicit legacy mapping."""

import hashlib
import json
import runpy
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue, ValidationError

import prosper.advisory_store as module
from prosper import basket
from prosper.advisory_legacy import export_checkpoint, map_checkpoint
from prosper.advisory_records import (
    DecimalFact,
    Fact,
    Finding,
    ImportSnapshot,
    Lot,
    Position,
    SavedSuggestion,
    Security,
)
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.imports import ImportService
from prosper.persistence import CheckpointStore, PersistenceError

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-10-23T20:00:00Z"
RAW = b"fictional source: ABC,12.5000,basis unknown\n"


def snapshot(raw: bytes = RAW) -> ImportSnapshot:
    return ImportSnapshot(
        source_type="fictional-csv",
        source_name="fictional.csv",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        account_id="account-a",
        account_alias="Fictional account",
        account_scope="one-taxable-account",
        source_as_of=AS_OF,
        securities=(
            Security(
                id="security-a",
                source_ref="row:1",
                ticker="ABC",
                identity=Fact[str](value="fictional-stable-identity"),
                classification=Fact[str](value=None, reason="classification not supplied"),
            ),
        ),
        lots=(
            Lot(
                id="lot-a",
                account_id="account-a",
                security_id="security-a",
                source_ref="row:1",
                quantity=DecimalFact(value="12.5000"),
                total_basis=DecimalFact(value=None, reason="basis not supplied"),
                acquired=Fact[str](value=None, reason="date not supplied"),
                term=Fact[str](value=None, reason="term not supplied"),
            ),
        ),
        positions=(
            Position(
                id="position-a",
                account_id="account-a",
                security_id="security-a",
                source_ref="row:1",
                quantity=DecimalFact(value="12.5000"),
            ),
        ),
        cash=(),
    )


@pytest.fixture
def store(tmp_path: Path) -> AdvisoryStore:
    return AdvisoryStore(RuntimeBoundary(tmp_path / "advisory", ROOT, "synthetic"))


def select(store: AdvisoryStore) -> str:
    identity = store.stage(snapshot(), RAW)
    assert store.select(identity, "first", 0) == {"outcome": "changed", "revision": 1}
    return identity


def start(store: AdvisoryStore, identity: str = "run-a", revision: int = 1) -> None:
    store.start_run(
        identity,
        revision,
        inputs={
            "ordered_securities": ["security-a"],
            "sessions": ["2026-10-23"],
            "marks": {"security-a": 10.0},
        },
        application_version="test-v1",
        model_version="estimates-v1",
        as_of=AS_OF,
    )


def counts(store: AdvisoryStore) -> tuple[int, ...]:
    with closing(sqlite3.connect(store.runtime.path(DATABASE_NAME))) as connection:
        return tuple(
            connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in ("sources", "snapshots", "commands", "runs", "suggestions")
        )


def test_import_sources_unknowns_decimals_and_reopen(store: AdvisoryStore) -> None:
    identity = select(store)
    assert store.stage(snapshot(), RAW) == identity
    assert store.select(identity, "second", 1)["outcome"] == "duplicate"
    reopened = AdvisoryStore.existing(store.runtime)
    assert reopened.current()["revision"] == 1
    saved = reopened.snapshot(identity)
    assert saved.lots[0].quantity.value == "12.5000"
    assert saved.lots[0].total_basis.value is None
    assert saved.lots[0].total_basis.reason == "basis not supplied"
    assert saved.securities[0].classification.value is None
    assert reopened.source(identity) == RAW
    assert counts(reopened) == (1, 1, 2, 0, 0)
    # Reimporting the same bytes with explicit different as-of metadata is a
    # separate preview sharing one source copy, never a transaction stream.
    alternate = snapshot().model_copy(update={"source_name": "renamed.csv"})
    other = store.stage(alternate, RAW)
    assert other != identity and counts(store)[:2] == (1, 2)
    assert len(cast(list[JsonValue], store.catalog()["snapshots"])) == 2


def test_atomic_replacement_and_original_retry_after_new_import(store: AdvisoryStore) -> None:
    old = select(store)
    raw = RAW + b"changed"
    new = store.stage(snapshot(raw), raw)
    receipt = store.select(new, "replacement", 1)
    assert receipt == {"outcome": "changed", "revision": 2}
    assert store.select(old, "first", 0) == {"outcome": "changed", "revision": 1}
    assert store.current()["snapshot_id"] == new
    assert store.select(old, "stale", 1)["outcome"] == "stale_revision"
    with pytest.raises(PersistenceError, match="command_key_reused"):
        store.select(old, "replacement", 2)
    assert store.snapshot(old) == snapshot()


def test_rejected_and_account_mismatch_do_not_change_selection(store: AdvisoryStore) -> None:
    old = select(store)
    identity = store.stage(snapshot().model_copy(update={"source_name": "rejected"}), RAW)
    store.reject(identity)
    store.reject(identity)
    assert store.select(identity, "rejected", 1)["outcome"] == "preview_rejected"
    with pytest.raises(PersistenceError, match="selected_snapshot"):
        store.reject(old)
    changed = snapshot().model_copy(update={"account_scope": "other account"})
    other = store.stage(changed, RAW)
    assert store.select(other, "account", 1)["outcome"] == "account_review_required"
    assert store.current()["snapshot_id"] == old


def test_failure_after_real_writes_rolls_back_every_selection_write(
    store: AdvisoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = select(store)
    other = store.stage(snapshot().model_copy(update={"source_name": "replacement"}), RAW)
    before = counts(store)

    def fail(connection: sqlite3.Connection) -> None:
        assert connection.execute("SELECT snapshot_id FROM state").fetchone() == (other,)
        raise RuntimeError("fictional interruption")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_before_commit", fail)
        with pytest.raises(RuntimeError, match="interruption"):
            store.select(other, "retry", 1)
    assert AdvisoryStore.existing(store.runtime).current()["snapshot_id"] == old
    assert counts(store) == before
    assert store.select(other, "retry", 1)["outcome"] == "changed"


def test_stage_and_completion_failures_preserve_user_work(
    store: AdvisoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    select(store)
    start(store)
    before = counts(store)

    def fail(connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("private OS detail must not escape")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_before_commit", fail)
        with pytest.raises(PersistenceError, match="^advisory_database_unavailable$"):
            store.complete_run("run-a", outputs={"nav": 125.0}, status="partial")
        with pytest.raises(PersistenceError):
            store.stage(snapshot(RAW + b"2"), RAW + b"2")
    assert store.run("run-a").status == "running" and counts(store) == before
    assert store.current()["revision"] == 1


def test_saved_analysis_settings_outputs_and_historical_view_do_not_recompute(
    store: AdvisoryStore,
) -> None:
    old = select(store)
    store.configure(
        {"additional_cash": "0.00", "final_cash_target": None, "risk_enabled": False}, "settings", 1
    )
    start(store, revision=2)
    exclusions = (Finding(code="basis_missing", locator="lots/lot-a", reason="basis not supplied"),)
    outputs: dict[str, JsonValue] = {"holdings_value": 125.0, "loss_estimate": None}
    result = store.complete_run(
        "run-a",
        outputs=outputs,
        status="partial",
        exclusions=exclusions,
        warnings=("History is incomplete; no wash-sale clearance is implied.",),
    )
    assert store.current()["current_run_id"] == "run-a"
    assert result.snapshot_id == old and result.settings["additional_cash"] == "0.00"
    assert result.exclusions == exclusions and result.outputs["loss_estimate"] is None
    assert (
        store.complete_run(
            "run-a",
            outputs=outputs,
            status="partial",
            exclusions=exclusions,
            warnings=result.warnings,
        )
        == result
    )
    with pytest.raises(PersistenceError, match="immutable"):
        store.complete_run("run-a", outputs={"holdings_value": 126.0}, status="partial")
    store.configure({"additional_cash": "5.00"}, "new-settings", 2)
    assert store.current()["current_run_id"] is None
    assert AdvisoryStore.existing(store.runtime).run("run-a") == result
    start(store, revision=2)  # Identical old start retry returns saved run.
    assert store.catalog()["runs"] == ["run-a"]


def test_stale_input_and_out_of_order_results_cannot_publish(store: AdvisoryStore) -> None:
    select(store)
    start(store)
    start(store, "newer")
    store.complete_run("newer", outputs={"nav": 125.0}, status="complete")
    store.complete_run("run-a", outputs={"nav": 124.0}, status="complete")
    assert store.current()["current_run_id"] == "newer"
    start(store, "old-inputs")
    store.configure({"cash": "0"}, "change", 1)
    store.complete_run("old-inputs", outputs={"nav": 125.0}, status="complete")
    assert store.current()["current_run_id"] is None
    assert store.run("old-inputs").outputs == {"nav": 125.0}
    with pytest.raises(PersistenceError, match="stale_revision"):
        start(store, "stale-start")
    with pytest.raises(PersistenceError, match="analysis_id_reused"):
        start(store, "run-a", 2)


def test_unvalidated_suggestion_round_trip_and_edits_create_new_records(
    store: AdvisoryStore,
) -> None:
    select(store)
    start(store)
    suggestion = SavedSuggestion(
        id="worksheet-a",
        run_id="run-a",
        saved_at=AS_OF,
        export_as_of=AS_OF,
        worksheet={"lines": [], "estimated_cash": 0.0},
        assumptions=("Synthetic diagnostic worksheet",),
        warnings=("Not validated for trading",),
    )
    with pytest.raises(PersistenceError, match="completed_analysis_required"):
        store.save_suggestion(suggestion)
    store.complete_run("run-a", outputs={"nav": 125.0}, status="partial")
    assert store.save_suggestion(suggestion) == suggestion
    assert store.save_suggestion(suggestion) == suggestion
    changed = suggestion.model_copy(update={"worksheet": {"lines": [], "estimated_cash": 1.0}})
    with pytest.raises(PersistenceError, match="immutable"):
        store.save_suggestion(changed)
    store.save_suggestion(changed.model_copy(update={"id": "worksheet-b"}))
    assert AdvisoryStore.existing(store.runtime).suggestion("worksheet-a") == suggestion
    assert counts(store)[-1] == 2


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_settings_inputs_and_outputs_never_persist(
    store: AdvisoryStore, bad: float
) -> None:
    select(store)
    start(store)
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.configure({"value": bad}, "bad", 1)
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.start_run(
            "bad",
            1,
            inputs={"value": bad},
            application_version="v1",
            model_version="v1",
            as_of=AS_OF,
        )
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.complete_run("run-a", outputs={"value": bad}, status="complete")
    assert counts(store)[2:4] == (1, 1)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-1", "1e999", ""])
def test_invalid_source_decimal_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        DecimalFact(value=text)


@pytest.mark.parametrize("text", ["", " "])
def test_missing_identity_cannot_be_disguised_as_known_text(text: str) -> None:
    with pytest.raises(ValidationError):
        Fact[str](value=text)


def test_bad_source_and_nested_mutations_cannot_be_staged(store: AdvisoryStore) -> None:
    with pytest.raises(PersistenceError, match="source_checksum_or_size_invalid"):
        store.stage(snapshot(), b"wrong source")
    mutated = snapshot()
    mutated.observations["estimate"] = float("nan")
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.stage(mutated, RAW)
    duplicate = snapshot().model_copy(update={"lots": (snapshot().lots[0],) * 2})
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.stage(duplicate, RAW)
    unresolved = snapshot().lots[0].model_copy(update={"security_id": "not-mapped"})
    with pytest.raises(PersistenceError, match="invalid_advisory_record"):
        store.stage(snapshot().model_copy(update={"lots": (unresolved,)}), RAW)
    assert counts(store) == (0, 0, 0, 0, 0)


def test_legacy_export_mapping_preserves_old_selected_state(store: AdvisoryStore) -> None:
    legacy = ImportService(CheckpointStore(EvidenceStore(store.runtime)))
    raw = (ROOT / "examples/synthetic/F001.json").read_bytes()
    preview = legacy.previews.stage(raw)
    identity = preview.receipt.raw_sha256
    legacy.commit(identity, "legacy-first", 0)
    before = legacy.current()
    mapped = map_checkpoint(legacy.store, identity)
    assert export_checkpoint(legacy.store, identity) == raw
    new = store.stage(mapped, raw)
    store.select(new, "mapped-first", 0)
    assert legacy.current() == before
    assert store.source(new) == raw
    assert [x.quantity.value for x in mapped.positions] == ["12", "5"]
    assert mapped.lots[0].total_basis.value is not None
    assert mapped.observations["activity"]  # Retained, never reapplied.
    assert mapped.findings[0].code == "legacy_mapping"
    with pytest.raises(PersistenceError):
        map_checkpoint(legacy.store, "history-object-is-not-a-checkpoint")


def test_legacy_maximum_length_cash_id_maps_without_truncation_collision(
    store: AdvisoryStore,
) -> None:
    legacy = ImportService(CheckpointStore(EvidenceStore(store.runtime)))
    document = json.loads((ROOT / "examples/synthetic/F001.json").read_bytes())
    document["cash"][0]["id"] = "a" * 128
    raw = json.dumps(document).encode()
    identity = legacy.previews.stage(raw).receipt.raw_sha256
    legacy.commit(identity, "legacy-first", 0)
    mapped = map_checkpoint(legacy.store, identity)
    assert len({cash.id for cash in mapped.cash}) == len(mapped.cash)
    assert all(len(cash.id) <= 128 for cash in mapped.cash)
    new = store.stage(mapped, raw)
    assert store.source(new) == raw


def test_new_estimate_inputs_outputs_and_code_independent_historical_view(
    store: AdvisoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = runpy.run_path(str(ROOT / "scripts/qualify_advisory.py"))
    reference = cast(Callable[[], basket.BasketInput], helper["reference"])
    data = reference()
    inputs = cast(dict[str, JsonValue], json.loads(json.dumps(asdict(data))))
    raw = json.dumps(inputs).encode()
    imported = snapshot(raw).model_copy(
        update={
            "source_type": "fictional-basket",
            "securities": tuple(
                Security(
                    id=key,
                    source_ref=key,
                    ticker=key,
                    identity=Fact[str](value=key),
                    classification=Fact[str](value="fictional-equity"),
                )
                for key in data.universe
            ),
            "positions": tuple(
                Position(
                    id=p.row_id,
                    account_id="account-a",
                    security_id=p.security.security_id or "",
                    source_ref=p.row_id,
                    quantity=DecimalFact(value=p.quantity.raw),
                )
                for p in data.positions
            ),
            "lots": (),
        }
    )
    identity = store.stage(imported, raw)
    store.select(identity, "estimate-input", 0)
    store.start_run(
        "run-a",
        1,
        inputs=inputs,
        application_version="estimate-app-v1",
        model_version="advisory-basket-v1",
        as_of=AS_OF,
    )
    estimate = basket.estimate(data)
    outputs = cast(dict[str, JsonValue], json.loads(json.dumps(asdict(estimate), allow_nan=False)))
    result = store.complete_run("run-a", outputs=outputs, status="complete")
    assert result.outputs["version"] == "advisory-basket-v1"
    assert result.outputs["portfolio_nav_usd"] == 3.0
    assert result.inputs == inputs
    assert store.source(identity) == raw

    def changed_code(data: basket.BasketInput) -> basket.BasketEstimate:
        raise AssertionError("historical reads cannot invoke the current estimator")

    monkeypatch.setattr(basket, "estimate", changed_code)
    assert AdvisoryStore.existing(store.runtime).run("run-a").outputs == outputs


def test_missing_source_bytes_do_not_hide_saved_outputs(store: AdvisoryStore) -> None:
    identity = select(store)
    start(store)
    expected = store.complete_run("run-a", outputs={"nav": 125.0}, status="partial")
    with closing(sqlite3.connect(store.runtime.path(DATABASE_NAME))) as connection:
        connection.execute("DELETE FROM sources")
        connection.commit()
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        store.source(identity)
    assert AdvisoryStore.existing(store.runtime).run("run-a") == expected


def test_date_only_source_has_no_invented_time_and_corrupt_source_cannot_be_reimported(
    store: AdvisoryStore,
) -> None:
    imported = snapshot().model_copy(update={"source_as_of": "2026-10-23"})
    identity = store.stage(imported, RAW)
    assert store.snapshot(identity).source_as_of == "2026-10-23"
    with closing(sqlite3.connect(store.runtime.path(DATABASE_NAME))) as connection:
        connection.execute("UPDATE sources SET raw=?", (b"corrupt bytes",))
        connection.commit()
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        store.stage(imported, RAW)
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        store.select(identity, "corrupt", 0)
    assert store.current()["snapshot_id"] is None


def test_simultaneous_replacement_only_one_writer_wins(store: AdvisoryStore) -> None:
    old = select(store)
    first = store.stage(snapshot().model_copy(update={"source_name": "first"}), RAW)
    second = store.stage(snapshot().model_copy(update={"source_name": "second"}), RAW)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: store.select(*args), [(first, "writer-a", 1), (second, "writer-b", 1)]
            )
        )
    assert sorted(str(x["outcome"]) for x in results) == ["changed", "stale_revision"]
    assert store.current()["revision"] == 2
    assert store.current()["snapshot_id"] in (first, second)
    assert store.snapshot(old) == snapshot()


def test_process_death_during_pending_transaction_rolls_back(store: AdvisoryStore) -> None:
    old = select(store)
    other = store.stage(snapshot().model_copy(update={"source_name": "new"}), RAW)
    script = """
import os, sys
from pathlib import Path
import prosper.advisory_store as m
from prosper.evidence import RuntimeBoundary
store=m.AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'))
def crash(connection):
    os._exit(23)
m._before_commit=crash
store.select(sys.argv[3], 'process-retry', 1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(store.runtime.root), str(ROOT), other],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 23, result.stderr
    reopened = AdvisoryStore.existing(store.runtime)
    assert reopened.current()["snapshot_id"] == old
    assert reopened.select(other, "process-retry", 1)["outcome"] == "changed"


def test_pending_transaction_serializes_another_process_before_revision_check(
    store: AdvisoryStore,
) -> None:
    identity = select(store)
    script = """
import json, sys
from pathlib import Path
from prosper.advisory_store import AdvisoryStore
from prosper.evidence import RuntimeBoundary
store=AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'))
print('ready', flush=True)
print(json.dumps(store.select(sys.argv[3], 'waiting-writer', 1)), flush=True)
"""
    with closing(sqlite3.connect(store.runtime.path(DATABASE_NAME))) as connection:
        connection.execute("BEGIN IMMEDIATE")
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(store.runtime.root), str(ROOT), identity],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "ready"
            assert process.poll() is None
            connection.execute("UPDATE state SET revision=2,settings='{}' WHERE id=1")
            connection.commit()
            output, errors = process.communicate(timeout=30)
            assert process.returncode == 0, errors
            assert json.loads(output) == {"outcome": "stale_revision", "revision": 2}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=30)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
    assert store.current()["snapshot_id"] == identity


def test_missing_corrupt_and_unsupported_database_never_become_empty_state(
    store: AdvisoryStore,
) -> None:
    path = store.runtime.path(DATABASE_NAME)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(PersistenceError, match="incompatible_advisory_schema"):
        AdvisoryStore(store.runtime)
    assert path.exists()
    path.write_bytes(b"corrupt fictional database")
    with pytest.raises(PersistenceError, match="advisory_database_unavailable"):
        AdvisoryStore(store.runtime)
    assert path.read_bytes() == b"corrupt fictional database"
    path.unlink()
    with pytest.raises(PersistenceError, match="advisory_database_unavailable"):
        AdvisoryStore.existing(store.runtime)
    assert not path.exists()


def test_restore_marker_and_hardlink_alias_block_reads(store: AdvisoryStore) -> None:
    marker = store.runtime.path("restore-in-progress")
    marker.write_text("incomplete")
    with pytest.raises(PersistenceError, match="restore_incomplete"):
        store.current()
    marker.unlink()
    alias = store.runtime.root / "alias.sqlite3"
    alias.hardlink_to(store.runtime.path(DATABASE_NAME))
    try:
        with pytest.raises(PersistenceError, match="untrusted_database_file"):
            store.current()
    finally:
        alias.unlink()
