"""Frozen synthetic hierarchy diagnostics using one identified stock covariance.

Exact exposure arithmetic is separate from floating point covariance diagnostics.
Cash is a preserved zero-price-shock bucket. No financial readiness is asserted.
"""

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl

from prosper import advisory
from prosper import covariance as covariance_model
from prosper.covariance import CovarianceResult, Matrix
from prosper.exact import ExactValue, Sign
from prosper.innovations import fingerprint

VERSION = "synthetic-industry-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CASH = ("cash", "selected-residual-USD")
UNKNOWN = ("unknown",)
Level = Literal["sector", "industry"]
Measure = Literal["one_session", "cumulative", "average_daily", "annualized"]
Group = tuple[str, ...]


class IndustryUnavailable(ValueError):
    """Invalid evidence is refused without renormalization or numerical repair."""


@dataclass(frozen=True)
class ExactWeight:
    """Explicit canonical derived ratio; source decimals remain separate evidence."""

    numerator: str
    denominator: str

    def __post_init__(self) -> None:
        for part in (self.numerator, self.denominator):
            if (
                not isinstance(part, str)
                or len(part) > 128
                or re.fullmatch(r"0|[1-9][0-9]*", part, re.ASCII) is None
            ):
                raise IndustryUnavailable("bounded canonical weight integers required")
        n, d = int(self.numerator), int(self.denominator)
        if d <= 0 or n > d or math.gcd(n, d) != 1:
            raise IndustryUnavailable("reduced weight ratio in [0,1] required")

    @classmethod
    def from_fraction(cls, value: Fraction) -> "ExactWeight":
        return cls(str(value.numerator), str(value.denominator))


Weight = str | ExactWeight


@dataclass(frozen=True)
class Classification:
    security_id: str
    sector: str | None
    industry: str | None
    effective: str
    recorded: str
    evidence: str
    unknown_reasons: tuple[str, ...] = ()
    corrections: tuple[str, ...] = ()


@dataclass(frozen=True)
class Taxonomy:
    name: str
    version: str
    as_of: str
    source_sha256: str
    records: tuple[Classification, ...]
    hierarchy: tuple[tuple[str, str], ...]
    scope: str = "explicitly-stipulated-synthetic"


@dataclass(frozen=True)
class Weights:
    """Decimal source lexemes or explicit exact ratios use the same sleeve NAV.

    The NAV identities identify each basket's own denominator/evidence. No whole
    account or untouched cash is included. Complete baskets must sum exactly to 1.
    """

    security_ids: tuple[str, ...]
    portfolio: tuple[Weight, ...]
    benchmark: tuple[Weight, ...]
    portfolio_cash: Weight
    benchmark_cash: Weight
    portfolio_nav_identity: str
    benchmark_nav_identity: str
    as_of: str


@dataclass(frozen=True)
class ExposureLimit:
    level: Level
    group: Group
    kind: Literal["absolute", "active"]
    enabled: bool
    lower: str | None
    upper: str | None
    evidence: str


@dataclass(frozen=True)
class Exposure:
    level: Level
    group: Group
    portfolio: str
    benchmark: str
    active: str


@dataclass(frozen=True)
class LimitResult:
    index: int
    status: str
    value: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FrozenCovariance:
    security_ids: tuple[str, ...]
    matrix: Matrix
    cutoff: str
    horizon: int
    measure: Measure
    source_identity: str
    approximation: str
    units: str = "decimal-return-squared"
    scope: str = "explicitly-stipulated-synthetic"
    projection_identity: str | None = None
    annualization: int = 252


@dataclass(frozen=True)
class Contribution:
    group: Group
    euler: float
    fraction_of_te: float | None
    standalone_variance: float
    standalone_risk: float


@dataclass(frozen=True)
class Attribution:
    variance: float
    tracking_error: float
    securities: tuple[Contribution, ...]
    sectors: tuple[Contribution, ...]
    industries: tuple[Contribution, ...]
    sector_cross_variance: float
    industry_cross_variance: float
    covariance_identity: str


