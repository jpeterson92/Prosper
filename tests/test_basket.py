"""Written exact NAV/weight expectations, adverse evidence and industry consumers."""

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import replace
from decimal import ROUND_UP, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from prosper import basket as b
from prosper import industry as i

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/basket/reference.json"
DAY = "2000-01-03"


def inputs() -> b.BasketInput:
    raw = REFERENCE.read_bytes()
    ref = json.loads(raw)
    e = b.Evidence(hashlib.sha256(raw).hexdigest(), "fictional fixture", DAY, DAY, DAY)
    securities = tuple(b.Security(s, "USD", "stock", e) for s in ref["security_ids"])
    return b.BasketInput(
        "Fictional Benchmark",
        DAY,
        DAY,
        tuple(ref["security_ids"]),
        tuple(
            b.Position(f"P{j}", s, b.Fact(ref["quantity"], e), b.Fact(ref["mark_usd"], e))
            for j, s in enumerate(securities[:3])
        ),
        tuple(
            b.BenchmarkRow(f"B{j}", s, b.Fact(w, e), "percent")
            for j, (s, w) in enumerate(
                zip(securities[:3], ref["benchmark_weights_percent"], strict=True)
            )
        ),
        (securities[3],),
        b.Fact(ref["portfolio_cash_usd"], e),
        b.Fact(ref["benchmark_cash_percent"], e),
        "percent",
    )


def fraction(weight: i.Weight) -> Fraction:
    if isinstance(weight, i.ExactWeight):
        return Fraction(int(weight.numerator), int(weight.denominator))
    return Fraction(weight)


def taxonomy(data: b.BasketInput) -> i.Taxonomy:
    return i.Taxonomy(
        "Fictional hierarchy",
        "v1",
        DAY,
        data.portfolio_cash.evidence.source_sha256,
        tuple(
            i.Classification(
                s, "Alpha" if j < 2 else "Beta", "Group", DAY, DAY, "stipulated fixture"
            )
            for j, s in enumerate(data.universe)
        ),
        (("Alpha", "Group"), ("Beta", "Group")),
    )


