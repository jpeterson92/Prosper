"""Current normalized upload and saved source-quality diagnostics.

Conditional lot estimates and retained history use frozen reviewed inputs.
Unknown facts and financial qualification remain explicit; no candidate is constructed.
"""

import base64
import binascii
import hashlib
import json
from datetime import UTC, date, datetime
from http.client import HTTPException
from threading import Lock
from typing import cast
from urllib.error import URLError

from pydantic import JsonValue

from prosper import benchmark_metadata as metadata_source
from prosper import benchmark_source as benchmark_sources
from prosper import vanguard as v
from prosper.advisory_records import AnalysisRun, Fact, Finding, ImportSnapshot, encode
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import (
    DiagnosticRequest,
    FidelityOpening,
    FidelityPreviewResponse,
    FidelityUpload,
    HistoryDiagnosticRequest,
    HistoryManifest,
    HistoryUpload,
    LotSettingsRequest,
    PreviewResponse,
    SourceIssue,
    Upload,
)
from prosper.benchmark import (
    BenchmarkDiagnostic,
    BenchmarkFetch,
    BenchmarkImport,
    BenchmarkObservation,
    BenchmarkResult,
    BenchmarkReview,
    review_result,
)
from prosper.candidate_workflow import CandidateStart, FrozenCandidate
from prosper.fidelity_import import normalize
from prosper.history import Alignment, HistoryRequest
from prosper.history_refresh import align
from prosper.holdings_mapping import HoldingsMappingRequest
from prosper.lot_opportunities import ScreeningInputs, evaluate, screening_inputs
from prosper.lot_records import (
    Account,
    Evidence,
    FidelityContext,
    LotDiagnosticRequest,
    LotSettings,
    ScreeningFacts,
)
from prosper.modeled_inputs import (
    FrozenModeledInputs,
    ModeledDiagnostic,
    ModeledResult,
    ModeledUpload,
)
from prosper.modeled_inputs import (
    evaluate as evaluate_inputs,
)
from prosper.modeled_inputs import (
    history_request as modeled_history_request,
)
from prosper.modeled_inputs import (
    union as modeled_union,
)
from prosper.risk_inputs import conventions_available
from prosper.storage import PersistenceError


