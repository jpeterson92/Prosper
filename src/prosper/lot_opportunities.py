"""Deterministic conditional lot estimates and conservative supplied-fact screening.

PP01/PP03/PP08 are product exclusions, not a wash-sale matching/tax-return engine.
No candidate, broker action, basis rewrite or tax-dollar benefit is produced.
"""

import math
from datetime import date, datetime
from decimal import Context, Decimal, localcontext
from typing import Literal

import polars as pl

from prosper import advisory
from prosper.advisory_records import DecimalFact, Digest, Fact, ImportSnapshot, Record, Security
from prosper.lot_records import (
    Activity,
    LotDiagnosticRequest,
    LotSettings,
    Relationship,
    Restriction,
    ScreeningFacts,
)
from prosper.record_types import Identifier, Text


class Row(Record):
    lot_id: Identifier
    security_id: Identifier
    source_ref: Text
    quantity: DecimalFact
    term: Fact[str]
    proposed_whole_shares: int | None
    remaining_quantity: str | None
    allocated_basis: Fact[float]
    reference_value: Fact[float]
    price_basis_loss: Fact[float]
    indicative_net_proceeds: Fact[float]
    indicative_tax_pnl: Fact[float]
    modeled_cost: Fact[float]
    status: Literal["conditional-loss", "blocked", "no-price-loss", "cash-treatment", "excluded"]
    blockers: tuple[Text, ...]
    warnings: tuple[Text, ...]


class BuyScreen(Record):
    security_id: Identifier
    status: Literal["conditional", "blocked"]
    blockers: tuple[Text, ...]


class LotResult(Record):
    kind: Literal["lot-opportunities-v1"] = "lot-opportunities-v1"
    rows: tuple[Row, ...]
    buy_screens: tuple[BuyScreen, ...]
    conditional_price_loss_subtotal: Fact[float]
    counts: dict[str, int]
    warnings: tuple[Text, ...]
    validation_outcome: Literal["not_validated"] = "not_validated"


class ScreeningInputs(Record):
    activities: tuple[Activity, ...]
    relationships: tuple[Relationship, ...]
    restrictions: tuple[Restriction, ...]
    basis_disputes: tuple[Text, ...]
    unbounded_events: tuple[Fact[bool], ...]
    sources: tuple[Digest, ...]


def screening_inputs(snapshots: tuple[ImportSnapshot, ...]) -> ScreeningInputs:
    imported = tuple(f for s in snapshots if (f := facts_from(s)) is not None)
    return ScreeningInputs(
        activities=retained_activities(snapshots),
        relationships=tuple(r for f in imported for r in f.relationships),
        restrictions=tuple(r for f in imported for r in f.restrictions),
        basis_disputes=tuple(sorted({v for f in imported for v in f.basis_disputes})),
        unbounded_events=tuple(f.unbounded_event for f in imported),
        sources=tuple(sorted({s.source_sha256 for s in snapshots})),
    )


def unknown(reason: str) -> Fact[float]:
    return Fact[float](value=None, reason=reason)


def metric(value: float, reason: str = "Unrepresentable derived estimate") -> Fact[float]:
    return Fact[float](value=value) if math.isfinite(value) else unknown(reason)


def facts_from(snapshot: ImportSnapshot) -> ScreeningFacts | None:
    import json

    value = snapshot.observations.get("screening")
    return ScreeningFacts.model_validate_json(json.dumps(value)) if value is not None else None