def test_written_three_position_recurring_ratios_and_selected_cash() -> None:
    data = inputs()
    result = b.qualify(data)
    expected = json.loads(REFERENCE.read_text())["expected"]
    assert result.status == "qualified-synthetic-input"
    assert result.portfolio_nav_usd == expected["nav_usd"]
    assert [v.value_usd for v in result.position_values] == ["1"] * 3
    assert result.benchmark_weight_sum == "1" and result.benchmark_residual == "0"
    w = b.to_industry(result)
    assert [str(fraction(v)) for v in w.portfolio] == expected["portfolio"]
    assert [str(fraction(v)) for v in w.benchmark] == expected["benchmark"]
    assert [
        str(fraction(p) - fraction(v)) for p, v in zip(w.portfolio, w.benchmark, strict=True)
    ] == expected["active"]
    assert w.security_ids == data.universe  # Includes the zero-weight candidate.
    assert result.data.positions[0].quantity.raw == "1.000"
    assert result.data.benchmark[0].weight.raw == "50.00"
    budget = b.qualify(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1.00")))
    assert budget.portfolio_nav_usd == "4"
    assert budget.weights is not None
    assert [fraction(v) for v in budget.weights.portfolio] == [Fraction(1, 4)] * 3 + [0]
    assert fraction(budget.weights.portfolio_cash) == Fraction(1, 4)
    assert budget.identity_sha256 != result.identity_sha256


def test_ratio_industry_totals_limits_and_covariance_use_exact_active_weights() -> None:
    data = inputs()
    w = b.to_industry(b.qualify(data))
    limit = i.ExposureLimit(
        "sector", ("sector", "Alpha"), "absolute", True, None, "0.666666666666", "fictional limit"
    )
    covariance = i.FrozenCovariance(
        data.universe,
        tuple(tuple(float(j == k) for k in range(4)) for j in range(4)),
        DAY,
        1,
        "one_session",
        "stipulated identity covariance",
        "fixed synthetic identity covariance",
    )
    result = i.diagnose(w, taxonomy(data), (limit,), covariance)
    alpha = next(e for e in result.exposures if e.group == ("sector", "Alpha"))
    assert (alpha.portfolio, alpha.benchmark, alpha.active) == ("2/3", "3/4", "-1/12")
    assert result.limit_results[0].status == "breach"
    assert result.attribution is not None
    with localcontext() as ctx:
        ctx.prec = 80
        oracle = (Decimal(1) / Decimal(24)).sqrt()
        assert result.attribution.tracking_error == pytest.approx(float(oracle), rel=2e-15)
    assert result.attribution.variance == pytest.approx(1 / 24)
    assert sum(v.euler for v in result.attribution.sectors) == pytest.approx(float(oracle))
    for level in ("sector", "industry"):
        assert sum(Fraction(e.portfolio) for e in result.exposures if e.level == level) == 1


@pytest.mark.parametrize(
    "first, total, residual", [("48.54", "4927/5000", "73/5000"), ("51", "101/100", "-1/100")]
)
def test_non_unit_benchmark_retains_all_rows_and_exact_residual(
    first: str, total: str, residual: str
) -> None:
    data = inputs()
    changed = replace(
        data,
        benchmark=(
            replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw=first)),
            *data.benchmark[1:],
        ),
    )
    result = b.qualify(changed)
    assert result.status == "incomplete" and result.weights is None
    assert result.benchmark_weight_sum == total and result.benchmark_residual == residual
    assert result.data == changed and len(result.data.benchmark) == 3
    assert result.data.benchmark_cash.raw == "0.00"
    assert "non_unit_weight_sum" in [v.code for v in result.issues]
    with pytest.raises(b.BasketUnavailable):
        b.to_industry(result)


def test_benchmark_units_and_explicit_cash_are_exact_and_independent() -> None:
    data = inputs()
    rows = tuple(
        replace(row, weight=replace(row.weight, raw=raw), unit="decimal")
        for row, raw in zip(data.benchmark, ("0.50", "0.25", "0.25"), strict=True)
    )
    a, other = b.qualify(data), b.qualify(replace(data, benchmark=rows))
    assert a.canonical_sha256 == other.canonical_sha256
    assert a.input_sha256 != other.input_sha256
    with_cash = replace(
        data,
        benchmark=(
            replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw="25")),
            *data.benchmark[1:],
        ),
        benchmark_cash=replace(data.benchmark_cash, raw="25"),
    )
    w = b.to_industry(b.qualify(with_cash))
    assert fraction(w.benchmark_cash) == Fraction(1, 4)
    assert fraction(w.portfolio_cash) == 0


