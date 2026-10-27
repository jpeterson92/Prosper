"""Bounded exhaustive whole-share reference; no production solver.

Construction enumerates the declared integer domain without financial pruning.
The separate final validator alone decides feasibility from original inputs;
there is no shared solver constraint builder or pre-round feasibility flag.
"""

from collections.abc import Callable
from decimal import Context, Decimal, localcontext
from itertools import product
from math import prod

from prosper.advisory import decimal_value
from prosper.candidate_records import (
    BuyOrder,
    CandidateCheck,
    CandidateRequest,
    CandidateSearch,
    Orders,
    SaleOrder,
)
from prosper.candidate_validation import WARNINGS, FinalValidator


def _key(
    request: CandidateRequest, check: CandidateCheck
) -> tuple[Decimal, Decimal, int, tuple[tuple[str, str, int], ...]]:
    assert check.metrics is not None
    # Independently rank the constructor's objective/cost from supplied decimals.
    # Final validation still recomputes everything from orders; displayed Float64
    # collisions cannot change which tiny-domain objective/cost wins.
    sale_ids = {sale.lot_id for sale in check.orders.sales}
    lots = {lot.id: lot for lot in request.snapshot.lots if lot.id in sale_ids}
    prices = {m.security_id: decimal_value(m.price.value or "") for m in request.settings.marks}
    operands = [
        *prices.values(),
        *(decimal_value(lot.quantity.value or "") for lot in lots.values()),
        *(
            decimal_value(lot.total_basis.value)
            for lot in lots.values()
            if lot.total_basis.value is not None
        ),
        decimal_value(request.settings.sell_fee_per_isolated_order.value or ""),
        decimal_value(request.settings.sell_discount_bps.value or ""),
        decimal_value(request.buy_fee_per_security_order),
        decimal_value(request.buy_premium_bps),
    ]
    precision = max(
        28, sum(len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent)) for v in operands) + 64
    )
    with localcontext(Context(prec=precision)):
        reward = Decimal(0)
        gross_by_security: dict[str, Decimal] = {}
        for sale in check.orders.sales:
            lot = lots[sale.lot_id]
            q = decimal_value(lot.quantity.value or "")
            basis = decimal_value(lot.total_basis.value or "")
            allocated = basis if sale.shares == q else basis * sale.shares / q
            gross = prices[lot.security_id] * sale.shares
            reward += max(allocated - gross, Decimal(0))
            gross_by_security[lot.security_id] = (
                gross_by_security.get(lot.security_id, Decimal(0)) + gross
            )
        cost = sum(
            (
                gross * decimal_value(request.settings.sell_discount_bps.value or "") / 10000
                + decimal_value(request.settings.sell_fee_per_isolated_order.value or "")
                for gross in gross_by_security.values()
            ),
            Decimal(0),
        )
        cost += sum(
            (
                prices[buy.security_id]
                * buy.shares
                * decimal_value(request.buy_premium_bps)
                / 10000
                + decimal_value(request.buy_fee_per_security_order)
                for buy in check.orders.buys
            ),
            Decimal(0),
        )
    return (
        reward.copy_negate(),
        cost,
        check.metrics.order_count,
        tuple(
            sorted(
                [("sell", s.lot_id, s.shares) for s in check.orders.sales]
                + [("buy", b.security_id, b.shares) for b in check.orders.buys]
            )
        ),
    )


def search(
    request: CandidateRequest, should_stop: Callable[[], bool] | None = None
) -> CandidateSearch:
    """Freeze inputs, then enumerate at most max_states; callbacks only cancel.

    All zero is a separately checked baseline and also a member of the domain.
    Fees count each security/side order once, including multi-lot sales. No
    borrowing, implied household coverage, or financial-use status is conferred.
    """
    request = CandidateRequest.model_validate_json(request.model_dump_json())
    if request.method != "complete-cartesian-whole-share-reference":
        raise ValueError("explicit_reference_method_required")
    validator = FinalValidator(request)
    baseline = validator.check(Orders(sales=(), buys=()))
    sales = sorted(request.sale_bounds.items())
    buys = sorted(request.buy_bounds.items())
    domains = [range(bound + 1) for _, bound in (*sales, *buys)]
    total = prod(len(domain) for domain in domains)
    exclusions = tuple(
        f"{s.source_ref}: excluded known tax class {s.classification.value}"
        for s in request.snapshot.securities
        if s.classification.value not in (None, "us-domestic-common-equity")
    )
    exclusions += tuple(f"{f.locator}: {f.code}: {f.reason}" for f in request.snapshot.exclusions)
    if validator.issues:
        return CandidateSearch(
            inputs=request,
            method="complete-cartesian-whole-share-reference",
            outcome="invalid-input",
            stopping="invalid-input",
            domain_states=total,
            evaluated_states=0,
            feasible_harvests=0,
            unresolved_states=0,
            baseline=baseline,
            best=None,
            exclusions=exclusions,
            warnings=WARNINGS,
        )
    evaluated = feasible = unresolved = 0
    best = None
    stopping = "complete"
    for quantities in product(*domains):
        if should_stop is not None and should_stop():
            stopping = "cancelled"
            break
        if evaluated == request.max_states:
            stopping = "state-limit"
            break
        orders = Orders(
            sales=tuple(
                SaleOrder(lot_id=lot, shares=q)
                for (lot, _), q in zip(sales, quantities[: len(sales)], strict=True)
                if q
            ),
            buys=tuple(
                BuyOrder(security_id=sid, shares=q)
                for (sid, _), q in zip(buys, quantities[len(sales) :], strict=True)
                if q
            ),
        )
        checked = validator.check(orders)
        evaluated += 1
        unresolved += int(checked.unresolved)
        if "unrepresentable_final_calculation" in checked.blockers:
            stopping = "numerical-failure"
            break
        if checked.feasible and checked.metrics is not None and checked.metrics.price_loss > 0:
            feasible += 1
            if best is None or _key(request, checked) < _key(request, best):
                best = checked
    outcome = (
        "numerical-failure"
        if stopping == "numerical-failure"
        else "optimal-in-domain"
        if stopping == "complete" and best is not None and unresolved == 0
        else "no-feasible-harvest-in-domain"
        if stopping == "complete" and unresolved == 0
        else "feasible-incumbent"
        if best is not None
        else "no-candidate"
    )
    return CandidateSearch.model_validate(
        dict(
            inputs=request,
            method="complete-cartesian-whole-share-reference",
            outcome=outcome,
            stopping=stopping,
            domain_states=total,
            evaluated_states=evaluated,
            feasible_harvests=feasible,
            unresolved_states=unresolved,
            baseline=baseline,
            best=best,
            candidates=(best,) if best else (),
            exclusions=exclusions,
            warnings=WARNINGS,
        )
    )
