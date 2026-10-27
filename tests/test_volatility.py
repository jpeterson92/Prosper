"""Independent scalar expressions and fault injection; model review remains open."""

import json
import math
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import scipy  # type: ignore[import-untyped]
from scipy import optimize

from prosper import volatility as v
from prosper.innovations import InnovationContext, OHLCRow, fingerprint, transform_ohlc

ROOT = Path(__file__).resolve().parents[1]
REFERENCES: Any = json.loads((ROOT / "examples/synthetic/innovations/reference.json").read_text())


def data_for(x: tuple[float, ...]) -> v.VolatilityInput:
    sessions = tuple((date(2000, 1, 1) + timedelta(days=j)).isoformat() for j in range(len(x)))
    return v.VolatilityInput(
        x,
        "FICTIONAL-SCALAR",
        sessions,
        sessions[-1],
        "fictional-daily",
        "UTC",
        "returns-only",
        "decimal",
        fingerprint(list(x)),
        "primitive",
        len(x),
    )


def test_fixed_stack_seed_states_density_and_forecasts() -> None:
    reference = REFERENCES["stack_fixed_state"]
    x = tuple(float(Fraction(value)) for value in reference["x"])
    path = v.evaluate_fixed(x, (0.1, 0.2, 0.7))
    assert path.s2 == 3 and path.tau == 3
    assert path.initialization == "R1-weighted"
    assert path.seed == pytest.approx(float(Fraction(reference["seed"])), rel=1e-8, abs=3e-12)
    assert path.variance == pytest.approx(
        [float(Fraction(s)) for s in reference["variance_fractions"]], rel=1e-8, abs=3e-12
    )
    assert path.nll == pytest.approx([float(s) for s in reference["nll_90_digits"]], abs=1e-8)
    assert path.nll_sum == pytest.approx(float(reference["nll_sum_90_digits"]), abs=1e-8)
    assert path.sensitivities[0] == (0, 0, 0)
    assert path.standardized == pytest.approx(
        [a / math.sqrt(b) for a, b in zip(x, path.variance, strict=True)]
    )
    expected = [float(Fraction(f)) for f in reference["forecast_1_to_21_fractions"]]
    assert v.forecast_variance(path, 21) == pytest.approx(expected, rel=1e-8, abs=3e-12)
    assert v.forecast_variance(path, 1) == pytest.approx(expected[:1])
    assert expected[0] != path.variance[-1]  # Forecast origin follows the final scored observation.


def test_e01_e02_and_written_sensitivity() -> None:
    path = v.evaluate_fixed((2.0, 0.0, 0.0, 0.0, 4.0), (0.25, 0.25, 0.5), initial_variance=4)
    assert path.s2 == 4 and path.variance[:2] == (4, 4)
    assert path.initialization == "explicit-fixed-state"
    assert path.sensitivities[1] == (4, 4, 4)
    # For the written zero-current-innovation observation, dNLL=dv/(2*v).
    assert tuple(d / (2 * path.variance[1]) for d in path.sensitivities[1]) == (0.5, 0.5, 0.5)
    # The written s2=4 toy holds s2 fixed at 4 using an all-magnitude-two sample.
    constant = v.evaluate_fixed((2.0, -2.0, 2.0, -2.0), (0.25, 0.25, 0.5), initial_variance=4)
    assert constant.sensitivities[1] == (4, 4, 4)
    assert constant.variance == (4, 4, 4, 4)
    assert constant.nll[0] == pytest.approx(
        float(REFERENCES["stack_fixed_state"]["E02_90_digits"]), abs=1e-8
    )
    assert v.forecast_variance(constant, 21) == (4,) * 21
    assert constant.gradient == (0, 0, 0)


