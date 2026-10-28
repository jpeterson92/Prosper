"""Cash treatment uses source amounts once and never creates stock trades or funding."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from prosper.advisory_records import Cash, DecimalFact, Fact, ImportSnapshot, Position
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import DiagnosticRequest, HistoryDiagnosticRequest
from prosper.candidate_records import BuyOrder, CandidateRequest, Orders, SaleOrder
from prosper.candidate_validation import validate
from prosper.cash_treatment import CashTreatmentRequest, apply, holdings
from prosper.fidelity_import import normalize
from prosper.lot_opportunities import evaluate, retained_activities, screening_inputs
from prosper.lot_records import (
    Activity,
    FidelityContext,
    LotDiagnosticRequest,
    LotSettings,
    Restriction,
    ScreeningFacts,
)
from prosper.modeled_inputs import ModeledUpload, union
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "examples/synthetic/fidelity"
RAW = (FOLDER / "cash-holdings.csv").read_bytes()
NOW = datetime.now(UTC).isoformat()


def source() -> ImportSnapshot:
    context = FidelityContext.model_validate_json((FOLDER / "current-context.json").read_bytes())
    context = context.model_copy(
        update={
            "source_sha256": hashlib.sha256(RAW).hexdigest(),
            "mappings": tuple(m for m in context.mappings if m.symbol == "FAAA"),
            "independent_positions": (),
        }
    )
    snapshot, inspection = normalize(RAW, context)
    assert snapshot is not None and not snapshot.observations["selection_blockers"]
    assert len(inspection.observations) == 4
    return snapshot


def money(snapshot: ImportSnapshot) -> str:
    return next(s.id for s in snapshot.securities if s.ticker == "FMMXX")


def service(path: Path) -> Workspace:
    return Workspace(AdvisoryStore(RuntimeBoundary(path)))


def request(
    identity: str,
    sid: str,
    kind: str | None = "cash-equivalent",
    revision: int = 1,
    key: str = "cash",
) -> CashTreatmentRequest:
    return CashTreatmentRequest.model_validate(
        {
            "snapshot_id": identity,
            "security_id": sid,
            "kind": kind,
            "expected_revision": revision,
            "command_key": key,
        }
    )


def test_reported_names_values_unknowns_and_no_position_lot_double_counting() -> None:
    snapshot = source()
    rows = holdings(snapshot)
    assert [r.ticker for r in rows] == ["FMMXX", "FUNK"]
    assert rows[0].name.value == "Fictional Money Market Fund"
    assert rows[0].reported_value.value == "100.00"  # $40.10 + $59.90, not 12 shares * $1.
    assert rows[1].reported_value.value is None
    unknown_cash = apply(snapshot, rows[1].security_id, "cash", NOW)
    unknown_row = next(
        row for row in holdings(unknown_cash) if row.security_id == rows[1].security_id
    )
    assert unknown_row.treatment is not None and unknown_row.reported_value.value is None
    assert len(snapshot.lots) == 4 and not snapshot.cash
    position = Position(
        id="independent",
        account_id=snapshot.account_id,
        security_id=money(snapshot),
        source_ref="position:1",
        quantity=DecimalFact(value="12"),
        reported_value=DecimalFact(value="100.00"),
    )
    matched = snapshot.model_copy(update={"positions": (position,)})
    assert holdings(matched)[0].reported_value.value == "100.00"  # Never $200.
    bad = position.model_copy(update={"reported_value": DecimalFact(value="99.00")})
    value = holdings(snapshot.model_copy(update={"positions": (bad,)}))[0].reported_value
    assert value.value is None and "contradict" in str(value.reason)
    missing = position.model_copy(
        update={"reported_value": DecimalFact(value=None, reason="Source value missing")}
    )
    assert (
        holdings(snapshot.model_copy(update={"positions": (missing,)}))[0].reported_value.value
        is None
    )


def test_atomic_treatment_undo_retry_stale_historical_outputs_and_recovery(tmp_path: Path) -> None:
    w = service(tmp_path / "source")
    original = source()
    identity = w.store.stage(original, RAW)
    w.store.select(identity, "select", 0)
    w.store.configure({"additional_cash": "7.00"}, "settings", 1)
    run = w.diagnose(DiagnosticRequest(run_id="before", expected_revision=2, as_of=NOW))
    command = request(identity, money(original), revision=2)
    assert w.store.treat_cash(command) == {"outcome": "changed", "revision": 3}
    after = w.store.current()
    assert after["current_run_id"] is None and after["settings"] == {"additional_cash": "7.00"}
    assert after["snapshot_id"] != identity
    changed = w.store.snapshot(str(after["snapshot_id"]))
    assert changed.lots == original.lots and changed.securities == original.securities
    assert changed.findings == original.findings and changed.exclusions == original.exclusions
    assert changed.observations == original.observations and not changed.cash
    assert w.store.source(str(after["snapshot_id"])) == RAW
    assert w.store.run("before") == run and w.store.snapshot(identity) == original
    assert w.store.treat_cash(command) == {"outcome": "changed", "revision": 3}
    assert w.store.current() == after
    stale = request(str(after["snapshot_id"]), money(original), "cash", revision=2, key="stale")
    assert w.store.treat_cash(stale)["outcome"] == "stale_revision"
    with pytest.raises(PersistenceError, match="command_key_reused"):
        w.store.treat_cash(request(identity, money(original), "cash", revision=2))
    target = service(tmp_path / "restored")
    restore(target.store, backup(w.store))
    assert target.store.current() == after
    assert target.preview(str(after["snapshot_id"])) == w.preview(str(after["snapshot_id"]))
    assert target.store.run("before") == run
    w.store.treat_cash(
        request(str(after["snapshot_id"]), money(original), None, revision=3, key="undo")
    )
    assert w.store.current()["snapshot_id"] == identity
    assert w.store.current()["settings"] == {"additional_cash": "7.00"}
    assert w.store.run("before") == run
    assert not w.store.snapshot(identity).cash_treatments
    # Older selected views of the same bytes cannot undo the current treatment,
    # and conversely the current undo cannot inherit their former treatment.
    assert len(retained_activities((changed, original))) < len(
        retained_activities((original, changed))
    )


def test_concurrent_edits_only_one_revision_wins_and_failed_commit_rolls_back(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "source")
    snapshot = source()
    identity = w.store.stage(snapshot, RAW)
    w.store.select(identity, "select", 0)
    before = w.store.current()
    with patch("prosper.advisory_store._before_commit", side_effect=RuntimeError("interrupted")):
        with pytest.raises(RuntimeError):
            w.store.treat_cash(request(identity, money(snapshot)))
    snapshots = w.store.catalog()["snapshots"]
    assert isinstance(snapshots, list)
    assert w.store.current() == before and len(snapshots) == 1
    commands = [
        request(identity, money(snapshot), kind, key=kind) for kind in ("cash", "cash-equivalent")
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(w.store.treat_cash, commands))
    assert sorted(str(r["outcome"]) for r in results) == ["changed", "stale_revision"]
    assert w.store.current()["revision"] == 2


def test_wrong_holding_known_equity_source_refs_future_and_existing_cash_refuse(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "source")
    snapshot = source()
    identity = w.store.stage(snapshot, RAW)
    w.store.select(identity, "select", 0)
    for sid in ("missing", "security-faaa"):
        with pytest.raises(PersistenceError, match="cash_treatment_invalid"):
            w.store.treat_cash(request(identity, sid, key=sid))
    with pytest.raises(PersistenceError, match="cash_treatment_snapshot_changed"):
        w.store.treat_cash(request("f" * 64, money(snapshot)))
    changed = apply(snapshot, money(snapshot), "cash", NOW)
    document = changed.model_dump(mode="json")
    document["cash_treatments"][0]["source_refs"] = ["unrelated-row"]
    with pytest.raises(ValueError):
        ImportSnapshot.model_validate_json(json.dumps(document))
    for field, value in (
        ("source_sha256", "f" * 64),
        ("account_id", "other-account"),
        ("source_as_of", "2026-10-24"),
    ):
        document = changed.model_dump(mode="json")
        document["cash_treatments"][0][field] = value
        with pytest.raises(ValueError, match="cash_treatment_source_mismatch"):
            ImportSnapshot.model_validate_json(json.dumps(document))
    with pytest.raises(ValueError, match="future_cash_treatment"):
        apply(snapshot, money(snapshot), "cash", "2099-01-01T00:00:00Z")
    cash = Cash(
        id="already",
        account_id=snapshot.account_id,
        source_ref=changed.cash_treatments[0].source_refs[0],
        amount=DecimalFact(value="40.10"),
        kind="reported",
    )
    with pytest.raises(ValueError, match="cash_treatment_source_mismatch"):
        apply(snapshot.model_copy(update={"cash": (cash,)}), money(snapshot), "cash", NOW)
    assert w.store.current()["revision"] == 1


def test_stock_universe_lot_metrics_and_screening_keep_known_restrictions() -> None:
    original = source()
    changed = apply(original, money(original), "cash-equivalent", NOW)
    bundle = ModeledUpload.model_validate_json(
        (ROOT / "examples/synthetic/modeled-inputs/current.json").read_bytes()
    ).bundle
    bundle = bundle.model_copy(update={"candidate_security_ids": ()})
    old_ids, _, _ = union(original, None, bundle)
    ids, _, exclusions = union(changed, None, bundle)
    assert set(ids) == set(old_ids) - {money(original)}
    assert any(e.code == "user_cash_treatment" for e in exclusions)
    retained = screening_inputs((changed, original))
    before = screening_inputs((original,))
    assert set(before.restrictions) <= set(retained.restrictions)
    assert changed.observations["screening"] == original.observations["screening"]
    original_own = {
        a.id
        for a in before.activities
        if a.identity.value is None and a.source_ref in changed.cash_treatments[0].source_refs
    }
    assert original_own and original_own.isdisjoint({a.id for a in retained.activities})
    facts = dict(changed.observations)
    screening = ScreeningFacts.model_validate_json(json.dumps(facts["screening"]))
    external = Activity(
        id="independent",
        identity=Fact[str](value=None, reason="Independent unknown activity"),
        account_ref=changed.account_id,
        account_scope=changed.account_scope,
        day=Fact[str](value="2026-10-23"),
        side="acquisition",
        quantity=DecimalFact(value="1"),
        pnl=Fact[str](value=None, reason="Not supplied"),
        source_ref=changed.cash_treatments[0].source_refs[0],
    )
    facts["screening"] = screening.model_copy(
        update={"activities": (*screening.activities, external)}
    ).model_dump(mode="json")
    assert external in retained_activities((changed.model_copy(update={"observations": facts}),))
    settings = LotSettings.model_validate_json((FOLDER / "current-lot-settings.json").read_bytes())
    result = evaluate(
        changed,
        retained,
        settings,
        LotDiagnosticRequest(run_id="lots", expected_revision=1, as_of=NOW),
    )
    cash_rows = [r for r in result.rows if r.security_id == money(original)]
    assert len(result.rows) == len(original.lots) and len(cash_rows) == 2
    assert all(
        r.status == "cash-treatment"
        and r.proposed_whole_shares is None
        and r.price_basis_loss.value is None
        for r in cash_rows
    )


def test_missing_required_source_refuses_recovery_and_fresh_input_has_no_treatment(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "source")
    snapshot = source()
    identity = w.store.stage(snapshot, RAW)
    w.store.select(identity, "select", 0)
    w.store.treat_cash(request(identity, money(snapshot)))
    with sqlite3.connect(tmp_path / "source" / DATABASE_NAME) as connection:
        connection.execute("DELETE FROM sources")
    with pytest.raises(PersistenceError):
        backup(w.store)
    # A refreshed source is normalized independently and carries no old treatment.
    assert not source().cash_treatments


def test_history_diagnostic_requires_stocks_without_requiring_user_cash_history(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "history")
    original = source()
    allowed = {s.id for s in original.securities if s.ticker != "FUNK"}
    original = original.model_copy(
        update={
            "securities": tuple(s for s in original.securities if s.id in allowed),
            "lots": tuple(lot for lot in original.lots if lot.security_id in allowed),
        }
    )
    identity = w.store.stage(original, RAW)
    w.store.select(identity, "select", 0)
    w.store.treat_cash(request(identity, money(original)))
    bundle = ModeledUpload.model_validate_json(
        (ROOT / "examples/synthetic/modeled-inputs/current.json").read_bytes()
    ).bundle
    stock = next(s.id for s in original.securities if s.ticker == "FAAA")
    series = bundle.history.series[0].model_copy(update={"security_id": stock})
    required = bundle.history.model_copy(update={"series": (series,), "manual_security_ids": ()})
    result = w.diagnose_history(
        HistoryDiagnosticRequest(
            request=required, run_id="stock-history", expected_revision=2, as_of=NOW
        )
    )
    assert result.outputs["ordered_securities"] == [stock]
    assert result.outputs["coverage_complete"] is False  # No history was invented.


def test_current_cash_treatment_keeps_known_conflicts_and_never_creates_candidate_funding() -> None:
    request = CandidateRequest.model_validate_json(
        (ROOT / "examples/synthetic/candidates/tiny-request.json").read_bytes()
    )
    original = request.snapshot
    imported = source()
    sid = money(imported)
    security = next(s for s in imported.securities if s.id == sid)
    lots = tuple(
        lot.model_copy(update={"account_id": original.account_id})
        for lot in imported.lots
        if lot.security_id == sid
    )
    extended = original.model_copy(
        update={"securities": (*original.securities, security), "lots": (*original.lots, *lots)}
    )
    extended = apply(extended, sid, "cash-equivalent", NOW)
    candidate = request.model_copy(
        update={
            "snapshot": extended,
            "sale_bounds": {**request.sale_bounds, **{lot.id: 0 for lot in lots}},
        }
    )
    orders = Orders(
        sales=(SaleOrder(lot_id="lot-a", shares=2),),
        buys=(BuyOrder(security_id="security-fbbb", shares=1),),
    )
    baseline = validate(request, orders)
    check = validate(candidate, orders)
    assert check.feasible and baseline.metrics == check.metrics
    assert check.metrics is not None and check.metrics.price_loss == 4
    # The $100 reported money-market value adds no financing to the $0 budget.
    assert check.metrics.final_cash == 10
    bad = candidate.model_copy(update={"sale_bounds": {**candidate.sale_bounds, lots[0].id: 1}})
    assert "cash_treatment_not_a_stock_sale" in validate(bad, orders).blockers
    bad_buy = candidate.model_copy(update={"buy_bounds": {**candidate.buy_bounds, sid: 1}})
    assert "cash_treatment_not_a_stock_purchase" in validate(bad_buy, orders).blockers
    stock = original.securities[0]
    known = Restriction(
        name="Known restriction", identity=stock.identity, source_ref="known-restriction"
    )
    facts = ScreeningFacts.model_validate_json(json.dumps(extended.observations["screening"]))
    activity = Activity(
        id="known-acquisition",
        identity=stock.identity,
        account_ref=original.account_id,
        account_scope=original.account_scope,
        day=Fact[str](value="2026-10-23"),
        side="acquisition",
        quantity=DecimalFact(value="1"),
        pnl=Fact[str](value=None, reason="Acquisition"),
        source_ref=lots[0].source_ref,
    )
    observations = {
        **extended.observations,
        "screening": facts.model_copy(
            update={
                "restrictions": (*facts.restrictions, known),
                "activities": (*facts.activities, activity),
            }
        ).model_dump(mode="json"),
    }
    blocked = validate(
        candidate.model_copy(
            update={"snapshot": extended.model_copy(update={"observations": observations})}
        ),
        orders,
    )
    assert any("known_acquisition_conflict" in reason for reason in blocked.blockers)
    assert any("manual_restriction:known-restriction" in reason for reason in blocked.blockers)
