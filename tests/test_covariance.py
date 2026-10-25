"""R1 forecast algebra, component identity/failure and frozen lifecycle checks."""

import json
import math
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from prosper import covariance as c
from prosper import dcc
from prosper import volatility as v
from prosper.innovations import fingerprint

ROOT = Path(__file__).resolve().parents[1]
I2: c.Matrix = ((1.0, 0.0), (0.0, 1.0))


def inputs_for(n: int = 3, count: int = 64) -> tuple[v.VolatilityInput, ...]:
    rng = np.random.Generator(np.random.PCG64(622222))
    rows = rng.standard_normal((count, n)) * 0.01
    sessions = tuple((date(2000, 1, 1) + timedelta(days=j)).isoformat() for j in range(count))
    return tuple(
        v.VolatilityInput(
            tuple(float(row[j]) for row in rows),
            f"FICTIONAL-{j}",
            sessions,
            sessions[-1],
            "fictional-daily-grid",
            "UTC",
            "returns-only",
            "decimal",
            fingerprint([j, rows.tolist()]),
            "primitive",
            count,
        )
        for j in range(n)
    )


@pytest.fixture(scope="module")
def composed() -> c.CovarianceResult:
    result = c.fit_covariance(inputs_for())
    assert result.projection is not None, result.issues
    return result


def primitive(**changes: Any) -> c.Projection:
    args: dict[str, Any] = dict(
        target=I2,
        next_q=((1.0, 0.5), (0.5, 1.0)),
        variance_one=(4.0, 4.0),
        omega=(1.0, 1.0),
        persistence=(0.75, 0.75),
        dcc_persistence=0.9,
        horizon=21,
    )
    args.update(changes)
    return c.project_fixed(**args)


@pytest.mark.parametrize("index", range(8))
def test_frozen_90_digit_forecasts(index: int) -> None:
    case = json.loads((ROOT / "examples/synthetic/dcc/covariance-reference.json").read_text())[
        "cases"
    ][index]
    args = {k: val for k, val in case["input"].items() if k != "name"}
    actual = c.project_fixed(**args, horizon=case["horizon"])
    for key, matrix in case["expected"].items():
        expected = np.asarray(matrix, dtype=float)
        assert np.allclose(
            getattr(actual, key), expected, rtol=1e-8, atol=1e-12 * float(np.max(np.abs(expected)))
        )


def test_e05_e06_constant_covariance_units_and_signed_active_quadratic() -> None:
    result = primitive(
        target=((1.0, 0.5), (0.5, 1.0)),
        next_q=((4.0, 3.0), (3.0, 9.0)),
        variance_one=(4.0, 9.0),
        omega=(1.0, 2.25),
    )
    expected = np.array([[4.0, 3.0], [3.0, 9.0]])
    assert np.allclose(result.one_session, expected)
    assert np.allclose(result.last_session, expected)
    assert np.allclose(result.cumulative, expected * 21)
    assert np.allclose(result.average_daily, expected)
    assert np.allclose(result.annualized, expected * 252)
    a = np.array([1.0, -1.0])
    assert a @ np.array(result.one_session) @ a == pytest.approx(7)
    assert a @ np.array(result.cumulative) @ a == pytest.approx(147)
    assert math.sqrt(a @ np.array(result.annualized) @ a) == pytest.approx(42)
    assert result.units == "decimal-return-squared" and result.annualization == 252


def test_e14_second_step_normalized_correlation_blend_and_q_zero() -> None:
    # For horizon 21, off-diagonal cumulative is 2*sum(.9**j); diagonal stays 4.
    result = primitive()
    assert result.cumulative[0][1] == pytest.approx(2 * sum(0.9**j for j in range(21)))
    assert result.last_session[0][1] == pytest.approx(2 * 0.9**20)
    zero = primitive(dcc_persistence=0.0)
    assert zero.one_session[0][1] == pytest.approx(2)
    assert zero.last_session[0][1] == 0
    assert zero.cumulative[0][1] == pytest.approx(2)
    one = primitive(horizon=1)
    assert one.cumulative == one.average_daily == one.one_session == one.last_session
    assert one.identity_sha256 != result.identity_sha256


def test_e03_full_replay_uses_last_observation_only_for_forecast() -> None:
    z: c.Matrix = ((1.0, 2.0), (0.5, -1.0))
    terminal, future = c.replay_full(z, I2, (0.1, 0.8))
    assert np.allclose(terminal, ((1.0, 0.2), (0.2, 1.3)))
    expected_future = np.array([[0.925, 0.11], [0.11, 1.24]])
    assert np.allclose(future, expected_future)
    assert not np.allclose(future, terminal)
    altered, later = c.replay_full((z[0], (9.0, 8.0)), I2, (0.1, 0.8))
    assert altered == terminal and later != future