@pytest.mark.parametrize("length", [1, 2, 65, 1260])
@pytest.mark.parametrize("theta", [(0.1, 0.2, 0.7), (1.0, 0.0, 0.0), (1e-5, 0.0, 0.99997)])
def test_filter_paths_against_direct_polynomial_and_derivative(length: int, theta: v.Theta) -> None:
    # Expand h[t] as a polynomial in b, rather than using a state recurrence
    # or the production filter. Differentiate those powers directly for dh/db.
    values = np.asarray([0.01 * math.sin(t + 0.5) for t in range(length)])
    squares = values**2
    s2 = math.fsum(squares) / length
    seed = 0.0002
    u, g, b = theta
    powers = np.asarray([b**t for t in range(length)])
    derivative_powers = np.asarray([0.0, *[t * b ** (t - 1) for t in range(1, length)]])
    h = seed * powers
    dv = np.zeros((3, length))
    dv[2] = seed * derivative_powers
    if length > 1:
        forcing = u * s2 + g * squares[:-1]
        h[1:] += np.convolve(forcing, powers)[: length - 1]
        dv[0, 1:] = s2 * np.cumsum(powers)[: length - 1]
        dv[1, 1:] = np.convolve(squares[:-1], powers)[: length - 1]
        dv[2, 1:] += np.convolve(forcing, derivative_powers)[: length - 1]
    path = v.evaluate_fixed(tuple(values), theta, initial_variance=seed)
    np.testing.assert_allclose(path.variance, h, rtol=1e-8, atol=1e-12 * s2)
    np.testing.assert_allclose(path.sensitivities, dv.T, rtol=1e-8, atol=1e-12 * s2)
    expected = math.fsum(
        (math.log(2 * math.pi * h[t]) + squares[t] / h[t]) / 2 for t in range(length)
    )
    assert path.nll_sum == pytest.approx(expected, abs=1e-8)
    gradient = tuple(math.fsum(((1 - squares / h) / 2 * row / h).tolist()) for row in dv)
    assert path.gradient == pytest.approx(gradient, rel=1e-8, abs=1e-8)


def test_filter_refuses_the_first_invalid_observation_without_clipping() -> None:
    # A finite positive seed can still produce an unrepresentable score before
    # a later overflowing state; preserve the first refusal and its location.
    with pytest.raises(v.VolatilityUnavailable, match="path: observation 0"):
        v.evaluate_fixed((1e150, 1e150), (10.0, 0.1, 0.8), initial_variance=5e-324)
    with pytest.raises(v.VolatilityUnavailable, match="variance: observation 1"):
        v.evaluate_fixed((1e154, 0.0), (3.0, 0.5, 0.4), initial_variance=1.0)


@pytest.mark.parametrize("scale", [1e-6, 100.0, 1e6])
def test_consistent_units_without_automatic_rescale(scale: float) -> None:
    x = (1.0, -2.0, 0.0, 3.0, -1.0)
    base = v.evaluate_fixed(x, (0.1, 0.2, 0.7))
    changed = v.evaluate_fixed(tuple(value * scale for value in x), (0.1, 0.2, 0.7))
    assert changed.s2 == pytest.approx(base.s2 * scale**2)
    assert changed.omega == pytest.approx(base.omega * scale**2)
    assert changed.variance == pytest.approx(
        [value * scale**2 for value in base.variance], rel=1e-8
    )
    assert changed.nll_sum == pytest.approx(base.nll_sum + len(x) * math.log(scale), abs=1e-8)
    assert changed.standardized == pytest.approx(base.standardized, abs=1e-10)
    assert changed.gradient == pytest.approx(base.gradient, rel=1e-8, abs=1e-8)
    assert v.forecast_variance(changed, 21) == pytest.approx(
        [value * scale**2 for value in v.forecast_variance(base, 21)], rel=1e-8
    )


@pytest.mark.parametrize(
    "theta,expected",
    [
        ((1.0, 1.0, 1.0), (1.0, v.CAP / 2, v.CAP / 2)),
        ((1.0, -1.0, 2.0), (1.0, 0.0, v.CAP)),
        ((1.0, 0.1, 0.2), (1.0, 0.1, 0.2)),
        ((-1.0, 2.0, -1.0), (1e-12, v.CAP, 0.0)),
        ((11.0, -1.0, -1.0), (10.0, 0.0, 0.0)),
        ((0.1, 0.8, 0.7), (0.1, (v.CAP + 0.1) / 2, (v.CAP - 0.1) / 2)),
    ],
)
def test_independent_closed_projection(theta: v.Theta, expected: v.Theta) -> None:
    assert v.project_parameters(theta) == pytest.approx(expected, abs=1e-15)


