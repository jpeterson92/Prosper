"""Synthetic R1 scalar GARCH qualification, not investor/model acceptance.

Zero mean, all observations scored, fixed weighted seed and observed second
moment. All nine SLSQP starts retain their status; no penalty/fallback rescues a
domain failure. Fitted outputs require an independent projected-gradient check.
"""

import hashlib
import math
import platform
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray
from scipy import optimize

from prosper.innovations import SPECIFICATION_SHA256, InnovationResult, fingerprint

VERSION = "scalar-garch-r1-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CAP = 0.99998
MAX_ITERATIONS = 2000
MAX_CALLBACKS = 40000
FTOL = 1e-10
FEASIBILITY_ATOL = 1e-10
PROJECTED_GRADIENT_ATOL = 1e-5
STARTS = tuple((1 - s, g, s - g) for g in (0.01, 0.05, 0.10) for s in (0.90, 0.97, 0.99))
FloatArray = NDArray[np.float64]
Theta = tuple[float, float, float]


class VolatilityUnavailable(ValueError):
    """Located/domain refusal, never a repaired numerical result."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class VolatilityInput:
    x: tuple[float, ...]
    security_id: str
    sessions: tuple[str, ...]
    cutoff: str
    calendar: str
    timezone: str
    variant: str
    units: str
    innovation_identity_sha256: str
    purpose: str
    expected_observations: int
    fictional: bool = True


@dataclass(frozen=True)
class VariancePath:
    x: tuple[float, ...]
    parameters_u_g_b: Theta
    s2: float
    tau: int
    initialization: str
    seed: float
    omega: float
    variance: tuple[float, ...]
    standardized: tuple[float, ...]
    nll: tuple[float, ...]
    nll_sum: float
    sensitivities: tuple[Theta, ...]
    gradient: Theta


@dataclass(frozen=True)
class StartDiagnostic:
    index: int
    initial: Theta
    status: str
    optimizer_success: bool | None
    optimizer_status: int | None
    message: str
    objective_callbacks: int
    gradient_callbacks: int
    iterations: int
    parameters: Theta | None
    reported_objective: float | None
    objective: float | None
    feasibility_residual: float | None
    projected_gradient_residual: float | None
    boundary: tuple[str, ...]
    last_evaluated_parameters: Theta | None
    last_evaluated_objective: float | None


@dataclass(frozen=True)
class VolatilityResult:
    status: str
    issues: tuple[str, ...]
    version: str
    data: VolatilityInput
    horizon: int
    configuration_sha256: str
    input_sha256: str
    starts: tuple[StartDiagnostic, ...]
    selected_start: int | None
    path: VariancePath | None
    forecast: tuple[float, ...]
    objective_range: tuple[float, float] | None
    parameter_ranges: tuple[tuple[float, float], ...]
    output_sha256: str
    identity_sha256: str


def _sha(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def series_from_innovations(
    result: InnovationResult,
    column: int,
    *,
    purpose: Literal["primitive", "research-window"],
    expected_observations: int,
) -> VolatilityInput:
    if result.status != "ready" or result.profile.identity != "R1":
        raise VolatilityUnavailable("innovation_unavailable", result.status)
    if type(column) is not int or not 0 <= column < len(result.context.security_ids):
        raise VolatilityUnavailable("column", "explicit valid security column required")
    return VolatilityInput(
        tuple(row[column] for row in result.innovations),
        result.context.security_ids[column],
        result.context.sessions,
        result.context.cutoff,
        result.context.calendar,
        result.context.timezone,
        result.variant,
        result.units,
        result.identity_sha256,
        purpose,
        expected_observations,
        result.context.fictional,
    )


def _moments(x: tuple[float, ...]) -> tuple[tuple[float, ...], float, int, float]:
    if not x:
        raise VolatilityUnavailable("observations", "nonempty innovation history required")
    for j, value in enumerate(x):
        if not math.isfinite(value):
            raise VolatilityUnavailable("observations", f"observation {j}: nonfinite innovation")
    squares = tuple(v * v for v in x)
    try:
        s2 = math.fsum(squares) / len(x)
    except OverflowError as exc:
        raise VolatilityUnavailable("second_moment", "overflow") from exc
    if not math.isfinite(s2) or s2 <= 0:
        raise VolatilityUnavailable(
            "second_moment", "positive representable second moment required"
        )
    tau = math.isqrt(len(x)) + (math.isqrt(len(x)) ** 2 != len(x))
    weights = tuple(0.94**j for j in range(tau))
    seed = math.fsum(w * v for w, v in zip(weights, squares[:tau], strict=True)) / math.fsum(
        weights
    )
    if not math.isfinite(seed) or seed <= 0:
        raise VolatilityUnavailable(
            "seed", "R1 weighted initial variance is nonpositive/unrepresentable"
        )
    return squares, s2, tau, seed


def _theta(parameters: tuple[float, ...]) -> Theta:
    if len(parameters) != 3 or any(not math.isfinite(v) for v in parameters):
        raise VolatilityUnavailable("parameters", "three finite scaled parameters required")
    u, g, b = parameters
    if u <= 0 or min(g, b) < 0 or g + b >= 1:
        raise VolatilityUnavailable("parameters", "require u>0, g,b>=0, g+b<1")
    return u, g, b


def evaluate_fixed(
    x: tuple[float, ...],
    parameters: Theta,
    *,
    initial_variance: float | None = None,
) -> VariancePath:
    """Fixed-parameter primitive; an explicit seed is identified by the returned path.

    The fitter always uses R1's weighted seed. Custom states are only fixed-state
    reference primitives, not a selectable fitting configuration.
    """
    squares, s2, tau, seed = _moments(x)
    u, g, b = _theta(parameters)
    if initial_variance is not None:
        seed = initial_variance
    if not math.isfinite(seed) or seed <= 0:
        raise VolatilityUnavailable("seed", "positive finite initial variance required")
    omega = u * s2
    if not math.isfinite(omega) or omega <= 0:
        raise VolatilityUnavailable("omega", "positive representable omega required")
    variances, standardized, contributions = [], [], []
    sensitivities: list[Theta] = []
    derivatives: list[Theta] = []
    variance = seed
    dv: Theta = (0.0, 0.0, 0.0)
    for t, value in enumerate(x):
        if t:
            dv = (s2 + b * dv[0], squares[t - 1] + b * dv[1], variance + b * dv[2])
            variance = omega + g * squares[t - 1] + b * variance
        if not math.isfinite(variance) or variance <= 0:
            raise VolatilityUnavailable("variance", f"observation {t}: nonpositive/nonfinite state")
        ratio = squares[t] / variance
        nll = (math.log(2 * math.pi) + math.log(variance) + ratio) / 2
        gradient = tuple((1 - ratio) / 2 * (d / variance) for d in dv)
        z = value / math.sqrt(variance)
        if not all(math.isfinite(v) for v in (nll, z, *dv, *gradient)):
            raise VolatilityUnavailable("path", f"observation {t}: nonfinite score/sensitivity")
        variances.append(variance)
        standardized.append(z)
        contributions.append(nll)
        sensitivities.append(dv)
        derivatives.append((gradient[0], gradient[1], gradient[2]))
    total = math.fsum(contributions)
    grad: Theta = tuple(math.fsum(row[j] for row in derivatives) for j in range(3))  # type: ignore[assignment]
    if not all(math.isfinite(v) for v in (total, *grad)):
        raise VolatilityUnavailable("objective", "nonfinite summed objective/gradient")
    return VariancePath(
        x,
        (u, g, b),
        s2,
        tau,
        "R1-weighted" if initial_variance is None else "explicit-fixed-state",
        seed,
        omega,
        tuple(variances),
        tuple(standardized),
        tuple(contributions),
        total,
        tuple(sensitivities),
        grad,
    )


def project_parameters(theta: Theta) -> Theta:
    """Euclidean projection onto u's box times the capped nonnegative simplex."""
    if any(not math.isfinite(v) for v in theta):
        raise VolatilityUnavailable("projection", "finite three-coordinate vector required")
    u, a, b = theta
    u = min(10.0, max(1e-12, u))
    if max(a, 0) + max(b, 0) <= CAP:
        return u, max(a, 0), max(b, 0)
    if a - b >= CAP:
        return u, CAP, 0.0
    if b - a >= CAP:
        return u, 0.0, CAP
    return u, (a - b + CAP) / 2, (b - a + CAP) / 2


