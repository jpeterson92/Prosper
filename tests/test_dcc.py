"""DCC independent written expressions, streamed/full-state checks and failure injection."""

import json
import math
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import scipy  # type: ignore[import-untyped]
from scipy import optimize

from prosper import dcc as d
from prosper.innovations import fingerprint
from prosper.shrinkage import analytical_target
from prosper.volatility import evaluate_fixed as scalar_path

ROOT = Path(__file__).resolve().parents[1]
I2: d.Matrix = ((1.0, 0.0), (0.0, 1.0))
Z: d.Matrix = ((1.0, 2.0), (-1.0, 0.5), (0.25, -1.5), (2.0, -0.5))


def context_for(z: d.Matrix) -> d.DCCContext:
    sessions = tuple((date(2000, 1, 1) + timedelta(days=j)).isoformat() for j in range(len(z)))
    return d.DCCContext(
        tuple(f"FICTIONAL-{j}" for j in range(len(z[0]))),
        sessions,
        sessions[-1],
        "fictional-daily-grid",
        "UTC",
        "returns-only",
        "decimal",
        tuple(fingerprint([j, z]) for j in range(len(z[0]))),
        "primitive",
        len(z),
    )


def data_for(z: d.Matrix = Z, target: d.Matrix = I2) -> d.DCCInput:
    return d.fixed_input(z, target, context_for(z))


def orthogonal_data() -> d.DCCInput:
    return data_for(((2.0, 0.0), (0.0, 2.0)) * 8)


def test_e03_terminal_state_seed_sensitivities_and_all_session_score() -> None:
    evaluation = d.evaluate_fixed(((1.0, 2.0), (0.5, -1.0)), I2, (0.1, 0.8))
    assert evaluation.terminal_q[0] == pytest.approx((1.0, 1.3, 0.2))
    assert evaluation.terminal_alpha[0] == pytest.approx((0.0, 3.0, 2.0))
    assert evaluation.terminal_beta == ((0.0, 0.0, 0.0),)
    assert evaluation.nll[0] == pytest.approx(math.log(2 * math.pi) + 2.5)
    rho = 0.2 / math.sqrt(1.3)
    expected = (
        math.log(2 * math.pi)
        + math.log(1 - rho * rho) / 2
        + (0.25 + 1 + rho) / (2 * (1 - rho * rho))
    )
    assert evaluation.nll[1] == pytest.approx(expected, abs=1e-8)
    assert evaluation.nll_sum == pytest.approx(sum(evaluation.nll), abs=1e-8)
    # Mutating an observation AFTER this declared history does not enter this frozen result.
    longer = d.evaluate_fixed(((1.0, 2.0), (0.5, -1.0), (5.0, 8.0)), I2, (0.1, 0.8))
    assert longer.nll[:2] == evaluation.nll
    assert longer.terminal_q != evaluation.terminal_q


def test_e04_pair_density_constants_and_initial_sensitivities() -> None:
    target: d.Matrix = ((1.0, 0.5), (0.5, 1.0))
    evaluation = d.evaluate_fixed(((1.0, 2.0),), target, (0.1, 0.8))
    assert evaluation.nll_sum == pytest.approx(math.log(2 * math.pi) + math.log(0.75) / 2 + 2)
    assert evaluation.gradient == (0, 0)
    assert evaluation.terminal_alpha == evaluation.terminal_beta == ((0, 0, 0),)
    # Independent derivative of the stipulated bivariate density at rho=1/2.
    assert -(0.5 + 2) / 0.75 + 0.5 * 3 / 0.75**2 == pytest.approx(-2 / 3)


def test_pair_mean_and_time_sum_are_separate() -> None:
    base = d.evaluate_fixed(((1.0, 1.0), (2.0, 2.0)), ((1.0, 0.5), (0.5, 1.0)), (0.1, 0.8))
    repeated = d.evaluate_fixed(
        ((1.0, 1.0, 1.0), (2.0, 2.0, 2.0)),
        ((1.0, 0.5, 0.5), (0.5, 1.0, 0.5), (0.5, 0.5, 1.0)),
        (0.1, 0.8),
    )
    assert repeated.pairs == ((0, 1), (1, 2))
    assert repeated.nll_sum == base.nll_sum and repeated.gradient == base.gradient
    # With alpha=0, Ctarget stays constant; doubling time doubles the score.
    first = d.evaluate_fixed(Z, I2, (0.0, 0.8))
    second = d.evaluate_fixed(Z + Z, I2, (0.0, 0.8))
    assert second.nll_sum == pytest.approx(2 * first.nll_sum)


