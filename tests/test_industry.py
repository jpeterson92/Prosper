"""Independent written rational cases for hierarchy/exposure/covariance diagnostics."""

import hashlib
import json
import math
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pytest

from prosper import covariance as c
from prosper import industry as i
from prosper import volatility as v
from prosper.innovations import fingerprint

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/industry/reference.json"
DAY = "2000-03-04"


def inputs() -> tuple[i.EstimatedWeights, i.Taxonomy, i.FrozenCovariance]:
    ref = json.loads(REFERENCE.read_text())
    ids = tuple(ref["security_ids"])
    w = i.EstimatedWeights(
        ids,
        tuple(float(x) for x in ref["portfolio"]),
        tuple(float(x) for x in ref["benchmark"]),
        float(ref["portfolio_cash"]),
        float(ref["benchmark_cash"]),
        DAY,
    )
    t = i.Taxonomy(
        "Fictional Research Hierarchy",
        "v1",
        DAY,
        hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        tuple(
            (
                i.Classification(s, sector, industry, "2000-01-01", DAY, "stipulated fixture")
                for s, sector, industry in zip(
                    ids,
                    ("Tech", "Tech", "Defensive"),
                    ("Hardware", "Services", "Services"),
                    strict=True,
                )
            )
        ),
        (("Tech", "Hardware"), ("Tech", "Services"), ("Defensive", "Services"), ("Empty", "Empty")),
    )
    cov = i.FrozenCovariance(
        ids,
        tuple(tuple(row) for row in ref["covariance"]),
        DAY,
        1,
        "one_session",
        fingerprint(ref),
        "stipulated one-session covariance",
    )
    return (w, t, cov)


def limit(
    *,
    level: i.Level = "sector",
    group: i.Group = ("sector", "Tech"),
    kind: Literal["absolute", "active"] = "absolute",
    enabled: bool = True,
    lower: str | None = None,
    upper: str | None = "0.60",
) -> i.ExposureLimit:
    assert kind in ("absolute", "active")
    return i.ExposureLimit(level, group, kind, enabled, lower, upper, "fictional user profile")


def test_hand_derived_nested_exposures_negative_euler_and_cross_variances() -> None:
    w, t, cov = inputs()
    r = i.estimate(w, t, (), cov)
    assert r.status == "estimated-diagnostic"
    rows = {(e.level, e.group): e for e in r.exposures}
    tech = rows["sector", ("sector", "Tech")]
    assert (tech.portfolio, tech.benchmark, tech.active) == pytest.approx((0.6, 0.4, 0.2))
    for level in ("sector", "industry"):
        assert math.fsum(e.portfolio for e in r.exposures if e.level == level) == pytest.approx(
            1.0, abs=1e-14
        )
        assert math.fsum(e.benchmark for e in r.exposures if e.level == level) == pytest.approx(
            1.0, abs=1e-14
        )
        assert math.fsum(e.active for e in r.exposures if e.level == level) == pytest.approx(
            0.0, abs=1e-14
        )
    assert rows["industry", ("industry", "Tech", "Services")].active == pytest.approx(-0.2)
    assert rows["industry", ("industry", "Defensive", "Services")].active == pytest.approx(-0.2)
    a = r.attribution
    assert a is not None
    expected = json.loads(REFERENCE.read_text())["expected"]
    with localcontext() as ctx:
        ctx.prec = 80
        variance = Decimal(51) / Decimal(6250)
        te = variance.sqrt()
        assert a.variance == pytest.approx(float(variance), rel=2e-15)
        assert a.tracking_error == pytest.approx(float(te), rel=2e-15)
        for security, numerator in zip(w.security_ids, expected["euler_numerators"], strict=True):
            f = Fraction(numerator)
            oracle = Decimal(f.numerator) / Decimal(f.denominator) / te
            actual = next(x for x in a.securities if x.group == ("security", security))
            assert actual.euler == pytest.approx(float(oracle), rel=2e-14)
    assert next(x for x in a.securities if x.group == ("security", "FICTIONAL-B")).euler < 0
    for rows_a, cross in (
        (a.sectors, a.sector_cross_variance),
        (a.industries, a.industry_cross_variance),
    ):
        assert sum(x.euler for x in rows_a) == pytest.approx(a.tracking_error, abs=1e-15)
        assert sum(
            x.fraction_of_te for x in rows_a if x.fraction_of_te is not None
        ) == pytest.approx(1)
        assert sum(x.standalone_variance for x in rows_a) + cross == pytest.approx(a.variance)
        cash = next(x for x in rows_a if x.group == i.CASH)
        assert cash.euler == cash.standalone_variance == 0
    assert a.sector_cross_variance == pytest.approx(
        float(Fraction(expected["sector_cross_variance"]))
    )
    assert a.industry_cross_variance == pytest.approx(
        float(Fraction(expected["industry_cross_variance"]))
    )
    tech_contribution = next(x.euler for x in a.sectors if x.group == ("sector", "Tech"))
    assert tech_contribution == pytest.approx(
        sum(x.euler for x in a.industries if x.group[:2] == ("industry", "Tech"))
    )