def projected_residual(theta: Theta, gradient: Theta, observations: int) -> float:
    if observations <= 0:
        raise VolatilityUnavailable("projection", "positive scored count required")
    projected = project_parameters(tuple(theta[j] - gradient[j] / observations for j in range(3)))  # type: ignore[arg-type]
    return max(abs(theta[j] - projected[j]) for j in range(3))


def forecast_variance(path: VariancePath, horizon: int) -> tuple[float, ...]:
    if type(horizon) is not int or horizon not in (1, 21):
        raise VolatilityUnavailable("horizon", "R1 qualification supports 1 or 21 sessions")
    _, g, b = path.parameters_u_g_b
    value = path.omega + g * path.x[-1] ** 2 + b * path.variance[-1]
    result = []
    for _ in range(horizon):
        if not math.isfinite(value) or value <= 0:
            raise VolatilityUnavailable("forecast", "positive finite variance required")
        result.append(value)
        value = path.omega + (g + b) * value
    return tuple(result)


def _validate_input(data: VolatilityInput) -> None:
    if data.fictional is not True or data.timezone != "UTC":
        raise VolatilityUnavailable(
            "synthetic_only", f"{data.security_id}: fictional UTC inputs only"
        )
    if (
        not data.security_id.strip()
        or not data.calendar
        or not _sha(data.innovation_identity_sha256)
    ):
        raise VolatilityUnavailable("identity", "security/calendar/innovation identity required")
    if data.variant not in ("idr", "returns-only") or data.units not in (
        "decimal",
        "percent-experiment",
    ):
        raise VolatilityUnavailable("variant_units", "explicit qualified variant/units required")
    if data.purpose not in ("primitive", "research-window"):
        raise VolatilityUnavailable(
            "purpose", "explicit primitive or research-window qualification required"
        )
    if type(data.expected_observations) is not int or data.expected_observations != len(data.x):
        raise VolatilityUnavailable(
            "history_length", "history differs from declared experiment length"
        )
    if data.purpose == "research-window" and len(data.x) != 1260:
        raise VolatilityUnavailable(
            "history_length", "R1 research window requires 1260 observations"
        )
    try:
        dates = tuple(date.fromisoformat(s) for s in data.sessions)
        if not dates or len(dates) != len(data.x) or tuple(sorted(set(dates))) != dates:
            raise ValueError("ordered unique complete sessions required")
        if any(d.isoformat() != s for d, s in zip(dates, data.sessions, strict=True)):
            raise ValueError("canonical sessions required")
        if data.cutoff != data.sessions[-1]:
            raise ValueError("cutoff must equal last declared session")
    except ValueError as exc:
        raise VolatilityUnavailable("sessions", str(exc)) from exc
    _moments(data.x)