def test_adjacent_pair_order_changes_objective_but_full_reversal_relabels() -> None:
    z: d.Matrix = ((1.0, 2.0, -0.5), (-1.0, 0.5, 2.0), (0.2, -2.0, 0.5))
    c: d.Matrix = ((1.0, 0.2, -0.1), (0.2, 1.0, 0.3), (-0.1, 0.3, 1.0))
    base = d.evaluate_fixed(z, c, (0.1, 0.8))

    def relabel(order: tuple[int, ...]) -> d.PairEvaluation:
        return d.evaluate_fixed(
            tuple(tuple(row[j] for j in order) for row in z),
            tuple(tuple(c[i][j] for j in order) for i in order),
            (0.1, 0.8),
        )

    assert relabel((0, 2, 1)).nll_sum != pytest.approx(base.nll_sum, abs=1e-8)
    reverse = relabel((2, 1, 0))
    assert reverse.nll_sum == pytest.approx(base.nll_sum, abs=1e-8)
    for original, changed in zip(base.terminal_q, reversed(reverse.terminal_q), strict=True):
        assert original == pytest.approx((changed[1], changed[0], changed[2]))


@pytest.mark.parametrize(
    "theta,expected",
    [
        ((1.0, 1.0), (d.CAP / 2, d.CAP / 2)),
        ((-1.0, 2.0), (0.0, d.CAP)),
        ((2.0, -1.0), (d.CAP, 0.0)),
        ((0.1, 0.2), (0.1, 0.2)),
        ((-1.0, -1.0), (0.0, 0.0)),
        ((0.8, 0.7), ((d.CAP + 0.1) / 2, (d.CAP - 0.1) / 2)),
    ],
)
def test_independent_simplex_projection(theta: d.Theta, expected: d.Theta) -> None:
    assert d.project_parameters(theta) == pytest.approx(expected, abs=1e-15)


def test_projection_per_session_normalization_and_cap_kkt() -> None:
    assert d.projected_residual((0.2, 0.3), (1.0, -1.0), 10) == pytest.approx(0.1)
    assert d.projected_residual((0.2, 0.3), (10.0, -10.0), 100) == pytest.approx(0.1)
    assert d.projected_residual((d.CAP / 2, d.CAP / 2), (-2.0, -2.0), 1) < 1e-15
    for theta in ((math.nan, 0.0), (math.inf, 0.0)):
        with pytest.raises(d.DCCUnavailable, match="projection"):
            d.project_parameters(theta)
    with pytest.raises(d.DCCUnavailable, match="projection"):
        d.projected_residual((0.1, 0.2), (0.0, 0.0), 0)


@pytest.mark.parametrize(
    "z,target,code",
    [
        ((), I2, "shape"),
        (((1.0,),), ((1.0,),), "shape"),
        (((1.0, 2.0), (1.0,)), I2, "shape"),
        (Z, ((1.0,), (0.0,)), "shape"),
        (((math.nan, 1.0),), I2, "nonfinite"),
        (Z, ((1.0, math.inf), (0.0, 1.0)), "nonfinite"),
        (((0.0, 1.0),), I2, "second_moment"),
        (((1e308, 1.0),), I2, "second_moment"),
        (((1e-300, 1.0),), I2, "second_moment"),
        (Z, ((4.0, 0.0), (0.0, 1.0)), "target_diagonal"),
        (Z, ((1.0, 0.3), (0.1, 1.0)), "target_asymmetry"),
        (Z, ((1.0, 1.0), (1.0, 1.0)), "target_not_spd"),
        (Z, ((1.0, 1.00001), (1.00001, 1.0)), "target_not_spd"),
        (Z, ((1.0, 1 - 1e-13), (1 - 1e-13, 1.0)), "target_not_spd"),
    ],
)
def test_fixed_domain_refusals(z: d.Matrix, target: d.Matrix, code: str) -> None:
    with pytest.raises(d.DCCUnavailable) as exc:
        d.evaluate_fixed(z, target, (0.1, 0.8))
    assert exc.value.code == code