class Workspace:
    def __init__(self, store: AdvisoryStore) -> None:
        self.store = store
        self._metadata_lock = Lock()
        from prosper.candidate_jobs import CandidateJobs

        self.candidates = CandidateJobs(store)

    def start_candidate(self, command: CandidateStart) -> AnalysisRun:
        def freeze() -> FrozenCandidate:
            state = self.store.current()
            inputs = self.store.run(command.input_run_id)
            if (
                inputs.model_version != "modeled-inputs-v1"
                or inputs.status != "partial"
                or inputs.input_revision != command.expected_revision
                or inputs.snapshot_id != state["snapshot_id"]
            ):
                raise PersistenceError("current_modeled_inputs_required")
            frozen = self.store.modeled_inputs(inputs.inputs["modeled_inputs"])
            selected = self.store.selected_snapshots()
            sources = tuple(
                sorted(set(frozen.retained_sources) | {s.source_sha256 for s in selected})
            )
            for digest in sources:
                self.store.source_bytes(digest)
            return FrozenCandidate(
                command=command,
                modeled=frozen,
                coverage=ModeledResult.model_validate_json(json.dumps(inputs.outputs)),
                snapshot=self.store.snapshot(inputs.snapshot_id),
                retained_snapshots=tuple(
                    s for s in selected if s != self.store.snapshot(inputs.snapshot_id)
                ),
                required_sources=sources,
            )

        return self.candidates.start(command, freeze)

    @staticmethod
    def _input_sources(upload: ModeledUpload) -> dict[str, bytes]:
        result = {}
        for source in upload.sources:
            try:
                raw = base64.b64decode(source.source_base64, validate=True)
            except ValueError:
                raise PersistenceError("invalid_source_encoding") from None
            if not raw or hashlib.sha256(raw).hexdigest() != source.sha256:
                raise PersistenceError("source_checksum_or_size_invalid")
            if source.sha256 in result:
                raise PersistenceError("duplicate_input_source")
            result[source.sha256] = raw
        return result

    def _prepare_inputs(
        self, upload: ModeledUpload, as_of: str
    ) -> tuple[FrozenModeledInputs, ModeledResult]:
        supplied = self._input_sources(upload)
        state = self.store.current()
        if state["snapshot_id"] is None:
            raise PersistenceError("selected_snapshot_required")
        snapshot = self.store.snapshot(str(state["snapshot_id"]))
        settings = cast(dict[str, JsonValue], state["settings"])
        benchmark_id = settings.get("benchmark_run_id")
        benchmark = None
        benchmark_sources = set()
        if isinstance(benchmark_id, str):
            saved = self.store.run(benchmark_id)
            if saved.model_version != "benchmark-proxy-v1" or saved.status != "partial":
                raise PersistenceError("benchmark_selection_unavailable")
            benchmark = BenchmarkResult.model_validate_json(json.dumps(saved.outputs))
            with self.store._connection() as connection:
                benchmark_sources = {
                    row[0]
                    for row in connection.execute(
                        "SELECT source_sha256 FROM run_sources WHERE run_id=?", (benchmark_id,)
                    )
                }
        try:
            lot_settings = LotSettings.model_validate_json(
                json.dumps(settings["lot_opportunities"])
            )
        except (KeyError, ValueError, TypeError):
            lot_settings = None
        ids, _, _ = modeled_union(snapshot, benchmark, upload.bundle)
        request = modeled_history_request(upload.bundle, ids)
        alignment = self.plan_history(request) if request else None
        evidence = [s.evidence for s in upload.bundle.securities if s.security_id in ids]
        evidence += [m.evidence for m in upload.bundle.marks if m.mark.security_id in ids]
        evidence += [c.evidence for c in upload.bundle.classifications if c.security_id in ids]
        requested_sources = (
            {s.source_sha256 for s in evidence} | {snapshot.source_sha256} | benchmark_sources
        )
        if alignment:
            requested_sources.update(alignment.required_sources)
        available = set()
        for digest in requested_sources:
            if digest in supplied:
                available.add(digest)
            else:
                try:
                    self.store.source_bytes(digest)
                    available.add(digest)
                except PersistenceError:
                    pass
        frozen = FrozenModeledInputs(
            bundle=upload.bundle,
            benchmark=benchmark,
            benchmark_run_id=str(benchmark_id) if benchmark_id else None,
            lot_settings=lot_settings,
            alignment=alignment,
            available_sources=tuple(sorted(available)),
            retained_sources=tuple(sorted(available)),
            benchmark_sources=tuple(sorted(benchmark_sources)),
        )
        result = evaluate_inputs(
            snapshot,
            benchmark,
            lot_settings,
            upload.bundle,
            alignment,
            as_of,
            frozenset(available),
            tuple(sorted(benchmark_sources)),
            int(str(state["revision"])),
        )
        return frozen, result

    def preview_inputs(self, upload: ModeledUpload) -> ModeledResult:
        from prosper.advisory_store import _now

        return self._prepare_inputs(upload, _now())[1]

    def diagnose_inputs(self, command: ModeledDiagnostic) -> AnalysisRun:
        supplied = self._input_sources(command)
        request = command.model_dump(mode="json", exclude={"sources"})
        request["source_digests"] = sorted(supplied)
        try:
            saved = self.store.run(command.run_id)
        except PersistenceError as error:
            if error.code != "analysis_missing":
                raise
            saved = None
        if saved:
            if (
                saved.model_version != "modeled-inputs-v1"
                or saved.inputs.get("modeled_request") != request
            ):
                raise PersistenceError("analysis_id_reused")
            if saved.status != "running":
                return saved
            frozen = self.store.modeled_inputs(saved.inputs["modeled_inputs"])
            for digest in frozen.retained_sources:
                self.store.source_bytes(digest)
            snapshot = self.store.snapshot(saved.snapshot_id)
            result = evaluate_inputs(
                snapshot,
                frozen.benchmark,
                frozen.lot_settings,
                frozen.bundle,
                frozen.alignment,
                saved.as_of,
                frozenset(frozen.available_sources),
                frozen.benchmark_sources,
                saved.input_revision,
            )
        else:
            frozen, result = self._prepare_inputs(command, command.as_of)
            if result.input_revision != command.expected_revision:
                raise PersistenceError("stale_revision")
            for digest in frozen.retained_sources:
                if digest in supplied:
                    self.store.retain_source(supplied[digest])
            saved = self.store.start_run(
                command.run_id,
                command.expected_revision,
                inputs={
                    "modeled_request": request,
                    "modeled_inputs": self.store.freeze_modeled(frozen),
                },
                application_version="prosper-advisory-v1",
                model_version="modeled-inputs-v1",
                as_of=command.as_of,
                source_ids=frozen.retained_sources,
            )
        return self.store.complete_run(
            saved.id,
            outputs=result.model_dump(mode="json"),
            status="partial",
            exclusions=result.exclusions,
            warnings=result.warnings,
        )

    def fetch_benchmark(self, request: BenchmarkFetch) -> BenchmarkObservation:
        observation, fresh = self.store.begin_benchmark(request)
        if not fresh:
            return observation
        selection = benchmark_sources.select_fund(
            request.ticker,
            date.fromisoformat(request.requested_date) if request.requested_date else None,
        )
        acquired = benchmark_sources.acquire(
            selection,
            collected_at=datetime.fromisoformat(observation.collected_at),
            transport=v.fetch_https,
        )
        return self._save_benchmark(observation, acquired)

    def import_benchmark(self, imported: BenchmarkImport) -> BenchmarkObservation:
        try:
            raw = base64.b64decode(imported.source_base64, validate=True)
        except ValueError:
            raise PersistenceError("invalid_source_encoding") from None
        # A saved response uses the same acquisition parser; imports are never a fallback.
        request_digest = hashlib.sha256(encode(imported).encode()).hexdigest()
        observation, fresh = self.store.begin_benchmark(
            imported.request, request_digest, imported.collected_at
        )
        if not fresh:
            if (
                observation.source_sha256
                and observation.source_sha256 != hashlib.sha256(raw).hexdigest()
            ):
                raise PersistenceError("command_key_reused")
            return observation
        selection = benchmark_sources.select_fund(
            imported.request.ticker,
            date.fromisoformat(imported.request.requested_date)
            if imported.request.requested_date
            else None,
        )
        acquired = benchmark_sources.acquire(
            selection,
            collected_at=datetime.fromisoformat(imported.collected_at),
            transport=lambda _: v.Response(
                imported.http_status,
                imported.response_url,
                imported.content_type,
                raw,
                imported.body_complete,
            ),
        )
        return self._save_benchmark(observation, acquired)

    def _save_benchmark(
        self, observation: BenchmarkObservation, acquired: v.Acquisition
    ) -> BenchmarkObservation:
        response, snapshot = acquired.response, acquired.snapshot
        raw = response.body if response and response.body else None
        issues = acquired.issues
        if raw and len(raw) > v.MAX_BYTES:
            raw = None
            issues += ("response_exceeds_retention_limit",)
        updated = observation.model_copy(
            update={
                "status": "observed" if snapshot else "unavailable",
                "effective_date": snapshot.effective_date.isoformat() if snapshot else None,
                "source_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                "http_status": response.status if response else None,
                "response_url": response.url if response else None,
                "content_type": response.content_type if response else None,
                "body_complete": response.body_complete if response else False,
                "issues": issues,
                "section_counts": {s.name: len(s.rows) for s in snapshot.sections}
                if snapshot
                else {},
            }
        )
        return self.store.finish_benchmark(updated, raw)

    def prepare_benchmark(self, command: metadata_source.PrepareRequest) -> "BenchmarkReview":
        with self._metadata_lock:
            observation = self.store.benchmark_observation(command.observation_id)
            if observation.status != "observed" or observation.request.ticker != "IVV":
                raise PersistenceError("benchmark_metadata_invalid")
            imported = command.metadata_response
            try:
                if observation.metadata is not None:
                    metadata_raw = self.store.source_bytes(observation.metadata.source_sha256)
                    if imported is not None and (
                        hashlib.sha256(
                            metadata_source.decode_metadata(imported.source_base64)
                        ).hexdigest()
                        != observation.metadata.source_sha256
                    ):
                        raise PersistenceError("benchmark_metadata_already_bound")
                else:
                    if imported is None:
                        response = metadata_source.fetch_metadata()
                        collected = datetime.now(UTC)
                    else:
                        response = v.Response(
                            imported.http_status,
                            imported.response_url,
                            imported.content_type,
                            metadata_source.decode_metadata(imported.source_base64),
                            imported.body_complete,
                        )
                        collected = datetime.fromisoformat(imported.collected_at)
                    metadata = metadata_source.inspect_metadata(observation, response, collected)
                    metadata_raw = response.body
                    observation = self.store.attach_benchmark_metadata(
                        command.observation_id, metadata, metadata_raw
                    )
                if observation.source_sha256 is None:
                    raise PersistenceError("benchmark_source_unavailable")
                return metadata_source.draft(
                    observation, self.store.source_bytes(observation.source_sha256), metadata_raw
                )
            except (OSError, URLError, HTTPException):
                raise PersistenceError("benchmark_metadata_unavailable") from None
            except PersistenceError:
                raise
            except (ValueError, RecursionError):
                raise PersistenceError("benchmark_metadata_invalid") from None

    def diagnose_benchmark(self, command: BenchmarkDiagnostic) -> AnalysisRun:
        request = command.model_dump(mode="json")
        # Large source bytes belong in sources, not duplicated in frozen request JSON.
        try:
            metadata = metadata_source.decode_metadata(command.review.metadata_base64)
        except ValueError:
            raise PersistenceError("invalid_source_encoding") from None
        metadata_digest = hashlib.sha256(metadata).hexdigest()
        request["review"].pop("metadata_base64")
        request["review"]["metadata_sha256"] = metadata_digest
        try:
            run = self.store.run(command.run_id)
        except PersistenceError as error:
            if error.code != "analysis_missing":
                raise
            run = None
        if run:
            if (
                run.model_version != "benchmark-proxy-v1"
                or run.inputs.get("benchmark_request") != request
            ):
                raise PersistenceError("analysis_id_reused")
            if run.status != "running":
                return run
        observation = self.store.benchmark_observation(command.review.observation_id)
        if observation.source_sha256 is None:
            raise PersistenceError("benchmark_selection_unavailable")
        if max(
            datetime.fromisoformat(observation.collected_at),
            datetime.fromisoformat(command.review.reviewed_at),
        ) > datetime.fromisoformat(command.as_of):
            raise PersistenceError("benchmark_knowledge_after_analysis")
        raw = self.store.source_bytes(observation.source_sha256)
        try:
            result = review_result(observation, raw, command.review, metadata_digest)
        except ValueError:
            raise PersistenceError("benchmark_review_invalid") from None
        if run is None:
            self.store.retain_source(metadata)
            run = self.store.start_run(
                command.run_id,
                command.expected_revision,
                inputs={"benchmark_request": request},
                application_version="prosper-advisory-v1",
                model_version="benchmark-proxy-v1",
                as_of=command.as_of,
                source_ids=tuple(sorted({metadata_digest, observation.source_sha256})),
            )
        return self.store.complete_run(
            run.id,
            outputs=result.model_dump(mode="json"),
            status="partial",
            warnings=result.warnings,
        )

    def stage(self, upload: Upload) -> PreviewResponse:
        if upload.snapshot.holding_preparation is not None:
            raise PersistenceError("holdings_mapping_generated_record_required")
        try:
            raw = base64.b64decode(upload.source_base64, validate=True)
        except (ValueError, binascii.Error):
            raise PersistenceError("invalid_source_encoding") from None
        identity = self.store.stage(upload.snapshot, raw)
        return self.preview(identity)

    def preview(self, identity: str) -> PreviewResponse:
        from prosper.cash_treatment import holdings

        snapshot = self.store.snapshot(identity)
        return PreviewResponse(id=identity, snapshot=snapshot, cash_holdings=holdings(snapshot))

    def prepare_holdings(self, command: "HoldingsMappingRequest") -> PreviewResponse:
        from prosper.holdings_mapping import prepare

        state = self.store.current()
        settings = cast(dict[str, JsonValue], state["settings"])
        if (state["revision"], state["snapshot_id"], settings.get("benchmark_run_id")) != (
            command.expected_revision,
            command.snapshot_id,
            command.benchmark_run_id,
        ):
            raise PersistenceError("holdings_mapping_inputs_changed")
        snapshot = self.store.snapshot(command.snapshot_id)
        benchmark = self.store.run(command.benchmark_run_id)
        result = BenchmarkResult.model_validate_json(json.dumps(benchmark.outputs))
        observation = self.store.benchmark_observation(result.observation_id)
        if observation.source_sha256 is None:
            raise PersistenceError("benchmark_source_unavailable")
        raw = self.store.source(command.snapshot_id)
        try:
            prepared = prepare(
                snapshot,
                raw,
                observation,
                self.store.source_bytes(observation.source_sha256),
                result,
                command,
            )
        except ValueError as error:
            code = str(error)
            raise PersistenceError(
                code if code.startswith("holdings_mapping_") else "holdings_mapping_invalid"
            ) from None
        return self.preview(self.store.stage(prepared, raw))

    def open_fidelity(self, opening: FidelityOpening) -> FidelityPreviewResponse:
        """Import source facts without requiring hand-authored context JSON."""
        try:
            raw = base64.b64decode(opening.source_base64, validate=True)
        except ValueError:
            raise PersistenceError("invalid_source_encoding") from None
        evidence = Evidence(
            actor="Local user",
            reference="User-entered U.S. taxable USD opening facts; securities unreviewed",
            effective_at=opening.source_as_of,
            recorded_at=opening.recorded_at,
        )
        context = FidelityContext(
            version="fidelity-lot-context-v1",
            source_sha256=hashlib.sha256(raw).hexdigest(),
            source_as_of=opening.source_as_of,
            currency=opening.currency,
            accounts=(
                Account(
                    source_account=opening.source_account,
                    account_id="account-"
                    + hashlib.sha256(opening.source_account.encode()).hexdigest(),
                    alias=opening.account_alias,
                    role="traded-taxable",
                    evidence=evidence,
                ),
            ),
            mappings=(),
            source_coverage=Fact[str](value=None, reason="Export coverage has not been reviewed"),
            reported_basis_assumption=Fact[bool](
                value=None, reason="Reported basis assumption has not been reviewed"
            ),
            evidence=evidence,
            screening=ScreeningFacts(
                unbounded_event=Fact[bool](
                    value=None, reason="Account activity coverage is unknown"
                )
            ),
        )
        return self.stage_fidelity(
            FidelityUpload(context=context, source_base64=opening.source_base64)
        )

    def stage_fidelity(self, upload: FidelityUpload) -> FidelityPreviewResponse:
        try:
            raw = base64.b64decode(upload.source_base64, validate=True)
            snapshot, inspected = normalize(raw, upload.context)
        except (ValueError, binascii.Error):
            raise PersistenceError("fidelity_context_or_source_invalid") from None
        preview = None
        if snapshot is not None:
            identity = self.store.stage(snapshot, raw)
            preview = self.preview(identity)
        return FidelityPreviewResponse(
            preview=preview,
            issues=tuple(
                SourceIssue(code=i.code, record=i.record, column=i.column) for i in inspected.issues
            ),
        )

    def configure_lots(self, command: LotSettingsRequest) -> dict[str, JsonValue]:
        settings = cast(dict[str, JsonValue], self.store.current()["settings"])
        return self.store.configure(
            {**settings, "lot_opportunities": command.settings.model_dump(mode="json")},
            command.command_key,
            command.expected_revision,
        )

    def diagnose_lots(self, command: LotDiagnosticRequest) -> AnalysisRun:

        try:
            run = self.store.run(command.run_id)
        except PersistenceError as error:
            if error.code != "analysis_missing":
                raise
            run = None
        document = command.model_dump(mode="json")
        if run:
            if (
                run.model_version != "lot-opportunities-v1"
                or run.inputs.get("lot_request") != document
            ):
                raise PersistenceError("analysis_id_reused")
            if run.status != "running":
                return run
            retained = ScreeningInputs.model_validate_json(
                json.dumps(run.inputs["screening_inputs"])
            )
        else:
            state = self.store.current()
            if state["snapshot_id"] is None:
                raise PersistenceError("selected_snapshot_required")
            selected = self.store.snapshot(str(state["snapshot_id"]))
            retained = screening_inputs(
                (selected, *(s for s in self.store.selected_snapshots() if s != selected))
            )
            if set(command.sale_quantities) - {lot.id for lot in selected.lots}:
                raise PersistenceError("lot_diagnostic_request_invalid")
            try:
                settings = LotSettings.model_validate_json(
                    json.dumps(cast(dict[str, JsonValue], state["settings"])["lot_opportunities"])
                )
            except (KeyError, ValueError, TypeError):
                raise PersistenceError("lot_settings_required_or_invalid") from None
            if (
                settings.analysis_date
                > datetime.fromisoformat(command.as_of).astimezone(UTC).date().isoformat()
            ):
                raise PersistenceError("future_lot_analysis_date")
            run = self.store.start_run(
                command.run_id,
                command.expected_revision,
                inputs={
                    "lot_request": document,
                    "screening_inputs": retained.model_dump(mode="json"),
                },
                application_version="prosper-advisory-v1",
                model_version="lot-opportunities-v1",
                as_of=command.as_of,
                source_ids=retained.sources,
            )
        settings = LotSettings.model_validate_json(json.dumps(run.settings["lot_opportunities"]))
        snapshot = self.store.snapshot(run.snapshot_id)
        try:
            result = evaluate(snapshot, retained, settings, command)
        except ValueError:
            raise PersistenceError("lot_diagnostic_request_invalid") from None
        return self.store.complete_run(
            run.id,
            outputs=result.model_dump(mode="json"),
            status="partial",
            exclusions=snapshot.exclusions,
            warnings=result.warnings,
        )

    def import_history(self, upload: HistoryUpload) -> dict[str, JsonValue]:
        """Current local file workflow; HTTP callers stage bounded parts first."""
        from prosper import history_upload
        from prosper.api_contracts import HistoryManifest

        history_upload.validate(tuple(history_upload.decode(p) for p in upload.parts))
        identities = tuple(history_upload.stage(self.store, p).id for p in upload.parts)
        return self.refresh_history(
            HistoryManifest(
                part_count=upload.part_count,
                part_ids=identities,
                command_key=upload.command_key,
                expected_revision=upload.expected_revision,
            )
        )

    def refresh_history(self, manifest: HistoryManifest) -> dict[str, JsonValue]:
        from prosper.history_upload import activate

        return activate(self.store, manifest)

    def preview_history(self, manifest: HistoryManifest) -> HistoryManifest:
        from prosper.history_upload import preview

        return preview(self.store, manifest)

    def plan_history(self, request: HistoryRequest) -> Alignment:
        batches = self.store.history_batches()
        unavailable = set()
        with self.store._connection() as connection:
            for batch in batches:
                try:
                    self.store._source(connection, batch.source_sha256)
                except PersistenceError:
                    unavailable.add(batch.source_sha256)
        try:
            return align(request, batches, frozenset(unavailable))
        except ValueError as error:
            if str(error) in ("history_table_encoded_size_limit", "history_table_size_limit"):
                raise PersistenceError("history_alignment_size_limit") from None
            raise

    def diagnose_history(self, command: HistoryDiagnosticRequest) -> AnalysisRun:
        if datetime.fromisoformat(command.request.known_at) > datetime.fromisoformat(command.as_of):
            raise PersistenceError("history_knowledge_after_analysis")
        try:
            run = self.store.run(command.run_id)
        except PersistenceError as error:
            if error.code != "analysis_missing":
                raise
            run = None
        if run:
            if (run.input_revision, run.as_of, run.inputs.get("history_request")) != (
                command.expected_revision,
                command.as_of,
                command.request.model_dump(mode="json"),
            ):
                raise PersistenceError("analysis_id_reused")
            if run.status != "running":
                return run
            alignment = self.store.alignment(str(run.inputs["alignment_ref"]))
            for digest in alignment.required_sources:
                self.store.source_bytes(digest)
        else:
            alignment = self.plan_history(command.request)
            # Refuse a request that omits a held name; keep the explicit full grid.
            state = self.store.current()
            if state["snapshot_id"]:
                snapshot = self.store.snapshot(str(state["snapshot_id"]))
                held = {r.security_id for r in snapshot.lots} | {
                    r.security_id for r in snapshot.positions
                }
                held -= {
                    s.id
                    for s in snapshot.securities
                    if s.classification.value is not None
                    and s.classification.value != "us-domestic-common-equity"
                }
                held -= snapshot.cash_security_ids
                held -= snapshot.excluded_stock_ids
                if not held <= {s.security_id for s in command.request.series}:
                    raise PersistenceError("required_held_security_missing")
            run = self.store.start_run(
                command.run_id,
                command.expected_revision,
                inputs={
                    "history_request": command.request.model_dump(mode="json"),
                    "alignment_ref": self.store.retain_alignment(alignment),
                },
                application_version="prosper-advisory-v1",
                model_version="history-inputs-v1",
                as_of=command.as_of,
                source_ids=alignment.required_sources,
            )
        innovation_available = conventions_available(alignment)
        outputs: dict[str, JsonValue] = {
            "kind": "history-inputs-v1",
            "financial_use_authorized": False,
            "coverage_complete": alignment.complete,
            "ordered_securities": [s.security_id for s in alignment.request.series],
            "sessions": list(alignment.request.sessions),
            "return_cell_count": alignment.rows.row_count,
            "alignment_ref": run.inputs["alignment_ref"],
            "issues": [i.model_dump(mode="json") for i in alignment.issues],
            "intervals": [i.model_dump(mode="json") for i in alignment.intervals],
            "full_window_validated_at": dict(alignment.validated_at),
            "innovation_inputs_available": innovation_available,
            "innovation_reason": None
            if innovation_available
            else (
                "Complete compatible declared OHLC/total-return inputs "
                "and an explicit profile are required"
            ),
            "financial_metrics": None,
            "financial_metrics_reason": (
                "History input diagnostics do not establish qualified risk, "
                "tax eligibility or suggestions"
            ),
        }
        # Convert dataclass tuples to JSON arrays at this single analytical boundary.
        outputs = cast(dict[str, JsonValue], json.loads(json.dumps(outputs, allow_nan=False)))
        return self.store.complete_run(
            run.id,
            outputs=outputs,
            status="partial",
            warnings=(
                "History/input diagnostics only; model/source qualification "
                "and financial suggestions remain unavailable",
            ),
        )

    @staticmethod
    def findings(snapshot: ImportSnapshot) -> tuple[Finding, ...]:
        findings = list(snapshot.findings)
        for group in ("securities", "lots", "positions", "cash"):
            for row in getattr(snapshot, group):
                for name, value in row.model_dump().items():
                    if isinstance(value, dict) and value.get("value", 1) is None:
                        findings.append(
                            Finding(
                                code="unknown_fact",
                                locator=f"{group}/{row.id}/{name}",
                                reason=str(value["reason"]),
                            )
                        )
        return tuple(findings)

    def diagnose(self, command: DiagnosticRequest) -> AnalysisRun:
        # Start freezes selected inputs/settings. A retry uses the same run ID;
        # later edits cannot publish an old result as current.
        run = self.store.start_run(
            command.run_id,
            command.expected_revision,
            inputs={"diagnostic": "source-quality-v1"},
            application_version="prosper-advisory-v1",
            model_version="source-quality-v1",
            as_of=command.as_of,
        )
        if run.status != "running":
            return run
        snapshot = self.store.snapshot(run.snapshot_id)
        findings = self.findings(snapshot)
        source_status = "available"
        try:
            self.store.source(run.snapshot_id)
        except PersistenceError:
            source_status = "unavailable"
            findings += (
                Finding(
                    code="source_unavailable",
                    locator="source",
                    reason="Retained source bytes are unavailable or corrupt",
                ),
            )
        counts: dict[str, JsonValue] = {
            name: len(getattr(snapshot, name))
            for name in ("securities", "lots", "positions", "cash")
        }
        return self.store.complete_run(
            run.id,
            status="partial",
            outputs=cast(
                dict[str, JsonValue],
                {
                    "kind": "source-quality-v1",
                    "financial_use_authorized": False,
                    "source_as_of": snapshot.source_as_of,
                    "source_status": source_status,
                    "counts": counts,
                    "findings": [item.model_dump(mode="json") for item in findings],
                    "financial_metrics": None,
                    "financial_metrics_reason": (
                        "Marks, screening and qualified risk inputs are not assembled"
                    ),
                },
            ),
            exclusions=snapshot.exclusions,
            warnings=("Source diagnostics only; financial suggestions are unavailable",),
        )
