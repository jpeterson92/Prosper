"""Synthetic equation, integrity and refusal evidence; independent review stays open."""

import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from prosper.innovations import (
    InnovationContext,
    InnovationProfile,
    OHLCRow,
    regularized_innovation,
    transform_ohlc,
)

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "examples/synthetic/innovations"
REFERENCE: Any = json.loads((FOLDER / "reference.json").read_text())


@pytest.fixture
def inputs() -> tuple[InnovationContext, tuple[OHLCRow, ...]]:
    data = json.loads((FOLDER / "inputs.json").read_text())
    raw = data["context"]
    raw["security_ids"] = tuple(raw["security_ids"])
    raw["sessions"] = tuple(raw["sessions"])
    return InnovationContext(**raw), tuple(OHLCRow(**r) for r in data["rows"])


def test_frozen_r1_direct_reference_and_actions(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    result = transform_ohlc(context, rows)
    assert result.status == "ready" and not result.issues
    assert result.source_rows is rows and result.context is context
    assert result.series_status == ("usable", "usable")
    for matrix, name in (
        (result.preceding_close, "preceding_close"),
        (result.proxy, "proxy"),
        (result.innovations, "x"),
    ):
        assert len(matrix) == 12 and all(len(r) == 2 for r in matrix)
        assert [v for r in matrix for v in r] == pytest.approx(
            [float(r[name]) for r in REFERENCE["rows"]], rel=1e-8, abs=1e-12
        )
    # E08: compatible total return already includes actions; no extra dividend.
    assert result.preceding_close[0][0] == 50 and result.proxy[0][0] == 0
    assert result.preceding_close[1][0] == 99 and result.proxy[1][0] == 0
    assert result.source_rows[0].total_return == "0.0000"
    # E09: range-only and overnight-only closed expressions.
    assert result.proxy[2][0] == pytest.approx(83 * math.log(2) / 300)
    assert result.innovations[2][0] == 0
    assert result.proxy[3][0] == pytest.approx(17 * math.log(2) ** 2 / 25)


def test_e07_toy_sign_zero_and_r1_are_distinct() -> None:
    r = float(REFERENCE["E07"]["r_plus"])
    for sign in (-1, 0, 1):
        assert regularized_innovation(sign * r, 4, 2) == pytest.approx(sign, abs=1e-12)
    assert regularized_innovation(r, 4, 10000) == 2
    assert regularized_innovation(1e-9, 4, 10000) == pytest.approx(1e-5, rel=1e-8)


@pytest.mark.parametrize("arguments", [(0, -1, 2), (math.nan, 1, 2), (0, math.inf, 2), (0, 1, 0)])
def test_bad_primitive_arguments(arguments: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError):
        regularized_innovation(*arguments)


@pytest.mark.parametrize("factor", ["0.000001", "1000000", "1e-100", "1e100"])
def test_common_price_rescaling(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
    factor: str,
) -> None:
    context, rows = inputs
    with localcontext() as ctx:
        ctx.prec = 110
        scaled = tuple(
            replace(
                row,
                **{
                    name: str(Decimal(getattr(row, name)) * Decimal(factor))
                    for name in ("open", "high", "low", "close")
                },
            )
            for row in rows
        )
    before, after = transform_ohlc(context, rows), transform_ohlc(context, scaled)
    assert after.status == "ready"
    for a, b in zip(before.proxy, after.proxy, strict=True):
        assert a == pytest.approx(b, rel=1e-8, abs=1e-12)
    for a, b in zip(before.innovations, after.innovations, strict=True):
        assert a == pytest.approx(b, rel=1e-8, abs=1e-12)
    assert before.input_sha256 != after.input_sha256


def test_units_and_explicit_returns_reference(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    decimal = transform_ohlc(context, rows)
    percent = transform_ohlc(context, rows, units="percent-experiment")
    returns = transform_ohlc(context, rows, variant="returns-only")
    assert percent.effective_kappa == 100
    assert decimal.effective_kappa == 10000
    for i, row in enumerate(rows):
        t, j = divmod(i, 2)
        assert percent.innovations[t][j] == pytest.approx(100 * decimal.innovations[t][j])
        assert percent.proxy[t][j] == pytest.approx(10000 * decimal.proxy[t][j])
        # Equivalently transform the regularization's units and kappa together.
        assert regularized_innovation(float(row.total_return) * 100, percent.proxy[t][j], 100) == (
            pytest.approx(percent.innovations[t][j])
        )
        assert returns.innovations[t][j] == float(row.total_return)
    assert len({r.configuration_sha256 for r in (decimal, percent, returns)}) == 3


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("total_return", "NaN", "invalid_numeric"),
        ("total_return", "Infinity", "invalid_numeric"),
        ("total_return", "-1", "invalid_numeric"),
        ("total_return", "-2", "invalid_numeric"),
        ("total_return", "1e-1000", "invalid_numeric"),
        ("total_return", " 0", "invalid_numeric"),
        ("open", "0", "invalid_numeric"),
        ("low", "-1", "invalid_numeric"),
        ("high", "1", "invalid_numeric"),
        ("high", "49.99999999999999999", "invalid_numeric"),
        ("close", "1e1000", "invalid_numeric"),
        ("action", "unknown", "action_compatibility"),
        ("action_evidence_sha256", "", "action_compatibility"),
        ("compatibility", "", "action_compatibility"),
        ("return_vintage", "new", "mixed_vintage"),
        ("ohlc_vintage", "new", "mixed_vintage"),
        ("action_vintage", "new", "mixed_vintage"),
    ],
)
def test_located_row_refusals_preserve_rejected_source(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
    field: str,
    value: str,
    code: str,
) -> None:
    context, rows = inputs
    changed = (replace(rows[0], **{field: value}), *rows[1:])
    result = transform_ohlc(context, changed)
    assert result.status == "unavailable" and result.innovations == result.proxy == ()
    assert result.source_rows == changed
    located = [i for i in result.issues if i.code == code]
    assert located and located[0].session == rows[0].session
    assert located[0].security_id == rows[0].security_id


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("return_convention", "simple-price-return-decimal", "return_convention"),
        ("calendar", "", "missing_provenance"),
        ("construction", "", "missing_provenance"),
        ("source_sha256", "", "missing_provenance"),
        ("vintage", "", "missing_provenance"),
        ("timezone", "", "timezone"),
        ("fictional", False, "synthetic_only"),
        ("cutoff", "2099-01-01", "sessions"),
        ("sessions", (), "sessions"),
        ("security_ids", (), "security_identity"),
        ("security_ids", ("FICTIONAL-ALPHA", "FICTIONAL-ALPHA"), "security_identity"),
    ],
)
def test_context_refusals(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
    field: str,
    value: Any,
    code: str,
) -> None:
    context, rows = inputs
    result = transform_ohlc(replace(context, **{field: value}), rows)
    assert result.status == "unavailable" and any(i.code == code for i in result.issues)