@pytest.mark.parametrize("theta", [(math.nan, 0.0), (-0.1, 0.8), (0.5, 0.5), (0.0, 1.0)])
def test_fixed_parameter_refusals(theta: d.Theta) -> None:
    with pytest.raises(d.DCCUnavailable, match="parameters"):
        d.evaluate_fixed(Z, I2, theta)


def test_roundoff_symmetry_is_explicit_and_no_determinant_clipping() -> None:
    result = d.evaluate_fixed(Z, ((1.0, 0.2 + 1e-12), (0.2, 1.0)), (0.1, 0.8))
    assert 0 < result.target_symmetry_correction < 1e-10
    # Finite but dominant collinear observations erase the small positive target in binary64.
    with pytest.raises(d.DCCUnavailable, match="pair_determinant"):
        d.evaluate_fixed(((1e100, 1e100), (1.0, 1.0)), I2, (0.5, 0.4))


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("timezone", "", "timezone"),
        ("security_ids", ("A", "A"), "identity"),
        ("security_ids", ("", "B"), "identity"),
        ("calendar", "", "identity"),
        ("upstream_sha256", ("", ""), "identity"),
        ("variant", "fallback", "variant_units"),
        ("source_units", "unknown", "variant_units"),
        ("purpose", "investor", "purpose"),
        ("purpose", "research-window", "history_length"),
        ("expected_observations", 1260, "history_length"),
        ("sessions", ("2000-01-02", "2000-01-01"), "sessions"),
        ("cutoff", "2099-01-01", "sessions"),
    ],
)
def test_identified_context_refusals(field: str, value: Any, code: str) -> None:
    original = data_for()
    data = replace(original, context=replace(original.context, **{field: value}))
    with pytest.raises(d.DCCUnavailable) as exc:
        d.fit_dcc(data)
    assert exc.value.code == code


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("target_input_sha256", "1" * 64, "target_provenance"),
        ("target_identity_sha256", "", "identity"),
        ("target_identity_sha256", "1" * 64, "target_provenance"),
        ("target_kind", "fallback", "target_profile"),
    ],
)
def test_target_provenance_refusals(field: str, value: Any, code: str) -> None:
    with pytest.raises(d.DCCUnavailable) as exc:
        d.fit_dcc(replace(data_for(), **{field: value}))
    assert exc.value.code == code


def test_actual_twelve_start_fit_against_independent_objective_bound() -> None:
    data = orthogonal_data()
    fitted = d.fit_dcc(data)
    assert fitted.status == "fit-complete" and fitted.evaluation is not None
    # For u*w=0 and u*u+w*w=4, each density is log(2pi)+log(D)/2+2/D.
    # It is minimized for D=1 on 0<D<=1, independently of the optimizer.
    lower_bound = len(data.z) * (math.log(2 * math.pi) + 2)
    assert fitted.evaluation.nll_sum == pytest.approx(lower_bound, abs=1e-8)
    assert fitted.evaluation.gradient == (0, 0)
    assert len(fitted.starts) == 12 and all(s.status == "eligible" for s in fitted.starts)
    assert fitted.selected_start == 0 and fitted.objective_range == (lower_bound, lower_bound)
    for j, start in enumerate(fitted.starts):
        assert start.index == j and start.initial == d.STARTS[j]
        assert 0 < start.objective_callbacks + start.gradient_callbacks <= 40000
        assert start.projected_gradient_residual == 0


def fake_optimizer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    theta: d.Theta = (0.0, 0.0),
    success: bool = True,
    offset: float = 0,
    iterations: int = 1,
    nonfinite: bool = False,
) -> list[d.Theta]:
    starts: list[d.Theta] = []

    def minimize(fun: Any, x0: Any, **kwargs: Any) -> SimpleNamespace:
        starts.append((float(x0[0]), float(x0[1])))
        assert kwargs["method"] == "SLSQP" and kwargs["options"] == {"maxiter": 2000, "ftol": 1e-10}
        assert kwargs["bounds"] == ((0, 1), (0, 1))
        assert kwargs["constraints"]["fun"](np.array([0.1, 0.2])) == pytest.approx(d.CAP - 0.3)
        assert tuple(kwargs["constraints"]["jac"](x0)) == (-1, -1)
        p = np.asarray(theta)
        score = fun(p)
        kwargs["jac"](p)
        kwargs["callback"](p)
        return SimpleNamespace(
            x=p,
            fun=math.nan if nonfinite else score + offset,
            success=success,
            status=0 if success else 9,
            message="synthetic injected optimizer",
            nit=iterations,
        )

    monkeypatch.setattr(optimize, "minimize", minimize)
    return starts


