"""Small numerical boundaries for estimates, not a bookkeeping framework."""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext

WEIGHT_TOLERANCE = 1e-10
MAX_NUMBER_TEXT = 128


def decimal_value(text: str, *, signed: bool = False) -> Decimal:
    """Preserve supplied value; bound parsing work without a fractional-place rule."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_NUMBER_TEXT:
        raise ValueError("bounded decimal text required")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("invalid decimal") from None
    if not value.is_finite() or (not signed and value < 0):
        raise ValueError("finite supported sign required")
    if abs(int(value.as_tuple().exponent)) > 512 or value.adjusted() > 308:
        raise ValueError("decimal magnitude/scale exceeds the bounded calculation range")
    return value


def number(text: str, *, signed: bool = False) -> float:
    value = decimal_value(text, signed=signed)
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("value is outside finite non-underflowing Float64 range")
    return result


def unit_sum(values: tuple[float, ...]) -> bool:
    if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values):
        return False
    try:
        return math.isclose(math.fsum(values), 1.0, rel_tol=0, abs_tol=WEIGHT_TOLERANCE)
    except OverflowError:
        return False


@dataclass(frozen=True)
class SaleEstimate:
    remaining_quantity: str
    allocated_basis: float | None
    price_loss: float | None
    loss_candidate: bool | None


def sale_estimate(available: str, total_basis: str | None, shares: int, mark: str) -> SaleEstimate:
    """Check discrete availability/sign from source decimals, then report estimates.

    No wash-sale clearance or executed/remaining basis ledger is implied.
    """
    quantity, price = decimal_value(available), decimal_value(mark)
    if (
        type(shares) is not int
        or shares <= 0
        or shares.bit_length() > 1024
        or Decimal(shares) > quantity
        or price <= 0
    ):
        raise ValueError("positive whole shares within supplied holding and positive mark required")
    basis = decimal_value(total_basis) if total_basis is not None else None
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        context.prec = max(
            28,
            sum(
                len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent))
                for v in (quantity, price, basis or Decimal(0))
            )
            + 8,
        )
        remaining = quantity - shares
        if basis is None:
            return SaleEstimate(str(remaining), None, None, None)
        allocated = basis if Decimal(shares) == quantity else basis * shares / quantity
        # Cross-multiplication determines sign without rounded prorata division.
        loss_candidate = basis > quantity * price
        loss = allocated - Decimal(shares) * price
        allocated_float, loss_float = float(allocated), float(loss)
    if (
        not all(math.isfinite(v) for v in (allocated_float, loss_float))
        or (allocated != 0 and allocated_float == 0)
        or (loss != 0 and loss_float == 0)
    ):
        raise ValueError("unrepresentable sale estimate")
    return SaleEstimate(str(remaining), allocated_float, loss_float, loss_candidate)


def cash_estimate(initial: str, proceeds: str, purchases: str, fees: str) -> tuple[float, bool]:
    values = tuple(decimal_value(v) for v in (initial, proceeds, purchases, fees))
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        context.prec = max(
            28, sum(len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent)) for v in values) + 8
        )
        balance = values[0] + values[1] - values[2] - values[3]
    result = float(balance)
    if not math.isfinite(result) or (balance != 0 and result == 0):
        raise ValueError("unrepresentable cash estimate")
    return result, balance >= 0
