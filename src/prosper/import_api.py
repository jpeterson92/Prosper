"""Current advisory routes under the protected owning loopback process."""

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, FastAPI, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from starlette.responses import JSONResponse, Response

from prosper import worksheets
from prosper.advisory_records import AnalysisRun
from prosper.advisory_recovery import backup, restore
from prosper.api_contracts import (
    APIError,
    APIIssue,
    CatalogResponse,
    ClearHistoryRequest,
    CommandResponse,
    CurrentResponse,
    DiagnosticRequest,
    FidelityOpening,
    FidelityPreviewResponse,
    FidelityUpload,
    HistoryDiagnosticRequest,
    HistoryManifest,
    HistoryPart,
    HistoryPartReceipt,
    HistoryPlanRequest,
    HistoryRowsPage,
    HistoryRowsRequest,
    LotSettingsInput,
    LotSettingsRequest,
    PreviewResponse,
    RejectRequest,
    SelectRequest,
    SettingsRequest,
    Upload,
)
from prosper.benchmark import (
    BenchmarkDiagnostic,
    BenchmarkFetch,
    BenchmarkImport,
    BenchmarkObservation,
    BenchmarkResult,
    BenchmarkReview,
    BenchmarkSelect,
    review_result,
)
from prosper.candidate_workflow import CandidateIdentity, CandidateOutput, CandidateStart
from prosper.history import Alignment
from prosper.lot_opportunities import LotResult
from prosper.lot_records import LotDiagnosticRequest, LotSettings
from prosper.modeled_inputs import ModeledDiagnostic, ModeledResult, ModeledUpload
from prosper.storage import EvidenceError, PersistenceError
from prosper.worksheets import Worksheet, WorksheetCheck, WorksheetPreview, WorksheetSave
from prosper.workspace import Workspace

BODY_MEDIA_TYPES = {
    "/api/v1/worksheets/check": b"application/json",
    "/api/v1/worksheets": b"application/json",
    "/api/v1/candidates/start": b"application/json",
    "/api/v1/candidates/cancel": b"application/json",
    "/api/v1/previews": b"application/json",
    "/api/v1/select": b"application/json",
    "/api/v1/settings": b"application/json",
    "/api/v1/diagnostics": b"application/json",
    "/api/v1/reject": b"application/json",
    "/api/v1/restore": b"application/octet-stream",
    "/api/v1/history/refresh": b"application/json",
    "/api/v1/history/preview": b"application/json",
    "/api/v1/history/parts": b"application/json",
    "/api/v1/history/discard": b"application/json",
    "/api/v1/history/plan": b"application/json",
    "/api/v1/history/diagnostics": b"application/json",
    "/api/v1/history/clear": b"application/json",
    "/api/v1/history/rows": b"application/json",
    "/api/v1/fidelity/previews": b"application/json",
    "/api/v1/fidelity/opening": b"application/json",
    "/api/v1/lots/settings": b"application/json",
    "/api/v1/lots/settings/preview": b"application/json",
    "/api/v1/lots/diagnostics": b"application/json",
    "/api/v1/benchmarks/fetch": b"application/json",
    "/api/v1/benchmarks/import": b"application/json",
    "/api/v1/benchmarks/review": b"application/json",
    "/api/v1/benchmarks/diagnostics": b"application/json",
    "/api/v1/benchmarks/select": b"application/json",
    "/api/v1/inputs/preview": b"application/json",
    "/api/v1/inputs/diagnostics": b"application/json",
}
CONTROL_BODY_BYTES = 64 * 1024