def test_ties_and_failure_provenance_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    starts = fake_optimizer(monkeypatch)
    data = orthogonal_data()
    first = d.fit_dcc(data)
    assert tuple(starts) == d.STARTS and first.selected_start == 0
    assert first == d.fit_dcc(data)
    assert all(s.boundary == ("alpha_zero", "beta_zero") for s in first.starts)
    context = replace(data.context, upstream_sha256=("1" * 64, "2" * 64))
    changed = d.fixed_input(data.z, data.target, context)
    assert d.fit_dcc(changed).identity_sha256 != first.identity_sha256
    assert changed.z == first.data.z


@pytest.mark.parametrize(
    "kwargs,status",
    [
        ({"success": False}, "optimizer_failed"),
        ({"iterations": 2001}, "iteration_budget_exceeded"),
        ({"nonfinite": True}, "nonfinite_optimizer"),
        ({"offset": 1.0}, "objective_mismatch"),
        ({"theta": (0.2, 0.7999800002)}, "infeasible"),
        ({"theta": (0.5, 0.5)}, "parameters"),
    ],
)
def test_optimizer_success_is_insufficient(
    monkeypatch: pytest.MonkeyPatch, kwargs: Any, status: str
) -> None:
    fake_optimizer(monkeypatch, **kwargs)
    fitted = d.fit_dcc(orthogonal_data())
    assert fitted.status == "unavailable" and fitted.evaluation is None
    assert fitted.selected_start is None and fitted.issues == ("no_eligible_start",)
    assert len(fitted.starts) == 12 and all(s.status == status for s in fitted.starts)


def test_independent_projected_gradient_recheck(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_optimizer(monkeypatch, theta=(0.2, 0.7))
    fitted = d.fit_dcc(data_for())
    assert fitted.evaluation is None
    assert all(s.status == "projected_gradient_failed" for s in fitted.starts)


def test_callback_budget_retains_last_evaluation_and_unknown_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(d, "MAX_CALLBACKS", 2)

    def exhaust(fun: Any, x0: Any, **kwargs: Any) -> None:
        fun(x0)
        kwargs["jac"](x0)
        fun(x0)
        raise AssertionError("budget should abort")

    monkeypatch.setattr(optimize, "minimize", exhaust)
    result = d.fit_dcc(data_for())
    assert result.evaluation is None
    for start in result.starts:
        assert start.status == "budget_exhausted"
        assert start.objective_callbacks == start.gradient_callbacks == 1
        assert start.optimizer_success is start.optimizer_status is None
        assert start.last_evaluated_parameters == start.initial
        assert start.last_evaluated_objective is not None


def test_iteration_callback_budget_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(d, "MAX_ITERATIONS", 2)

    def exhaust(fun: Any, x0: Any, **kwargs: Any) -> None:
        fun(x0)
        for _ in range(3):
            kwargs["callback"](x0)

    monkeypatch.setattr(optimize, "minimize", exhaust)
    result = d.fit_dcc(data_for())
    assert all(s.status == "iteration_budget_exceeded" and s.iterations == 3 for s in result.starts)


def test_continue_after_one_failed_start(monkeypatch: pytest.MonkeyPatch) -> None:
    count = 0

    def mixed(fun: Any, x0: Any, **kwargs: Any) -> SimpleNamespace:
        nonlocal count
        count += 1
        p = np.array([0.0, 0.0])
        return SimpleNamespace(
            x=p,
            fun=fun(p),
            success=count != 1,
            status=9 if count == 1 else 0,
            nit=1,
            message="synthetic mixed start outcomes",
        )

    monkeypatch.setattr(optimize, "minimize", mixed)
    result = d.fit_dcc(orthogonal_data())
    assert result.starts[0].status == "optimizer_failed" and result.selected_start == 1
    assert len(result.starts) == 12 and all(s.status == "eligible" for s in result.starts[1:])


def test_last_valid_evaluation_survives_later_domain_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fails(fun: Any, x0: Any, **kwargs: Any) -> None:
        fun(x0)
        fun(np.array([0.5, 0.5]))

    monkeypatch.setattr(optimize, "minimize", fails)
    result = d.fit_dcc(data_for())
    for start in result.starts:
        assert start.status == "parameters" and start.optimizer_success is None
        assert start.last_evaluated_parameters == start.initial
        assert start.last_evaluated_objective is not None


def test_unqualified_runtime_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scipy, "__version__", "unqualified")
    with pytest.raises(d.DCCUnavailable, match="runtime"):
        d.fit_dcc(data_for())


