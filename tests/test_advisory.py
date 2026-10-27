"""Written advisory cases, numerical edge cases and retained legacy consumers."""

import json
import math
import runpy
from collections.abc import Callable
from dataclasses import asdict, replace
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import cast

import pytest

from prosper import advisory as a
from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import equity_benchmark as e
from prosper import industry as i
from prosper import vanguard as v

ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / "scripts/qualify_advisory.py"))
reference = cast(Callable[[], b.BasketInput], HELPERS["reference"])
hierarchy = cast(Callable[[b.BasketInput], i.Taxonomy], HELPERS["hierarchy"])
covariance = cast(Callable[[b.BasketInput], i.FrozenCovariance], HELPERS["covariance"])
equity_scenario = cast(
    Callable[..., tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]],
    HELPERS["equity_scenario"],
)


def test_written_nav_weights_cash_exposures_and_tracking_error() -> None:
    data = reference()
    result = b.estimate(data)
    assert result.portfolio_nav_usd == 3.0
    assert [value for _, value in result.position_values] == [1.0] * 3
    assert result.weights is not None
    assert result.weights.portfolio == pytest.approx((1 / 3, 1 / 3, 1 / 3, 0))
    assert result.weights.benchmark == (0.5, 0.25, 0.25, 0)
    assert data.positions[0].quantity.raw == "1.000"  # Source strings are untouched.
    diagnostic = i.estimate(result.weights, hierarchy(data), (), covariance(data))
    alpha = next(x for x in diagnostic.exposures if x.group == ("sector", "Alpha"))
    assert (alpha.portfolio, alpha.benchmark, alpha.active) == pytest.approx(
        (2 / 3, 3 / 4, -1 / 12)
    )
    assert diagnostic.attribution is not None
    # Identity covariance: (-1/6)^2 + (1/12)^2 + (1/12)^2 = 1/24.
    assert diagnostic.attribution.variance == pytest.approx(1 / 24)
    assert diagnostic.attribution.tracking_error == pytest.approx(math.sqrt(1 / 24))
    assert math.fsum(x.euler for x in diagnostic.attribution.sectors) == pytest.approx(
        math.sqrt(1 / 24)
    )
    budget = b.estimate(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1.00")))
    assert budget.portfolio_nav_usd == 4.0 and budget.weights is not None
    assert budget.weights.portfolio == (0.25, 0.25, 0.25, 0)
    assert budget.weights.portfolio_cash == 0.25
    json.dumps(asdict(result), allow_nan=False)


def test_float_tolerance_does_not_repair_source_coverage() -> None:
    data = reference()
    first = data.benchmark[0]
    noise = replace(first, weight=replace(first.weight, raw="50.000000001"))
    assert b.estimate(replace(data, benchmark=(noise, *data.benchmark[1:]))).weights is not None
    gap = replace(first, weight=replace(first.weight, raw="48.54"))
    partial = b.estimate(replace(data, benchmark=(gap, *data.benchmark[1:])))
    assert partial.weights is None and partial.portfolio_nav_usd == 3.0
    assert partial.benchmark_weight_sum == pytest.approx(0.9854)
    assert "non_unit_weight_sum" in {issue.code for issue in partial.issues}


@pytest.mark.parametrize("quantity", ["1e0", "1.00000000000000000000000000000000001"])
def test_new_source_spellings_and_precision_are_not_legacy_fixed_point_rules(quantity: str) -> None:
    data = reference()
    position = replace(
        data.positions[0], quantity=replace(data.positions[0].quantity, raw=quantity)
    )
    changed = replace(data, positions=(position, *data.positions[1:]))
    assert b.estimate(changed).weights is not None
    assert b.estimate(changed).data.positions[0].quantity.raw == quantity


@pytest.mark.parametrize(
    "mutation",
    ["unknown_mark", "duplicate", "outside", "unknown_id", "ratio", "nan", "overflow", "underflow"],
)
def test_incomplete_or_invalid_basket_is_never_zero_filled_into_weights(mutation: str) -> None:
    data = reference()
    p, benchmark = data.positions[0], data.benchmark[0]
    if mutation == "unknown_mark":
        p = replace(
            p, reference_mark=replace(p.reference_mark, raw=None, unknown_reasons=("missing",))
        )
    elif mutation == "duplicate":
        data = replace(data, positions=(*data.positions, replace(p, row_id="duplicate")))
    elif mutation == "outside":
        data = replace(data, universe=data.universe[:-1])
    elif mutation == "unknown_id":
        p = replace(
            p, security=replace(p.security, security_id=None, unknown_reasons=("unmapped",))
        )
    elif mutation == "ratio":
        benchmark = replace(
            benchmark, unit="exact-ratio", weight=replace(benchmark.weight, raw="1/2")
        )
    elif mutation == "nan":
        p = replace(p, quantity=replace(p.quantity, raw="NaN"))
    elif mutation == "overflow":
        p = replace(
            p,
            quantity=replace(p.quantity, raw="1e308"),
            reference_mark=replace(p.reference_mark, raw="1e308"),
        )
    elif mutation == "underflow":
        p = replace(
            p,
            quantity=replace(p.quantity, raw="1e-200"),
            reference_mark=replace(p.reference_mark, raw="1e-200"),
        )
    if mutation != "duplicate":
        data = replace(data, positions=(p, *data.positions[1:]))
    data = replace(data, benchmark=(benchmark, *data.benchmark[1:]))
    result = b.estimate(data)
    assert result.weights is None and result.issues
    json.dumps(asdict(result), allow_nan=False)


def test_unknown_benchmark_cash_cannot_become_zero() -> None:
    data = reference()
    result = b.estimate(
        replace(
            data,
            benchmark_cash=replace(data.benchmark_cash, raw=None, unknown_reasons=("unknown",)),
        )
    )
    assert result.weights is None and result.benchmark_weight_sum is None
    assert result.portfolio_nav_usd == 3.0


@pytest.mark.parametrize("case", ["position", "cash", "percent"])
def test_nonzero_derived_weight_underflow_stays_unavailable(case: str) -> None:
    data = reference()
    p, other = data.positions[:2]
    if case == "percent":
        row = replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw="1e-323"))
        data = replace(data, benchmark=(row, *data.benchmark[1:]))
    else:
        other = replace(other, reference_mark=replace(other.reference_mark, raw="1e200"))
        if case == "position":
            p = replace(p, quantity=replace(p.quantity, raw="1e-200"))
        else:
            data = replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1e-200"))
        data = replace(data, positions=(p, other, *data.positions[2:]))
    result = b.estimate(data)
    assert result.weights is None and result.issues
    json.dumps(asdict(result), allow_nan=False)