def retained_activities(snapshots: tuple[ImportSnapshot, ...]) -> tuple[Activity, ...]:
    # Callers put the frozen current snapshot first. Its user treatment applies
    # only to the same original source/account/holding, including older views
    # of those bytes. Original screening records remain unchanged. Known
    # identities/conflicts and independently supplied activities are retained.
    cash_refs: dict[tuple[str, str], set[str]] = {}
    mapped_refs: dict[tuple[str, str], dict[str, Fact[str]]] = {}
    for snapshot in snapshots:
        cash_refs.setdefault(
            (snapshot.source_sha256, snapshot.account_id),
            {ref for t in snapshot.cash_treatments for ref in t.source_refs},
        )
        mapped_refs.setdefault(
            (snapshot.source_sha256, snapshot.account_id),
            {
                ref: Fact[str](value=row.security_id)
                for row in snapshot.holding_preparation.rows
                if row.disposition == "mapped"
                for ref in row.source_refs
            }
            if snapshot.holding_preparation
            else {},
        )
    result: list[Activity] = []
    for snapshot in snapshots:
        refs = cash_refs[(snapshot.source_sha256, snapshot.account_id)]
        identities = mapped_refs[(snapshot.source_sha256, snapshot.account_id)]
        accounting = snapshot.observations.get("source_row_accounting")
        own_acquisitions = (
            {
                "lot-acquisition-" + snapshot.source_sha256 + "-" + str(r.get("record"))
                for r in accounting
                if isinstance(r, dict) and r.get("disposition") == "selected-lot"
            }
            if isinstance(accounting, list)
            else set()
        )
        context = snapshot.observations.get("lot_context")
        supplied = context.get("screening") if isinstance(context, dict) else None
        independent = supplied.get("activities") if isinstance(supplied, dict) else None
        if isinstance(independent, list):
            own_acquisitions -= {
                a["id"] for a in independent if isinstance(a, dict) and isinstance(a.get("id"), str)
            }
        facts = facts_from(snapshot)
        if facts:
            result.extend(
                a.model_copy(update={"identity": identities[a.source_ref]})
                if (
                    a.id in own_acquisitions
                    and a.side == "acquisition"
                    and a.identity.value is None
                    and a.source_ref in identities
                    and a.account_ref == snapshot.account_id
                )
                else a
                for a in facts.activities
                if not (
                    a.id in own_acquisitions
                    and a.side == "acquisition"
                    and a.identity.value is None
                    and a.source_ref in refs
                    and a.account_ref == snapshot.account_id
                )
            )
            continue
        securities = {s.id: s for s in snapshot.securities}
        for lot in snapshot.lots:
            if lot.source_ref in refs and securities[lot.security_id].identity.value is None:
                continue
            result.append(
                Activity(
                    id=lot.id,
                    identity=securities[lot.security_id].identity
                    if securities[lot.security_id].identity.value is not None
                    else identities.get(lot.source_ref, securities[lot.security_id].identity),
                    account_ref=snapshot.account_id,
                    account_scope=snapshot.account_scope,
                    day=_acquired(lot.acquired),
                    side="acquisition",
                    quantity=lot.quantity
                    if lot.quantity.value and advisory.decimal_value(lot.quantity.value) > 0
                    else DecimalFact(
                        value=None,
                        reason=(
                            "Original acquisition quantity is not reconstructed from "
                            "remaining shares"
                        ),
                    ),
                    pnl=Fact[str](value=None, reason="No sale P&L is supplied for an acquisition"),
                    source_ref=lot.source_ref,
                )
            )
    return tuple(result)


def _acquired(value: Fact[str]) -> Fact[str]:
    if value.value is not None:
        try:
            date.fromisoformat(value.value)
        except ValueError:
            return Fact[str](value=None, reason="Source acquisition date is unsupported")
    return value


def _related(
    identity: str, other: str, relationships: tuple[Relationship, ...], first: str, second: str
) -> str | None:
    if identity == other:
        return "conflict"
    matches = [r for r in relationships if {r.left, r.right} == {identity, other}]
    if not matches:
        return None
    if any(
        r.status == "conflict"
        and r.valid_from <= min(first, second) <= max(first, second) <= r.valid_through
        for r in matches
    ):
        return "conflict"
    if any(
        r.status == "unknown"
        or not r.valid_from <= min(first, second) <= max(first, second) <= r.valid_through
        or r.evidence.effective_at > first
        or datetime.fromisoformat(r.evidence.recorded_at).date().isoformat() > first
        for r in matches
    ):
        return "unresolved"
    return None


