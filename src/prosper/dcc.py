"""R1 original-DCC composite fitting; no covariance forecast or model acceptance.

Adjacent bivariate states/sensitivities stream in bounded 64-session blocks. Fixed Z/target and
all start outcomes survive in immutable results for subsequent full-Q replay.
"""

import hashlib
import math
import platform
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray
from scipy import linalg, optimize, signal

from prosper.innovations import SPECIFICATION_SHA256, fingerprint
from prosper.shrinkage import IMPLEMENTATION_SHA256 as TARGET_IMPLEMENTATION_SHA256
from prosper.shrinkage import VERSION as TARGET_VERSION
from prosper.shrinkage import TargetContext, TargetResult

VERSION = "dcc-pairs-r1-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CAP = 0.99998
MAX_ITERATIONS = 2000
MAX_CALLBACKS = 40000
FTOL = 1e-10
FEASIBILITY_ATOL = 1e-10
PROJECTED_GRADIENT_ATOL = 1e-5
STARTS = tuple((a, s - a) for a in (0.01, 0.03, 0.05, 0.10) for s in (0.99, 0.97, 0.95))
Theta = tuple[float, float]
Triple = tuple[float, float, float]
Matrix = tuple[tuple[float, ...], ...]
FloatArray = NDArray[np.float64]


