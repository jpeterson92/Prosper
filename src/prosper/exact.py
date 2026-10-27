"""Bounded book values and diagnostic allocation, not broker/tax rules."""

import re
from dataclasses import dataclass, field
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    localcontext,
)
from enum import Enum
from typing import Literal

MAX_SIGNIFICANT = 28
MAX_FRACTIONAL = 12
WORKING_PRECISION = 80
_FIXED = re.compile(r"-?[0-9]+(?:\.[0-9]+)?", re.ASCII)


class Sign(Enum):
    SIGNED = "signed"
    NONNEGATIVE = "nonnegative"
    POSITIVE = "positive"


class ExactValueError(ValueError):
    """Located failure without embedding the supplied value in diagnostics."""

    def __init__(self, field_name: str, code: str) -> None:
        self.field_name = field_name
        self.code = code
        super().__init__(f"{field_name}: {code}")


def _context(*, allow_rounding: bool = False) -> Context:
    # Construct a fresh context; never inherit caller precision, traps or rounding.
    context = Context(
        prec=WORKING_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    context.traps[Inexact] = not allow_rounding
    context.traps[Rounded] = not allow_rounding
    return context


def _canonical(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True)
class ExactValue:
    """Validated fixed-point input; construction preserves its spelling and unit.

    Leading integer zeros are accepted. Bounds apply to the source coefficient
    (leading zeros excluded, trailing zeros included) and source fractional scale.
    Arithmetic creates derived spellings; callers retain source objects as evidence.
    """

    original_text: str
    sign: Sign
    field_name: str = field(default="value", compare=False)
    value: Decimal = field(init=False)
    canonical: str = field(init=False)
    source_quantum: Decimal = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sign, Sign):
            raise ExactValueError(self.field_name, "invalid_sign_rule")
        if not isinstance(self.original_text, str):
            raise ExactValueError(self.field_name, "decimal_string_required")
        # Bound work before regex/Decimal conversion, including excessive zero padding.
        if len(self.original_text) > MAX_SIGNIFICANT + MAX_FRACTIONAL + 2:
            raise ExactValueError(self.field_name, "source_length_exceeded")
        if _FIXED.fullmatch(self.original_text) is None:
            raise ExactValueError(self.field_name, "fixed_point_required")
        fractional = len(self.original_text.partition(".")[2])
        if fractional > MAX_FRACTIONAL:
            raise ExactValueError(self.field_name, "fractional_digits_exceeded")
        value = Decimal(self.original_text)
        if not value.is_finite():
            raise ExactValueError(self.field_name, "nonfinite")
        if len(value.as_tuple().digits) > MAX_SIGNIFICANT:
            raise ExactValueError(self.field_name, "significant_digits_exceeded")
        if self.sign is not Sign.SIGNED and value.is_signed():
            raise ExactValueError(self.field_name, "negative_sign_forbidden")
        if self.sign is Sign.POSITIVE and value.is_zero():
            raise ExactValueError(self.field_name, "positive_value_required")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "canonical", _canonical(value))
        object.__setattr__(self, "source_quantum", Decimal((0, (1,), -fractional)))


@dataclass(frozen=True)
class UnknownValue:
    """An explicit missing fact with one or more retained reasons, never zero."""

    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reasons, tuple) or not self.reasons:
            raise ValueError("unknown requires a tuple of reasons")
        if any(not isinstance(reason, str) or not reason.strip() for reason in self.reasons):
            raise ValueError("unknown requires nonempty reasons")


type BookValue = ExactValue | UnknownValue


def parse_value(
    raw: object,
    *,
    field_name: str,
    sign: Sign,
    unknown_reason: str | None = None,
) -> BookValue:
    """Parse an exact string or explicit null-with-reason; reject ambiguous pairs."""
    if raw is None:
        if not isinstance(unknown_reason, str) or not unknown_reason.strip():
            raise ExactValueError(field_name, "unknown_reason_required")
        return UnknownValue((unknown_reason,))
    if unknown_reason is not None:
        raise ExactValueError(field_name, "reason_requires_null")
    if not isinstance(raw, str):
        raise ExactValueError(field_name, "decimal_string_required")
    return ExactValue(raw, sign, field_name)


