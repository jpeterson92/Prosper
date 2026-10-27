"""Predeclared fictional fixed-portfolio forward study; never real calibration.

Every forecast uses only its rolling training slice. The evaluation grid and
paired uncertainty retain failed observations rather than selecting successes.
Workload workers run separately and retain first refusal/timeout dimensions.
"""

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import scipy  # type: ignore[import-untyped]
from qualify_risk_profile import MANIFEST, source

from prosper import industry, volatility
from prosper.innovations import InnovationContext, OHLCRow, fingerprint
from prosper.modeled_inputs import InputProfile
from prosper.risk_qualification import Variant, fit_r1, profile_issues

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "examples/synthetic/dcc/fixed-study-plan.json"


def study_source(plan: dict[str, Any]) -> tuple[InnovationContext, tuple[OHLCRow, ...]]:
    manifest = json.loads(MANIFEST.read_bytes())
    manifest.update(
        seed=plan["seed"], observations=plan["training_sessions"] + plan["evaluation_sessions"]
    )
    context, original = source(manifest)
    construction = {
        "base": context.construction,
        "stress": plan["stress"],
        "version": plan["version"],
    }
    context = replace(
        context,
        source_sha256=fingerprint(construction),
        construction=json.dumps(construction, sort_keys=True),
    )
    stress, previous = plan["stress"], [100.0] * len(context.security_ids)
    rows = []
    for index, row in enumerate(original):
        t, j = divmod(index, len(context.security_ids))
        factor = (
            stress["return_and_log_range_multiplier"]
            if stress["start"] <= t < stress["stop"]
            else 1
        )
        old_return = float(row.total_return)
        old_previous = float(row.close) / (1 + old_return)
        r = factor * old_return
        opening = previous[j] * (float(row.open) / old_previous) ** factor
        close = previous[j] * (1 + r)
        high = (
            max(opening, close)
            * (float(row.high) / max(float(row.open), float(row.close))) ** factor
        )
        low = (
            min(opening, close)
            * (float(row.low) / min(float(row.open), float(row.close))) ** factor
        )
        rows.append(
            replace(
                row,
                total_return=repr(r),
                open=repr(opening),
                high=repr(high),
                low=repr(low),
                close=repr(close),
            )
        )
        previous[j] = close
    return context, tuple(rows)


def training_slice(
    context: InnovationContext, rows: tuple[OHLCRow, ...], origin: int, window: int
) -> tuple[InnovationContext, tuple[OHLCRow, ...]]:
    n = len(context.security_ids)
    if window != 1260 or origin < window or origin >= len(context.sessions):
        raise ValueError("explicit complete R1 training window and future evaluation required")
    sessions = context.sessions[origin - window : origin]
    selected = rows[(origin - window) * n : origin * n]
    frozen = replace(context, sessions=sessions, cutoff=sessions[-1])
    if tuple((r.session, r.security_id) for r in selected) != tuple(
        (s, i) for s in sessions for i in context.security_ids
    ):
        raise ValueError("complete ordered source window required")
    # Bind only actual training facts, never the evaluation values or their hash.
    frozen = replace(frozen, source_sha256=fingerprint([asdict(r) for r in selected]))
    return frozen, selected


def loss(predicted: float, realized_squared: float, *, zero_active: bool) -> float | None:
    if (
        not all(math.isfinite(v) for v in (predicted, realized_squared))
        or min(predicted, realized_squared) < 0
    ):
        raise ValueError("finite nonnegative variance/outcome required")
    if zero_active:
        if predicted != 0 or realized_squared != 0:
            raise ValueError("zero-active result must be exactly zero")
        return None
    if predicted <= 0:
        raise ValueError("positive forecast variance required for loss")
    value = math.log(predicted) + realized_squared / predicted
    if not math.isfinite(value):
        raise ValueError("unrepresentable loss")
    return value


