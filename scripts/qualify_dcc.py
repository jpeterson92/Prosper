"""Independent direct-matrix Decimal expressions and synthetic DCC replay.

References use a finite geometric/convolution expression, not the production
streamed recursion or its analytic derivatives. Same-agent expected outputs do
not replace independent model review, full-model parity or forecast calibration.
"""

import argparse
import ctypes
import hashlib
import json
import math
import platform
import time
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import numpy as np
from qualify_numerics import close, decimal_pi

from prosper import dcc
from prosper.innovations import SPECIFICATION_SHA256, fingerprint
from prosper.shrinkage import analytical_target

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/synthetic/dcc/reference.json"
CASES: tuple[tuple[str, dcc.Matrix, dcc.Matrix, dcc.Theta], ...] = (
    ("E03", ((1.0, 2.0), (0.5, -1.0)), ((1.0, 0.0), (0.0, 1.0)), (0.1, 0.8)),
    ("E04", ((1.0, 2.0),), ((1.0, 0.5), (0.5, 1.0)), (0.1, 0.8)),
    (
        "three-stock",
        (
            (1.0, 2.0, -0.5),
            (-1.0, 0.5, 1.0),
            (0.25, -1.5, 0.5),
            (2.0, -0.5, -1.0),
            (0.5, 0.25, 1.5),
        ),
        ((1.0, 0.25, -0.125), (0.25, 1.0, 0.375), (-0.125, 0.375, 1.0)),
        (0.05, 0.9),
    ),
)


def direct_reference(
    z: dcc.Matrix, c: dcc.Matrix, theta: tuple[Decimal, ...], *, precision: int = 90
) -> dict[str, Any]:
    """Full matrix closed finite convolution, separately specified from the recurrence."""
    with localcontext() as ctx:
        ctx.prec = precision
        x = [[Decimal.from_float(v) for v in row] for row in z]
        target = [[Decimal.from_float(v) for v in row] for row in c]
        a, b = theta
        scores, states = [], []
        for t, row in enumerate(x):
            # Python/Decimal 0**0 is undefined for Decimal, so define beta^0 explicitly.
            powers = [Decimal(1)] + [b**k for k in range(1, t + 1)]
            target_coefficient = powers[t] + (1 - a - b) * sum(powers[:t], Decimal(0))
            q = [
                [
                    target_coefficient * target[i][j]
                    + a * sum((powers[t - 1 - k] * x[k][i] * x[k][j] for k in range(t)), Decimal(0))
                    for j in range(len(c))
                ]
                for i in range(len(c))
            ]
            terms = []
            for i in range(len(c) - 1):
                j = i + 1
                r = q[i][j] / (q[i][i] * q[j][j]).sqrt()
                determinant = 1 - r * r
                terms.append(
                    (2 * decimal_pi()).ln()
                    + determinant.ln() / 2
                    + (row[i] * row[i] + row[j] * row[j] - 2 * r * row[i] * row[j])
                    / (2 * determinant)
                )
            scores.append(sum(terms) / len(terms))
            states.append(q)
        return {
            "nll": [str(v) for v in scores],
            "nll_sum": str(sum(scores)),
            "terminal_full_q": [[str(v) for v in row] for row in states[-1]],
        }


def derivative_reference(
    z: dcc.Matrix, c: dcc.Matrix, theta: dcc.Theta, direction: dcc.Theta, one_sided: bool
) -> float:
    with localcontext() as ctx:
        ctx.prec = 90
        h = Decimal("1e-30")
        point = tuple(Decimal.from_float(v) for v in theta)
        vector = tuple(Decimal.from_float(v) for v in direction)
        plus = tuple(p + h * d for p, d in zip(point, vector, strict=True))
        left = point if one_sided else tuple(p - h * d for p, d in zip(point, vector, strict=True))
        return float(
            (
                Decimal(direct_reference(z, c, plus)["nll_sum"])
                - Decimal(direct_reference(z, c, left)["nll_sum"])
            )
            / (h if one_sided else 2 * h)
        )


