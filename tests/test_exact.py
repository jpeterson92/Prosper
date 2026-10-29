"""Synthetic primitive expectations; rational references do not use Decimal allocation."""

from decimal import ROUND_UP, Decimal, Inexact, InvalidOperation, Rounded, localcontext
from fractions import Fraction
from typing import Literal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prosper.exact import (
    DiagnosticAllocation,
    ExactValue,
    ExactValueError,
    Sign,
    UnknownValue,
    allocate_diagnostic_basis,
    calculate,
    parse_value,
)


def known(text: str, sign: Sign = Sign.NONNEGATIVE) -> ExactValue:
    return ExactValue(text, sign)


def split(quantity: str, basis: str, sold: str, quantum: str = "0.01") -> DiagnosticAllocation:
    return allocate_diagnostic_basis(
        remaining_quantity=known(quantity),
        remaining_basis=known(basis),
        sold_quantity=known(sold),
        basis_quantum=known(quantum),
    )


@pytest.mark.parametrize(
    ("text", "canonical", "quantum"),
    [
        ("0", "0", "1"),
        ("-0.00", "0", "0.01"),
        ("001.2300", "1.23", "0.0001"),
        ("100.00", "100", "0.01"),
        ("0.000000000001", "0.000000000001", "0.000000000001"),
    ],
)
def test_canonicalization_retains_evidence(text: str, canonical: str, quantum: str) -> None:
    value = known(text, Sign.SIGNED)
    assert value.canonical == canonical
    assert value.original_text == text
    assert value.source_quantum == Decimal(quantum)


@pytest.mark.parametrize("raw", [0.1, 1, True, Decimal("0.1"), {}, [], None])
def test_non_string_never_becomes_a_known_value(raw: object) -> None:
    with pytest.raises(ExactValueError) as failure:
        parse_value(raw, field_name="lots[0].basis", sign=Sign.NONNEGATIVE)
    assert failure.value.field_name == "lots[0].basis"
    assert failure.value.code in ("decimal_string_required", "unknown_reason_required")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "+1",
        " 1",
        "1 ",
        "1e2",
        "NaN",
        "Infinity",
        "-Inf",
        "1,000",
        "$1",
        ".1",
        "1.",
        "1_000",
        "\u0661",
        "1\n",
    ],
)
def test_invalid_fixed_point(text: str) -> None:
    with pytest.raises(ExactValueError, match="fixed_point_required"):
        known(text)


@pytest.mark.parametrize("text", ["-1", "-0", "-0.00"])
def test_nonnegative_forbids_negative_spelling(text: str) -> None:
    with pytest.raises(ExactValueError, match="negative_sign_forbidden"):
        known(text)


def test_signs_and_numeric_bounds() -> None:
    assert known("-1", Sign.SIGNED).canonical == "-1"
    with pytest.raises(ExactValueError, match="positive_value_required"):
        known("0", Sign.POSITIVE)
    assert known("9999999999999999999999999999").canonical == "9999999999999999999999999999"
    assert known("9999999999999999.999999999999").canonical == "9999999999999999.999999999999"
    with pytest.raises(ExactValueError, match="significant_digits_exceeded"):
        known("10000000000000000000000000000")
    with pytest.raises(ExactValueError, match="significant_digits_exceeded"):
        known("9999999999999999999999999999.0")
    for text in ("0.1000000000001", "0.1000000000000"):
        with pytest.raises(ExactValueError, match="fractional_digits_exceeded"):
            known(text)
    with pytest.raises(ExactValueError, match="source_length_exceeded"):
        known("0" * 10000)