def test_industry_unknowns_remain_visible_and_only_affected_limits_block() -> None:
    data = reference()
    weights = b.estimate(data).weights
    assert weights is not None
    taxonomy = hierarchy(data)
    unknown = replace(
        taxonomy.records[0], sector=None, industry=None, unknown_reasons=("unmapped",)
    )
    taxonomy = replace(taxonomy, records=(unknown, *taxonomy.records[1:]))
    limit = i.ExposureLimit("sector", ("sector", "Alpha"), "absolute", True, None, "0.9", "fixture")
    cash_limit = i.ExposureLimit("sector", i.CASH, "absolute", True, None, "0.1", "fixture")
    result = i.estimate(weights, taxonomy, (limit, cash_limit), covariance(data))
    assert result.limits[0].status == "blocked" and result.limits[0].value is None
    assert result.limits[1].status == "pass"
    assert next(
        x for x in result.exposures if x.level == "sector" and x.group == i.UNKNOWN
    ).portfolio == pytest.approx(1 / 3)
    assert result.attribution is not None  # The supplied covariance is still a valid diagnostic.


@pytest.mark.parametrize(
    "bound, expected",
    [
        ("0.8", "pass"),
        ("0.666666666666", "breach"),
        ("0.6666666666666666666667", "review-required"),
    ],
)
def test_exposure_tolerance_does_not_relax_economic_limit(bound: str, expected: str) -> None:
    data = reference()
    weights = b.estimate(data).weights
    assert weights is not None
    limit = i.ExposureLimit("sector", ("sector", "Alpha"), "absolute", True, None, bound, "fixture")
    assert (
        i.estimate(weights, hierarchy(data), (limit,), covariance(data)).limits[0].status
        == expected
    )


def test_bad_covariance_preserves_exposure_and_cannot_become_risk() -> None:
    data = reference()
    weights = b.estimate(data).weights
    assert weights is not None
    result = i.estimate(
        weights,
        hierarchy(data),
        (),
        replace(covariance(data), security_ids=tuple(reversed(data.universe))),
    )
    assert result.exposures and result.attribution is None
    assert any(s.startswith("covariance:") for s in result.issues)


def test_no_classifications_still_has_unknown_exposures() -> None:
    data = reference()
    weights = b.estimate(data).weights
    assert weights is not None
    taxonomy = replace(hierarchy(data), records=(), hierarchy=())
    result = i.estimate(weights, taxonomy)
    unknown = next(x for x in result.exposures if x.level == "sector" and x.group == i.UNKNOWN)
    assert (unknown.portfolio, unknown.benchmark) == pytest.approx((1, 1))
    assert result.issues and result.attribution is None


def test_equivalent_percent_and_decimal_link_survives_float_roundoff() -> None:
    raw = json.loads((ROOT / "examples/synthetic/benchmark/equity-only.json").read_bytes())
    rows = raw["2000-01-03"]
    rows["equity"][0]["percentOfFunds"] = "0.7"
    section = "allocationToUnderlyingFunds"
    rows[section] = [{"marketValue": "60.000", "percentOfFunds": "0.007"}]
    acquisition, stipulation, policy, portfolio = equity_scenario(json.dumps(raw).encode())
    stipulation = replace(
        stipulation,
        sections=tuple(
            replace(s, role="subset", unit="decimal") if s.section == section else s
            for s in stipulation.sections
        ),
        rows=tuple(
            replace(row, target=r.Locator("equity", 0)) if row.locator.section == section else row
            for row in stipulation.rows
        ),
    )
    policy = replace(
        policy, decisions=tuple(d for d in policy.decisions if d.locator.section != section)
    )
    result = e.estimate(acquisition, stipulation, policy, portfolio)
    assert result.weights == pytest.approx((2 / 3, 1 / 3))
    assert not result.issues


