"""Dated local identity preparation from retained, selected IVV evidence."""

import json
import math
import re
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext

import polars as pl
from pydantic import Field

from prosper.advisory import number, supplied_sum
from prosper.advisory_records import (
    DecimalFact,
    Digest,
    Fact,
    HoldingMappingRow,
    HoldingPreparation,
    ImportSnapshot,
    Lot,
    Position,
    Record,
    Revision,
)
from prosper.benchmark import BenchmarkObservation, BenchmarkResult, acquisition
from prosper.benchmark_mapping import prepare as issuer_mapping
from prosper.cash_treatment import holdings
from prosper.fidelity_import import normalize
from prosper.lot_records import Evidence, FidelityContext, SecurityMapping
from prosper.record_types import Identifier, Text, Timestamp


class HoldingsMappingRequest(Record):
    snapshot_id: Digest
    benchmark_run_id: Identifier
    expected_revision: Revision
    recorded_at: Timestamp
    exclusions: dict[Identifier, Text] = Field(default_factory=dict, max_length=10000)


def name_key(value: str | None) -> str | None:
    # Case, whitespace and these punctuation separators only. No issuer-name
    # expansion, suffix deletion, fuzzy match or share-class symbol conversion.
    return " ".join(re.sub(r"[.,()\"'\-]+", " ", value.upper()).split()) if value else None


