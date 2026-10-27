"""Independent finite-sum Decimal forecast references and frozen synthetic replay.

References use geometric/convolution expressions, not production recurrences.
Same-agent expectations do not replace independent model review or calibration.
"""

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import numpy as np
from qualify_dcc import peak_working_set
from qualify_innovations import load_input

from prosper import covariance as cv
from prosper import dcc, volatility
from prosper.innovations import SPECIFICATION_SHA256, fingerprint, transform_ohlc

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/dcc/covariance-reference.json"
I2: cv.Matrix = ((1.0, 0.0), (0.0, 1.0))
CASES: tuple[dict[str, Any], ...] = (
    {
        "name": "E05-E06-constant",
        "target": ((1.0, 0.5), (0.5, 1.0)),
        "next_q": ((4.0, 3.0), (3.0, 9.0)),
        "variance_one": (4.0, 9.0),
        "omega": (1.0, 2.25),
        "persistence": (0.75, 0.75),
        "dcc_persistence": 0.9,
    },
    {
        "name": "E14-decay",
        "target": I2,
        "next_q": ((1.0, 0.5), (0.5, 1.0)),
        "variance_one": (4.0, 4.0),
        "omega": (1.0, 1.0),
        "persistence": (0.75, 0.75),
        "dcc_persistence": 0.9,
    },
    {
        "name": "q-zero",
        "target": I2,
        "next_q": ((1.0, 0.5), (0.5, 1.0)),
        "variance_one": (4.0, 9.0),
        "omega": (0.1, 0.2),
        "persistence": (0.0, 0.8),
        "dcc_persistence": 0.0,
    },
    {
        "name": "nonconstant-three-stock",
        "target": ((1.0, 0.2, -0.1), (0.2, 1.0, 0.3), (-0.1, 0.3, 1.0)),
        "next_q": ((2.0, 0.3, -0.2), (0.3, 3.0, 0.4), (-0.2, 0.4, 1.0)),
        "variance_one": (0.0002, 0.0005, 0.0003),
        "omega": (0.00001, 0.00002, 0.00003),
        "persistence": (0.95, 0.90, 0.85),
        "dcc_persistence": 0.98,
    },
)


def decimal_forecast(case: dict[str, Any], horizon: int, precision: int = 90) -> dict[str, Any]:
    """Direct powers and finite sums; preserve exact binary64 inputs in the oracle."""
    with localcontext() as ctx:
        ctx.prec = precision
        d = Decimal.from_float
        c = [[d(v) for v in row] for row in case["target"]]
        q = [[d(v) for v in row] for row in case["next_q"]]
        n = len(c)
        r1 = [[q[i][j] / (q[i][i] * q[j][j]).sqrt() for j in range(n)] for i in range(n)]
        forecasts = []
        for h in range(1, horizon + 1):
            v = []
            for i in range(n):
                s = d(case["persistence"][i])
                powers = [Decimal(1)] + [s**k for k in range(1, h)]
                v.append(
                    d(case["omega"][i]) * sum(powers[: h - 1], Decimal(0))
                    + powers[h - 1] * d(case["variance_one"][i])
                )
            power = Decimal(1) if h == 1 else d(case["dcc_persistence"]) ** (h - 1)
            forecasts.append(
                [
                    [
                        (v[i] * v[j]).sqrt() * (c[i][j] + power * (r1[i][j] - c[i][j]))
                        for j in range(n)
                    ]
                    for i in range(n)
                ]
            )
        total = [
            [sum((h[i][j] for h in forecasts), Decimal(0)) for j in range(n)] for i in range(n)
        ]
        average = [[v / horizon for v in row] for row in total]
        annual = [[v * 252 for v in row] for row in average]
        return {
            k: [[str(v) for v in row] for row in matrix]
            for k, matrix in (
                ("next_correlation", r1),
                ("one_session", forecasts[0]),
                ("last_session", forecasts[-1]),
                ("cumulative", total),
                ("average_daily", average),
                ("annualized", annual),
            )
        }


