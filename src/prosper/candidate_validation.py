"""Final discrete checks recomputed from canonical inputs, independently of search.

Tiny inventories use Python/Decimal boundary logic; matrix products use NumPy.
No constraint or accounting routine from candidate_reference is imported here.
"""

import math
from datetime import date
from decimal import Context, Decimal, localcontext

import numpy as np

from prosper.advisory import decimal_value, supplied_sum, unit_sum
from prosper.advisory_records import Lot, Position
from prosper.candidate_records import (
    BuyOrder,
    CandidateCheck,
    CandidateMetrics,
    CandidateRequest,
    Orders,
    SaleOrder,
)
from prosper.lot_opportunities import (
    _related,
    facts_from,
    retained_activities,
    screen,
    screening_inputs,
)
from prosper.lot_records import FidelityContext

WARNINGS = (
    "Unqualified covariance estimate; no calibrated investor risk or financial authorization",
    "Conditional wash-sale screening: future activity and incomplete household history "
    "can change losses",
    "Reference marks, pro-rata basis and costs are estimates; broker lot selection/funding "
    "remain unverified",
    "Excluded holdings and untouched account cash are outside the modeled sleeve",
)


def _precision(request: CandidateRequest) -> int:
    # Bounded text/operands; local precision keeps discrete/sign checks independent
    # of caller Decimal settings. Division remains an estimated pro-rata allocation.
    cfg, limits = request.settings, request.limits
    tokens = [
        cfg.cash_to_invest,
        cfg.sell_fee_per_isolated_order.value,
        cfg.sell_discount_bps.value,
        cfg.final_cash_target.amount,
        cfg.final_cash_target.investor_tolerance,
        request.buy_fee_per_security_order,
        request.buy_premium_bps,
        limits.tracking_error,
        limits.max_cost,
        limits.max_turnover,
        limits.min_order_notional,
        limits.max_position_weight,
    ]
    tokens += [lot.quantity.value for lot in request.snapshot.lots]
    tokens += [lot.total_basis.value for lot in request.snapshot.lots]
    tokens += [p.quantity.value for p in request.snapshot.positions]
    tokens += [m.price.value for m in cfg.marks]
    tokens += [
        v.value
        for v in (
            limits.max_order_notional,
            limits.min_price_loss,
            limits.max_cost_to_loss,
            limits.min_scenario_net_value,
        )
    ]
    tokens += [v.maximum for v in limits.exposures]
    if limits.scenario is not None:
        tokens += [limits.scenario.offset_rate, limits.scenario.usable_loss_fraction]
    values = [decimal_value(t) for t in tokens if t is not None]
    return max(
        28, sum(len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent)) for v in values) + 64
    )


