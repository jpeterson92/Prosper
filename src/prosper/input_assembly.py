"""Source-bound assembly of the current input contract, without acquisition."""

import hashlib
import json
import math
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Self

import polars as pl
from pydantic import Field, field_validator, model_validator

from prosper.advisory_records import (
    DecimalFact,
    Digest,
    Fact,
    ImportSnapshot,
    Lot,
    Position,
    Record,
    encode,
)
from prosper.benchmark import BenchmarkResult, acquisition
from prosper.benchmark_mapping import prepare as issuer_mapping
from prosper.history import HistoryBatch, HistoryRequest, SeriesContext
from prosper.history_refresh import check_parts
from prosper.history_table import SessionGrid
from prosper.lot_records import Mark
from prosper.modeled_inputs import (
    ClassificationInput,
    InputAssemblyBinding,
    InputCoverageSettings,
    InputIssue,
    InputProfile,
    InputSource,
    InvestorControl,
    MarkInput,
    ModeledBundle,
    ModeledResult,
    ModeledUpload,
    RiskOverrides,
    RiskPresetRequest,
    SecurityInput,
    SourceFact,
    prepare_risk_preset,
)
from prosper.record_types import DateText, Identifier, Text, Timestamp
from prosper.storage import PersistenceError

if TYPE_CHECKING:
    from prosper.workspace import Workspace


