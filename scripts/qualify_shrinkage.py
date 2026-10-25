"""Synthetic spectral qualification with a separate 90-digit direct-equation oracle.

No provider calls, fitted model, portfolio files or external reference runtime.
The Decimal reference uses no Prosper kernel/shrinkage/eigensolver output.
"""

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray

from prosper.shrinkage import TargetContext, analytical_target, hilbert_kernel

ROOT = Path(__file__).resolve().parents[1]
RTOL = 1e-8
COV_ATOL = 1e-12
CORR_ATOL = 1e-10


def decimal_pi() -> Decimal:
    """Machin's identity; independent of binary pi and the component."""
    totals = []
    for divisor in (5, 239):
        x = Decimal(1) / divisor
        power, total = x, x
        for k in range(1, 1000):
            power *= -x * x
            updated = total + power / (2 * k + 1)
            if updated == total:
                break
            total = updated
        else:
            raise AssertionError("pi oracle failed")
        totals.append(total)
    return 16 * totals[0] - 4 * totals[1]


def decimal_kernel(x: Decimal, pi: Decimal) -> Decimal:
    root = Decimal(5).sqrt()
    if abs(x) == root:
        return -3 * x / (10 * pi)
    return -3 * x / (10 * pi) + 3 / (4 * root * pi) * (1 - x * x / 5) * (
        abs((root - x) / (root + x)).ln()
    )


def reference_spectrum(n: int, p: int, values: list[str]) -> list[str]:
    """Direct published equations at 90 digits, without stable-series shortcuts."""
    if p == n:
        raise ValueError("unsupported equality in reference manifest")
    with localcontext() as ctx:
        ctx.prec = 90
        pi = decimal_pi()
        ell = [Decimal(v) for v in values]
        h = (-Decimal(n).ln() / 3).exp()
        root = Decimal(5).sqrt()
        f, g = [], []
        for left in ell:
            density, hilbert = Decimal(0), Decimal(0)
            for right in ell:
                x = (left - right) / (h * right)
                density += 3 / (4 * root) * max(1 - x * x / 5, Decimal(0)) / (h * right)
                hilbert += decimal_kernel(x, pi) / (h * right)
            f.append(density / len(ell))
            g.append(hilbert / len(ell))
        if p < n:
            c = Decimal(p) / n
            d = [
                value / ((pi * c * value * fi) ** 2 + (1 - c - pi * c * value * gi) ** 2)
                for value, fi, gi in zip(ell, f, g, strict=True)
            ]
        else:
            bracket = (
                3 / (10 * h * h)
                + 3
                / (4 * root * h)
                * (1 - 1 / (5 * h * h))
                * ((1 + root * h) / (1 - root * h)).ln()
            )
            g0 = bracket * sum(1 / v for v in ell) / len(ell) / pi
            d0 = 1 / (pi * (Decimal(p - n) / n) * g0)
            d = [d0] * (p - n) + [
                1 / (pi * pi * value * (fi * fi + gi * gi))
                for value, fi, gi in zip(ell, f, g, strict=True)
            ]
        return [str(v) for v in d]


def context(p: int) -> TargetContext:
    return TargetContext(
        tuple(f"SYNTHETIC-{i:03d}" for i in range(p)),
        "synthetic-session-0064",
        "synthetic-ordered-sessions-v1",
        "synthetic-decimal-innovations-float64-v1",
        ("0" * 64,),
    )


