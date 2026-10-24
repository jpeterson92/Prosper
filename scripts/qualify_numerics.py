"""Synthetic stack probes and independently specified scalar oracles, never a risk service."""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray
from scipy import linalg, optimize, stats

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {"numpy": "2.5.4", "scipy": "1.18.1"}
# R1 candidates fixed before execution. Scales are explicit per comparison.
RTOL = 1e-8
COV_ATOL = 1e-12
OBJECTIVE_ATOL = 1e-8
CONSTRAINT_CAP = 0.99998


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual: float, reference: float, *, atol: float, scale: float = 1.0) -> float:
    """Fail on unknown/nonfinite/invalid scale; return measured absolute error."""
    if not all(math.isfinite(v) for v in (actual, reference, atol, scale)):
        raise ValueError("nonfinite comparison")
    if scale <= 0 or atol < 0:
        raise ValueError("invalid comparison scale/tolerance")
    error = abs(actual - reference)
    if error > atol * scale + RTOL * max(abs(actual), abs(reference)):
        raise AssertionError((actual, reference, error, atol, scale))
    return error


def decimal_pi() -> Decimal:
    """Machin identity, independent of NumPy/SciPy and binary libm pi."""

    def atan_inverse(n: int) -> Decimal:
        x = Decimal(1) / n
        power = x
        total = x
        for k in range(1, 1000):
            power *= -(x * x)
            term = power / (2 * k + 1)
            updated = total + term
            if updated == total:
                return total
            total = updated
        raise AssertionError("arctangent series did not converge")

    return 16 * atan_inverse(5) - 4 * atan_inverse(239)


def scalar_oracle() -> dict[str, Any]:
    """Exact Fraction states and 90-digit density expectations, with all terms scored.

    No Prosper estimator or numerical library supplies these expected values.
    The fixed-state recurrence and initial state are the R1 engineering convention.
    """
    x = [Fraction(v) for v in (1, -2, 0, 3, -1)]
    s2 = sum((v * v for v in x), Fraction()) / len(x)
    tau = math.isqrt(len(x) - 1) + 1
    weights = [Fraction(94**j, 100**j) for j in range(tau)]
    seed = sum((w * v * v for w, v in zip(weights, x, strict=False)), Fraction()) / sum(
        weights, Fraction()
    )
    u, g, b = Fraction(1, 10), Fraction(1, 5), Fraction(7, 10)
    states = [seed]
    for previous in x[:-1]:
        states.append(u * s2 + g * previous * previous + b * states[-1])
    with localcontext() as ctx:
        ctx.prec = 90
        pi = decimal_pi()

        def dec(f: Fraction) -> Decimal:
            return Decimal(f.numerator) / f.denominator

        contributions = [
            ((2 * pi).ln() + dec(v).ln() + dec(r * r / v)) / 2
            for r, v in zip(x, states, strict=True)
        ]
        # E04 from the bivariate Gaussian determinant and inverse quadratic form.
        pair = (2 * pi).ln() + (Decimal(3) / 4).ln() / 2 + 2
        return {
            "x": [str(v) for v in x],
            "units": "synthetic decimal innovations; zero mean; no rescale/demean",
            "s2": str(s2),
            "tau": tau,
            "seed": str(seed),
            "parameters_u_g_b": [str(u), str(g), str(b)],
            "variance_fractions": [str(v) for v in states],
            "nll_90_digits": [str(v) for v in contributions],
            "nll_sum_90_digits": str(sum(contributions)),
            "E02_90_digits": str(((2 * pi).ln() + Decimal(4).ln() + 1) / 2),
            "E04_90_digits": str(pair),
        }