def screen(
    security: Security,
    side: Literal["sell", "buy"],
    settings: LotSettings,
    activities: tuple[Activity, ...],
    relationships: tuple[Relationship, ...],
    restrictions: tuple[Restriction, ...],
) -> tuple[str, ...]:
    identity = security.identity.value
    reasons: set[str] = set()
    if identity is None:
        return ("security_identity_unknown",)
    day = date.fromisoformat(settings.analysis_date)
    for restriction in restrictions:
        if (
            restriction.side not in ("both", side)
            or (restriction.start and restriction.start > settings.analysis_date)
            or (restriction.end and restriction.end < settings.analysis_date)
        ):
            continue
        if restriction.identity.value is None:
            reasons.add("unresolved_manual_name")
        elif _related(
            identity,
            restriction.identity.value,
            relationships,
            settings.analysis_date,
            settings.analysis_date,
        ):
            reasons.add("manual_restriction:" + restriction.source_ref)
    for activity in activities:
        if (side == "sell" and activity.side != "acquisition") or (
            side == "buy" and activity.side != "sale"
        ):
            continue
        # A known zero transaction is not a purchase; an unknown amount is not zero.
        if (
            activity.quantity.value is not None
            and advisory.decimal_value(activity.quantity.value) == 0
        ):
            continue
        if (
            side == "buy"
            and activity.pnl.value is not None
            and advisory.decimal_value(activity.pnl.value, signed=True) >= 0
        ):
            continue
        event_day = date.fromisoformat(activity.day.value) if activity.day.value else None
        if event_day is not None and abs((event_day - day).days) > 30:
            continue
        if activity.identity.value is None:
            reasons.add("activity_identity_unknown:" + activity.source_ref)
            continue
        relation = _related(
            identity,
            activity.identity.value,
            relationships,
            settings.analysis_date,
            activity.day.value or settings.analysis_date,
        )
        if relation is None:
            continue
        if event_day is None:
            reasons.add("activity_date_unknown:" + activity.source_ref)
        elif relation == "unresolved":
            reasons.add("identity_relationship_unresolved:" + activity.source_ref)
        elif activity.account_scope == "scope-unresolved":
            reasons.add("household_scope_unresolved:" + activity.source_ref)
        else:
            reasons.add(
                (
                    "known_acquisition_conflict:"
                    if side == "sell"
                    else "prior_loss_or_unknown_sale_conflict:"
                )
                + activity.source_ref
            )
    return tuple(sorted(reasons))


def _funded(shares: int, mark: str, fee: str, discount: str, cash: str) -> bool:
    # This isolated feasibility sign is a final discrete boundary, with no tolerance
    # or imported-balance fallback. Derived displayed analytics still use Float64.
    values = tuple(advisory.decimal_value(v) for v in (mark, fee, discount, cash))
    precision = sum(len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent)) for v in values) + 32
    with localcontext(Context(prec=max(28, precision))):
        price, charge, spread, budget = values
        proceeds = Decimal(shares) * price
        return budget + proceeds - (proceeds * spread / Decimal(10000) + charge) >= 0


