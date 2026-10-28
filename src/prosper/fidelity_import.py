"""Normalize reviewed Fidelity-shaped source observations without reconstructing accounts."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import polars as pl
from pydantic import JsonValue

from prosper.advisory import decimal_value, supplied_sum
from prosper.advisory_records import (
    DecimalFact,
    Fact,
    Finding,
    ImportSnapshot,
    Lot,
    Position,
    Security,
)
from prosper.exact import ExactValue
from prosper.fidelity_lots import LotInspection, LotIssue, Observed, inspect_combined_lots
from prosper.lot_records import Activity, FidelityContext


def _decimal(observed: Observed[ExactValue]) -> DecimalFact:
    if observed.value is None:
        return DecimalFact(value=None, reason=observed.reason or "source amount unavailable")
    try:
        return DecimalFact(value=observed.value.original_text)
    except ValueError:
        return DecimalFact(
            value=None, reason="source amount exceeds the supported decimal boundary"
        )


def normalize(raw: bytes, context: FidelityContext) -> tuple[ImportSnapshot | None, LotInspection]:
    inspected = inspect_combined_lots(raw)
    if hashlib.sha256(raw).hexdigest() != context.source_sha256:
        raise ValueError("source_checksum_or_size_invalid")
    if (
        not inspected.observations
        or inspected.input_truncated
        or any(
            i.code in {"unsupported_header", "malformed_csv", "byte_limit_exceeded", "invalid_utf8"}
            for i in inspected.issues
        )
    ):
        return None, inspected
    traded = next(a for a in context.accounts if a.role == "traded-taxable")
    accounts = {a.source_account: a for a in context.accounts}
    mappings = {(m.source_account, m.symbol): m for m in context.mappings}
    securities: dict[str, Security] = {}
    lots: list[Lot] = []
    findings = [
        Finding(
            code=i.code,
            locator=f"record:{i.record or 1}/{i.column or 'source'}",
            reason="Source parser finding; original values remain in the retained CSV",
        )
        for i in inspected.issues
    ]
    exclusions: list[Finding] = []
    accounting: list[dict[str, object]] = []
    activities = list(context.screening.activities)
    blockers = {
        i.code
        for i in inspected.issues
        if i.code
        in {
            "duplicate_source_reference",
            "conflicting_source_reference",
            "source_file_metadata_conflict",
            "record_width",
            "unsupported_field",
            "missing_metadata",
            "source_record_required",
            "source_basename_required",
        }
    }
    normalized_records = set()
    for row in inspected.observations:
        normalized_records.add(row.record)
        fields = row.source_fields
        account = accounts.get(fields[0])
        mapping = mappings.get((fields[0], fields[2]))
        locator = f"combined-record:{row.record}; source:{fields[4]}/record:{fields[5]}"
        if mapping:
            security = mapping.security
            if security.name.value is None and fields[3].strip():
                security = security.model_copy(update={"name": Fact[str](value=fields[3])})
        else:
            key = hashlib.sha256((fields[0] + "\0" + fields[2]).encode()).hexdigest()
            security = Security(
                id="unresolved-" + key,
                source_ref=locator,
                ticker=fields[2] or "unresolved",
                identity=Fact[str](value=None, reason="No reviewed source-to-security mapping"),
                classification=Fact[str](value=None, reason="No reviewed tax classification"),
                name=Fact[str](value=fields[3])
                if fields[3].strip()
                else Fact[str](value=None, reason="Reported name not supplied"),
            )
        securities.setdefault(security.id, security)
        acquired = Fact[str](value=row.acquired.value, reason=row.acquired.reason)
        quantity, basis = _decimal(row.quantity), _decimal(row.reported_basis)
        # Acquisition dates are observations, never a replacement for retained term evidence.
        activities.append(
            Activity(
                id=f"lot-acquisition-{context.source_sha256}-{row.record}",
                identity=security.identity,
                account_ref=account.account_id if account else fields[0],
                account_scope=account.role if account else "scope-unresolved",
                day=acquired,
                side="acquisition",
                quantity=quantity
                if quantity.value and decimal_value(quantity.value) > 0
                else DecimalFact(
                    value=None,
                    reason="Original acquisition quantity is unknown from remaining shares",
                ),
                pnl=Fact[str](value=None, reason="Acquisition has no supplied sale P&L"),
                source_ref=locator,
            )
        )
        if fields[0] != traded.source_account:
            exclusions.append(
                Finding(
                    code="outside_selected_account",
                    locator=locator,
                    reason=(
                        "Not included in selected holdings; supplied "
                        "acquisition/scope facts remain screening observations"
                    ),
                )
            )
            accounting.append(
                {
                    "record": row.record,
                    "disposition": "outside-selected-account",
                    "security_id": security.id,
                }
            )
            continue
        term = {"Long": "long-term", "Short": "short-term"}.get(fields[8])
        lots.append(
            Lot(
                id=f"lot-{context.source_sha256}-{row.record}",
                account_id=traded.account_id,
                security_id=security.id,
                source_ref=locator,
                quantity=quantity,
                total_basis=basis,
                reported_value=_decimal(row.current_value),
                acquired=acquired,
                term=Fact[str](
                    value=term,
                    reason=None
                    if term
                    else (
                        "Source term is missing or unsupported; not inferred from acquisition date"
                    ),
                ),
            )
        )
        accounting.append(
            {
                "record": row.record,
                "disposition": "selected-lot",
                "lot_id": lots[-1].id,
                "security_id": security.id,
            }
        )
        if security.classification.value != "us-domestic-common-equity":
            exclusions.append(
                Finding(
                    code="unsupported_or_unknown_tax_class",
                    locator=locator,
                    reason=(
                        "Only reviewed ordinary U.S. domestic common equity supports "
                        "conditional sale opportunities"
                    ),
                )
            )
    for record in range(2, len(inspected.records) + 2):
        if record not in normalized_records:
            accounting.append({"record": record, "disposition": "unparsed"})
            blockers.add("unparsed_source_row")
    if not lots:
        blockers.add("selected_account_has_no_lots")
    evidence = (
        context.evidence,
        *(a.evidence for a in context.accounts),
        *(m.evidence for m in context.mappings),
    )
    if any(
        e.effective_at > context.source_as_of
        or datetime.fromisoformat(e.recorded_at) > datetime.now(UTC)
        for e in evidence
    ):
        blockers.add("future_context_evidence")
    positions = tuple(
        Position(
            id=f"independent-{i}",
            account_id=traded.account_id,
            security_id=p.security_id,
            source_ref=p.source_ref,
            quantity=p.quantity,
        )
        for i, p in enumerate(context.independent_positions)
    )
    # Polars groups the supplied row inventory. Decimal is limited to the supplied
    # quantity comparison; a lot sum is never presented as independent positions.
    frame = pl.DataFrame(
        [(lot.security_id, lot.quantity.value) for lot in lots],
        orient="row",
        schema={"security_id": pl.String, "quantity": pl.String},
    )
    grouped = {
        sid: quantities
        for sid, quantities in frame.group_by("security_id").agg(pl.col("quantity")).iter_rows()
    }
    if positions:
        if {p.security_id for p in positions} != set(grouped):
            blockers.add("independent_position_membership_mismatch")
        for p in positions:
            values = grouped.get(p.security_id, [])
            if p.quantity.value is None or any(value is None for value in values):
                findings.append(
                    Finding(
                        code="position_reconciliation_unknown",
                        locator=p.source_ref,
                        reason="Independent position or lot quantity is unknown",
                    )
                )
                blockers.add("independent_position_quantity_unknown")
            elif supplied_sum(tuple(values)) != decimal_value(p.quantity.value):
                blockers.add("independent_position_quantity_mismatch")
                findings.append(
                    Finding(
                        code="independent_position_quantity_mismatch",
                        locator=p.source_ref,
                        reason="Supplied independent position differs from supplied lot quantities",
                    )
                )
    # An unmatched independent identity cannot become a fabricated security.
    if any(p.security_id not in securities for p in positions):
        return None, replace(
            inspected,
            issues=(*inspected.issues, LotIssue(code="independent_position_security_unresolved")),
        )
    facts = context.screening.model_copy(update={"activities": tuple(activities)})
    snapshot = ImportSnapshot(
        source_type="fidelity-shaped-combined-lots",
        source_name="reviewed-combined-lots.csv",
        source_sha256=context.source_sha256,
        account_id=traded.account_id,
        account_alias=traded.alias,
        account_scope="us-taxable-individual",
        source_as_of=context.source_as_of,
        securities=tuple(securities.values()),
        lots=tuple(lots),
        positions=positions,
        cash=(),
        findings=tuple(findings),
        exclusions=tuple(exclusions),
        observations=cast(
            dict[str, JsonValue],
            {
                "lot_context": context.model_dump(mode="json"),
                "screening": facts.model_dump(mode="json"),
                "selection_blockers": sorted(blockers),
                "source_row_accounting": accounting,
                "excluded_security_ids": sorted(
                    s.id
                    for s in securities.values()
                    if s.classification.value is not None
                    and s.classification.value != "us-domestic-common-equity"
                ),
            },
        ),
    )
    return snapshot, inspected
