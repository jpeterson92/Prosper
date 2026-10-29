"""Pre-fit history review and source-valued exclusion coverage.

Original inputs and the full source alignment remain immutable. This module
selects a modeled sleeve, never repairs history or responds to a failed fit.
"""

import math
from decimal import Context, Decimal, localcontext
from typing import TYPE_CHECKING, Literal

import polars as pl

from prosper.advisory import number, supplied_sum
from prosper.advisory_records import DecimalFact, Digest, ImportSnapshot, Record
from prosper.benchmark import BenchmarkResult
from prosper.cash_treatment import holdings
from prosper.equity_benchmark import Row
from prosper.history import Alignment, HistoryBatch, SeriesContext
from prosper.history_table import HistoryTable, SessionGrid
from prosper.record_types import DateText, Identifier, Text, Timestamp

if TYPE_CHECKING:
    from prosper.modeled_inputs import ModeledBundle, ModeledResult


class HistoryDecision(Record):
    security_id: Identifier
    roles: tuple[Literal["held", "benchmark", "candidate"], ...]
    excluded: bool
    issue_codes: tuple[Text, ...]


class CoverageName(Record):
    key: Text
    security_id: Identifier | None
    locators: tuple[Text, ...]
    value_usd: DecimalFact
    excluded: bool
    excluded_bps: float | None = None
    highlight: bool | None = None


class SleeveCoverage(Record):
    scope: Literal["portfolio", "benchmark"]
    valuation_date: DateText
    denominator_scope: Text
    names: tuple[CoverageName, ...]
    reference_value_usd: DecimalFact
    excluded_known_value_usd: str
    unknown_value_keys: tuple[Text, ...]
    aggregate_excluded_bps: float | None
    aggregate_highlight: bool | None


class HistoryCoverageEvidence(Record):
    source_sha256: Digest
    contexts: tuple[SeriesContext, ...]
    sessions: SessionGrid
    validation_scope: Literal["requested-interval", "full-window"]
    collected_at: Timestamp
    validated_at: Timestamp


class ModeledSleeve(Record):
    decisions: tuple[HistoryDecision, ...]
    history_evidence: tuple[HistoryCoverageEvidence, ...]
    portfolio: SleeveCoverage
    benchmark: SleeveCoverage | None

    @property
    def excluded_ids(self) -> frozenset[str]:
        return frozenset(d.security_id for d in self.decisions if d.excluded)

    @property
    def retained_ids(self) -> tuple[str, ...]:
        return tuple(d.security_id for d in self.decisions if not d.excluded)

    @property
    def warnings(self) -> tuple[str, ...]:
        result = [
            f"History exclusion: {d.security_id}; {', '.join(d.issue_codes)}; "
            "outside the modeled sleeve, with no spendable cash or permitted trades"
            for d in self.decisions
            if d.excluded
        ]
        for coverage in (self.portfolio, self.benchmark):
            if coverage is None:
                continue
            prefix = f"{coverage.scope} exclusion coverage at {coverage.valuation_date}"
            if coverage.aggregate_excluded_bps is None:
                result.append(f"{prefix}: unavailable; {coverage.reference_value_usd.reason}")
            else:
                result.append(
                    f"{prefix}: {coverage.aggregate_excluded_bps:.8g} bps; "
                    f"reference USD {coverage.reference_value_usd.value}; "
                    f"{coverage.denominator_scope}"
                )
            if coverage.aggregate_highlight:
                result.append(f"{prefix}: warning, aggregate strictly above 100 bps")
            result.extend(
                f"{prefix}: warning, {n.key} strictly above 10 bps"
                for n in coverage.names
                if n.highlight
            )
        return tuple(result)


def history_codes(
    alignment: Alignment, evidence: tuple[HistoryCoverageEvidence, ...]
) -> dict[str, tuple[str, ...]]:
    """Inspect source facts in one partition pass, without fitting or repair."""
    by_id: dict[str, set[str]] = {}
    for issue in alignment.issues:
        by_id.setdefault(issue.security_id, set()).add(issue.code)
    known = {c for e in evidence for c in e.contexts}
    parts = alignment.rows.frame.select("security_id", "source_sha256", "action").partition_by(
        "security_id", as_dict=True
    )
    for context in alignment.request.series:
        codes = by_id.setdefault(context.security_id, set())
        rows = parts.get((context.security_id,))
        if (
            context.coherence == "immutable-vintage"
            and context in known
            and rows is not None
            and rows["source_sha256"].drop_nulls().len()
        ):
            if (
                context.currency != "USD"
                or context.interval != "1d"
                or context.timezone != "UTC"
                or context.adjustment not in ("no-actions", "total-return-adjusted")
                or context.return_convention != "simple-total-return-decimal"
                or context.action_convention != "compatible-total-return-and-raw-ohlc"
            ):
                codes.add("unsupported_history_conventions")
            if rows.filter(
                pl.col("action").is_not_null()
                & ~pl.col("action").is_in(["none", "split", "dividend", "split-and-dividend"])
            ).height:
                codes.add("unsupported_history_action")
    return {sid: tuple(sorted(codes)) for sid, codes in by_id.items()}


