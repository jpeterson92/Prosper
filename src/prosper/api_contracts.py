"""Closed synthetic HTTP projections. No financial arithmetic or raw-byte export."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from prosper.bundle import Location, ParsedBundle
from prosper.bundle_schema import BundleDocument, Identifier
from prosper.checkpoint import Inspection
from prosper.evidence import EvidenceReceipt
from prosper.exact import BookValue, ExactValue
from prosper.persistence import StoredCheckpoint
from prosper.previews import ImportPreview

API_VERSION = "synthetic-import-api-v1"
type Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type Generation = Annotated[int, Field(ge=0, lt=2**63 - 1)]
type ReadinessState = Literal["complete", "incomplete", "contradictory"]


class ClosedAPI(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class RejectRequest(ClosedAPI):
    schema_version: Literal["synthetic-import-api-v1"]
    preview_sha256: Digest


class CommitRequest(RejectRequest):
    command_key: Identifier
    expected_generation: Generation


class APIIssue(ClosedAPI):
    code: str
    path: Location = ()
    offset: int | None = None
    path_truncated: bool = False


class APIError(ClosedAPI):
    error: str
    issues: tuple[APIIssue, ...] = ()
    further_issues: bool = False


class KnownValue(ClosedAPI):
    state: Literal["known"] = "known"
    value: str
    original_text: str
    source_quantum: str


class UnknownValue(ClosedAPI):
    state: Literal["unknown"] = "unknown"
    value: None = None
    reasons: tuple[str, ...]


type ValueResponse = Annotated[KnownValue | UnknownValue, Field(discriminator="state")]


def book_value(value: BookValue) -> KnownValue | UnknownValue:
    if isinstance(value, ExactValue):
        return KnownValue(
            value=value.canonical,
            original_text=value.original_text,
            source_quantum=format(value.source_quantum, "f"),
        )
    return UnknownValue(reasons=value.reasons)


class SourceValue(ClosedAPI):
    path: Location
    exact: KnownValue


def _source_values(value: object, path: Location = ()) -> tuple[SourceValue, ...]:
    if isinstance(value, ExactValue):
        return (
            SourceValue(
                path=path,
                exact=KnownValue(
                    value=value.canonical,
                    original_text=value.original_text,
                    source_quantum=format(value.source_quantum, "f"),
                ),
            ),
        )
    result: list[SourceValue] = []
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            result.extend(_source_values(getattr(value, name), (*path, name)))
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            result.extend(_source_values(item, (*path, index)))
    return tuple(result)


class SourceResponse(ClosedAPI):
    status: Literal["parsed_unvalidated"] = "parsed_unvalidated"
    canonicalization_version: Literal["canonical-json-v1"] = "canonical-json-v1"
    canonical_sha256: Digest
    document: BundleDocument
    source_values: tuple[SourceValue, ...]


def source_response(parsed: ParsedBundle) -> SourceResponse:
    return SourceResponse(
        canonical_sha256=parsed.canonical_sha256,
        document=parsed.document,
        source_values=_source_values(parsed.document),
    )


class ReceiptResponse(ClosedAPI):
    raw_sha256: Digest
    byte_length: int
    storage_version: Literal["evidence-bytes-v1"] = "evidence-bytes-v1"


def receipt_response(receipt: EvidenceReceipt) -> ReceiptResponse:
    # Storage paths are adapter details, never HTTP selection/response authority.
    return ReceiptResponse(raw_sha256=receipt.raw_sha256, byte_length=receipt.byte_length)


class PositionResponse(ClosedAPI):
    account_id: str
    security_id: str
    quantity: ValueResponse
    lot_quantity: ValueResponse
    price: ValueResponse
    market_value: ValueResponse
    basis: ValueResponse
    market_minus_basis: ValueResponse


class CashResponse(ClosedAPI):
    account_id: str
    settled: ValueResponse
    available: ValueResponse
    unsettled: ValueResponse


class ReadinessResponse(ClosedAPI):
    inspection: ReadinessState
    basis: ReadinessState
    valuation: ReadinessState
    coverage: ReadinessState
    planning_ready: Literal[False] = False
    planning_reasons: tuple[str, ...]


class FindingResponse(ClosedAPI):
    code: str
    path: Location
    blocking: bool
    reason: str | None


class InspectionResponse(ClosedAPI):
    version: Literal["synthetic-inspection-v1"] = "synthetic-inspection-v1"
    traded_account_id: str | None
    positions: tuple[PositionResponse, ...]
    cash: tuple[CashResponse, ...]
    settled_cash_nav: ValueResponse
    total_basis: ValueResponse
    market_minus_basis: ValueResponse
    readiness: ReadinessResponse
    findings: tuple[FindingResponse, ...]
    further_findings: bool
    inspection_valid: bool


def inspection_response(inspection: Inspection) -> InspectionResponse:
    return InspectionResponse(
        traded_account_id=inspection.traded_account_id,
        positions=tuple(
            PositionResponse(
                account_id=row.account_id,
                security_id=row.security_id,
                quantity=book_value(row.quantity),
                lot_quantity=book_value(row.lot_quantity),
                price=book_value(row.price),
                market_value=book_value(row.market_value),
                basis=book_value(row.basis),
                market_minus_basis=book_value(row.market_minus_basis),
            )
            for row in inspection.positions
        ),
        cash=tuple(
            CashResponse(
                account_id=row.account_id,
                settled=book_value(row.settled),
                available=book_value(row.available),
                unsettled=book_value(row.unsettled),
            )
            for row in inspection.cash
        ),
        settled_cash_nav=book_value(inspection.settled_cash_nav),
        total_basis=book_value(inspection.total_basis),
        market_minus_basis=book_value(inspection.market_minus_basis),
        readiness=ReadinessResponse(
            inspection=inspection.readiness.inspection,
            basis=inspection.readiness.basis,
            valuation=inspection.readiness.valuation,
            coverage=inspection.readiness.coverage,
            planning_reasons=inspection.readiness.planning_reasons,
        ),
        findings=tuple(
            FindingResponse(code=f.code, path=f.path, blocking=f.blocking, reason=f.reason)
            for f in inspection.findings
        ),
        further_findings=inspection.further_findings,
        inspection_valid=inspection.validated is not None,
    )


class PreviewResponse(ClosedAPI):
    schema_version: Literal["synthetic-import-api-v1"] = "synthetic-import-api-v1"
    version: Literal["synthetic-preview-v1"] = "synthetic-preview-v1"
    receipt: ReceiptResponse
    recorded_at: str
    state: Literal["staged", "rejected", "committed"]
    rejected_at: str | None
    source: SourceResponse | None
    issues: tuple[APIIssue, ...]
    further_issues: bool
    inspection: InspectionResponse | None
    planning_ready: Literal[False] = False


def preview_response(preview: ImportPreview) -> PreviewResponse:
    return PreviewResponse(
        receipt=receipt_response(preview.receipt),
        recorded_at=preview.recorded_at,
        state=preview.state,
        rejected_at=preview.rejected_at,
        source=source_response(preview.parsing.parsed) if preview.parsing.parsed else None,
        issues=tuple(
            APIIssue(
                code=i.code,
                path=tuple(p[:128] if isinstance(p, str) else p for p in i.path),
                offset=i.offset,
                path_truncated=any(isinstance(p, str) and len(p) > 128 for p in i.path),
            )
            for i in preview.parsing.issues
        ),
        further_issues=preview.parsing.further_issues,
        inspection=inspection_response(preview.inspection) if preview.inspection else None,
    )


class CheckpointResponse(ClosedAPI):
    sequence: int
    recorded_at: str
    receipt: ReceiptResponse
    source: SourceResponse
    inspection: InspectionResponse


def checkpoint_response(checkpoint: StoredCheckpoint) -> CheckpointResponse:
    return CheckpointResponse(
        sequence=checkpoint.sequence,
        recorded_at=checkpoint.recorded_at,
        receipt=receipt_response(checkpoint.receipt),
        source=source_response(checkpoint.inspection.source),
        inspection=inspection_response(checkpoint.inspection),
    )


class CurrentResponse(ClosedAPI):
    schema_version: Literal["synthetic-import-api-v1"] = "synthetic-import-api-v1"
    generation: Generation
    checkpoint: CheckpointResponse | None
    planning_ready: Literal[False] = False


class CommandResponse(ClosedAPI):
    schema_version: Literal["synthetic-import-api-v1"] = "synthetic-import-api-v1"
    scope: Literal["synthetic-portfolio-import-v1"]
    command_key: Identifier
    payload_version: Literal["activate-preview-v1"]
    payload_sha256: Digest
    preview_sha256: Digest
    expected_generation: Generation
    outcome: Literal[
        "committed",
        "duplicate",
        "stale_generation",
        "preview_rejected",
        "preview_invalid",
        "identity_review_required",
        "source_conflict",
    ]
    generation: Generation
    activation_generation: int | None
    recorded_at: str