def input_issues(request: CandidateRequest) -> tuple[str, ...]:
    """Canonical coverage/units safety, shared with the enumeration entry point."""
    issues: list[str] = []
    ids = tuple(a.security.id for a in request.assets)
    if len(set(ids)) != len(ids) or request.risk.security_ids != ids:
        issues.append("asset_covariance_order_or_duplicate")
    identities = [a.security.identity.value for a in request.assets]
    if None in identities or len(set(identities)) != len(identities):
        issues.append("identity_unknown_or_aliased")
    if any(a.security.classification.value != "us-domestic-common-equity" for a in request.assets):
        issues.append("included_tax_class_unsupported_or_unknown")
    if any(len(v) != len(ids) for v in request.risk.annual_covariance) or len(
        request.risk.annual_covariance
    ) != len(ids):
        issues.append("covariance_dimensions")
    else:
        matrix = np.asarray(request.risk.annual_covariance, dtype=np.float64)
        symmetry_bound = 32 * np.finfo(np.float64).eps * len(ids) * float(np.max(np.abs(matrix)))
        if not np.isfinite(matrix).all() or not np.allclose(
            matrix, matrix.T, rtol=0, atol=symmetry_bound
        ):
            issues.append("covariance_not_finite_symmetric")
        else:
            try:
                # Negative eigenvalues are refused, never clipped or repaired.
                with np.errstate(over="raise", invalid="raise"):
                    eigenvalues = np.linalg.eigvalsh(matrix)
                if not np.isfinite(eigenvalues).all() or float(eigenvalues[0]) < 0:
                    issues.append("covariance_not_psd")
            except (np.linalg.LinAlgError, FloatingPointError):
                issues.append("covariance_eigendecomposition_failed")
    b = request.risk.benchmark_weights
    if len(b) != len(ids) or not unit_sum(b):
        issues.append("benchmark_weights_incomplete_or_invalid")
    if (
        len(set(request.risk.benchmark_ids)) != len(request.risk.benchmark_ids)
        or not set(request.risk.benchmark_ids) <= set(ids)
        or any(
            w != 0 and sid not in request.risk.benchmark_ids for sid, w in zip(ids, b, strict=False)
        )
    ):
        issues.append("benchmark_membership_invalid")
    risk_age = (
        date.fromisoformat(request.settings.analysis_date) - date.fromisoformat(request.risk.as_of)
    ).days
    if not 0 <= risk_age <= request.risk.max_age_days:
        issues.append("risk_date_stale_or_future")
    snapshot = request.snapshot
    original = {s.id: s for s in snapshot.securities}
    assets = {a.security.id: a for a in request.assets}
    included = {
        s.id
        for s in snapshot.securities
        if s.classification.value in (None, "us-domestic-common-equity")
        and s.id not in snapshot.cash_security_ids
        and s.id not in snapshot.excluded_stock_ids
        and s.id not in request.history_excluded_ids
    }
    if len(set(request.history_excluded_ids)) != len(request.history_excluded_ids) or set(
        request.history_excluded_ids
    ) & set(ids):
        issues.append("history_sleeve_membership_invalid")
    if set(request.buy_bounds) & set(request.history_excluded_ids):
        issues.append("history_excluded_purchase")
    if any(
        request.sale_bounds.get(lot.id, 0)
        for lot in snapshot.lots
        if lot.security_id in request.history_excluded_ids
    ):
        issues.append("history_excluded_sale")
    rows: tuple[Lot | Position, ...] = (*snapshot.lots, *snapshot.positions)
    held = {r.security_id for r in rows} & included
    if not held <= set(ids):
        issues.append("held_universe_incomplete")
    if set(ids) != held | set(request.risk.benchmark_ids) | set(request.buy_bounds):
        issues.append("declared_union_mismatch")
    if any(sid in original and assets[sid].security != original[sid] for sid in ids):
        issues.append("source_security_mapping_changed")
    if set(request.sale_bounds) != {lot.id for lot in snapshot.lots}:
        issues.append("sale_domain_must_account_for_every_source_lot")
    locators = [(lot.account_id, lot.security_id, lot.source_ref) for lot in snapshot.lots]
    if len(set(locators)) != len(locators):
        issues.append("ambiguous_source_lot_locator")
    if not set(request.buy_bounds) <= set(ids):
        issues.append("unknown_buy_domain_security")
    if set(request.buy_bounds) & snapshot.cash_security_ids:
        issues.append("cash_treatment_not_a_stock_purchase")
    if set(request.buy_bounds) & snapshot.excluded_stock_ids:
        issues.append("holding_mapping_excluded_purchase")
    if any(
        request.sale_bounds.get(lot.id, 0)
        for lot in snapshot.lots
        if lot.security_id in snapshot.excluded_stock_ids
    ):
        issues.append("holding_mapping_excluded_sale")
    if any(
        request.sale_bounds.get(lot.id, 0)
        for lot in snapshot.lots
        if lot.security_id in snapshot.cash_security_ids
    ):
        issues.append("cash_treatment_not_a_stock_sale")
    if request.method == "complete-cartesian-whole-share-reference" and (
        len(ids) > 16 or len(request.sale_bounds) + len(request.buy_bounds) > 16
    ):
        issues.append("tiny_domain_dimension_limit")
    marks = {m.security_id: m for m in request.settings.marks}
    if set(marks) != set(ids):
        issues.append("mark_universe_mismatch")
    for asset in request.assets:
        mark = marks.get(asset.security.id)
        if (
            mark is None
            or mark.price.value is None
            or mark.day.value is None
            or mark.identity != asset.security.identity.value
        ):
            issues.append("mark_unknown_or_identity_mismatch:" + asset.security.id)
        else:
            age = (
                date.fromisoformat(request.settings.analysis_date)
                - date.fromisoformat(mark.day.value)
            ).days
            if (
                decimal_value(mark.price.value) <= 0
                or not 0 <= age <= request.settings.max_mark_age_days
            ):
                issues.append("mark_stale_future_or_nonpositive:" + asset.security.id)
    for row in rows:
        if row.security_id in included and row.quantity.value is None:
            issues.append("held_quantity_unknown:" + row.source_ref)
    seen_positions: set[str] = set()
    for position in snapshot.positions:
        sid = position.security_id
        if sid not in included:
            continue
        if sid in seen_positions:
            issues.append("duplicate_independent_position:" + sid)
        seen_positions.add(sid)
        parts = [lot.quantity.value for lot in snapshot.lots if lot.security_id == sid]
        if parts and position.quantity.value is not None and all(v is not None for v in parts):
            total = supplied_sum(tuple(v for v in parts if v is not None))
            if total != decimal_value(position.quantity.value):
                issues.append("position_lot_quantity_contradiction:" + sid)
    if snapshot.account_scope != "us-taxable-individual":
        issues.append("supported_taxable_account_required")
    age = (
        date.fromisoformat(request.settings.analysis_date)
        - date.fromisoformat(snapshot.source_as_of[:10])
    ).days
    if not 0 <= age <= request.settings.max_snapshot_age_days:
        issues.append("snapshot_stale_or_future")
    context = snapshot.observations.get("lot_context")
    assumption = context.get("reported_basis_assumption") if isinstance(context, dict) else None
    if not isinstance(assumption, dict) or assumption.get("value") is not True:
        issues.append("reported_basis_assumption_unreviewed")
    if snapshot.observations.get("selection_blockers"):
        issues.append("source_reconciliation_blocked")
    for source in (snapshot, *request.retained_snapshots):
        source_context = source.observations.get("lot_context")
        if source_context is not None:
            import json

            reviewed = FidelityContext.model_validate_json(json.dumps(source_context))
            supplied = facts_from(source)
            # The source adapter augments context activity with observed lots;
            # retaining that superset is valid. Omission of context facts is not.
            if (
                supplied is None
                or any(
                    item not in getattr(supplied, field)
                    for field in ("activities", "relationships", "restrictions", "basis_disputes")
                    for item in getattr(reviewed.screening, field)
                )
                or (
                    supplied is not None
                    and supplied.unbounded_event != reviewed.screening.unbounded_event
                )
            ):
                issues.append("source_screening_omitted_or_changed:" + source.source_name)
    retained = screening_inputs((snapshot, *request.retained_snapshots))
    if any(v.value is not False for v in retained.unbounded_events):
        issues.append("unbounded_or_unknown_event_impact")
    if (
        not request.settings.cash_budget_reviewed
        or request.settings.funding_assumption.value is None
    ):
        issues.append("reviewed_cash_and_funding_required")
    if (
        request.settings.sell_fee_per_isolated_order.value is None
        or request.settings.sell_discount_bps.value is None
    ):
        issues.append("selling_cost_assumptions_unknown")
    return tuple(sorted(set(issues)))


