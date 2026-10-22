"""Independent synthetic reference values and conservative failure boundaries."""

import copy
import json
from dataclasses import FrozenInstanceError
from decimal import ROUND_UP, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prosper.bundle import parse_bundle
from prosper.checkpoint import Inspection, compare_checkpoints, inspect_checkpoint
from prosper.exact import BookValue, ExactValue, UnknownValue

FIXTURES = Path(__file__).resolve().parents[1] / "examples/synthetic"
type Document = dict[str, Any]


def fixture(name: str = "F001") -> Document:
    value: Document = json.loads((FIXTURES / f"{name}.json").read_bytes())
    return value


def inspect(document: Document) -> Inspection:
    parsed = parse_bundle(json.dumps(document).encode())
    assert parsed.parsed is not None, parsed.issues
    return inspect_checkpoint(parsed.parsed)


def amount(value: BookValue) -> Fraction:
    assert isinstance(value, ExactValue), value
    return Fraction(value.value)


def test_f001_reference_and_never_replay_or_double_count_fees() -> None:
    result = inspect(fixture())
    assert result.validated is not None
    assert amount(result.settled_cash_nav) == 2399
    assert amount(result.total_basis) == 2181
    assert amount(result.market_minus_basis) == -101
    positions = {row.security_id: row for row in result.positions}
    aaa = positions["SEC-FAAA"]
    assert amount(aaa.quantity) == amount(aaa.lot_quantity) == 12
    assert amount(aaa.market_value) == 1080 and amount(aaa.basis) == 1181
    assert amount(positions["SEC-FBBB"].market_minus_basis) == 0
    cash = result.cash[0]
    assert amount(cash.settled) == amount(cash.available) == 319
    assert result.readiness.inspection == result.readiness.basis == "complete"
    assert result.readiness.coverage == "complete"
    assert result.readiness.planning_ready is False
    assert "risk_model_missing" in result.readiness.planning_reasons
    # Repeat is a pure function, not an import or an increment to source state.
    assert inspect(fixture()) == result


def test_f000_comparison_is_a_snapshot_bridge_not_a_return() -> None:
    previous, current = inspect(fixture("F000")), inspect(fixture())
    assert amount(previous.settled_cash_nav) == 2500
    assert amount(previous.total_basis) == 2000
    assert previous.cash[0].available == UnknownValue(("not_stipulated",))
    assert previous.cash[0].unsettled == UnknownValue(("not_stipulated",))
    comparison = compare_checkpoints(previous, current)
    assert comparison.comparable
    assert [amount(row.quantity) for row in comparison.quantities] == [2, 0]
    assert amount(comparison.settled_cash_delta) == -181
    assert amount(comparison.basis_delta) == 181
    assert amount(comparison.nav_delta) == -101
    assert amount(comparison.prior_holdings_mark_effect) == -100
    assert amount(comparison.new_activity_fees) == 1
    assert amount(comparison.residual_after_marks_and_fees) == 0
    assert not hasattr(comparison, "investment_return")


@pytest.mark.parametrize("change", ["unknown", "omitted_event", "dangling_event", "event_unknown"])
def test_f002_unproven_inclusion_blocks_validation(change: str) -> None:
    document = fixture()
    if change == "unknown":
        document["metadata"]["inclusion"] = {"value": None, "reason": "inclusion_unproven"}
    elif change == "omitted_event":
        document["metadata"]["included_activity_ids"] = []
    elif change == "dangling_event":
        document["metadata"]["included_activity_ids"].append("ABSENT-EVENT")
    else:
        document["activity"][0]["inclusion_evidence"] = {"value": None, "reason": "unproven"}
    result = inspect(document)
    assert result.validated is None
    assert any("inclusion" in row.code and row.blocking for row in result.findings)
    assert amount(result.positions[0].quantity) == 12


def test_f003_quantity_contradiction_is_located_and_source_preserved() -> None:
    document = fixture()
    document["lots"][0]["quantity"]["value"] = "11"
    result = inspect(document)
    assert result.validated is None and result.readiness.inspection == "contradictory"
    assert any(
        row.code == "position_lot_quantity_mismatch"
        and row.path == ("positions", "POSITION-FAAA", "quantity")
        for row in result.findings
    )
    assert amount(result.positions[0].quantity) == 12
    assert amount(result.positions[0].lot_quantity) == 13
    assert result.source.document.lots[0].quantity.value is not None
    assert result.source.document.lots[0].quantity.value.canonical == "11"


