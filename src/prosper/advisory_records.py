"""Versioned advisory records. Original sources replace per-field proof objects."""

import json
import math
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from prosper.advisory import decimal_value
from prosper.record_types import DateText, Identifier, Text, Timestamp

type Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type Revision = Annotated[int, Field(ge=0, lt=2**63 - 1)]


class Record(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class Fact[T](Record):
    value: T | None
    reason: Text | None = None

    @model_validator(mode="after")
    def explained(self) -> Self:
        if (self.value is None) != (self.reason is not None):
            raise ValueError("unknown requires a reason; known cannot have one")
        if isinstance(self.value, str) and (not self.value.strip() or len(self.value) > 4096):
            raise ValueError("known text must be nonempty and bounded")
        return self


class DecimalFact(Fact[str]):
    @model_validator(mode="after")
    def supported(self) -> Self:
        if self.value is not None:
            decimal_value(self.value)
        return self


class Security(Record):
    id: Identifier
    source_ref: Text
    ticker: Text
    identity: Fact[str]
    classification: Fact[str]
    currency: Literal["USD"] = "USD"
    name: Fact[str] = Fact[str](value=None, reason="Reported name not supplied")


class Lot(Record):
    id: Identifier
    account_id: Identifier
    security_id: Identifier
    source_ref: Text
    quantity: DecimalFact
    total_basis: DecimalFact
    acquired: Fact[DateText]
    term: Fact[str]
    reported_value: DecimalFact = DecimalFact(value=None, reason="Reported value not supplied")


class Position(Record):
    id: Identifier
    account_id: Identifier
    security_id: Identifier
    source_ref: Text
    quantity: DecimalFact
    reported_value: DecimalFact = DecimalFact(value=None, reason="Reported value not supplied")


class CashTreatment(Record):
    source_sha256: Digest
    account_id: Identifier
    source_as_of: DateText | Timestamp
    security_id: Identifier
    source_refs: tuple[Text, ...]
    kind: Literal["cash", "cash-equivalent"]
    recorded_at: Timestamp
    assertion: Literal["User classified this holding; funding is not asserted"] = (
        "User classified this holding; funding is not asserted"
    )

    @model_validator(mode="after")
    def dated(self) -> Self:
        if datetime.fromisoformat(self.recorded_at) > datetime.now(UTC):
            raise ValueError("future_cash_treatment")
        return self


class Cash(Record):
    id: Identifier
    account_id: Identifier
    source_ref: Text
    amount: DecimalFact
    kind: Text
    currency: Literal["USD"] = "USD"


class Finding(Record):
    code: Text
    locator: Text
    reason: Text


class HoldingMappingRow(Record):
    source: Security
    source_refs: tuple[Text, ...]
    security_id: Identifier
    disposition: Literal["mapped", "preserved", "excluded", "cash-treatment"]
    reason: Text
    benchmark_index: int | None = Field(default=None, ge=0)
    reported_value: DecimalFact
    excluded_bps: float | None = None
    highlight: bool | None = None


class HoldingPreparation(Record):
    method: Literal["same-date-ivv-holdings-v1"] = "same-date-ivv-holdings-v1"
    source_snapshot_id: Digest
    source_sha256: Digest
    account_id: Identifier
    source_as_of: DateText | Timestamp
    benchmark_run_id: Identifier
    benchmark_source_sha256: Digest
    metadata_source_sha256: Digest
    benchmark_date: DateText
    recorded_at: Timestamp
    rows: tuple[HoldingMappingRow, ...]
    reference_value_usd: DecimalFact
    excluded_known_value_usd: str
    unknown_value_ids: tuple[Identifier, ...]
    aggregate_excluded_bps: float | None
    aggregate_highlight: bool | None
    coverage_unknown_reasons: tuple[Text, ...]


class ImportSnapshot(Record):
    version: Literal["advisory-import-v1"] = "advisory-import-v1"
    source_type: Text
    source_name: Text
    source_sha256: Digest
    account_id: Identifier
    account_alias: Text
    account_scope: Text
    source_as_of: DateText | Timestamp
    securities: tuple[Security, ...]
    lots: tuple[Lot, ...]
    positions: tuple[Position, ...]
    cash: tuple[Cash, ...]
    cash_treatments: tuple[CashTreatment, ...] = ()
    holding_preparation: HoldingPreparation | None = None
    findings: tuple[Finding, ...] = ()
    exclusions: tuple[Finding, ...] = ()
    # Optional screening/quotes are observations, never applied to holdings again.
    observations: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def references(self) -> Self:
        blockers = self.observations.get("selection_blockers", [])
        if not isinstance(blockers, list) or any(
            not isinstance(v, str) or not v.strip() for v in blockers
        ):
            raise ValueError("invalid_selection_blockers")
        # These reserved observations feed deterministic financial consumers.
        # Reject malformed facts at import rather than failing after selection.
        if "screening" in self.observations or "lot_context" in self.observations:
            from prosper.lot_records import FidelityContext, ScreeningFacts

            if "screening" in self.observations:
                ScreeningFacts.model_validate_json(json.dumps(self.observations["screening"]))
            if "lot_context" in self.observations:
                context = FidelityContext.model_validate_json(
                    json.dumps(self.observations["lot_context"])
                )
                if (context.source_sha256, context.source_as_of) != (
                    self.source_sha256,
                    self.source_as_of[:10],
                ):
                    raise ValueError("lot_context_source_mismatch")
        for rows in (self.securities, self.lots, self.positions, self.cash):
            if len({row.id for row in rows}) != len(rows):
                raise ValueError("duplicate row identity")
        identities = {row.id for row in self.securities}
        holdings: tuple[Lot | Position, ...] = (*self.lots, *self.positions)
        for row in holdings:
            if row.security_id not in identities or row.account_id != self.account_id:
                raise ValueError("unresolved security/account reference")
        if any(row.account_id != self.account_id for row in self.cash):
            raise ValueError("unresolved cash account")
        if len({t.security_id for t in self.cash_treatments}) != len(self.cash_treatments):
            raise ValueError("duplicate_cash_treatment")
        securities = {s.id: s for s in self.securities}
        preparation = self.holding_preparation
        if preparation is not None:
            if (
                (preparation.source_sha256, preparation.account_id, preparation.source_as_of)
                != (self.source_sha256, self.account_id, self.source_as_of)
                or preparation.benchmark_date != self.source_as_of[:10]
                or datetime.fromisoformat(preparation.recorded_at) > datetime.now(UTC)
                or len({r.source.id for r in preparation.rows}) != len(preparation.rows)
                or len({r.security_id for r in preparation.rows}) != len(preparation.rows)
                or {r.security_id for r in preparation.rows} != {r.security_id for r in holdings}
            ):
                raise ValueError("holding_preparation_binding_invalid")
            for mapping in preparation.rows:
                current = securities[mapping.security_id]
                expected = mapping.source
                if mapping.disposition == "mapped":
                    expected = expected.model_copy(
                        update={
                            "id": mapping.security_id,
                            "identity": Fact[str](value=mapping.security_id),
                        }
                    )
                    if mapping.benchmark_index is None or mapping.source.identity.value is not None:
                        raise ValueError("holding_preparation_mapping_invalid")
                elif (
                    mapping.security_id != mapping.source.id or mapping.benchmark_index is not None
                ):
                    raise ValueError("holding_preparation_mapping_invalid")
                if current != expected or mapping.source_refs != tuple(
                    sorted({r.source_ref for r in holdings if r.security_id == mapping.security_id})
                ):
                    raise ValueError("holding_preparation_mapping_invalid")
        for treatment in self.cash_treatments:
            refs = tuple(
                sorted({r.source_ref for r in holdings if r.security_id == treatment.security_id})
            )
            security = securities.get(treatment.security_id)
            if (
                not refs
                or (treatment.source_sha256, treatment.account_id, treatment.source_as_of)
                != (self.source_sha256, self.account_id, self.source_as_of)
                or refs != treatment.source_refs
                or security is None
                or (
                    security.identity.value is not None
                    and security.classification.value == "us-domestic-common-equity"
                )
                or set(refs) & {r.source_ref for r in self.cash}
                or any(
                    r.security_id != treatment.security_id and r.source_ref in refs
                    for r in holdings
                )
            ):
                raise ValueError("cash_treatment_source_mismatch")
        return self

    @property
    def cash_security_ids(self) -> frozenset[str]:
        return frozenset(t.security_id for t in self.cash_treatments)

    @property
    def excluded_stock_ids(self) -> frozenset[str]:
        return (
            frozenset(
                r.security_id for r in self.holding_preparation.rows if r.disposition == "excluded"
            )
            if self.holding_preparation
            else frozenset()
        )


class AnalysisRun(Record):
    version: Literal["advisory-analysis-v1"] = "advisory-analysis-v1"
    id: Identifier
    snapshot_id: Digest
    input_revision: Revision
    settings: dict[str, JsonValue]
    inputs: dict[str, JsonValue]
    application_version: Text
    model_version: Text
    as_of: Timestamp
    started_at: Timestamp
    completed_at: Timestamp | None = None
    status: Literal["running", "complete", "partial", "failed"] = "running"
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    exclusions: tuple[Finding, ...] = ()
    warnings: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if (self.status == "running") != (self.completed_at is None):
            raise ValueError("completed status and completion time must agree")
        return self


def encode(value: Record | dict[str, JsonValue]) -> str:
    """Bounded JSON storage with no NaN, tuple/decimal conversion or proof replay."""
    document = value.model_dump(mode="json") if isinstance(value, Record) else value

    def check(item: object, depth: int = 0) -> None:
        if depth > 32:
            raise ValueError("record nesting exceeds limit")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("finite estimates required")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("text keys required")
                check(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                check(child, depth + 1)

    check(document)
    result = json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(result.encode()) > 16 * 1024 * 1024:
        raise ValueError("record size exceeds limit")
    return result
