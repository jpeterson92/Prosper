"""Pure stipulated synthetic basket valuation and exact weight qualification.

No source adapter, lookup, persistence, price forecast or financial readiness.
Every supplied row and unknown remains in the immutable result input evidence.
"""

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path

import polars as pl

from prosper import advisory, industry
from prosper.exact import ExactValue, ExactValueError, Sign
from prosper.innovations import fingerprint

VERSION = "synthetic-basket-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_ROWS = 10000


class BasketUnavailable(ValueError):
    """Invalid structural input or attempted consumption of blocked evidence."""


@dataclass(frozen=True)
class Evidence:
    source_sha256: str
    reference: str
    effective: str | None
    recorded: str | None
    valid_through: str | None
    unknown_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Fact:
    raw: str | None
    evidence: Evidence
    unknown_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Security:
    security_id: str | None
    currency: str | None
    asset_type: str
    evidence: Evidence
    unknown_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Position:
    row_id: str
    security: Security
    quantity: Fact
    reference_mark: Fact


@dataclass(frozen=True)
class BenchmarkRow:
    row_id: str
    security: Security
    weight: Fact
    unit: str


@dataclass(frozen=True)
class BasketInput:
    benchmark_name: str
    as_of: str
    known_at: str
    universe: tuple[str, ...]
    positions: tuple[Position, ...]
    benchmark: tuple[BenchmarkRow, ...]
    candidates: tuple[Security, ...]
    portfolio_cash: Fact
    benchmark_cash: Fact
    benchmark_cash_unit: str
    scope: str = "explicitly-stipulated-synthetic"


@dataclass(frozen=True)
class Issue:
    location: str
    code: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PositionValue:
    row_id: str
    value_usd: str | None


@dataclass(frozen=True)
class BasketResult:
    status: str
    issues: tuple[Issue, ...]
    data: BasketInput
    position_values: tuple[PositionValue, ...]
    portfolio_nav_usd: str | None
    benchmark_weight_sum: str | None
    benchmark_residual: str | None
    weights: industry.Weights | None
    input_sha256: str
    canonical_sha256: str
    identity_sha256: str


@dataclass(frozen=True)
class BasketEstimate:
    data: BasketInput
    status: str
    issues: tuple[Issue, ...]
    position_values: tuple[tuple[str, float | None], ...]
    portfolio_nav_usd: float | None
    benchmark_weight_sum: float | None
    weights: industry.EstimatedWeights | None
    version: str = "advisory-basket-v1"


def _text(value: str) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 256
        and bool(value.strip())
        and all(ord(c) >= 32 for c in value)
    )


def _day(value: str) -> date:
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BasketUnavailable("canonical ISO date required") from None
    if day.isoformat() != value:
        raise BasketUnavailable("canonical ISO date required")
    return day


def _evidence(
    e: Evidence, cutoff: date, known_at: date, location: str, issues: list[Issue]
) -> bool:
    if (
        not isinstance(e, Evidence)
        or not isinstance(e.source_sha256, str)
        or len(e.source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in e.source_sha256)
        or not _text(e.reference)
    ):
        raise BasketUnavailable("source hash and bounded reference required")
    _reasons(e.unknown_reasons)
    if e.effective is None or e.recorded is None or e.valid_through is None:
        if not e.unknown_reasons:
            raise BasketUnavailable("missing dates require explicit unknown reasons")
        issues.append(Issue(location, "unknown_evidence_dates", e.unknown_reasons))
        return False
    if e.unknown_reasons:
        issues.append(Issue(location, "contradictory_evidence_dates", e.unknown_reasons))
        return False
    effective, recorded, through = _day(e.effective), _day(e.recorded), _day(e.valid_through)
    if effective > through:
        issues.append(Issue(location, "contradictory_validity"))
        return False
    if effective > cutoff or recorded > known_at:
        issues.append(Issue(location, "future_fact"))
        return False
    if through < cutoff:
        issues.append(Issue(location, "stale_under_stipulated_validity"))
        return False
    return True


def _reasons(reasons: tuple[str, ...]) -> None:
    if type(reasons) is not tuple or len(reasons) > 32 or any(not _text(s) for s in reasons):
        raise BasketUnavailable("bounded immutable unknown reasons required")