class DCCUnavailable(ValueError):
    """Located refusal; no penalty, repaired matrix or fallback model."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class DCCContext:
    security_ids: tuple[str, ...]
    sessions: tuple[str, ...]
    cutoff: str
    calendar: str
    timezone: str
    variant: str
    source_units: str
    upstream_sha256: tuple[str, ...]
    purpose: str
    expected_observations: int


@dataclass(frozen=True)
class DCCInput:
    z: Matrix
    target: Matrix
    context: DCCContext
    target_context: TargetContext
    target_input_sha256: str
    target_identity_sha256: str
    target_kind: str


@dataclass(frozen=True)
class PairEvaluation:
    parameters: Theta
    pairs: tuple[tuple[int, int], ...]
    nll: tuple[float, ...]
    nll_sum: float
    gradient: Theta
    # Each triple is (Qii, Qjj, Qij) at the LAST SCORED session, not a forecast.
    terminal_q: tuple[Triple, ...]
    terminal_alpha: tuple[Triple, ...]
    terminal_beta: tuple[Triple, ...]
    target_symmetry_correction: float


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
class DCCResult:
    status: str
    issues: tuple[str, ...]
    version: str
    data: DCCInput
    configuration_sha256: str
    input_sha256: str
    starts: tuple[StartDiagnostic, ...]
    selected_start: int | None
    evaluation: PairEvaluation | None
    objective_range: tuple[float, float] | None
    parameter_ranges: tuple[tuple[float, float], ...]
    output_sha256: str
    identity_sha256: str


def observation_hash(z: Matrix) -> str:
    """Same original float64 row-major observation identity as the target component."""
    return hashlib.sha256(np.asarray(z, dtype="<f8", order="C").tobytes()).hexdigest()


def target_context(context: DCCContext) -> TargetContext:
    return TargetContext(
        context.security_ids,
        context.cutoff,
        context.calendar,
        f"standardized-r1/{context.variant}/{context.source_units}",
        context.upstream_sha256,
    )


def input_from_target(z: Matrix, context: DCCContext, target: TargetResult) -> DCCInput:
    """Snapshot a qualified analytical target; callers still supply input provenance.

    This consumes an existing result, without fitting scalars or constructing a
    target. The sibling owns that orchestration and matching component lifecycle.
    """
    if (
        target.version != TARGET_VERSION
        or target.implementation_sha256 != TARGET_IMPLEMENTATION_SHA256
        or target.specification_sha256 != SPECIFICATION_SHA256
        or target.preprocessing != "none"
        or target.degrees_of_freedom != 0
        or target.observations != len(z)
        or target.effective_observations != len(z)
    ):
        raise DCCUnavailable("target_profile", "matching analytical R1 k=0 target required")
    data = DCCInput(
        z,
        tuple(tuple(float(v) for v in row) for row in target.correlation),
        context,
        target.context,
        target.input_sha256,
        target.model_sha256,
        "analytical-r1",
    )
    _validate_input(data)
    return data


def fixed_input(z: Matrix, target: Matrix, context: DCCContext) -> DCCInput:
    """Explicit stipulated target for primitive reference experiments only."""
    _arrays(z, target)
    data = DCCInput(
        z,
        target,
        context,
        target_context(context),
        observation_hash(z),
        fingerprint(["stipulated-fixed-target", target]),
        "fixed-primitive",
    )
    _validate_input(data)
    return data


def _arrays(z: Matrix, target: Matrix) -> tuple[Matrix, float]:
    if (
        type(z) is not tuple
        or not z
        or type(z[0]) is not tuple
        or len(z[0]) < 2
        or any(type(row) is not tuple or len(row) != len(z[0]) for row in z)
        or type(target) is not tuple
        or len(target) != len(z[0])
        or any(type(row) is not tuple or len(row) != len(z[0]) for row in target)
    ):
        raise DCCUnavailable("shape", "immutable complete Z[T,N], C[N,N], N>=2 required")
    if any(
        not isinstance(v, (int, float)) or not math.isfinite(v)
        for row in (*z, *target)
        for v in row
    ):
        raise DCCUnavailable("nonfinite", "finite numeric observations/target required")
    n = len(z[0])
    for j in range(n):
        try:
            moment = math.fsum(row[j] * row[j] for row in z) / len(z)
        except OverflowError as exc:
            raise DCCUnavailable("second_moment", f"column {j}: overflow") from exc
        if not math.isfinite(moment) or moment <= 0:
            raise DCCUnavailable(
                "second_moment", f"column {j}: positive representable moment required"
            )
    c = np.asarray(target, dtype=np.float64)
    scale = float(np.max(np.abs(c)))
    if scale == 0 or np.any(np.abs(np.diag(c) - 1) > 1e-10):
        raise DCCUnavailable("target_diagonal", "correlation target must have unit diagonal")
    correction = float(np.max(np.abs(c - c.T))) / scale
    if correction > 1e-10:
        raise DCCUnavailable("target_asymmetry", "target exceeds R1 symmetry tolerance")
    c = (c + c.T) / 2
    try:
        eigenvalues = linalg.eigvalsh(c, check_finite=True)
    except linalg.LinAlgError as exc:
        raise DCCUnavailable("target_not_spd", "target eigensystem failed") from exc
    if eigenvalues[-1] <= 0 or eigenvalues[0] <= 1e-12 * eigenvalues[-1]:
        raise DCCUnavailable("target_not_spd", "target fails R1 relative SPD threshold")
    return tuple(tuple(float(v) for v in row) for row in c), correction


def _sha(value: str) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _validate_input(data: DCCInput) -> tuple[Matrix, float]:
    c, correction = _arrays(data.z, data.target)
    context = data.context
    if context.timezone != "UTC":
        raise DCCUnavailable("timezone", "UTC session dates required")
    if (
        type(context.security_ids) is not tuple
        or len(context.security_ids) != len(data.z[0])
        or any(not isinstance(v, str) or not v.strip() for v in context.security_ids)
        or len(set(context.security_ids)) != len(context.security_ids)
        or not isinstance(context.calendar, str)
        or not context.calendar.strip()
        or type(context.upstream_sha256) is not tuple
        or len(context.upstream_sha256) != len(context.security_ids)
        or not all(_sha(v) for v in context.upstream_sha256)
        or not _sha(data.target_identity_sha256)
    ):
        raise DCCUnavailable(
            "identity", "ordered unique securities/calendar/upstream identities required"
        )
    if context.variant not in ("idr", "returns-only") or context.source_units not in (
        "decimal",
        "percent-experiment",
    ):
        raise DCCUnavailable(
            "variant_units", "explicit qualified variant/source units required; Z is dimensionless"
        )
    if context.purpose not in ("primitive", "research-window"):
        raise DCCUnavailable("purpose", "primitive or research-window required")
    if (
        type(context.expected_observations) is not int
        or context.expected_observations != len(data.z)
        or (context.purpose == "research-window" and len(data.z) != 1260)
    ):
        raise DCCUnavailable("history_length", "history differs from declared experiment/R1 window")
    try:
        if type(context.sessions) is not tuple:
            raise ValueError("immutable sessions required")
        dates = tuple(date.fromisoformat(s) for s in context.sessions)
        if not dates or len(dates) != len(data.z) or tuple(sorted(set(dates))) != dates:
            raise ValueError("ordered unique complete sessions required")
        if any(d.isoformat() != s for d, s in zip(dates, context.sessions, strict=True)):
            raise ValueError("canonical dates required")
        if context.cutoff != context.sessions[-1]:
            raise ValueError("cutoff must equal final declared session")
    except (TypeError, ValueError) as exc:
        raise DCCUnavailable("sessions", str(exc)) from exc
    if data.target_context != target_context(
        context
    ) or data.target_input_sha256 != observation_hash(data.z):
        raise DCCUnavailable("target_provenance", "target and ordered Z provenance must match")
    if data.target_kind not in ("analytical-r1", "fixed-primitive") or (
        data.target_kind == "fixed-primitive" and context.purpose != "primitive"
    ):
        raise DCCUnavailable("target_profile", "fixed target is only a primitive reference")
    if data.target_kind == "analytical-r1" and (len(data.z) < 12 or len(data.z) == len(data.z[0])):
        raise DCCUnavailable(
            "target_profile", "analytical target short/equality domain is unsupported"
        )
    if data.target_kind == "fixed-primitive" and data.target_identity_sha256 != fingerprint(
        ["stipulated-fixed-target", data.target]
    ):
        raise DCCUnavailable("target_provenance", "stipulated target identity differs from matrix")
    return c, correction


def _theta(values: tuple[float, ...]) -> Theta:
    if len(values) != 2 or any(not math.isfinite(v) for v in values):
        raise DCCUnavailable("parameters", "two finite parameters required")
    a, b = values
    if a < 0 or b < 0 or a + b >= 1:
        raise DCCUnavailable("parameters", "require a,b>=0 and a+b<1")
    return a, b


def _evaluate(z: Matrix, c: Matrix, theta: Theta, correction: float) -> PairEvaluation:
    a, b = _theta(theta)
    pairs = tuple((j, j + 1) for j in range(len(c) - 1))
    target = np.asarray([(c[i][i], c[j][j], c[i][j]) for i, j in pairs], dtype=np.float64)
    observations = np.asarray(z, dtype=np.float64)
    last_q = target.copy()
    last_da = np.zeros_like(target)
    last_db = np.zeros_like(target)
    scores: list[float] = []
    ga: list[float] = []
    gb: list[float] = []

    def filtered(forcing: FloatArray, previous: FloatArray) -> FloatArray:
        # y[t] = forcing[t] + beta*y[t-1]. zi is the carried delay,
        # not a steady-state seed. This preserves the declared Q[1]/zero dQ.
        result, _ = signal.lfilter([1.0], [1.0, -b], forcing, axis=0, zi=b * previous[None])
        return np.asarray(result, dtype=np.float64)

    def refuse(mask: NDArray[np.bool_], start: int, code: str, reason: str) -> None:
        if mask.any():
            row, pair = np.argwhere(mask)[0]
            raise DCCUnavailable(code, f"session {start + int(row)}, pair {int(pair)}: {reason}")

    # Bound temporary path arrays independently of the full history length.
    # There is no full covariance history, time-window truncation or pair subset.
    for start in range(0, len(z), 64):
        stop = min(start + 64, len(z))
        block = observations[start:stop]
        prior = np.empty_like(block)
        prior[0] = observations[start - 1] if start else 0.0
        prior[1:] = block[:-1]
        with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
            products = np.stack(
                (prior[:, :-1] ** 2, prior[:, 1:] ** 2, prior[:, :-1] * prior[:, 1:]), axis=-1
            )
            forcing = (1 - a - b) * target + a * products
            forcing_da = -target + products
            if start == 0:
                forcing[0] = target
                forcing_da[0] = 0.0
            q = filtered(forcing, last_q if start else np.zeros_like(target))
            da = filtered(forcing_da, last_da)
            previous_q = np.concatenate((last_q[None], q[:-1]), axis=0)
            db = filtered(-target + previous_q, last_db)
            qi, qj, qij = q[..., 0], q[..., 1], q[..., 2]
            refuse(
                ~np.isfinite(q).all(axis=-1) | (qi <= 0) | (qj <= 0),
                start,
                "pair_state",
                "invalid diagonal/state",
            )
            denominator = np.sqrt(qi) * np.sqrt(qj)
            rho = qij / denominator
            determinant = 1 - rho * rho
            refuse(
                ~np.isfinite(determinant) | (determinant <= 0),
                start,
                "pair_determinant",
                "nonpositive determinant",
            )
            u, w = block[:, :-1], block[:, 1:]
            quadratic = u * u + w * w - 2 * rho * u * w
            nll = math.log(2 * math.pi) + np.log(determinant) / 2 + quadratic / (2 * determinant)
            derivative = -(rho + u * w) / determinant + rho * quadratic / (
                determinant * determinant
            )
            dr_a = da[..., 2] / denominator - rho * (da[..., 0] / qi + da[..., 1] / qj) / 2
            dr_b = db[..., 2] / denominator - rho * (db[..., 0] / qi + db[..., 1] / qj) / 2
            alpha_scores, beta_scores = derivative * dr_a, derivative * dr_b
            refuse(
                ~np.isfinite(nll)
                | ~np.isfinite(alpha_scores)
                | ~np.isfinite(beta_scores)
                | ~np.isfinite(da).all(axis=-1)
                | ~np.isfinite(db).all(axis=-1),
                start,
                "pair_score",
                "nonfinite score/sensitivity",
            )
        # Retain the original accurately summed pair mean and chronological
        # all-session sum; NumPy reductions do not replace the score convention.
        scores.extend(math.fsum(row) / len(pairs) for row in nll)
        ga.extend(math.fsum(row) / len(pairs) for row in alpha_scores)
        gb.extend(math.fsum(row) / len(pairs) for row in beta_scores)
        last_q, last_da, last_db = q[-1].copy(), da[-1].copy(), db[-1].copy()
    total = math.fsum(scores)
    gradient = math.fsum(ga), math.fsum(gb)
    if not all(math.isfinite(v) for v in (total, *gradient)):
        raise DCCUnavailable("objective", "nonfinite objective/gradient")

    def triples(values: FloatArray) -> tuple[Triple, ...]:
        return tuple((float(row[0]), float(row[1]), float(row[2])) for row in values)

    return PairEvaluation(
        theta,
        pairs,
        tuple(scores),
        total,
        gradient,
        triples(last_q),
        triples(last_da),
        triples(last_db),
        correction,
    )


def evaluate_fixed(z: Matrix, target: Matrix, parameters: Theta) -> PairEvaluation:
    """All-session R1 fixed-parameter primitive; normalization/score constants retained."""
    c, correction = _arrays(z, target)
    try:
        return _evaluate(z, c, parameters, correction)
    except (OverflowError, FloatingPointError) as exc:
        raise DCCUnavailable("numerical_failure", str(exc)) from exc


def project_parameters(theta: Theta) -> Theta:
    if len(theta) != 2 or any(not math.isfinite(v) for v in theta):
        raise DCCUnavailable("projection", "finite two-coordinate vector required")
    a, b = theta
    if max(a, 0) + max(b, 0) <= CAP:
        return max(a, 0), max(b, 0)
    if a - b >= CAP:
        return CAP, 0.0
    if b - a >= CAP:
        return 0.0, CAP
    return (a - b + CAP) / 2, (b - a + CAP) / 2


def projected_residual(theta: Theta, gradient: Theta, observations: int) -> float:
    if type(observations) is not int or observations <= 0:
        raise DCCUnavailable("projection", "positive scored count required")
    point = project_parameters(
        (theta[0] - gradient[0] / observations, theta[1] - gradient[1] / observations)
    )
    return max(abs(theta[j] - point[j]) for j in range(2))


def _boundary(theta: Theta) -> tuple[str, ...]:
    return tuple(
        name
        for name, residual in (
            ("alpha_zero", abs(theta[0])),
            ("beta_zero", abs(theta[1])),
            ("persistence_cap", abs(sum(theta) - CAP)),
        )
        if residual <= FEASIBILITY_ATOL
    )


def _run_start(
    data: DCCInput, c: Matrix, correction: float, index: int, initial: Theta
) -> StartDiagnostic:
    objective_calls = gradient_calls = iterations = 0
    last_theta: Theta | None = None
    cached: PairEvaluation | None = None

    def evaluate(values: FloatArray, *, jacobian: bool) -> PairEvaluation:
        nonlocal objective_calls, gradient_calls, last_theta, cached
        if objective_calls + gradient_calls >= MAX_CALLBACKS:
            raise DCCUnavailable("budget_exhausted", "combined callback cap reached")
        if jacobian:
            gradient_calls += 1
        else:
            objective_calls += 1
        theta = _theta(tuple(float(v) for v in values))
        if theta != last_theta:
            result = _evaluate(data.z, c, theta, correction)
            cached, last_theta = result, theta
        assert cached is not None
        return cached

    def objective(values: FloatArray) -> float:
        return evaluate(values, jacobian=False).nll_sum

    def jacobian(values: FloatArray) -> FloatArray:
        return np.asarray(evaluate(values, jacobian=True).gradient)

    def callback(values: FloatArray) -> None:
        nonlocal iterations
        iterations += 1
        if iterations > MAX_ITERATIONS:
            raise DCCUnavailable("iteration_budget_exceeded", "iteration callback cap reached")

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
            bounds=((0.0, 1.0), (0.0, 1.0)),
            constraints={
                "type": "ineq",
                "fun": lambda p: CAP - p[0] - p[1],
                "jac": lambda p: np.array([-1.0, -1.0]),
            },
            callback=callback,
            options={"maxiter": MAX_ITERATIONS, "ftol": FTOL},
        )
        success, optimizer_status = bool(raw.success), int(raw.status)
        message = str(raw.message)
        iterations = max(iterations, int(raw.nit))
        theta = _theta(tuple(float(v) for v in raw.x))
        raw_objective = float(raw.fun)
        if not math.isfinite(raw_objective):
            raise DCCUnavailable("nonfinite_optimizer", "reported objective is nonfinite")
        reported = raw_objective
        result = _evaluate(data.z, c, theta, correction)
        score = result.nll_sum
        feasible = max(0.0, -theta[0], -theta[1], sum(theta) - CAP)
        residual = projected_residual(theta, result.gradient, len(data.z))
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
    except (DCCUnavailable, OverflowError, FloatingPointError) as exc:
        status = exc.code if isinstance(exc, DCCUnavailable) else "numerical_failure"
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


def fit_dcc(data: DCCInput) -> DCCResult:
    """Twelve R1 starts. Unavailable means no selected model, with all diagnostics retained."""
    c, correction = _validate_input(data)
    if np.__version__ != "2.5.4" or scipy.__version__ != "1.18.1":
        raise DCCUnavailable("runtime", "unqualified NumPy/SciPy versions")
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
        "seed": "Q[1]=Ctarget; zero sensitivities",
        "score": "all sessions; adjacent pair mean/time sum",
        "runtime": [
            platform.python_version(),
            platform.system(),
            platform.machine(),
            np.__version__,
            scipy.__version__,
        ],
        "target_symmetry_correction": correction,
    }
    config_hash, input_hash = fingerprint(configuration), fingerprint(asdict(data))
    starts = tuple(_run_start(data, c, correction, j, theta) for j, theta in enumerate(STARTS))
    eligible = tuple(s for s in starts if s.status == "eligible")
    selected: int | None = None
    result: PairEvaluation | None = None
    score_range: tuple[float, float] | None = None
    parameter_ranges: tuple[tuple[float, float], ...] = ()
    if eligible:
        chosen = min(eligible, key=lambda s: (float(s.objective), s.index))  # type: ignore[arg-type]
        assert chosen.parameters is not None
        selected = chosen.index
        result = _evaluate(data.z, c, chosen.parameters, correction)
        scores = tuple(float(s.objective) for s in eligible)  # type: ignore[arg-type]
        score_range = min(scores), max(scores)
        parameter_ranges = tuple(
            (
                min(s.parameters[j] for s in eligible if s.parameters is not None),
                max(s.parameters[j] for s in eligible if s.parameters is not None),
            )
            for j in range(2)
        )
    status = "fit-complete" if result else "unavailable"
    issues = () if result else ("no_eligible_start",)
    output_hash = fingerprint(
        {
            "status": status,
            "issues": issues,
            "starts": [asdict(s) for s in starts],
            "selected": selected,
            "evaluation": asdict(result) if result else None,
            "objective_range": score_range,
            "parameter_ranges": parameter_ranges,
        }
    )
    return DCCResult(
        status,
        issues,
        VERSION,
        data,
        config_hash,
        input_hash,
        starts,
        selected,
        result,
        score_range,
        parameter_ranges,
        output_hash,
        fingerprint([config_hash, input_hash, output_hash]),
    )