def test_explicit_limits_exact_boundaries_disabled_absent_group_and_negative_active() -> None:
    w, t, cov = inputs()
    ls = (
        limit(),
        limit(upper="0.599999999999"),
        limit(kind="active", lower="0.20", upper="0.20"),
        limit(
            level="industry",
            group=("industry", "Tech", "Services"),
            kind="active",
            lower="-0.20",
            upper="-0.20",
        ),
        limit(enabled=False, lower=None, upper=None),
        limit(group=("sector", "Empty"), lower="0", upper="0"),
    )
    r = i.estimate(w, t, ls, cov)
    assert [x.status for x in r.limits] == [
        "review-required",
        "breach",
        "breach",
        "breach",
        "disabled",
        "review-required",
    ]
    assert r.status == "diagnostic-breach"
    assert tuple(item.index for item in r.limits) == tuple(range(len(ls)))


def test_missing_and_partial_classification_preserve_weights_and_scope_blockers() -> None:
    w, t, cov = inputs()
    ls = (
        limit(),
        limit(level="industry", group=("industry", "Tech", "Services")),
        limit(group=i.CASH, upper="0.20"),
        limit(enabled=False),
    )
    partial = replace(t.records[1], industry=None, unknown_reasons=("source unavailable",))
    r = i.estimate(w, replace(t, records=(t.records[0], partial, t.records[2])), ls, cov)
    assert r.status == "diagnostic-incomplete"
    assert [x.status for x in r.limits] == [
        "review-required",
        "blocked",
        "review-required",
        "disabled",
    ]
    unknown = next(e for e in r.exposures if e.group == ("unknown-industry", "Tech"))
    assert unknown.portfolio == pytest.approx(0.1)
    assert unknown.benchmark == pytest.approx(0.3)
    assert "source unavailable" in r.issues[0]
    missing = i.estimate(w, replace(t, records=t.records[1:]), ls, cov)
    assert missing.limits[0].status == "blocked"
    assert missing.attribution is not None
    assert any(e.group == i.UNKNOWN for e in missing.exposures)
    assert math.fsum(
        e.portfolio for e in missing.exposures if e.level == "sector"
    ) == pytest.approx(1.0)


@pytest.mark.parametrize("nullspace", [False, True])
def test_zero_te_zero_contributions_undefined_percentages(nullspace: bool) -> None:
    w, t, cov = inputs()
    if nullspace:
        w = replace(w, portfolio=(0.6, 0.1, 0.1), benchmark=(0.2, 0.5, 0.1))
        cov = replace(cov, matrix=((0.04, 0.04, 0), (0.04, 0.04, 0), (0, 0, 0)))
    else:
        w = replace(w, portfolio=w.benchmark, portfolio_cash=w.benchmark_cash)
    a = i.estimate(w, t, (), cov).attribution
    assert a is not None
    assert a.tracking_error == a.variance == 0
    for row in (*a.securities, *a.sectors, *a.industries):
        assert row.euler == 0
        assert row.fraction_of_te is None


