"""Independent endpoint expectations and refusals for dated proxy weights; no fits."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from prosper.benchmark_drift import weights_at
from prosper.history_table import HistoryTable
from prosper.modeled_inputs import FrozenModeledInputs
from tests.test_modeled_inputs import command, seed, service


@pytest.fixture
def frozen(tmp_path: Path) -> FrozenModeledInputs:
    workspace = service(tmp_path / "workspace")
    seed(workspace)
    run = workspace.diagnose_inputs(command())
    return workspace.store.modeled_inputs(run.inputs["modeled_inputs"])


def test_total_return_reinvestment_normalization_and_source_preservation(
    frozen: FrozenModeledInputs,
) -> None:
    benchmark, alignment = frozen.benchmark, frozen.alignment
    assert benchmark is not None and alignment is not None
    original = benchmark.model_dump_json()
    # End-point adjusted closes supply an independent Decimal reference:
    # 60*(198/200) and 30*(208/210), regardless of intermediate path.
    a, b = Decimal(60) * Decimal(198) / 200, Decimal(30) * Decimal(208) / 210
    result = weights_at(benchmark, alignment, "2026-10-23")
    assert not result.issues and result.weights is not None
    assert result.weights == pytest.approx(
        {"FICTIONAL-0": float(a / (a + b)), "FICTIONAL-1": float(b / (a + b))}
    )
    assert benchmark.model_dump_json() == original
    assert result.warning and "constituent distributions reinvested" in result.warning


def test_same_date_needs_no_drift_and_future_holdings_are_refused(
    frozen: FrozenModeledInputs,
) -> None:
    benchmark = frozen.benchmark
    assert benchmark is not None
    same = weights_at(benchmark, None, benchmark.effective_date)
    assert same.weights == dict(zip(benchmark.security_ids, benchmark.weights, strict=True))
    assert not same.issues and same.warning is None
    future = weights_at(benchmark, frozen.alignment, "2026-10-19")
    assert future.weights is None and future.issues[0].code == "benchmark_future_holdings"


def test_distributions_use_total_returns_and_exclude_source_day_return(
    frozen: FrozenModeledInputs,
) -> None:
    benchmark, alignment = frozen.benchmark, frozen.alignment
    assert benchmark is not None and alignment is not None
    # A +100% source-day return must be excluded. The following sessions have
    # gross factors .9*1.0 and 1.0*1.1, including a declared distribution.
    rows = alignment.rows.frame.with_columns(
        pl.when(pl.col("session") == "2026-10-21")
        .then(1.0)
        .when((pl.col("security_id") == "FICTIONAL-0") & (pl.col("session") == "2026-10-22"))
        .then(-0.1)
        .when((pl.col("security_id") == "FICTIONAL-1") & (pl.col("session") == "2026-10-23"))
        .then(0.1)
        .otherwise(0.0)
        .alias("total_return"),
        pl.lit("dividend").alias("action"),
    )
    request = alignment.request.model_copy(
        update={
            "series": tuple(
                c.model_copy(update={"adjustment": "total-return-adjusted"})
                for c in alignment.request.series
            )
        }
    )
    changed = alignment.model_copy(
        update={"rows": HistoryTable.pack(rows, "alignment"), "request": request}
    )
    result = weights_at(
        benchmark.model_copy(update={"effective_date": "2026-10-21"}), changed, "2026-10-23"
    )
    assert result.weights == pytest.approx({"FICTIONAL-0": 54 / 87, "FICTIONAL-1": 33 / 87})


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("no-alignment", "benchmark_drift_window_incomplete"),
        ("leading", "benchmark_drift_window_incomplete"),
        ("tail", "benchmark_drift_window_incomplete"),
        ("missing", "benchmark_drift_returns_incomplete"),
        ("zero-name-missing", "benchmark_drift_returns_incomplete"),
        ("minus-one", "benchmark_drift_returns_incomplete"),
        ("no-source", "benchmark_drift_returns_incomplete"),
        ("convention", "benchmark_drift_conventions_unavailable"),
        ("vintage", "benchmark_drift_vintage_mismatch"),
        ("overflow", "benchmark_drift_unrepresentable"),
        ("underflow", "benchmark_drift_unrepresentable"),
        ("weights", "benchmark_weights_invalid"),
        ("weights-nonfinite", "benchmark_weights_invalid"),
        ("weights-overflow", "benchmark_weights_invalid"),
    ],
)
def test_missing_unsafe_or_unrepresentable_drift_never_reuses_static_weights(
    frozen: FrozenModeledInputs,
    mutation: str,
    code: str,
) -> None:
    benchmark, alignment = frozen.benchmark, frozen.alignment
    assert benchmark is not None and alignment is not None
    target = "2026-10-23"
    if mutation == "no-alignment":
        alignment = None
    elif mutation == "leading":
        benchmark = benchmark.model_copy(update={"effective_date": "2026-10-19"})
    elif mutation == "tail":
        target = "2026-10-26"
    elif mutation in ("convention", "vintage"):
        changes = (
            {"return_convention": "price-only"}
            if mutation == "convention"
            else {"vintage": "different"}
        )
        contexts = (
            alignment.request.series[0].model_copy(update=changes),
            *alignment.request.series[1:],
        )
        alignment = alignment.model_copy(
            update={"request": alignment.request.model_copy(update={"series": contexts})}
        )
    elif mutation.startswith("weights"):
        values = (
            (float("inf"), -float("inf"))
            if mutation == "weights-nonfinite"
            else (1e308, 1e308)
            if mutation == "weights-overflow"
            else (0.5, 0.4)
        )
        benchmark = benchmark.model_copy(update={"weights": values})
    else:
        rows = alignment.rows.frame
        sid = "FICTIONAL-1" if mutation == "zero-name-missing" else "FICTIONAL-0"
        if mutation == "zero-name-missing":
            benchmark = benchmark.model_copy(update={"weights": (1.0, 0.0)})
        if mutation == "underflow":
            benchmark = benchmark.model_copy(update={"weights": (1e-320, 1.0)})
        column = "source_sha256" if mutation == "no-source" else "total_return"
        value: Any = (
            -1.0
            if mutation == "minus-one"
            else 1e200
            if mutation == "overflow"
            else -0.9999999999999999
            if mutation == "underflow"
            else None
        )
        rows = rows.with_columns(
            pl.when(pl.col("security_id") == sid)
            .then(pl.lit(value))
            .otherwise(pl.col(column))
            .alias(column)
        )
        if mutation == "no-source":
            rows = rows.with_columns(
                pl.when(pl.col("security_id") == sid)
                .then(None)
                .otherwise(pl.col("source_ref"))
                .alias("source_ref")
            )
        alignment = alignment.model_copy(update={"rows": HistoryTable.pack(rows, "alignment")})
    result = weights_at(benchmark, alignment, target)
    assert result.weights is None
    assert code in {issue.code for issue in result.issues}