def _boundary(theta: Theta) -> tuple[str, ...]:
    u, g, b = theta
    return tuple(
        name
        for name, residual in (
            ("u_lower", abs(u - 1e-12)),
            ("u_upper", abs(u - 10)),
            ("g_zero", abs(g)),
            ("b_zero", abs(b)),
            ("persistence_cap", abs(g + b - CAP)),
        )
        if residual <= FEASIBILITY_ATOL
    )


def _run_start(data: VolatilityInput, index: int, initial: Theta) -> StartDiagnostic:
    objective_calls = gradient_calls = iterations = 0
    last_theta: Theta | None = None
    cached: VariancePath | None = None

    def evaluate(values: FloatArray, *, jacobian: bool) -> VariancePath:
        nonlocal objective_calls, gradient_calls, last_theta, cached
        if objective_calls + gradient_calls >= MAX_CALLBACKS:
            raise VolatilityUnavailable("budget_exhausted", "combined callback cap reached")
        if jacobian:
            gradient_calls += 1
        else:
            objective_calls += 1
        theta = _theta(tuple(float(v) for v in values))
        if theta != last_theta:
            cached = evaluate_fixed(data.x, theta)
            last_theta = theta
        assert cached is not None
        return cached

    def objective(values: FloatArray) -> float:
        return evaluate(values, jacobian=False).nll_sum

    def jacobian(values: FloatArray) -> FloatArray:
        return np.asarray(evaluate(values, jacobian=True).gradient, dtype=np.float64)

    def callback(values: FloatArray) -> None:
        nonlocal iterations
        iterations += 1

    theta: Theta | None = None
    reported = score = feasible = residual = None
    success: bool | None = None
    optimizer_status: int | None = None
    boundary: tuple[str, ...] = ()
    try:
        raw: Any = optimize.minimize(
            objective,
            np.asarray(initial),
            jac=jacobian,
            method="SLSQP",
            bounds=((1e-12, 10.0), (0.0, 1.0), (0.0, 1.0)),
            constraints={
                "type": "ineq",
                "fun": lambda p: CAP - p[1] - p[2],
                "jac": lambda p: np.array([0.0, -1.0, -1.0]),
            },
            callback=callback,
            options={"maxiter": MAX_ITERATIONS, "ftol": FTOL},
        )
        success, optimizer_status = bool(raw.success), int(raw.status)
        message = str(raw.message)
        iterations = int(raw.nit)
        theta = _theta(tuple(float(v) for v in raw.x))
        raw_objective = float(raw.fun)
        if not math.isfinite(raw_objective):
            raise VolatilityUnavailable("nonfinite_optimizer", "reported objective is nonfinite")
        reported = raw_objective
        # Fresh path evaluation never trusts the optimizer's cached objective/Jacobian.
        path = evaluate_fixed(data.x, theta)
        score = path.nll_sum
        feasible = max(
            0.0, 1e-12 - theta[0], theta[0] - 10, -theta[1], -theta[2], theta[1] + theta[2] - CAP
        )
        residual = projected_residual(theta, path.gradient, len(data.x))
        boundary = _boundary(theta)
        if not success:
            status = "optimizer_failed"
        elif iterations > MAX_ITERATIONS:
            status = "iteration_budget_exceeded"
        elif abs(score - reported) > 1e-8 + 1e-8 * max(abs(score), abs(reported)):
            status = "objective_mismatch"
        elif feasible > FEASIBILITY_ATOL:
            status = "infeasible"
        elif residual > PROJECTED_GRADIENT_ATOL:
            status = "projected_gradient_failed"
        else:
            status = "eligible"
    except (VolatilityUnavailable, OverflowError, FloatingPointError) as exc:
        status = exc.code if isinstance(exc, VolatilityUnavailable) else "numerical_failure"
        message = str(exc)
    return StartDiagnostic(
        index,
        initial,
        status,
        success,
        optimizer_status,
        message,
        objective_calls,
        gradient_calls,
        iterations,
        theta,
        reported,
        score,
        feasible,
        residual,
        boundary,
        last_theta,
        cached.nll_sum if cached is not None else None,
    )