def test_f004_preserves_unknown_basis_without_fee_inference() -> None:
    document = fixture()
    document["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    result = inspect(document)
    assert result.validated is not None
    assert result.total_basis == UnknownValue(("source_missing",))
    assert result.market_minus_basis == UnknownValue(("source_missing",))
    assert amount(result.settled_cash_nav) == 2399
    assert result.readiness.basis == "incomplete"
    assert result.source.document.lots[1].basis.reason == "source_missing"
    assert isinstance(
        compare_checkpoints(inspect(fixture("F000")), result).basis_delta, UnknownValue
    )


def test_f009_does_not_turn_inspection_into_clean_household_or_planning() -> None:
    document = fixture()
    document["coverage"][0]["status"] = "unknown"
    document["coverage"][0]["evidence"] = {"value": None, "reason": "household_unknown"}
    result = inspect(document)
    assert result.validated is not None and amount(result.settled_cash_nav) == 2399
    assert result.readiness.coverage == "incomplete" and not result.readiness.planning_ready
    assert any(
        row.code == "coverage_incomplete" and row.reason == "household_unknown"
        for row in result.findings
    )


@pytest.mark.parametrize("where", ["position", "lot", "settled_cash"])
def test_required_unknowns_are_incomplete_never_zero_or_contradictory(where: str) -> None:
    document = fixture()
    pair = {"value": None, "reason": "source_missing"}
    if where == "position":
        document["positions"][0]["quantity"] = pair
    elif where == "lot":
        document["lots"][0]["quantity"] = pair
    else:
        document["cash"][0]["settled"] = pair
    result = inspect(document)
    assert result.validated is None
    assert result.readiness.inspection == "incomplete"
    if where != "lot":
        assert isinstance(result.settled_cash_nav, UnknownValue)


@pytest.mark.parametrize(
    ("family", "field", "value", "code"),
    [
        ("accounts", "profile_id", "OTHER-PROFILE", "profile_mismatch"),
        ("lots", "account_id", "ABSENT", "unknown_account_reference"),
        ("positions", "security_id", "ABSENT", "unknown_security_reference"),
        ("lots", "checkpoint_id", "F000", "checkpoint_reference_mismatch"),
        ("cash", "checkpoint_id", "F000", "checkpoint_reference_mismatch"),
        ("quotes", "security_id", "ABSENT", "unknown_security_reference"),
    ],
)
def test_reference_closure(family: str, field: str, value: str, code: str) -> None:
    document = fixture()
    document[family][0][field] = value
    result = inspect(document)
    assert result.validated is None
    assert any(row.code == code and row.blocking for row in result.findings)


@pytest.mark.parametrize(
    "change",
    ["lot_link", "lot_scope", "future_trade", "future_lot", "settlement", "principal", "cash"],
)
def test_activity_and_time_contradictions(change: str) -> None:
    document = fixture()
    if change == "lot_link":
        document["activity"][0]["lot_ids"] = ["ABSENT"]
    elif change == "lot_scope":
        document["activity"][0]["lot_ids"] = ["LOT-B-OLD"]
    elif change == "future_trade":
        document["activity"][0]["trade_date"]["value"] = "2026-10-23"
    elif change == "future_lot":
        document["lots"][0]["acquired"]["value"] = "2026-10-23"
    elif change == "settlement":
        document["activity"][0]["settlement_date"]["value"] = "2026-10-20"
    elif change == "principal":
        document["activity"][0]["principal"]["value"] = "179"
    else:
        document["activity"][0]["cash_movement"]["value"] = "-180"
    result = inspect(document)
    assert result.validated is None and result.readiness.inspection == "contradictory"


def test_cash_buckets_are_independent_and_fractional_holdings_not_truncated() -> None:
    document = fixture()
    document["positions"][0]["quantity"]["value"] = "12.25"
    document["lots"][0]["quantity"]["value"] = "10.25"
    document["cash"][0]["available"]["value"] = "400"
    document["cash"][0]["unsettled"]["value"] = "100"
    result = inspect(document)
    assert result.validated is not None
    assert amount(result.settled_cash_nav) == Fraction(4843, 2)
    assert amount(result.cash[0].available) == 400 and amount(result.cash[0].unsettled) == 100


@pytest.mark.parametrize("change", ["missing", "wrong_time", "ambiguous"])
def test_valuation_gaps_are_explicit(change: str) -> None:
    document = fixture()
    if change == "missing":
        document["quotes"] = document["quotes"][1:]
    elif change == "wrong_time":
        document["quotes"][0]["as_of"]["value"] = "2026-10-22T15:00:00-04:00"
    else:
        duplicate = copy.deepcopy(document["quotes"][0])
        duplicate["id"] = "SECOND-MARK"
        document["quotes"].append(duplicate)
    result = inspect(document)
    assert isinstance(result.settled_cash_nav, UnknownValue)
    assert result.readiness.valuation == "incomplete"
    assert (result.validated is None) == (change == "ambiguous")


def test_quantum_and_coverage_contradictions_and_unknowns() -> None:
    document = fixture()
    document["lots"][0]["basis"]["value"] = "1000.001"
    assert inspect(document).validated is None
    document = fixture()
    document["lots"][0]["basis_quantum"] = {"value": None, "reason": "unit_missing"}
    assert inspect(document).validated is not None
    assert inspect(document).readiness.basis == "incomplete"
    document = fixture()
    document["coverage"][0]["starts"]["value"] = "2026-10-23"
    assert inspect(document).validated is None
    document = fixture()
    document["coverage"] = []
    assert inspect(document).readiness.coverage == "incomplete"


def test_large_derived_values_are_explicit_and_context_is_isolated() -> None:
    document = fixture()
    document["quotes"][0]["price"]["value"] = "9999999999999999999999999999"
    result = inspect(document)
    assert isinstance(result.settled_cash_nav, UnknownValue)
    assert any(row.code == "derived_value_unsupported" for row in result.findings)
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.Emax = 2
        ambient.rounding = ROUND_UP
        assert amount(inspect(fixture()).settled_cash_nav) == 2399
        assert ambient.prec == 2 and ambient.rounding == ROUND_UP


def test_immutable_result_and_noncomparable_inputs() -> None:
    previous, current = inspect(fixture("F000")), inspect(fixture())
    with pytest.raises(FrozenInstanceError):
        current.total_basis = UnknownValue(("changed",))  # type: ignore[misc]
    assert not compare_checkpoints(current, previous).comparable
    document = fixture()
    document["lots"][0]["quantity"]["value"] = "11"
    assert not compare_checkpoints(previous, inspect(document)).comparable


def test_monitor_account_is_preserved_without_polluting_traded_totals() -> None:
    document = fixture()
    account = copy.deepcopy(document["accounts"][0])
    account.update(id="MONITOR", role="monitor_only")
    document["accounts"].append(account)
    position = copy.deepcopy(document["positions"][0])
    position.update(id="MONITOR-POSITION", account_id="MONITOR")
    position["quantity"]["value"] = "3"
    document["positions"].append(position)
    lot = copy.deepcopy(document["lots"][0])
    lot.update(id="MONITOR-LOT", account_id="MONITOR")
    lot["quantity"]["value"], lot["basis"]["value"] = "3", "300"
    document["lots"].append(lot)
    cash = copy.deepcopy(document["cash"][0])
    cash.update(id="MONITOR-CASH", account_id="MONITOR")
    cash["settled"] = {"value": None, "reason": "monitor_cash_unknown"}
    document["cash"].append(cash)
    document["coverage"][0]["other_accounts"]["value"] = "Monitor account supplied"
    result = inspect(document)
    assert result.validated is not None and len(result.positions) == 3
    assert amount(result.settled_cash_nav) == 2399 and amount(result.total_basis) == 2181
    assert any(row.account_id == "MONITOR" for row in result.positions)


def test_incomplete_activity_cannot_claim_complete_coverage() -> None:
    document = fixture()
    document["activity"][0]["quantity"] = {"value": None, "reason": "history_incomplete"}
    result = inspect(document)
    assert result.validated is not None  # Authoritative snapshot still reconciles.
    assert result.readiness.coverage == "incomplete"
    assert not result.readiness.planning_ready


def test_finding_cap_cannot_hide_a_late_blocker() -> None:
    document = fixture()
    for index in range(150):
        lot = copy.deepcopy(document["lots"][0])
        lot.update(id=f"Z-LOT-{index:03d}")
        lot["quantity"]["value"], lot["basis"]["value"] = "0", "0"
        lot["holding_evidence"] = {"value": None, "reason": "missing"}
        document["lots"].append(lot)
    document["lots"][-1]["account_id"] = "ABSENT"
    result = inspect(document)
    assert len(result.findings) == 100 and result.further_findings
    assert result.validated is None and result.readiness.inspection == "contradictory"


def test_equivalent_timestamp_instants_and_unknown_aggregate_bounds() -> None:
    document = fixture()
    document["quotes"][0]["as_of"]["value"] = "2026-10-22T20:00:00Z"
    assert amount(inspect(document).settled_cash_nav) == 2399
    document["lots"][0]["quantity"]["value"] = "9999999999999999999999999999"
    result = inspect(document)
    assert result.validated is None
    assert isinstance(result.positions[0].lot_quantity, UnknownValue)


@settings(max_examples=100, derandomize=True, database=None)
@given(quantity=st.integers(1, 10**6), mark=st.integers(1, 10**4), reverse=st.booleans())
def test_totals_against_independent_integer_reference_and_permutations(
    quantity: int,
    mark: int,
    reverse: bool,
) -> None:
    document = fixture()
    document["lots"][0]["quantity"]["value"] = str(quantity)
    document["lots"][0]["basis"]["value"] = str(quantity * 100)
    document["positions"][0]["quantity"]["value"] = str(quantity + 2)
    document["quotes"][0]["price"]["value"] = str(mark)
    original = inspect(document)
    if reverse:
        for family in ("positions", "lots", "cash", "activity", "quotes", "coverage", "securities"):
            document[family].reverse()
    result = inspect(document)
    assert result.validated is not None
    assert amount(result.settled_cash_nav) == (quantity + 2) * mark + 1000 + 319
    assert amount(result.total_basis) == quantity * 100 + 181 + 1000
    assert result.positions == original.positions and result.readiness == original.readiness