def fixture(
    n: int, p: int, values: list[str], *, demean: bool = False
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Known Householder eigenbasis; no numerical eigensolver supplies truth."""
    nulls = max(p - n, 0)
    v = np.arange(1, p + 1, dtype=np.float64)
    basis = np.eye(p) - 2 * np.outer(v, v) / float(v @ v)
    positive = basis[:, nulls:]
    weights = np.sqrt(n * np.array([float(v) for v in values]))
    rows = n + int(demean)
    temporal = np.eye(rows, len(values))
    if demean:
        temporal = np.zeros((rows, len(values)))
        for j in range(len(values)):
            denominator = math.sqrt((j + 1) * (j + 2))
            temporal[: j + 1, j] = 1 / denominator
            temporal[j + 1, j] = -(j + 1) / denominator
    x = (temporal * weights) @ positive.T
    if demean:
        x += np.arange(1, p + 1, dtype=np.float64)
    return x, basis


def assert_close(actual: NDArray[np.float64], expected: NDArray[np.float64], atol: float) -> float:
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise AssertionError("nonfinite comparison")
    error = np.abs(actual - expected)
    if np.any(error > atol + RTOL * np.maximum(np.abs(actual), np.abs(expected))):
        raise AssertionError(f"reference mismatch, maximum absolute error {np.max(error)}")
    return float(np.max(error))


def qualify() -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    cases = [
        ("nondegenerate-low", 64, 4, ["0.01", "0.5", "2", "6"], False),
        ("minimum-n-low", 12, 3, ["0.7", "1", "4"], False),
        ("minimum-n-singular", 12, 15, [str(Decimal(i + 4) / 8) for i in range(12)], False),
        ("nondegenerate-singular", 32, 35, [str(Decimal(i + 4) / 8) for i in range(32)], False),
        ("near-zero-accepted", 64, 3, ["0.0000000001", "1", "2"], False),
        ("repeated", 64, 4, ["1", "1", "3", "3"], False),
        ("demean-minimum", 12, 3, ["0.7", "1", "4"], True),
    ]
    with localcontext() as ctx:
        ctx.prec = 90
        edge = 1 + Decimal(5).sqrt() / 4
        for label, delta in (("below", "-1e-12"), ("at", "0"), ("above", "1e-12")):
            cases.append(
                (f"spectral-endpoint-{label}", 64, 2, ["1", str(edge + Decimal(delta))], False)
            )
    for name, n, p, values, demean in cases:
        x, basis = fixture(n, p, values, demean=demean)
        reference = reference_spectrum(n, p, values)
        d = np.array([float(v) for v in reference])
        expected = (basis * d) @ basis.T
        sd = np.sqrt(np.diag(expected))
        expected_correlation = expected / sd[:, None] / sd[None, :]
        result = analytical_target(
            x,
            context=context(p),
            preprocessing="demean" if demean else "none",
            degrees_of_freedom=int(demean),
        )
        # Same predeclared R1 scale as the specification: largest marginal s2.
        centered = x - x.mean(axis=0) if demean else x
        scale = float(np.max(np.sum(centered * centered, axis=0) / n))
        spectrum_error = assert_close(result.shrunk_eigenvalues, d, COV_ATOL * scale)
        covariance_error = assert_close(result.covariance, expected, COV_ATOL * scale)
        correlation_error = assert_close(result.correlation, expected_correlation, CORR_ATOL)
        outputs.append(
            {
                "case": name,
                "n": n,
                "p": p,
                "spectrum": values,
                "preprocessing": result.preprocessing,
                "branch": result.branch,
                "reference_90_digits": reference,
                "spectrum_error": spectrum_error,
                "covariance_error": covariance_error,
                "correlation_error": correlation_error,
                "input_sha256": result.input_sha256,
                "model_sha256": result.model_sha256,
                "covariance": result.covariance.tolist(),
                "correlation": result.correlation.tolist(),
            }
        )
    with localcontext() as ctx:
        ctx.prec = 90
        pi = decimal_pi()
        root = Decimal(5).sqrt()
        e10 = Decimal(5120) / (4805 + 9 * pi * pi)
        e11_d1 = 5 / (9 * pi * pi)
        e11_d0 = 64 / (Decimal(24) / 5 - 33 / (5 * root) * ((4 + root) / (4 - root)).ln())
        e10_x = np.zeros((64, 2))
        e10_x[:2] = np.eye(2) * 8
        e10_result = analytical_target(
            e10_x,
            context=context(2),
            preprocessing="none",
            degrees_of_freedom=0,
        )
        e10_error = assert_close(e10_result.covariance, np.eye(2) * float(e10), COV_ATOL)
        # Helmert columns analytically span the orthogonal complement of ones.
        helmert = np.zeros((65, 64))
        for j in range(64):
            denominator = math.sqrt((j + 1) * (j + 2))
            helmert[: j + 1, j] = 1 / denominator
            helmert[j + 1, j] = -(j + 1) / denominator
        e11_result = analytical_target(
            8 * helmert.T,
            context=context(65),
            preprocessing="none",
            degrees_of_freedom=0,
        )
        null_projection = np.ones((65, 65)) / 65
        e11_expected = float(e11_d1) * (np.eye(65) - null_projection)
        e11_expected += float(e11_d0) * null_projection
        e11_error = assert_close(e11_result.covariance, e11_expected, COV_ATOL)
        points = np.array(
            [
                -1e12,
                -100,
                -2 * math.sqrt(5),
                -math.sqrt(5),
                np.nextafter(-math.sqrt(5), -math.inf),
                -math.sqrt(5) * (1 - 1e-10),
                -1e-12,
                0,
                1e-12,
                math.sqrt(5) * (1 - 1e-10),
                math.sqrt(5),
                np.nextafter(math.sqrt(5), math.inf),
                math.sqrt(5) * (1 + 1e-10),
                2 * math.sqrt(5),
                np.nextafter(2 * math.sqrt(5), math.inf),
                100,
                1e12,
            ]
        )
        kernel_reference = [str(decimal_kernel(Decimal.from_float(float(x)), pi)) for x in points]
        kernel_values = hilbert_kernel(points)
        kernel_error = assert_close(
            kernel_values,
            np.array([float(v) for v in kernel_reference]),
            COV_ATOL,
        )
        # Tail comparisons also use a relative criterion, so absolute atol cannot
        # conceal cancellation to zero in a value of order 1e-13.
        tail = np.abs(points) >= 100
        assert_close(
            kernel_values[tail],
            np.array([float(v) for v in kernel_reference])[tail],
            0,
        )
        closed = {
            "E10_d": str(e10),
            "E11_d1": str(e11_d1),
            "E11_d0": str(e11_d0),
            "E10_error": e10_error,
            "E11_error": e11_error,
        }
    return {
        "cases": outputs,
        "closed_expressions": closed,
        "kernel": {
            "x": points.tolist(),
            "reference_90_digits": kernel_reference,
            "actual": kernel_values.tolist(),
            "maximum_error": kernel_error,
        },
        "tolerances": {
            "rtol": RTOL,
            "covariance_atol_times_max_s2": COV_ATOL,
            "correlation_atol": CORR_ATOL,
            "tail_atol": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if not destination.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("output must be a new ignored checkout .local directory")
    outputs = qualify()
    sources = [
        "src/prosper/shrinkage.py",
        "scripts/qualify_shrinkage.py",
        "docs/tasks/T006.2.1.1-python-numerical-spec.md",
        "pyproject.toml",
        "uv.lock",
    ]
    record = {
        "outputs": outputs,
        "sources": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "blas": np.show_config(mode="dicts"),
        },
        "context_example": asdict(context(2)),
        "limits": "synthetic checks; independent model review and financial use pending",
    }
    destination.mkdir(parents=True, exist_ok=False)
    encoded = (json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    (destination / "qualification.json").write_bytes(encoded)
    print(
        json.dumps(
            {
                "path": str(destination),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "cases": len(outputs["cases"]),
                "closed": outputs["closed_expressions"],
                "kernel_error": outputs["kernel"]["maximum_error"],
            }
        )
    )


if __name__ == "__main__":
    main()