@dataclass(frozen=True)
class IndustryResult:
    status: str
    issues: tuple[str, ...]
    weights: Weights
    taxonomy: Taxonomy
    limits: tuple[ExposureLimit, ...]
    covariance: FrozenCovariance | None
    exposures: tuple[Exposure, ...]
    limit_results: tuple[LimitResult, ...]
    attribution: Attribution | None
    input_sha256: str
    identity_sha256: str


@dataclass(frozen=True)
class EstimatedWeights:
    security_ids: tuple[str, ...]
    portfolio: tuple[float, ...]
    benchmark: tuple[float, ...]
    portfolio_cash: float
    benchmark_cash: float
    as_of: str


@dataclass(frozen=True)
class EstimatedExposure:
    level: Level
    group: Group
    portfolio: float
    benchmark: float
    active: float


@dataclass(frozen=True)
class EstimatedLimit:
    index: int
    status: str
    value: float | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndustryEstimate:
    status: str
    issues: tuple[str, ...]
    exposures: tuple[EstimatedExposure, ...]
    limits: tuple[EstimatedLimit, ...]
    attribution: Attribution | None


def from_composition(result: CovarianceResult, measure: Measure) -> FrozenCovariance:
    """Bind the exact forecast matrix/order/horizon/units to its parent identity."""
    if (
        result.status != "qualified-synthetic-forecast"
        or result.issues
        or result.projection is None
        or result.cutoff is None
    ):
        raise IndustryUnavailable("eligible complete covariance forecast required")
    if measure not in ("one_session", "cumulative", "average_daily", "annualized"):
        raise IndustryUnavailable("explicit forecast measure required")
    replayed = covariance_model.compose_covariance(
        result.scalars, result.dcc_fit, horizon=result.horizon
    )
    if replayed != result:
        raise IndustryUnavailable("covariance evidence differs from identified component replay")
    p = result.projection
    return FrozenCovariance(
        result.security_ids,
        getattr(p, measure),
        result.cutoff,
        1 if measure == "one_session" else p.horizon,
        measure,
        result.identity_sha256,
        p.approximation,
        p.units,
        "qualified-synthetic-composition",
        p.identity_sha256,
        p.annualization,
    )


def _date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise IndustryUnavailable("canonical ISO date required")
    return parsed


def _weight(value: Weight) -> Fraction:
    if isinstance(value, ExactWeight):
        return Fraction(int(value.numerator), int(value.denominator))
    return Fraction(ExactValue(value, Sign.NONNEGATIVE, "weight").value)


def _bound(value: str) -> Fraction:
    return Fraction(ExactValue(value, Sign.SIGNED, "limit").value)


def _groups(record: Classification | None) -> tuple[Group, Group]:
    if record is None or record.sector is None:
        return UNKNOWN, UNKNOWN
    sector = ("sector", record.sector)
    industry = (
        ("industry", record.sector, record.industry)
        if record.industry is not None
        else ("unknown-industry", record.sector)
    )
    return sector, industry


def _validate(
    w: Weights, taxonomy: Taxonomy, limits: tuple[ExposureLimit, ...]
) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    n = len(w.security_ids)
    if (
        not n
        or len(set(w.security_ids)) != n
        or any(not s.strip() for s in w.security_ids)
        or len(w.portfolio) != n
        or len(w.benchmark) != n
        or not w.portfolio_nav_identity.strip()
        or not w.benchmark_nav_identity.strip()
    ):
        raise IndustryUnavailable("ordered complete weights and NAV evidence required")
    _date(w.as_of)
    p = tuple(_weight(s) for s in (*w.portfolio, w.portfolio_cash))
    b = tuple(_weight(s) for s in (*w.benchmark, w.benchmark_cash))
    if sum(p) != 1 or sum(b) != 1:
        raise IndustryUnavailable("complete basket weights must sum exactly to one")
    _validate_metadata(w, taxonomy, limits)
    for limit in limits:
        lo = _bound(limit.lower) if limit.lower is not None else None
        hi = _bound(limit.upper) if limit.upper is not None else None
        if (limit.enabled and lo is None and hi is None) or (
            lo is not None and hi is not None and lo > hi
        ):
            raise IndustryUnavailable("enabled limit bounds required and ordered")
    return p, b


