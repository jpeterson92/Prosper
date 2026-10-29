"""Frozen current-input adapter and bounded worker protocol for candidates."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from prosper import covariance, volatility
from prosper.advisory import decimal_value
from prosper.advisory_records import Digest, ImportSnapshot, Record, Revision, Security
from prosper.benchmark_drift import weights_at
from prosper.candidate_fit import CandidateFit, compact
from prosper.candidate_records import (
    Amount,
    Bound,
    CandidateAsset,
    CandidateLimits,
    CandidateRequest,
    CandidateSearch,
    ExposureLimit,
    OptionalLimit,
    RiskInput,
    SearchMethod,
    TaxScenario,
)
from prosper.candidate_reference import search
from prosper.innovations import fingerprint
from prosper.modeled_inputs import FrozenModeledInputs, InvestorControl, ModeledResult, union
from prosper.record_types import Identifier, Text, Timestamp
from prosper.risk_inputs import assemble
from prosper.risk_qualification import profile_issues

MODEL: Literal["candidate-workflow-v1"] = "candidate-workflow-v1"


class CandidateProgress(Record):
    kind: Literal["candidate-progress-v1"]
    claim: Identifier
    phase: Literal["starting", "fitting", "searching"]
    states: Annotated[int, Field(ge=0, le=100000)]
    cancel_requested: bool


class CandidateControls(Record):
    method: SearchMethod
    max_candidates: Annotated[int, Field(ge=1, le=5)]
    max_cost: Amount
    min_price_loss: OptionalLimit
    max_cost_to_loss: OptionalLimit
    min_scenario_net_value: OptionalLimit
    scenario: TaxScenario | None
    buy_fee_per_security_order: Amount
    buy_premium_bps: Amount
    sale_bounds: dict[Identifier, Bound] = Field(max_length=2000)
    buy_bounds: dict[Identifier, Bound] = Field(max_length=500)
    max_states: Annotated[int, Field(ge=1, le=100000)]
    timeout_seconds: Annotated[int, Field(ge=1, le=300)]


class CandidateStart(Record):
    run_id: Identifier
    expected_revision: Revision
    as_of: Timestamp
    input_run_id: Identifier
    controls: CandidateControls


class CandidateIdentity(Record):
    run_id: Identifier


class FrozenCandidate(Record):
    command: CandidateStart
    modeled: FrozenModeledInputs
    coverage: ModeledResult
    snapshot: ImportSnapshot
    retained_snapshots: tuple[ImportSnapshot, ...]
    required_sources: tuple[Digest, ...]

    @model_validator(mode="after")
    def sleeve_links(self) -> "FrozenCandidate":
        ids, _, _ = union(self.snapshot, self.modeled.benchmark, self.modeled.bundle)
        if (
            ids != tuple(d.security_id for d in self.modeled.sleeve.decisions)
            or self.coverage.sleeve != self.modeled.sleeve
            or self.coverage.security_ids != self.modeled.sleeve.retained_ids
        ):
            raise ValueError("candidate_history_sleeve_links_invalid")
        return self


class CandidateOutput(Record):
    kind: Literal["candidate-workflow-v1"] = MODEL
    outcome: Literal[
        "checked", "unavailable", "cancelled", "timeout", "interrupted", "stale", "failed"
    ]
    issues: tuple[Text, ...]
    risk: CandidateFit | None
    search: CandidateSearch | None
    warnings: tuple[Text, ...] = (
        "Unqualified proxy risk and conditional loss estimates; no financial-use authorization",
        "Independent tax/model review, real-source qualification and calibration remain open",
    )
    financial_use_authorized: Literal[False] = False


def check_output_links(frozen: FrozenCandidate, output: CandidateOutput) -> None:
    """Check retained links/shape without fitting or recalculating historical outputs."""
    result = output.search
    if output.outcome == "checked" and (result is None or output.risk is None):
        raise ValueError("candidate_output_links_invalid")
    model = frozen.modeled
    risk = output.risk
    if risk is not None:
        alignment = model.alignment
        if alignment is None or (
            risk.security_ids != frozen.coverage.security_ids
            or risk.cutoff != alignment.request.cutoff
            or risk.sessions != len(alignment.request.sessions)
            or risk.horizon != model.bundle.profile.horizon_sessions
            or risk.calendar != alignment.request.series[0].calendar
            or risk.timezone != alignment.request.series[0].timezone
            or risk.variant != "idr"
            or risk.source_units != "decimal"
            or risk.purpose != "research-window"
        ):
            raise ValueError("candidate_output_links_invalid")
        if risk.projection is not None and (
            result is None
            or risk.projection.annualization != model.bundle.profile.annualization_sessions
            or risk.projection.units != "decimal-return-squared"
            or fingerprint(result.inputs.risk.annual_covariance)
            != risk.projection.annual_covariance_sha256
        ):
            raise ValueError("candidate_output_links_invalid")
    if result is None:
        return
    request = result.inputs
    if model.alignment is None or model.benchmark is None or model.lot_settings is None:
        raise ValueError("candidate_output_links_invalid")
    projection = risk.projection if risk else None
    if projection is None or risk is None:
        raise ValueError("candidate_output_links_invalid")
    settings = model.lot_settings.model_copy(
        update={
            "marks": tuple(
                m.mark
                for m in model.bundle.marks
                if m.mark.security_id in frozen.coverage.security_ids
            )
        }
    )
    controls = frozen.command.controls
    if (
        request.snapshot != frozen.snapshot
        or request.retained_snapshots != frozen.retained_snapshots
        or request.settings != settings
        or request.limits != limits(frozen)
        or request.risk.security_ids != frozen.coverage.security_ids
        or request.risk.benchmark_ids
        != tuple(s for s in model.benchmark.security_ids if s not in model.sleeve.excluded_ids)
        or request.history_excluded_ids != tuple(sorted(model.sleeve.excluded_ids))
        or request.risk.benchmark_weights
        != tuple(m.benchmark_weight or 0.0 for m in frozen.coverage.members)
        or request.risk.as_of != model.alignment.request.cutoff
        or request.risk.max_age_days != model.bundle.profile.max_history_age_days
        or request.risk.annualization_sessions != model.bundle.profile.annualization_sessions
        or request.risk.reference
        != (f"{risk.version}/{risk.identity_sha256}; horizon {risk.horizon}; cutoff {risk.cutoff}")
        or request.sale_bounds != controls.sale_bounds
        or request.buy_bounds != controls.buy_bounds
        or request.max_states != controls.max_states
        or request.method != controls.method
        or request.max_candidates != controls.max_candidates
        or request.buy_fee_per_security_order != controls.buy_fee_per_security_order
        or request.buy_premium_bps != controls.buy_premium_bps
    ):
        raise ValueError("candidate_output_links_invalid")
    supplied = {s.security_id: s for s in model.bundle.securities}
    taxonomy = {s.security_id: s for s in model.bundle.classifications}
    for asset in request.assets:
        sid = asset.security.id
        if (
            sid not in supplied
            or asset.security.identity != supplied[sid].identity
            or asset.security.classification != supplied[sid].classification
            or asset.sector != taxonomy[sid].sector
            or asset.industry != taxonomy[sid].industry
        ):
            raise ValueError("candidate_output_links_invalid")
    if tuple(a.security.id for a in request.assets) != request.risk.security_ids:
        raise ValueError("candidate_output_links_invalid")


def limits(frozen: FrozenCandidate) -> CandidateLimits:
    selected: dict[str, InvestorControl] = {
        c.name: c for c in frozen.modeled.bundle.investor_controls
    }

    def required(name: str) -> str:
        control = selected.get(name)
        if control is None or not control.enabled or control.value.value is None:
            raise ValueError("required_candidate_control_unavailable:" + name)
        return control.value.value

    maximum = selected.get("max_trade_notional")
    if maximum is None:
        raise ValueError("required_candidate_control_unavailable:max_trade_notional")
    exposures = tuple(
        ExposureLimit(
            level="sector" if name == "sector_exposure" else "industry",
            group=control.group or "",
            kind=control.kind or "absolute",
            maximum=control.value.value or "",
        )
        for name, control in selected.items()
        if name in ("sector_exposure", "industry_exposure") and control.enabled
    )
    controls = frozen.command.controls
    return CandidateLimits(
        tracking_error=required("tracking_error"),
        max_cost=controls.max_cost,
        max_orders=int(decimal_value(required("max_orders"))),
        max_turnover=required("turnover"),
        min_order_notional=required("min_trade_notional"),
        max_order_notional=OptionalLimit(enabled=maximum.enabled, value=maximum.value.value),
        max_position_weight=required("max_position_weight"),
        exposures=exposures,
        min_price_loss=controls.min_price_loss,
        max_cost_to_loss=controls.max_cost_to_loss,
        min_scenario_net_value=controls.min_scenario_net_value,
        scenario=controls.scenario,
    )


def prepare(frozen: FrozenCandidate) -> tuple[CandidateRequest | None, tuple[str, ...]]:
    """Inspect the actual application boundary before any expensive fitting."""
    issues = [f"{i.locator}:{i.code}" for i in frozen.coverage.issues]
    model = frozen.modeled
    if (
        not frozen.coverage.software_inputs_complete
        or model.alignment is None
        or model.lot_settings is None
        or model.benchmark is None
    ):
        issues.append("complete_selected_inputs_required")
        return None, tuple(issues)
    if (
        model.bundle.analysis_date
        > datetime.fromisoformat(frozen.command.as_of).astimezone(UTC).date().isoformat()
    ):
        issues.append("analysis_date_after_run")
    ids = frozen.coverage.security_ids
    retained_benchmark = tuple(
        s for s in model.benchmark.security_ids if s not in model.sleeve.excluded_ids
    )
    dated_weights = weights_at(
        model.benchmark,
        model.alignment,
        model.bundle.analysis_date,
        retained_ids=retained_benchmark,
    )
    issues.extend(f"{i.locator}:{i.code}" for i in dated_weights.issues)
    if dated_weights.weights is None or any(
        member.benchmark_weight != dated_weights.weights.get(member.security_id, 0.0)
        for member in frozen.coverage.members
    ):
        issues.append("benchmark_weights_do_not_match_analysis_date")
    if len(ids) > 500:
        issues.append("candidate_component_capacity_unavailable_full_union_retained")
    if frozen.command.controls.method == "complete-cartesian-whole-share-reference" and (
        len(ids) > 16
        or len(frozen.command.controls.sale_bounds) + len(frozen.command.controls.buy_bounds) > 16
    ):
        issues.append("tiny_reference_capacity_unavailable_full_union_retained")
    if (
        set(frozen.command.controls.buy_bounds)
        != set(model.bundle.candidate_security_ids) - model.sleeve.excluded_ids
    ):
        issues.append("candidate_buy_domain_mismatch")
    if issues:
        return None, tuple(issues)
    innovation = assemble(model.alignment)
    if innovation is None:
        return None, ("compatible_innovation_inputs_required",)
    issues.extend(profile_issues(model.bundle.profile, innovation.context, "idr"))
    if issues:
        return None, tuple(issues)
    source_securities = {s.id: s for s in frozen.snapshot.securities}
    supplied = {s.security_id: s for s in model.bundle.securities}
    taxonomy = {c.security_id: c for c in model.bundle.classifications}
    assets = tuple(
        CandidateAsset(
            security=source_securities.get(sid)
            or Security(
                id=sid,
                source_ref=supplied[sid].evidence.source_ref,
                ticker="[ticker not supplied]",
                identity=supplied[sid].identity,
                classification=supplied[sid].classification,
            ),
            sector=taxonomy[sid].sector,
            industry=taxonomy[sid].industry,
        )
        for sid in ids
    )
    settings = model.lot_settings.model_copy(
        update={"marks": tuple(m.mark for m in model.bundle.marks if m.mark.security_id in ids)}
    )
    # A placeholder matrix is used only for schema/financial input inspection;
    # it never leaves this preparation boundary as candidate risk or a fallback.
    request = CandidateRequest(
        method=frozen.command.controls.method,
        max_candidates=frozen.command.controls.max_candidates,
        snapshot=frozen.snapshot,
        retained_snapshots=frozen.retained_snapshots,
        history_excluded_ids=tuple(sorted(model.sleeve.excluded_ids)),
        assets=assets,
        settings=settings,
        risk=RiskInput(
            security_ids=ids,
            benchmark_ids=retained_benchmark,
            benchmark_weights=tuple(m.benchmark_weight or 0.0 for m in frozen.coverage.members),
            annual_covariance=tuple(tuple(0.0 for _ in ids) for _ in ids),
            units="annualized-simple-return-covariance",
            annualization_sessions=model.bundle.profile.annualization_sessions,
            as_of=model.alignment.request.cutoff,
            max_age_days=model.bundle.profile.max_history_age_days,
            reference="Preparation only; fitting required before candidate search",
        ),
        limits=limits(frozen),
        buy_fee_per_security_order=frozen.command.controls.buy_fee_per_security_order,
        buy_premium_bps=frozen.command.controls.buy_premium_bps,
        sale_bounds=frozen.command.controls.sale_bounds,
        buy_bounds=frozen.command.controls.buy_bounds,
        max_states=frozen.command.controls.max_states,
    )
    from prosper.candidate_validation import input_issues

    return request, input_issues(request)


def calculate(
    frozen: FrozenCandidate, emit: Callable[[str, int], None] | None = None
) -> CandidateOutput:
    """Actual IDR kernel path; no supplied-covariance or returns-only alternative."""
    request, issues = prepare(frozen)
    if issues or request is None:
        return CandidateOutput(outcome="unavailable", issues=issues, risk=None, search=None)
    alignment = frozen.modeled.alignment
    assert alignment is not None
    innovation = assemble(alignment)
    assert innovation is not None
    inputs = tuple(
        volatility.series_from_innovations(
            innovation, j, purpose="research-window", expected_observations=1260
        )
        for j in range(len(request.assets))
    )
    fitted = covariance.fit_covariance(
        inputs, horizon=frozen.modeled.bundle.profile.horizon_sessions
    )
    risk = compact(fitted)
    if fitted.projection is None:
        return CandidateOutput(
            outcome="unavailable",
            issues=fitted.issues or ("risk_fit_unavailable",),
            risk=risk,
            search=None,
        )
    if callable(emit):
        emit("searching", 0)
    request = request.model_copy(
        update={
            "risk": request.risk.model_copy(
                update={
                    "annual_covariance": fitted.projection.annualized,
                    "reference": (
                        f"{fitted.version}/{fitted.identity_sha256}; "
                        f"horizon {fitted.horizon}; cutoff {fitted.cutoff}"
                    ),
                }
            )
        }
    )
    count = 0

    def progress() -> bool:
        nonlocal count
        if callable(emit) and count % 100 == 0:
            emit("searching", count)
        count += 1
        return False

    if request.method == "complete-cartesian-whole-share-reference":
        result = search(request, progress)
    else:
        from prosper.candidate_search import search as heuristic_search

        result = heuristic_search(request, progress)
    if result.outcome in ("invalid-input", "numerical-failure"):
        return CandidateOutput(
            outcome="unavailable",
            issues=result.baseline.blockers or (result.outcome,),
            risk=risk,
            search=result,
        )
    dated_weights = weights_at(
        frozen.modeled.benchmark,
        frozen.modeled.alignment,
        frozen.modeled.bundle.analysis_date,
        retained_ids=tuple(
            s
            for s in frozen.modeled.benchmark.security_ids
            if s not in frozen.modeled.sleeve.excluded_ids
        )
        if frozen.modeled.benchmark
        else (),
    )
    return CandidateOutput(
        outcome="checked",
        issues=(),
        risk=risk,
        search=result,
        warnings=CandidateOutput.model_fields["warnings"].default
        + ((dated_weights.warning,) if dated_weights.warning else ())
        + frozen.modeled.sleeve.warnings,
    )
