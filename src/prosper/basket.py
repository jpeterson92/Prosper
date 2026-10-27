"""Current Float64 basket valuation and weight diagnostics.

No source adapter, lookup, persistence, price forecast or financial readiness.
Every supplied row and unknown remains in the immutable result input evidence.
"""

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from prosper import advisory, industry

VERSION = "basket-v1"
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


@dataclass(frozen=True)
class Issue:
    location: str
    code: str
    reasons: tuple[str, ...] = ()


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
    """Value and align current inputs with Float64 and Polars."""
    if not _text(data.benchmark_name):
        raise BasketUnavailable("named benchmark inputs required")
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