def test_scalar_and_analytical_target_input_consumer() -> None:
    # Only interface qualification here; production scalar/target orchestration is the sibling.
    x = np.random.Generator(np.random.PCG64(62222)).standard_normal((24, 3))
    paths = [scalar_path(tuple(float(v) for v in x[:, j]), (0.1, 0.1, 0.8)) for j in range(3)]
    z = tuple(tuple(path.standardized[t] for path in paths) for t in range(24))
    context = context_for(z)
    target = analytical_target(
        np.asarray(z), context=d.target_context(context), preprocessing="none", degrees_of_freedom=0
    )
    data = d.input_from_target(z, context, target)
    assert data.target_kind == "analytical-r1" and data.target_input_sha256 == d.observation_hash(z)
    fitted = d.fit_dcc(data)
    assert len(fitted.starts) == 12 and fitted.evaluation is not None
    with pytest.raises(d.DCCUnavailable, match="target_provenance"):
        d.input_from_target(tuple(reversed(z)), context, target)
    with pytest.raises(d.DCCUnavailable, match="target_provenance"):
        d.input_from_target(z, replace(context, variant="idr"), target)
    with pytest.raises(d.DCCUnavailable, match="target_profile"):
        d.input_from_target(z, context, replace(target, preprocessing="demean"))
    # The qualified component arrays are immutable; the binding also snapshots a copy.
    with pytest.raises(ValueError):
        target.correlation.setflags(write=True)
    mutable = target.correlation.copy()
    snapshot = d.input_from_target(z, context, replace(target, correlation=mutable))
    mutable[0, 1] = 0.9
    assert snapshot.target == data.target


def test_order_cutoff_and_variant_change_identity() -> None:
    data = orthogonal_data()
    base = d.fit_dcc(data)
    variant = replace(data.context, variant="idr")
    assert (
        d.fit_dcc(d.fixed_input(data.z, data.target, variant)).identity_sha256
        != base.identity_sha256
    )
    sessions = tuple((date(2001, 1, 1) + timedelta(days=j)).isoformat() for j in range(len(data.z)))
    context = replace(data.context, sessions=sessions, cutoff=sessions[-1])
    assert (
        d.fit_dcc(d.fixed_input(data.z, data.target, context)).identity_sha256
        != base.identity_sha256
    )


def test_future_row_or_target_order_cannot_enter_a_frozen_fit() -> None:
    data = data_for()
    with pytest.raises(d.DCCUnavailable, match="history_length"):
        d.fit_dcc(replace(data, z=data.z + ((9.0, -9.0),)))
    with pytest.raises(d.DCCUnavailable, match="target_provenance"):
        d.fit_dcc(
            replace(
                data,
                target_context=replace(
                    data.target_context, security_ids=tuple(reversed(data.context.security_ids))
                ),
            )
        )
    with pytest.raises(d.DCCUnavailable, match="target_provenance"):
        d.fit_dcc(replace(data, target_context=replace(data.target_context, calendar="other-grid")))


def test_dimension_above_observations_uses_qualified_spd_target() -> None:
    raw = np.random.Generator(np.random.PCG64(6222213)).standard_normal((12, 13))
    z = tuple(tuple(float(v) for v in row) for row in raw)
    context = context_for(z)
    target = analytical_target(
        raw, context=d.target_context(context), preprocessing="none", degrees_of_freedom=0
    )
    assert target.branch == "singular" and target.structural_nulls == 1
    data = d.input_from_target(z, context, target)
    result = d.evaluate_fixed(data.z, data.target, (0.05, 0.9))
    assert math.isfinite(result.nll_sum) and len(result.terminal_q) == 12


def test_reference_gradients_and_two_fresh_process_replays(tmp_path: Path) -> None:
    outputs = [tmp_path / "a.json", tmp_path / "b.json"]
    for output in outputs:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/qualify_dcc.py"), "--output", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    report = json.loads(outputs[0].read_text())
    assert len(report["derivatives"]) == 36
    assert len(report["fixed"]) == 3
    for row in report["derivatives"]:
        assert row["actual"] == pytest.approx(row["reference"], rel=1e-8, abs=1e-8)