def excludable(codes: tuple[str, ...]) -> bool:
    allowed = {
        "missing_observation",
        "unknown_observation",
        "invalid_ohlc",
        "unsupported_history_action",
    }
    if "unsupported_history_conventions" in codes:
        allowed |= {"unsupported_history_conventions", "coherence_unestablished"}
    return bool(codes) and set(codes) <= allowed


def coverage(
    scope: Literal["portfolio", "benchmark"],
    day: str,
    names: tuple[CoverageName, ...],
    denominator_scope: str,
) -> SleeveCoverage:
    unknown = tuple(n.key for n in names if n.value_usd.value is None)
    total = supplied_sum(tuple(n.value_usd.value for n in names if n.value_usd.value is not None))
    excluded = supplied_sum(
        tuple(n.value_usd.value for n in names if n.excluded and n.value_usd.value is not None)
    )
    available = not unknown and total > 0
    try:
        number(str(total))
        for n in names:
            if n.value_usd.value is not None:
                number(n.value_usd.value)
    except ValueError:
        available = False
    fraction = float(excluded) / float(total) * 10000 if available else None
    if fraction is not None and not math.isfinite(fraction):
        available, fraction = False, None
    reference = (
        DecimalFact(value=str(total))
        if available
        else DecimalFact(
            value=None, reason="Original source values are unknown, nonpositive or unrepresentable"
        )
    )
    # Exact supplied-amount comparisons decide strict warning thresholds;
    # displayed ratios use the ordinary Float64 analytical boundary.
    with localcontext(Context(prec=2048)):
        aggregate_highlight = excluded * 10000 > total * 100 if available else None
        reviewed = tuple(
            n.model_copy(
                update={
                    "excluded_bps": float(n.value_usd.value or "0") / float(total) * 10000,
                    "highlight": Decimal(n.value_usd.value or "0") * 10000 > total * 10,
                }
            )
            if n.excluded and available
            else n
            for n in names
        )
    return SleeveCoverage(
        scope=scope,
        valuation_date=day,
        denominator_scope=denominator_scope,
        names=reviewed,
        reference_value_usd=reference,
        excluded_known_value_usd=str(excluded),
        unknown_value_keys=unknown,
        aggregate_excluded_bps=fraction,
        aggregate_highlight=aggregate_highlight,
    )