def test_unknown_pairs_and_propagation() -> None:
    missing = parse_value(
        None, field_name="basis", sign=Sign.NONNEGATIVE, unknown_reason="source_missing"
    )
    assert missing == UnknownValue(("source_missing",))
    for reason in (None, "", "  "):
        with pytest.raises(ExactValueError, match="unknown_reason_required"):
            parse_value(None, field_name="basis", sign=Sign.NONNEGATIVE, unknown_reason=reason)
    with pytest.raises(ExactValueError, match="reason_requires_null"):
        parse_value("0", field_name="basis", sign=Sign.NONNEGATIVE, unknown_reason="missing")
    with pytest.raises(ValueError):
        UnknownValue(())
    result = calculate("multiply", missing, known("0"), field_name="result", sign=Sign.SIGNED)
    assert result == missing
    combined = calculate(
        "add",
        missing,
        UnknownValue(("contradictory", "source_missing")),
        field_name="result",
        sign=Sign.SIGNED,
    )
    assert combined == UnknownValue(("source_missing", "contradictory"))
    allocation = allocate_diagnostic_basis(
        remaining_quantity=known("3"),
        remaining_basis=missing,
        sold_quantity=known("1"),
        basis_quantum=known("0.01"),
    )
    assert allocation.allocated_basis == missing == allocation.remaining_basis
    assert allocation.remaining_quantity.canonical == "2"


def test_exact_arithmetic_and_unsupported_results() -> None:
    cases: tuple[tuple[Literal["add", "subtract", "multiply"], str, str, str], ...] = (
        ("add", "0.1", "0.2", "0.3"),
        ("subtract", "1080", "1181", "-101"),
        ("multiply", "90", "12", "1080"),
    )
    for operation, left, right, expected in cases:
        value = calculate(
            operation, known(left), known(right), field_name="result", sign=Sign.SIGNED
        )
        assert isinstance(value, ExactValue)
        assert value.canonical == expected
    with pytest.raises(ExactValueError, match="significant_digits_exceeded"):
        calculate(
            "add",
            known("9999999999999999999999999999"),
            known("1"),
            field_name="result",
            sign=Sign.NONNEGATIVE,
        )
    with pytest.raises(ExactValueError, match="fractional_digits_exceeded"):
        calculate(
            "multiply",
            known("0.000000000001"),
            known("0.1"),
            field_name="result",
            sign=Sign.NONNEGATIVE,
        )
    with pytest.raises(ExactValueError, match="negative_sign_forbidden"):
        calculate("subtract", known("1"), known("2"), field_name="cash", sign=Sign.NONNEGATIVE)


def test_prescribed_sequential_allocation() -> None:
    quantity = known("3")
    basis = known("1.00")
    allocations = []
    for expected in ("0.33", "0.34", "0.33"):
        allocation = allocate_diagnostic_basis(
            remaining_quantity=quantity,
            remaining_basis=basis,
            sold_quantity=known("1"),
            basis_quantum=known("0.01"),
        )
        assert isinstance(allocation.allocated_basis, ExactValue)
        assert allocation.allocated_basis.canonical == expected
        assert isinstance(allocation.remaining_basis, ExactValue)
        allocations.append(Fraction(allocation.allocated_basis.value))
        quantity, basis = allocation.remaining_quantity, allocation.remaining_basis
    assert sum(allocations) == 1
    assert quantity.canonical == basis.canonical == "0"


@pytest.mark.parametrize(
    ("quantity", "basis", "sold", "quantum", "expected"),
    [
        ("2", "0.01", "1", "0.01", "0"),
        ("2", "0.03", "1", "0.01", "0.02"),
        ("0.25", "10.00", "0.1", "0.01", "4"),
        ("3", "0", "1", "0.01", "0"),
        ("2", "30", "1", "10", "20"),
        (
            "9999999999999999999999999999",
            "9999999999999999999999999999",
            "9999999999999999999999999998",
            "1",
            "9999999999999999999999999998",
        ),
        ("0.000000000003", "0.000000000001", "0.000000000001", "0.000000000001", "0"),
    ],
)
def test_rounding_and_extremes(
    quantity: str, basis: str, sold: str, quantum: str, expected: str
) -> None:
    allocation = split(quantity, basis, sold, quantum)
    assert isinstance(allocation.allocated_basis, ExactValue)
    assert allocation.allocated_basis.canonical == expected