def _validate_metadata(
    w: Weights | EstimatedWeights, taxonomy: Taxonomy, limits: tuple[ExposureLimit, ...]
) -> None:
    if (
        taxonomy.scope != "explicitly-stipulated-synthetic"
        or not taxonomy.name.strip()
        or not taxonomy.version.strip()
        or len(taxonomy.source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in taxonomy.source_sha256)
        or _date(taxonomy.as_of) > _date(w.as_of)
    ):
        raise IndustryUnavailable("dated stipulated synthetic taxonomy evidence required")
    ids: set[str] = set()
    if (
        (not taxonomy.hierarchy and isinstance(w, Weights))
        or len(set(taxonomy.hierarchy)) != len(taxonomy.hierarchy)
        or any(not s.strip() or not i.strip() for s, i in taxonomy.hierarchy)
    ):
        raise IndustryUnavailable("explicit unique synthetic hierarchy required")
    known_sectors = {s for s, _ in taxonomy.hierarchy}
    for r in taxonomy.records:
        if (
            r.security_id in ids
            or r.security_id not in w.security_ids
            or not r.evidence.strip()
            or (r.sector is not None and not r.sector.strip())
            or (r.industry is not None and (not r.industry.strip() or r.sector is None))
            or ((r.sector is None or r.industry is None) and not r.unknown_reasons)
            or (r.sector is not None and r.industry is not None and r.unknown_reasons)
            or (r.sector is not None and r.sector not in known_sectors)
            or (r.industry is not None and (r.sector, r.industry) not in taxonomy.hierarchy)
            or any(not x.strip() for x in (*r.unknown_reasons, *r.corrections))
            or _date(r.effective) > _date(taxonomy.as_of)
        ):
            raise IndustryUnavailable("contradictory, duplicate or undated classification")
        _date(r.recorded)  # Known time is retained; no point-in-time historical claim.
        ids.add(r.security_id)
    for limit in limits:
        valid_groups = (
            {("sector", s) for s in known_sectors}
            if limit.level == "sector"
            else {("industry", s, i) for s, i in taxonomy.hierarchy}
        )
        if (
            limit.level not in ("sector", "industry")
            or limit.kind not in ("absolute", "active")
            or type(limit.enabled) is not bool
            or not limit.evidence.strip()
            or not limit.group
            or (limit.group != CASH and limit.group not in valid_groups)
            or (limit.group != CASH and limit.group[0] != limit.level)
            or (limit.group != CASH and len(limit.group) != (2 if limit.level == "sector" else 3))
            or any(not s.strip() for s in limit.group)
        ):
            raise IndustryUnavailable("explicit limit scope/state/evidence required")