@pytest.mark.parametrize(
    "mutation, code",
    [
        ("quantity", "unknown"),
        ("mark", "unknown"),
        ("cash", "unknown"),
        ("weight", "unknown"),
        ("identity", "unresolved_security"),
        ("currency", "unsupported_or_unknown_currency"),
        ("unsupported", "unsupported_asset_type"),
        ("negative", "negative_sign_forbidden"),
        ("zero-mark", "positive_value_required"),
        ("future", "future_fact"),
        ("recorded-future", "future_fact"),
        ("stale", "stale_under_stipulated_validity"),
        ("date-missing", "unknown_evidence_dates"),
        ("contradictory", "contradictory_known_and_unknown"),
        ("invalid-unit", "explicit_weight_unit_required"),
    ],
)
def test_located_unknown_unsupported_and_invalid_facts_block(mutation: str, code: str) -> None:
    data = inputs()
    position = data.positions[0]
    unknown = ("explicit fictional missing fact",)
    if mutation == "quantity":
        position = replace(
            position, quantity=replace(position.quantity, raw=None, unknown_reasons=unknown)
        )
    if mutation == "mark":
        position = replace(
            position,
            reference_mark=replace(position.reference_mark, raw=None, unknown_reasons=unknown),
        )
    if mutation == "cash":
        data = replace(
            data, portfolio_cash=replace(data.portfolio_cash, raw=None, unknown_reasons=unknown)
        )
    if mutation == "weight":
        data = replace(
            data,
            benchmark=(
                replace(
                    data.benchmark[0],
                    weight=replace(data.benchmark[0].weight, raw=None, unknown_reasons=unknown),
                ),
                *data.benchmark[1:],
            ),
        )
    if mutation == "identity":
        position = replace(
            position, security=replace(position.security, security_id=None, unknown_reasons=unknown)
        )
    if mutation == "currency":
        position = replace(position, security=replace(position.security, currency="EUR"))
    if mutation == "unsupported":
        data = replace(
            data,
            benchmark=(
                replace(
                    data.benchmark[0],
                    security=replace(data.benchmark[0].security, asset_type="derivative"),
                ),
                *data.benchmark[1:],
            ),
        )
    if mutation == "negative":
        position = replace(position, quantity=replace(position.quantity, raw="-1"))
    if mutation == "zero-mark":
        position = replace(position, reference_mark=replace(position.reference_mark, raw="0"))
    if mutation in ("future", "recorded-future", "stale", "date-missing"):
        e = position.reference_mark.evidence
        if mutation == "future":
            e = replace(e, effective="2000-01-04", valid_through="2000-01-05")
        if mutation == "recorded-future":
            e = replace(e, recorded="2000-01-04")
        if mutation == "stale":
            e = replace(e, effective="2000-01-01", valid_through="2000-01-02")
        if mutation == "date-missing":
            e = replace(e, effective=None, unknown_reasons=unknown)
        position = replace(position, reference_mark=replace(position.reference_mark, evidence=e))
    if mutation == "contradictory":
        position = replace(position, quantity=replace(position.quantity, unknown_reasons=unknown))
    if mutation == "invalid-unit":
        data = replace(data, benchmark_cash_unit="guessed")
    data = replace(data, positions=(position, *data.positions[1:]))
    result = b.qualify(data)
    assert code in [v.code for v in result.issues]
    assert result.weights is None and result.data == data
    assert len(result.position_values) == 3
    with pytest.raises(b.BasketUnavailable):
        b.to_industry(result)


@pytest.mark.parametrize("kind", ["position", "benchmark", "candidate"])
def test_duplicate_securities_do_not_become_a_qualified_sum(kind: str) -> None:
    data = inputs()
    if kind == "position":
        data = replace(
            data, positions=(*data.positions, replace(data.positions[0], row_id="P-duplicate"))
        )
    if kind == "benchmark":
        data = replace(
            data, benchmark=(*data.benchmark, replace(data.benchmark[0], row_id="B-duplicate"))
        )
    if kind == "candidate":
        data = replace(data, candidates=(*data.candidates, data.candidates[0]))
    result = b.qualify(data)
    assert f"duplicate_{kind}_security" in [v.code for v in result.issues]
    assert result.weights is None
    if kind == "position":
        assert result.portfolio_nav_usd is None


@pytest.mark.parametrize("cash", ["0", "1"])
def test_zero_nav_and_cash_only_scope_never_yield_qualified_weights(cash: str) -> None:
    data = inputs()
    data = replace(
        data,
        positions=tuple(replace(p, quantity=replace(p.quantity, raw="0")) for p in data.positions),
        portfolio_cash=replace(data.portfolio_cash, raw=cash),
    )
    result = b.qualify(data)
    assert result.weights is None and result.portfolio_nav_usd == cash
    assert ("zero_nav" if cash == "0" else "unsupported_cash_only_sleeve") in [
        v.code for v in result.issues
    ]


