"""R1 covariance composition and normalized-correlation projection.

Frozen scalar/target/DCC identities are consumed without refitting or repairing
failed components. These are approximate proxy-model forecasts, not calibrated
actual-return tracking error or investor/model acceptance.
"""

import hashlib
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import scipy  # type: ignore[import-untyped]
from scipy import linalg

from prosper import dcc, volatility
from prosper.innovations import SPECIFICATION_SHA256, fingerprint
from prosper.shrinkage import TargetUnavailable, analytical_target

VERSION = "covariance-normalized-blend-r1-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
APPROXIMATION = (
    "P22 normalized-correlation blend; fixed weights/zero mean/zero cross-day covariance"
)
Matrix = dcc.Matrix


class CovarianceUnavailable(ValueError):
    """Located refusal; all failed upstream components remain with the caller/result."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class Projection:
    horizon: int
    approximation: str
    units: str
    annualization: int
    next_correlation: Matrix
    one_session: Matrix
    last_session: Matrix
    cumulative: Matrix
    average_daily: Matrix
    annualized: Matrix
    input_sha256: str
    identity_sha256: str


@dataclass(frozen=True)
class CovarianceResult:
    status: str
    issues: tuple[str, ...]
    version: str
    scalars: tuple[volatility.VolatilityResult, ...]
    dcc_fit: dcc.DCCResult | None
    horizon: int
    security_ids: tuple[str, ...]
    cutoff: str | None
    terminal_q: Matrix | None
    next_q: Matrix | None
    projection: Projection | None
    configuration_sha256: str
    input_sha256: str
    output_sha256: str
    identity_sha256: str


def _matrix(values: dcc.FloatArray) -> Matrix:
    return tuple(tuple(float(v) for v in row) for row in values)


def _spd(values: dcc.FloatArray, label: str) -> None:
    if (
        values.ndim != 2
        or values.shape[0] != values.shape[1]
        or values.shape[0] < 2
        or not np.isfinite(values).all()
        or not np.allclose(values, values.T, rtol=0, atol=1e-10)
    ):
        raise CovarianceUnavailable("matrix", f"{label}: finite symmetric square matrix required")
    eigenvalues = linalg.eigvalsh(values)
    if eigenvalues[0] <= 1e-12 * eigenvalues[-1]:
        raise CovarianceUnavailable("matrix", f"{label}: R1 positive-definite threshold failed")


def _horizon(horizon: int) -> None:
    if type(horizon) is not int or horizon not in (1, 21):
        raise CovarianceUnavailable("horizon", "R1 supports one or 21 sessions")


def _project_fixed(
    target: Matrix,
    next_q: Matrix,
    variance_one: tuple[float, ...],
    omega: tuple[float, ...],
    persistence: tuple[float, ...],
    dcc_persistence: float,
    *,
    horizon: int,
    source_units: str = "decimal",
) -> Projection:
    """Stipulated next-session Q/variance reference boundary; no fitted-model claim.

    Keep only current variance/correlation/covariance and the running sum. H1 is
    the T+1 forecast, not the last in-sample covariance. q=0 still uses R1 at h=1.
    """
    _horizon(horizon)
    if np.__version__ != "2.5.4" or scipy.__version__ != "1.18.1":
        raise CovarianceUnavailable("runtime", "unqualified NumPy/SciPy versions")
    c, q1 = np.asarray(target, dtype=float), np.asarray(next_q, dtype=float)
    _spd(c, "target")
    _spd(q1, "next Q")
    n = len(c)
    if c.shape != q1.shape or not np.allclose(np.diag(c), 1, rtol=0, atol=1e-10):
        raise CovarianceUnavailable("matrix", "matching target correlation and next Q required")
    v, w, s = (np.asarray(a, dtype=float) for a in (variance_one, omega, persistence))
    if (
        any(a.shape != (n,) for a in (v, w, s))
        or not all(np.isfinite(a).all() for a in (v, w, s))
        or np.any(v <= 0)
        or np.any(w <= 0)
        or np.any(s < 0)
        or np.any(s > volatility.CAP + volatility.FEASIBILITY_ATOL)
        or not math.isfinite(dcc_persistence)
        or not 0 <= dcc_persistence <= dcc.CAP + dcc.FEASIBILITY_ATOL
    ):
        raise CovarianceUnavailable(
            "parameters", "positive variance/omega and R1 persistence required"
        )
    if source_units not in ("decimal", "percent-experiment"):
        raise CovarianceUnavailable("units", "explicit source-return units required")
    inputs = fingerprint([target, next_q, variance_one, omega, persistence, dcc_persistence])
    sd = np.sqrt(np.diag(q1))
    r1 = q1 / sd[:, None] / sd[None, :]
    total = np.zeros_like(c)
    first = None
    power = 1.0
    for _ in range(horizon):
        r = c + power * (r1 - c)
        d = np.sqrt(v)
        h = d[:, None] * r * d[None, :]
        _spd(h, "forecast covariance")
        if first is None:
            first = _matrix(h)
        total += h
        v = w + s * v
        power *= dcc_persistence
    assert first is not None
    average = total / horizon
    annual = average * 252
    if not all(np.isfinite(a).all() for a in (total, average, annual)):
        raise CovarianceUnavailable("numeric_scale", "unrepresentable covariance aggregates")
    payload = {
        "horizon": horizon,
        "approximation": APPROXIMATION,
        "units": f"{source_units}-return-squared",
        "annualization": 252,
        "next_correlation": _matrix(r1),
        "one_session": first,
        "last_session": _matrix(h),
        "cumulative": _matrix(total),
        "average_daily": _matrix(average),
        "annualized": _matrix(annual),
        "input_sha256": inputs,
    }
    return Projection(
        horizon,
        APPROXIMATION,
        f"{source_units}-return-squared",
        252,
        _matrix(r1),
        first,
        _matrix(h),
        _matrix(total),
        _matrix(average),
        _matrix(annual),
        inputs,
        fingerprint([VERSION, IMPLEMENTATION_SHA256, SPECIFICATION_SHA256, payload]),
    )


def project_fixed(
    target: Matrix,
    next_q: Matrix,
    variance_one: tuple[float, ...],
    omega: tuple[float, ...],
    persistence: tuple[float, ...],
    dcc_persistence: float,
    *,
    horizon: int,
    source_units: str = "decimal",
) -> Projection:
    """Project identified stipulated T+1 states, with explicit numerical refusals."""
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            return _project_fixed(
                target,
                next_q,
                variance_one,
                omega,
                persistence,
                dcc_persistence,
                horizon=horizon,
                source_units=source_units,
            )
    except CovarianceUnavailable:
        raise
    except (ValueError, OverflowError, FloatingPointError, linalg.LinAlgError) as exc:
        raise CovarianceUnavailable("numerical_failure", str(exc)) from exc


def _scalar(result: volatility.VolatilityResult) -> volatility.VariancePath:
    if result.status != "fit-complete" or result.issues or result.path is None:
        raise CovarianceUnavailable(
            "scalar_unavailable", f"{result.data.security_id}: {result.issues}"
        )
    if result.version != volatility.VERSION or result.input_sha256 != fingerprint(
        asdict(result.data)
    ):
        raise CovarianceUnavailable("scalar_identity", result.data.security_id)
    output = fingerprint(
        {
            "status": result.status,
            "issues": result.issues,
            "starts": [asdict(s) for s in result.starts],
            "selected": result.selected_start,
            "path": asdict(result.path),
            "forecast": result.forecast,
            "objective_range": result.objective_range,
            "parameter_ranges": result.parameter_ranges,
        }
    )
    if output != result.output_sha256 or result.identity_sha256 != fingerprint(
        [result.configuration_sha256, result.input_sha256, output]
    ):
        raise CovarianceUnavailable("scalar_identity", result.data.security_id)
    volatility._validate_input(result.data)
    if type(result.data.x) is not tuple or type(result.data.sessions) is not tuple:
        raise CovarianceUnavailable("scalar_identity", "immutable source/session tuples required")
    if result.configuration_sha256 != _configuration(scalar_horizon=result.horizon):
        raise CovarianceUnavailable("scalar_configuration", result.data.security_id)
    eligible = [s for s in result.starts if s.status == "eligible"]
    if (
        tuple(s.initial for s in result.starts) != volatility.STARTS
        or tuple(s.index for s in result.starts) != tuple(range(len(volatility.STARTS)))
        or not eligible
    ):
        raise CovarianceUnavailable("scalar_eligibility", result.data.security_id)
    for start in eligible:
        _eligible(start)
    chosen = min(eligible, key=lambda s: (float(s.objective), s.index))  # type: ignore[arg-type]
    if chosen.index != result.selected_start or chosen.parameters != result.path.parameters_u_g_b:
        raise CovarianceUnavailable("scalar_eligibility", result.data.security_id)
    replay = volatility.evaluate_fixed(result.data.x, result.path.parameters_u_g_b)
    if chosen.objective is None or not math.isclose(
        chosen.objective, replay.nll_sum, rel_tol=1e-8, abs_tol=1e-8
    ):
        raise CovarianceUnavailable("scalar_eligibility", "selected score mismatch")
    u, g, b = replay.parameters_u_g_b
    if max(0, 1e-12 - u, u - 10, -g, -b, g + b - volatility.CAP) > volatility.FEASIBILITY_ATOL:
        raise CovarianceUnavailable("scalar_eligibility", result.data.security_id)
    if (
        replay != result.path
        or volatility.forecast_variance(replay, result.horizon) != result.forecast
    ):
        raise CovarianceUnavailable("scalar_replay", result.data.security_id)
    if (
        volatility.projected_residual(replay.parameters_u_g_b, replay.gradient, len(replay.x))
        > 1e-5
    ):
        raise CovarianceUnavailable("scalar_eligibility", result.data.security_id)
    return replay


def _eligible(start: volatility.StartDiagnostic | dcc.StartDiagnostic) -> None:
    if (
        start.optimizer_success is not True
        or start.objective is None
        or not math.isfinite(start.objective)
        or start.parameters is None
        or start.iterations > 2000
        or start.objective_callbacks + start.gradient_callbacks > 40000
    ):
        raise CovarianceUnavailable("eligibility", "incomplete/failed start cannot be eligible")


def _configuration(*, scalar_horizon: int | None = None, correction: float = 0) -> str:
    """Bind consumed configurations to the loaded R1 implementations and runtime."""
    scalar = scalar_horizon is not None
    module = volatility if scalar else dcc
    config: dict[str, object] = {
        "version": module.VERSION,
        "implementation": module.IMPLEMENTATION_SHA256,
        "specification": SPECIFICATION_SHA256,
        "profile": "R1",
        "starts": module.STARTS,
        "max_iterations": module.MAX_ITERATIONS,
        "max_callbacks": module.MAX_CALLBACKS,
        "ftol": module.FTOL,
        "feasibility_atol": module.FEASIBILITY_ATOL,
        "projected_gradient_atol": module.PROJECTED_GRADIENT_ATOL,
        "cap": module.CAP,
        "seed": (
            "normalized .94**j first ceil(sqrt(T)) squared innovations"
            if scalar
            else "Q[1]=Ctarget; zero sensitivities"
        ),
        "score": "all sessions" if scalar else "all sessions; adjacent pair mean/time sum",
        "runtime": [
            platform.python_version(),
            platform.system(),
            platform.machine(),
            np.__version__,
            scipy.__version__,
        ],
    }
    if scalar:
        config.update(u_bounds=[1e-12, 10], zero_mean=True, horizon=scalar_horizon)
    else:
        config["target_symmetry_correction"] = correction
    return fingerprint(config)


def prepare_dcc(scalars: tuple[volatility.VolatilityResult, ...]) -> dcc.DCCInput:
    """Assemble complete ordered Z and its analytical target from frozen scalar fits."""
    if type(scalars) is not tuple or len(scalars) < 2:
        raise CovarianceUnavailable("universe", "at least two immutable scalar results required")
    paths = tuple(_scalar(s) for s in scalars)
    first = scalars[0].data
    for scalar in scalars:
        data = scalar.data
        if any(
            getattr(data, k) != getattr(first, k)
            for k in (
                "sessions",
                "cutoff",
                "calendar",
                "timezone",
                "variant",
                "units",
                "purpose",
                "expected_observations",
            )
        ):
            raise CovarianceUnavailable(
                "component_context", f"{data.security_id}: common context required"
            )
    context = dcc.DCCContext(
        tuple(s.data.security_id for s in scalars),
        first.sessions,
        first.cutoff,
        first.calendar,
        first.timezone,
        first.variant,
        first.units,
        tuple(s.identity_sha256 for s in scalars),
        first.purpose,
        first.expected_observations,
    )
    z = tuple(tuple(p.standardized[t] for p in paths) for t in range(len(first.x)))
    target = analytical_target(
        np.asarray(z),
        context=dcc.target_context(context),
        preprocessing="none",
        degrees_of_freedom=0,
    )
    return dcc.input_from_target(z, context, target)


def replay_full(z: Matrix, target: Matrix, parameters: dcc.Theta) -> tuple[Matrix, Matrix]:
    """Stream full last-scored Q and T+1 Q, independently checked against pair replay."""
    pair = dcc.evaluate_fixed(z, target, parameters)
    c = np.asarray(target, dtype=float)
    # Match the fitter's explicitly recorded permitted symmetry correction.
    c = (c + c.T) / 2
    q = c.copy()
    a, b = parameters
    for row in z[:-1]:
        v = np.asarray(row)
        q = (1 - a - b) * c + a * np.outer(v, v) + b * q
    _spd(q, "terminal Q")
    for (i, j), expected in zip(pair.pairs, pair.terminal_q, strict=True):
        if not np.allclose((q[i, i], q[j, j], q[i, j]), expected, rtol=1e-8, atol=1e-10):
            raise CovarianceUnavailable("pair_replay", "full Q differs from fitting pair states")
    last = np.asarray(z[-1])
    next_q = (1 - a - b) * c + a * np.outer(last, last) + b * q
    _spd(next_q, "next Q")
    return _matrix(q), _matrix(next_q)


def _dcc_result(fit: dcc.DCCResult, data: dcc.DCCInput) -> dcc.PairEvaluation:
    if fit.status != "fit-complete" or fit.issues or fit.evaluation is None:
        raise CovarianceUnavailable("dcc_unavailable", str(fit.issues))
    if (
        fit.version != dcc.VERSION
        or fit.data != data
        or fit.input_sha256 != fingerprint(asdict(data))
    ):
        raise CovarianceUnavailable(
            "dcc_identity", "fit must match every composed input/target identity"
        )
    output = fingerprint(
        {
            "status": fit.status,
            "issues": fit.issues,
            "starts": [asdict(s) for s in fit.starts],
            "selected": fit.selected_start,
            "evaluation": asdict(fit.evaluation),
            "objective_range": fit.objective_range,
            "parameter_ranges": fit.parameter_ranges,
        }
    )
    if output != fit.output_sha256 or fit.identity_sha256 != fingerprint(
        [fit.configuration_sha256, fit.input_sha256, output]
    ):
        raise CovarianceUnavailable("dcc_identity", "fit output hash differs")
    eligible = [s for s in fit.starts if s.status == "eligible"]
    if (
        tuple(s.initial for s in fit.starts) != dcc.STARTS
        or tuple(s.index for s in fit.starts) != tuple(range(len(dcc.STARTS)))
        or not eligible
    ):
        raise CovarianceUnavailable("dcc_eligibility", "all starts and eligible selection required")
    for start in eligible:
        _eligible(start)
    chosen = min(eligible, key=lambda s: (float(s.objective), s.index))  # type: ignore[arg-type]
    if chosen.index != fit.selected_start or chosen.parameters != fit.evaluation.parameters:
        raise CovarianceUnavailable("dcc_eligibility", "selection mismatch")
    replay = dcc.evaluate_fixed(data.z, data.target, fit.evaluation.parameters)
    if chosen.objective is None or not math.isclose(
        chosen.objective, replay.nll_sum, rel_tol=1e-8, abs_tol=1e-8
    ):
        raise CovarianceUnavailable("dcc_eligibility", "selected score mismatch")
    if fit.configuration_sha256 != _configuration(correction=replay.target_symmetry_correction):
        raise CovarianceUnavailable("dcc_configuration", "loaded source/runtime/profile differs")
    if (
        max(0, -replay.parameters[0], -replay.parameters[1], sum(replay.parameters) - dcc.CAP)
        > dcc.FEASIBILITY_ATOL
    ):
        raise CovarianceUnavailable("dcc_eligibility", "infeasible selected parameters")
    if (
        replay != fit.evaluation
        or dcc.projected_residual(replay.parameters, replay.gradient, len(data.z)) > 1e-5
    ):
        raise CovarianceUnavailable("dcc_replay", "selected fit no longer eligible/matching")
    return replay


def compose_covariance(
    scalars: tuple[volatility.VolatilityResult, ...],
    fit: dcc.DCCResult | None,
    *,
    horizon: int = 21,
) -> CovarianceResult:
    """Fail closed with complete components retained; no missing-security deletion."""
    _horizon(horizon)
    issues: tuple[str, ...] = ()
    terminal = next_q = None
    projection = None
    try:
        data = prepare_dcc(scalars)
        if fit is None:
            raise CovarianceUnavailable("dcc_unavailable", "no fit supplied")
        evaluated = _dcc_result(fit, data)
        terminal, next_q = replay_full(data.z, data.target, evaluated.parameters)
        paths = tuple(s.path for s in scalars)
        assert all(p is not None for p in paths)
        valid = tuple(p for p in paths if p is not None)
        projection = project_fixed(
            data.target,
            next_q,
            tuple(volatility.forecast_variance(p, 1)[0] for p in valid),
            tuple(p.omega for p in valid),
            tuple(p.parameters_u_g_b[1] + p.parameters_u_g_b[2] for p in valid),
            sum(evaluated.parameters),
            horizon=horizon,
            source_units=data.context.source_units,
        )
    except (
        CovarianceUnavailable,
        volatility.VolatilityUnavailable,
        dcc.DCCUnavailable,
        TargetUnavailable,
    ) as exc:
        issues = (str(exc),)
        terminal = next_q = None
    status = "forecast-complete" if projection is not None else "unavailable"
    configuration = fingerprint(
        [
            VERSION,
            IMPLEMENTATION_SHA256,
            SPECIFICATION_SHA256,
            APPROXIMATION,
            horizon,
            252,
            volatility.IMPLEMENTATION_SHA256,
            dcc.IMPLEMENTATION_SHA256,
        ]
    )
    # Hash actual supplied evidence as well as its claimed identities, including
    # unavailable/mismatched inputs. A stale child hash must not alias failures.
    inputs = fingerprint([[asdict(s) for s in scalars], asdict(fit) if fit else None])
    output = fingerprint(
        [status, issues, terminal, next_q, asdict(projection) if projection else None]
    )
    return CovarianceResult(
        status,
        issues,
        VERSION,
        scalars,
        fit,
        horizon,
        tuple(s.data.security_id for s in scalars),
        scalars[0].data.cutoff if scalars else None,
        terminal,
        next_q,
        projection,
        configuration,
        inputs,
        output,
        fingerprint([configuration, inputs, output]),
    )


def fit_covariance(
    inputs: tuple[volatility.VolatilityInput, ...], *, horizon: int = 21
) -> CovarianceResult:
    """Covariance orchestration; each fitter retains every start diagnostic."""
    _horizon(horizon)
    scalars = tuple(volatility.fit_volatility(data, horizon=horizon) for data in inputs)
    try:
        fit = dcc.fit_dcc(prepare_dcc(scalars))
    except (
        CovarianceUnavailable,
        volatility.VolatilityUnavailable,
        dcc.DCCUnavailable,
        TargetUnavailable,
    ):
        fit = None
    return compose_covariance(scalars, fit, horizon=horizon)
