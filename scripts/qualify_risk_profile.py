"""Matched full-window R1 IDR/reference comparison on one fictional OHLC source.

Independent expressions/library density calculations check selected states and
scores, not fitted optima, author-runtime parity or independent model acceptance.
No holdout evaluation, financial calibration or workload qualification occurs.
"""

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]
from numpy.typing import NDArray
from qualify_covariance import decimal_forecast
from qualify_innovations import reference_rows
from qualify_shrinkage import reference_spectrum
from qualify_volatility import decimal_objective
from scipy import stats

from prosper import covariance as cv
from prosper import dcc
from prosper.innovations import InnovationContext, OHLCRow, fingerprint
from prosper.modeled_inputs import InputProfile
from prosper.risk_qualification import ResearchFit, fit_r1

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/synthetic/dcc/profile-comparison.json"
Array = NDArray[np.float64]
FIXED_DCC = (0.04, 0.91)


def source(manifest: dict[str, Any]) -> tuple[InnovationContext, tuple[OHLCRow, ...]]:
    """PCG64 normal shocks; explicit synthetic raw/return/overnight construction.

    This daily grid includes weekends deliberately; it is not a real calendar.
    No prices/actions/identity or performance inference comes from this source.
    """
    rng = np.random.Generator(np.random.PCG64(manifest["seed"]))
    count, ids = manifest["observations"], tuple(manifest["security_ids"])
    shocks = rng.standard_normal((count, len(ids) + 1))
    first = date.fromisoformat(manifest["first_session"])
    sessions = tuple((first + timedelta(days=t)).isoformat() for t in range(count))
    construction = {
        "generator": "PCG64 normal; shared/idiosyncratic shocks; scalar GARCH price construction",
        "version": manifest["version"],
        "seed": manifest["seed"],
        "shape": [count, len(ids)],
        "calendar": "fictional-all-days",
        "action": "none; compatible simple total return equals price return",
        "initial_close": 100,
        "initial_variance": 0.0001,
        "variance_update": "0.000002 + .06*r*r + .92*v",
        "overnight_log": ".3*r + .001*idiosyncratic_shock",
        "range_padding": ".001 + .002*abs(common_shock)",
    }
    context = InnovationContext(
        ids,
        sessions,
        sessions[-1],
        "fictional-all-days",
        "UTC",
        "fictional-r1-v1",
        fingerprint(construction),
        json.dumps(construction, sort_keys=True),
    )
    previous, variance = [100.0] * len(ids), [0.0001] * len(ids)
    rows = []
    for t, session in enumerate(sessions):
        for j, security_id in enumerate(ids):
            shock = (shocks[t, 0] + shocks[t, j + 1]) / math.sqrt(2)
            r = math.sqrt(variance[j]) * float(shock)
            close = previous[j] * (1 + r)
            opening = previous[j] * math.exp(0.3 * r + 0.001 * float(shocks[t, j + 1]))
            padding = 0.001 + 0.002 * abs(float(shocks[t, 0]))
            high, low = max(opening, close) * (1 + padding), min(opening, close) / (1 + padding)
            rows.append(
                OHLCRow(
                    session,
                    security_id,
                    repr(r),
                    repr(opening),
                    repr(high),
                    repr(low),
                    repr(close),
                    "none",
                    fingerprint(["fictional-no-action", session, security_id]),
                    context.vintage,
                    context.vintage,
                    context.vintage,
                    "compatible-total-return-and-raw-ohlc",
                )
            )
            previous[j] = close
            variance[j] = 0.000002 + 0.06 * r * r + 0.92 * variance[j]
    return context, tuple(rows)


def check(actual: Any, expected: Any, *, rtol: float, atol: float) -> float:
    a, e = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if a.shape != e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():
        raise AssertionError("reference shape/nonfinite mismatch")
    if not np.allclose(a, e, rtol=rtol, atol=atol):
        raise AssertionError(f"reference comparison failed; max error {float(np.max(abs(a - e)))}")
    return float(np.max(abs(a - e)))


def scalar_states(x: tuple[float, ...], theta: tuple[float, ...]) -> Array:
    """Full closed convolution, including T+1; no production variance recurrence."""
    values = np.asarray(x)
    squares = values * values
    s2 = math.fsum(squares) / len(x)
    tau = math.isqrt(len(x)) + (math.isqrt(len(x)) ** 2 != len(x))
    weights = [0.94**j for j in range(tau)]
    seed = math.fsum(w * v for w, v in zip(weights, squares[:tau], strict=True)) / math.fsum(
        weights
    )
    u, g, b = theta
    powers = b ** np.arange(len(x) + 1)
    sums = np.concatenate(([0.0], np.cumsum(powers[:-1])))
    lagged = np.concatenate(([0.0], np.convolve(squares, powers)[: len(x)]))
    return np.asarray(powers * seed + u * s2 * sums + g * lagged, dtype=np.float64)


