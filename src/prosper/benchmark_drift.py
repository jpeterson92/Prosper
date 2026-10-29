"""Carry a disclosed equity proxy forward using covered constituent total returns.

Source holdings/weights remain immutable. This estimates a reinvested, unchanged
constituent proxy, not the issuer's subsequent trades or actual account positions.
"""

import math
from dataclasses import dataclass

import polars as pl

from prosper.advisory import WEIGHT_TOLERANCE
from prosper.benchmark import BenchmarkResult
from prosper.history import Alignment


@dataclass(frozen=True)
class WeightIssue:
    code: str
    locator: str
    reason: str
    security_id: str | None = None


@dataclass(frozen=True)
class WeightEstimate:
    weights: dict[str, float] | None
    issues: tuple[WeightIssue, ...] = ()
    warning: str | None = None


def weights_at(
    benchmark: BenchmarkResult | None,
    alignment: Alignment | None,
    target_date: str,
    *,
    retained_ids: tuple[str, ...] | None = None,
) -> WeightEstimate:
    """Require the complete declared daily grid over (source close, target close].

    The grid/calendar evidence also defines nontrading days between the predecessor
    and cutoff. A target beyond the cutoff is refused: no flat tail or calendar guess.
    Polars aligns and compounds each retained name; zero weights remain members.
    """
    if benchmark is None or benchmark.status != "estimated-equity-benchmark":
        return WeightEstimate(None)

    def unavailable(code: str, reason: str) -> WeightEstimate:
        return WeightEstimate(None, (WeightIssue(code, "benchmark/weights", reason),))

    ids = benchmark.security_ids
    weights = benchmark.weights
    try:
        source_total = math.fsum(weights)
    except (OverflowError, ValueError):
        source_total = math.inf
    if (
        not ids
        or len(ids) != len(set(ids))
        or len(ids) != len(weights)
        or any(not math.isfinite(w) or w < 0 for w in weights)
        or not math.isclose(source_total, 1.0, rel_tol=0, abs_tol=WEIGHT_TOLERANCE)
    ):
        return unavailable(
            "benchmark_weights_invalid", "Complete finite source-date weights required"
        )
    if retained_ids is not None:
        if (
            not retained_ids
            or len(set(retained_ids)) != len(retained_ids)
            or not set(retained_ids) <= set(ids)
        ):
            return unavailable(
                "benchmark_retained_sleeve_empty_or_invalid",
                "Nonempty declared retained benchmark sleeve required",
            )
        selected = [
            (sid, weight) for sid, weight in zip(ids, weights, strict=True) if sid in retained_ids
        ]
        total = math.fsum(w for _, w in selected)
        if total <= 0:
            return unavailable(
                "benchmark_retained_value_nonpositive",
                "Retained benchmark needs positive source value",
            )
        ids = tuple(s for s, _ in selected)
        weights = tuple(w / total for _, w in selected)
    source_date = benchmark.effective_date
    if target_date < source_date:
        return unavailable(
            "benchmark_future_holdings", "Cannot use future holdings or reverse drift"
        )
    if target_date == source_date:
        return WeightEstimate(dict(zip(ids, weights, strict=True)))
    if (
        alignment is None
        or alignment.request.predecessor > source_date
        or alignment.request.cutoff != target_date
    ):
        return unavailable(
            "benchmark_drift_window_incomplete",
            f"Total-return coverage must span holdings date {source_date} through target "
            f"session {target_date}; extend the declared history window or use a covered target",
        )
    request = alignment.request
    contexts = {c.security_id: c for c in request.series}
    issues = []
    for sid in ids:
        context = contexts.get(sid)
        if context is None or (
            context.currency != "USD"
            or context.interval != "1d"
            or context.timezone != "UTC"
            or context.adjustment not in ("no-actions", "total-return-adjusted")
            or context.return_convention != "simple-total-return-decimal"
            or context.action_convention != "compatible-total-return-and-raw-ohlc"
            or context.coherence != "immutable-vintage"
        ):
            issues.append(
                WeightIssue(
                    "benchmark_drift_conventions_unavailable",
                    "history/series",
                    "Compatible attributable USD daily total returns required for weight drift",
                    sid,
                )
            )
    if len({contexts[sid].vintage for sid in ids if sid in contexts}) > 1:
        issues.append(
            WeightIssue(
                "benchmark_drift_vintage_mismatch",
                "history/series",
                "Do not combine incompatible history vintages for weight drift",
            )
        )
    sessions = tuple(day for day in request.sessions if source_date < day <= target_date)
    frame = alignment.rows.frame.filter(
        pl.col("security_id").is_in(ids) & pl.col("session").is_in(sessions)
    )
    for error in alignment.issues:
        if error.security_id in ids and (error.session is None or error.session in sessions):
            issues.append(
                WeightIssue(
                    error.code,
                    f"history/{error.session or 'window'}",
                    error.reason,
                    error.security_id,
                )
            )
    if (
        not sessions
        or frame.height != len(ids) * len(sessions)
        or frame.select("security_id", "session").unique().height != frame.height
        or frame.filter(
            pl.col("total_return").is_null()
            | ~pl.col("total_return").is_finite()
            | (pl.col("total_return") <= -1)
            | pl.col("source_sha256").is_null()
        ).height
    ):
        issues.append(
            WeightIssue(
                "benchmark_drift_returns_incomplete",
                "history/grid",
                "Every retained benchmark name needs a usable sourced total return "
                "for every drift session",
            )
        )
    if issues:
        return WeightEstimate(None, tuple(issues))
    factors = frame.group_by("security_id").agg(
        (pl.col("total_return") + 1).product().alias("growth")
    )
    derived = (
        pl.DataFrame({"security_id": ids, "source_weight": weights})
        .join(factors, on="security_id", how="left", validate="1:1", maintain_order="left")
        .with_columns((pl.col("source_weight") * pl.col("growth")).alias("value"))
    )
    if derived.filter(
        ~pl.col("growth").is_finite()
        | (pl.col("growth") <= 0)
        | ~pl.col("value").is_finite()
        | ((pl.col("source_weight") > 0) & (pl.col("value") <= 0))
    ).height:
        return unavailable(
            "benchmark_drift_unrepresentable", "Compounded values are outside Float64 range"
        )
    try:
        total = math.fsum(derived["value"])
    except OverflowError:
        total = math.inf
    if not math.isfinite(total) or total <= 0:
        return unavailable(
            "benchmark_drift_unrepresentable", "Positive finite proxy value required"
        )
    values = tuple(value / total for value in derived["value"])
    if any(
        not math.isfinite(w) or (old > 0 and w <= 0) for old, w in zip(weights, values, strict=True)
    ):
        return unavailable(
            "benchmark_drift_unrepresentable", "Positive source weight underflowed during drift"
        )
    return WeightEstimate(
        dict(zip(ids, values, strict=True)),
        warning=(
            f"Benchmark weights: total-return drift from reported holdings {source_date} "
            f"to {target_date} over {len(sessions)} declared sessions; unchanged constituents "
            "with constituent distributions reinvested. This estimates a disclosed-holdings "
            "proxy, not subsequent fund trades, rebalances or current disclosed holdings."
        ),
    )