def prepare(
    snapshot: ImportSnapshot,
    raw: bytes,
    observation: BenchmarkObservation,
    benchmark_raw: bytes,
    result: BenchmarkResult,
    command: HoldingsMappingRequest,
) -> ImportSnapshot:
    if snapshot.holding_preparation is not None:
        raise ValueError("holdings_mapping_original_snapshot_required")
    if snapshot.source_type != "fidelity-shaped-combined-lots":
        raise ValueError("holdings_mapping_source_unsupported")
    context = FidelityContext.model_validate_json(
        json.dumps(snapshot.observations.get("lot_context"))
    )
    original, inspection = normalize(raw, context)
    if original is None or snapshot.model_copy(update={"cash_treatments": ()}) != original:
        raise ValueError("holdings_mapping_original_snapshot_required")
    if (
        observation.request.ticker != "IVV"
        or result.status != "estimated-equity-benchmark"
        or result.observation_id != observation.request.observation_id
        or snapshot.source_as_of[:10] != observation.effective_date
        or result.effective_date != observation.effective_date
        or datetime.fromisoformat(command.recorded_at) > datetime.now(UTC)
        or datetime.fromisoformat(command.recorded_at)
        < datetime.fromisoformat(context.evidence.recorded_at)
        or datetime.fromisoformat(command.recorded_at) < datetime.fromisoformat(result.reviewed_at)
    ):
        raise ValueError("holdings_mapping_fund_date_or_knowledge_invalid")
    source = acquisition(observation, benchmark_raw).snapshot
    policy = issuer_mapping(source) if source is not None else None
    if policy is None:
        raise ValueError("holdings_mapping_source_unsupported")
    retained = {
        r.locator.index: r
        for r in result.ledger
        if r.disposition == "included-equity" and r.locator.section == "holdings"
    }
    candidates = [r for r in policy.rows if r.action == "include" and r.index in retained]
    pool = pl.DataFrame(
        [(r.ticker, name_key(r.name), retained[r.index].security_id, r.index) for r in candidates],
        orient="row",
        schema={"ticker": pl.String, "name": pl.String, "target": pl.String, "index": pl.Int64},
    )
    pool = pool.join(
        pool.group_by("ticker").len().rename({"len": "ticker_count"}),
        on="ticker",
        validate="m:1",
        maintain_order="left",
    )
    pool = pool.join(
        pool.group_by("target").len().rename({"len": "target_count"}),
        on="target",
        validate="m:1",
        maintain_order="left",
    )
    # Ambiguous ticker rows are deliberately represented once as unavailable.
    pool = pool.unique("ticker", maintain_order=True)
    refs: dict[str, set[str]] = {}
    holding_rows: tuple[Lot | Position, ...] = (*snapshot.lots, *snapshot.positions)
    for row in holding_rows:
        refs.setdefault(row.security_id, set()).add(row.source_ref)
    held = [s for s in snapshot.securities if s.id in refs]
    if set(command.exclusions) - set(refs) or set(command.exclusions) & snapshot.cash_security_ids:
        raise ValueError("holdings_mapping_unknown_exclusion")
    table = pl.DataFrame(
        [(s.id, s.ticker.strip().upper()) for s in held],
        orient="row",
        schema={"source_id": pl.String, "ticker": pl.String},
    )
    table = table.join(
        table.group_by("ticker").len().rename({"len": "source_count"}),
        on="ticker",
        validate="m:1",
        maintain_order="left",
    )
    table = table.join(pool, on="ticker", how="left", validate="m:1", maintain_order="left")
    if table.height != len(held) or table["source_id"].to_list() != [s.id for s in held]:
        raise ValueError("holdings_mapping_cardinality_invalid")
    rows = []
    mappings = list(context.mappings)
    aliases: dict[str, str] = {}
    selected = next(a for a in context.accounts if a.role == "traded-taxable")
    source_names: dict[str, set[str | None]] = {}
    for observed in inspection.observations:
        if observed.source_fields[0] == selected.source_account:
            source_names.setdefault(observed.source_fields[2], set()).add(
                name_key(observed.source_fields[3])
            )
    existing_ids = {s.id for s in snapshot.securities}
    reported = {
        row.security_id: row.reported_value for row in holdings(snapshot, all_holdings=True)
    }
    for security, item in zip(held, table.iter_rows(named=True), strict=True):
        disposition, reason, target, index = (
            "excluded",
            "No supported benchmark ticker match",
            security.id,
            None,
        )
        if security.id in snapshot.cash_security_ids:
            disposition, reason = "cash-treatment", "Explicit personal cash treatment preserved"
        elif security.id in command.exclusions:
            reason = command.exclusions[security.id]
        elif security.identity.value is not None:
            disposition, reason = (
                "preserved",
                "Existing supplied identity preserved; no inferred alias",
            )
        elif security.classification.value not in (None, "us-domestic-common-equity"):
            reason = "Source classification is outside the supported stock scope"
        elif len(source_names.get(security.ticker, set())) != 1:
            reason = "Ambiguous or missing names among the original holding rows"
        elif (
            item["source_count"] != 1
            or item["ticker_count"] not in (None, 1)
            or item["target_count"] not in (None, 1)
        ):
            reason = "Ambiguous source ticker or benchmark identity"
        elif item["target"] is not None:
            if not name_key(security.name.value) or name_key(security.name.value) != item["name"]:
                reason = "Reported names do not agree under the supported comparison"
            elif item["target"] != security.id and item["target"] in existing_ids:
                reason = "Benchmark target conflicts with an existing supplied security ID"
            else:
                disposition, reason, target, index = (
                    "mapped",
                    "Same-date ticker and normalized name agree with retained IVV stock evidence",
                    item["target"],
                    item["index"],
                )
                mapped = security.model_copy(
                    update={"id": target, "identity": Fact[str](value=target)}
                )
                mappings = [
                    m
                    for m in mappings
                    if (m.source_account, m.symbol) != (selected.source_account, security.ticker)
                ]
                mappings.append(
                    SecurityMapping(
                        source_account=selected.source_account,
                        symbol=security.ticker,
                        security=mapped,
                        evidence=Evidence(
                            actor="Prosper deterministic preparation",
                            reference=(
                                f"Selected IVV run {command.benchmark_run_id}; "
                                f"holdings:{index}; dated local identity only"
                            ),
                            effective_at=result.effective_date,
                            recorded_at=command.recorded_at,
                        ),
                    )
                )
                aliases[security.id] = target
        rows.append(
            HoldingMappingRow.model_validate(
                {
                    "source": security,
                    "source_refs": tuple(sorted(refs[security.id])),
                    "security_id": target,
                    "disposition": disposition,
                    "reason": reason,
                    "benchmark_index": index,
                    "reported_value": reported[security.id],
                }
            )
        )
    context = context.model_copy(
        update={
            "mappings": tuple(mappings),
            "independent_positions": tuple(
                p.model_copy(update={"security_id": aliases.get(p.security_id, p.security_id)})
                for p in context.independent_positions
            ),
        }
    )
    context = FidelityContext.model_validate_json(context.model_dump_json())
    updated, inspected = normalize(raw, context)
    if (
        updated is None
        or inspected.input_truncated
        or updated.observations.get("selection_blockers")
    ):
        raise ValueError("holdings_mapping_source_reconciliation_invalid")
    proof = HoldingPreparation.model_validate(
        {
            "source_snapshot_id": command.snapshot_id,
            "source_sha256": snapshot.source_sha256,
            "account_id": snapshot.account_id,
            "source_as_of": snapshot.source_as_of,
            "benchmark_run_id": command.benchmark_run_id,
            "benchmark_source_sha256": str(observation.source_sha256),
            "metadata_source_sha256": result.metadata_source_sha256,
            "benchmark_date": result.effective_date,
            "recorded_at": command.recorded_at,
            **coverage(rows),
        }
    )
    document = updated.model_dump(mode="json")
    document["holding_preparation"] = proof.model_dump(mode="json")
    document["cash_treatments"] = [t.model_dump(mode="json") for t in snapshot.cash_treatments]
    return ImportSnapshot.model_validate_json(json.dumps(document))