def install_import_routes(app: FastAPI, service: Workspace) -> None:
    router = APIRouter(
        prefix="/api/v1",
        dependencies=[Depends(HTTPBearer(auto_error=False))],
        responses={status: {"model": APIError} for status in (400, 404, 409, 413, 415, 422, 503)},
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Never echo portfolio values or arbitrary object keys from failed input.
        known = {
            "batch",
            "request",
            "series",
            "contexts",
            "session",
            "sessions",
            "predecessor",
            "cutoff",
            "known_at",
            "calendar_evidence",
            "overlap_sessions",
            "manual_security_ids",
            "profile",
            "f",
            "a3",
            "kappa",
            "provider",
            "dataset",
            "provider_symbol",
            "mapping_start",
            "mapping_end",
            "calendar",
            "timezone",
            "interval",
            "adjustment",
            "action_convention",
            "repair",
            "source_schema",
            "transform_version",
            "vintage",
            "coherence",
            "coherence_evidence",
            "return_convention",
            "permission_scope",
            "collected_at",
            "validated_at",
            "requested_sessions",
            "validation_scope",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "action",
            "body",
            "version",
            "snapshot",
            "source_base64",
            "source_type",
            "source_name",
            "source_sha256",
            "source_as_of",
            "account_id",
            "account_alias",
            "account_scope",
            "securities",
            "lots",
            "positions",
            "cash",
            "findings",
            "exclusions",
            "observations",
            "id",
            "source_ref",
            "security_id",
            "ticker",
            "identity",
            "classification",
            "currency",
            "quantity",
            "total_basis",
            "acquired",
            "term",
            "amount",
            "kind",
            "value",
            "reason",
            "code",
            "locator",
            "settings",
            "command_key",
            "expected_revision",
            "snapshot_id",
            "run_id",
            "as_of",
        }
        return JSONResponse(
            APIError(
                error="request_invalid",
                issues=tuple(
                    APIIssue(
                        code=str(item["type"]),
                        path=tuple(
                            p if isinstance(p, int) or p in known else "<field>"
                            for p in item["loc"][:12]
                        ),
                    )
                    for item in error.errors()[:20]
                ),
            ).model_dump(mode="json"),
            status_code=422,
        )

    @app.exception_handler(PersistenceError)
    @app.exception_handler(EvidenceError)
    async def storage_error(
        request: Request, error: PersistenceError | EvidenceError
    ) -> JSONResponse:
        code = error.code
        status = (
            413
            if code == "history_alignment_size_limit"
            else 404
            if code
            in (
                "snapshot_missing",
                "analysis_missing",
                "lot_result_unavailable",
                "benchmark_observation_missing",
                "worksheet_missing",
                "history_part_missing",
            )
            else 409
            if code
            in (
                "stale_revision",
                "candidate_worker_busy",
                "current_modeled_inputs_required",
                "candidate_result_unavailable",
                "command_key_reused",
                "analysis_id_reused",
                "worksheet_id_reused",
                "checked_candidate_required",
                "restore_requires_empty_workspace",
                "selected_snapshot_cannot_be_rejected",
                "selected_snapshot_required",
            )
            else 422
            if code
            in (
                "history_page_offset_invalid",
                "invalid_source_encoding",
                "source_checksum_or_size_invalid",
                "invalid_advisory_backup",
                "incompatible_advisory_schema",
                "corrupt_advisory_backup",
                "required_held_security_missing",
                "history_knowledge_after_analysis",
                "fidelity_context_or_source_invalid",
                "lot_settings_required_or_invalid",
                "future_lot_analysis_date",
                "lot_diagnostic_request_invalid",
                "benchmark_review_invalid",
                "benchmark_selection_unavailable",
                "benchmark_knowledge_after_analysis",
                "duplicate_input_source",
                "worksheet_orders_refused",
                "worksheet_date_before_analysis",
                "worksheet_date_future",
                "worksheet_parent_invalid",
                "worksheet_price_unrepresentable",
                "pending_history_budget_exceeded",
                "history_observation_budget_exceeded",
                "history_source_total_size_limit",
                "duplicate_history_source_part",
                "contradictory_history_parts",
                "invalid_history_source_encoding",
            )
            else 503
        )
        return JSONResponse(APIError(error=code).model_dump(mode="json"), status_code=status)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"error": "internal_error"}, status_code=500)

    @router.post("/previews", response_model=PreviewResponse)
    def stage(upload: Upload) -> PreviewResponse:
        return service.stage(upload)

    @router.post("/candidates/start", response_model=AnalysisRun)
    def start_candidate(command: CandidateStart) -> AnalysisRun:
        return service.start_candidate(command)

    @router.post("/worksheets/check", response_model=WorksheetPreview)
    def check_worksheet(command: WorksheetCheck) -> WorksheetPreview:
        return worksheets.preview(service.store, command)

    @router.post("/worksheets", response_model=Worksheet)
    def save_worksheet(command: WorksheetSave) -> Worksheet:
        return worksheets.save(service.store, command)

    @router.get("/worksheets/{identity}", response_model=Worksheet)
    def read_worksheet(identity: str) -> Worksheet:
        return worksheets.read(service.store, identity)

    @router.get("/worksheets/{identity}/export", response_class=Response)
    def export_worksheet(identity: str) -> Response:
        return Response(
            worksheets.export_text(worksheets.read(service.store, identity)),
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="prosper-manual-worksheet.txt"'},
        )

    @router.post("/candidates/cancel", response_model=AnalysisRun)
    def cancel_candidate(command: CandidateIdentity) -> AnalysisRun:
        return service.candidates.cancel(command.run_id)

    @router.get("/candidates/results/{identity}", response_model=CandidateOutput)
    def candidate_result(identity: str) -> CandidateOutput:
        run = service.store.run(identity)
        if run.model_version != "candidate-workflow-v1" or run.status == "running":
            raise PersistenceError("candidate_result_unavailable")
        return CandidateOutput.model_validate_json(json.dumps(run.outputs))

    @router.post("/benchmarks/fetch", response_model=BenchmarkObservation)
    def fetch_benchmark(command: BenchmarkFetch) -> BenchmarkObservation:
        return service.fetch_benchmark(command)

    @router.post("/inputs/preview", response_model=ModeledResult)
    def preview_inputs(command: ModeledUpload) -> ModeledResult:
        return service.preview_inputs(command)

    @router.post("/inputs/diagnostics", response_model=AnalysisRun)
    def diagnose_inputs(command: ModeledDiagnostic) -> AnalysisRun:
        return service.diagnose_inputs(command)

    @router.post("/benchmarks/import", response_model=BenchmarkObservation)
    def import_benchmark(command: BenchmarkImport) -> BenchmarkObservation:
        return service.import_benchmark(command)

    @router.get("/benchmarks/observations/{identity}", response_model=BenchmarkObservation)
    def benchmark_observation(identity: str) -> BenchmarkObservation:
        return service.store.benchmark_observation(identity)

    @router.get("/benchmarks/observations/{identity}/source", response_class=Response)
    def benchmark_source(identity: str) -> Response:
        observation = service.store.benchmark_observation(identity)
        if observation.source_sha256 is None:
            raise PersistenceError("benchmark_selection_unavailable")
        return Response(
            service.store.source_bytes(observation.source_sha256),
            media_type="application/octet-stream",
        )

    @router.post("/benchmarks/review", response_model=BenchmarkResult)
    def preview_benchmark(command: BenchmarkReview) -> BenchmarkResult:
        if datetime.fromisoformat(command.reviewed_at) > datetime.now(UTC):
            raise PersistenceError("benchmark_knowledge_after_analysis")
        observation = service.store.benchmark_observation(command.observation_id)
        if observation.source_sha256 is None:
            raise PersistenceError("benchmark_selection_unavailable")
        try:
            metadata = base64.b64decode(command.metadata_base64, validate=True)
            return review_result(
                observation,
                service.store.source_bytes(observation.source_sha256),
                command,
                hashlib.sha256(metadata).hexdigest(),
            )
        except ValueError:
            raise PersistenceError("benchmark_review_invalid") from None

    @router.post("/benchmarks/diagnostics", response_model=AnalysisRun)
    def benchmark_diagnostic(command: BenchmarkDiagnostic) -> AnalysisRun:
        return service.diagnose_benchmark(command)

    @router.post("/benchmarks/select", response_model=CommandResponse)
    def select_benchmark(command: BenchmarkSelect) -> CommandResponse:
        return CommandResponse.model_validate(
            service.store.select_benchmark(
                command.run_id, command.command_key, command.expected_revision
            )
        )

    @router.post("/fidelity/previews", response_model=FidelityPreviewResponse)
    def stage_fidelity(upload: FidelityUpload) -> FidelityPreviewResponse:
        return service.stage_fidelity(upload)

    @router.post("/fidelity/opening", response_model=FidelityPreviewResponse)
    def open_fidelity(opening: FidelityOpening) -> FidelityPreviewResponse:
        return service.open_fidelity(opening)

    @router.post("/lots/settings", response_model=CommandResponse)
    def configure_lots(command: LotSettingsRequest) -> CommandResponse:
        return CommandResponse.model_validate(service.configure_lots(command))

    @router.post("/lots/diagnostics", response_model=AnalysisRun)
    def lot_diagnostic(command: LotDiagnosticRequest) -> AnalysisRun:
        return service.diagnose_lots(command)

    @router.post("/lots/settings/preview", response_model=LotSettings)
    def preview_lot_settings(command: LotSettingsInput) -> LotSettings:
        return command.settings

    @router.get("/lots/results/{identity}", response_model=LotResult)
    def lot_result(identity: str) -> LotResult:
        run = service.store.run(identity)
        if run.model_version != "lot-opportunities-v1" or run.status == "running":
            raise PersistenceError("lot_result_unavailable")
        return LotResult.model_validate_json(json.dumps(run.outputs))

    @router.get("/previews/{identity}", response_model=PreviewResponse)
    def preview(identity: Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]) -> PreviewResponse:
        return service.preview(identity)

    @router.get("/current", response_model=CurrentResponse)
    def current() -> CurrentResponse:
        return CurrentResponse.model_validate(service.store.current())

    @router.get("/catalog", response_model=CatalogResponse)
    def catalog() -> CatalogResponse:
        return CatalogResponse.model_validate_json(json.dumps(service.store.catalog()))

    @router.post("/select", response_model=CommandResponse)
    def select(command: SelectRequest) -> CommandResponse:
        return CommandResponse.model_validate(
            service.store.select(
                command.snapshot_id, command.command_key, command.expected_revision
            )
        )

    @router.post("/settings", response_model=CommandResponse)
    def settings(command: SettingsRequest) -> CommandResponse:
        return CommandResponse.model_validate(
            service.store.configure(
                command.settings, command.command_key, command.expected_revision
            )
        )

    @router.post("/reject", response_model=PreviewResponse)
    def reject(command: RejectRequest) -> PreviewResponse:
        service.store.reject(command.snapshot_id)
        return service.preview(command.snapshot_id)

    @router.post("/diagnostics", response_model=AnalysisRun)
    def diagnose(command: DiagnosticRequest) -> AnalysisRun:
        return service.diagnose(command)

    @router.get("/runs/{identity}", response_model=AnalysisRun)
    def run(identity: str) -> AnalysisRun:
        return service.store.run(identity)

    @router.get("/input-records/{identity}", response_model=Alignment)
    def input_record(identity: str) -> Alignment:
        return service.store.alignment(identity)

    @router.post("/history/rows", response_model=HistoryRowsPage)
    def history_rows(command: HistoryRowsRequest) -> HistoryRowsPage:
        frame = command.table.frame
        if command.offset > frame.height:
            raise PersistenceError("history_page_offset_invalid")
        return HistoryRowsPage(
            row_count=frame.height,
            offset=command.offset,
            columns=tuple(frame.columns),
            rows=tuple(frame.slice(command.offset, command.limit).rows()),
        )

    @router.post("/history/refresh", response_model=CommandResponse)
    def refresh_history(upload: HistoryManifest) -> CommandResponse:
        return CommandResponse.model_validate(service.refresh_history(upload))

    @router.post("/history/preview", response_model=HistoryManifest)
    def preview_history(upload: HistoryManifest) -> HistoryManifest:
        return service.preview_history(upload)

    @router.post("/history/parts", response_model=HistoryPartReceipt)
    def stage_history_part(part: HistoryPart) -> HistoryPartReceipt:
        from prosper.history_upload import stage

        return stage(service.store, part)

    @router.post("/history/discard", response_model=CommandResponse)
    def discard_history_parts(manifest: HistoryManifest) -> CommandResponse:
        from prosper.history_upload import discard

        return CommandResponse.model_validate(discard(service.store, manifest))

    @router.post("/history/plan", response_model=Alignment)
    def plan_history(command: HistoryPlanRequest) -> Alignment:
        return service.plan_history(command.request)

    @router.post("/history/diagnostics", response_model=AnalysisRun)
    def history_diagnostic(command: HistoryDiagnosticRequest) -> AnalysisRun:
        return service.diagnose_history(command)

    @router.post("/history/clear", response_model=CommandResponse)
    def clear_history(command: ClearHistoryRequest) -> CommandResponse:
        return CommandResponse.model_validate(
            service.store.clear_history_cache(command.command_key, command.expected_revision)
        )

    @router.get(
        "/backup",
        response_class=Response,
        responses={
            200: {
                "content": {
                    "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
                }
            }
        },
    )
    def download_backup() -> Response:
        return Response(
            backup(service.store),
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="prosper-advisory.sqlite3"'},
        )

    @router.post("/restore", response_model=CommandResponse)
    def upload_backup(
        raw: Annotated[bytes, Body(media_type="application/octet-stream")],
    ) -> CommandResponse:
        return CommandResponse.model_validate(restore(service.store, raw))

    app.include_router(router)