def _attribution(
    w: Weights | EstimatedWeights,
    c: FrozenCovariance,
    a: tuple[Fraction, ...] | tuple[float, ...],
    sectors: tuple[Group, ...],
    industries: tuple[Group, ...],
) -> Attribution:
    if (
        c.security_ids != w.security_ids
        or c.cutoff != w.as_of
        or type(c.horizon) is not int
        or c.horizon not in (1, 21)
        or (c.measure == "one_session" and c.horizon != 1)
        or type(c.annualization) is not int
        or c.annualization != 252
        or c.measure not in ("one_session", "cumulative", "average_daily", "annualized")
        or c.units != "decimal-return-squared"
        or not c.source_identity.strip()
        or not c.approximation.strip()
        or c.scope not in ("explicitly-stipulated-synthetic", "qualified-synthetic-composition")
        or (c.scope == "qualified-synthetic-composition" and not c.projection_identity)
    ):
        raise IndustryUnavailable("covariance scope/order/cutoff/units do not match")
    n = len(w.security_ids)
    matrix = np.asarray(c.matrix, dtype=float)
    if (
        matrix.shape != (n, n)
        or not np.isfinite(matrix).all()
        or not np.allclose(matrix, matrix.T, rtol=1e-12, atol=0)
    ):
        raise IndustryUnavailable("finite symmetric complete covariance required")
    eigenvalues = np.linalg.eigvalsh(matrix)
    # Roundoff tolerance only, no clipping, jitter, symmetrization or substitution.
    scale = float(np.max(np.abs(matrix)))
    if eigenvalues[0] < -1e-12 * scale:
        raise IndustryUnavailable("covariance is not positive semidefinite")
    active = np.array([float(v) for v in a])
    augmented = np.zeros((n + 1, n + 1))
    augmented[:n, :n] = matrix  # Cash weight is preserved with zero price shock.
    ca = augmented @ active
    variance = float(active @ ca)
    if not math.isfinite(variance) or variance < 0:
        raise IndustryUnavailable("unrepresentable or negative active variance")
    te = math.sqrt(variance)
    euler = active * ca / te if te > 0 else np.zeros(n + 1)
    if not np.isfinite(euler).all() or (te == 0 and np.any(np.abs(ca) > 1e-12 * scale)):
        raise IndustryUnavailable("unrepresentable Euler or inconsistent zero variance")

    def grouped(groups: tuple[Group, ...]) -> tuple[Contribution, ...]:
        rows = []
        for group in sorted(set(groups)):
            indices = [i for i, g in enumerate(groups) if g == group]
            sub = active[indices]
            standalone = float(sub @ augmented[np.ix_(indices, indices)] @ sub)
            contribution = float(math.fsum(float(euler[i]) for i in indices))
            if not math.isfinite(standalone) or standalone < 0:
                raise IndustryUnavailable("unrepresentable or negative group variance")
            rows.append(
                Contribution(
                    group,
                    contribution,
                    contribution / te if te > 0 else None,
                    standalone,
                    math.sqrt(standalone),
                )
            )
        return tuple(rows)

    securities = grouped(tuple(("security", s) for s in w.security_ids) + (CASH,))
    sector_rows, industry_rows = grouped(sectors), grouped(industries)
    return Attribution(
        variance,
        te,
        securities,
        sector_rows,
        industry_rows,
        variance - math.fsum(r.standalone_variance for r in sector_rows),
        variance - math.fsum(r.standalone_variance for r in industry_rows),
        fingerprint(asdict(c)),
    )


