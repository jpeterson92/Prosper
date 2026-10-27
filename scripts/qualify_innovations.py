"""90/110-digit direct-expression corpus and synthetic component replay.

Reference construction never calls the transformation. --write-reference is an
explicit authoring operation, separate from the default frozen-corpus comparison.
No volatility fitter is implemented or executed here.
"""

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

from qualify_numerics import decimal_pi, scalar_oracle

from prosper.innovations import (
    IMPLEMENTATION_SHA256,
    SPECIFICATION_SHA256,
    InnovationContext,
    OHLCRow,
    regularized_innovation,
    transform_ohlc,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/synthetic/innovations/inputs.json"
REFERENCE = ROOT / "examples/synthetic/innovations/reference.json"
# Frozen before comparison: binary64 vs 90 digits; no fitted-model tolerance claim.
RTOL = 1e-8
ATOL = 1e-12


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_input() -> tuple[InnovationContext, tuple[OHLCRow, ...]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = fixture["context"]
    if hashlib.sha256(raw["construction"].encode()).hexdigest() != raw["source_sha256"]:
        raise AssertionError("construction attestation hash mismatch")
    for row in fixture["rows"]:
        text = fixture["action_construction"][f"{row['session']}/{row['security_id']}"]
        if hashlib.sha256(text.encode()).hexdigest() != row["action_evidence_sha256"]:
            raise AssertionError("action construction evidence hash mismatch")
    raw["sessions"] = tuple(raw["sessions"])
    raw["security_ids"] = tuple(raw["security_ids"])
    return InnovationContext(**raw), tuple(OHLCRow(**row) for row in fixture["rows"])


def reference_rows(rows: tuple[OHLCRow, ...], precision: int = 90) -> list[dict[str, str]]:
    """Literal P22 expressions in Decimal, independent of binary64 implementation."""
    with localcontext() as ctx:
        ctx.prec = precision
        results = []
        for row in rows:
            r, o, h, low, c = map(
                Decimal, (row.total_return, row.open, row.high, row.low, row.close)
            )
            p = c / (1 + r)
            overnight, range_log = (o / p).ln(), (h / low).ln()
            proxy = Decimal(17) / 25 * overnight**2 + Decimal(83) / 75 * (
                range_log**2 / (4 * Decimal(2).ln())
            )
            # Stable direct exponential identity for tanh, not production/libm.
            e = (-abs(10000 * r)).exp()
            sign = Decimal(1) if r >= 0 else Decimal(-1)
            x = sign * (1 - e) / (1 + e) * proxy.sqrt()
            results.append({"preceding_close": str(p), "proxy": str(proxy), "x": str(x)})
        return results


def fixed_state_reference(x_text: list[str], precision: int = 90) -> dict[str, Any]:
    """R1 seed/scoring and fixed-parameter forecast expressions, without a fitter."""
    with localcontext() as ctx:
        ctx.prec = precision
        x = [Decimal(v) for v in x_text]
        s2 = sum((v * v for v in x), Decimal(0)) / len(x)
        tau = math.isqrt(len(x)) + (math.isqrt(len(x)) ** 2 != len(x))
        weights = [(Decimal(47) / 50) ** Decimal(j) for j in range(tau)]
        seed = sum((w * v * v for w, v in zip(weights, x[:tau], strict=True)), Decimal(0)) / sum(
            weights
        )
        u, g, b = Decimal(".1"), Decimal(".2"), Decimal(".7")
        states = [seed]
        for previous in x[:-1]:
            states.append(u * s2 + g * previous * previous + b * states[-1])
        pi = decimal_pi()
        nll = [
            ((2 * pi).ln() + v.ln() + value * value / v) / 2
            for v, value in zip(states, x, strict=True)
        ]
        first = u * s2 + g * x[-1] * x[-1] + b * states[-1]
        persistence = g + b
        forecasts = [
            u * s2 * sum((persistence ** Decimal(j) for j in range(h - 1)), Decimal(0))
            + persistence ** Decimal(h - 1) * first
            for h in range(1, 22)
        ]
        return {
            "x": x_text,
            "s2": str(s2),
            "tau": tau,
            "seed": str(seed),
            "parameters_u_g_b": [str(u), str(g), str(b)],
            "variance": [str(v) for v in states],
            "nll": [str(v) for v in nll],
            "nll_sum": str(sum(nll)),
            "forecast_1_to_21": [str(v) for v in forecasts],
            "origin": "after final scored observation; first uses last x squared and variance",
            "units": "decimal innovation squared; Gaussian NLL includes all constants",
            "scoring": "all observations including the weighted initial variance",
        }


def build_reference() -> dict[str, Any]:
    context, rows = load_input()
    direct = reference_rows(rows)
    higher = reference_rows(rows, 110)
    # 90-digit arithmetic leaves ample headroom over binary64's ~16 digits.
    for left, right in zip(direct, higher, strict=True):
        for name in left:
            with localcontext() as ctx:
                ctx.prec = 110
                a, b = Decimal(left[name]), Decimal(right[name])
                if abs(a - b) > Decimal("1e-85") * max(abs(b), Decimal(1)):
                    raise AssertionError("reference precision disagreement")
    scalar = scalar_oracle()
    fractions = [Fraction(v) for v in scalar["x"]]
    states = [Fraction(v) for v in scalar["variance_fractions"]]
    s2 = Fraction(scalar["s2"])
    first = s2 / 10 + fractions[-1] ** 2 / 5 + 7 * states[-1] / 10
    scalar["forecast_1_to_21_fractions"] = [
        str(
            s2 / 10 * sum((Fraction(9, 10) ** j for j in range(h - 1)), Fraction(0))
            + Fraction(9, 10) ** (h - 1) * first
        )
        for h in range(1, 22)
    ]
    with localcontext() as ctx:
        ctx.prec = 90
        e07_r = Decimal(3).ln() / 2
        toy = {
            "kappa": "2",
            "r_plus": str(e07_r),
            "proxy": "4",
            "x_plus": "1",
            "x_minus": "-1",
            "x_zero": "0",
            "identity": "E07-toy-not-R1",
        }
    return {
        "version": "synthetic-idr-reference-v1",
        "expected_status": "ready",
        "shape": [len(context.sessions), len(context.security_ids)],
        "ordered_security_ids": list(context.security_ids),
        "cutoff": context.cutoff,
        "units": "decimal innovations; decimal squared proxy/variance",
        "profile": {"identity": "R1", "f": "0.25", "a3": "0.17", "kappa": "10000"},
        "input_sha256": digest(FIXTURE),
        "specification_sha256": SPECIFICATION_SHA256,
        "sources": {
            "P22": "157f75f74ebabf154a3d0b7d3f0652f6e90cba43906702cafe8ea211a5a43522",
            "locators": "P22 4.7, 3.2-3.6; R1 seed/scoring; E01/E02/E07-E09",
        },
        "precision": "90 Decimal digits; independent 110-digit re-evaluation within 1e-85",
        "tolerance": {
            "rtol": RTOL,
            "atol": ATOL,
            "scale": "preceding close: reference price; proxy/x: 1 decimal analytical unit",
        },
        "rows": direct,
        "E07": toy,
        "E08_price_only": {
            "return": "-0.01",
            "close": "99",
            "preceding_close": "100",
            "convention": "simple-price-return-decimal",
            "expected_status": "unavailable",
            "reason": "price-only input is refused by the total-return interface",
        },
        "E01": {
            "omega": "1",
            "g": "1/4",
            "b": "1/2",
            "prior_x2": "4",
            "prior_variance": "4",
            "next_variance": "4",
            "forecast_1_to_21": ["4"] * 21,
        },
        "stack_fixed_state": scalar,
        "idr_fixed_state": [
            fixed_state_reference([row["x"] for row in direct[j :: len(context.security_ids)]])
            for j in range(len(context.security_ids))
        ],
    }


def qualify() -> dict[str, Any]:
    expected = json.loads(REFERENCE.read_text(encoding="utf-8"))
    # Explicitly recompute the independent route before the component is called.
    if expected != build_reference():
        raise AssertionError("frozen reference/input mismatch")
    context, rows = load_input()
    result = transform_ohlc(context, rows)
    if result.status != "ready":
        raise AssertionError(result.issues)
    errors = []
    for name, matrix in (
        ("preceding_close", result.preceding_close),
        ("proxy", result.proxy),
        ("x", result.innovations),
    ):
        for actual, reference in zip(
            (v for row in matrix for v in row), expected["rows"], strict=True
        ):
            value = float(reference[name])
            scale = abs(value) if name == "preceding_close" else 1.0
            error = abs(actual - value)
            if not math.isfinite(actual) or error > ATOL * scale + RTOL * abs(value):
                raise AssertionError((name, actual, value))
            errors.append(error)
    toy = expected["E07"]
    for sign in (-1, 0, 1):
        value = regularized_innovation(sign * float(toy["r_plus"]), 4, 2)
        if abs(value - sign) > ATOL:
            raise AssertionError("E07 toy sign/zero")
    return {
        "input_sha256": digest(FIXTURE),
        "reference_sha256": digest(REFERENCE),
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "reference_implementation_sha256": digest(Path(__file__)),
        "stack_reference_sha256": digest(ROOT / "scripts/qualify_numerics.py"),
        "specification_sha256": SPECIFICATION_SHA256,
        "current_specification_document_sha256": hashlib.sha256(
            (ROOT / "docs/tasks/T006.2.1.1-python-numerical-spec.md").read_bytes()
        ).hexdigest(),
        "runtime": platform.python_version(),
        "result": asdict(result),
        "max_absolute_error": max(errors),
        "scope": "synthetic transformation and fixed-state references; no fitted estimator",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-reference", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.write_reference:
        REFERENCE.write_text(
            json.dumps(build_reference(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print("Authored independent synthetic reference corpus")
        return
    report = json.dumps(qualify(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print("Synthetic OHLC/reference checks passed")


if __name__ == "__main__":
    main()