def build_reference() -> dict[str, Any]:
    cases = []
    for name, z, c, theta in CASES:
        point = tuple(Decimal.from_float(v) for v in theta)
        expected = direct_reference(z, c, point)
        higher = direct_reference(z, c, point, precision=110)
        with localcontext() as ctx:
            ctx.prec = 110
            values = [
                expected["nll_sum"],
                *expected["nll"],
                *(v for row in expected["terminal_full_q"] for v in row),
            ]
            high_values = [
                higher["nll_sum"],
                *higher["nll"],
                *(v for row in higher["terminal_full_q"] for v in row),
            ]
            for value, high_value in zip(values, high_values, strict=True):
                if abs(Decimal(value) - Decimal(high_value)) > Decimal("1e-85") * max(
                    Decimal(1), abs(Decimal(high_value))
                ):
                    raise AssertionError("reference precision instability")
        cases.append({"name": name, "z": z, "target": c, "theta": theta, "expected": expected})
    return {
        "scope": (
            "synthetic fixed-state direct geometric/convolution expression; same-agent reference"
        ),
        "precision": 90,
        "precision_crosscheck": 110,
        "comparison": {"rtol": 1e-8, "objective_atol": 1e-8, "correlation_atol": 1e-10},
        "specification_sha256": SPECIFICATION_SHA256,
        "cases": cases,
    }


def context_for(
    z: dcc.Matrix, *, purpose: str = "primitive", variant: str = "returns-only"
) -> dcc.DCCContext:
    sessions = tuple((date(2000, 1, 1) + timedelta(days=j)).isoformat() for j in range(len(z)))
    return dcc.DCCContext(
        tuple(f"FICTIONAL-DCC-{j}" for j in range(len(z[0]))),
        sessions,
        sessions[-1],
        "fictional-daily-grid",
        "UTC",
        variant,
        "decimal",
        tuple(
            fingerprint(["fictional-column", j, [row[j] for row in z]]) for j in range(len(z[0]))
        ),
        purpose,
        len(z),
    )


def simulation_input() -> tuple[dcc.DCCInput, dict[str, Any]]:
    generator = np.random.Generator(np.random.PCG64(622221))
    shocks = generator.standard_normal((1260, 3))
    c = np.array([[1.0, 0.35, -0.1], [0.35, 1.0, 0.2], [-0.1, 0.2, 1.0]])
    a, b = 0.04, 0.91
    q = c.copy()
    rows = []
    for shock in shocks:
        sd = np.sqrt(np.diag(q))
        r = q / sd[:, None] / sd[None, :]
        value = np.linalg.cholesky(r) @ shock
        rows.append(tuple(float(v) for v in value))
        q = (1 - a - b) * c + a * np.outer(value, value) + b * q
    z = tuple(rows)
    context = context_for(z, purpose="research-window")
    target = analytical_target(
        np.asarray(z),
        context=dcc.target_context(context),
        preprocessing="none",
        degrees_of_freedom=0,
    )
    data = dcc.input_from_target(z, context, target)
    construction = {
        "generator": "NumPy PCG64 seed 622221 standard_normal shape (1260,3), row-major draws",
        "generating_parameters": [a, b],
        "generating_target": c.tolist(),
        "initial_q": c.tolist(),
        "shock_sha256": hashlib.sha256(shocks.astype("<f8").tobytes()).hexdigest(),
        "z_sha256": dcc.observation_hash(z),
        "target_model_sha256": target.model_sha256,
        "target_estimation": (
            "R1 analytical target from complete generated Z; differs from generating C"
        ),
        "scope": "dimensionless synthetic DCC-stage experiment, no scalar fitting/composition",
    }
    return data, construction


