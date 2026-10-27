"""Independent fixed-weight outcomes, forecast cutoffs, paired denominators and recovery."""

import importlib
import json
import math
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from prosper import industry
from prosper.innovations import InnovationContext, OHLCRow
from prosper.risk_qualification import ResearchFit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "scripts"))
        yield importlib.import_module("qualify_risk_study")


def context() -> InnovationContext:
    return InnovationContext(
        ("A", "B", "C"),
        ("2001-01-01",),
        "2001-01-01",
        "fictional",
        "UTC",
        "v1",
        "a" * 64,
        "fictional study test",
    )


def future() -> tuple[OHLCRow, ...]:
    return tuple(
        OHLCRow(
            "2001-01-02",
            sid,
            str(r),
            "1",
            "2",
            ".5",
            "1",
            "none",
            "a" * 64,
            "v1",
            "v1",
            "v1",
            "compatible-total-return-and-raw-ohlc",
        )
        for sid, r in zip(("A", "B", "C"), (0.1, -0.2, 0.3), strict=True)
    )


def covariance() -> industry.FrozenCovariance:
    return industry.FrozenCovariance(
        ("A", "B", "C"),
        ((0.04, 0.0, 0.0), (0.0, 0.09, 0.0), (0.0, 0.0, 0.16)),
        "2001-01-01",
        1,
        "cumulative",
        "stipulated test covariance",
        "fixed synthetic covariance",
    )


@pytest.mark.parametrize("cash,expected", [(False, 0.008125), (True, 0.008525)])
def test_fixed_portfolio_independent_quadratic_realization_and_selected_cash(
    probe: ModuleType, cash: bool, expected: float
) -> None:
    portfolio = {
        "name": "test",
        "stock_weights": [0.25, 0.5, 0.2 if cash else 0.25],
        "cash_weight": 0.05 if cash else 0,
    }
    value = probe.observation(
        "test",
        1,
        1,
        portfolio,
        [0.5, 0.25, 0.25],
        future(),
        covariance(),
        probe.taxonomy(context()),
    )
    assert value["predicted_cumulative_variance"] == pytest.approx(expected)
    # a=(-1/4,1/4,0), or (-1/4,1/4,-1/20) with selected cash.
    realized = (-0.075 - (0.015 if cash else 0)) ** 2
    assert value["realized_squared_return"] == pytest.approx(realized)
    assert value["loss"] == pytest.approx(math.log(expected) + realized / expected)
    assert value["annualized_equivalent_te"] == pytest.approx(math.sqrt(expected * 252))
    assert math.fsum(c["euler"] for c in value["attribution"]["sectors"]) == pytest.approx(
        math.sqrt(expected)
    )


def test_zero_active_keeps_zero_risk_and_undefined_loss(probe: ModuleType) -> None:
    portfolio = {"name": "zero-active", "stock_weights": [0.5, 0.25, 0.25], "cash_weight": 0}
    value = probe.observation(
        "test",
        1,
        1,
        portfolio,
        [0.5, 0.25, 0.25],
        future(),
        covariance(),
        probe.taxonomy(context()),
    )
    assert value["predicted_cumulative_variance"] == value["realized_squared_return"] == 0
    assert value["loss"] is None
    assert all(c["fraction_of_te"] is None for c in value["attribution"]["sectors"])


@pytest.mark.parametrize(
    "predicted,actual,zero",
    [(0.0, 1.0, False), (-1.0, 1.0, False), (1.0, float("nan"), False), (1.0, 0.0, True)],
)
def test_invalid_loss_does_not_turn_unknown_into_zero(
    probe: ModuleType, predicted: float, actual: float, zero: bool
) -> None:
    with pytest.raises(ValueError):
        probe.loss(predicted, actual, zero_active=zero)