def test_fractional_quantity_and_small_products_ignore_decimal_context() -> None:
    data = inputs()
    position = replace(
        data.positions[0],
        quantity=replace(data.positions[0].quantity, raw="0.000000000001"),
        reference_mark=replace(data.positions[0].reference_mark, raw="0.000000000001"),
    )
    data = replace(data, positions=(position, *data.positions[1:]))
    baseline = b.qualify(data)
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.rounding = ROUND_UP
        assert b.qualify(data) == baseline
    assert baseline.position_values[0].value_usd == "1/1000000000000000000000000"
    assert baseline.weights is not None
    assert fraction(baseline.weights.portfolio[0]) == Fraction(1, 2000000000000000000000001)


def test_source_lexeme_nav_order_and_date_identities_freeze_old_inputs() -> None:
    data = inputs()
    original = b.qualify(data)
    pos = replace(data.positions[0], quantity=replace(data.positions[0].quantity, raw="1.0"))
    spelling = b.qualify(replace(data, positions=(pos, *data.positions[1:])))
    assert spelling.canonical_sha256 == original.canonical_sha256
    assert spelling.identity_sha256 != original.identity_sha256
    source = replace(
        data.portfolio_cash, evidence=replace(data.portfolio_cash.evidence, source_sha256="a" * 64)
    )
    variants = (
        replace(data, portfolio_cash=source),
        replace(data, universe=tuple(reversed(data.universe))),
    )
    for variant in variants:
        assert b.qualify(variant).identity_sha256 != original.identity_sha256
    assert b.qualify(data) == original
    assert original.data.positions[0].quantity.raw == "1.000"
    with pytest.raises(b.BasketUnavailable):
        b.to_industry(replace(original, identity_sha256="a" * 64))


@pytest.mark.parametrize("missing", [True, False])
def test_explicit_universe_cannot_drop_or_invent_names(missing: bool) -> None:
    data = inputs()
    universe = data.universe[:-1] if missing else (*data.universe, "FICTIONAL-UNATTRIBUTED")
    result = b.qualify(replace(data, universe=universe))
    assert result.weights is None
    assert (
        "required_security_missing_from_order" if missing else "unattributed_universe_member"
    ) in [v.code for v in result.issues]


@pytest.mark.parametrize("n,d", [("1", "3"), ("0", "1"), ("1", "1")])
def test_explicit_ratio_valid_inputs(n: str, d: str) -> None:
    assert i.ExactWeight(n, d) == i.ExactWeight.from_fraction(Fraction(int(n), int(d)))


@pytest.mark.parametrize(
    "n,d",
    [("1", "0"), ("-1", "3"), ("2", "6"), ("2", "1"), ("01", "3"), ("1.0", "3"), ("1", "9" * 129)],
)
def test_ratio_representation_never_silently_repairs(n: str, d: str) -> None:
    with pytest.raises(i.IndustryUnavailable):
        i.ExactWeight(n, d)


def test_fresh_process_replay() -> None:
    command = [sys.executable, "-I", str(ROOT / "scripts/qualify_basket.py")]
    first = subprocess.check_output(command, cwd=ROOT)
    assert first == subprocess.check_output(command, cwd=ROOT)
    output = json.loads(first)
    assert output["base"]["identity_sha256"] == b.qualify(inputs()).identity_sha256
    assert output["non_unit"]["benchmark_residual"] == "73/5000"
    assert math.isclose(output["industry"]["attribution"]["variance"], 1 / 24)