def test_per_session_projection_normalization() -> None:
    assert v.CAP == 0.99998
    theta = (0.1, 0.2, 0.3)
    assert v.projected_residual(theta, (0.5, 1.0, -1.0), 10) == pytest.approx(0.1)
    assert v.projected_residual(theta, (5.0, 10.0, -10.0), 100) == pytest.approx(0.1)
    # Outward derivatives at a binding cap are KKT-compatible.
    assert v.projected_residual((0.1, v.CAP / 2, v.CAP / 2), (0.0, -2.0, -2.0), 1) < 1e-15


@pytest.mark.parametrize(
    "x,code",
    [
        ((), "observations"),
        ((math.nan, 1.0), "observations"),
        ((math.inf, 1.0), "observations"),
        ((0.0, 0.0), "second_moment"),
        ((1e-300, 1e-300), "second_moment"),
        ((1e308, 1e308), "second_moment"),
        ((0.0, 0.0, 1.0, 2.0), "seed"),
    ],
)
def test_unusable_histories_are_not_repaired(x: tuple[float, ...], code: str) -> None:
    with pytest.raises(v.VolatilityUnavailable) as error:
        v.evaluate_fixed(x, (0.1, 0.2, 0.7))
    assert error.value.code == code


@pytest.mark.parametrize(
    "theta",
    [
        (-1.0, 0.1, 0.8),
        (0.0, 0.1, 0.8),
        (0.1, -0.1, 0.8),
        (0.1, 0.1, -0.1),
        (0.1, 0.5, 0.5),
        (0.1, 0.6, 0.5),
        (math.nan, 0.1, 0.8),
    ],
)
def test_invalid_fixed_parameters(theta: v.Theta) -> None:
    with pytest.raises(v.VolatilityUnavailable, match="parameters"):
        v.evaluate_fixed((1.0, 2.0), theta)


@pytest.mark.parametrize("seed", [0.0, -1.0, math.nan, math.inf])
def test_bad_explicit_seed(seed: float) -> None:
    with pytest.raises(v.VolatilityUnavailable, match="seed"):
        v.evaluate_fixed((1.0, 2.0), (0.1, 0.2, 0.7), initial_variance=seed)


@pytest.mark.parametrize("horizon", [0, 2, 22, True])
def test_unsupported_horizons(horizon: int) -> None:
    with pytest.raises(v.VolatilityUnavailable, match="horizon"):
        v.forecast_variance(v.evaluate_fixed((1.0, 2.0), (0.1, 0.2, 0.7)), horizon)
    with pytest.raises(v.VolatilityUnavailable, match="horizon"):
        v.fit_volatility(data_for((1.0, 2.0)), horizon=horizon)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("timezone", "", "timezone"),
        ("security_id", "", "identity"),
        ("calendar", "", "identity"),
        ("innovation_identity_sha256", "", "identity"),
        ("variant", "fallback", "variant_units"),
        ("units", "unknown", "variant_units"),
        ("purpose", "investor-default", "purpose"),
        ("purpose", "research-window", "history_length"),
        ("expected_observations", 1260, "history_length"),
        ("sessions", ("2000-01-02", "2000-01-01"), "sessions"),
        ("cutoff", "2099-01-01", "sessions"),
    ],
)
def test_identified_input_refusals(field: str, value: Any, code: str) -> None:
    with pytest.raises(v.VolatilityUnavailable) as error:
        v.fit_volatility(replace(data_for((1.0, 2.0)), **{field: value}))
    assert error.value.code == code


def test_real_nine_start_fit_against_independent_constant_variance_bound() -> None:
    data = data_for((2.0, -2.0) * 12)
    fitted = v.fit_volatility(data)
    assert fitted.status == "fit-complete" and fitted.path is not None
    # Each Gaussian term for |x|=2 is minimized at v=4. This is a nonunique
    # global objective bound, independent of a fitted-parameter expectation.
    lower_bound = len(data.x) * (math.log(2 * math.pi) + math.log(4) + 1) / 2
    assert fitted.path.nll_sum == pytest.approx(lower_bound, abs=1e-8)
    assert fitted.path.variance == pytest.approx([4.0] * len(data.x), rel=1e-8)
    assert fitted.forecast == pytest.approx([4.0] * 21, rel=1e-8)
    assert len(fitted.starts) == 9
    for index, start in enumerate(fitted.starts):
        assert start.index == index and start.initial == v.STARTS[index]
        assert start.status == "eligible"
        assert start.projected_gradient_residual is not None
        assert start.projected_gradient_residual <= 1e-5
        assert 0 < start.objective_callbacks + start.gradient_callbacks <= 40000
    assert fitted.objective_range is not None and len(fitted.parameter_ranges) == 3