def paired_interval(differences: list[float], settings: dict[str, Any]) -> dict[str, Any]:
    values = np.asarray(differences, dtype=float)
    n, block = len(values), settings["block_origins"]
    if n < block or not np.isfinite(values).all() or block < 1:
        raise ValueError("finite chronological paired differences and valid block required")
    rng = np.random.Generator(np.random.PCG64(settings["seed"]))
    starts = rng.integers(0, n, size=(settings["draws"], math.ceil(n / block)))
    indices = ((starts[:, :, None] + np.arange(block)) % n).reshape(settings["draws"], -1)[:, :n]
    means = values[indices].mean(axis=1)
    return {
        "mean_difference": float(values.mean()),
        "interval": np.quantile(means, settings["quantiles"]).tolist(),
        "paired_origins": n,
    }


def taxonomy(context: InnovationContext) -> industry.Taxonomy:
    return industry.Taxonomy(
        "fictional-study",
        "v1",
        context.sessions[0],
        fingerprint(["fictional-study-taxonomy"]),
        tuple(
            industry.Classification(
                sid,
                "group-a" if j < 2 else "group-b",
                f"industry-{j}",
                context.sessions[0],
                context.sessions[0],
                "stipulated fictional group",
            )
            for j, sid in enumerate(context.security_ids)
        ),
        tuple(
            ("group-a" if j < 2 else "group-b", f"industry-{j}")
            for j in range(len(context.security_ids))
        ),
    )


def observation(
    model: str,
    origin: int,
    horizon: int,
    portfolio: dict[str, Any],
    benchmark: list[float],
    future: tuple[OHLCRow, ...],
    covariance: industry.FrozenCovariance,
    groups: industry.Taxonomy,
) -> dict[str, Any]:
    weights = industry.EstimatedWeights(
        covariance.security_ids,
        tuple(portfolio["stock_weights"]),
        tuple(benchmark),
        portfolio["cash_weight"],
        0,
        covariance.cutoff,
    )
    result = industry.estimate(weights, groups, covariance=covariance)
    if result.issues or result.attribution is None:
        return {
            "model": model,
            "origin": origin,
            "horizon": horizon,
            "portfolio": portfolio["name"],
            "status": "unavailable",
            "issues": result.issues,
        }
    attribution = result.attribution
    active = np.asarray(portfolio["stock_weights"]) - np.asarray(benchmark)
    n = len(active)
    if len(future) != horizon * n or tuple((r.session, r.security_id) for r in future) != tuple(
        (s, i) for s in dict.fromkeys(r.session for r in future) for i in covariance.security_ids
    ):
        raise ValueError("complete ordered evaluation grid required")
    if future[0].session <= covariance.cutoff:
        raise ValueError("evaluation must be strictly after the forecast cutoff")
    returns = np.asarray([float(r.total_return) for r in future]).reshape(horizon, n)
    realized = float(np.sum(returns @ active)) ** 2
    expected = float(active @ np.asarray(covariance.matrix) @ active)
    if not math.isclose(attribution.variance, expected, rel_tol=1e-10, abs_tol=1e-16):
        raise AssertionError("independent fixed-weight quadratic disagrees")
    for group in (attribution.securities, attribution.sectors, attribution.industries):
        if not math.isclose(
            math.fsum(c.euler for c in group),
            attribution.tracking_error,
            rel_tol=1e-10,
            abs_tol=1e-14,
        ):
            raise AssertionError("Euler contributions do not reconcile")
    return {
        "model": model,
        "origin": origin,
        "horizon": horizon,
        "portfolio": portfolio["name"],
        "status": "scored",
        "cutoff": covariance.cutoff,
        "evaluation_start": future[0].session,
        "evaluation_end": future[-1].session,
        "predicted_cumulative_variance": attribution.variance,
        "realized_squared_return": realized,
        "annualized_equivalent_te": math.sqrt(attribution.variance * 252 / horizon),
        "loss": loss(attribution.variance, realized, zero_active=bool(np.all(active == 0))),
        "attribution": asdict(attribution),
    }