def test_selected_cash_dilution_and_explicit_benchmark_cash() -> None:
    w, t, cov = inputs()
    w = replace(w, portfolio=(0.25, 0.05, 0.1), portfolio_cash=0.6)
    r = i.estimate(w, t, (limit(group=i.CASH, kind="active", upper="0.39"),), cov)
    cash = next(e for e in r.exposures if e.level == "sector" and e.group == i.CASH)
    assert cash.active == pytest.approx(0.4)
    assert r.limits[0].status == "breach"
    assert next(e for e in r.exposures if e.group == ("sector", "Tech")).portfolio == pytest.approx(
        0.3
    )
    assert r.attribution is not None
    assert next(e for e in r.attribution.securities if e.group == i.CASH).euler == 0


@pytest.mark.parametrize(
    "change",
    [
        {"matrix": ((1.0, 2.0, 0), (2.0, 1.0, 0), (0, 0, 1.0))},
        {"matrix": ((1.0, 0, 0), (0.1, 1.0, 0), (0, 0, 1.0))},
        {"matrix": ((float("nan"), 0, 0), (0, 1.0, 0), (0, 0, 1.0))},
        {"matrix": ((float("inf"), 0, 0), (0, 1.0, 0), (0, 0, 1.0))},
        {"matrix": ((1.0,),)},
        {"security_ids": ("FICTIONAL-B", "FICTIONAL-A", "FICTIONAL-C")},
        {"cutoff": "2000-03-05"},
        {"horizon": 0},
        {"units": "percent-return-squared"},
        {"source_identity": ""},
        {"measure": "unknown"},
    ],
)
def test_invalid_covariance_retained_without_fallback(change: dict[str, object]) -> None:
    w, t, cov = inputs()
    bad = replace(cov, **cast(Any, change))
    r = i.estimate(w, t, (), bad)
    assert r.attribution is None and r.status == "diagnostic-incomplete"
    assert r.exposures
    assert r.issues[0].startswith("covariance:")


@pytest.mark.parametrize(
    "mutation",
    [
        "sum",
        "duplicate",
        "negative",
        "future",
        "blank",
        "unknown-no-reason",
        "duplicate-record",
        "unversioned",
        "taxonomy-invention",
    ],
)
def test_invalid_weight_or_taxonomy_evidence_refuses(mutation: str) -> None:
    w, t, cov = inputs()
    if mutation == "sum":
        w = replace(w, portfolio_cash=0.19)
    if mutation == "duplicate":
        w = replace(w, security_ids=(w.security_ids[0],) * 3)
    if mutation == "negative":
        w = replace(w, portfolio=(-0.5, 0.1, 1.2))
    if mutation == "future":
        t = replace(t, records=(replace(t.records[0], effective="2001-01-01"), *t.records[1:]))
    if mutation == "blank":
        t = replace(t, records=(replace(t.records[0], evidence=""), *t.records[1:]))
    if mutation == "unknown-no-reason":
        t = replace(t, records=(replace(t.records[0], sector=None, industry=None), *t.records[1:]))
    if mutation == "duplicate-record":
        t = replace(t, records=(*t.records, t.records[0]))
    if mutation == "unversioned":
        t = replace(t, version="")
    if mutation == "taxonomy-invention":
        t = replace(t, records=(replace(t.records[0], sector="Invented"), *t.records[1:]))
    with pytest.raises(ValueError):
        i.estimate(w, t, (), cov)