def validate(request: CandidateRequest, orders: Orders) -> CandidateCheck:
    """Validate arbitrary orders, including tampered/out-of-domain proposals."""
    return FinalValidator(request).check(orders)


class FinalValidator:
    """One immutable input inspection per search, final arithmetic for every order set.

    Retain no global cache or persisted proof. This local copy prevents callback
    mutations from invalidating its covariance/source inspection.
    """

    def __init__(self, request: CandidateRequest) -> None:
        self._request = CandidateRequest.model_validate_json(request.model_dump_json())
        self.issues = input_issues(self._request)
        self._precision = _precision(self._request) if not self.issues else 28

    def check(self, orders: Orders) -> CandidateCheck:
        return _checked(self._request, orders, self.issues, self._precision)


def _checked(
    request: CandidateRequest, orders: Orders, blockers: tuple[str, ...], precision: int
) -> CandidateCheck:
    if blockers:
        return CandidateCheck(
            orders=orders,
            feasible=False,
            unresolved=True,
            blockers=tuple(blockers),
            metrics=None,
            warnings=WARNINGS,
        )
    order_values: tuple[SaleOrder | BuyOrder, ...] = (*orders.sales, *orders.buys)
    if any(type(v.shares) is not int or not 0 < v.shares <= 2**53 - 1 for v in order_values):
        return CandidateCheck(
            orders=orders,
            feasible=False,
            unresolved=False,
            blockers=("invalid_whole_share_order",),
            metrics=None,
            warnings=WARNINGS,
        )
    with localcontext(Context(prec=precision)):
        try:
            return _validate(request, orders)
        except (ValueError, ArithmeticError, OverflowError):
            return CandidateCheck(
                orders=orders,
                feasible=False,
                unresolved=True,
                blockers=("unrepresentable_final_calculation",),
                metrics=None,
                warnings=WARNINGS,
            )


