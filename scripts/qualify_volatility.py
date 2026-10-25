"""Synthetic R1 fixed-state, gradient and fitted-output replay evidence.

The Decimal objective below is a direct expression route, without production
recursions, gradients or optimization. Simulation recovery is reported, never
treated as proof of a unique/global optimum or calibrated portfolio risk.
"""

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from qualify_innovations import load_input
from qualify_numerics import decimal_pi

from prosper.innovations import SPECIFICATION_SHA256, fingerprint, transform_ohlc
from prosper.volatility import (
    IMPLEMENTATION_SHA256,
    Theta,
    VolatilityInput,
    evaluate_fixed,
    fit_volatility,
    forecast_variance,
    series_from_innovations,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/innovations/reference.json"


def decimal_objective(x: tuple[float, ...], theta: tuple[Decimal, ...]) -> Decimal:
    """90-digit direct Gaussian expression with independently constructed R1 seed."""
    with localcontext() as ctx:
        ctx.prec = 90
        values = [Decimal.from_float(v) for v in x]
        s2 = sum((v * v for v in values), Decimal(0)) / len(values)
        tau = math.isqrt(len(values)) + (math.isqrt(len(values)) ** 2 != len(values))
        weights = [(Decimal(47) / 50) ** Decimal(j) for j in range(tau)]
        variance = sum(
            (w * v * v for w, v in zip(weights, values[:tau], strict=True)), Decimal(0)
        ) / sum(weights)
        u, g, b = theta
        total = Decimal(0)
        pi = decimal_pi()
        for j, value in enumerate(values):
            if j:
                variance = u * s2 + g * values[j - 1] * values[j - 1] + b * variance
            total += ((2 * pi).ln() + variance.ln() + value * value / variance) / 2
        return +total


def reference_directional_derivative(
    x: tuple[float, ...],
    theta: Theta,
    direction: Theta,
    *,
    one_sided: bool = False,
) -> float:
    """High precision finite difference, separate from analytic sensitivity code."""
    with localcontext() as ctx:
        ctx.prec = 90
        h = Decimal("1e-30")
        point = tuple(Decimal.from_float(v) for v in theta)
        vector = tuple(Decimal.from_float(v) for v in direction)
        plus = tuple(p + h * d for p, d in zip(point, vector, strict=True))
        if one_sided:
            return float((decimal_objective(x, plus) - decimal_objective(x, point)) / h)
        minus = tuple(p - h * d for p, d in zip(point, vector, strict=True))
        return float((decimal_objective(x, plus) - decimal_objective(x, minus)) / (2 * h))


def simulation_input() -> tuple[VolatilityInput, dict[str, Any]]:
    """Seeded fictional 1260-session scalar research experiment, no provider data."""
    generator = np.random.Generator(np.random.PCG64(62212))
    shocks = generator.standard_normal(1260)
    omega, g, b = 0.00001, 0.08, 0.87
    variance = omega / (1 - g - b)
    innovations = []
    for shock in shocks:
        value = math.sqrt(variance) * float(shock)
        innovations.append(value)
        variance = omega + g * value * value + b * variance
    construction = {
        "generator": "NumPy PCG64 seed 62212 standard_normal, ordered scalar draws",
        "numpy": np.__version__,
        "omega_g_b": [omega, g, b],
        "generation_seed_variance": omega / (1 - g - b),
        "shocks_sha256": hashlib.sha256(shocks.tobytes()).hexdigest(),
        "note": "generating initial state differs from R1 fitted weighted seed",
    }
    sessions = tuple((date(2001, 1, 1) + timedelta(days=j)).isoformat() for j in range(1260))
    data = VolatilityInput(
        tuple(innovations),
        "FICTIONAL-SIMULATED",
        sessions,
        sessions[-1],
        "fictional-consecutive-daily-v1",
        "UTC",
        "returns-only",
        "decimal",
        fingerprint(construction),
        "research-window",
        1260,
    )
    return data, construction


def qualify(*, simulate: bool = False) -> dict[str, Any]:
    spec = ROOT / "docs/tasks/T006.2.1.1-python-numerical-spec.md"
    if hashlib.sha256(spec.read_bytes()).hexdigest() != SPECIFICATION_SHA256:
        raise AssertionError("frozen specification changed")
    references = json.loads(REFERENCE.read_text(encoding="utf-8"))
    stack = references["stack_fixed_state"]
    x = tuple(float(Fraction(v)) for v in stack["x"])
    path = evaluate_fixed(x, (0.1, 0.2, 0.7))
    if abs(path.nll_sum - float(stack["nll_sum_90_digits"])) > 1e-8:
        raise AssertionError("fixed-state NLL")
    for actual, exact in zip(path.variance, stack["variance_fractions"], strict=True):
        if abs(actual - float(Fraction(exact))) > 1e-12 * path.s2 + 1e-8 * abs(actual):
            raise AssertionError("fixed-state variance")
    forecasts = forecast_variance(path, 21)
    for actual, exact in zip(forecasts, stack["forecast_1_to_21_fractions"], strict=True):
        if abs(actual - float(Fraction(exact))) > 1e-12 * path.s2 + 1e-8 * abs(actual):
            raise AssertionError("fixed-state forecast")
    derivatives = []
    derivative_cases: list[tuple[Theta, Theta, bool]] = [
        ((0.1, 0.2, 0.7), (1.0, 0.0, 0.0), False),
        ((0.1, 0.2, 0.7), (0.0, 1.0, 0.0), False),
        ((0.1, 0.2, 0.7), (0.0, 0.0, 1.0), False),
        ((1e-12, 0.0, 0.8), (1.0, 1.0, 0.0), True),
        ((0.2, 0.4, 0.59998), (0.0, 1.0, -1.0), False),
        ((10.0, 0.0, 0.0), (-1.0, 1.0, 1.0), True),
    ]
    # Fixed, predeclared interior grid, separate from optimizer trial points.
    for u in (0.001, 0.1, 1.0, 9.5):
        for g in (0.01, 0.2, 0.6):
            for b in (0.01, 0.2, 0.35):
                for direction in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
                    derivative_cases.append(((u, g, b), direction, False))
    for theta, direction, one_sided in derivative_cases:
        point: Theta = theta
        vector: Theta = direction
        gradient = evaluate_fixed(x, point).gradient
        actual = math.fsum(g * d for g, d in zip(gradient, vector, strict=True))
        expected = reference_directional_derivative(x, point, vector, one_sided=one_sided)
        if abs(actual - expected) > 1e-8 + 1e-8 * max(abs(actual), abs(expected)):
            raise AssertionError((point, actual, expected))
        derivatives.append(
            {
                "theta": point,
                "direction": vector,
                "one_sided": one_sided,
                "actual": actual,
                "reference": expected,
            }
        )
    context, rows = load_input()
    transformed = transform_ohlc(context, rows)
    fits = []
    for j, reference in enumerate(references["idr_fixed_state"]):
        data = series_from_innovations(
            transformed, j, purpose="primitive", expected_observations=12
        )
        fixed = evaluate_fixed(data.x, (0.1, 0.2, 0.7))
        if abs(fixed.nll_sum - float(reference["nll_sum"])) > 1e-8:
            raise AssertionError("IDR fixed-state NLL")
        for actual, expected in ((fixed.s2, reference["s2"]), (fixed.seed, reference["seed"])):
            if abs(actual - float(expected)) > 1e-12 * fixed.s2 + 1e-8 * abs(actual):
                raise AssertionError("IDR second moment/seed")
        for actuals, expected_values, kind in (
            (fixed.variance, reference["variance"], "variance"),
            (fixed.nll, reference["nll"], "nll"),
            (forecast_variance(fixed, 21), reference["forecast_1_to_21"], "forecast"),
        ):
            for actual, expected in zip(actuals, expected_values, strict=True):
                atol = 1e-8 if kind == "nll" else 1e-12 * fixed.s2
                if abs(actual - float(expected)) > atol + 1e-8 * max(
                    abs(actual), abs(float(expected))
                ):
                    raise AssertionError(f"IDR fixed-state {kind}")
        fitted = fit_volatility(data)
        if fitted.path is None:
            raise AssertionError(fitted.starts)
        fits.append(asdict(fitted))
    report: dict[str, Any] = {
        "scope": "synthetic scalar R1; independent review/calibration open",
        "specification_sha256": SPECIFICATION_SHA256,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "qualifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "runtime": platform.python_version(),
        "fixed_stack": asdict(path),
        "fixed_stack_forecast": forecasts,
        "derivatives": derivatives,
        "primitive_fits": fits,
    }
    if simulate:
        data, construction = simulation_input()
        fitted = fit_volatility(data)
        if fitted.path is None:
            raise AssertionError(fitted.starts)
        generating = construction["omega_g_b"]
        generating_scaled: Theta = (generating[0] / fitted.path.s2, generating[1], generating[2])
        candidate = evaluate_fixed(data.x, generating_scaled)
        if fitted.path.nll_sum > candidate.nll_sum + 1e-8:
            raise AssertionError(
                "fit worse than the declared generating candidate under R1 scoring"
            )
        report["simulation"] = {
            "construction": construction,
            "fit": asdict(fitted),
            "generating_candidate_r1_nll": candidate.nll_sum,
            "fitted_omega_g_b": [fitted.path.omega, *fitted.path.parameters_u_g_b[1:]],
            "interpretation": "finite-sample recovery diagnostic; no unique/global-optimum claim",
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    report = (
        json.dumps(qualify(simulate=args.simulate), indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print("Synthetic scalar volatility qualification passed")


if __name__ == "__main__":
    main()