def _fact(
    f: Fact,
    cutoff: date,
    known_at: date,
    location: str,
    issues: list[Issue],
    *,
    positive: bool = False,
) -> Fraction | None:
    if not isinstance(f, Fact) or (f.raw is not None and not isinstance(f.raw, str)):
        raise BasketUnavailable(
            "immutable fact with decimal source text or explicit unknown required"
        )
    valid = _evidence(f.evidence, cutoff, known_at, location, issues)
    _reasons(f.unknown_reasons)
    if f.raw is None:
        if not f.unknown_reasons:
            raise BasketUnavailable("missing fact requires explicit unknown reasons")
        issues.append(Issue(location, "unknown", f.unknown_reasons))
        return None
    if f.unknown_reasons:
        issues.append(Issue(location, "contradictory_known_and_unknown", f.unknown_reasons))
        return None
    try:
        value = ExactValue(f.raw, Sign.POSITIVE if positive else Sign.NONNEGATIVE, location)
    except ExactValueError as exc:
        issues.append(Issue(location, exc.code))
        return None
    return Fraction(value.value) if valid else None


def _security(
    s: Security, cutoff: date, known_at: date, location: str, issues: list[Issue]
) -> bool:
    if (
        not isinstance(s, Security)
        or (s.security_id is not None and not isinstance(s.security_id, str))
        or (s.currency is not None and not isinstance(s.currency, str))
        or not isinstance(s.asset_type, str)
    ):
        raise BasketUnavailable("immutable security with explicit identity/currency text required")
    valid = _evidence(s.evidence, cutoff, known_at, location, issues)
    _reasons(s.unknown_reasons)
    if s.security_id is None or s.currency is None:
        if not s.unknown_reasons:
            raise BasketUnavailable("unresolved security requires explicit reasons")
        issues.append(Issue(location, "unresolved_security", s.unknown_reasons))
        valid = False
    elif not _text(s.security_id) or s.unknown_reasons:
        issues.append(Issue(location, "contradictory_identity", s.unknown_reasons))
        valid = False
    if s.currency != "USD":
        issues.append(Issue(location, "unsupported_or_unknown_currency"))
        valid = False
    if s.asset_type != "stock":
        issues.append(Issue(location, "unsupported_asset_type"))
        valid = False
    return valid


def _weight(
    f: Fact, unit: str, cutoff: date, known_at: date, location: str, issues: list[Issue]
) -> Fraction | None:
    if unit == "exact-ratio":
        # Explicit derived rational weights never pass through a decimal/float
        # approximation. Original source observations stay in their own evidence.
        if not isinstance(f, Fact) or (f.raw is not None and not isinstance(f.raw, str)):
            raise BasketUnavailable("immutable fact with exact ratio text required")
        valid = _evidence(f.evidence, cutoff, known_at, location, issues)
        _reasons(f.unknown_reasons)
        if f.raw is None or f.unknown_reasons:
            issues.append(Issue(location, "unknown_or_contradictory_ratio", f.unknown_reasons))
            return None
        if re.fullmatch(r"(?:0|[1-9][0-9]{0,127})/[1-9][0-9]{0,127}", f.raw) is None:
            issues.append(Issue(location, "invalid_exact_ratio"))
            return None
        ratio = Fraction(f.raw)
        if f.raw != f"{ratio.numerator}/{ratio.denominator}":
            issues.append(Issue(location, "noncanonical_exact_ratio"))
            return None
        return ratio if valid else None
    value = _fact(f, cutoff, known_at, location, issues)
    if unit not in ("decimal", "percent"):
        issues.append(Issue(location, "explicit_weight_unit_required"))
        return None
    return value / (100 if unit == "percent" else 1) if value is not None else None