def test_order_missing_and_duplicates(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    for changed in (rows[1:], (*rows, rows[0]), tuple(reversed(rows))):
        result = transform_ohlc(context, changed)
        assert result.status == "unavailable" and result.source_rows == changed
        assert any(i.code == "grid_order" for i in result.issues)
    missing = transform_ohlc(context, rows[2:])
    assert len([i for i in missing.issues if i.code == "missing_observation"]) == 2
    reordered_context = replace(context, security_ids=tuple(reversed(context.security_ids)))
    assert transform_ohlc(reordered_context, rows).status == "unavailable"
    reordered = tuple(
        r
        for t in context.sessions
        for r in rows
        if r.session == t and r.security_id == "FICTIONAL-BETA"
    )
    reordered = tuple(v for pair in zip(reordered, rows[::2], strict=True) for v in pair)
    before, after = transform_ohlc(context, rows), transform_ohlc(reordered_context, reordered)
    assert after.status == "ready"
    assert after.innovations == tuple(tuple(reversed(r)) for r in before.innovations)


def test_zero_series_and_numeric_failures(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    zero = tuple(
        replace(r, total_return="0", open="100", close="100", low="100", high="200") for r in rows
    )
    result = transform_ohlc(context, zero)
    assert result.status == "unusable-series"
    assert result.series_status == ("zero-second-moment", "zero-second-moment")
    assert result.proxy[0][0] > 0 and result.innovations[0] == (0, 0)
    for changed in (
        replace(rows[0], total_return="1e-200"),
        replace(
            rows[0], total_return="-.5", open="1e308", high="1e308", low="1e308", close="1e308"
        ),
    ):
        bad = transform_ohlc(context, (changed, *rows[1:]))
        assert bad.status == "unavailable"
        assert any(i.code == "derived_numeric" for i in bad.issues)


@pytest.mark.parametrize(
    "profile",
    [
        InnovationProfile(f="0"),
        InnovationProfile(a3="2"),
        InnovationProfile(kappa="0"),
        InnovationProfile(kappa="2"),
        InnovationProfile(f="NaN"),
        InnovationProfile(kappa="10000.0000000000001"),
        InnovationProfile(identity="toy", a3="1.00000000000000001"),
    ],
)
def test_invalid_profile_no_fallback(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
    profile: InnovationProfile,
) -> None:
    context, rows = inputs
    result = transform_ohlc(context, rows, profile=profile)
    assert result.status == "unavailable" and result.effective_kappa is None
    assert result.innovations == ()


def test_frozen_identity_and_cutoff(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    original = transform_ohlc(context, rows)
    assert original == transform_ohlc(context, rows)
    for changed in (
        replace(rows[0], action="dividend"),
        replace(rows[0], total_return="0.0"),
        replace(rows[0], action_evidence_sha256="1" * 64),
    ):
        assert (
            transform_ohlc(context, (changed, *rows[1:])).identity_sha256
            != original.identity_sha256
        )
    vintage = replace(context, vintage="revision-2")
    revised_rows = tuple(
        replace(
            r, return_vintage="revision-2", ohlc_vintage="revision-2", action_vintage="revision-2"
        )
        for r in rows
    )
    assert transform_ohlc(vintage, revised_rows).identity_sha256 != original.identity_sha256
    later = (*rows, replace(rows[-1], session="2000-01-13"))
    assert transform_ohlc(context, later).status == "unavailable"
    assert transform_ohlc(context, rows) == original  # Frozen tuple was never extended.
    with pytest.raises(FrozenInstanceError):
        original.status = "changed"  # type: ignore[misc]


def test_independent_fixed_state_handoff() -> None:
    stack = REFERENCE["stack_fixed_state"]
    assert stack["s2"] == "3" and stack["tau"] == 3
    assert stack["variance_fractions"][0] == "11900/7059"
    assert float(stack["nll_sum_90_digits"]) == pytest.approx(10.471074718877173, abs=1e-12)
    states = [Fraction(v) for v in stack["variance_fractions"]]
    x = [Fraction(v) for v in stack["x"]]
    first = Fraction(3, 10) + x[-1] ** 2 / 5 + Fraction(7, 10) * states[-1]
    assert Fraction(stack["forecast_1_to_21_fractions"][0]) == first
    assert Fraction(stack["forecast_1_to_21_fractions"][-1]) == (
        3 + Fraction(9, 10) ** 20 * (first - 3)
    )
    assert REFERENCE["E01"]["forecast_1_to_21"] == ["4"] * 21
    for series in REFERENCE["idr_fixed_state"]:
        assert len(series["x"]) == len(series["variance"]) == len(series["nll"]) == 12
        assert float(series["s2"]) > 0 and len(series["forecast_1_to_21"]) == 21


def test_declared_sessions_and_explicit_toy_profile(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    for sessions in (
        tuple(reversed(context.sessions)),
        ("invalid-date",),
        (*context.sessions, context.sessions[-1]),
    ):
        result = transform_ohlc(replace(context, sessions=sessions), rows)
        assert result.status == "unavailable" and any(i.code == "sessions" for i in result.issues)
    missing_day = tuple(row for row in rows if row.session != context.sessions[4])
    result = transform_ohlc(context, missing_day)
    missing = [i for i in result.issues if i.code == "missing_observation"]
    assert len(missing) == 2 and all(i.session == context.sessions[4] for i in missing)
    toy = transform_ohlc(
        context, rows, profile=InnovationProfile(identity="explicit-toy", kappa="2")
    )
    assert toy.status == "ready" and toy.effective_kappa == 2
    assert toy.configuration_sha256 != transform_ohlc(context, rows).configuration_sha256


def test_unsupported_configuration_and_underflow(
    inputs: tuple[InnovationContext, tuple[OHLCRow, ...]],
) -> None:
    context, rows = inputs
    for kwargs in ({"variant": "hidden-fallback"}, {"units": "percent-input"}):
        result = transform_ohlc(context, rows, **kwargs)  # type: ignore[arg-type]
        assert result.status == "unavailable" and result.innovations == ()
    # Nonzero x whose binary64 squared moment is unrepresentable stays unusable.
    tiny = tuple(
        replace(row, total_return="1e-100", open="50", high="50", low="50", close="50")
        for row in rows
    )
    result = transform_ohlc(context, tiny)
    assert result.status == "unusable-series"
    assert result.series_status == ("unrepresentable-second-moment",) * 2
    assert result.innovations[0][0] != 0


def test_reference_and_component_fresh_process_replay(tmp_path: Path) -> None:
    files = [tmp_path / "first.json", tmp_path / "second.json"]
    for output in files:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/qualify_innovations.py"), "--output", str(output)],
            check=True,
            cwd=ROOT,
            capture_output=True,
        )
    assert files[0].read_bytes() == files[1].read_bytes()