@pytest.mark.parametrize(
    ("quantity", "basis", "sold", "quantum", "code"),
    [
        ("0", "1", "1", "0.01", "positive_value_required"),
        ("1", "1", "0", "0.01", "positive_value_required"),
        ("1", "1", "2", "0.01", "exceeds_remaining_quantity"),
        ("2", "1.001", "1", "0.01", "basis_quantum_mismatch"),
        ("2", "1", "1", "0", "power_of_ten_required"),
        ("2", "1", "1", "0.05", "power_of_ten_required"),
        ("1000000000000000000000000000", "1", "0.01", "0.01", "significant_digits_exceeded"),
    ],
)
def test_invalid_allocations(quantity: str, basis: str, sold: str, quantum: str, code: str) -> None:
    with pytest.raises(ExactValueError, match=code):
        split(quantity, basis, sold, quantum)


def test_unknown_quantum_and_known_contradictions() -> None:
    allocation = allocate_diagnostic_basis(
        remaining_quantity=known("1"),
        remaining_basis=known("1"),
        sold_quantity=known("1"),
        basis_quantum=UnknownValue(("quantum_missing",)),
    )
    assert allocation.allocated_basis == UnknownValue(("quantum_missing",))
    assert allocation.remaining_quantity.canonical == "0"
    with pytest.raises(ExactValueError, match="negative_basis"):
        allocate_diagnostic_basis(
            remaining_quantity=known("2"),
            remaining_basis=known("-1", Sign.SIGNED),
            sold_quantity=known("1"),
            basis_quantum=UnknownValue(("quantum_missing",)),
        )
    with pytest.raises(ExactValueError, match="negative_basis"):
        allocate_diagnostic_basis(
            remaining_quantity=known("1"),
            remaining_basis=known("-0", Sign.SIGNED),
            sold_quantity=known("1"),
            basis_quantum=known("0.01"),
        )


@pytest.mark.parametrize("preexisting_flags", [False, True])
def test_hostile_decimal_context_does_not_change_values_or_rounding(
    preexisting_flags: bool,
) -> None:
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = ROUND_UP
        ambient.Emax = 2
        ambient.Emin = -2
        ambient.traps[Inexact] = True
        ambient.traps[Rounded] = True
        # localcontext inherits sticky flags from prior work in this worker.
        # Exercise both a clean caller and an already signaled caller explicitly.
        ambient.clear_flags()
        if preexisting_flags:
            for signal in (InvalidOperation, Inexact, Rounded):
                ambient.flags[signal] = True
        before = ambient.copy()
        assert known("1234567890.1200").canonical == "1234567890.12"
        allocation = split("3", "1.00", "1")
        assert isinstance(allocation.allocated_basis, ExactValue)
        assert allocation.allocated_basis.canonical == "0.33"
        assert ambient.prec == 2 and ambient.rounding == ROUND_UP
        assert ambient.flags == before.flags
        assert ambient.traps == before.traps
        assert ambient.Emax == before.Emax and ambient.Emin == before.Emin


@settings(max_examples=250, derandomize=True, database=None)
@given(cents=st.integers(0, 10**16), quantity=st.integers(1, 10**12), data=st.data())
def test_allocation_matches_independent_rational_reference(
    cents: int,
    quantity: int,
    data: st.DataObject,
) -> None:
    sold = data.draw(st.integers(1, quantity))
    allocation = split(str(quantity), f"{cents // 100}.{cents % 100:02d}", str(sold))
    assert isinstance(allocation.allocated_basis, ExactValue)
    assert isinstance(allocation.remaining_basis, ExactValue)
    # Fraction.__round__ implements integer ties-to-even without Decimal or module helpers.
    expected_cents = round(Fraction(cents * sold, quantity))
    assert Fraction(allocation.allocated_basis.value) == Fraction(expected_cents, 100)
    assert Fraction(allocation.allocated_basis.value) + Fraction(
        allocation.remaining_basis.value
    ) == (Fraction(cents, 100))
    assert Fraction(allocation.remaining_quantity.value) == quantity - sold