@pytest.mark.parametrize(
    "bad",
    [
        limit(upper=None),
        limit(lower="0.7", upper="0.6"),
        limit(group=("sector", "Typo")),
        limit(level="industry", group=("industry", "Services")),
    ],
)
def test_invalid_limit_never_silently_passes(bad: i.ExposureLimit) -> None:
    w, t, cov = inputs()
    with pytest.raises(i.IndustryUnavailable):
        i.estimate(w, t, (bad,), cov)


def test_composed_forecast_consumer_uses_same_matrix_and_units() -> None:
    rng = np.random.Generator(np.random.PCG64(623))
    returns = rng.standard_normal((64, 3)) * 0.01
    sessions = tuple((date(2000, 1, 1) + timedelta(days=j)).isoformat() for j in range(64))
    scalar_inputs = tuple(
        v.VolatilityInput(
            tuple(float(x) for x in returns[:, j]),
            f"FICTIONAL-{j}",
            sessions,
            sessions[-1],
            "fictional-grid",
            "UTC",
            "returns-only",
            "decimal",
            fingerprint(returns[:, j].tolist()),
            "primitive",
            64,
        )
        for j in range(3)
    )
    result = c.fit_covariance(scalar_inputs)
    w, t, _ = inputs()
    w = replace(w, security_ids=result.security_ids, as_of=str(result.cutoff))
    t = replace(
        t,
        as_of=w.as_of,
        records=tuple(
            replace(r, security_id=s) for r, s in zip(t.records, w.security_ids, strict=True)
        ),
    )
    base = None
    for measure in ("one_session", "cumulative", "average_daily", "annualized"):
        frozen = i.from_composition(result, measure)
        r = i.estimate(w, t, (), frozen)
        assert r.attribution is not None, r.issues
        assert result.projection is not None
        assert frozen.matrix == getattr(result.projection, measure)
        assert frozen.horizon == (1 if measure == "one_session" else result.horizon)
        assert frozen.source_identity == result.identity_sha256
        assert frozen.projection_identity == result.projection.identity_sha256
        if measure == "average_daily":
            base = r.attribution.tracking_error
        if measure == "annualized":
            assert base is not None
            assert r.attribution.tracking_error == pytest.approx(base * math.sqrt(252))
    with pytest.raises(i.IndustryUnavailable):
        i.from_composition(replace(result, status="unavailable"), "one_session")
    assert result.projection is not None
    for bad in (
        replace(result, security_ids=tuple(reversed(result.security_ids))),
        replace(
            result, projection=replace(result.projection, annualized=result.projection.one_session)
        ),
        replace(result, identity_sha256="a" * 64),
    ):
        with pytest.raises(i.IndustryUnavailable):
            i.from_composition(bad, "one_session")


def test_classification_correction_and_aligned_permutation_preserve_numerical_authority() -> None:
    w, t, cov = inputs()
    first = i.estimate(w, t, (), cov)
    correction = replace(
        t.records[1],
        sector="Defensive",
        recorded="2000-04-01",
        corrections=("fictional correction",),
    )
    second = i.estimate(
        w, replace(t, version="v2", records=(t.records[0], correction, t.records[2])), (), cov
    )
    assert first.attribution is not None and second.attribution is not None
    assert first.attribution.tracking_error == second.attribution.tracking_error
    assert next(
        e for e in second.exposures if e.group == ("sector", "Tech")
    ).portfolio == pytest.approx(0.5)
    assert i.estimate(w, t, (), cov) == first
    order = (2, 0, 1)
    moved = replace(
        w,
        security_ids=tuple(w.security_ids[j] for j in order),
        portfolio=tuple(w.portfolio[j] for j in order),
        benchmark=tuple(w.benchmark[j] for j in order),
    )
    matrix = replace(
        cov,
        security_ids=moved.security_ids,
        matrix=tuple(tuple(cov.matrix[j][k] for k in order) for j in order),
    )
    permuted = i.estimate(moved, t, (), matrix)
    assert first.exposures == permuted.exposures and permuted.attribution is not None
    assert first.attribution.tracking_error == pytest.approx(permuted.attribution.tracking_error)
