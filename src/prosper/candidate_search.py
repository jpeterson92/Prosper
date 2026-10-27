"""Explicit experimental loss-prefix proposals with whole-share buying repair.

This is a bounded deterministic construction, not a solver or production method.
Every displayed point passes the separate final validator. Exhausting proposals
never proves integer optimality or infeasibility of the declared share domain.
"""

import math
from collections.abc import Callable, Iterator

import numpy as np
import polars as pl

from prosper.advisory import decimal_value, number, sale_estimate
from prosper.candidate_records import (
    BuyOrder,
    CandidateCheck,
    CandidateRequest,
    CandidateSearch,
    Orders,
    SaleOrder,
)
from prosper.candidate_reference import _key
from prosper.candidate_validation import WARNINGS, FinalValidator
from prosper.lot_opportunities import retained_activities, screen, screening_inputs

METHOD = "deterministic-loss-prefix-repair-v1"
LIMITATIONS = (
    "Experimental deterministic loss-prefix/repair search; production method is not accepted",
    "Only declared prefixes, quantity scales and two buying repairs are sampled; "
    "no optimality gap or infeasibility proof",
)


def _ranked_sales(request: CandidateRequest) -> list[tuple[str, int]]:
    marks = {m.security_id: m for m in request.settings.marks}
    assets = {a.security.id: a.security for a in request.assets}
    snapshots = (request.snapshot, *request.retained_snapshots)
    facts = screening_inputs(snapshots)
    derived = retained_activities(
        tuple(s.model_copy(update={"observations": {}}) for s in snapshots)
    )
    activities = (*facts.activities, *derived, *request.settings.supplied_activity)
    relations = (*facts.relationships, *request.settings.relationships)
    restrictions = (*facts.restrictions, *request.settings.manual_restrictions)
    rows = []
    for lot in request.snapshot.lots:
        mark = marks.get(lot.security_id)
        security = assets.get(lot.security_id)
        if (
            mark is None
            or security is None
            or lot.quantity.value is None
            or lot.total_basis.value is None
            or mark.price.value is None
            or security.identity.value in facts.basis_disputes
        ):
            continue
        maximum = min(request.sale_bounds[lot.id], int(decimal_value(lot.quantity.value)))
        if not maximum or screen(
            security, "sell", request.settings, activities, relations, restrictions
        ):
            continue
        estimate = sale_estimate(
            lot.quantity.value, lot.total_basis.value, maximum, mark.price.value
        )
        if estimate.loss_candidate and estimate.price_loss is not None:
            rows.append((lot.id, maximum, estimate.price_loss / maximum))
    # Numerical ranking is tabular; final quantity/sign/cost checks remain separate.
    if not rows:
        return []
    frame = pl.DataFrame(
        rows,
        orient="row",
        schema={"lot": pl.String, "shares": pl.Int64, "loss_per_share": pl.Float64},
    )
    return [
        (str(lot), int(shares))
        for lot, shares in frame.sort(["loss_per_share", "lot"], descending=[True, False])
        .select("lot", "shares")
        .iter_rows()
    ]


def _repair(
    request: CandidateRequest, sales: tuple[SaleOrder, ...], mode: str
) -> tuple[BuyOrder, ...]:
    ids = request.risk.security_ids
    index = {sid: i for i, sid in enumerate(ids)}
    prices = {m.security_id: number(m.price.value or "") for m in request.settings.marks}
    rows = [
        (lot.security_id, number(lot.quantity.value or ""))
        for lot in request.snapshot.lots
        if lot.security_id in index
    ]
    lot_ids = {sid for sid, _ in rows}
    rows += [
        (p.security_id, number(p.quantity.value or ""))
        for p in request.snapshot.positions
        if p.security_id in index and p.security_id not in lot_ids
    ]
    holdings = np.zeros(len(ids), dtype=np.float64)
    if rows:
        frame = pl.DataFrame(rows, orient="row", schema={"sid": pl.String, "quantity": pl.Float64})
        for sid, quantity in frame.group_by("sid").agg(pl.col("quantity").sum()).iter_rows():
            holdings[index[sid]] = float(quantity)
    cash = number(request.settings.cash_to_invest)
    sold: dict[str, int] = {}
    lots = {lot.id: lot for lot in request.snapshot.lots}
    for sale in sales:
        sid = lots[sale.lot_id].security_id
        sold[sid] = sold.get(sid, 0) + sale.shares
        holdings[index[sid]] -= sale.shares
        cash += prices[sid] * sale.shares
    for sid, q in sold.items():
        cash -= prices[sid] * q * number(request.settings.sell_discount_bps.value or "") / 10000
        cash -= number(request.settings.sell_fee_per_isolated_order.value or "")
    prices_array = np.asarray([prices[sid] for sid in ids])
    values = holdings * prices_array
    b = np.asarray(request.risk.benchmark_weights)
    covariance = np.asarray(request.risk.annual_covariance)
    fee = number(request.buy_fee_per_security_order)
    premium = number(request.buy_premium_bps) / 10000
    available = set(request.buy_bounds) - set(sold)
    result: list[BuyOrder] = []
    for _ in range(min(len(available), max(0, request.limits.max_orders - len(sold)))):
        nav = float(np.sum(values)) + cash
        if nav <= 0 or not math.isfinite(nav) or cash <= fee:
            break
        active = values / nav - b
        marginal = covariance @ active
        choices = []
        for sid in sorted(available):
            i = index[sid]
            affordable = math.floor((cash - fee) / (prices[sid] * (1 + premium)))
            cap = min(request.buy_bounds[sid], affordable)
            if cap <= 0:
                continue
            target = (
                (b[i] * nav - values[i]) / prices[sid]
                if mode == "deficit"
                else (
                    -float(marginal[i]) * nav / (float(covariance[i, i]) * prices[sid])
                    if covariance[i, i] > 0
                    else 0
                )
            )
            if not math.isfinite(target) or target <= 0:
                continue
            # Compare adjacent integers at the one-coordinate quadratic minimum.
            for q in sorted(
                {max(1, min(cap, math.floor(target))), max(1, min(cap, math.ceil(target)))}
            ):
                delta = q * prices[sid] / nav
                change = 2 * delta * float(marginal[i]) + delta * delta * float(covariance[i, i])
                if mode == "deficit" or change < 0:
                    choices.append((change, sid, q))
        if not choices:
            break
        _, sid, q = min(choices)
        result.append(BuyOrder(security_id=sid, shares=q))
        cash -= q * prices[sid] * (1 + premium) + fee
        values[index[sid]] += q * prices[sid]
        available.remove(sid)
    return tuple(sorted(result, key=lambda order: order.security_id))


