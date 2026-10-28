"""Current advisory HTTP shapes. No checkpoint transport or financial authority."""

import json
from typing import Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from prosper.advisory_records import Digest, ImportSnapshot, Record, Revision
from prosper.benchmark import BenchmarkObservation
from prosper.cash_treatment import CashHolding
from prosper.history import HistoryBatch, HistoryRequest
from prosper.history_table import HistoryTable
from prosper.lot_records import FidelityContext, LotSettings
from prosper.record_types import DateText, Identifier, Text, Timestamp


class APIIssue(Record):
    code: str
    path: tuple[str | int, ...]


class APIError(Record):
    error: str
    issues: tuple[APIIssue, ...] = ()


class HistoryRowsRequest(Record):
    table: HistoryTable
    offset: int = Field(default=0, ge=0, le=650000)
    limit: int = Field(default=20, ge=1, le=100)


class HistoryRowsPage(Record):
    row_count: int
    offset: int
    columns: tuple[str, ...]
    rows: tuple[tuple[str | float | None, ...], ...]


class Upload(Record):
    version: Literal["advisory-upload-v1"]
    snapshot: ImportSnapshot
    source_base64: str = Field(max_length=2800000)

    @field_validator("snapshot", mode="before")
    @classmethod
    def json_snapshot(cls, value: object) -> object:
        # FastAPI decodes JSON before Pydantic; validate collections with JSON
        # semantics while retaining strict decimal strings and scalar types.
        if isinstance(value, dict):
            return ImportSnapshot.model_validate_json(json.dumps(value, allow_nan=False))
        return value


class PreviewResponse(Record):
    id: Digest
    snapshot: ImportSnapshot
    cash_holdings: tuple[CashHolding, ...] = ()


class FidelityUpload(Record):
    context: FidelityContext
    source_base64: str = Field(max_length=2800000)

    @field_validator("context", mode="before")
    @classmethod
    def json_context(cls, value: object) -> object:
        return (
            FidelityContext.model_validate_json(json.dumps(value, allow_nan=False))
            if isinstance(value, dict)
            else value
        )


class FidelityOpening(Record):
    """Minimal user-supplied opening facts; unresolved identity stays unresolved."""

    source_base64: str = Field(max_length=2800000)
    source_account: Text
    source_as_of: DateText
    account_alias: Text
    currency: Literal["USD"]
    recorded_at: Timestamp


class SourceIssue(Record):
    code: str
    record: int | None
    column: str | None


class FidelityPreviewResponse(Record):
    preview: PreviewResponse | None
    issues: tuple[SourceIssue, ...]


class LotSettingsInput(Record):
    settings: LotSettings

    @field_validator("settings", mode="before")
    @classmethod
    def json_settings(cls, value: object) -> object:
        return (
            LotSettings.model_validate_json(json.dumps(value, allow_nan=False))
            if isinstance(value, dict)
            else value
        )


class LotSettingsRequest(LotSettingsInput):
    command_key: Identifier
    expected_revision: Revision


class CurrentResponse(Record):
    revision: Revision
    snapshot_id: Digest | None
    settings: dict[str, JsonValue]
    current_run_id: Identifier | None


class SelectRequest(Record):
    snapshot_id: Digest
    command_key: Identifier
    expected_revision: Revision


class SettingsRequest(Record):
    settings: dict[str, JsonValue]
    command_key: Identifier
    expected_revision: Revision


class RejectRequest(Record):
    snapshot_id: Digest


class DiagnosticRequest(Record):
    run_id: Identifier
    expected_revision: Revision
    as_of: Timestamp


class CommandResponse(Record):
    outcome: str
    revision: Revision


class SnapshotEntry(Record):
    id: Digest
    imported_at: Timestamp
    state: Literal["staged", "selected", "rejected"]


class CatalogResponse(Record):
    snapshots: tuple[SnapshotEntry, ...]
    runs: tuple[Identifier, ...]
    worksheets: tuple[Identifier, ...]
    benchmarks: tuple[BenchmarkObservation, ...]
    pending_history_parts: tuple[Digest, ...]


class HistoryPart(Record):
    batch: HistoryBatch
    source_zlib_base64: str = Field(max_length=2800000)

    @field_validator("batch", mode="before")
    @classmethod
    def json_batch(cls, value: object) -> object:
        return (
            HistoryBatch.model_validate_json(json.dumps(value, allow_nan=False))
            if isinstance(value, dict)
            else value
        )


class HistoryPartReceipt(Record):
    id: Digest
    batch: HistoryBatch


class HistoryManifest(Record):
    version: Literal["advisory-history-manifest-v1"] = "advisory-history-manifest-v1"
    part_count: int = Field(ge=1, le=500)
    part_ids: tuple[Digest, ...] = Field(min_length=1, max_length=500)
    command_key: Identifier
    expected_revision: Revision

    @field_validator("part_ids", mode="before")
    @classmethod
    def json_ids(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def complete(self) -> Self:
        if self.part_count != len(self.part_ids) or len(set(self.part_ids)) != self.part_count:
            raise ValueError("history_manifest_parts_invalid")
        return self


class HistoryUpload(Record):
    version: Literal["advisory-history-upload-v2"] = "advisory-history-upload-v2"
    part_count: int = Field(ge=1, le=500)
    parts: tuple[HistoryPart, ...] = Field(min_length=1, max_length=500)
    command_key: Identifier
    expected_revision: Revision

    @field_validator("parts", mode="before")
    @classmethod
    def json_parts(cls, value: object) -> object:
        if isinstance(value, list):
            if len(value) > 500:
                raise ValueError("history_parts_size_limit")
            count = 0
            for part in value:
                if isinstance(part, dict) and isinstance(part.get("batch"), dict):
                    rows = part["batch"].get("rows")
                    if isinstance(rows, dict) and type(rows.get("row_count")) is int:
                        count += rows["row_count"]
            if count > 650000:
                raise ValueError("history_observation_budget_exceeded")
            return tuple(
                HistoryPart.model_validate_json(json.dumps(part, allow_nan=False)) for part in value
            )
        return value

    @model_validator(mode="after")
    def manifest(self) -> Self:
        if self.part_count != len(self.parts):
            raise ValueError("history_parts_missing")
        if sum(p.batch.rows.row_count for p in self.parts) > 650000:
            raise ValueError("history_observation_budget_exceeded")
        digests = [p.batch.source_sha256 for p in self.parts]
        if len(set(digests)) != len(digests):
            raise ValueError("duplicate_history_source_part")
        return self


class HistoryPlanRequest(Record):
    request: HistoryRequest

    @field_validator("request", mode="before")
    @classmethod
    def json_request(cls, value: object) -> object:
        return (
            HistoryRequest.model_validate_json(json.dumps(value, allow_nan=False))
            if isinstance(value, dict)
            else value
        )


class HistoryDiagnosticRequest(HistoryPlanRequest):
    run_id: Identifier
    expected_revision: Revision
    as_of: Timestamp


class ClearHistoryRequest(Record):
    command_key: Identifier
    expected_revision: Revision