def summaries(records: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    origins = list(
        range(
            plan["training_sessions"],
            plan["training_sessions"] + plan["evaluation_sessions"],
            plan["origin_stride"],
        )
    )
    for horizon in plan["horizons"]:
        for portfolio in plan["portfolios"]:
            if portfolio["name"] == "zero-active":
                continue
            for reference in plan["models"][1:]:
                selected = {
                    (r["origin"], r["model"]): r
                    for r in records
                    if r["horizon"] == horizon and r["portfolio"] == portfolio["name"]
                }
                if len(selected) != sum(
                    r["horizon"] == horizon and r["portfolio"] == portfolio["name"] for r in records
                ):
                    raise ValueError("duplicate origin/model observations")
                pairs = [(selected.get((o, "idr")), selected.get((o, reference))) for o in origins]
                complete = all(
                    a is not None
                    and b is not None
                    and a["status"] == b["status"] == "scored"
                    and a["loss"] is not None
                    and b["loss"] is not None
                    for a, b in pairs
                )
                summary = {
                    "horizon": horizon,
                    "portfolio": portfolio["name"],
                    "comparison": f"idr-minus-{reference}",
                    "expected_origins": len(origins),
                    "status": "complete" if complete else "unavailable-incomplete-pairs",
                }
                if complete:
                    diffs = [
                        a["loss"] - b["loss"] for a, b in pairs if a is not None and b is not None
                    ]
                    summary.update(paired_interval(diffs, plan["uncertainty"]))
                    for label, during in (("stress", True), ("post_stress", False)):
                        group = [
                            d
                            for origin, d in zip(origins, diffs, strict=True)
                            if (plan["stress"]["start"] <= origin < plan["stress"]["stop"])
                            == during
                        ]
                        summary[label + "_mean_difference"] = (
                            float(np.mean(group)) if group else None
                        )
                summaries.append(summary)
    return summaries


def forward_study(plan: dict[str, Any]) -> dict[str, Any]:
    context, rows = study_source(plan)
    profile = InputProfile.model_validate(json.loads(MANIFEST.read_bytes())["profile"])
    groups, n = taxonomy(context), len(context.security_ids)
    records, fits, sensitivity = [], [], []
    window = plan["training_sessions"]
    for origin in range(window, len(context.sessions), plan["origin_stride"]):
        frozen, training = training_slice(context, rows, origin, window)
        train_returns = np.asarray([float(r.total_return) for r in training]).reshape(window, n)
        simple = train_returns.T @ train_returns / window
        for variant in ("idr", "returns-only", "static-zero-mean-sample"):
            matrices: dict[int, industry.FrozenCovariance] = {}
            if variant == "static-zero-mean-sample":
                for h in plan["horizons"]:
                    matrix = tuple(tuple(float(v) for v in row) for row in simple * h)
                    matrices[h] = industry.FrozenCovariance(
                        frozen.security_ids,
                        matrix,
                        frozen.cutoff,
                        h,
                        "cumulative",
                        fingerprint([frozen.source_sha256, variant, h]),
                        "constant daily sample covariance; validation reference only",
                    )
            else:
                fit = fit_r1(frozen, training, profile, variant=cast(Variant, variant))
                result = fit.covariance
                fit_record: dict[str, Any] = {
                    "origin": origin,
                    "variant": variant,
                    "status": fit.status,
                    "issues": fit.issues,
                    "training_start": frozen.sessions[0],
                    "cutoff": frozen.cutoff,
                    "source_identity": frozen.source_sha256,
                }
                if result is not None:
                    fit_record["scalars"] = [
                        {
                            "security_id": s.data.security_id,
                            "status": s.status,
                            "selected_start": s.selected_start,
                            "parameters": s.path.parameters_u_g_b if s.path else None,
                            "starts": [asdict(start) for start in s.starts],
                        }
                        for s in result.scalars
                    ]
                    fit_record["dcc_starts"] = (
                        [asdict(s) for s in result.dcc_fit.starts] if result.dcc_fit else []
                    )
                    fit_record["identity"] = result.identity_sha256
                fits.append(fit_record)
                if result is not None and result.projection is not None:
                    for h in plan["horizons"]:
                        matrices[h] = industry.from_composition(
                            result, "one_session" if h == 1 else "cumulative"
                        )
                    for scalar in result.scalars:
                        path = scalar.path
                        assert path is not None
                        _, g, b = path.parameters_u_g_b
                        alternative = volatility.evaluate_fixed(
                            path.x, path.parameters_u_g_b, initial_variance=path.omega / (1 - g - b)
                        )
                        sensitivity.append(
                            {
                                "origin": origin,
                                "variant": variant,
                                "security_id": scalar.data.security_id,
                                "kind": "fixed-parameters alternative seed; no refit",
                                "initial_variance_difference": alternative.seed - path.seed,
                                "next_variance_relative_difference": volatility.forecast_variance(
                                    alternative, 1
                                )[0]
                                / volatility.forecast_variance(path, 1)[0]
                                - 1,
                            }
                        )
            for h in plan["horizons"]:
                for portfolio in plan["portfolios"]:
                    if h not in matrices:
                        records.append(
                            {
                                "model": variant,
                                "origin": origin,
                                "horizon": h,
                                "portfolio": portfolio["name"],
                                "status": "unavailable",
                                "issues": ["fit unavailable; no fallback"],
                            }
                        )
                    else:
                        records.append(
                            observation(
                                variant,
                                origin,
                                h,
                                portfolio,
                                plan["benchmark"],
                                rows[origin * n : (origin + h) * n],
                                matrices[h],
                                groups,
                            )
                        )
    baseline, _ = training_slice(context, rows, window, window)
    return {
        "source": {"context": asdict(context), "rows": [asdict(r) for r in rows]},
        "fits": fits,
        "observations": records,
        "paired_comparisons": summaries(records, plan),
        "sensitivity": sensitivity,
        "profile_refusals": {
            "short": profile_issues(
                profile, replace(context, sessions=context.sessions[:3]), "idr"
            ),
            "changed": profile_issues(
                profile.model_copy(update={"annualization_sessions": 365}), baseline, "idr"
            ),
        },
        "qualified_actual_input_calibration": "unavailable; synthetic harness only",
    }


def workloads(plan: dict[str, Any]) -> list[dict[str, Any]]:
    reports = []
    for n in plan["workload_names"]:
        try:
            run = subprocess.run(
                [sys.executable, str(ROOT / "scripts/risk_workload.py"), "--names", str(n)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=plan["workload_timeout_seconds"],
            )
            if run.returncode:
                reports.append(
                    {
                        "names": n,
                        "sessions": 1260,
                        "status": "worker-failed",
                        "returncode": run.returncode,
                    }
                )
            else:
                reports.append(json.loads(run.stdout))
        except subprocess.TimeoutExpired:
            reports.append(
                {
                    "names": n,
                    "sessions": 1260,
                    "status": "timeout",
                    "fitting_completed": False,
                    "stage": "unknown at termination; no capacity claim",
                }
            )
    return reports


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Existing reports remain immutable. A fresh run requires a new destination.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workloads-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Existing report preserved; choose a new output path")
    raw = PLAN.read_bytes()
    plan = json.loads(raw)
    report = {
        "plan": plan,
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "scope": "synthetic local study; no real calibration/capacity acceptance",
        "qualifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if not args.workloads_only:
        report["study"] = forward_study(plan)
    report["workloads"] = workloads(plan)
    write_report(args.output, report)
    print("Synthetic study saved; inspect unavailable outcomes and claim-specific gates")


if __name__ == "__main__":
    main()
