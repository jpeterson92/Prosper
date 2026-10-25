"""Identified analytical nonlinear-shrinkage component, synthetic-qualified only.

P18 Appendix C/D, P20 equations 4.3-4.9 and A20, frozen R1 thresholds.
Derived float64 values never replace exact source/ledger facts. This component
does not resolve identities, qualify histories, fit DCC or accept financial use.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray
from scipy import linalg

FloatArray = NDArray[np.float64]
VERSION = "analytical-nl-p18-a20-r1-v1"
SPECIFICATION_SHA256 = "9535aac0560aedc2d06d35d4201643d018500683f5f23910446dc52c3704e01b"
# Bind the loaded source once; calculations themselves perform no filesystem I/O.
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
RANK_RTOL = 1e-12
NEGATIVE_RTOL = 1e-10
SYMMETRY_RTOL = 1e-10


class TargetUnavailable(ValueError):
    """Located refusal; no repaired/fallback matrix accompanies a failure."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class TargetContext:
    """Caller-attested frozen provenance, never proof of qualified market data."""

    security_ids: tuple[str, ...]
    cutoff: str
    calendar: str
    transformation: str
    source_sha256: tuple[str, ...]


@dataclass(frozen=True)
class TargetResult:
    version: str
    implementation_sha256: str
    specification_sha256: str
    context: TargetContext
    preprocessing: str
    degrees_of_freedom: int
    observations: int
    effective_observations: int
    branch: str
    structural_nulls: int
    input_sha256: str
    model_sha256: str
    sample_eigenvalues: FloatArray
    shrunk_eigenvalues: FloatArray
    covariance: FloatArray
    correlation: FloatArray
    relative_symmetry_correction: float
    minimum_relative_eigenvalue: float


def _frozen(array: FloatArray) -> FloatArray:
    # A bytes-backed view cannot be made writable by flipping the NumPy flag.
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def hilbert_kernel(x: FloatArray) -> FloatArray:
    """Hilbert transform of the Epanechnikov kernel, including exact limits.

    log1p retains the neighborhood of zero/endpoints. The convergent inverse-x
    series avoids cancellation between two O(x) terms in the far tail; this is
    the same equation, not a clipped neighborhood or substituted kernel.
    """
    if not np.isfinite(x).all():
        raise TargetUnavailable("nonfinite_kernel", "kernel arguments must be finite")
    y = x / math.sqrt(5)
    result = np.empty_like(y)
    tail = np.abs(y) > 2
    middle = ~tail & (np.abs(y) != 1)
    endpoint = ~tail & ~middle
    ym = y[middle]
    logs = np.log(np.abs(1 - ym)) - np.log(np.abs(1 + ym))
    small = np.abs(ym) < 0.5
    logs[small] = np.log1p(-ym[small]) - np.log1p(ym[small])
    result[middle] = 3 / (4 * math.sqrt(5) * math.pi) * (-2 * ym + (1 - ym * ym) * logs)
    result[endpoint] = -3 * x[endpoint] / (10 * math.pi)
    inverse = 1 / y[tail]
    power = inverse.copy()
    total = power / 3
    for k in range(1, 128):
        power *= inverse * inverse
        updated = total + power / ((2 * k + 1) * (2 * k + 3))
        if np.array_equal(updated, total):
            break
        total = updated
    else:
        raise TargetUnavailable("kernel_series", "tail series did not converge")
    result[tail] = -3 / (math.sqrt(5) * math.pi) * total
    return result


def _null_density(h: float, eigenvalues: FloatArray) -> float:
    # With a=sqrt(5)*h, the published bracket equals the positive series
    # sum_{k>=0} 3*a^(2k)/((2k+1)*(2k+3)). Avoid 1/h^2 cancellation.
    a2 = 5 * h * h
    total, power = 1.0, 1.0
    for k in range(1, 10000):
        power *= a2
        updated = total + 3 * power / ((2 * k + 1) * (2 * k + 3))
        if updated == total:
            return total * float(np.mean(1 / eigenvalues)) / math.pi
        total = updated
    raise TargetUnavailable("null_series", "null-density series did not converge")