def fake_optimizer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    theta: v.Theta = (1.0, 0.0, 0.0),
    success: bool = True,
    objective_offset: float = 0.0,
    iterations: int = 1,
    nonfinite: bool = False,
) -> list[tuple[float, ...]]:
    starts: list[tuple[float, ...]] = []

    def minimize(fun: Any, x0: Any, **kwargs: Any) -> SimpleNamespace:
        starts.append(tuple(float(value) for value in x0))
        assert kwargs["method"] == "SLSQP"
        assert kwargs["options"] == {"maxiter": 2000, "ftol": 1e-10}
        p = np.array(theta)
        score = fun(p)
        kwargs["jac"](p)
        kwargs["callback"](p)
        return SimpleNamespace(
            x=p,
            fun=math.nan if nonfinite else score + objective_offset,
            success=success,
            status=0 if success else 9,
            message="synthetic optimizer injection",
            nit=iterations,
        )

    monkeypatch.setattr(optimize, "minimize", minimize)
    return starts


def test_ties_rechecks_boundaries_and_immutable_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    starts = fake_optimizer(monkeypatch)
    data = data_for((2.0, -2.0) * 4)
    first = v.fit_volatility(data)
    assert tuple(starts) == v.STARTS
    assert first.selected_start == 0  # Exact re-evaluated ties use original index.
    assert all(s.boundary == ("g_zero", "b_zero") for s in first.starts)
    assert first == v.fit_volatility(data)
    changed = v.fit_volatility(replace(data, innovation_identity_sha256="1" * 64))
    assert changed.identity_sha256 != first.identity_sha256
    changed_horizon = v.fit_volatility(data, horizon=1)
    assert changed_horizon.configuration_sha256 != first.configuration_sha256
    assert changed_horizon.forecast == first.forecast[:1]


@pytest.mark.parametrize(
    "kwargs,status",
    [
        ({"success": False}, "optimizer_failed"),
        ({"iterations": 2001}, "iteration_budget_exceeded"),
        ({"nonfinite": True}, "nonfinite_optimizer"),
        ({"objective_offset": 1.0}, "objective_mismatch"),
        ({"theta": (0.2, 0.2, 0.7)}, "projected_gradient_failed"),
        ({"theta": (1.0, 0.5, 0.4999800002)}, "infeasible"),
        ({"theta": (0.1, 0.5, 0.5)}, "parameters"),
    ],
)
def test_success_flag_does_not_rescue_failed_candidate(
    monkeypatch: pytest.MonkeyPatch,
    kwargs: Any,
    status: str,
) -> None:
    fake_optimizer(monkeypatch, **kwargs)
    fitted = v.fit_volatility(data_for((2.0, -2.0) * 4))
    assert fitted.status == "unavailable" and fitted.path is None and fitted.forecast == ()
    assert fitted.selected_start is None and fitted.issues == ("no_eligible_start",)
    assert len(fitted.starts) == 9 and all(s.status == status for s in fitted.starts)


def test_callback_budget_has_no_retry_or_penalty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v, "MAX_CALLBACKS", 2)

    def exhausting(fun: Any, x0: Any, **kwargs: Any) -> None:
        fun(x0)
        kwargs["jac"](x0)
        fun(x0)
        raise AssertionError("third callback must have aborted the start")

    monkeypatch.setattr(optimize, "minimize", exhausting)
    fitted = v.fit_volatility(data_for((1.0, -2.0, 3.0)))
    assert fitted.path is None and len(fitted.starts) == 9
    for start in fitted.starts:
        assert start.status == "budget_exhausted"
        assert start.objective_callbacks == start.gradient_callbacks == 1
        assert start.optimizer_success is None and start.optimizer_status is None
        assert start.last_evaluated_parameters == start.initial
        assert start.last_evaluated_objective is not None