def test_compose_exact_component_binding_and_forecast_origin(composed: c.CovarianceResult) -> None:
    assert composed.status == "qualified-synthetic-forecast" and not composed.issues
    fit, projection = composed.dcc_fit, composed.projection
    assert fit and fit.evaluation and projection
    assert composed.terminal_q is not None and composed.next_q is not None
    assert composed.security_ids == fit.data.context.security_ids
    assert fit.data.context.upstream_sha256 == tuple(s.identity_sha256 for s in composed.scalars)
    q = np.array(fit.data.target)
    alpha, beta = fit.evaluation.parameters
    # Direct finite convolution specifies Q_T separately from the streamed implementation.
    t = len(fit.data.z) - 1
    coefficient = beta**t + (1 - alpha - beta) * sum(beta**j for j in range(t))
    q = coefficient * q + alpha * sum(
        (beta ** (t - 1 - k) * np.outer(row, row) for k, row in enumerate(fit.data.z[:-1])),
        np.zeros_like(q),
    )
    assert np.allclose(composed.terminal_q, q, rtol=1e-8, atol=1e-10)
    q1 = (
        (1 - alpha - beta) * np.array(fit.data.target)
        + alpha * np.outer(fit.data.z[-1], fit.data.z[-1])
        + beta * q
    )
    assert np.allclose(composed.next_q, q1, rtol=1e-8, atol=1e-10)
    variances = []
    for scalar in composed.scalars:
        path = scalar.path
        assert path
        variances.append(
            path.omega
            + path.parameters_u_g_b[1] * path.x[-1] ** 2
            + path.parameters_u_g_b[2] * path.variance[-1]
        )
    assert np.diag(projection.one_session) == pytest.approx(variances)
    assert c.compose_covariance(composed.scalars, fit) == composed
    one = c.compose_covariance(composed.scalars, fit, horizon=1)
    assert one.projection and one.projection.one_session == projection.one_session
    assert one.identity_sha256 != composed.identity_sha256


@pytest.mark.parametrize(
    "field",
    [
        "calendar",
        "variant",
        "units",
        "cutoff",
        "sessions",
        "innovation_identity_sha256",
        "security_id",
        "x",
    ],
)
def test_changed_scalar_input_cannot_reuse_old_fit(
    composed: c.CovarianceResult, field: str
) -> None:
    first = composed.scalars[0]
    values: dict[str, Any] = {
        "calendar": "other-calendar",
        "variant": "idr",
        "units": "percent-experiment",
        "cutoff": "2099-01-01",
        "sessions": first.data.sessions[::-1],
        "innovation_identity_sha256": "f" * 64,
        "security_id": "FICTIONAL-OTHER",
        "x": tuple(x * 2 for x in first.data.x),
    }
    changed = replace(first, data=replace(first.data, **{field: values[field]}))
    result = c.compose_covariance((changed,) + composed.scalars[1:], composed.dcc_fit)
    assert result.status == "unavailable" and result.projection is None
    assert result.scalars[0] == changed and result.dcc_fit is composed.dcc_fit
    another = replace(first, data=replace(first.data, security_id="FICTIONAL-DIFFERENT"))
    other_result = c.compose_covariance((another,) + composed.scalars[1:], composed.dcc_fit)
    assert result.input_sha256 != other_result.input_sha256


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "unavailable"),
        ("path", None),
        ("issues", ("missing-history",)),
        ("identity_sha256", "a" * 64),
        ("output_sha256", "b" * 64),
        ("configuration_sha256", "c" * 64),
        ("selected_start", None),
        ("starts", ()),
        ("forecast", ()),
        ("version", "unknown-version"),
    ],
)
def test_failed_or_changed_scalar_preserved(
    composed: c.CovarianceResult, field: str, value: Any
) -> None:
    changed = replace(composed.scalars[0], **{field: value})
    result = c.compose_covariance((changed,) + composed.scalars[1:], composed.dcc_fit)
    assert result.status == "unavailable" and result.terminal_q is None
    assert len(result.scalars) == 3 and result.scalars[0] is changed


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "unavailable"),
        ("evaluation", None),
        ("issues", ("no_eligible_start",)),
        ("identity_sha256", "a" * 64),
        ("output_sha256", "b" * 64),
        ("configuration_sha256", "c" * 64),
        ("selected_start", None),
        ("starts", ()),
        ("version", "unknown-version"),
    ],
)
def test_failed_or_changed_dcc_preserved(
    composed: c.CovarianceResult, field: str, value: Any
) -> None:
    assert composed.dcc_fit
    changed = replace(composed.dcc_fit, **{field: value})
    result = c.compose_covariance(composed.scalars, changed)
    assert result.status == "unavailable" and result.projection is None
    assert result.dcc_fit is changed and result.scalars == composed.scalars


