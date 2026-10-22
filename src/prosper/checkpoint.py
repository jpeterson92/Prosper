"""Synthetic checkpoint inspection. No replay, tax eligibility, mutation or planning."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    localcontext,
)
from typing import Literal

from prosper.bundle import Location, ParsedBundle
from prosper.bundle_schema import Fact, Lot, Quote
from prosper.exact import BookValue, ExactValue, ExactValueError, Sign, UnknownValue, calculate

type State = Literal["complete", "incomplete", "contradictory"]
ZERO = ExactValue("0", Sign.NONNEGATIVE)
MAX_FINDINGS = 100


@dataclass(frozen=True)
class Finding:
    code: str
    path: Location
    blocking: bool = False
    reason: str | None = None


class _Findings:
    def __init__(self) -> None:
        self.items: list[Finding] = []
        self.more = False
        self.blocked = False
        self.contradictory = False

    def add(
        self, code: str, path: Location, blocking: bool = False, reason: str | None = None
    ) -> None:
        self.blocked |= blocking
        incomplete = {
            "unknown_fact",
            "inclusion_unproven",
            "event_inclusion_unproven",
            "trade_date_unknown",
            "one_traded_cash_snapshot_required",
            "one_traded_account_required",
            "derived_value_unsupported",
            "checkpoint_mark_ambiguous",
        }
        self.contradictory |= blocking and code not in incomplete
        if len(self.items) < MAX_FINDINGS:
            self.items.append(Finding(code, path, blocking, reason))
        else:
            self.more = True


@dataclass(frozen=True)
class PositionReview:
    account_id: str
    security_id: str
    quantity: BookValue
    lot_quantity: BookValue
    price: BookValue
    market_value: BookValue
    basis: BookValue
    market_minus_basis: BookValue


@dataclass(frozen=True)
class CashReview:
    account_id: str
    settled: BookValue
    available: BookValue
    unsettled: BookValue


@dataclass(frozen=True)
class Readiness:
    inspection: State
    basis: State
    valuation: State
    coverage: State

    @property
    def planning_ready(self) -> Literal[False]:
        return False

    @property
    def planning_reasons(self) -> tuple[str, ...]:
        return (
            "benchmark_missing",
            "risk_model_missing",
            "investor_limits_missing",
            "tax_engine_unqualified",
            "broker_workflow_unqualified",
            "freshness_unqualified",
        )


@dataclass(frozen=True)
class ValidatedCheckpoint:
    """Inspection-valid under synthetic source assertions; not financial-use acceptance."""

    source: ParsedBundle
    traded_account_id: str


@dataclass(frozen=True)
class Inspection:
    source: ParsedBundle
    traded_account_id: str | None
    positions: tuple[PositionReview, ...]
    cash: tuple[CashReview, ...]
    settled_cash_nav: BookValue
    total_basis: BookValue
    market_minus_basis: BookValue
    readiness: Readiness
    findings: tuple[Finding, ...]
    further_findings: bool
    validated: ValidatedCheckpoint | None
    version: str = "synthetic-inspection-v1"


def _fact(
    value: Fact[ExactValue], path: Location, notes: _Findings, required: bool = False
) -> BookValue:
    if value.value is not None:
        return value.value
    assert value.reason is not None
    notes.add("unknown_fact", path, required, value.reason)
    return UnknownValue((value.reason,))


def _amount(
    operation: Literal["add", "subtract", "multiply"],
    left: BookValue,
    right: BookValue,
    path: Location,
    notes: _Findings,
    required: bool = False,
) -> BookValue:
    try:
        return calculate(operation, left, right, field_name="derived", sign=Sign.SIGNED)
    except ExactValueError as error:
        notes.add("derived_value_unsupported", path, required, error.code)
        return UnknownValue((error.code,))


def _sum(
    values: Iterable[BookValue], path: Location, notes: _Findings, required: bool = False
) -> BookValue:
    total: BookValue = ZERO
    for value in values:
        total = _amount("add", total, value, path, notes, required)
    return total


def _known(value: BookValue) -> bool:
    return isinstance(value, ExactValue)


def inspect_checkpoint(source: ParsedBundle) -> Inspection:
    document = source.document
    notes = _Findings()
    cutoff = datetime.fromisoformat(document.metadata.cutoff)
    accounts = {row.id: row for row in document.accounts}
    securities = {row.id: row for row in document.securities}
    lots = {row.id: row for row in document.lots}
    traded = sorted(row.id for row in document.accounts if row.role == "traded")
    account_id = traded[0] if len(traded) == 1 else None
    if account_id is None:
        notes.add("one_traded_account_required", ("accounts",), True)
    for account in sorted(document.accounts, key=lambda row: row.id):
        if account.profile_id != document.metadata.profile_id:
            notes.add("profile_mismatch", ("accounts", account.id, "profile_id"), True)

    def references(
        account: str, security: str | None, checkpoint: str | None, path: Location
    ) -> None:
        if account not in accounts:
            notes.add("unknown_account_reference", (*path, "account_id"), True)
        if security is not None and security not in securities:
            notes.add("unknown_security_reference", (*path, "security_id"), True)
        if checkpoint is not None and checkpoint != document.metadata.bundle_id:
            notes.add("checkpoint_reference_mismatch", (*path, "checkpoint_id"), True)

    position_keys = {(row.account_id, row.security_id) for row in document.positions}
    lots_by_position: dict[tuple[str, str], list[Lot]] = defaultdict(list)
    marks_by_security: dict[str, list[Quote]] = defaultdict(list)
    for lot in document.lots:
        lots_by_position[(lot.account_id, lot.security_id)].append(lot)
    for quote in document.quotes:
        if quote.as_of.value is not None and datetime.fromisoformat(quote.as_of.value) == cutoff:
            marks_by_security[quote.security_id].append(quote)
    basis_complete = True
    for lot in sorted(document.lots, key=lambda row: row.id):
        path = ("lots", lot.id)
        references(lot.account_id, lot.security_id, lot.checkpoint_id, path)
        if (lot.account_id, lot.security_id) not in position_keys:
            notes.add("lot_without_position", path, True)
        if (
            lot.acquired.value is not None
            and date.fromisoformat(lot.acquired.value) > cutoff.date()
        ):
            notes.add("future_acquisition", (*path, "acquired"), True)
        if any(
            fact.value is None
            for fact in (
                lot.quantity,
                lot.basis,
                lot.basis_quantum,
                lot.acquired,
                lot.holding_evidence,
                lot.adjustments,
            )
        ):
            basis_complete = False
            notes.add("lot_evidence_incomplete", path)
        if lot.basis.value is not None and lot.basis_quantum.value is not None:
            with localcontext(
                Context(
                    prec=80,
                    rounding=ROUND_HALF_EVEN,
                    Emin=-999999,
                    Emax=999999,
                    clamp=0,
                    flags=[],
                    traps=[Inexact, Rounded, InvalidOperation, DivisionByZero, Overflow],
                )
            ):
                quantum = lot.basis_quantum.value.value
                if quantum.normalize().as_tuple().digits != (1,):
                    basis_complete = False
                    notes.add("basis_quantum_unqualified", (*path, "basis_quantum"))
                elif lot.basis.value.value % quantum != 0:
                    notes.add("basis_quantum_mismatch", (*path, "basis"), True)

    included = set(document.metadata.included_activity_ids)
    event_ids = {event.id for event in document.activity}
    if document.metadata.inclusion.value is None:
        notes.add(
            "inclusion_unproven",
            ("metadata", "inclusion"),
            True,
            document.metadata.inclusion.reason,
        )
    if included != event_ids:
        notes.add("inclusion_reference_mismatch", ("metadata", "included_activity_ids"), True)
    activity_complete = True
    for event in sorted(document.activity, key=lambda row: row.id):
        path = ("activity", event.id)
        references(event.account_id, event.security_id, None, path)
        if any(
            fact.value is None
            for fact in (
                event.quantity,
                event.price,
                event.principal,
                event.fees,
                event.cash_movement,
                event.trade_date,
                event.settlement_date,
                event.inclusion_evidence,
                event.correction_evidence,
                event.basis_treatment,
            )
        ):
            activity_complete = False
            notes.add("event_evidence_incomplete", path)
        if event.inclusion_evidence.value is None:
            notes.add("event_inclusion_unproven", path, True, event.inclusion_evidence.reason)
        if event.trade_date.value is None:
            notes.add("trade_date_unknown", path, True, event.trade_date.reason)
        elif date.fromisoformat(event.trade_date.value) > cutoff.date():
            notes.add("future_included_event", path, True)
        if (
            event.trade_date.value is not None
            and event.settlement_date.value is not None
            and event.settlement_date.value < event.trade_date.value
        ):
            notes.add("settlement_before_trade", path, True)
        for lot_id in event.lot_ids:
            linked = lots.get(lot_id)
            if linked is None:
                notes.add("unknown_lot_reference", (*path, "lot_ids", lot_id), True)
            elif (linked.account_id, linked.security_id) != (event.account_id, event.security_id):
                notes.add("event_lot_scope_mismatch", (*path, "lot_ids", lot_id), True)
        if event.activity_type in ("buy", "sell"):
            quantity = _fact(event.quantity, (*path, "quantity"), notes)
            event_price = _fact(event.price, (*path, "price"), notes)
            principal = _fact(event.principal, (*path, "principal"), notes)
            fees = _fact(event.fees, (*path, "fees"), notes)
            movement = _fact(event.cash_movement, (*path, "cash_movement"), notes)
            expected_principal = _amount("multiply", quantity, event_price, path, notes)
            if isinstance(principal, ExactValue) and isinstance(expected_principal, ExactValue):
                if principal.value != expected_principal.value:
                    notes.add("activity_principal_mismatch", (*path, "principal"), True)
            expected_cash = _amount(
                "add" if event.activity_type == "buy" else "subtract", principal, fees, path, notes
            )
            if event.activity_type == "buy":
                expected_cash = _amount("subtract", ZERO, expected_cash, path, notes)
            if isinstance(movement, ExactValue) and isinstance(expected_cash, ExactValue):
                if movement.value != expected_cash.value:
                    notes.add("activity_cash_mismatch", (*path, "cash_movement"), True)

    for quote in sorted(document.quotes, key=lambda row: row.id):
        if quote.security_id not in securities:
            notes.add("unknown_security_reference", ("quotes", quote.id, "security_id"), True)

    rows = []
    for position in sorted(document.positions, key=lambda row: row.id):
        path = ("positions", position.id)
        references(position.account_id, position.security_id, position.checkpoint_id, path)
        matching_lots = sorted(
            lots_by_position[(position.account_id, position.security_id)], key=lambda row: row.id
        )
        required = position.account_id == account_id
        quantity = _fact(position.quantity, (*path, "quantity"), notes, required)
        lot_quantity = _sum(
            (
                _fact(lot.quantity, ("lots", lot.id, "quantity"), notes, required)
                for lot in matching_lots
            ),
            (*path, "lot_quantity"),
            notes,
            required,
        )
        if isinstance(quantity, ExactValue) and isinstance(lot_quantity, ExactValue):
            if quantity.value != lot_quantity.value:
                notes.add("position_lot_quantity_mismatch", (*path, "quantity"), True)
        basis = _sum(
            (_fact(lot.basis, ("lots", lot.id, "basis"), notes) for lot in matching_lots),
            (*path, "basis"),
            notes,
        )
        marks = marks_by_security[position.security_id]
        price: BookValue
        if len(marks) != 1:
            code = "checkpoint_mark_missing" if not marks else "checkpoint_mark_ambiguous"
            notes.add(code, (*path, "price"), len(marks) > 1)
            price = UnknownValue((code,))
        else:
            price = _fact(marks[0].price, ("quotes", marks[0].id, "price"), notes)
        market_value = _amount("multiply", quantity, price, (*path, "market_value"), notes)
        pnl = _amount("subtract", market_value, basis, (*path, "market_minus_basis"), notes)
        rows.append(
            PositionReview(
                position.account_id,
                position.security_id,
                quantity,
                lot_quantity,
                price,
                market_value,
                basis,
                pnl,
            )
        )

    cash_rows = []
    for cash in sorted(document.cash, key=lambda row: row.id):
        path = ("cash", cash.id)
        references(cash.account_id, None, cash.checkpoint_id, path)
        cash_rows.append(
            CashReview(
                cash.account_id,
                _fact(cash.settled, (*path, "settled"), notes, cash.account_id == account_id),
                _fact(cash.available, (*path, "available"), notes),
                _fact(cash.unsettled, (*path, "unsettled"), notes),
            )
        )
    selected_cash = [cash for cash in cash_rows if cash.account_id == account_id]
    if len(selected_cash) != 1:
        notes.add("one_traded_cash_snapshot_required", ("cash",), True)
        settled: BookValue = UnknownValue(("traded_cash_missing",))
    else:
        settled = selected_cash[0].settled
    selected = [row for row in rows if row.account_id == account_id]
    market = _sum((row.market_value for row in selected), ("totals", "market_value"), notes)
    basis = _sum((row.basis for row in selected), ("totals", "basis"), notes)
    nav = _amount("add", market, settled, ("totals", "settled_cash_nav"), notes)
    pnl = _sum(
        (row.market_minus_basis for row in selected), ("totals", "market_minus_basis"), notes
    )

    coverage_complete = bool(document.coverage) and activity_complete
    household = False
    coverage_contradictory = False
    for coverage in sorted(document.coverage, key=lambda row: row.id):
        path = ("coverage", coverage.id)
        household |= coverage.scope == "household"
        if coverage.account_id.value is not None and coverage.account_id.value not in accounts:
            notes.add("unknown_account_reference", (*path, "account_id"), True)
        if (
            coverage.starts.value is not None
            and coverage.ends.value is not None
            and coverage.starts.value > coverage.ends.value
        ):
            notes.add("coverage_date_order", path, True)
            coverage_contradictory = True
        evidence = (
            coverage.starts,
            coverage.ends,
            coverage.evidence,
            coverage.automation,
            coverage.other_accounts,
            coverage.outstanding_restrictions,
        )
        complete = (
            coverage.status == "complete"
            and all(fact.value is not None for fact in evidence)
            and (coverage.scope == "household" or coverage.account_id.value is not None)
        )
        if coverage.ends.value is not None and coverage.ends.value != cutoff.date().isoformat():
            complete = False
        if not complete:
            notes.add("coverage_incomplete", path, reason=coverage.evidence.reason)
        coverage_complete &= complete
        coverage_contradictory |= coverage.status == "contradictory"
    coverage_state: State = (
        "contradictory"
        if coverage_contradictory
        else "complete"
        if coverage_complete and household
        else "incomplete"
    )
    readiness = Readiness(
        "contradictory" if notes.contradictory else "incomplete" if notes.blocked else "complete",
        "complete" if basis_complete and _known(basis) else "incomplete",
        "complete" if _known(nav) else "incomplete",
        coverage_state,
    )
    validated = (
        ValidatedCheckpoint(source, account_id)
        if not notes.blocked and account_id is not None
        else None
    )
    return Inspection(
        source,
        account_id,
        tuple(rows),
        tuple(cash_rows),
        nav,
        basis,
        pnl,
        readiness,
        tuple(notes.items),
        notes.more,
        validated,
    )


@dataclass(frozen=True)
class QuantityDelta:
    security_id: str
    quantity: BookValue


@dataclass(frozen=True)
class CheckpointComparison:
    comparable: bool
    quantities: tuple[QuantityDelta, ...]
    settled_cash_delta: BookValue
    basis_delta: BookValue
    nav_delta: BookValue
    prior_holdings_mark_effect: BookValue
    new_activity_fees: BookValue
    residual_after_marks_and_fees: BookValue
    findings: tuple[Finding, ...]


def compare_checkpoints(prior: Inspection, current: Inspection) -> CheckpointComparison:
    """Snapshot deltas and a descriptive arithmetic bridge, never a return/replay."""
    notes = _Findings()
    if (
        prior.validated is None
        or current.validated is None
        or prior.traded_account_id != current.traded_account_id
        or prior.source.document.metadata.profile_id != current.source.document.metadata.profile_id
        or datetime.fromisoformat(prior.source.document.metadata.cutoff)
        >= datetime.fromisoformat(current.source.document.metadata.cutoff)
    ):
        notes.add("comparable_validated_checkpoints_required", ("comparison",), True)
        unknown = UnknownValue(("comparison_unavailable",))
        return CheckpointComparison(
            False, (), unknown, unknown, unknown, unknown, unknown, unknown, tuple(notes.items)
        )
    before = {
        row.security_id: row for row in prior.positions if row.account_id == prior.traded_account_id
    }
    after = {
        row.security_id: row
        for row in current.positions
        if row.account_id == current.traded_account_id
    }
    deltas = []
    mark_effects = []
    for security in sorted(before.keys() | after.keys()):
        left, right = before.get(security), after.get(security)
        delta = _amount(
            "subtract",
            right.quantity if right else ZERO,
            left.quantity if left else ZERO,
            ("comparison", security),
            notes,
        )
        deltas.append(QuantityDelta(security, delta))
        if left is not None:
            new_price = right.price if right else UnknownValue(("current_mark_missing",))
            mark_delta = _amount("subtract", new_price, left.price, ("comparison", security), notes)
            mark_effects.append(
                _amount("multiply", left.quantity, mark_delta, ("comparison", security), notes)
            )
    cash_before = next(row for row in prior.cash if row.account_id == prior.traded_account_id)
    cash_after = next(row for row in current.cash if row.account_id == current.traded_account_id)
    cash_delta = _amount(
        "subtract", cash_after.settled, cash_before.settled, ("comparison",), notes
    )
    basis_delta = _amount(
        "subtract", current.total_basis, prior.total_basis, ("comparison",), notes
    )
    nav_delta = _amount(
        "subtract", current.settled_cash_nav, prior.settled_cash_nav, ("comparison",), notes
    )
    marks = _sum(mark_effects, ("comparison", "mark_effect"), notes)
    prior_ids = {row.id for row in prior.source.document.activity}
    fees = _sum(
        (
            _fact(row.fees, ("activity", row.id, "fees"), notes)
            for row in sorted(current.source.document.activity, key=lambda row: row.id)
            if row.id not in prior_ids and row.account_id == current.traded_account_id
        ),
        ("comparison", "new_activity_fees"),
        notes,
    )
    residual = _amount(
        "add",
        _amount("subtract", nav_delta, marks, ("comparison",), notes),
        fees,
        ("comparison",),
        notes,
    )
    return CheckpointComparison(
        True,
        tuple(deltas),
        cash_delta,
        basis_delta,
        nav_delta,
        marks,
        fees,
        residual,
        tuple(notes.items),
    )
