"""Stack/reference checks, not model acceptance or financial correctness."""

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/qualify_numerics.py"
SPEC = importlib.util.spec_from_file_location("qualify_numerics", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PROBE: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def test_stack_against_independently_specified_oracles() -> None:
    result = PROBE.qualify()
    assert len(result["outputs"]["spectra"]) == 9
    assert len(result["outputs"]["optimizations"]) == 3
    assert result["input"]["s2"] == "3"
    assert result["input"]["tau"] == 3
    assert result["input"]["variance_fractions"] == [
        "11900/7059",
        "23719/14118",
        "321331/141180",
        "2672857/1411800",
        "48357799/14118000",
    ]
    assert result["outputs"]["nll_sum"] == pytest.approx(10.471074718877173, abs=1e-12)


@pytest.mark.parametrize(
    ("actual", "reference", "atol", "scale"),
    [
        (math.nan, 1, 1e-8, 1),
        (1, math.inf, 1e-8, 1),
        (1, 1, -1, 1),
        (1, 1, 1e-8, 0),
        (1, 1, 1e-8, math.inf),
    ],
)
def test_unknown_comparison_does_not_pass(
    actual: float, reference: float, atol: float, scale: float
) -> None:
    with pytest.raises(ValueError):
        PROBE.close(actual, reference, atol=atol, scale=scale)


def test_failed_accuracy_is_not_repaired() -> None:
    with pytest.raises(AssertionError):
        PROBE.close(1.01, 1.0, atol=1e-8)


def test_unqualified_runtime_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PROBE.metadata, "version", lambda _: "0.0.unqualified")
    with pytest.raises(ValueError, match="unqualified versions"):
        PROBE.qualify()


def test_nonconverged_optimizer_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PROBE.optimize,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(success=False, message="synthetic nonconvergence"),
    )
    with pytest.raises(AssertionError, match="synthetic nonconvergence"):
        PROBE.qualify()