def test_derived_equity_weight_underflow_is_not_a_known_zero() -> None:
    raw = json.loads((ROOT / "examples/synthetic/benchmark/equity-only.json").read_bytes())
    raw["2000-01-03"]["equity"][0]["marketValue"] = "1e-200"
    raw["2000-01-03"]["equity"][1]["marketValue"] = "1e200"
    result = e.estimate(*equity_scenario(json.dumps(raw).encode()))
    assert not result.weights
    assert "unrepresentable_equity_weights" in {issue.code for issue in result.issues}


def test_equity_source_decisions_feed_current_plain_estimates() -> None:
    acquisition, stipulation, policy, portfolio = equity_scenario()
    result = e.estimate(acquisition, stipulation, policy, portfolio)
    assert result.status == "estimated-equity-benchmark"
    assert result.equity_value == 90.0
    assert result.weights == pytest.approx((2 / 3, 1 / 3))
    assert all(type(x) is float for x in result.weights)
    assert result.basket is not None and result.basket.weights is not None
    assert result.basket.weights.benchmark == pytest.approx((2 / 3, 1 / 3))
    assert (
        len(result.ledger) == 8 and sum(row.disposition == "excluded" for row in result.ledger) == 6
    )
    json.dumps(asdict(result), allow_nan=False)


@pytest.mark.parametrize(
    "value, good",
    [("1e-200", True), (None, False), ("-1", False), ("NaN", False), ("1e-400", False)],
)
def test_equity_included_values_no_longer_require_exact_ratio_range(
    value: str | None, good: bool
) -> None:
    raw = json.loads((ROOT / "examples/synthetic/benchmark/equity-only.json").read_bytes())
    raw["2000-01-03"]["equity"][0]["marketValue"] = value
    acquisition, stipulation, policy, portfolio = equity_scenario(json.dumps(raw).encode())
    result = e.estimate(acquisition, stipulation, policy, portfolio)
    assert bool(result.weights) is good
    if good:
        assert result.weights[0] > 0
        assert math.fsum(result.weights) == pytest.approx(1)
    else:
        assert result.issues and result.equity_value is None


def test_sale_and_cash_boundaries_use_supplied_decimals_not_display_rounding() -> None:
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        sale = a.sale_estimate("3", "1", 1, "0.2")
        assert sale.allocated_basis == pytest.approx(1 / 3)
        assert sale.price_loss == pytest.approx(2 / 15)
        assert sale.loss_candidate is True
    assert a.sale_estimate("3.5", "350", 3, "80").remaining_quantity == "0.5"
    assert a.sale_estimate("1", "100", 1, "100.0001").loss_candidate is False
    assert a.sale_estimate("3", None, 1, "1").price_loss is None
    balance, funded = a.cash_estimate("0", "100", "100.0001", "0")
    assert balance == pytest.approx(-0.0001) and not funded
    assert a.sale_estimate("1", "100.1234567890123", 1, "1").allocated_basis == float(
        Decimal("100.1234567890123")
    )


@pytest.mark.parametrize(
    "available, shares",
    [("3.5", 4), ("9007199254740992.5", 9007199254740993), ("3", True), ("3", 0)],
)
def test_discrete_availability_is_not_float_rounded(available: str, shares: int) -> None:
    with pytest.raises(ValueError):
        a.sale_estimate(available, "100", shares, "1")


@pytest.mark.parametrize(
    "text", ["NaN", "Infinity", "-1", "1e999999999999", "1e-999999999", "1e-400", "0" * 129]
)
def test_number_range_and_input_work_are_bounded(text: str) -> None:
    with pytest.raises(ValueError):
        a.number(text)


def test_500_name_alignment_and_grouping_reconcile_without_rational_transport() -> None:
    base = reference()
    evidence = base.portfolio_cash.evidence
    securities = tuple(b.Security(f"S{n:03}", "USD", "stock", evidence) for n in range(500))
    data = replace(
        base,
        universe=tuple(s.security_id or "" for s in securities),
        candidates=(),
        positions=tuple(
            b.Position(f"P{n}", s, b.Fact("1", evidence), b.Fact("1", evidence))
            for n, s in enumerate(securities[:100])
        ),
        benchmark=tuple(
            b.BenchmarkRow(f"B{n}", s, b.Fact("0.002", evidence), "decimal")
            for n, s in enumerate(securities)
        ),
    )
    result = b.estimate(data)
    assert result.weights is not None and result.portfolio_nav_usd == 100.0
    assert result.weights.portfolio[:100] == pytest.approx([0.01] * 100)
    assert result.weights.portfolio[100:] == (0.0,) * 400
    groups = i.estimate(result.weights, hierarchy(data))
    assert math.fsum(x.portfolio for x in groups.exposures if x.level == "sector") == pytest.approx(
        1
    )
    assert math.fsum(
        x.benchmark for x in groups.exposures if x.level == "industry"
    ) == pytest.approx(1)
