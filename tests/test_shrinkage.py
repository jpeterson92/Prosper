"""Synthetic analytical-target cases; independent model acceptance remains open."""

import hashlib
import importlib.util
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from prosper import shrinkage
from prosper.shrinkage import TargetUnavailable, analytical_target

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/qualify_shrinkage.py"
SPEC = importlib.util.spec_from_file_location("qualify_shrinkage", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PROBE: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def test_independent_spectral_and_closed_expression_references() -> None:
    result = PROBE.qualify()
    assert len(result["cases"]) == 10
    assert {c["branch"] for c in result["cases"]} == {"singular", "nonsingular"}
    assert result["closed_expressions"]["E11_d0"].startswith("59.662858962")


@pytest.mark.parametrize("scale", [1e-6, 1.0, 1e6])
@pytest.mark.parametrize("singular", [False, True])
def test_scale_order_spd_and_input_immutability(scale: float, singular: bool) -> None:
    n, p = (12, 15) if singular else (64, 4)
    spectrum = [str((i + 4) / 8) for i in range(min(n, p))]
    x, _ = PROBE.fixture(n, p, spectrum)
    original = x.copy()
    context = PROBE.context(p)
    baseline = analytical_target(x, context=context, preprocessing="none", degrees_of_freedom=0)
    result = analytical_target(
        x * scale,
        context=context,
        preprocessing="none",
        degrees_of_freedom=0,
    )
    np.testing.assert_array_equal(x, original)
    np.testing.assert_allclose(result.covariance, baseline.covariance * scale**2, rtol=1e-8)
    np.testing.assert_allclose(result.correlation, baseline.correlation, rtol=1e-8, atol=1e-10)
    permutation = np.arange(p)[::-1]
    reordered = analytical_target(
        x[:, permutation],
        context=replace(context, security_ids=context.security_ids[::-1]),
        preprocessing="none",
        degrees_of_freedom=0,
    )
    np.testing.assert_allclose(
        reordered.covariance,
        baseline.covariance[np.ix_(permutation, permutation)],
        rtol=1e-8,
        atol=1e-12 * float(np.max(np.mean(x * x, axis=0))),
    )
    assert np.linalg.eigvalsh(result.covariance)[0] > 0
    np.testing.assert_allclose(np.diag(result.correlation), 1, atol=1e-14)
    np.testing.assert_array_equal(result.covariance, result.covariance.T)
    with pytest.raises(ValueError):
        result.covariance.setflags(write=True)


@pytest.mark.parametrize(
    ("shape", "preprocessing", "k", "code"),
    [
        ((11, 2), "none", 0, "short_history"),
        ((12, 2), "demean", 1, "short_history"),
        ((12, 12), "none", 0, "unsupported_equality"),
        ((13, 12), "demean", 1, "unsupported_equality"),
        ((64, 2), "none", 1, "preprocessing"),
        ((64, 2), "demean", 0, "preprocessing"),
        ((64, 2), "other", 0, "preprocessing"),
        ((64, 2), "residuals", -1, "preprocessing"),
        ((64, 2), "none", True, "preprocessing"),
    ],
)
def test_effective_observations_and_unsupported_domains(
    shape: tuple[int, int],
    preprocessing: Any,
    k: int,
    code: str,
) -> None:
    with pytest.raises(TargetUnavailable) as exc:
        analytical_target(
            np.ones(shape),
            context=PROBE.context(shape[1]),
            preprocessing=preprocessing,
            degrees_of_freedom=k,
        )
    assert exc.value.code == code


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_observations(value: float) -> None:
    x = np.ones((64, 2))
    x[4, 1] = value
    with pytest.raises(TargetUnavailable, match="nonfinite_input"):
        analytical_target(x, context=PROBE.context(2), preprocessing="none", degrees_of_freedom=0)


@pytest.mark.parametrize("kind", ["zero", "duplicate", "nearzero", "singular-extra", "constant"])
def test_no_silent_rank_repair_or_stock_deletion(kind: str) -> None:
    if kind == "singular-extra":
        x, _ = PROBE.fixture(12, 15, ["1"] * 12)
        x[-1] = 0
    else:
        x, _ = PROBE.fixture(64, 3, ["0.00000000000001", "1", "2"])
        if kind == "zero":
            x[:, 0] = 0
        elif kind == "duplicate":
            x[:, 0] = x[:, 1]
        elif kind == "constant":
            x = np.ones((64, 3))
    with pytest.raises(TargetUnavailable, match="zero_variance|rank"):
        analytical_target(
            x,
            context=PROBE.context(x.shape[1]),
            preprocessing="none",
            degrees_of_freedom=0,
        )


@pytest.mark.parametrize("kind", ["int", "complex", "1d", "empty", "overflow", "underflow"])
def test_explicit_float_cast_shape_and_representability(kind: str) -> None:
    x: Any = np.ones((64, 2))
    if kind == "int":
        x = x.astype(np.int64)
    elif kind == "complex":
        x = x.astype(np.complex128)
    elif kind == "1d":
        x = x[:, 0]
    elif kind == "empty":
        x = x[:0]
    elif kind == "overflow":
        x *= 1e200
    elif kind == "underflow":
        x *= 1e-200
    with pytest.raises(TargetUnavailable, match="input_shape_type|numeric_scale"):
        analytical_target(x, context=PROBE.context(2), preprocessing="none", degrees_of_freedom=0)


@pytest.mark.parametrize("field", ["security_ids", "source_sha256", "cutoff", "calendar"])
def test_missing_or_ambiguous_provenance(field: str) -> None:
    x, _ = PROBE.fixture(64, 2, ["1", "2"])
    invalid: Any = ("duplicate", "duplicate") if field == "security_ids" else ""
    if field == "source_sha256":
        invalid = ("not-a-hash",)
    with pytest.raises(TargetUnavailable, match="provenance"):
        analytical_target(
            x,
            context=replace(PROBE.context(2), **{field: invalid}),
            preprocessing="none",
            degrees_of_freedom=0,
        )


def test_identity_replay_and_frozen_cutoff() -> None:
    x, _ = PROBE.fixture(64, 3, ["1", "2", "3"])
    future = np.vstack((x, np.ones((1, 3))))
    context = PROBE.context(3)
    first = analytical_target(x, context=context, preprocessing="none", degrees_of_freedom=0)
    future[-1] = 999
    replay = analytical_target(
        future[:64],
        context=context,
        preprocessing="none",
        degrees_of_freedom=0,
    )
    assert first.model_sha256 == replay.model_sha256
    np.testing.assert_array_equal(first.covariance, replay.covariance)
    changed = analytical_target(
        x,
        context=replace(context, cutoff="later-synthetic-cutoff"),
        preprocessing="none",
        degrees_of_freedom=0,
    )
    assert changed.model_sha256 != first.model_sha256
    changed_source = analytical_target(
        x,
        context=replace(context, source_sha256=("1" * 64,)),
        preprocessing="none",
        degrees_of_freedom=0,
    )
    assert changed_source.model_sha256 != first.model_sha256
    residuals = analytical_target(
        x,
        context=context,
        preprocessing="residuals",
        degrees_of_freedom=1,
    )
    assert residuals.effective_observations == 63
    assert residuals.model_sha256 != first.model_sha256
    assert not np.array_equal(residuals.covariance, first.covariance)


def test_perturbed_reference_is_refused() -> None:
    with pytest.raises(AssertionError, match="reference mismatch"):
        PROBE.assert_close(np.array([1.01]), np.array([1.0]), 1e-12)


def test_masked_unknowns_are_not_coerced_into_observations() -> None:
    mask = np.zeros((64, 2), dtype=np.bool_)
    mask[0, 0] = True
    data = np.ma.array(np.ones((64, 2)), mask=mask)
    with pytest.raises(TargetUnavailable, match="input_shape_type"):
        analytical_target(
            data,
            context=PROBE.context(2),
            preprocessing="none",
            degrees_of_freedom=0,
        )


def test_source_and_frozen_specification_are_bound() -> None:
    assert (
        shrinkage.IMPLEMENTATION_SHA256
        == hashlib.sha256(Path(shrinkage.__file__).read_bytes()).hexdigest()
    )
    assert (
        shrinkage.SPECIFICATION_SHA256
        == hashlib.sha256(
            (SCRIPT.parents[1] / "docs/tasks/T006.2.1.1-python-numerical-spec.md").read_bytes()
        ).hexdigest()
    )


@pytest.mark.parametrize("mode", ["negative", "eigensolver", "non-spd"])
def test_failed_numerical_backend_never_returns_a_fallback(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    x, _ = PROBE.fixture(64, 2, ["1", "2"])
    if mode == "negative":
        monkeypatch.setattr(
            "prosper.shrinkage.linalg.eigh",
            lambda *args, **kwargs: (np.array([-1.0, 2.0]), np.eye(2)),
        )
        code = "negative_spectrum"
    elif mode == "eigensolver":

        def fail(*args: Any, **kwargs: Any) -> None:
            raise np.linalg.LinAlgError("synthetic solver failure")

        monkeypatch.setattr("prosper.shrinkage.linalg.eigh", fail)
        code = "numerical_failure"
    else:
        monkeypatch.setattr(
            "prosper.shrinkage.linalg.eigvalsh",
            lambda *args, **kwargs: np.array([1e-14, 1.0]),
        )
        code = "target_not_spd"
    with pytest.raises(TargetUnavailable, match=code):
        analytical_target(x, context=PROBE.context(2), preprocessing="none", degrees_of_freedom=0)


def test_subnormal_output_does_not_silently_lose_rank_precision() -> None:
    x, _ = PROBE.fixture(64, 2, ["1", "2"])
    with pytest.raises(TargetUnavailable, match="numeric_scale"):
        analytical_target(
            x * 1e-155,
            context=PROBE.context(2),
            preprocessing="none",
            degrees_of_freedom=0,
        )