def test_missing_fit_and_reordered_or_duplicate_universe_refuse(
    composed: c.CovarianceResult,
) -> None:
    assert c.compose_covariance(composed.scalars, None).projection is None
    assert c.compose_covariance(composed.scalars[::-1], composed.dcc_fit).projection is None
    duplicate = (composed.scalars[0], composed.scalars[0])
    assert c.compose_covariance(duplicate, composed.dcc_fit).projection is None
    assert c.compose_covariance(composed.scalars[:1], composed.dcc_fit).projection is None


@pytest.mark.parametrize(
    "field,value",
    [("calendar", "other-calendar"), ("variant", "idr"), ("units", "percent-experiment")],
)
def test_individually_eligible_mixed_contexts_refuse(field: str, value: str) -> None:
    data = inputs_for(n=2)
    change: dict[str, Any] = {field: value}
    mixed = (data[0], replace(data[1], **change))
    result = c.fit_covariance(mixed)
    assert result.projection is None and result.dcc_fit is None
    assert result.issues[0].startswith("component_context:")
    assert len(result.scalars) == 2 and all(s.path for s in result.scalars)


def test_fixed_model_relabeling_is_equivariant_not_a_changed_pair_refit() -> None:
    target: c.Matrix = ((1.0, 0.2, -0.1), (0.2, 1.0, 0.3), (-0.1, 0.3, 1.0))
    z: c.Matrix = ((1.0, 2.0, -0.5), (-1.0, 0.5, 2.0), (0.2, -2.0, 0.5))
    order = (0, 2, 1)
    permuted = tuple(tuple(row[j] for j in order) for row in z)
    relabeled = tuple(tuple(target[i][j] for j in order) for i in order)
    _, q1 = c.replay_full(z, target, (0.1, 0.8))
    _, qp = c.replay_full(permuted, relabeled, (0.1, 0.8))
    base = c.project_fixed(
        target, q1, (4.0, 9.0, 1.0), (1.0, 2.25, 0.25), (0.75,) * 3, 0.9, horizon=21
    )
    renamed = c.project_fixed(
        relabeled, qp, (4.0, 1.0, 9.0), (1.0, 0.25, 2.25), (0.75,) * 3, 0.9, horizon=21
    )
    assert np.allclose(np.array(base.cumulative)[np.ix_(order, order)], renamed.cumulative)
    assert dcc.evaluate_fixed(z, target, (0.1, 0.8)).nll_sum != pytest.approx(
        dcc.evaluate_fixed(permuted, relabeled, (0.1, 0.8)).nll_sum
    )


def test_return_scaling_and_units() -> None:
    base = primitive()
    scaled = primitive(
        variance_one=(40000.0,) * 2, omega=(10000.0,) * 2, source_units="percent-experiment"
    )
    assert np.allclose(np.array(base.cumulative) * 10000, scaled.cumulative)
    assert scaled.next_correlation == base.next_correlation
    assert scaled.units == "percent-experiment-return-squared"
    assert base.identity_sha256 != scaled.identity_sha256


@pytest.mark.parametrize(
    "changes",
    [
        {"horizon": 0},
        {"horizon": True},
        {"horizon": 2},
        {"horizon": 252},
        {"variance_one": (0.0, 1.0)},
        {"variance_one": (math.nan, 1.0)},
        {"omega": (0.0, 1.0)},
        {"persistence": (1.0, 0.9)},
        {"dcc_persistence": 1.0},
        {"dcc_persistence": -0.1},
        {"target": ((1.0, 1.0), (1.0, 1.0))},
        {"next_q": ((1.0, 2.0), (2.0, 1.0))},
        {"next_q": ((1.0, 0.1), (0.2, 1.0))},
        {"source_units": "unknown"},
        {"variance_one": (1.0,)},
        {"target": ((1.0,),)},
    ],
)
def test_primitive_invalid_inputs_refuse(changes: dict[str, Any]) -> None:
    with pytest.raises(c.CovarianceUnavailable):
        primitive(**changes)


def test_inherited_feasibility_tolerance_does_not_clip_parameters() -> None:
    inside = primitive(dcc_persistence=dcc.CAP + 2e-14)
    assert inside.last_session[0][1] == pytest.approx(2 * (dcc.CAP + 2e-14) ** 20, rel=1e-14)
    with pytest.raises(c.CovarianceUnavailable):
        primitive(dcc_persistence=dcc.CAP + 2e-10)