def test_start_order_matches_frozen_r1() -> None:
    assert d.CAP == 0.99998 and len(d.STARTS) == 12
    assert d.STARTS == tuple(
        (a, s - a) for a in (0.01, 0.03, 0.05, 0.10) for s in (0.99, 0.97, 0.95)
    )
    assert all(a >= 0 and b >= 0 and a + b < d.CAP for a, b in d.STARTS)


@pytest.mark.parametrize("sessions", [1, 63, 64, 65, 129, 1260])
@pytest.mark.parametrize("theta", [(0.0, 0.0), (0.0, d.CAP), (0.05, 0.9), (0.4, d.CAP - 0.4)])
def test_blocked_likelihood_matches_independent_full_matrix_recurrence(
    sessions: int, theta: d.Theta
) -> None:
    # The reference propagates full matrices one session at a time; it does not
    # use the production linear filter, adjacent triples or block carry logic.
    x = np.random.Generator(np.random.PCG64(7152)).standard_normal((sessions, 5))
    c = np.eye(5) * 0.7 + np.ones((5, 5)) * 0.3
    z = tuple(tuple(float(v) for v in row) for row in x)
    target = tuple(tuple(float(v) for v in row) for row in c)
    q = c.copy()
    da = np.zeros_like(c)
    db = np.zeros_like(c)
    scores = []
    alpha = []
    beta = []
    a, b = theta
    for t, row in enumerate(x):
        if t:
            previous = np.outer(x[t - 1], x[t - 1])
            da, db = -c + previous + b * da, -c + q + b * db
            q = (1 - a - b) * c + a * previous + b * q
        pair_scores, pair_alpha, pair_beta = [], [], []
        for i in range(4):
            j = i + 1
            normalizer = np.sqrt(q[i, i] * q[j, j])
            rho = q[i, j] / normalizer
            correlation = np.array([[1.0, rho], [rho, 1.0]])
            v = row[[i, j]]
            # Direct Gaussian log determinant / inverse quadratic expression.
            inverse = np.linalg.inv(correlation)
            pair_scores.append(
                math.log(2 * math.pi)
                + np.linalg.slogdet(correlation)[1] / 2
                + float(v @ inverse @ v) / 2
            )
            # Matrix-density differential: tr((R^-1 - R^-1 vv' R^-1) dR)/2.
            density_derivative = inverse - inverse @ np.outer(v, v) @ inverse
            derivatives = []
            for sensitivity in (da, db):
                drho = (
                    sensitivity[i, j] / normalizer
                    - rho * (sensitivity[i, i] / q[i, i] + sensitivity[j, j] / q[j, j]) / 2
                )
                differential = np.array([[0.0, drho], [drho, 0.0]])
                derivatives.append(float(np.trace(density_derivative @ differential)) / 2)
            pair_alpha.append(derivatives[0])
            pair_beta.append(derivatives[1])
        scores.append(math.fsum(pair_scores) / 4)
        alpha.append(math.fsum(pair_alpha) / 4)
        beta.append(math.fsum(pair_beta) / 4)
    result = d.evaluate_fixed(z, target, theta)
    np.testing.assert_allclose(result.nll, scores, rtol=1e-12, atol=1e-10)
    assert result.nll_sum == pytest.approx(math.fsum(scores), rel=1e-12, abs=1e-8)
    assert result.gradient == pytest.approx(
        (math.fsum(alpha), math.fsum(beta)), rel=1e-10, abs=1e-8
    )
    for actual, matrix in (
        (result.terminal_q, q),
        (result.terminal_alpha, da),
        (result.terminal_beta, db),
    ):
        expected = [(matrix[i, i], matrix[i + 1, i + 1], matrix[i, i + 1]) for i in range(4)]
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-10)


def test_block_boundary_determinant_failure_is_not_clipped() -> None:
    rows = [(1.0, -1.0)] * 64 + [(1e100, 1e100), (1.0, 1.0)]
    with pytest.raises(d.DCCUnavailable, match="pair_determinant") as error:
        d.evaluate_fixed(tuple(rows), I2, (0.5, 0.4))
    assert "session 65, pair 0" in str(error.value)