@settings(max_examples=150, derandomize=True, database=None)
@given(coefficient=st.integers(-(10**28 - 1), 10**28 - 1), scale=st.integers(0, 12))
def test_admitted_values_round_trip_without_binary_float(coefficient: int, scale: int) -> None:
    digits = str(abs(coefficient)).zfill(scale + 1)
    text = ("-" if coefficient < 0 else "") + (
        digits if scale == 0 else digits[:-scale] + "." + digits[-scale:]
    )
    parsed = known(text, Sign.SIGNED)
    assert Fraction(parsed.value) == Fraction(coefficient, 10**scale)
    assert known(parsed.canonical, Sign.SIGNED).canonical == parsed.canonical


def fixed(coefficient: int, scale: int) -> str:
    digits = str(coefficient).zfill(scale + 1)
    return digits if scale == 0 else digits[:-scale] + "." + digits[-scale:]


@settings(max_examples=300, derandomize=True, database=None)
@given(
    units=st.integers(0, 10**28 - 1),
    quantity_units=st.integers(1, 10**28 - 1),
    basis_scale=st.integers(0, 12),
    quantity_scale=st.integers(0, 12),
    data=st.data(),
)
def test_full_domain_allocation_against_rationals(
    units: int, quantity_units: int, basis_scale: int, quantity_scale: int, data: st.DataObject
) -> None:
    sold_units = data.draw(st.integers(1, quantity_units))
    allocation = split(
        fixed(quantity_units, quantity_scale),
        fixed(units, basis_scale),
        fixed(sold_units, quantity_scale),
        fixed(1, basis_scale),
    )
    assert isinstance(allocation.allocated_basis, ExactValue)
    assert isinstance(allocation.remaining_basis, ExactValue)
    expected_units = round(Fraction(units * sold_units, quantity_units))
    assert Fraction(allocation.allocated_basis.value) == Fraction(expected_units, 10**basis_scale)
    assert Fraction(allocation.remaining_basis.value) == Fraction(
        units - expected_units, 10**basis_scale
    )
    assert Fraction(allocation.remaining_quantity.value) == Fraction(
        quantity_units - sold_units, 10**quantity_scale
    )


@settings(max_examples=100, derandomize=True, database=None)
@given(cents=st.integers(0, 10**20), shares=st.integers(1, 20))
def test_sequential_disposals_always_conserve(cents: int, shares: int) -> None:
    basis = known(fixed(cents, 2))
    disposed = Fraction(0)
    for remaining in range(shares, 0, -1):
        allocation = allocate_diagnostic_basis(
            remaining_quantity=known(str(remaining)),
            remaining_basis=basis,
            sold_quantity=known("1"),
            basis_quantum=known("0.01"),
        )
        assert isinstance(allocation.allocated_basis, ExactValue)
        assert isinstance(allocation.remaining_basis, ExactValue)
        disposed += Fraction(allocation.allocated_basis.value)
        basis = allocation.remaining_basis
        assert disposed + Fraction(basis.value) == Fraction(cents, 100)
    assert basis.canonical == "0"


def test_intermediate_product_can_exceed_book_bounds_without_rounding() -> None:
    # Product has 56 digits, but division yields supported exact 28-digit outputs.
    result = split(
        "9999999999999999999999999999",
        "9999999999999999999999999999",
        "4999999999999999999999999999",
        "1",
    )
    assert isinstance(result.allocated_basis, ExactValue)
    assert result.allocated_basis.canonical == "4999999999999999999999999999"
    assert isinstance(result.remaining_basis, ExactValue)
    assert result.remaining_basis.canonical == "5000000000000000000000000000"


def test_fine_quantum_cannot_create_an_unsupported_residual() -> None:
    with pytest.raises(ExactValueError, match="significant_digits_exceeded"):
        split("1000000000000000000000000000", "1000000000000000000000000000", "0.01")