def diagnose(
    weights: Weights,
    taxonomy: Taxonomy,
    limits: tuple[ExposureLimit, ...],
    covariance: FrozenCovariance | None,
) -> IndustryResult:
    """Diagnose frozen synthetic weights; never certify an actionable portfolio.

    Invalid structural input raises. Missing classification stays in explicit
    unknown buckets; applicable limits are blocked. Invalid covariance retains
    exposures and the original covariance with an unavailable attribution.
    """
    p, b = _validate(weights, taxonomy, limits)
    records = {r.security_id: r for r in taxonomy.records}
    groups = tuple(_groups(records.get(s)) for s in weights.security_ids)
    sectors = tuple(g[0] for g in groups) + (CASH,)
    industries = tuple(g[1] for g in groups) + (CASH,)
    issues = []
    for security in weights.security_ids:
        r = records.get(security)
        if r is None:
            issues.append(f"classification:{security}:missing")
        elif r.sector is None or r.industry is None:
            issues.append(f"classification:{security}:" + ";".join(r.unknown_reasons))
    a = tuple(x - y for x, y in zip(p, b, strict=True))
    exposures = []
    values: dict[tuple[Level, Group, str], Fraction] = {}
    incomplete: dict[Level, bool] = {}
    levels: tuple[tuple[Level, tuple[Group, ...]], ...] = (
        ("sector", sectors),
        ("industry", industries),
    )
    for level, level_groups in levels:
        incomplete[level] = any(
            g[0].startswith("unknown") and (p[i] != 0 or b[i] != 0)
            for i, g in enumerate(level_groups)
        )
        for group in sorted(set(level_groups)):
            pw = sum((p[i] for i, g in enumerate(level_groups) if g == group), Fraction())
            bw = sum((b[i] for i, g in enumerate(level_groups) if g == group), Fraction())
            exposures.append(Exposure(level, group, str(pw), str(bw), str(pw - bw)))
            values[level, group, "absolute"] = pw
            values[level, group, "active"] = pw - bw
    limit_results = []
    for index, limit in enumerate(limits):
        value = values.get((limit.level, limit.group, limit.kind), Fraction())
        reasons: tuple[str, ...]
        if not limit.enabled:
            state, reasons = "disabled", ()
        elif incomplete[limit.level] and limit.group != CASH:
            state, reasons = "blocked", ("incomplete classification at constrained level",)
        else:
            breach = (limit.lower is not None and value < _bound(limit.lower)) or (
                limit.upper is not None and value > _bound(limit.upper)
            )
            state, reasons = ("breach" if breach else "pass"), ()
        limit_results.append(
            LimitResult(index, state, None if state == "blocked" else str(value), reasons)
        )
    attribution = None
    if covariance is None:
        issues.append("covariance:missing")
    else:
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                attribution = _attribution(weights, covariance, a, sectors, industries)
        except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            issues.append(f"covariance:{exc}")
    status = "diagnostic-incomplete" if issues else "qualified-synthetic-diagnostic"
    if any(r.status == "breach" for r in limit_results):
        status = "diagnostic-breach" if not issues else "diagnostic-incomplete"
    inputs = fingerprint(
        [
            asdict(weights),
            asdict(taxonomy),
            [asdict(v) for v in limits],
            _covariance_payload(covariance) if covariance else None,
        ]
    )
    outputs = [
        status,
        issues,
        [asdict(e) for e in exposures],
        [asdict(r) for r in limit_results],
        asdict(attribution) if attribution else None,
    ]
    identity = fingerprint([VERSION, IMPLEMENTATION_SHA256, np.__version__, inputs, outputs])
    return IndustryResult(
        status,
        tuple(issues),
        weights,
        taxonomy,
        limits,
        covariance,
        tuple(exposures),
        tuple(limit_results),
        attribution,
        inputs,
        identity,
    )


def _covariance_payload(covariance: FrozenCovariance) -> dict[str, object]:
    """Nonfinite evidence has explicit stable text identity, never JSON NaN."""
    payload = asdict(covariance)
    payload["matrix"] = tuple(tuple(float(v).hex() for v in row) for row in covariance.matrix)
    return payload