def qualify(data: BasketInput) -> BasketResult:
    """Retain partial evidence, emitting weights only for complete stipulated inputs.

    Source validity intervals are explicit synthetic inputs, not adopted freshness
    settings. Duplicate positions/weights are blocked instead of implicitly added.
    """
    if data.scope != "explicitly-stipulated-synthetic" or not _text(data.benchmark_name):
        raise BasketUnavailable("named explicitly stipulated synthetic basket required")
    cutoff = _day(data.as_of)
    known_at = _day(data.known_at)
    if known_at < cutoff:
        raise BasketUnavailable("knowledge cutoff cannot precede valuation cutoff")
    for rows in (data.universe, data.positions, data.benchmark, data.candidates):
        if type(rows) is not tuple or len(rows) > MAX_ROWS:
            raise BasketUnavailable("bounded immutable input rows required")
    if (
        not data.universe
        or any(not _text(s) for s in data.universe)
        or len(set(data.universe)) != len(data.universe)
    ):
        raise BasketUnavailable("explicit nonempty unique ordered universe required")
    if any(not isinstance(r, Position) for r in data.positions) or any(
        not isinstance(r, BenchmarkRow) for r in data.benchmark
    ):
        raise BasketUnavailable("immutable typed source rows required")
    issues: list[Issue] = []
    values = []
    unique_positions = True
    positions: dict[str, Fraction] = {}
    benchmark: dict[str, Fraction] = {}
    seen_securities: set[str] = set()
    seen_rows: set[str] = set()
    members: set[str] = set()
    for row in data.positions:
        loc = "position:" + row.row_id
        if not _text(row.row_id) or row.row_id in seen_rows:
            raise BasketUnavailable("unique bounded position row IDs required")
        seen_rows.add(row.row_id)
        ok = _security(row.security, cutoff, known_at, loc, issues)
        sid = row.security.security_id
        if sid is not None:
            members.add(sid)
            if sid in seen_securities:
                issues.append(Issue(loc, "duplicate_position_security"))
                unique_positions = False
            seen_securities.add(sid)
        qty = _fact(row.quantity, cutoff, known_at, loc + ":quantity", issues)
        mark = _fact(row.reference_mark, cutoff, known_at, loc + ":mark", issues, positive=True)
        value = qty * mark if ok and qty is not None and mark is not None else None
        values.append(PositionValue(row.row_id, str(value) if value is not None else None))
        if value is not None and sid is not None:
            positions[sid] = value
    seen_securities.clear()
    seen_rows.clear()
    source_weights: list[Fraction | None] = []
    for benchmark_row in data.benchmark:
        loc = "benchmark:" + benchmark_row.row_id
        if not _text(benchmark_row.row_id) or benchmark_row.row_id in seen_rows:
            raise BasketUnavailable("unique bounded benchmark row IDs required")
        seen_rows.add(benchmark_row.row_id)
        _security(benchmark_row.security, cutoff, known_at, loc, issues)
        weight = _weight(
            benchmark_row.weight, benchmark_row.unit, cutoff, known_at, loc + ":weight", issues
        )
        source_weights.append(weight)
        sid = benchmark_row.security.security_id
        if sid is not None:
            members.add(sid)
            if sid in seen_securities:
                issues.append(Issue(loc, "duplicate_benchmark_security"))
            seen_securities.add(sid)
            if weight is not None:
                benchmark[sid] = weight
    seen_securities.clear()
    for index, security in enumerate(data.candidates):
        loc = f"candidate:{index}"
        _security(security, cutoff, known_at, loc, issues)
        if security.security_id is not None:
            members.add(security.security_id)
            if security.security_id in seen_securities:
                issues.append(Issue(loc, "duplicate_candidate_security"))
            seen_securities.add(security.security_id)
    for sid in sorted(members - set(data.universe)):
        issues.append(Issue("universe:" + sid, "required_security_missing_from_order"))
    for sid in sorted(set(data.universe) - members):
        issues.append(Issue("universe:" + sid, "unattributed_universe_member"))
    cash = _fact(data.portfolio_cash, cutoff, known_at, "portfolio_cash", issues)
    benchmark_cash = _weight(
        data.benchmark_cash, data.benchmark_cash_unit, cutoff, known_at, "benchmark_cash", issues
    )
    nav = None
    if cash is not None and unique_positions and all(v.value_usd is not None for v in values):
        nav = sum((Fraction(v.value_usd) for v in values if v.value_usd is not None), cash)
        if nav == 0:
            issues.append(Issue("portfolio_nav", "zero_nav"))
        elif nav == cash:
            issues.append(Issue("portfolio_nav", "unsupported_cash_only_sleeve"))
    total = None
    if benchmark_cash is not None and all(w is not None for w in source_weights):
        total = sum((w for w in source_weights if w is not None), benchmark_cash)
        if total != 1:
            issues.append(Issue("benchmark", "non_unit_weight_sum"))
    inputs = fingerprint(asdict(data))
    weights = None
    if (
        not issues
        and nav is not None
        and nav > 0
        and cash is not None
        and benchmark_cash is not None
    ):
        weights = industry.Weights(
            data.universe,
            tuple(
                industry.ExactWeight.from_fraction(positions.get(s, Fraction()) / nav)
                for s in data.universe
            ),
            tuple(
                industry.ExactWeight.from_fraction(benchmark.get(s, Fraction()))
                for s in data.universe
            ),
            industry.ExactWeight.from_fraction(cash / nav),
            industry.ExactWeight.from_fraction(benchmark_cash),
            fingerprint(
                [asdict(r) for r in data.positions]
                + [asdict(data.portfolio_cash), data.as_of, data.known_at]
            ),
            fingerprint(
                [
                    data.benchmark_name,
                    [asdict(r) for r in data.benchmark],
                    asdict(data.benchmark_cash),
                    data.benchmark_cash_unit,
                    data.as_of,
                    data.known_at,
                ]
            ),
            data.as_of,
        )
    canonical = fingerprint(
        [
            data.benchmark_name,
            data.universe,
            data.as_of,
            data.known_at,
            [
                (
                    p.row_id,
                    p.security.security_id,
                    p.security.currency,
                    p.security.asset_type,
                    v.value_usd,
                )
                for p, v in zip(data.positions, values, strict=True)
            ],
            [
                (
                    r.row_id,
                    r.security.security_id,
                    r.security.currency,
                    r.security.asset_type,
                    str(w) if w is not None else None,
                )
                for r, w in zip(data.benchmark, source_weights, strict=True)
            ],
            [(s.security_id, s.currency, s.asset_type) for s in data.candidates],
            str(cash) if cash is not None else None,
            str(benchmark_cash) if benchmark_cash is not None else None,
            str(nav) if nav is not None else None,
            str(total) if total is not None else None,
            [_canonical_weight(w) for w in weights.portfolio] if weights else None,
            [_canonical_weight(w) for w in weights.benchmark] if weights else None,
            _canonical_weight(weights.portfolio_cash) if weights else None,
            _canonical_weight(weights.benchmark_cash) if weights else None,
            [asdict(issue) for issue in issues],
        ]
    )
    status = "qualified-synthetic-input" if weights is not None else "incomplete"
    identity = fingerprint(
        [
            VERSION,
            IMPLEMENTATION_SHA256,
            industry.IMPLEMENTATION_SHA256,
            inputs,
            canonical,
            status,
            [asdict(v) for v in issues],
            asdict(weights) if weights else None,
        ]
    )
    return BasketResult(
        status,
        tuple(issues),
        data,
        tuple(values),
        str(nav) if nav is not None else None,
        str(total) if total is not None else None,
        str(1 - total) if total is not None else None,
        weights,
        inputs,
        canonical,
        identity,
    )