class HistoryWindow(Record):
    batch_ids: tuple[Digest, ...] = Field(min_length=1, max_length=500)
    sessions: tuple[DateText, ...] = Field(min_length=1, max_length=10000)
    predecessor: DateText
    cutoff: DateText
    known_at: Timestamp
    calendar_evidence: Text
    overlap_sessions: Annotated[int, Field(ge=1, le=100)]
    # An explicit choice must equal a context in a selected original batch.
    series_choices: tuple[SeriesContext, ...] = ()

    @field_validator("batch_ids", "sessions", "series_choices", mode="before")
    @classmethod
    def json_arrays(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


class TaxonomyDeclaration(Record):
    name: Text
    version: Text


class InputAssemblyRequest(Record):
    expected_revision: Annotated[int, Field(ge=0, lt=2**63 - 1)]
    analysis_date: DateText
    as_of: Timestamp
    history: HistoryWindow | None = None
    coverage_settings: InputCoverageSettings | None = None
    risk_overrides: RiskOverrides = Field(default_factory=lambda: RiskOverrides())
    investor_controls: tuple[InvestorControl, ...] = ()
    fact_run_id: Identifier | None = None
    source_declarations: tuple[SourceFact, ...] = ()
    securities: tuple[SecurityInput, ...] = ()
    marks: tuple[MarkInput, ...] = ()
    taxonomy: TaxonomyDeclaration | None = None
    classifications: tuple[ClassificationInput, ...] = ()
    sources: tuple[InputSource, ...] = ()

    @field_validator(
        "investor_controls",
        "source_declarations",
        "securities",
        "marks",
        "classifications",
        "sources",
        mode="before",
    )
    @classmethod
    def json_arrays(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def keys(self) -> Self:
        groups = [
            tuple(s.source_sha256 for s in self.source_declarations),
            tuple(s.security_id for s in self.securities),
            tuple(m.mark.security_id for m in self.marks),
            tuple(c.security_id for c in self.classifications),
            tuple(c.name for c in self.investor_controls),
            tuple(s.sha256 for s in self.sources),
        ]
        if self.history:
            groups.extend(
                [self.history.batch_ids, tuple(c.security_id for c in self.history.series_choices)]
            )
        if any(len(set(g)) != len(g) for g in groups):
            raise ValueError("duplicate_assembly_key")
        return self


class HistoryOption(Record):
    id: Digest
    source_name: Text
    source_sha256: Digest
    contexts: tuple[SeriesContext, ...]
    sessions: SessionGrid
    collected_at: Timestamp
    validated_at: Timestamp
    validation_scope: Literal["requested-interval", "full-window"]


class InputAssemblyContext(Record):
    input_revision: int
    snapshot_id: Digest | None
    benchmark_run_id: Identifier | None
    selected_source_sha256: tuple[Digest, ...]
    benchmark_security_ids: tuple[Identifier, ...]
    history_options: tuple[HistoryOption, ...]
    fact_run_ids: tuple[Identifier, ...]


class AssembledInputs(Record):
    input_revision: int
    snapshot_id: Digest | None
    benchmark_run_id: Identifier | None
    candidate_security_ids: tuple[Identifier, ...]
    retained_candidate_security_ids: tuple[Identifier, ...] | None
    upload: ModeledUpload | None
    coverage: ModeledResult | None
    issues: tuple[InputIssue, ...]


def selected(
    workspace: "Workspace",
) -> tuple[dict[str, object], ImportSnapshot | None, str | None, BenchmarkResult | None]:
    state = workspace.store.current()
    snapshot = workspace.store.snapshot(str(state["snapshot_id"])) if state["snapshot_id"] else None
    settings = state["settings"]
    identity = settings.get("benchmark_run_id") if isinstance(settings, dict) else None
    benchmark_id = identity if isinstance(identity, str) else None
    benchmark = None
    if benchmark_id:
        saved = workspace.store.run(benchmark_id)
        if saved.model_version != "benchmark-proxy-v1" or saved.status != "partial":
            raise PersistenceError("benchmark_selection_unavailable")
        benchmark = BenchmarkResult.model_validate_json(json.dumps(saved.outputs))
    return dict(state), snapshot, benchmark_id, benchmark


def context(workspace: "Workspace") -> InputAssemblyContext:
    state, snapshot, benchmark_id, benchmark = selected(workspace)
    sources = {snapshot.source_sha256} if snapshot else set()
    with workspace.store._connection() as connection:
        if benchmark_id:
            sources.update(
                r[0]
                for r in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=?", (benchmark_id,)
                )
            )
        fact_runs = tuple(
            r[0]
            for r in connection.execute(
                "SELECT id FROM runs WHERE json_extract(document,'$.model_version')="
                "'modeled-inputs-v1' AND json_extract(document,'$.status')='partial' ORDER BY rowid"
            )
        )
    result = InputAssemblyContext(
        input_revision=int(str(state["revision"])),
        snapshot_id=str(state["snapshot_id"]) if snapshot else None,
        benchmark_run_id=benchmark_id,
        selected_source_sha256=tuple(sorted(sources)),
        benchmark_security_ids=benchmark.security_ids if benchmark else (),
        history_options=tuple(
            HistoryOption(
                id=hashlib.sha256(encode(b).encode()).hexdigest(),
                source_name=b.source_name,
                source_sha256=b.source_sha256,
                contexts=b.contexts,
                sessions=b.sessions,
                collected_at=b.collected_at,
                validated_at=b.validated_at,
                validation_scope=b.validation_scope,
            )
            for b in workspace.store.history_batches()
        ),
        fact_run_ids=fact_runs,
    )
    if workspace.store.current()["revision"] != state["revision"]:
        raise PersistenceError("stale_revision")
    return result


def assemble(workspace: "Workspace", request: InputAssemblyRequest) -> AssembledInputs:
    state, snapshot, benchmark_id, benchmark = selected(workspace)
    revision = int(str(state["revision"]))
    if revision != request.expected_revision:
        raise PersistenceError("stale_revision")
    issues: list[InputIssue] = []

    def issue(scope: str, code: str, locator: str, reason: str, sid: str | None = None) -> None:
        issues.append(
            InputIssue.model_validate(
                dict(scope=scope, code=code, locator=locator, reason=reason, security_id=sid)
            )
        )

    candidates = (
        tuple(
            s
            for s in benchmark.security_ids
            if snapshot is None or s not in snapshot.cash_security_ids | snapshot.excluded_stock_ids
        )
        if benchmark
        else ()
    )
    result_upload: ModeledUpload | None = None
    result_coverage: ModeledResult | None = None

    def finish() -> AssembledInputs:
        if workspace.store.current()["revision"] != revision:
            raise PersistenceError("stale_revision")
        retained = set(result_coverage.security_ids) if result_coverage else set()
        return AssembledInputs(
            input_revision=revision,
            snapshot_id=str(state["snapshot_id"]) if snapshot else None,
            benchmark_run_id=benchmark_id,
            candidate_security_ids=candidates,
            retained_candidate_security_ids=tuple(s for s in candidates if s in retained)
            if result_coverage
            else None,
            upload=result_upload,
            coverage=result_coverage,
            issues=tuple(issues),
        )

    if snapshot is None:
        issue("universe", "selected_snapshot_required", "snapshot", "Select current holdings")
    if benchmark is None or benchmark.status != "estimated-equity-benchmark":
        issue(
            "benchmark",
            "selected_benchmark_required",
            "benchmark",
            "Select a complete reviewed benchmark",
        )
    if benchmark and any(
        datetime.fromisoformat(t) > datetime.fromisoformat(request.as_of)
        for t in (benchmark.collected_at, benchmark.reviewed_at)
    ):
        issue(
            "source",
            "benchmark_knowledge_after_analysis",
            "benchmark/known_at",
            "Selected benchmark collection/review follows the declared analysis knowledge time",
        )
        return finish()
    if request.coverage_settings is None:
        issue(
            "settings",
            "coverage_settings_required",
            "coverage_settings",
            "Declare freshness and capacity settings; no example values are adopted",
        )
    if request.history is None:
        issue(
            "history",
            "history_selection_required",
            "history",
            "Choose imported history originals and declare the exact calendar/window",
        )
    if not request.investor_controls:
        issue(
            "settings",
            "investor_controls_required",
            "investor_controls",
            "Supply explicit investor controls; no economic limits are invented",
        )
    if (
        snapshot is None
        or benchmark is None
        or benchmark_id is None
        or request.history is None
        or request.coverage_settings is None
    ):
        return finish()
    window = request.history
    if window.cutoff != request.analysis_date:
        issue(
            "history",
            "eod_cutoff_mismatch",
            "history/cutoff",
            "EOD analysis date must equal the declared completed-session cutoff",
        )
    if datetime.fromisoformat(window.known_at) > datetime.fromisoformat(request.as_of):
        issue(
            "history",
            "history_knowledge_after_analysis",
            "history/known_at",
            "History knowledge follows the declared analysis time",
        )
    try:
        batches = workspace.store.history_batches(window.batch_ids)
        check_parts(batches)
        for batch in batches:
            workspace.store.source_bytes(batch.source_sha256)
            if datetime.fromisoformat(batch.validated_at) > datetime.fromisoformat(window.known_at):
                issue(
                    "history",
                    "selected_history_knowledge_after_window",
                    "history/known_at",
                    "A selected batch was validated after the declared knowledge time",
                )
        if any(i.code == "selected_history_knowledge_after_window" for i in issues):
            return finish()
    except (PersistenceError, ValueError):
        issue(
            "source",
            "selected_history_unavailable_or_conflicting",
            "history/batch_ids",
            "Selected originals are absent, corrupt or contradictory; no replacement is selected",
        )
        return finish()
    prior = None
    if request.fact_run_id:
        try:
            saved = workspace.store.run(request.fact_run_id)
        except PersistenceError:
            issue(
                "source",
                "fact_run_unavailable",
                "fact_run_id",
                "The selected fact run is unavailable",
            )
            return finish()
        if saved.model_version != "modeled-inputs-v1" or saved.status != "partial":
            issue(
                "source",
                "fact_run_unavailable",
                "fact_run_id",
                "Choose a saved modeled-input diagnostic explicitly",
            )
            return finish()
        try:
            prior = workspace.store.modeled_inputs(saved.inputs["modeled_inputs"]).bundle
        except (PersistenceError, ValueError):
            issue(
                "source",
                "fact_run_unavailable",
                "fact_run_id",
                "The selected frozen fact record is corrupt or unavailable",
            )
            return finish()
    taxonomy = request.taxonomy or (
        TaxonomyDeclaration(name=prior.taxonomy_name, version=prior.taxonomy_version)
        if prior
        else None
    )
    if taxonomy is None:
        issue(
            "taxonomy",
            "taxonomy_declaration_required",
            "taxonomy",
            "Declare taxonomy name/version; sector names do not imply an industry framework",
        )
        return finish()
    securities = {s.security_id: s for s in prior.securities} if prior else {}
    securities.update({s.security_id: s for s in request.securities})
    classifications = (
        {c.security_id: c for c in prior.classifications}
        if prior
        and (taxonomy.name, taxonomy.version) == (prior.taxonomy_name, prior.taxonomy_version)
        else {}
    )
    classifications.update({c.security_id: c for c in request.classifications})
    marks = {m.mark.security_id: m for m in request.marks}
    declarations = {s.source_sha256: s for s in request.source_declarations}
    # Preserve supplied held identities. Only the inspected IVV policy supplies
    # dated benchmark-only local identities; other layouts require explicit facts.
    origins = {
        s.id: (
            s.identity,
            s.classification,
            s.currency,
            snapshot.source_sha256,
            s.source_ref,
            snapshot.source_as_of[:10],
        )
        for s in snapshot.securities
    }
    observation = workspace.store.benchmark_observation(benchmark.observation_id)
    if observation.source_sha256:
        try:
            raw = workspace.store.source_bytes(observation.source_sha256)
        except PersistenceError:
            issue(
                "source",
                "benchmark_source_unavailable",
                "benchmark/source",
                "The selected benchmark original is unavailable or corrupt",
            )
            return finish()
        source = acquisition(observation, raw).snapshot
        policy = issuer_mapping(source) if source else None
        if policy:
            rows = {r.index: r for r in policy.rows if r.action == "include"}
            for row in benchmark.ledger:
                p = rows.get(row.locator.index)
                if (
                    row.disposition == "included-equity"
                    and p
                    and p.security_id == row.security_id
                    and p.row_sha256 == row.row_sha256
                ):
                    sid = str(row.security_id)
                    origins.setdefault(
                        sid,
                        (
                            Fact[str](value=sid),
                            Fact[str](value="us-domestic-common-equity"),
                            "USD",
                            observation.source_sha256,
                            f"{row.locator.section}/{row.locator.index}",
                            benchmark.effective_date,
                        ),
                    )
    holding_rows: tuple[Lot | Position, ...] = (*snapshot.lots, *snapshot.positions)
    held = {r.security_id for r in holding_rows}
    source_securities = {s.id: s for s in snapshot.securities}
    held = {
        s
        for s in held
        if s not in snapshot.cash_security_ids | snapshot.excluded_stock_ids
        and source_securities[s].classification.value in (None, "us-domestic-common-equity")
    }
    ids = tuple(sorted(held | set(benchmark.security_ids) | set(candidates)))
    for sid, (identity, classification, currency, digest, locator, day) in origins.items():
        if sid not in ids:
            continue
        existing = securities.get(sid)
        if existing:
            if (
                (identity.value is not None and identity.value != existing.identity.value)
                or (
                    classification.value is not None
                    and classification.value != existing.classification.value
                )
                or currency != existing.currency
            ):
                issue(
                    "identity",
                    "selected_identity_conflict",
                    locator,
                    "Supplied identity/classification/currency conflicts with the selected source",
                    sid,
                )
        elif digest in declarations:
            declared = declarations[digest]
            if declared.effective != day:
                issue(
                    "identity",
                    "identity_source_date_mismatch",
                    locator,
                    "The declaration must retain the original identity source date",
                    sid,
                )
            else:
                securities[sid] = SecurityInput(
                    security_id=sid,
                    identity=identity,
                    classification=classification,
                    currency=currency,
                    evidence=declared.model_copy(update={"source_ref": locator}),
                )
        else:
            issue(
                "source",
                "source_declaration_required",
                locator,
                "Declare provider, dataset, permission and validity for this identity source",
                sid,
            )
    # Construct the union without inventing identities or requiring a full bundle.
    if any(
        i.code in ("selected_identity_conflict", "identity_source_date_mismatch") for i in issues
    ):
        return finish()
    choices = {c.security_id: c for c in window.series_choices}
    selected_contexts = []
    for sid in ids:
        options = {c for b in batches for c in b.contexts if c.security_id == sid}
        chosen = choices.get(sid)
        if chosen is not None and chosen not in options:
            issue(
                "history",
                "history_context_not_in_selected_sources",
                "history/series_choices",
                "A declared context must equal a selected original context",
                sid,
            )
        elif chosen is not None:
            selected_contexts.append(chosen)
        elif len(options) == 1:
            selected_contexts.append(next(iter(options)))
        else:
            issue(
                "history",
                "history_context_ambiguous_or_missing",
                "history/batch_ids",
                "Choose an attributable history context; none is inferred",
                sid,
            )
    if not selected_contexts or any(
        i.code
        in (
            "eod_cutoff_mismatch",
            "history_knowledge_after_analysis",
            "history_context_not_in_selected_sources",
        )
        for i in issues
    ):
        return finish()
    profile = InputProfile(**request.coverage_settings.model_dump())
    try:
        history = HistoryRequest(
            series=tuple(selected_contexts),
            sessions=window.sessions,
            predecessor=window.predecessor,
            cutoff=window.cutoff,
            known_at=window.known_at,
            calendar_evidence=window.calendar_evidence,
            overlap_sessions=window.overlap_sessions,
            profile=profile.model,
        )
    except ValueError:
        issue(
            "history",
            "history_window_invalid",
            "history",
            "The declared grid, mappings or window is invalid; it is not reconstructed",
        )
        return finish()
    alignment = workspace.plan_history(history, batches=batches)
    by_source: dict[tuple[str, SeriesContext], HistoryBatch] = {}
    for b in batches:
        for c in b.contexts:
            key = (b.source_sha256, c)
            old = by_source.get(key)
            if old is None or datetime.fromisoformat(b.collected_at) < datetime.fromisoformat(
                old.collected_at
            ):
                by_source[key] = b
    by_context = {c.security_id: c for c in selected_contexts}
    end = alignment.rows.frame.filter(pl.col("session") == request.analysis_date)
    for cell in end.iter_rows(named=True):
        sid, price = cell["security_id"], cell["close"]
        identity_input = securities.get(sid)
        c = by_context[sid]
        source_batch = by_source.get((cell["source_sha256"], c))
        supported = (
            c.currency == "USD"
            and c.timezone == "UTC"
            and c.interval == "1d"
            and c.adjustment in ("no-actions", "total-return-adjusted")
            and c.action_convention == "compatible-total-return-and-raw-ohlc"
            and c.repair == "none"
            and not any(
                e.security_id == sid and e.session in (None, request.analysis_date)
                for e in alignment.issues
            )
        )
        supplied_mark = marks.get(sid)
        if supplied_mark and supplied_mark.mark.day.value not in (None, request.analysis_date):
            issue(
                "marks",
                "eod_supplied_mark_date_mismatch",
                supplied_mark.mark.source_ref,
                "A supplied EOD mark must describe the declared completed session",
                sid,
            )
            return finish()
        if (
            supplied_mark
            and source_batch
            and supported
            and price is not None
            and supplied_mark.evidence.source_sha256 == source_batch.source_sha256
            and supplied_mark.mark.price.value is not None
            and float(supplied_mark.mark.price.value) != price
        ):
            issue(
                "marks",
                "eod_source_mark_conflict",
                supplied_mark.mark.source_ref,
                "The supplied mark contradicts this selected original's normalized close",
                sid,
            )
            return finish()
        if (
            sid not in marks
            and identity_input
            and identity_input.identity.value is not None
            and source_batch
            and supported
            and price is not None
            and math.isfinite(price)
            and price > 0
            and cell["source_ref"]
        ):
            marks[sid] = MarkInput(
                mark=Mark(
                    security_id=sid,
                    identity=identity_input.identity.value,
                    price=DecimalFact(value=repr(price)),
                    day=Fact[str](value=request.analysis_date),
                    source_ref=cell["source_ref"],
                    currency="USD",
                ),
                evidence=SourceFact(
                    source_sha256=source_batch.source_sha256,
                    source_ref=cell["source_ref"],
                    provider=c.provider,
                    dataset=c.dataset,
                    permission_scope=c.permission_scope,
                    effective=request.analysis_date,
                    valid_through=request.analysis_date,
                    recorded_at=source_batch.collected_at,
                ),
            )
    binding = InputAssemblyBinding(
        input_revision=revision,
        snapshot_id=str(state["snapshot_id"]),
        benchmark_run_id=benchmark_id,
        history_batch_ids=window.batch_ids,
        fact_run_id=request.fact_run_id,
        source_declarations=request.source_declarations,
        prepared_at=request.as_of,
    )
    bundle = ModeledBundle(
        analysis_date=request.analysis_date,
        candidate_security_ids=candidates,
        securities=tuple(securities[s] for s in ids if s in securities),
        marks=tuple(marks[s] for s in ids if s in marks),
        taxonomy_name=taxonomy.name,
        taxonomy_version=taxonomy.version,
        classifications=tuple(classifications[s] for s in ids if s in classifications),
        history=history,
        profile=profile,
        investor_controls=request.investor_controls,
        assembly=binding,
    )
    result_upload = prepare_risk_preset(
        RiskPresetRequest(
            upload=ModeledUpload(bundle=bundle, sources=request.sources),
            overrides=request.risk_overrides,
        )
    )
    # One financial/source authority: reuse the existing full preview and sleeve.
    result_coverage = workspace._prepare_inputs(result_upload, request.as_of)[1]
    issues.extend(i for i in result_coverage.issues if i not in issues)
    return finish()
