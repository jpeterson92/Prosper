"""Thin HTTP routes over already verified synthetic import services."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Body, Depends, FastAPI, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from starlette.responses import JSONResponse

from prosper.api_contracts import (
    APIError,
    APIIssue,
    CommandResponse,
    CommitRequest,
    CurrentResponse,
    PreviewResponse,
    RejectRequest,
    checkpoint_response,
    preview_response,
)
from prosper.bundle import MAX_BYTES
from prosper.evidence import EvidenceError
from prosper.imports import ImportService
from prosper.persistence import PersistenceError

BODY_MEDIA_TYPES = {
    "/api/v1/previews": b"application/octet-stream",
    "/api/v1/commit": b"application/json",
    "/api/v1/reject": b"application/json",
}
CONTROL_BODY_BYTES = 4096


def install_import_routes(app: FastAPI, service: ImportService) -> None:
    # The outer ASGI boundary is the enforcing authority. This dependency describes
    # bearer requirements in actual OpenAPI without a second session implementation.
    router = APIRouter(
        prefix="/api/v1",
        dependencies=[Depends(HTTPBearer(auto_error=False))],
        responses={status: {"model": APIError} for status in (400, 404, 409, 413, 415, 422, 503)},
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        known = {
            "body",
            "path",
            "identity",
            "schema_version",
            "preview_sha256",
            "command_key",
            "expected_generation",
        }
        errors = error.errors()
        issues = tuple(
            APIIssue(
                code=str(item["type"]),
                path=tuple(
                    p if isinstance(p, int) or p in known else "<field>" for p in item["loc"]
                ),
            )
            for item in errors[:20]
        )
        return JSONResponse(
            APIError(
                error="request_invalid", issues=issues, further_issues=len(errors) > 20
            ).model_dump(mode="json"),
            status_code=422,
        )

    @app.exception_handler(PersistenceError)
    @app.exception_handler(EvidenceError)
    async def storage_error(
        request: Request, error: PersistenceError | EvidenceError
    ) -> JSONResponse:
        status = {
            "preview_missing": 404,
            "command_payload_mismatch": 409,
            "committed_preview_cannot_reject": 409,
        }.get(error.code, 503)
        return JSONResponse(APIError(error=error.code).model_dump(mode="json"), status_code=status)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            APIError(error="internal_error").model_dump(mode="json"), status_code=500
        )

    @router.post("/previews", response_model=PreviewResponse)
    def stage_preview(
        raw: Annotated[
            bytes, Body(media_type="application/octet-stream", max_length=MAX_BYTES)
        ] = b"",
    ) -> PreviewResponse:
        return preview_response(service.previews.stage(raw))

    @router.get("/previews/{identity}", response_model=PreviewResponse)
    def get_preview(identity: Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]) -> PreviewResponse:
        return preview_response(service.previews.get(identity))

    @router.get("/current", response_model=CurrentResponse)
    def current() -> CurrentResponse:
        state = service.current()
        return CurrentResponse(
            generation=state.generation,
            checkpoint=checkpoint_response(state.checkpoint) if state.checkpoint else None,
        )

    @router.post("/commit", response_model=CommandResponse)
    def commit(command: CommitRequest) -> CommandResponse:
        result = service.commit(
            command.preview_sha256, command.command_key, command.expected_generation
        )
        return CommandResponse.model_validate(asdict(result))

    @router.post("/reject", response_model=PreviewResponse)
    def reject(command: RejectRequest) -> PreviewResponse:
        return preview_response(service.previews.reject(command.preview_sha256))

    app.include_router(router)