def to_industry(result: BasketResult) -> industry.Weights:
    """Revalidate frozen evidence before passing complete ratios to the consumer."""
    if qualify(result.data) != result or result.weights is None:
        raise BasketUnavailable("complete replay-matching synthetic input required")
    return result.weights


def _canonical_weight(value: industry.Weight) -> str:
    if isinstance(value, industry.ExactWeight):
        return str(Fraction(int(value.numerator), int(value.denominator)))
    raise BasketUnavailable("derived weights require an explicit exact ratio")


def _estimated_fact(
    fact: Fact,
    cutoff: date,
    known_at: date,
    location: str,
    issues: list[Issue],
    *,
    positive: bool = False,
) -> float | None:
    if not isinstance(fact, Fact):
        raise BasketUnavailable("typed source fact required")
    valid = _evidence(fact.evidence, cutoff, known_at, location, issues)
    _reasons(fact.unknown_reasons)
    if fact.raw is None or fact.unknown_reasons:
        issues.append(Issue(location, "unknown_or_contradictory_fact", fact.unknown_reasons))
        return None
    try:
        value = advisory.number(fact.raw)
        if positive and value <= 0:
            raise ValueError("positive value required")
    except ValueError:
        issues.append(Issue(location, "invalid_estimate_input"))
        return None
    return value if valid else None