def dcc_states(z: Array, target: Array, theta: tuple[float, ...]) -> Array:
    """All full Q states via finite convolution; includes last-scored and T+1."""
    a, b = theta
    t, n = z.shape
    powers = b ** np.arange(t + 1)
    coefficient = powers + (1 - a - b) * np.concatenate(([0.0], np.cumsum(powers[:-1])))
    states = coefficient[:, None, None] * target[None, :, :]
    for i in range(n):
        for j in range(n):
            lagged = np.concatenate(([0.0], np.convolve(z[:, i] * z[:, j], powers)[:t]))
            states[:, i, j] += a * lagged
    return np.asarray(states, dtype=np.float64)


def compare_fit(fit: ResearchFit, limits: dict[str, float]) -> dict[str, Any]:
    """Separate selected-output references; no production evaluator supplies truth."""
    innovation, result = fit.innovation, fit.covariance
    if innovation is None or result is None or result.projection is None:
        return {"status": "unavailable", "issues": fit.issues, "fit": asdict(fit)}
    assert result.dcc_fit is not None and result.dcc_fit.evaluation is not None
    rtol, absolute = limits["rtol"], limits["objective_atol"]
    # Reuse the already qualified 90-digit literal P22 expressions on every source row.
    reference = reference_rows(innovation.source_rows)
    x = np.asarray(
        [
            float(v["x"]) if fit.variant == "idr" else float(row.total_return)
            for v, row in zip(reference, innovation.source_rows, strict=True)
        ]
    ).reshape(len(innovation.context.sessions), -1)
    errors: dict[str, Any] = {
        "innovation": check(innovation.innovations, x, rtol=rtol, atol=1e-12),
    }
    scalar_reports, standardized, next_variance, omega, persistence = [], [], [], [], []
    for j, scalar in enumerate(result.scalars):
        path = scalar.path
        assert path is not None
        # Isolate scalar score accuracy at its actual supplied binary64 x.
        objective = decimal_objective(
            path.x, tuple(Decimal.from_float(v) for v in path.parameters_u_g_b)
        )
        state = scalar_states(tuple(float(v) for v in x[:, j]), path.parameters_u_g_b)
        scale = float(np.max(state))
        state_error = check(path.variance, state[:-1], rtol=rtol, atol=1e-12 * scale)
        score_error = check(path.nll_sum, str(objective), rtol=rtol, atol=absolute)
        density = -stats.norm.logpdf(x[:, j], loc=0, scale=np.sqrt(state[:-1]))
        check(path.nll, density, rtol=rtol, atol=absolute)
        standardized.append(x[:, j] / np.sqrt(state[:-1]))
        next_variance.append(float(state[-1]))
        omega.append(path.parameters_u_g_b[0] * math.fsum(v * v for v in x[:, j]) / len(x))
        persistence.append(sum(path.parameters_u_g_b[1:]))
        scalar_reports.append(
            {
                "security_id": scalar.data.security_id,
                "input_identity": scalar.data.innovation_identity_sha256,
                "parameters_u_g_b": path.parameters_u_g_b,
                "selected_start": scalar.selected_start,
                "starts": [asdict(s) for s in scalar.starts],
                "nll_sum": path.nll_sum,
                "decimal_reference_nll_sum": str(objective),
                "max_variance_error": state_error,
                "objective_error": score_error,
                "objective_range": scalar.objective_range,
                "parameter_ranges": scalar.parameter_ranges,
            }
        )
    z = np.asarray(standardized).T
    # NumPy eigensystem versus the production SciPy/scaled-Gram route; spectral
    # formulas use the existing independent Decimal oracle. This shares LAPACK
    # methodology and is not an independent eigensolver/model review.
    eigenvalues, vectors = np.linalg.eigh(z.T @ z / len(z))
    d = np.asarray(
        reference_spectrum(len(z), z.shape[1], [repr(float(v)) for v in eigenvalues]), dtype=float
    )
    target_cov = (vectors * d) @ vectors.T
    sd = np.sqrt(np.diag(target_cov))
    target = target_cov / sd[:, None] / sd[None, :]
    fitted = result.dcc_fit
    assert fitted.evaluation is not None
    errors["target_correlation"] = check(
        fitted.data.target, target, rtol=rtol, atol=limits["correlation_atol"]
    )
    errors["standardized"] = check(fitted.data.z, z, rtol=rtol, atol=limits["correlation_atol"])
    states = dcc_states(z, target, fitted.evaluation.parameters)
    nll = density_scores(z, states)
    fixed_states = dcc_states(z, target, FIXED_DCC)
    fixed_scores = density_scores(z, fixed_states)
    fixed = dcc.evaluate_fixed(fitted.data.z, fitted.data.target, FIXED_DCC)
    terminal, next_q = cv.replay_full(fitted.data.z, fitted.data.target, FIXED_DCC)
    errors["nonzero_dcc_nll"] = check(fixed.nll, fixed_scores, rtol=rtol, atol=absolute)
    errors["nonzero_dcc_terminal_q"] = check(
        terminal, fixed_states[-2], rtol=rtol, atol=limits["correlation_atol"]
    )
    errors["nonzero_dcc_next_q"] = check(
        next_q, fixed_states[-1], rtol=rtol, atol=limits["correlation_atol"]
    )
    errors["dcc_nll"] = check(fitted.evaluation.nll, nll, rtol=rtol, atol=absolute)
    errors["dcc_objective"] = check(
        fitted.evaluation.nll_sum, math.fsum(nll), rtol=rtol, atol=absolute
    )
    errors["terminal_q"] = check(
        result.terminal_q, states[-2], rtol=rtol, atol=limits["correlation_atol"]
    )
    errors["next_q"] = check(result.next_q, states[-1], rtol=rtol, atol=limits["correlation_atol"])
    case = {
        "target": target.tolist(),
        "next_q": states[-1].tolist(),
        "variance_one": next_variance,
        "omega": omega,
        "persistence": persistence,
        "dcc_persistence": sum(fitted.evaluation.parameters),
    }
    projections = {}
    for horizon in (1, 21):
        projected = cv.compose_covariance(result.scalars, fitted, horizon=horizon)
        assert projected.projection is not None, projected.issues
        expected = decimal_forecast(case, horizon)
        projection_errors = {}
        for field, matrix in expected.items():
            scale = float(np.max(np.abs(np.asarray(matrix, dtype=float))))
            projection_errors[field] = check(
                getattr(projected.projection, field),
                matrix,
                rtol=rtol,
                atol=limits["covariance_scale_atol"] * scale,
            )
        projections[str(horizon)] = {
            "result": asdict(projected.projection),
            "max_errors": projection_errors,
        }
    return {
        "status": "compared",
        "innovation_identity": innovation.identity_sha256,
        "source_input_identity": innovation.input_sha256,
        "variant": fit.variant,
        "units": innovation.units,
        "security_ids": result.security_ids,
        "cutoff": result.cutoff,
        "scalars": scalar_reports,
        "dcc_starts": [asdict(s) for s in fitted.starts],
        "dcc_selected_start": fitted.selected_start,
        "dcc_parameters": fitted.evaluation.parameters,
        "dcc_objective": fitted.evaluation.nll_sum,
        "dcc_reference_objective": math.fsum(nll),
        "dcc_objective_range": fitted.objective_range,
        "dcc_parameter_ranges": fitted.parameter_ranges,
        "nonzero_dcc": {
            "parameters": FIXED_DCC,
            "terminal_q": terminal,
            "next_q": next_q,
            "objective": fixed.nll_sum,
            "reference_objective": math.fsum(fixed_scores),
        },
        "target": fitted.data.target,
        "terminal_q": result.terminal_q,
        "next_q": result.next_q,
        "errors": errors,
        "projections": projections,
        "result_identity": result.identity_sha256,
    }