def fit_volatility(data: VolatilityInput, *, horizon: int = 21) -> VolatilityResult:
    """One synthetic scalar R1 fit; unavailable fits retain all nine start records."""
    _validate_input(data)
    if type(horizon) is not int or horizon not in (1, 21):
        raise VolatilityUnavailable("horizon", "R1 qualification supports 1 or 21 sessions")
    if np.__version__ != "2.5.4" or scipy.__version__ != "1.18.1":
        raise VolatilityUnavailable("runtime", "unqualified NumPy/SciPy versions")
    configuration = {
        "version": VERSION,
        "implementation": IMPLEMENTATION_SHA256,
        "specification": SPECIFICATION_SHA256,
        "profile": "R1",
        "starts": STARTS,
        "max_iterations": MAX_ITERATIONS,
        "max_callbacks": MAX_CALLBACKS,
        "ftol": FTOL,
        "feasibility_atol": FEASIBILITY_ATOL,
        "projected_gradient_atol": PROJECTED_GRADIENT_ATOL,
        "cap": CAP,
        "u_bounds": [1e-12, 10],
        "zero_mean": True,
        "score": "all sessions",
        "seed": "normalized .94**j first ceil(sqrt(T)) squared innovations",
        "runtime": [
            platform.python_version(),
            platform.system(),
            platform.machine(),
            np.__version__,
            scipy.__version__,
        ],
        "horizon": horizon,
    }
    config_hash, input_hash = fingerprint(configuration), fingerprint(asdict(data))
    starts = tuple(_run_start(data, j, theta) for j, theta in enumerate(STARTS))
    eligible = tuple(start for start in starts if start.status == "eligible")
    selected: int | None = None
    path: VariancePath | None = None
    forecasts: tuple[float, ...] = ()
    score_range: tuple[float, float] | None = None
    parameter_ranges: tuple[tuple[float, float], ...] = ()
    issues: tuple[str, ...] = ()
    if eligible:
        chosen = min(eligible, key=lambda s: (float(s.objective), s.index))  # type: ignore[arg-type]
        assert chosen.parameters is not None
        selected = chosen.index
        path = evaluate_fixed(data.x, chosen.parameters)
        try:
            forecasts = forecast_variance(path, horizon)
        except VolatilityUnavailable as exc:
            issues = (str(exc),)
            path, selected = None, None
        scores = tuple(float(s.objective) for s in eligible)  # type: ignore[arg-type]
        score_range = min(scores), max(scores)
        parameter_ranges = tuple(
            (
                min(s.parameters[j] for s in eligible if s.parameters is not None),
                max(s.parameters[j] for s in eligible if s.parameters is not None),
            )
            for j in range(3)
        )
    else:
        issues = ("no_eligible_start",)
    status = "qualified-synthetic-fit" if path is not None else "unavailable"
    output_hash = fingerprint(
        {
            "status": status,
            "issues": issues,
            "starts": [asdict(s) for s in starts],
            "selected": selected,
            "path": asdict(path) if path else None,
            "forecast": forecasts,
            "objective_range": score_range,
            "parameter_ranges": parameter_ranges,
        }
    )
    return VolatilityResult(
        status,
        issues,
        VERSION,
        data,
        horizon,
        config_hash,
        input_hash,
        starts,
        selected,
        path,
        forecasts,
        score_range,
        parameter_ranges,
        output_hash,
        fingerprint([config_hash, input_hash, output_hash]),
    )