def estimate(data: BasketInput) -> BasketEstimate:
    """Value/align current inputs with Polars; qualify is the legacy exact path.

    Input records are reused until the T019.3 import bridge. No legacy result or
    stored proof object is rewritten. Supplied decimal strings remain in data.
    """
    if data.scope != "explicitly-stipulated-synthetic" or not _text(data.benchmark_name):
        raise BasketUnavailable("named stipulated synthetic inputs required")
    cutoff, known_at = _day(data.as_of), _day(data.known_at)
    if known_at < cutoff:
        raise BasketUnavailable("knowledge cutoff cannot precede valuation cutoff")
    if any(
        type(rows) is not tuple or len(rows) > MAX_ROWS
        for rows in (data.universe, data.positions, data.benchmark, data.candidates)
    ):
        raise BasketUnavailable("bounded immutable input rows required")
    if (
        not data.universe
        or len(set(data.universe)) != len(data.universe)
        or any(not _text(s) for s in data.universe)
    ):
        raise BasketUnavailable("nonempty unique ordered universe required")
    if any(not isinstance(r, Position) for r in data.positions) or any(
        not isinstance(r, BenchmarkRow) for r in data.benchmark
    ):
        raise BasketUnavailable("typed position and benchmark records required")
    issues: list[Issue] = []
    position_rows = []
    for row in data.positions:
        loc = "position:" + row.row_id
        valid = _security(row.security, cutoff, known_at, loc, issues)
        qty = _estimated_fact(row.quantity, cutoff, known_at, loc + ":quantity", issues)
        mark = _estimated_fact(
            row.reference_mark, cutoff, known_at, loc + ":mark", issues, positive=True
        )
        position_rows.append((row.row_id, row.security.security_id, qty, mark, valid))
    positions = pl.DataFrame(
        position_rows,
        orient="row",
        schema={
            "row_id": pl.String,
            "security_id": pl.String,
            "quantity": pl.Float64,
            "mark": pl.Float64,
            "valid": pl.Boolean,
        },
    ).with_columns(
        pl.when(pl.col("valid"))
        .then(pl.col("quantity") * pl.col("mark"))
        .otherwise(None)
        .alias("value")
    )
    bad_value = pl.col("value").is_not_null() & (
        ~pl.col("value").is_finite() | ((pl.col("value") == 0) & (pl.col("quantity") > 0))
    )
    for row_id in positions.filter(bad_value).get_column("row_id").to_list():
        issues.append(Issue("position:" + row_id, "unrepresentable_position_value"))
    positions = positions.with_columns(
        pl.when(bad_value).then(None).otherwise(pl.col("value")).alias("value")
    )
    benchmark_rows = []
    for benchmark_row in data.benchmark:
        loc = "benchmark:" + benchmark_row.row_id
        _security(benchmark_row.security, cutoff, known_at, loc, issues)
        value = _estimated_fact(benchmark_row.weight, cutoff, known_at, loc + ":weight", issues)
        if benchmark_row.unit not in ("decimal", "percent"):
            issues.append(Issue(loc, "explicit_decimal_or_percent_unit_required"))
            value = None
        weight = value / 100 if value is not None and benchmark_row.unit == "percent" else value
        if value is not None and value > 0 and weight == 0:
            issues.append(Issue(loc, "unrepresentable_weight"))
            weight = None
        benchmark_rows.append(
            (
                benchmark_row.row_id,
                benchmark_row.security.security_id,
                weight,
            )
        )
    benchmark = pl.DataFrame(
        benchmark_rows,
        orient="row",
        schema={"row_id": pl.String, "security_id": pl.String, "benchmark": pl.Float64},
    )
    for name, frame in (("position", positions), ("benchmark", benchmark)):
        if (
            any(not _text(s) for s in frame.get_column("row_id"))
            or frame.select("row_id").is_duplicated().any()
        ):
            raise BasketUnavailable("unique bounded row IDs required")
        duplicates = (
            frame.filter(pl.col("security_id").is_not_null())
            .filter(pl.col("security_id").is_duplicated())
            .get_column("security_id")
            .unique()
            .sort()
        )
        for sid in duplicates:
            issues.append(Issue(name + ":" + sid, "duplicate_" + name + "_security"))
    for index, security in enumerate(data.candidates):
        _security(security, cutoff, known_at, f"candidate:{index}", issues)
    candidates = pl.DataFrame(
        {"security_id": [s.security_id for s in data.candidates]}, schema={"security_id": pl.String}
    )
    if candidates.filter(pl.col("security_id").is_not_null()).is_duplicated().any():
        issues.append(Issue("candidates", "duplicate_candidate_security"))
    members = (
        pl.concat([f.select("security_id") for f in (positions, benchmark, candidates)])
        .drop_nulls()
        .unique()
    )
    order = pl.DataFrame(
        {"security_id": data.universe}, schema={"security_id": pl.String}
    ).with_row_index()
    for sid in (
        members.join(order, on="security_id", how="anti")
        .sort("security_id")
        .get_column("security_id")
    ):
        issues.append(Issue("universe:" + sid, "required_security_missing_from_order"))
    for sid in (
        order.join(members, on="security_id", how="anti").sort("index").get_column("security_id")
    ):
        issues.append(Issue("universe:" + sid, "unattributed_universe_member"))
    cash = _estimated_fact(data.portfolio_cash, cutoff, known_at, "portfolio_cash", issues)
    bcash = _estimated_fact(data.benchmark_cash, cutoff, known_at, "benchmark_cash", issues)
    if data.benchmark_cash_unit not in ("percent", "decimal"):
        issues.append(Issue("benchmark_cash", "explicit_decimal_or_percent_unit_required"))
        bcash = None
    elif data.benchmark_cash_unit == "percent" and bcash is not None:
        scaled = bcash / 100
        if bcash > 0 and scaled == 0:
            issues.append(Issue("benchmark_cash", "unrepresentable_weight"))
            bcash = None
        else:
            bcash = scaled
    nav = None
    if (
        cash is not None
        and positions.get_column("value").null_count() == 0
        and not any(i.code == "duplicate_position_security" for i in issues)
    ):
        nav = float(positions.get_column("value").sum()) + cash
        if not math.isfinite(nav) or nav <= 0 or nav == cash:
            issues.append(Issue("portfolio_nav", "positive_representable_stock_sleeve_required"))
            nav = None
    total = None
    if bcash is not None and benchmark.get_column("benchmark").null_count() == 0:
        total = float(benchmark.get_column("benchmark").sum()) + bcash
        if not math.isfinite(total) or not math.isclose(
            total, 1.0, rel_tol=0, abs_tol=advisory.WEIGHT_TOLERANCE
        ):
            issues.append(Issue("benchmark", "non_unit_weight_sum"))
            if not math.isfinite(total):
                total = None
    weights = None
    if not issues and nav is not None and cash is not None and bcash is not None:
        aligned = (
            order.join(
                positions.select("security_id", "value"),
                on="security_id",
                how="left",
                validate="1:1",
            )
            .join(
                benchmark.select("security_id", "benchmark"),
                on="security_id",
                how="left",
                validate="1:1",
            )
            .sort("index")
            .with_columns(
                (pl.col("value").fill_null(0.0) / nav).alias("portfolio"),
                pl.col("benchmark").fill_null(0.0),
            )
        )
        weights = industry.EstimatedWeights(
            data.universe,
            tuple(aligned.get_column("portfolio").to_list()),
            tuple(aligned.get_column("benchmark").to_list()),
            cash / nav,
            bcash,
            data.as_of,
        )
        underflow = aligned.filter((pl.col("value") > 0) & (pl.col("portfolio") == 0)).height > 0
        if (
            not advisory.unit_sum((*weights.portfolio, weights.portfolio_cash))
            or underflow
            or (cash > 0 and weights.portfolio_cash == 0)
        ):
            issues.append(Issue("portfolio", "weight_reconciliation_failed"))
            weights = None
    return BasketEstimate(
        data,
        "estimated-input" if weights is not None else "incomplete",
        tuple(issues),
        tuple((row_id, value) for row_id, value in positions.select("row_id", "value").iter_rows()),
        nav,
        total,
        weights,
    )