def closed_q(z: cv.Matrix, target: cv.Matrix, theta: dcc.Theta, t: int) -> cv.Matrix:
    """Full Q at zero-based t, using direct convolution rather than Q recursion."""
    with localcontext() as ctx:
        ctx.prec = 90
        d = Decimal.from_float
        a, b = map(d, theta)
        powers = [Decimal(1)] + [b**j for j in range(1, t + 1)]
        coefficient = powers[t] + (1 - a - b) * sum(powers[:t], Decimal(0))
        return tuple(
            tuple(
                float(
                    coefficient * d(target[i][j])
                    + a
                    * sum(
                        (powers[t - 1 - k] * d(z[k][i]) * d(z[k][j]) for k in range(t)), Decimal(0)
                    )
                )
                for j in range(len(target))
            )
            for i in range(len(target))
        )


def build_reference() -> dict[str, Any]:
    cases = []
    for case in CASES:
        for horizon in (1, 21):
            ref = decimal_forecast(case, horizon)
            finer = decimal_forecast(case, horizon, 110)
            for key in ref:
                for row, fine_row in zip(ref[key], finer[key], strict=True):
                    for value, fine in zip(row, fine_row, strict=True):
                        if abs(Decimal(value) - Decimal(fine)) > Decimal("1e-85") * max(
                            Decimal(1), abs(Decimal(fine))
                        ):
                            raise AssertionError("reference precision disagreement")
            cases.append({"input": case, "horizon": horizon, "expected": ref})
    return {
        "version": "covariance-finite-sums-r1-v1",
        "precision": "90 digits; 110-digit cross-check",
        "specification_sha256": SPECIFICATION_SHA256,
        "cases": cases,
    }


def compare(actual: cv.Projection, reference: dict[str, Any]) -> None:
    for key, matrix in reference.items():
        # R1 covariance comparisons are scale-relative, with 1e-12*s2 absolute term.
        expected = np.asarray(matrix, dtype=float)
        scale = float(np.max(np.abs(expected)))
        if not np.allclose(getattr(actual, key), expected, rtol=1e-8, atol=1e-12 * scale):
            raise AssertionError(f"forecast reference mismatch: {key}")


def simulation_inputs() -> tuple[tuple[volatility.VolatilityInput, ...], dict[str, Any]]:
    """Fictional 1260-by-3 returns-only research experiment, no provider data."""
    rng = np.random.Generator(np.random.PCG64(622222))
    shocks = rng.standard_normal((1260, 3))
    c = np.array([[1.0, 0.3, -0.1], [0.3, 1.0, 0.2], [-0.1, 0.2, 1.0]])
    shocks = shocks @ np.linalg.cholesky(c).T
    omega = np.array([0.00001, 0.00002, 0.000015])
    g, b = np.array([0.08, 0.06, 0.09]), np.array([0.87, 0.90, 0.85])
    variance = omega / (1 - g - b)
    rows = []
    for shock in shocks:
        x = np.sqrt(variance) * shock
        rows.append(tuple(float(v) for v in x))
        variance = omega + g * x * x + b * variance
    construction = {
        "generator": "NumPy PCG64 seed 622222; 1260-by-3 normal draws; correlated shocks",
        "shocks_sha256": hashlib.sha256(shocks.tobytes()).hexdigest(),
        "omega": omega.tolist(),
        "g": g.tolist(),
        "b": b.tolist(),
        "generating_correlation": c.tolist(),
        "interpretation": "component-composition experiment; no calibration/recovery claim",
    }
    sessions = tuple((date(2001, 1, 1) + timedelta(days=j)).isoformat() for j in range(1260))
    inputs = tuple(
        volatility.VolatilityInput(
            tuple(row[j] for row in rows),
            f"FICTIONAL-COMPOSE-{j}",
            sessions,
            sessions[-1],
            "fictional-consecutive-daily-v1",
            "UTC",
            "returns-only",
            "decimal",
            fingerprint([construction, j, rows]),
            "research-window",
            1260,
        )
        for j in range(3)
    )
    return inputs, construction