def _validate(request: CandidateRequest, orders: Orders) -> CandidateCheck:
    cfg, limits = request.settings, request.limits
    ids = request.risk.security_ids
    assets = {a.security.id: a for a in request.assets}
    lots = {lot.id: lot for lot in request.snapshot.lots}
    marks = {m.security_id: decimal_value(m.price.value or "") for m in cfg.marks}
    remaining = dict.fromkeys(ids, Decimal(0))
    issues: list[str] = []
    # Source positions corroborate lots; they are never counted twice.
    for lot in lots.values():
        if lot.security_id in remaining:
            remaining[lot.security_id] += decimal_value(lot.quantity.value or "")
    position_ids: set[str] = set()
    for position in request.snapshot.positions:
        sid = position.security_id
        if sid not in remaining:
            continue
        if sid in position_ids:
            issues.append("duplicate_independent_position:" + sid)
        position_ids.add(sid)
        q = decimal_value(position.quantity.value or "")
        if any(item.security_id == sid for item in lots.values()):
            if q != remaining[sid]:
                issues.append("position_lot_quantity_contradiction:" + sid)
        else:
            remaining[sid] = q
    initial_nav = sum((remaining[sid] * marks[sid] for sid in ids), Decimal(0)) + decimal_value(
        cfg.cash_to_invest
    )
    if initial_nav <= 0:
        issues.append("nonpositive_initial_sleeve_nav")
    retained = screening_inputs((request.snapshot, *request.retained_snapshots))
    # Remaining held lots also establish acquisitions. They cannot disappear
    # because a supplied screening list omits the adapter's derived observations.
    source_lots = tuple(
        source.model_copy(update={"observations": {}})
        for source in (request.snapshot, *request.retained_snapshots)
    )
    activities = (*retained.activities, *retained_activities(source_lots), *cfg.supplied_activity)
    relationships = (*retained.relationships, *cfg.relationships)
    restrictions = (*retained.restrictions, *cfg.manual_restrictions)
    sold: dict[str, int] = {}
    buy_ids = [b.security_id for b in orders.buys]
    lot_ids = [s.lot_id for s in orders.sales]
    if len(set(lot_ids)) != len(lot_ids) or len(set(buy_ids)) != len(buy_ids):
        issues.append("duplicate_order_identity")
    loss = Decimal(0)
    st = lt = unknown = Decimal(0)
    proceeds = cost = tax_pnl = turnover_value = Decimal(0)
    sell_gross: dict[str, Decimal] = {}
    for sale in orders.sales:
        proposed_lot = lots.get(sale.lot_id)
        if proposed_lot is None or proposed_lot.security_id not in assets:
            issues.append("unknown_or_excluded_sale_lot:" + sale.lot_id)
            continue
        lot = proposed_lot
        sid = lot.security_id
        if sale.shares > request.sale_bounds.get(lot.id, 0):
            issues.append("sale_outside_declared_domain:" + lot.id)
        q = decimal_value(lot.quantity.value or "")
        if Decimal(sale.shares) > q or q <= 0:
            issues.append("sale_exceeds_supplied_quantity:" + lot.id)
            continue
        if lot.total_basis.value is None:
            issues.append("sale_basis_unknown:" + lot.id)
            continue
        basis = decimal_value(lot.total_basis.value)
        # Compare sign before division: fees cannot make a reference gain eligible.
        if basis < q * marks[sid]:
            issues.append("reference_positive_gain:" + lot.id)
        allocated = basis if q == sale.shares else basis * sale.shares / q
        piece = allocated - marks[sid] * sale.shares
        loss += max(piece, Decimal(0))
        if lot.term.value == "short-term":
            st += max(piece, Decimal(0))
        elif lot.term.value == "long-term":
            lt += max(piece, Decimal(0))
        else:
            unknown += max(piece, Decimal(0))
        sold[sid] = sold.get(sid, 0) + sale.shares
        sell_gross[sid] = sell_gross.get(sid, Decimal(0)) + marks[sid] * sale.shares
        remaining[sid] -= sale.shares
        tax_pnl -= allocated
        if assets[sid].security.identity.value in retained.basis_disputes:
            issues.append("basis_dispute_unresolved:" + lot.id)
        issues.extend(
            "sell/" + sid + "/" + v
            for v in screen(
                assets[sid].security, "sell", cfg, activities, relationships, restrictions
            )
        )
    for gross in sell_gross.values():
        charge = gross * decimal_value(cfg.sell_discount_bps.value or "") / 10000 + decimal_value(
            cfg.sell_fee_per_isolated_order.value or ""
        )
        cost += charge
        proceeds += gross - charge
        tax_pnl += gross - charge
        turnover_value += gross
    buy_principal = Decimal(0)
    for buy in orders.buys:
        sid = buy.security_id
        if sid not in assets or sid not in request.buy_bounds:
            issues.append("unknown_or_ineligible_buy:" + sid)
            continue
        if buy.shares > request.buy_bounds[sid]:
            issues.append("buy_outside_declared_domain:" + sid)
        gross = marks[sid] * buy.shares
        charge = gross * decimal_value(request.buy_premium_bps) / 10000 + decimal_value(
            request.buy_fee_per_security_order
        )
        cost += charge
        buy_principal += gross + charge
        turnover_value += gross
        remaining[sid] += buy.shares
        issues.extend(
            "buy/" + sid + "/" + v
            for v in screen(
                assets[sid].security, "buy", cfg, activities, relationships, restrictions
            )
        )
        for sell_sid in sold:
            relation = _related(
                assets[sell_sid].security.identity.value or "",
                assets[sid].security.identity.value or "",
                relationships,
                cfg.analysis_date,
                cfg.analysis_date,
            )
            if relation is not None:
                issues.append("same_batch_conflict_or_unresolved:" + sell_sid + "/" + sid)
    for sid, value in remaining.items():
        if value < 0:
            issues.append("negative_final_quantity:" + sid)
    for sid, gross in (
        *sell_gross.items(),
        *(
            (b.security_id, marks[b.security_id] * b.shares)
            for b in orders.buys
            if b.security_id in assets
        ),
    ):
        if gross < decimal_value(limits.min_order_notional):
            issues.append("order_below_min_notional:" + sid)
        if limits.max_order_notional.enabled and gross > decimal_value(
            limits.max_order_notional.value or ""
        ):
            issues.append("order_above_max_notional:" + sid)
    cash = decimal_value(cfg.cash_to_invest) + proceeds - buy_principal
    values = {sid: remaining[sid] * marks[sid] for sid in ids}
    nav = sum(values.values(), Decimal(0)) + cash
    if cash < 0:
        issues.append("unfunded_final_cash")
    if nav <= 0:
        issues.append("nonpositive_final_nav")
    if cfg.final_cash_target.enabled and abs(
        cash - decimal_value(cfg.final_cash_target.amount or "")
    ) > decimal_value(cfg.final_cash_target.investor_tolerance or ""):
        issues.append("final_cash_target_unmet")
    count = len(sell_gross) + len(orders.buys)
    if count > limits.max_orders:
        issues.append("max_orders_exceeded")
    if cost > decimal_value(limits.max_cost):
        issues.append("max_cost_exceeded")
    if turnover_value > decimal_value(limits.max_turnover) * initial_nav:
        issues.append("max_turnover_exceeded")
    if nav <= 0 or initial_nav <= 0:
        return CandidateCheck(
            orders=orders,
            feasible=False,
            unresolved=False,
            blockers=tuple(sorted(set(issues))),
            metrics=None,
            warnings=WARNINGS,
        )
    for sid in ids:
        if values[sid] > decimal_value(limits.max_position_weight) * nav:
            issues.append("position_weight_exceeded:" + sid)
    for limit in limits.exposures:
        if limit.level == "security":
            if limit.group not in assets:
                issues.append("unknown_exposure_security:" + limit.group)
            members = [sid for sid in ids if sid == limit.group]
        else:
            if any(getattr(a, limit.level).value is None for a in request.assets):
                issues.append("unknown_constrained_taxonomy:" + limit.level)
            members = [sid for sid in ids if getattr(assets[sid], limit.level).value == limit.group]
            if not members:
                issues.append("unknown_exposure_group:" + limit.group)
        exposure = sum((values[sid] for sid in members), Decimal(0))
        if limit.kind == "active":
            benchmark = sum(
                (
                    Decimal.from_float(b)
                    for sid, b in zip(ids, request.risk.benchmark_weights, strict=True)
                    if sid in members
                ),
                Decimal(0),
            )
            exposure = abs(exposure - benchmark * nav)
        if exposure > decimal_value(limit.maximum) * nav:
            issues.append("exposure_limit_exceeded:" + limit.level + "/" + limit.group)
    decimal_weights = tuple(values[sid] / nav for sid in ids)
    if any(value != 0 and float(value) == 0 for value in decimal_weights):
        raise ValueError("underflow_final_weight")
    weights = tuple(float(value) for value in decimal_weights)
    active = np.asarray(weights) - np.asarray(request.risk.benchmark_weights)
    covariance = np.asarray(request.risk.annual_covariance)
    with np.errstate(over="raise", invalid="raise", under="raise"):
        variance = float(active @ covariance @ active)
    # Product/sum and weight conversion error bound, in annual variance units.
    # It is used to refuse an unresolved cap, never to permit a computed breach.
    with np.errstate(over="raise", invalid="raise", under="raise"):
        scale = float(np.abs(active) @ np.abs(covariance) @ np.abs(active))
        error = float(
            64 * np.finfo(np.float64).eps * len(ids) * (scale + float(np.max(np.abs(covariance))))
        )
    if all(
        values[sid] == Decimal.from_float(b) * nav
        for sid, b in zip(ids, request.risk.benchmark_weights, strict=True)
    ):
        error = 0.0
    if variance < -error or not math.isfinite(variance + error):
        raise ValueError("invalid_final_variance")
    te = math.sqrt(max(0.0, variance))
    upper = math.sqrt(max(0.0, variance) + error)
    cap = decimal_value(limits.tracking_error)
    if Decimal.from_float(te) > cap:
        issues.append("tracking_error_exceeded")
    elif Decimal.from_float(upper) > cap:
        issues.append("tracking_error_boundary_review_required")
    harvest = bool(orders.sales or orders.buys)
    if harvest:
        if loss <= 0:
            issues.append("positive_eligible_price_loss_required")
        if limits.min_price_loss.enabled and loss < decimal_value(
            limits.min_price_loss.value or ""
        ):
            issues.append("minimum_price_loss_unmet")
        if limits.max_cost_to_loss.enabled and cost > loss * decimal_value(
            limits.max_cost_to_loss.value or ""
        ):
            issues.append("cost_to_loss_exceeded")
    scenario = None
    if limits.scenario is not None:
        if unknown > 0:
            if limits.min_scenario_net_value.enabled:
                issues.append("unknown_term_cannot_support_tax_scenario")
        else:
            scenario = (
                loss
                * decimal_value(limits.scenario.usable_loss_fraction)
                * decimal_value(limits.scenario.offset_rate)
                - cost
            )
            if (
                harvest
                and limits.min_scenario_net_value.enabled
                and scenario < decimal_value(limits.min_scenario_net_value.value or "")
            ):
                issues.append("scenario_net_value_unmet")
    decimal_estimates = (
        loss,
        st,
        lt,
        unknown,
        tax_pnl,
        cost,
        cash,
        nav,
        *remaining.values(),
        turnover_value / initial_nav,
        *((scenario,) if scenario is not None else ()),
    )
    estimates = [float(v) for v in decimal_estimates] + [*weights, te, upper]
    if any(v != 0 and float(v) == 0 for v in decimal_estimates):
        raise ValueError("underflow_final_metric")
    if not all(math.isfinite(v) for v in estimates) or (
        scenario is not None and not math.isfinite(float(scenario))
    ):
        raise ValueError("nonfinite_final_metric")
    metrics = CandidateMetrics(
        price_loss=float(loss),
        short_term_loss=float(st),
        long_term_loss=float(lt),
        unknown_term_loss=float(unknown),
        net_proceeds_tax_pnl=float(tax_pnl),
        modeled_cost=float(cost),
        final_cash=float(cash),
        final_nav=float(nav),
        final_quantities=tuple(float(remaining[sid]) for sid in ids),
        final_weights=weights,
        tracking_error=te,
        risk_upper_bound=upper,
        turnover=float(turnover_value / initial_nav),
        order_count=count,
        scenario_net_value=float(scenario) if scenario is not None else None,
    )
    warnings = (
        *WARNINGS,
        *(
            ("Unknown source term: ST/LT and tax value remain unavailable for that loss",)
            if unknown > 0
            else ()
        ),
    )
    return CandidateCheck(
        orders=orders,
        feasible=not issues,
        unresolved=any(
            token in issue.split(":", 1)[0]
            for issue in issues
            for token in ("unknown", "unresolved", "review_required")
        ),
        blockers=tuple(sorted(set(issues))),
        metrics=metrics,
        warnings=warnings,
    )