def test_fractional_holdings_and_exact_limit_endpoint_with_selected_cash() -> None:
    data = inputs()
    p = replace(
        data.positions[0],
        quantity=replace(data.positions[0].quantity, raw="100.25"),
        reference_mark=replace(data.positions[0].reference_mark, raw="2.00"),
    )
    result = b.qualify(replace(data, positions=(p, *data.positions[1:])))
    assert result.portfolio_nav_usd == "405/2"
    assert result.position_values[0].value_usd == "401/2"
    assert result.weights is not None
    assert fraction(result.weights.portfolio[0]) == Fraction(401, 405)
    budget = b.qualify(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1")))
    limit = i.ExposureLimit(
        "sector", ("sector", "Alpha"), "absolute", True, "0.50", "0.50", "fictional exact endpoint"
    )
    assert (
        i.diagnose(b.to_industry(budget), taxonomy(data), (limit,), None).limit_results[0].status
        == "pass"
    )


def test_unknown_benchmark_cash_and_zero_weight_candidate_identity_are_required() -> None:
    data = inputs()
    unknown = ("explicit fictional missing fact",)
    for changed in (
        replace(
            data, benchmark_cash=replace(data.benchmark_cash, raw=None, unknown_reasons=unknown)
        ),
        replace(
            data,
            candidates=(replace(data.candidates[0], security_id=None, unknown_reasons=unknown),),
        ),
    ):
        result = b.qualify(changed)
        assert result.weights is None and result.data == changed
        assert any(issue.reasons == unknown for issue in result.issues)


def test_incomplete_canonical_identity_retains_mapping_and_distributions() -> None:
    data = inputs()
    first = replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw="48.54"))
    data = replace(data, benchmark=(first, *data.benchmark[1:]))
    original = b.qualify(data)
    switched = (
        replace(data.benchmark[0], security=data.benchmark[1].security),
        replace(data.benchmark[1], security=data.benchmark[0].security),
        data.benchmark[2],
    )
    changed = b.qualify(replace(data, benchmark=switched))
    assert original.weights is None and changed.weights is None
    assert original.benchmark_weight_sum == changed.benchmark_weight_sum
    assert original.canonical_sha256 != changed.canonical_sha256


def test_valuation_cutoff_and_knowledge_cutoff_do_not_imply_historical_availability() -> None:
    data = inputs()
    original_weights = b.to_industry(b.qualify(data))
    later_weights = b.to_industry(b.qualify(replace(data, known_at="2000-01-05")))
    assert later_weights.portfolio_nav_identity != original_weights.portfolio_nav_identity
    assert later_weights.benchmark_nav_identity != original_weights.benchmark_nav_identity
    later = replace(data.portfolio_cash.evidence, recorded="2000-01-04")
    disclosed = replace(
        data, known_at="2000-01-05", portfolio_cash=replace(data.portfolio_cash, evidence=later)
    )
    assert b.qualify(disclosed).weights is not None
    blocked = b.qualify(replace(disclosed, known_at=DAY))
    assert blocked.weights is None and any(v.code == "future_fact" for v in blocked.issues)
    with pytest.raises(b.BasketUnavailable):
        b.qualify(replace(data, known_at="2000-01-02"))


@pytest.mark.parametrize(
    "mutation",
    ["no-reason", "bad-hash", "duplicate-row", "non-tuple", "invalid-date", "unqualified-scope"],
)
def test_structural_ambiguities_are_rejected(mutation: str) -> None:
    data = inputs()
    if mutation == "no-reason":
        data = replace(data, portfolio_cash=replace(data.portfolio_cash, raw=None))
    if mutation == "bad-hash":
        data = replace(
            data,
            portfolio_cash=replace(
                data.portfolio_cash,
                evidence=replace(data.portfolio_cash.evidence, source_sha256="not-a-hash"),
            ),
        )
    if mutation == "duplicate-row":
        data = replace(data, positions=(*data.positions, data.positions[0]))
    if mutation == "non-tuple":
        data = replace(data, universe=list(data.universe))  # type: ignore[arg-type]
    if mutation == "invalid-date":
        data = replace(data, as_of="2000-1-3")
    if mutation == "unqualified-scope":
        data = replace(data, scope="live-portfolio")
    with pytest.raises(b.BasketUnavailable):
        b.qualify(data)