def density_scores(z: Array, states: Array) -> list[float]:
    """Library Gaussian densities, with the specified adjacent-pair mean/time sum."""
    nll = []
    for t, row in enumerate(z):
        terms = []
        for i in range(len(row) - 1):
            j = i + 1
            rho = states[t, i, j] / math.sqrt(states[t, i, i] * states[t, j, j])
            terms.append(
                -float(
                    stats.multivariate_normal.logpdf(
                        row[[i, j]], mean=[0, 0], cov=[[1, rho], [rho, 1]]
                    )
                )
            )
        nll.append(math.fsum(terms) / len(terms))
    return nll


def qualify() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    context, rows = source(manifest)
    profile = InputProfile.model_validate(manifest["profile"])
    fits = [fit_r1(context, rows, profile, variant=v) for v in ("idr", "returns-only")]
    compared = [compare_fit(fit, manifest["comparison"]) for fit in fits]
    return {
        "scope": (
            "matched synthetic R1 selected-output comparison; "
            "no calibrated risk or independent review"
        ),
        "status": "passed" if all(v["status"] == "compared" for v in compared) else "unavailable",
        "manifest": manifest,
        "source": {"context": asdict(context), "rows": [asdict(r) for r in rows]},
        "source_identity": fingerprint([asdict(context), [asdict(r) for r in rows]]),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "qualifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sources": {
            name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
            for name in (
                "qualify_covariance.py",
                "qualify_innovations.py",
                "qualify_shrinkage.py",
                "qualify_volatility.py",
                "qualify_numerics.py",
            )
        },
        "variants": compared,
        "reference_limits": [
            "Same-agent expressions/library comparison; no author-runtime or fitted-optimum parity",
            "NumPy/SciPy eigensystems share LAPACK methodology",
            "Existing fixed-state/derivative/rank/endpoint tests remain separate evidence",
            "No untouched forward period, enhancement claim, real inputs or capacity qualification",
            "Marks/freshness/taxonomy/investor controls are outside this numerical experiment",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = qualify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if report["status"] != "passed":
        raise SystemExit("Risk profile comparison unavailable; see retained diagnostics")
    print("Matched synthetic R1 IDR/returns-only comparison passed")


if __name__ == "__main__":
    main()