def evaluate(
    snapshot: ImportSnapshot,
    retained: ScreeningInputs,
    settings: LotSettings,
    command: LotDiagnosticRequest,
) -> LotResult:
    securities = {s.id: s for s in snapshot.securities}
    marks = {m.security_id: m for m in settings.marks}
    activities = (*retained.activities, *settings.supplied_activity)
    relationships = (*settings.relationships, *retained.relationships)
    restrictions = (*settings.manual_restrictions, *retained.restrictions)
    disputes = set(retained.basis_disputes)
    warnings = [
        (
            "Conditional estimates only: future acquisitions and "
            "automatic activity can change wash-sale outcomes"
        ),
        (
            "Same-security identities and supplied reviewed "
            "relationships are screened; different IDs are not legal clearance"
        ),
        (
            "Each row is an isolated hypothetical lot sale with the full "
            "entered order fee; do not sum row costs as a multi-lot order"
        ),
        (
            "No deductible-loss, tax-dollar, risk, candidate or "
            "broker-funding validation is established"
        ),
    ]
    if settings.history_coverage.value != "complete-supplied-scope":
        warnings.append(
            "Unverified wash-sale history/household coverage; manual "
            "lists do not establish absence of conflicts"
        )
    if not settings.cash_budget_reviewed or settings.funding_assumption.value is None:
        warnings.append(
            "Cash/funding assumptions are unreviewed or unknown; no "
            "borrowing or broker buying power is inferred"
        )
    if settings.final_cash_target.enabled:
        warnings.append(
            "The explicit final-cash target is recorded; candidate "
            "feasibility and target satisfaction are not calculated"
        )
    global_blocks: list[str] = []
    if snapshot.account_scope != "us-taxable-individual":
        global_blocks.append("supported_taxable_account_scope_required")
    cutoff = date.fromisoformat(snapshot.source_as_of[:10])
    age = (date.fromisoformat(settings.analysis_date) - cutoff).days
    if not 0 <= age <= settings.max_snapshot_age_days:
        global_blocks.append("snapshot_stale_or_future")
    if snapshot.observations.get("selection_blockers"):
        global_blocks.append("source_reconciliation_blocked")
    context = snapshot.observations.get("lot_context")
    assumption = context.get("reported_basis_assumption") if isinstance(context, dict) else None
    if not isinstance(assumption, dict) or assumption.get("value") is not True:
        global_blocks.append("reported_basis_opening_assumption_unreviewed")
    if any(event.value is not False for event in retained.unbounded_events):
        global_blocks.append("unbounded_or_unknown_event_impact")
    if set(command.sale_quantities) - {lot.id for lot in snapshot.lots}:
        raise ValueError("unknown_proposed_lot")
    rows: list[Row] = []
    for lot in snapshot.lots:
        if lot.security_id in snapshot.cash_security_ids | snapshot.excluded_stock_ids:
            cash = lot.security_id in snapshot.cash_security_ids
            na = unknown(
                "Not a stock sale after explicit user cash treatment"
                if cash
                else "Stock metrics unavailable for an excluded holding"
            )
            rows.append(
                Row(
                    lot_id=lot.id,
                    security_id=lot.security_id,
                    source_ref=lot.source_ref,
                    quantity=lot.quantity,
                    term=lot.term,
                    proposed_whole_shares=None,
                    remaining_quantity=lot.quantity.value,
                    allocated_basis=na,
                    reference_value=na,
                    price_basis_loss=na,
                    indicative_net_proceeds=na,
                    indicative_tax_pnl=na,
                    modeled_cost=na,
                    status="cash-treatment" if cash else "excluded",
                    blockers=("user_cash_treatment" if cash else "holding_mapping_excluded",),
                    warnings=(),
                )
            )
            continue
        security = securities[lot.security_id]
        blockers = [
            *global_blocks,
            *screen(security, "sell", settings, activities, relationships, restrictions),
        ]
        row_warnings: list[str] = []
        if security.classification.value != "us-domestic-common-equity":
            blockers.append("unsupported_or_unknown_tax_class")
        if security.identity.value in disputes:
            blockers.append("basis_dispute_unresolved")
        if lot.term.value not in ("long-term", "short-term"):
            row_warnings.append(
                "Unknown source holding term; loss dollars do not imply "
                "ST/LT or tax-dollar treatment"
            )
        q = advisory.decimal_value(lot.quantity.value) if lot.quantity.value is not None else None
        shares = command.sale_quantities.get(lot.id, int(q) if q is not None else 0)
        allocated = loss = reference = net = pnl = cost = unknown(
            "Required source quantity/basis/mark or entered cost assumption is unavailable"
        )
        remaining = lot.quantity.value if q is not None and shares == 0 else None
        mark = marks.get(lot.security_id)
        valid_mark = False
        if (
            mark
            and security.identity.value == mark.identity
            and mark.price.value is not None
            and mark.day.value
        ):
            mark_age = (
                date.fromisoformat(settings.analysis_date) - date.fromisoformat(mark.day.value)
            ).days
            valid_mark = (
                0 <= mark_age <= settings.max_mark_age_days
                and advisory.decimal_value(mark.price.value) > 0
            )
        if not valid_mark:
            blockers.append("mark_missing_stale_future_or_identity_mismatch")
        if q is None:
            blockers.append("quantity_unknown")
        elif not 0 < shares <= 2**53 - 1 or Decimal(shares) > q:
            blockers.append("whole_share_quantity_unavailable_or_exceeds_holding")
        elif valid_mark and mark and mark.price.value is not None:
            try:
                sale = advisory.sale_estimate(
                    lot.quantity.value or "", lot.total_basis.value, shares, mark.price.value
                )
                remaining = sale.remaining_quantity
                reference = metric(shares * advisory.number(mark.price.value))
                if sale.allocated_basis is not None and sale.price_loss is not None:
                    allocated, loss = metric(sale.allocated_basis), metric(sale.price_loss)
                    if sale.loss_candidate is not True:
                        blockers.append("no_reference_price_loss")
                else:
                    blockers.append("basis_unknown")
                if (
                    settings.sell_fee_per_isolated_order.value is not None
                    and settings.sell_discount_bps.value is not None
                    and reference.value is not None
                ):
                    modeled = reference.value * advisory.number(
                        settings.sell_discount_bps.value
                    ) / 10000 + advisory.number(settings.sell_fee_per_isolated_order.value)
                    cost, net = metric(modeled), metric(reference.value - modeled)
                    pnl = (
                        metric(-loss.value - modeled)
                        if loss.value is not None
                        else unknown("Basis is unknown")
                    )
                    if (
                        settings.cash_budget_reviewed
                        and net.value is not None
                        and not _funded(
                            shares,
                            mark.price.value,
                            settings.sell_fee_per_isolated_order.value,
                            settings.sell_discount_bps.value,
                            settings.cash_to_invest,
                        )
                    ):
                        blockers.append("isolated_sale_unfunded_under_selected_cash")
                else:
                    row_warnings.append(
                        "Entered fee or spread/impact assumption is unknown; net "
                        "proceeds/P&L are unavailable"
                    )
                if reference.value is None or (sale.price_loss is not None and loss.value is None):
                    blockers.append("unrepresentable_derived_estimate")
            except (ValueError, OverflowError):
                blockers.append("unrepresentable_or_invalid_sale_estimate")
        status: Literal["conditional-loss", "blocked", "no-price-loss"] = (
            "blocked" if blockers else "conditional-loss"
        )
        if blockers and set(blockers) == {"no_reference_price_loss"}:
            status = "no-price-loss"
        rows.append(
            Row(
                lot_id=lot.id,
                security_id=lot.security_id,
                source_ref=lot.source_ref,
                quantity=lot.quantity,
                term=lot.term,
                proposed_whole_shares=shares if 0 < shares <= 2**53 - 1 else None,
                remaining_quantity=remaining,
                allocated_basis=allocated,
                reference_value=reference,
                price_basis_loss=loss,
                indicative_net_proceeds=net,
                indicative_tax_pnl=pnl,
                modeled_cost=cost,
                status=status,
                blockers=tuple(sorted(set(blockers))),
                warnings=tuple(row_warnings),
            )
        )
    sold_identities = {
        securities[r.security_id].identity.value
        for r in rows
        if r.lot_id in command.sale_quantities and r.proposed_whole_shares
    }
    buys: list[BuyScreen] = []
    for sid in command.replacement_security_ids:
        buy_security = securities.get(sid)
        reasons = list(global_blocks)
        if buy_security is None:
            reasons.append("replacement_security_not_in_reviewed_snapshot")
        else:
            reasons.extend(
                screen(buy_security, "buy", settings, activities, relationships, restrictions)
            )
            if buy_security.classification.value != "us-domestic-common-equity":
                reasons.append("unsupported_or_unknown_tax_class")
            if sid in snapshot.cash_security_ids:
                reasons.append("user_cash_treatment")
            if sid in snapshot.excluded_stock_ids:
                reasons.append("holding_mapping_excluded")
            if (
                buy_security.identity.value is not None
                and buy_security.identity.value in sold_identities
            ):
                reasons.append("same_batch_sale_and_purchase")
        buys.append(
            BuyScreen(
                security_id=sid,
                status="blocked" if reasons else "conditional",
                blockers=tuple(sorted(set(reasons))),
            )
        )
    # Group the complete row inventory with Polars, retaining unavailable values.
    frame = pl.DataFrame(
        [(r.status, r.price_basis_loss.value) for r in rows],
        orient="row",
        schema={"status": pl.String, "loss": pl.Float64},
    )
    counts = {status: count for status, count in frame.group_by("status").len().iter_rows()}
    known = frame.filter(pl.col("loss").is_not_null())
    subtotal = unknown("No supported priced/basis lot estimates are available")
    if known.height:
        subtotal = metric(
            float(frame.filter(pl.col("status") == "conditional-loss").get_column("loss").sum())
        )
    return LotResult(
        rows=tuple(rows),
        buy_screens=tuple(buys),
        conditional_price_loss_subtotal=subtotal,
        counts=counts,
        warnings=tuple(warnings),
    )