def review(
    snapshot: ImportSnapshot,
    benchmark: BenchmarkResult | None,
    bundle: "ModeledBundle",
    original: "ModeledResult",
    alignment: Alignment | None,
    batches: tuple[HistoryBatch, ...],
) -> ModeledSleeve:
    """Only observed missing/unknown/invalid history can remove a declared name.

    Corruption, global declarations and contradictory facts remain blockers.
    Full-window validation absence alone is not evidence of short history.
    """
    # The aggregate convention blocker is expected when a name lacks history;
    # all other global declarations must be resolved first.
    global_block = any(
        (
            i.security_id is None
            and i.code not in ("idr_conventions_unqualified", "benchmark_drift_returns_incomplete")
        )
        or i.scope == "source"
        for i in original.issues
    )
    decisions = []
    evidence = tuple(
        HistoryCoverageEvidence(
            source_sha256=b.source_sha256,
            contexts=b.contexts,
            sessions=b.sessions,
            validation_scope=b.validation_scope,
            collected_at=b.collected_at,
            validated_at=b.validated_at,
        )
        for b in batches
        if alignment and b.source_sha256 in alignment.required_sources
    )
    known_contexts = tuple(c for b in batches for c in b.contexts)
    contexts = {c.security_id: c for c in bundle.history.series}
    codes_by_id = history_codes(alignment, evidence) if alignment else {}
    for member in original.members:
        sid = member.security_id
        codes = codes_by_id.get(sid, ())
        unsafe_codes = {
            "held_identity_unresolved_or_conflicting",
            "held_classification_conflict",
            "position_reconciliation_unknown",
            "position_quantity_conflict",
            "lot_mark_conflict",
            "mark_identity_mismatch",
            "hierarchy_conflict",
            "source_date_outside_window",
            "future_source_knowledge",
            "unsupported_or_unknown_security",
            "security_mapping_missing",
        }
        unsafe = any(i.security_id == sid and i.code in unsafe_codes for i in original.issues)
        candidates = tuple(c for c in known_contexts if c.security_id == sid)
        if candidates and contexts.get(sid) not in candidates:
            unsafe = True  # A changed declaration is not evidence of absent price history.
        excluded = bool(
            alignment and not global_block and not unsafe and sid in contexts and excludable(codes)
        )
        decisions.append(
            HistoryDecision(
                security_id=sid, roles=member.roles, excluded=excluded, issue_codes=codes
            )
        )
    dropped = {d.security_id for d in decisions if d.excluded}
    original_ids = set(original.security_ids)
    securities = {s.id: s for s in snapshot.securities}
    portfolio_names = tuple(
        CoverageName(
            key=h.security_id,
            security_id=h.security_id,
            locators=h.source_refs,
            value_usd=h.reported_value
            if securities[h.security_id].currency == "USD"
            else DecimalFact(
                value=None, reason="Original holding USD value convention is unsupported"
            ),
            excluded=h.security_id not in snapshot.cash_security_ids
            and (h.security_id in dropped or h.security_id not in original_ids),
        )
        for h in holdings(snapshot, all_holdings=True)
    )
    benchmark_names: list[CoverageName] = []
    if benchmark:
        groups: dict[str, list[Row]] = {}
        # Only primary economic rows enter coverage, never linked duplicates.
        for row in benchmark.ledger:
            if row.role != "primary":
                continue
            key = row.security_id or f"{row.locator.section}/{row.locator.index}"
            # Explicit IDs may be grouped; unknown identities remain located rows.
            groups.setdefault(key, []).append(row)
        for key, rows in groups.items():
            values = [
                r.value
                for r in rows
                if r.value_currency == "USD" and r.value is not None and Decimal(r.value) >= 0
            ]
            value = (
                DecimalFact(value=str(supplied_sum(tuple(values))))
                if len(values) == len(rows)
                else DecimalFact(
                    value=None,
                    reason="Original benchmark USD market value is unknown or unsupported",
                )
            )
            benchmark_names.append(
                CoverageName(
                    key=key,
                    security_id=rows[0].security_id,
                    locators=tuple(f"{r.locator.section}/{r.locator.index}" for r in rows),
                    value_usd=value,
                    excluded=rows[0].security_id in dropped
                    or all(r.disposition != "included-equity" for r in rows),
                )
            )
    return ModeledSleeve(
        decisions=tuple(decisions),
        history_evidence=evidence,
        portfolio=coverage(
            "portfolio",
            snapshot.source_as_of[:10],
            portfolio_names,
            "original reported holdings including cash-treated positions; "
            "lots/positions reconciled once; separate cash observations outside coverage",
        ),
        benchmark=coverage(
            "benchmark",
            benchmark.effective_date,
            tuple(benchmark_names),
            "original primary USD values from the selected benchmark review, "
            "including source-policy exclusions",
        )
        if benchmark
        else None,
    )


def project(alignment: Alignment | None, retained: tuple[str, ...]) -> Alignment | None:
    if alignment is None or not retained:
        return None
    request = alignment.request.model_copy(
        update={
            "series": tuple(c for c in alignment.request.series if c.security_id in retained),
            "manual_security_ids": tuple(
                s for s in alignment.request.manual_security_ids if s in retained
            ),
        }
    )
    frame = alignment.rows.frame.filter(pl.col("security_id").is_in(retained))
    issues = tuple(i for i in alignment.issues if i.security_id in retained)
    return Alignment(
        request=request,
        rows=HistoryTable.pack(frame, "alignment"),
        issues=issues,
        intervals=tuple(i for i in alignment.intervals if i.security_id in retained),
        complete=not issues and frame["total_return"].null_count() == 0,
        required_sources=alignment.required_sources,
        validated_at={s: v for s, v in alignment.validated_at.items() if s in retained},
    )