def test_reordered_future_cutoff_and_psd_failures_are_not_scored(probe: ModuleType) -> None:
    p = {"name": "test", "stock_weights": [0.25, 0.5, 0.25], "cash_weight": 0}
    for rows in (
        tuple(reversed(future())),
        future()[:-1],
        tuple(replace(r, session="2001-01-01") for r in future()),
    ):
        with pytest.raises(ValueError):
            probe.observation(
                "test", 1, 1, p, [0.5, 0.25, 0.25], rows, covariance(), probe.taxonomy(context())
            )
    bad = replace(covariance(), matrix=((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    result = probe.observation(
        "test", 1, 1, p, [0.5, 0.25, 0.25], future(), bad, probe.taxonomy(context())
    )
    assert result["status"] == "unavailable"


def test_training_slice_is_unchanged_by_future_mutation(probe: ModuleType) -> None:
    plan = json.loads(probe.PLAN.read_bytes())
    original, rows = probe.study_source(plan)
    cutoff, training = probe.training_slice(original, rows, 1260, 1260)
    mutated = (*rows[:3780], *(replace(r, total_return="0.9") for r in rows[3780:]))
    later, same = probe.training_slice(original, mutated, 1260, 1260)
    assert later == cutoff and same == training
    assert cutoff.cutoff < rows[3780].session
    with pytest.raises(ValueError):
        probe.training_slice(original, rows, 1259, 1260)
    with pytest.raises(ValueError):
        probe.training_slice(original, tuple(reversed(rows)), 1260, 1260)


def test_paired_uncertainty_is_reproducible_and_preserves_constants(probe: ModuleType) -> None:
    settings = json.loads(probe.PLAN.read_bytes())["uncertainty"]
    value = probe.paired_interval([2.0] * 12, settings)
    assert value["mean_difference"] == 2 and value["interval"] == [2, 2]
    values = list(range(12))
    base = probe.paired_interval(values, settings)
    assert base == probe.paired_interval(values, settings)
    shifted = probe.paired_interval([v + 3 for v in values], settings)
    assert np.allclose(np.asarray(shifted["interval"]) - 3, base["interval"])
    with pytest.raises(ValueError):
        probe.paired_interval([float("nan")] * 12, settings)


def test_duplicate_model_origin_does_not_overwrite_an_outcome(probe: ModuleType) -> None:
    plan = json.loads(probe.PLAN.read_bytes())
    row = {
        "origin": 1260,
        "model": "idr",
        "horizon": 1,
        "portfolio": "fixed-tilt",
        "status": "scored",
        "loss": 1.0,
    }
    with pytest.raises(ValueError, match="duplicate"):
        probe.summaries([row, row], plan)


def test_failed_origins_retain_complete_denominator_without_fallback(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads(probe.PLAN.read_bytes())
    calls = []

    def refused(
        c: InnovationContext, rows: tuple[OHLCRow, ...], profile: Any, *, variant: Any
    ) -> ResearchFit:
        assert len(c.sessions) == 1260 and len(rows) == 3780
        assert c.cutoff == rows[-1].session
        calls.append((c.cutoff, variant))
        return ResearchFit("unavailable", ("injected fit failure",), variant, None, None)

    monkeypatch.setattr(probe, "fit_r1", refused)
    result = probe.forward_study(plan)
    assert len(calls) == 24 and len(set(calls)) == 24
    assert len(result["observations"]) == 12 * 4 * 2 * 3
    assert sum(r["status"] == "unavailable" for r in result["observations"]) == 12 * 4 * 2 * 2
    assert all(
        r["status"] == "unavailable-incomplete-pairs" and r["expected_origins"] == 12
        for r in result["paired_comparisons"]
    )
    assert "mean_difference" not in result["paired_comparisons"][0]


def test_fresh_synthetic_workload_completes_or_reports_exact_refusal(probe: ModuleType) -> None:
    for n in (3, 8, 603):
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/risk_workload.py"), "--names", str(n)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        assert result["names"] == n and result["coordinates"] == n * 1260
        if n == 3:
            assert result["status"] == "completed-service-only", result
            assert result["fitting_completed"] and result["recovery_without_refitting"]
            assert result["http_envelope_accepted"] and not result["application_fitting_completed"]
            assert result["upload_envelope_bytes"] <= result["history_http_body_limit"]
        else:
            assert result["status"] == "refused" and not result["fitting_completed"]
            assert result["stage"] == ("request" if n == 603 else "history_store_import")
            if n == 8:
                assert result["source_bytes"] > result["limits"]["history_original_source_bytes"]
                assert result["reason"] == "invalid_history_source_encoding"
        if sys.platform == "win32":
            assert result["process_peak_working_set_bytes"] > 0


def test_report_is_exclusive_and_old_result_is_not_recalculated(
    probe: ModuleType, tmp_path: Path
) -> None:
    output = tmp_path / "study.json"
    probe.write_report(output, {"known": 1, "unavailable": None})
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        probe.write_report(output, {"known": 2})
    assert output.read_bytes() == before


def test_worker_timeout_is_an_unavailable_requested_workload(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired("fictional worker", 1)

    monkeypatch.setattr(probe.subprocess, "run", timeout)
    results = probe.workloads({"workload_names": [603], "workload_timeout_seconds": 1})
    assert results[0]["status"] == "timeout" and not results[0]["fitting_completed"]
    assert results[0]["names"] == 603