def qualify() -> dict[str, Any]:
    installed = {name: metadata.version(name) for name in VERSIONS}
    if installed != VERSIONS:
        raise ValueError(f"unqualified versions: {installed}")
    oracle = scalar_oracle()
    x = np.array([float(Fraction(v)) for v in oracle["x"]])
    s2 = float(np.mean(x * x))
    weights = np.power(0.94, np.arange(oracle["tau"]))
    seed = float(np.dot(weights, x[: oracle["tau"]] ** 2) / np.sum(weights))
    u, g, b = [float(Fraction(v)) for v in oracle["parameters_u_g_b"]]
    variances = [seed]
    for previous in x[:-1]:
        variances.append(u * s2 + g * previous**2 + b * variances[-1])
    states = np.array(variances)
    state_error = max(
        close(a, float(Fraction(r)), atol=COV_ATOL, scale=s2)
        for a, r in zip(variances, oracle["variance_fractions"], strict=True)
    )
    # An external density implementation scores explicitly supplied variances.
    nll = -stats.norm.logpdf(x, loc=0, scale=np.sqrt(states))
    likelihood_error = max(
        close(float(a), float(r), atol=OBJECTIVE_ATOL)
        for a, r in zip(nll, oracle["nll_90_digits"], strict=True)
    )
    total_error = close(float(np.sum(nll)), float(oracle["nll_sum_90_digits"]), atol=OBJECTIVE_ATOL)
    e02 = float(-stats.norm.logpdf(2, loc=0, scale=2))
    e04 = float(-stats.multivariate_normal.logpdf([1, 2], cov=[[1, 0.5], [0.5, 1]]))
    close(e02, float(oracle["E02_90_digits"]), atol=OBJECTIVE_ATOL)
    close(e04, float(oracle["E04_90_digits"]), atol=OBJECTIVE_ATOL)
    # Scaling returns and standard deviations by 100 adds T*log(100) to NLL.
    percent_nll = float(-np.sum(stats.norm.logpdf(x * 100, scale=np.sqrt(states) * 100)))
    close(percent_nll, float(np.sum(nll)) + len(x) * math.log(100), atol=OBJECTIVE_ATOL)

    spectra = []
    # Analytic eigenvalues: [[5, -2, 0], [-2, 5, 0], [0, 0, 1]] has 1,3,7.
    # Repeated and singular spectra exercise basis-independent reconstruction.
    for matrix, expected_spectrum in (
        ([[5, -2, 0], [-2, 5, 0], [0, 0, 1]], [1, 3, 7]),
        ([[3, 0, 0], [0, 3, 0], [0, 0, 1]], [1, 3, 3]),
        ([[1, -1, 0], [-1, 1, 0], [0, 0, 3]], [0, 2, 3]),
    ):
        for scale in (1e-12, 1.0, 1e12):
            a = np.array(matrix, dtype=float) * scale
            values, vectors = linalg.eigh(a, check_finite=True)
            numpy_values = np.linalg.eigvalsh(a)
            # Scale is max input-column second moment, here diagonal of test S.
            second_moment = float(np.max(np.diag(a)))
            errors = [
                close(float(v), e * scale, atol=COV_ATOL, scale=second_moment)
                for v, e in zip(values, expected_spectrum, strict=True)
            ]
            reconstruction = vectors @ np.diag(values) @ vectors.T
            for actual, ref in zip(reconstruction.flat, a.flat, strict=True):
                close(float(actual), float(ref), atol=COV_ATOL, scale=second_moment)
            for actual, ref in zip(values, numpy_values, strict=True):
                close(float(actual), float(ref), atol=COV_ATOL, scale=second_moment)
            spectra.append(
                {"spectrum": values.tolist(), "scale": second_moment, "max_error": max(errors)}
            )
    try:
        linalg.eigh(np.array([[math.nan, 0], [0, 1]]), check_finite=True)
    except ValueError:
        pass
    else:
        raise AssertionError("nonfinite eigensystem was accepted")

    optimizations = []
    # Strict convex quadratics have analytical constrained minima by projection.
    for target, expected in (
        ([0.25, 0.1, 0.2], [0.25, 0.1, 0.2]),
        ([0.25, 1.0, 1.0], [0.25, CONSTRAINT_CAP / 2, CONSTRAINT_CAP / 2]),
        ([-1.0, -1.0, 2.0], [1e-12, 0.0, CONSTRAINT_CAP]),
    ):
        destination = np.array(target)
        callbacks = 0

        def objective(
            theta: NDArray[np.float64], target: NDArray[np.float64] = destination
        ) -> tuple[float, NDArray[np.float64]]:
            nonlocal callbacks
            callbacks += 1  # combined fun/jac call counts once in this API.
            if callbacks > 40000:
                raise RuntimeError("callback budget exhausted")
            delta = theta - target
            return float(np.dot(delta, delta) / 2), delta

        result = optimize.minimize(
            objective,
            [0.1, 0.1, 0.8],
            jac=True,
            method="SLSQP",
            bounds=[(1e-12, 10), (0, 1), (0, 1)],
            constraints=[
                {
                    "type": "ineq",
                    "fun": lambda t: CONSTRAINT_CAP - t[1] - t[2],
                    "jac": lambda t: np.array([0.0, -1.0, -1.0]),
                }
            ],
            options={"maxiter": 2000, "ftol": 1e-10},
        )
        if not result.success:
            raise AssertionError(str(result.message))
        feasibility = max(
            0.0,
            1e-12 - result.x[0],
            result.x[0] - 10,
            -result.x[1],
            -result.x[2],
            result.x[1] + result.x[2] - CONSTRAINT_CAP,
        )
        if feasibility > 1e-10:
            raise AssertionError("infeasible optimizer result")
        # For this unit-Hessian quadratic, projected gradient residual is x-P(target).
        residual = float(np.max(np.abs(result.x - expected)))
        if residual > 1e-5:
            raise AssertionError("projected gradient residual")
        for parameter, expected_parameter in zip(result.x, expected, strict=True):
            close(float(parameter), expected_parameter, atol=1e-8)
        optimizations.append(
            {
                "target": target,
                "expected": expected,
                "x": result.x.tolist(),
                "status": int(result.status),
                "iterations": int(result.nit),
                "callbacks": callbacks,
                "feasibility": float(feasibility),
                "projected_gradient_residual": residual,
            }
        )
    config = np.show_config(mode="dicts")
    result = {
        "schema": "prosper-synthetic-stack-qualification-v1",
        "scope": "stack and fixed-state references only; no fitted risk model",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "executable": sys.executable,
            "versions": installed,
            "numpy_config": config,
            "scipy_config": scipy.show_config(mode="dicts"),
            "thread_overrides": {
                name: os.environ.get(name)
                for name in (
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NPY_DISABLE_CPU_FEATURES",
                )
            },
            "distribution_records": {
                name: {
                    str(p): digest(Path(str(metadata.distribution(name).locate_file(p))))
                    for p in (metadata.distribution(name).files or [])
                    if ".dist-info/" in str(p) and p.name in ("METADATA", "WHEEL", "RECORD")
                }
                for name in VERSIONS
            },
        },
        "input": oracle,
        "tolerances": {
            "rtol": RTOL,
            "covariance_atol_times_scale": COV_ATOL,
            "objective_atol": OBJECTIVE_ATOL,
            "objective_scale": 1,
        },
        "outputs": {
            "variance": variances,
            "nll": nll.tolist(),
            "nll_sum": float(np.sum(nll)),
            "E02": e02,
            "E04": e04,
            "state_max_error": state_error,
            "likelihood_max_error": likelihood_error,
            "total_error": total_error,
            "spectra": spectra,
            "optimizations": optimizations,
        },
        "source_sha256": {
            str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
            for p in (
                Path(__file__),
                ROOT / "pyproject.toml",
                ROOT / "uv.lock",
                ROOT / "docs/tasks/T006.2.1.1-python-numerical-spec.md",
            )
        },
    }
    for section in ("input", "environment"):
        result[section + "_sha256"] = hashlib.sha256(
            json.dumps(result[section], sort_keys=True, allow_nan=False).encode("utf-8")
        ).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if not destination.is_relative_to(ROOT / ".local"):
        parser.error("output must be a new directory inside project .local")
    destination.mkdir(parents=True, exist_ok=False)
    result = qualify()
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output = destination / "qualification.json"
    output.write_text(payload, encoding="utf-8", newline="\n")
    print(f"Synthetic stack qualification passed: {output}; SHA-256 {digest(output)}")


if __name__ == "__main__":
    main()
