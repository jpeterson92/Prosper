"""Complete ordered history alignment over compact Polars source columns."""

from datetime import datetime
from typing import Literal

import polars as pl

from prosper.history import Alignment, HistoryBatch, HistoryIssue, HistoryRequest, Interval
from prosper.history_table import ALIGNMENT_SCHEMA, OBSERVATION_SCHEMA, PRICES, HistoryTable


def align(
    request: HistoryRequest,
    batches: tuple[HistoryBatch, ...],
    unavailable: frozenset[str] = frozenset(),
) -> Alignment:
    """Retain every coordinate and explicit unknown; no damaged-source fallback."""
    grid = (request.predecessor, *request.sessions)
    grid_set = set(grid)
    # Partition once, rather than scanning all observations once per required name.
    partitioned = [b.rows.frame.partition_by("security_id", as_dict=True) for b in batches]
    issues: list[HistoryIssue] = []
    intervals: list[Interval] = []
    validated: dict[str, str] = {}
    used: set[str] = set()
    frames: list[pl.DataFrame] = []
    facts = [c for c in OBSERVATION_SCHEMA if c not in ("security_id", "source_ref")]
    for context in request.series:
        sid = context.security_id
        candidates = [
            (b, parts.get((sid,)))
            for b, parts in zip(batches, partitioned, strict=True)
            if context in b.contexts
            and datetime.fromisoformat(b.validated_at) <= datetime.fromisoformat(request.known_at)
        ]
        candidates.sort(key=lambda item: datetime.fromisoformat(item[0].validated_at))
        full = [
            i
            for i, (b, _) in enumerate(candidates)
            if b.validation_scope == "full-window" and grid_set <= set(b.requested_sessions)
        ]
        if full:
            candidates = candidates[full[-1] :]
        coherent = context.coherence == "immutable-vintage" or bool(full)
        coherent = coherent and (
            context.currency == "USD"
            and context.interval == "1d"
            and context.return_convention == "simple-total-return-decimal"
            and context.adjustment in ("no-actions", "total-return-adjusted")
            and context.calendar == request.series[0].calendar
            and context.timezone == request.series[0].timezone
        )
        selected = []
        for b, frame in candidates:
            if frame is not None:
                applicable = frame.filter(pl.col("session").is_in(list(grid)))
                if applicable.height:
                    used.add(b.source_sha256)
                    selected.append(
                        applicable.with_columns(pl.lit(b.source_sha256).alias("source_sha256"))
                    )
        if selected:
            combined = pl.concat(selected)
            if combined.select(pl.struct(facts).n_unique().over("session").max()).item() > 1:
                coherent = False
            chosen = combined.unique(subset="session", keep="last", maintain_order=True)
            used.update(chosen["source_sha256"])
        else:
            chosen = pl.DataFrame(schema={**OBSERVATION_SCHEMA, "source_sha256": pl.String})
        frame = pl.DataFrame({"security_id": [sid] * len(grid), "session": grid}).join(
            chosen, on=["security_id", "session"], how="left", validate="1:1", maintain_order="left"
        )
        missing = pl.col("source_ref").is_null()
        corrupt = pl.col("source_sha256").is_in(list(unavailable))
        unknown = pl.any_horizontal(pl.col(name).is_null() for name in (*PRICES, "action"))
        invalid = (
            pl.any_horizontal(pl.col(name) <= 0 for name in PRICES)
            | (pl.col("low") > pl.min_horizontal("open", "close"))
            | (pl.max_horizontal("open", "close") > pl.col("high"))
        )
        frame = frame.with_columns(
            pl.when(missing)
            .then(pl.lit("missing_observation"))
            .when(corrupt)
            .then(pl.lit("source_unavailable"))
            .when(unknown)
            .then(pl.lit("unknown_observation"))
            .when(invalid)
            .then(pl.lit("invalid_ohlc"))
            .otherwise(None)
            .alias("issue")
        )
        for row in frame.filter(pl.col("issue").is_not_null()).iter_rows(named=True):
            code = row["issue"]
            reason = {
                "missing_observation": "No compatible retained observation",
                "source_unavailable": "Required original source bytes are unavailable or corrupt",
                "invalid_ohlc": "Positive ordered OHLC and adjusted close required",
                "unknown_observation": "; ".join(
                    row[n + "_reason"] for n in (*PRICES, "action") if row[n + "_reason"]
                ),
            }[code]
            issues.append(
                HistoryIssue(security_id=sid, session=row["session"], code=code, reason=reason)
            )
        usable = frame["issue"].is_null().to_list()
        if not coherent:
            issues.append(
                HistoryIssue(
                    security_id=sid,
                    session=None,
                    code="coherence_unestablished",
                    reason=(
                        "Mixed/revised observations or incompatible conventions need "
                        "a full required-window refresh or a new coherent context/vintage"
                    ),
                )
            )
        full_used = [
            b
            for b, _ in candidates
            if b.validation_scope == "full-window" and grid_set <= set(b.requested_sessions)
        ]
        if full_used:
            validated[sid] = full_used[-1].validated_at
        if sid in request.manual_security_ids or not coherent:
            intervals.append(
                Interval(
                    security_id=sid,
                    sessions=grid,
                    reason="manual" if sid in request.manual_security_ids else "coherence",
                )
            )
        else:
            groups: list[list[int]] = []
            for i, good in enumerate(usable):
                if not good:
                    if groups and groups[-1][-1] + 1 == i:
                        groups[-1].append(i)
                    else:
                        groups.append([i])
            for group in groups:
                start, end = group[0], group[-1]
                reason_code: Literal["new-name", "leading", "tail", "interior"] = (
                    "new-name"
                    if not any(usable)
                    else "leading"
                    if start == 0
                    else "tail"
                    if end == len(grid) - 1
                    else "interior"
                )
                intervals.append(
                    Interval(
                        security_id=sid,
                        sessions=grid[max(0, start - request.overlap_sessions) : end + 1],
                        reason=reason_code,
                    )
                )
        adjusted = pl.when(pl.col("issue").is_null()).then(pl.col("adjusted_close")).otherwise(None)
        frame = (
            frame.with_columns(adjusted.alias("usable_adjusted"))
            .with_columns(
                (pl.col("usable_adjusted") / pl.col("usable_adjusted").shift(1) - 1.0).alias(
                    "total_return"
                )
            )
            .filter(pl.col("session") != request.predecessor)
        )
        if not coherent:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("total_return"))
        for row in frame.filter(
            pl.col("total_return").is_not_null()
            & (~pl.col("total_return").is_finite() | (pl.col("total_return") <= -1))
        ).iter_rows(named=True):
            issues.append(
                HistoryIssue(
                    security_id=sid,
                    session=row["session"],
                    code="unrepresentable_return",
                    reason="Derived return must be finite and greater than -1",
                )
            )
        frame = frame.with_columns(
            pl.when(pl.col("total_return").is_finite() & (pl.col("total_return") > -1))
            .then(pl.col("total_return"))
            .otherwise(None)
            .alias("total_return")
        )
        frames.append(frame.select(list(ALIGNMENT_SCHEMA)))
    order = pl.DataFrame({"session": request.sessions}).join(
        pl.DataFrame({"security_id": [s.security_id for s in request.series]}), how="cross"
    )
    ordered = order.join(
        pl.concat(frames),
        on=["security_id", "session"],
        how="left",
        validate="1:1",
        maintain_order="left",
    )
    return Alignment(
        request=request,
        rows=HistoryTable.pack(ordered.select(list(ALIGNMENT_SCHEMA)), "alignment"),
        issues=tuple(issues),
        intervals=tuple(intervals),
        complete=not issues and ordered["total_return"].null_count() == 0,
        required_sources=tuple(sorted(used)),
        validated_at=validated,
    )


def check_parts(batches: tuple[HistoryBatch, ...]) -> None:
    """One reviewed activation may not assert conflicting facts for one context."""
    import hashlib

    from prosper.advisory_records import encode

    grouped: dict[tuple[str, str], list[pl.DataFrame]] = {}
    for batch in batches:
        for context in batch.contexts:
            key = (context.security_id, hashlib.sha256(encode(context).encode()).hexdigest())
            grouped.setdefault(key, []).append(
                batch.rows.frame.filter(pl.col("security_id") == context.security_id)
            )
    facts = [c for c in OBSERVATION_SCHEMA if c != "source_ref"]
    for frames in grouped.values():
        if len(frames) > 1:
            combined = pl.concat(frames)
            if (
                combined.height
                and combined.select(pl.struct(facts).n_unique().over("session").max()).item() > 1
            ):
                raise ValueError("contradictory_history_parts")
