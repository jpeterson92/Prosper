"""Independent written rational cases for hierarchy/exposure/covariance diagnostics."""

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from prosper import covariance as c
from prosper import industry as i
from prosper import volatility as v
from prosper.innovations import fingerprint

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/industry/reference.json"
DAY = "2000-03-04"


def inputs() -> tuple[i.Weights, i.Taxonomy, i.FrozenCovariance]:
    ref = json.loads(REFERENCE.read_text())
    ids = tuple(ref["security_ids"])
    w = i.Weights(
        ids,
        tuple(ref["portfolio"]),
        tuple(ref["benchmark"]),
        ref["portfolio_cash"],
        ref["benchmark_cash"],
        "fictional-stock-sleeve-plus-selected-USD-NAV-portfolio",
        "fictional-benchmark-NAV-including-declared-cash",
        DAY,
    )
    t = i.Taxonomy(
        "Fictional Research Hierarchy",
        "v1",
        DAY,
        hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        tuple(
            i.Classification(s, sector, industry, "2000-01-01", DAY, "stipulated fixture")
            for s, sector, industry in zip(
                ids,
                ("Tech", "Tech", "Defensive"),
                ("Hardware", "Services", "Services"),
                strict=True,
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
    return w, t, cov


def limit(
    *,
    level: i.Level = "sector",
    group: i.Group = ("sector", "Tech"),
    kind: str = "absolute",
    enabled: bool = True,
    lower: str | None = None,
    upper: str | None = "0.60",
) -> i.ExposureLimit:
    assert kind in ("absolute", "active")
    return i.ExposureLimit(level, group, kind, enabled, lower, upper, "fictional user profile")  # type: ignore[arg-type]


def test_hand_derived_nested_exposures_negative_euler_and_cross_variances() -> None:
    w, t, cov = inputs()
    r = i.diagnose(w, t, (), cov)
    assert r.status == "qualified-synthetic-diagnostic"
    assert r.weights.portfolio[0] == "0.5000"
    assert r.weights.portfolio_cash == "0.2000"
    rows = {(e.level, e.group): e for e in r.exposures}
    tech = rows["sector", ("sector", "Tech")]
    assert (tech.portfolio, tech.benchmark, tech.active) == ("3/5", "2/5", "1/5")
    for level in ("sector", "industry"):
        assert sum(Fraction(e.portfolio) for e in r.exposures if e.level == level) == 1
        assert sum(Fraction(e.benchmark) for e in r.exposures if e.level == level) == 1
        assert sum(Fraction(e.active) for e in r.exposures if e.level == level) == 0
    assert rows["industry", ("industry", "Tech", "Services")].active == "-1/5"
    assert rows["industry", ("industry", "Defensive", "Services")].active == "-1/5"
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
    r = i.diagnose(w, t, ls, cov)
    assert [x.status for x in r.limit_results] == [
        "pass",
        "breach",
        "pass",
        "pass",
        "disabled",
        "pass",
    ]
    assert r.status == "diagnostic-breach"
    assert r.limits == ls


def test_missing_and_partial_classification_preserve_weights_and_scope_blockers() -> None:
    w, t, cov = inputs()
    ls = (
        limit(),
        limit(level="industry", group=("industry", "Tech", "Services")),
        limit(group=i.CASH, upper="0.20"),
        limit(enabled=False),
    )
    partial = replace(t.records[1], industry=None, unknown_reasons=("source unavailable",))
    r = i.diagnose(w, replace(t, records=(t.records[0], partial, t.records[2])), ls, cov)
    assert r.status == "diagnostic-incomplete"
    assert [x.status for x in r.limit_results] == ["pass", "blocked", "pass", "disabled"]
    unknown = next(e for e in r.exposures if e.group == ("unknown-industry", "Tech"))
    assert unknown.portfolio == "1/10"
    assert unknown.benchmark == "3/10"
    assert "source unavailable" in r.issues[0]
    missing = i.diagnose(w, replace(t, records=t.records[1:]), ls, cov)
    assert missing.limit_results[0].status == "blocked"
    assert missing.attribution is not None  # Complete covariance, labeled unknown group.
    assert any(e.group == i.UNKNOWN for e in missing.exposures)
    assert missing.weights == w


@pytest.mark.parametrize("nullspace", [False, True])
def test_zero_te_zero_contributions_undefined_percentages(nullspace: bool) -> None:
    w, t, cov = inputs()
    if nullspace:
        w = replace(w, portfolio=("0.6", "0.1", "0.1"), benchmark=("0.2", "0.5", "0.1"))
        cov = replace(cov, matrix=((0.04, 0.04, 0), (0.04, 0.04, 0), (0, 0, 0)))
    else:
        w = replace(w, portfolio=w.benchmark, portfolio_cash=w.benchmark_cash)
    a = i.diagnose(w, t, (), cov).attribution
    assert a is not None
    assert a.tracking_error == a.variance == 0
    for row in (*a.securities, *a.sectors, *a.industries):
        assert row.euler == 0
        assert row.fraction_of_te is None


def test_selected_cash_dilution_and_explicit_benchmark_cash() -> None:
    w, t, cov = inputs()
    w = replace(w, portfolio=("0.25", "0.05", "0.10"), portfolio_cash="0.60")
    r = i.diagnose(w, t, (limit(group=i.CASH, kind="active", upper="0.39"),), cov)
    cash = next(e for e in r.exposures if e.level == "sector" and e.group == i.CASH)
    assert cash.active == "2/5"
    assert r.limit_results[0].status == "breach"
    assert next(e for e in r.exposures if e.group == ("sector", "Tech")).portfolio == "3/10"
    assert r.attribution is not None
    assert next(e for e in r.attribution.securities if e.group == i.CASH).euler == 0


def test_reclassification_recorded_time_and_source_change_identity_without_rewriting_old() -> None:
    w, t, cov = inputs()
    first = i.diagnose(w, t, (), cov)
    correction = replace(
        t.records[1],
        sector="Defensive",
        effective=DAY,
        recorded="2000-04-01",
        corrections=("reviewed fictional correction C1",),
    )
    changed = replace(t, version="v2", records=(t.records[0], correction, t.records[2]))
    second = i.diagnose(w, changed, (), cov)
    assert second.identity_sha256 != first.identity_sha256
    assert second.attribution is not None and first.attribution is not None
    assert second.attribution.tracking_error == first.attribution.tracking_error
    assert next(e for e in second.exposures if e.group == ("sector", "Tech")).portfolio == "1/2"
    assert i.diagnose(w, t, (), cov) == first
    for tax in (
        replace(t, source_sha256="a" * 64),
        replace(t, version="v3"),
        replace(t, records=(replace(t.records[0], recorded="2000-04-01"), *t.records[1:])),
    ):
        assert i.diagnose(w, tax, (), cov).identity_sha256 != first.identity_sha256


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
        {"scope": "real"},
        {"measure": "unknown"},
    ],
)
def test_invalid_covariance_retained_without_fallback(change: dict[str, object]) -> None:
    w, t, cov = inputs()
    bad = replace(cov, **change)  # type: ignore[arg-type]
    r = i.diagnose(w, t, (), bad)
    assert r.attribution is None and r.status == "diagnostic-incomplete"
    assert r.covariance is bad and r.weights == w
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
        w = replace(w, portfolio_cash="0.19")
    if mutation == "duplicate":
        w = replace(w, security_ids=(w.security_ids[0],) * 3)
    if mutation == "negative":
        w = replace(w, portfolio=("-0.5", "0.1", "1.2"))
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
        i.diagnose(w, t, (), cov)


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
        i.diagnose(w, t, (bad,), cov)


def test_future_forecast_identity_and_lexeme_changes_are_material() -> None:
    w, t, cov = inputs()
    first = i.diagnose(w, t, (), cov)
    for changed in (
        replace(cov, horizon=21, measure="cumulative"),
        replace(cov, measure="annualized"),
        replace(cov, source_identity="different retained forecast"),
    ):
        assert i.diagnose(w, t, (), changed).identity_sha256 != first.identity_sha256
    same_value = replace(w, portfolio=("0.50", *w.portfolio[1:]))
    second = i.diagnose(same_value, t, (), cov)
    assert second.exposures == first.exposures and second.attribution == first.attribution
    assert second.identity_sha256 != first.identity_sha256
    missing = i.diagnose(w, t, (), None)
    assert missing.attribution is None and missing.issues == ("covariance:missing",)


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
        r = i.diagnose(w, t, (), frozen)
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


def test_aligned_permutation_and_denominator_evidence_are_frozen() -> None:
    w, t, cov = inputs()
    original = i.diagnose(w, t, (), cov)
    order = (2, 0, 1)
    w2 = replace(
        w,
        security_ids=tuple(w.security_ids[j] for j in order),
        portfolio=tuple(w.portfolio[j] for j in order),
        benchmark=tuple(w.benchmark[j] for j in order),
    )
    c2 = replace(
        cov,
        security_ids=w2.security_ids,
        matrix=tuple(tuple(cov.matrix[j][k] for k in order) for j in order),
    )
    permuted = i.diagnose(w2, t, (), c2)
    assert original.exposures == permuted.exposures
    assert original.attribution is not None and permuted.attribution is not None
    assert original.attribution.tracking_error == pytest.approx(permuted.attribution.tracking_error)
    assert original.identity_sha256 != permuted.identity_sha256
    changed = i.diagnose(
        replace(w, portfolio_nav_identity="different included cash/NAV"), t, (), cov
    )
    assert changed.identity_sha256 != original.identity_sha256


def test_fresh_process_replay() -> None:
    command = [sys.executable, "-I", str(ROOT / "scripts/qualify_industry.py")]
    first = subprocess.check_output(command, cwd=ROOT)
    second = subprocess.check_output(command, cwd=ROOT)
    assert first == second
    assert json.loads(first)["result"]["status"] == "qualified-synthetic-diagnostic"