def coverage(rows: list[HoldingMappingRow]) -> dict[str, object]:
    """Original portfolio-value scope; strict supplied-decimal warning comparisons."""
    unknown = tuple(row.source.id for row in rows if row.reported_value.value is None)
    texts = tuple(row.reported_value.value for row in rows if row.reported_value.value is not None)
    excluded = tuple(
        row.reported_value.value
        for row in rows
        if row.disposition == "excluded" and row.reported_value.value is not None
    )
    excluded_sum = supplied_sum(excluded)
    reasons = ["unknown_reported_usd_value"] if unknown else []
    reference = DecimalFact(value=None, reason="Original portfolio-value coverage is incomplete")
    total = supplied_sum(texts)
    try:
        number(str(total))
        if total <= 0:
            raise ValueError("nonpositive value")
        for text in texts:
            number(text)
        if not reasons:
            reference = DecimalFact(value=str(total))
    except ValueError:
        reasons.append("nonpositive_or_unrepresentable_reference_value")
    aggregate_bps = None
    aggregate_highlight = None
    if not reasons:
        # Decimal is confined to strict final comparisons of supplied amounts;
        # the displayed bps remain Float64 derived diagnostics.
        with localcontext(Context(prec=2048)):
            aggregate_bps = float(excluded_sum) / float(total) * 10000
            aggregate_highlight = excluded_sum * 10000 > total * 100
            rows = [
                row.model_copy(
                    update={
                        "excluded_bps": float(row.reported_value.value or "0")
                        / float(total)
                        * 10000,
                        "highlight": Decimal(row.reported_value.value or "0") * 10000 > total * 10,
                    }
                )
                if row.disposition == "excluded"
                else row
                for row in rows
            ]
        if not math.isfinite(aggregate_bps):
            raise ValueError("holdings_mapping_coverage_invalid")
    return {
        "rows": tuple(rows),
        "reference_value_usd": reference,
        "excluded_known_value_usd": str(excluded_sum),
        "unknown_value_ids": unknown,
        "aggregate_excluded_bps": aggregate_bps,
        "aggregate_highlight": aggregate_highlight,
        "coverage_unknown_reasons": tuple(reasons),
    }