def peak_working_set() -> int | None:
    if platform.system() != "Windows":
        return None
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def qualify(*, simulate: bool = False, burden: dict[str, Any] | None = None) -> dict[str, Any]:
    if (
        hashlib.sha256(
            (ROOT / "docs/tasks/T006.2.1.1-python-numerical-spec.md").read_bytes()
        ).hexdigest()
        != SPECIFICATION_SHA256
    ):
        raise AssertionError("frozen specification changed")
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    if reference != json.loads(json.dumps(build_reference())):
        raise AssertionError("frozen reference differs; never silently rewrite")
    fixed = []
    for name, z, c, theta in CASES:
        expected = next(v["expected"] for v in reference["cases"] if v["name"] == name)
        fixed_output = dcc.evaluate_fixed(z, c, theta)
        close(fixed_output.nll_sum, float(expected["nll_sum"]), atol=1e-8)
        for value, exact in zip(fixed_output.nll, expected["nll"], strict=True):
            close(value, float(exact), atol=1e-8)
        for (i, j), state in zip(fixed_output.pairs, fixed_output.terminal_q, strict=True):
            for value, exact in zip(
                state,
                (
                    expected["terminal_full_q"][i][i],
                    expected["terminal_full_q"][j][j],
                    expected["terminal_full_q"][i][j],
                ),
                strict=True,
            ):
                close(value, float(exact), atol=1e-10)
        fixed.append(asdict(fixed_output))
    _, z, c, _ = CASES[-1]
    cases: list[tuple[dcc.Theta, dcc.Theta, bool]] = []
    for a in (0.001, 0.01, 0.1, 0.4, 0.8):
        for b in (0.001, 0.05, 0.15):
            for direction in ((1.0, 0.0), (0.0, 1.0)):
                cases.append(((a, b), direction, False))
    cases += [
        ((0.0, 0.8), (1.0, 0.0), True),
        ((0.1, 0.0), (0.0, 1.0), True),
        ((0.0, 0.0), (1.0, 1.0), True),
        ((0.4, dcc.CAP - 0.4), (1.0, -1.0), False),
        ((dcc.CAP, 0.0), (-1.0, 1.0), True),
        ((0.0, dcc.CAP), (1.0, -1.0), True),
    ]
    derivatives = []
    for theta, direction, one_sided in cases:
        gradient = dcc.evaluate_fixed(z, c, theta).gradient
        actual = math.fsum(g * d for g, d in zip(gradient, direction, strict=True))
        expected_value = derivative_reference(z, c, theta, direction, one_sided)
        close(actual, expected_value, atol=1e-8)
        derivatives.append(
            {
                "theta": theta,
                "direction": direction,
                "one_sided": one_sided,
                "actual": actual,
                "reference": expected_value,
            }
        )
    report: dict[str, Any] = {
        "scope": "synthetic DCC pair fitting only; independent review/calibration open",
        "specification_sha256": SPECIFICATION_SHA256,
        "implementation_sha256": dcc.IMPLEMENTATION_SHA256,
        "qualifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "runtime": platform.python_version(),
        "fixed": fixed,
        "derivatives": derivatives,
    }
    if simulate:
        data, construction = simulation_input()
        start_wall, start_cpu = time.perf_counter(), time.process_time()
        fitted = dcc.fit_dcc(data)
        if fitted.evaluation is None:
            raise AssertionError(fitted.starts)
        if burden is not None:
            burden.update(
                {
                    "observations": len(data.z),
                    "securities": len(data.z[0]),
                    "starts": len(fitted.starts),
                    "wall_seconds": time.perf_counter() - start_wall,
                    "cpu_seconds": time.process_time() - start_cpu,
                    "process_peak_working_set_bytes": peak_working_set(),
                    "measurement": (
                        "whole-process Windows peak working set, not incremental fitter allocation"
                    ),
                    "scope": (
                        "one synthetic experiment; "
                        "not supported-universe capacity or performance target"
                    ),
                }
            )
        generating = dcc.evaluate_fixed(data.z, data.target, (0.04, 0.91))
        report["simulation"] = {
            "construction": construction,
            "fit": asdict(fitted),
            "generating_parameter_score_on_estimated_target": generating.nll_sum,
            "interpretation": (
                "finite-sample diagnostic; no exact recovery/global optimum/calibration claim"
            ),
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--burden-output", type=Path)
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()
    if args.write_reference:
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_text(
            json.dumps(build_reference(), sort_keys=True, indent=2) + "\n",
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
        args.burden_output.parent.mkdir(parents=True, exist_ok=True)
        args.burden_output.write_text(
            json.dumps(burden, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    print("Synthetic DCC fitting qualification passed")


if __name__ == "__main__":
    main()