def _unknown(*values: BookValue) -> UnknownValue | None:
    reasons = tuple(
        dict.fromkeys(
            reason
            for value in values
            if isinstance(value, UnknownValue)
            for reason in value.reasons
        )
    )
    return UnknownValue(reasons) if reasons else None


def _result(value: Decimal, field_name: str, sign: Sign) -> ExactValue:
    if not value.is_finite():
        raise ExactValueError(field_name, "nonfinite_result")
    return ExactValue(_canonical(value), sign, field_name)


def calculate(
    operation: Literal["add", "subtract", "multiply"],
    left: BookValue,
    right: BookValue,
    *,
    field_name: str,
    sign: Sign,
) -> BookValue:
    """Exact bounded output; no rounding to force an unsupported result to fit."""
    if operation not in ("add", "subtract", "multiply"):
        raise ExactValueError(field_name, "unsupported_operation")
    missing = _unknown(left, right)
    if missing is not None:
        return missing
    assert isinstance(left, ExactValue) and isinstance(right, ExactValue)
    with localcontext(_context()):
        match operation:
            case "add":
                result = left.value + right.value
            case "subtract":
                result = left.value - right.value
            case "multiply":
                result = left.value * right.value
    return _result(result, field_name, sign)


@dataclass(frozen=True)
class DiagnosticAllocation:
    allocated_basis: BookValue
    remaining_basis: BookValue
    remaining_quantity: ExactValue


def allocate_diagnostic_basis(
    *,
    remaining_quantity: ExactValue,
    remaining_basis: BookValue,
    sold_quantity: ExactValue,
    basis_quantum: BookValue,
) -> DiagnosticAllocation:
    """Pro-rata HALF_EVEN split; full disposal consumes the remainder.

    The explicit basis quantum must be a power of ten and align with known basis.
    Unknown basis/quantum propagates into both basis outputs. Quantities must be
    known and supported; unsupported residuals fail instead of losing precision.
    """
    for name, quantity in (
        ("remaining_quantity", remaining_quantity),
        ("sold_quantity", sold_quantity),
    ):
        if quantity.value <= 0:
            raise ExactValueError(name, "positive_value_required")
    if sold_quantity.value > remaining_quantity.value:
        raise ExactValueError("sold_quantity", "exceeds_remaining_quantity")
    with localcontext(_context()):
        quantity_left = _result(
            remaining_quantity.value - sold_quantity.value,
            "remaining_quantity",
            Sign.NONNEGATIVE,
        )
    # Validate known facts even when another required fact is unknown.
    if isinstance(remaining_basis, ExactValue) and remaining_basis.value.is_signed():
        raise ExactValueError("remaining_basis", "negative_basis")
    quantum: Decimal | None = None
    if isinstance(basis_quantum, ExactValue):
        with localcontext(_context()):
            quantum = basis_quantum.value.normalize()
        if quantum <= 0 or quantum.as_tuple().digits != (1,):
            raise ExactValueError("basis_quantum", "power_of_ten_required")
    if isinstance(remaining_basis, ExactValue) and quantum is not None:
        with localcontext(_context(allow_rounding=True)):
            aligned = remaining_basis.value.quantize(quantum)
        if aligned != remaining_basis.value:
            raise ExactValueError("remaining_basis", "basis_quantum_mismatch")
    missing = _unknown(remaining_basis, basis_quantum)
    if missing is not None:
        return DiagnosticAllocation(missing, missing, quantity_left)
    assert isinstance(remaining_basis, ExactValue) and quantum is not None
    with localcontext(_context(allow_rounding=True)):
        if sold_quantity.value == remaining_quantity.value:
            allocated = remaining_basis.value
        else:
            allocated = (
                remaining_basis.value * sold_quantity.value / remaining_quantity.value
            ).quantize(quantum, rounding=ROUND_HALF_EVEN)
        basis_left = remaining_basis.value - allocated
    return DiagnosticAllocation(
        _result(allocated, "allocated_basis", Sign.NONNEGATIVE),
        _result(basis_left, "remaining_basis", Sign.NONNEGATIVE),
        quantity_left,
    )