def test_preserve_a_failed_start_and_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    count = 0

    def mixed(fun: Any, x0: Any, **kwargs: Any) -> SimpleNamespace:
        nonlocal count
        count += 1
        theta = np.array([1.0, 0.0, 0.0])
        return SimpleNamespace(
            x=theta,
            fun=fun(theta),
            nit=1,
            success=count != 1,
            status=9 if count == 1 else 0,
            message="synthetic mixed outcomes",
        )

    monkeypatch.setattr(optimize, "minimize", mixed)
    fitted = v.fit_volatility(data_for((2.0, -2.0) * 4))
    assert count == 9 and fitted.selected_start == 1
    assert fitted.starts[0].status == "optimizer_failed"
    assert all(s.status == "eligible" for s in fitted.starts[1:])


def test_unqualified_runtime_and_projection_unknowns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scipy, "__version__", "unqualified")
    with pytest.raises(v.VolatilityUnavailable, match="runtime"):
        v.fit_volatility(data_for((1.0, 2.0)))
    with pytest.raises(v.VolatilityUnavailable, match="projection"):
        v.project_parameters((math.inf, 0.0, 0.0))
    with pytest.raises(v.VolatilityUnavailable, match="projection"):
        v.projected_residual((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0)


def test_innovation_consumer_and_order() -> None:
    fixture = json.loads((ROOT / "examples/synthetic/innovations/inputs.json").read_text())
    raw = fixture["context"]
    raw["security_ids"], raw["sessions"] = tuple(raw["security_ids"]), tuple(raw["sessions"])
    context = InnovationContext(**raw)
    rows = tuple(OHLCRow(**row) for row in fixture["rows"])
    result = transform_ohlc(context, rows)
    alpha = v.series_from_innovations(result, 0, purpose="primitive", expected_observations=12)
    beta = v.series_from_innovations(result, 1, purpose="primitive", expected_observations=12)
    assert (
        alpha.security_id == context.security_ids[0] and beta.security_id == context.security_ids[1]
    )
    assert alpha.x == tuple(row[0] for row in result.innovations)
    assert alpha.innovation_identity_sha256 == result.identity_sha256
    assert alpha.x != beta.x
    with pytest.raises(v.VolatilityUnavailable, match="column"):
        v.series_from_innovations(result, 2, purpose="primitive", expected_observations=12)
    with pytest.raises(v.VolatilityUnavailable, match="innovation_unavailable"):
        v.series_from_innovations(
            replace(result, status="unusable-series"),
            0,
            purpose="primitive",
            expected_observations=12,
        )


def test_reference_gradient_domain_and_fresh_process_replay(tmp_path: Path) -> None:
    outputs = [tmp_path / "first.json", tmp_path / "second.json"]
    for path in outputs:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/qualify_volatility.py"), "--output", str(path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    report = json.loads(outputs[0].read_text())
    assert len(report["derivatives"]) == 114
    for derivative in report["derivatives"]:
        assert derivative["actual"] == pytest.approx(derivative["reference"], rel=1e-8, abs=1e-8)
    assert len(report["primitive_fits"]) == 2


def test_nine_starts_have_source_order_and_scaled_omega() -> None:
    expected = tuple(
        (1 - s, g, s - g)
        for g in (Fraction(1, 100), Fraction(5, 100), Fraction(10, 100))
        for s in (Fraction(90, 100), Fraction(97, 100), Fraction(99, 100))
    )
    assert len(v.STARTS) == 9
    for actual, exact in zip(v.STARTS, expected, strict=True):
        assert actual == pytest.approx(tuple(float(value) for value in exact), abs=1e-15)
        assert sum(actual) == pytest.approx(1, abs=1e-15)
        assert actual[1] + actual[2] < 0.99998


def test_variant_units_and_frozen_cutoff_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_optimizer(monkeypatch)
    data = data_for((2.0, -2.0) * 4)
    frozen = v.fit_volatility(data)
    relabeled = v.fit_volatility(replace(data, variant="idr"))
    percent_data = replace(
        data, x=tuple(value * 100 for value in data.x), units="percent-experiment"
    )
    percent = v.fit_volatility(percent_data)
    assert len({result.identity_sha256 for result in (frozen, relabeled, percent)}) == 3
    assert frozen.path is not None and percent.path is not None
    assert percent.forecast == pytest.approx([value * 10000 for value in frozen.forecast])
    later = data_for((*data.x, 2.0, -2.0))
    assert v.fit_volatility(later).identity_sha256 != frozen.identity_sha256
    assert v.fit_volatility(data) == frozen
    with pytest.raises(v.VolatilityUnavailable, match="sessions"):
        v.fit_volatility(replace(later, cutoff=data.cutoff))