def qualify(*, simulate: bool = False, burden: dict[str, Any] | None = None) -> dict[str, Any]:
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    if reference != json.loads(json.dumps(build_reference())):
        raise AssertionError("frozen forecast reference differs; never silently rewrite")
    fixed = []
    for case in reference["cases"]:
        args = {k: v for k, v in case["input"].items() if k != "name"}
        projected = cv.project_fixed(**args, horizon=case["horizon"])
        compare(projected, case["expected"])
        fixed.append(asdict(projected))
    context, rows = load_input()
    innovation = transform_ohlc(context, rows)
    inputs = tuple(
        volatility.series_from_innovations(
            innovation, j, purpose="primitive", expected_observations=len(context.sessions)
        )
        for j in range(len(context.security_ids))
    )
    primitive = cv.fit_covariance(inputs)
    if primitive.projection is None:
        raise AssertionError(primitive.issues)
    report: dict[str, Any] = {
        "scope": "synthetic covariance composition; independent model review/calibration open",
        "implementation_sha256": cv.IMPLEMENTATION_SHA256,
        "qualifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "specification_sha256": SPECIFICATION_SHA256,
        "current_specification_document_sha256": hashlib.sha256(
            (ROOT / "docs/tasks/T006.2.1.1-python-numerical-spec.md").read_bytes()
        ).hexdigest(),
        "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "runtime": platform.python_version(),
        "fixed": fixed,
        "idr_primitive": asdict(primitive),
    }
    candidates = [primitive]
    if simulate:
        data, construction = simulation_inputs()
        wall, cpu = time.perf_counter(), time.process_time()
        composed = cv.fit_covariance(data)
        if burden is not None:
            burden.update(
                {
                    "observations": 1260,
                    "securities": 3,
                    "wall_seconds": time.perf_counter() - wall,
                    "cpu_seconds": time.process_time() - cpu,
                    "process_peak_working_set_bytes": peak_working_set(),
                    "scope": (
                        "whole-process peak including interpreter/reference work; no capacity claim"
                    ),
                }
            )
        if composed.projection is None:
            raise AssertionError(composed.issues)
        report["simulation"] = {"construction": construction, "result": asdict(composed)}
        candidates.append(composed)
    for result in candidates:
        assert result.dcc_fit and result.dcc_fit.evaluation and result.projection
        dcc_data, theta = result.dcc_fit.data, result.dcc_fit.evaluation.parameters
        for t, actual in (
            (len(dcc_data.z) - 1, result.terminal_q),
            (len(dcc_data.z), result.next_q),
        ):
            assert actual is not None
            if not np.allclose(
                actual, closed_q(dcc_data.z, dcc_data.target, theta, t), rtol=1e-8, atol=1e-10
            ):
                raise AssertionError("full Q convolution reference")
        paths = [s.path for s in result.scalars]
        assert all(p is not None for p in paths)
        valid = [p for p in paths if p is not None]
        case = {
            "target": dcc_data.target,
            "next_q": closed_q(dcc_data.z, dcc_data.target, theta, len(dcc_data.z)),
            "variance_one": tuple(
                p.omega
                + p.parameters_u_g_b[1] * p.x[-1] ** 2
                + p.parameters_u_g_b[2] * p.variance[-1]
                for p in valid
            ),
            "omega": tuple(p.omega for p in valid),
            "persistence": tuple(sum(p.parameters_u_g_b[1:]) for p in valid),
            "dcc_persistence": sum(theta),
        }
        compare(result.projection, decimal_forecast(case, 21))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--burden-output", type=Path)
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()
    if args.write_reference:
        REFERENCE.write_text(
            json.dumps(build_reference(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    burden: dict[str, Any] = {}
    report = qualify(simulate=args.simulate, burden=burden)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if args.burden_output:
        args.burden_output.write_text(
            json.dumps(burden, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    print("Synthetic covariance composition qualification passed")


if __name__ == "__main__":
    main()