def estimate(
    weights: EstimatedWeights,
    taxonomy: Taxonomy,
    limits: tuple[ExposureLimit, ...] = (),
    covariance: FrozenCovariance | None = None,
) -> IndustryEstimate:
    """Polars exposure estimates; diagnose remains the legacy exact-format path."""
    n = len(weights.security_ids)
    if (
        not n
        or len(set(weights.security_ids)) != n
        or any(not s.strip() for s in weights.security_ids)
        or len(weights.portfolio) != n
        or len(weights.benchmark) != n
        or not advisory.unit_sum((*weights.portfolio, weights.portfolio_cash))
        or not advisory.unit_sum((*weights.benchmark, weights.benchmark_cash))
    ):
        raise IndustryUnavailable("complete finite ordered estimated weights required")
    _date(weights.as_of)
    _validate_metadata(weights, taxonomy, limits)
    records = {r.security_id: r for r in taxonomy.records}
    frame = pl.DataFrame(
        {
            "security_id": weights.security_ids,
            "portfolio": weights.portfolio,
            "benchmark": weights.benchmark,
        },
        schema={"security_id": pl.String, "portfolio": pl.Float64, "benchmark": pl.Float64},
    ).with_row_index()
    groups = pl.DataFrame(
        [(r.security_id, list(_groups(r)[0]), list(_groups(r)[1])) for r in taxonomy.records],
        schema={
            "security_id": pl.String,
            "sector": pl.List(pl.String),
            "industry": pl.List(pl.String),
        },
        orient="row",
    )
    aligned = frame.join(groups, on="security_id", how="left", validate="1:1").sort("index")
    aligned = aligned.with_columns(pl.col("sector", "industry").fill_null(pl.lit(list(UNKNOWN))))
    cash = pl.DataFrame(
        [(n, "", weights.portfolio_cash, weights.benchmark_cash, list(CASH), list(CASH))],
        schema=aligned.schema,
        orient="row",
    )
    aligned = pl.concat([aligned, cash])
    issues = [
        f"classification:{sid}:"
        + ("missing" if sid not in records else ";".join(records[sid].unknown_reasons))
        for sid in weights.security_ids
        if sid not in records or records[sid].sector is None or records[sid].industry is None
    ]
    exposures: list[EstimatedExposure] = []
    incomplete: dict[str, bool] = {}
    sectors = tuple(tuple(g) for g in aligned.get_column("sector").to_list())
    industries = tuple(tuple(g) for g in aligned.get_column("industry").to_list())
    for level in ("sector", "industry"):
        grouped = aligned.group_by(level).agg(pl.col("portfolio", "benchmark").sum()).sort(level)
        incomplete[level] = False
        for group, p, b in grouped.iter_rows():
            if not math.isfinite(p) or not math.isfinite(b):
                raise IndustryUnavailable("nonfinite grouped exposure")
            if group[0].startswith("unknown") and (p != 0 or b != 0):
                incomplete[level] = True
            exposures.append(
                EstimatedExposure(
                    "sector" if level == "sector" else "industry", tuple(group), p, b, p - b
                )
            )
        for field in ("portfolio", "benchmark"):
            total = math.fsum(getattr(e, field) for e in exposures if e.level == level)
            if not math.isclose(total, 1.0, rel_tol=0, abs_tol=advisory.WEIGHT_TOLERANCE):
                raise IndustryUnavailable("grouped exposure reconciliation failed")
    limit_results = []
    by_group = {(e.level, e.group): e for e in exposures}
    reasons: tuple[str, ...]
    for index, limit in enumerate(limits):
        lo = advisory.decimal_value(limit.lower, signed=True) if limit.lower is not None else None
        hi = advisory.decimal_value(limit.upper, signed=True) if limit.upper is not None else None
        if (limit.enabled and lo is None and hi is None) or (
            lo is not None and hi is not None and lo > hi
        ):
            raise IndustryUnavailable("enabled limit bounds required and ordered")
        exposure = by_group.get((limit.level, limit.group))
        value = (
            (exposure.portfolio if limit.kind == "absolute" else exposure.active)
            if exposure
            else 0.0
        )
        bounds = tuple(
            advisory.number(s, signed=True) for s in (limit.lower, limit.upper) if s is not None
        )
        if not limit.enabled:
            state, reasons = "disabled", ()
        elif incomplete[limit.level] and limit.group != CASH:
            state, reasons = "blocked", ("incomplete classification at constrained level",)
        elif (lo is not None and value < float(lo)) or (hi is not None and value > float(hi)):
            state, reasons = "breach", ()
        elif any(abs(value - bound) <= advisory.WEIGHT_TOLERANCE for bound in bounds):
            state, reasons = "review-required", ("estimate is at a numerical limit boundary",)
        else:
            state, reasons = "pass", ()
        limit_results.append(
            EstimatedLimit(index, state, None if state == "blocked" else value, reasons)
        )
    attribution = None
    if covariance is None:
        issues.append("covariance:missing")
    else:
        active = tuple(
            p - b
            for p, b in zip(
                (*weights.portfolio, weights.portfolio_cash),
                (*weights.benchmark, weights.benchmark_cash),
                strict=True,
            )
        )
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                attribution = _attribution(weights, covariance, active, sectors, industries)
        except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            issues.append(f"covariance:{exc}")
    status = "diagnostic-incomplete" if issues else "estimated-diagnostic"
    if not issues and any(r.status == "breach" for r in limit_results):
        status = "diagnostic-breach"
    elif not issues and any(r.status == "review-required" for r in limit_results):
        status = "diagnostic-review-required"
    return IndustryEstimate(
        status,
        tuple(issues),
        tuple(exposures),
        tuple(limit_results),
        attribution,
    )