def proposals(request: CandidateRequest) -> Iterator[Orders]:
    ranked = _ranked_sales(request)
    if not ranked:
        yield Orders(sales=(), buys=())
        return
    sizes = []
    size = 1
    while size < len(ranked):
        sizes.append(size)
        size *= 2
    sizes.append(len(ranked))
    for size in sizes:
        for divisor in (1, 2, 10000):
            sales = tuple(
                sorted(
                    (
                        SaleOrder(lot_id=lot, shares=max(1, q // divisor))
                        for lot, q in ranked[:size]
                    ),
                    key=lambda v: v.lot_id,
                )
            )
            yield Orders(sales=sales, buys=())
            for mode in ("deficit", "risk"):
                yield Orders(sales=sales, buys=_repair(request, sales, mode))


def _points(request: CandidateRequest, checks: list[CandidateCheck]) -> tuple[CandidateCheck, ...]:
    ordered = sorted(checks, key=lambda c: _key(request, c))
    frontier: list[CandidateCheck] = []
    for check in ordered:
        assert check.metrics is not None
        m = check.metrics
        if any(
            other.metrics is not None
            and other.metrics.price_loss >= m.price_loss
            and other.metrics.modeled_cost <= m.modeled_cost
            and other.metrics.tracking_error <= m.tracking_error
            for other in frontier
        ):
            continue
        frontier.append(check)
    if not frontier:
        return ()
    # Keep the loss winner plus low-risk and low-cost extremes, then stable order.
    extremes = [
        frontier[0],
        min(
            frontier,
            key=lambda c: (c.metrics.tracking_error if c.metrics else math.inf, _key(request, c)),
        ),
        min(
            frontier,
            key=lambda c: (c.metrics.modeled_cost if c.metrics else math.inf, _key(request, c)),
        ),
    ]
    selected = []
    for check in (*extremes, *frontier):
        if check not in selected:
            selected.append(check)
        if len(selected) == request.max_candidates:
            break
    return tuple(selected)


def search(
    request: CandidateRequest, should_stop: Callable[[], bool] | None = None
) -> CandidateSearch:
    request = CandidateRequest.model_validate_json(request.model_dump_json())
    if request.method != METHOD:
        raise ValueError("explicit_heuristic_method_required")
    validator = FinalValidator(request)
    baseline = validator.check(Orders(sales=(), buys=()))
    issues = validator.issues
    seen: set[Orders] = set()
    feasible = []
    evaluated = unresolved = 0
    stopping = "invalid-input" if issues else "proposal-set-exhausted"
    try:
        if not issues:
            for orders in proposals(request):
                if orders in seen:
                    continue
                seen.add(orders)
                if should_stop and should_stop():
                    stopping = "cancelled"
                    break
                if evaluated == request.max_states:
                    stopping = "state-limit"
                    break
                checked = validator.check(orders)
                evaluated += 1
                unresolved += int(checked.unresolved)
                if "unrepresentable_final_calculation" in checked.blockers:
                    stopping = "numerical-failure"
                    break
                if checked.feasible and checked.metrics and checked.metrics.price_loss > 0:
                    feasible.append(checked)
    except (ValueError, ArithmeticError, OverflowError):
        stopping = "numerical-failure"
    points = _points(request, feasible)
    exclusions = tuple(f"{f.locator}: {f.code}: {f.reason}" for f in request.snapshot.exclusions)
    exclusions += tuple(
        f"{s.source_ref}: excluded known tax class {s.classification.value}"
        for s in request.snapshot.securities
        if s.classification.value not in (None, "us-domestic-common-equity")
    )
    return CandidateSearch.model_validate(
        dict(
            inputs=request,
            method=METHOD,
            outcome="invalid-input"
            if issues
            else "numerical-failure"
            if stopping == "numerical-failure"
            else "feasible-incumbent"
            if points
            else "no-candidate",
            stopping=stopping,
            domain_states=None,
            evaluated_states=evaluated,
            feasible_harvests=len(feasible),
            unresolved_states=unresolved,
            baseline=baseline,
            best=points[0] if points else None,
            candidates=points,
            exclusions=exclusions,
            warnings=(*WARNINGS, *LIMITATIONS),
        )
    )