@pytest.mark.parametrize(
    "changes",
    [
        {"variance_one": (1e308, 1e308), "omega": (1e308, 1e308)},
        {"next_q": ((1.0, 0.9999999999999), (0.9999999999999, 1.0))},
        {"next_q": ((1.0, math.nan), (math.nan, 1.0))},
        {"target": ((1.0, 0.0), (0.0,))},
    ],
)
def test_numeric_scale_near_singular_and_ragged_inputs_are_located_refusals(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(c.CovarianceUnavailable):
        primitive(**changes)


def test_hash_consistent_stale_component_configurations_refuse(
    composed: c.CovarianceResult,
) -> None:
    scalar = composed.scalars[0]
    stale = replace(
        scalar,
        configuration_sha256="f" * 64,
        identity_sha256=fingerprint(["f" * 64, scalar.input_sha256, scalar.output_sha256]),
    )
    refused = c.compose_covariance((stale,) + composed.scalars[1:], composed.dcc_fit)
    assert refused.issues[0].startswith("scalar_configuration:")
    fit = composed.dcc_fit
    assert fit
    stale_fit = replace(
        fit,
        configuration_sha256="f" * 64,
        identity_sha256=fingerprint(["f" * 64, fit.input_sha256, fit.output_sha256]),
    )
    refused = c.compose_covariance(composed.scalars, stale_fit)
    assert refused.issues[0].startswith("dcc_configuration:")


def test_failed_scalar_prevents_dcc_call_and_retains_all_diagnostics(
    composed: c.CovarianceResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = replace(
        composed.scalars[1],
        status="unavailable",
        issues=("no_eligible_start",),
        path=None,
        selected_start=None,
        forecast=(),
    )
    components = (composed.scalars[0], failed, composed.scalars[2])
    by_id = {s.data.security_id: s for s in components}
    monkeypatch.setattr(v, "fit_volatility", lambda data, **kwargs: by_id[data.security_id])

    def forbidden(data: dcc.DCCInput) -> dcc.DCCResult:
        raise AssertionError("failed scalar must block fitting")

    monkeypatch.setattr(dcc, "fit_dcc", forbidden)
    result = c.fit_covariance(tuple(s.data for s in components))
    assert result.status == "unavailable" and result.dcc_fit is None
    assert result.scalars == components and result.scalars[1].starts == failed.starts


def test_failed_dcc_retains_diagnostics_in_orchestration(
    composed: c.CovarianceResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert composed.dcc_fit
    failed = replace(
        composed.dcc_fit,
        status="unavailable",
        issues=("no_eligible_start",),
        evaluation=None,
        selected_start=None,
    )
    by_id = {s.data.security_id: s for s in composed.scalars}
    monkeypatch.setattr(v, "fit_volatility", lambda data, **kwargs: by_id[data.security_id])
    monkeypatch.setattr(dcc, "fit_dcc", lambda data: failed)
    result = c.fit_covariance(tuple(s.data for s in composed.scalars))
    assert result.status == "unavailable" and result.dcc_fit is failed
    assert result.dcc_fit.starts == composed.dcc_fit.starts and result.projection is None


def test_future_row_with_old_cutoff_is_refused(composed: c.CovarianceResult) -> None:
    old = composed.scalars[0].data
    with pytest.raises(v.VolatilityUnavailable, match="cutoff"):
        v.fit_volatility(
            replace(
                old,
                x=old.x + (0.1,),
                sessions=old.sessions + ("2000-03-05",),
                expected_observations=65,
            )
        )


def test_future_mutation_does_not_touch_frozen_cutoff_and_new_fit_changes_identity(
    composed: c.CovarianceResult,
) -> None:
    source = [list(s.data.x) + [99.0] for s in composed.scalars]
    old = asdict(composed)
    for row in source:
        row[-1] = -999.0
    replay = c.compose_covariance(composed.scalars, composed.dcc_fit)
    assert asdict(replay) == old
    later = tuple(
        replace(
            s.data,
            x=s.data.x + (0.02,),
            sessions=s.data.sessions + ("2000-03-05",),
            cutoff="2000-03-05",
            expected_observations=65,
            innovation_identity_sha256=fingerprint([s.data.x, "later"]),
        )
        for s in composed.scalars
    )
    newer = c.fit_covariance(later)
    assert newer.projection and newer.identity_sha256 != composed.identity_sha256
    assert c.compose_covariance(composed.scalars, newer.dcc_fit).projection is None


def test_fresh_process_reference_and_idr_replay(tmp_path: Path) -> None:
    outputs = [tmp_path / f"replay-{j}.json" for j in range(2)]
    for output in outputs:
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/qualify_covariance.py"), "--output", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stdout + run.stderr
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    result = json.loads(outputs[0].read_text())["idr_primitive"]
    assert result["status"] == "qualified-synthetic-forecast"
    assert all(s["data"]["variant"] == "idr" for s in result["scalars"])
