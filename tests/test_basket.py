"""Written exact NAV/weight expectations, adverse evidence and industry consumers."""

import hashlib
import json
from dataclasses import replace
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


def test_validity_window_does_not_carry_old_benchmark_weights_forward_unchanged() -> None:
    data = inputs()
    # Identity assertions can remain valid; a source-date weight cannot.
    old = replace(data.portfolio_cash.evidence, effective="2000-01-02")
    benchmark = tuple(
        replace(row, weight=replace(row.weight, evidence=old)) for row in data.benchmark
    )
    result = b.estimate(replace(data, benchmark=benchmark))
    assert result.weights is None
    assert "benchmark_weights_not_as_of" in {issue.code for issue in result.issues}
    result = b.estimate(replace(data, benchmark_cash=replace(data.benchmark_cash, evidence=old)))
    assert result.weights is None
    assert "benchmark_weights_not_as_of" in {issue.code for issue in result.issues}


def test_written_values_weights_and_selected_cash() -> None:
    data = inputs()
    result = b.estimate(data)
    assert result.portfolio_nav_usd == 3.0
    assert result.position_values == (("P0", 1.0), ("P1", 1.0), ("P2", 1.0))
    assert result.weights is not None
    assert result.weights.portfolio == pytest.approx((1 / 3, 1 / 3, 1 / 3, 0))
    cash = b.estimate(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1.00")))
    assert cash.portfolio_nav_usd == 4.0 and cash.weights is not None
    assert cash.weights.portfolio == (0.25, 0.25, 0.25, 0) and cash.weights.portfolio_cash == 0.25


@pytest.mark.parametrize("value", [None, "-1", "NaN", "Infinity", "1e-400", "1e309"])
def test_unknown_or_unsupported_values_never_create_partial_universe_weights(
    value: str | None,
) -> None:
    data = inputs()
    first = data.positions[0]
    fact = replace(
        first.reference_mark, raw=value, unknown_reasons=("not supplied",) if value is None else ()
    )
    result = b.estimate(
        replace(data, positions=(replace(first, reference_mark=fact), *data.positions[1:]))
    )
    assert result.weights is None and result.issues
    assert len(result.position_values) == 3


@pytest.mark.parametrize(
    "kind",
    [
        "missing-held-name",
        "duplicate-position",
        "duplicate-benchmark",
        "future-evidence",
        "unknown-identity",
    ],
)
def test_order_cardinality_and_source_evidence_block_dependent_weights(kind: str) -> None:
    data = inputs()
    if kind == "missing-held-name":
        data = replace(data, universe=data.universe[1:])
    elif kind == "duplicate-position":
        data = replace(
            data, positions=(*data.positions, replace(data.positions[0], row_id="extra"))
        )
    elif kind == "duplicate-benchmark":
        data = replace(
            data, benchmark=(*data.benchmark, replace(data.benchmark[0], row_id="extra"))
        )
    elif kind == "future-evidence":
        data = replace(
            data,
            positions=(
                replace(
                    data.positions[0],
                    reference_mark=replace(
                        data.positions[0].reference_mark,
                        evidence=replace(
                            data.positions[0].reference_mark.evidence, recorded="2000-01-04"
                        ),
                    ),
                ),
                *data.positions[1:],
            ),
        )
    else:
        data = replace(
            data,
            positions=(
                replace(
                    data.positions[0],
                    security=replace(
                        data.positions[0].security,
                        security_id=None,
                        unknown_reasons=("identity not supplied",),
                    ),
                ),
                *data.positions[1:],
            ),
        )
    result = b.estimate(data)
    assert result.weights is None and result.issues


def test_explicit_order_and_nonunit_benchmark_are_preserved() -> None:
    data = inputs()
    ordered = replace(data, universe=tuple(reversed(data.universe)))
    result = b.estimate(ordered)
    assert result.weights is not None and result.weights.security_ids == ordered.universe
    wrong = replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw="48.54"))
    partial = b.estimate(replace(data, benchmark=(wrong, *data.benchmark[1:])))
    assert partial.weights is None and partial.benchmark_weight_sum == pytest.approx(0.9854)
