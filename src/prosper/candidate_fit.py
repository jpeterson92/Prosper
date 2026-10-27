"""Compact historical fit diagnostics; numerical paths stay transient in the worker.

Original inputs belong to the saved modeled-input run. The only saved covariance
is the search request's annual matrix; its digest links the fit summary to it.
Reading these records never replays a fit or regenerates financial results.
"""

import json
from dataclasses import asdict
from typing import Literal, Self

from pydantic import Field, model_validator

from prosper import covariance, dcc, volatility
from prosper.advisory_records import Digest, Record
from prosper.innovations import fingerprint
from prosper.record_types import DateText, Identifier, Text


class StartDiagnostic(Record):
    index: int
    initial: tuple[float, ...]
    status: Text
    optimizer_success: bool | None
    optimizer_status: int | None
    message: str
    objective_callbacks: int
    gradient_callbacks: int
    iterations: int
    parameters: tuple[float, ...] | None
    reported_objective: float | None
    objective: float | None
    feasibility_residual: float | None
    projected_gradient_residual: float | None
    boundary: tuple[str, ...]
    last_evaluated_parameters: tuple[float, ...] | None
    last_evaluated_objective: float | None


class FitDiagnostic(Record):
    status: Text
    issues: tuple[Text, ...]
    version: Text
    configuration_sha256: Digest
    input_sha256: Digest
    output_sha256: Digest
    identity_sha256: Digest
    starts: tuple[StartDiagnostic, ...] = Field(max_length=12)
    selected_start: int | None
    objective_range: tuple[float, float] | None
    parameter_ranges: tuple[tuple[float, float], ...]

    @model_validator(mode="after")
    def selection(self) -> Self:
        if tuple(s.index for s in self.starts) != tuple(range(len(self.starts))):
            raise ValueError("fit_start_order_invalid")
        if self.selected_start is not None and (
            not 0 <= self.selected_start < len(self.starts)
            or self.starts[self.selected_start].status != "eligible"
        ):
            raise ValueError("fit_selection_invalid")
        return self


class ScalarDiagnostic(FitDiagnostic):
    security_id: Identifier
    innovation_identity_sha256: Digest
    parameters: tuple[float, float, float] | None
    second_moment: float | None
    seed: float | None
    omega: float | None
    terminal_variance: float | None
    forecast: tuple[float, ...]


class CorrelationDiagnostic(FitDiagnostic):
    target_kind: Text
    target_input_sha256: Digest
    target_identity_sha256: Digest
    parameters: tuple[float, float] | None
    objective: float | None
    gradient: tuple[float, float] | None
    target_symmetry_correction: float | None


class ProjectionDiagnostic(Record):
    horizon: int
    approximation: Text
    units: Text
    annualization: int
    input_sha256: Digest
    identity_sha256: Digest
    annual_covariance_sha256: Digest


class CandidateFit(Record):
    kind: Literal["candidate-fit-v1"] = "candidate-fit-v1"
    status: Text
    issues: tuple[Text, ...]
    version: Text
    security_ids: tuple[Identifier, ...] = Field(min_length=2, max_length=500)
    cutoff: DateText
    sessions: int
    calendar: Text
    timezone: Text
    variant: Text
    source_units: Text
    purpose: Text
    horizon: int
    configuration_sha256: Digest
    input_sha256: Digest
    output_sha256: Digest
    identity_sha256: Digest
    scalars: tuple[ScalarDiagnostic, ...] = Field(min_length=2, max_length=500)
    dcc_fit: CorrelationDiagnostic | None
    projection: ProjectionDiagnostic | None

    @model_validator(mode="after")
    def order(self) -> Self:
        if tuple(s.security_id for s in self.scalars) != self.security_ids or len(
            set(self.security_ids)
        ) != len(self.security_ids):
            raise ValueError("fit_scalar_order_invalid")
        if self.projection is not None and (
            self.issues
            or self.dcc_fit is None
            or self.dcc_fit.selected_start is None
            or any(s.selected_start is None or s.issues for s in self.scalars)
            or self.projection.horizon != self.horizon
        ):
            raise ValueError("fit_projection_invalid")
        return self


def _diagnostic(fit: volatility.VolatilityResult | dcc.DCCResult) -> dict[str, object]:
    return {
        k: [asdict(s) for s in fit.starts] if k == "starts" else getattr(fit, k)
        for k in FitDiagnostic.model_fields
    }


def compact(fit: covariance.CovarianceResult) -> CandidateFit:
    """Copy decision-relevant diagnostics once, without asdict on numerical paths."""
    first = fit.scalars[0].data
    scalars = []
    for scalar in fit.scalars:
        path = scalar.path
        scalars.append(
            {
                **_diagnostic(scalar),
                "security_id": scalar.data.security_id,
                "innovation_identity_sha256": scalar.data.innovation_identity_sha256,
                "parameters": path.parameters_u_g_b if path else None,
                "second_moment": path.s2 if path else None,
                "seed": path.seed if path else None,
                "omega": path.omega if path else None,
                "terminal_variance": path.variance[-1] if path else None,
                "forecast": scalar.forecast,
            }
        )
    correlation = None
    if fit.dcc_fit is not None:
        data, evaluation = fit.dcc_fit.data, fit.dcc_fit.evaluation
        correlation = {
            **_diagnostic(fit.dcc_fit),
            "target_kind": data.target_kind,
            "target_input_sha256": data.target_input_sha256,
            "target_identity_sha256": data.target_identity_sha256,
            "parameters": evaluation.parameters if evaluation else None,
            "objective": evaluation.nll_sum if evaluation else None,
            "gradient": evaluation.gradient if evaluation else None,
            "target_symmetry_correction": evaluation.target_symmetry_correction
            if evaluation
            else None,
        }
    projection = None
    if fit.projection is not None:
        projection = {
            k: fingerprint(fit.projection.annualized)
            if k == "annual_covariance_sha256"
            else getattr(fit.projection, k)
            for k in ProjectionDiagnostic.model_fields
        }
    return CandidateFit.model_validate_json(
        json.dumps(
            {
                **{
                    k: getattr(fit, k)
                    for k in (
                        "status",
                        "issues",
                        "version",
                        "security_ids",
                        "cutoff",
                        "horizon",
                        "configuration_sha256",
                        "input_sha256",
                        "output_sha256",
                        "identity_sha256",
                    )
                },
                "sessions": len(first.sessions),
                "calendar": first.calendar,
                "timezone": first.timezone,
                "variant": first.variant,
                "source_units": first.units,
                "purpose": first.purpose,
                "scalars": scalars,
                "dcc_fit": correlation,
                "projection": projection,
            },
            allow_nan=False,
        )
    )