def _spectrum_target(ell: FloatArray, n: int, p: int) -> FloatArray:
    """Rows are evaluation eigenvalues; columns carry kernel bandwidths."""
    h = n ** (-1 / 3)
    bandwidth = h * ell
    x = (ell[:, None] - ell[None, :]) / bandwidth[None, :]
    kernel = 3 / (4 * math.sqrt(5)) * np.maximum(1 - x * x / 5, 0)
    f = np.mean(kernel / bandwidth[None, :], axis=1)
    g = np.mean(hilbert_kernel(x) / bandwidth[None, :], axis=1)
    if p < n:
        c = p / n
        denominator = (math.pi * c * ell * f) ** 2 + (1 - c - math.pi * c * ell * g) ** 2
        shrunk = ell / denominator
    else:
        d0 = 1 / (math.pi * ((p - n) / n) * _null_density(h, ell))
        positive = 1 / (math.pi**2 * ell * (f * f + g * g))
        shrunk = np.concatenate((np.full(p - n, d0), positive))
    if not np.isfinite(shrunk).all() or np.any(shrunk <= 0):
        raise TargetUnavailable("invalid_shrinkage", "nonpositive/nonfinite target spectrum")
    return shrunk


def analytical_target(
    observations: FloatArray,
    *,
    context: TargetContext,
    preprocessing: Literal["none", "demean", "residuals"],
    degrees_of_freedom: int,
) -> TargetResult:
    """Compute a target from explicitly cast float64 observations [time, stock].

    `none` is R1 zero-mean k=0; `demean` subtracts means once with k=1;
    `residuals` uses already preprocessed data and explicit k without subtraction.
    Those preprocessing variants have distinct identities. N=n is unsupported.
    Context fields preserve caller attestations, not independently verified facts.
    """
    if (
        type(observations) is not np.ndarray
        or observations.dtype != np.float64
        or observations.ndim != 2
        or min(observations.shape) < 1
    ):
        raise TargetUnavailable("input_shape_type", "require a nonempty float64 [T,N] array")
    if not np.isfinite(observations).all():
        raise TargetUnavailable("nonfinite_input", "no missing/NaN/infinite observations")
    t, p = observations.shape
    if (
        type(degrees_of_freedom) is not int
        or degrees_of_freedom < 0
        or preprocessing not in ("none", "demean", "residuals")
        or (preprocessing == "none" and degrees_of_freedom != 0)
        or (preprocessing == "demean" and degrees_of_freedom != 1)
    ):
        raise TargetUnavailable("preprocessing", "explicit consistent preprocessing/k required")
    n = t - degrees_of_freedom
    if n < 12:
        raise TargetUnavailable("short_history", f"effective n={n}; require n>=12")
    if p == n:
        raise TargetUnavailable("unsupported_equality", f"N=n={n} remains unqualified")
    if (
        not isinstance(context, TargetContext)
        or type(context.security_ids) is not tuple
        or len(context.security_ids) != p
        or any(type(v) is not str or not v.strip() for v in context.security_ids)
        or len(set(context.security_ids)) != p
        or any(
            type(v) is not str or not v.strip()
            for v in (context.cutoff, context.calendar, context.transformation)
        )
        or type(context.source_sha256) is not tuple
        or not context.source_sha256
        or any(
            type(v) is not str or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in context.source_sha256
        )
    ):
        raise TargetUnavailable(
            "provenance", "ordered unique identities/frozen provenance required"
        )
    raw = np.array(observations, dtype="<f8", order="C", copy=True)
    input_hash = hashlib.sha256(raw.tobytes()).hexdigest()
    magnitude = float(np.max(np.abs(raw)))
    if magnitude == 0 or not math.isfinite(magnitude * magnitude) or magnitude * magnitude == 0:
        raise TargetUnavailable("numeric_scale", "zero/unrepresentable observation-square scale")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x = raw / magnitude
            if preprocessing == "demean":
                x -= np.mean(x, axis=0)
            sample = x.T @ x / n
            if np.any(np.diag(sample) <= 0):
                raise TargetUnavailable("zero_variance", "all stock variances must be positive")
            eigenvalues, vectors = linalg.eigh(sample, check_finite=True)
            spectral_scale = float(eigenvalues[-1])
            if spectral_scale <= 0 or np.any(eigenvalues < -NEGATIVE_RTOL * spectral_scale):
                raise TargetUnavailable("negative_spectrum", "materially negative sample spectrum")
            nulls = max(p - n, 0)
            if np.any(np.abs(eigenvalues[:nulls]) > RANK_RTOL * spectral_scale) or np.any(
                eigenvalues[nulls:] <= RANK_RTOL * spectral_scale
            ):
                raise TargetUnavailable("rank", "unexpected nullity or near-zero positive spectrum")
            shrunk = _spectrum_target(eigenvalues[nulls:], n, p)
            covariance = (vectors * shrunk) @ vectors.T
            correction = float(np.max(np.abs(covariance - covariance.T))) / float(
                np.max(np.abs(covariance))
            )
            if correction > SYMMETRY_RTOL:
                raise TargetUnavailable("asymmetry", "target exceeds R1 symmetry tolerance")
            covariance = (covariance + covariance.T) / 2
            diagonal = np.diag(covariance)
            if np.any(diagonal <= 0):
                raise TargetUnavailable("invalid_diagonal", "target diagonal must be positive")
            sd = np.sqrt(diagonal)
            correlation = covariance / sd[:, None] / sd[None, :]
            corr_eigenvalues = linalg.eigvalsh(correlation, check_finite=True)
            target_eigenvalues = linalg.eigvalsh(covariance, check_finite=True)
            relative_minimum = min(
                float(target_eigenvalues[0] / target_eigenvalues[-1]),
                float(corr_eigenvalues[0] / corr_eigenvalues[-1]),
            )
            if relative_minimum <= RANK_RTOL:
                raise TargetUnavailable(
                    "target_not_spd", "target/correlation fails R1 SPD threshold"
                )
            scale = magnitude * magnitude
            covariance *= scale
            shrunk *= scale
            eigenvalues *= scale
            if (
                not np.isfinite(covariance).all()
                or not np.isfinite(shrunk).all()
                or np.any(np.diag(covariance) <= 0)
                or np.any(shrunk < np.finfo(np.float64).tiny)
            ):
                raise TargetUnavailable("numeric_scale", "unrepresentable scaled output")
    except (FloatingPointError, linalg.LinAlgError) as exc:
        raise TargetUnavailable("numerical_failure", str(exc)) from exc
    identity = _hash(
        {
            "version": VERSION,
            "implementation_sha256": IMPLEMENTATION_SHA256,
            "specification_sha256": SPECIFICATION_SHA256,
            "context": asdict(context),
            "input": input_hash,
            "shape": [t, p],
            "preprocessing": preprocessing,
            "k": degrees_of_freedom,
            "n": n,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "thresholds": [RANK_RTOL, NEGATIVE_RTOL, SYMMETRY_RTOL],
        }
    )
    return TargetResult(
        VERSION,
        IMPLEMENTATION_SHA256,
        SPECIFICATION_SHA256,
        context,
        preprocessing,
        degrees_of_freedom,
        t,
        n,
        "nonsingular" if p < n else "singular",
        nulls,
        input_hash,
        identity,
        _frozen(eigenvalues),
        _frozen(shrunk),
        _frozen(covariance),
        _frozen(correlation),
        correction,
        relative_minimum,
    )
