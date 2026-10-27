"""Current ordered history-to-IDR inputs, without registry replay or fallback."""

import math
from decimal import Decimal, InvalidOperation

import polars as pl

from prosper.history import Alignment
from prosper.innovations import (
    InnovationContext,
    InnovationProfile,
    InnovationResult,
    OHLCRow,
    fingerprint,
    regularized_innovation,
    transform_ohlc,
)


def conventions_available(alignment: Alignment) -> bool:
    """Inspect every input/derived scalar without retaining innovation matrices.

    This is input availability, not a fitted/qualified risk result. Final fitting
    still calls transform_ohlc with the exact retained table and explicit profile.
    """
    request = alignment.request
    if not alignment.complete or request.profile is None:
        return False
    contexts = request.series
    if (
        any(
            c.currency != "USD"
            or c.interval != "1d"
            or c.timezone != "UTC"
            or c.adjustment not in ("no-actions", "total-return-adjusted")
            or c.return_convention != "simple-total-return-decimal"
            or c.action_convention != "compatible-total-return-and-raw-ohlc"
            for c in contexts
        )
        or len({c.vintage for c in contexts}) != 1
    ):
        return False
    frame = alignment.rows.frame
    if frame.filter(
        ~pl.col("action").is_in(["none", "split", "dividend", "split-and-dividend"])
    ).height:
        return False
    if (
        any(c.adjustment == "no-actions" for c in contexts)
        and frame.filter(
            pl.col("security_id").is_in(
                [c.security_id for c in contexts if c.adjustment == "no-actions"]
            )
            & ((pl.col("action") != "none") | (pl.col("close") != pl.col("adjusted_close")))
        ).height
    ):
        return False
    try:
        profile = request.profile
        ef, ea, ek = (Decimal(v) for v in (profile.f, profile.a3, profile.kappa))
        f, a3, kappa = map(float, (ef, ea, ek))
        if not (
            0 < ef < 1 and 0 <= ea <= 1 and ek > 0 and 0 < f < 1 and 0 <= a3 <= 1 and kappa > 0
        ):
            return False
        if not all(math.isfinite(v) for v in (f, a3, kappa)):
            return False
        for r, o, h, low, c in frame.select(
            "total_return", "open", "high", "low", "close"
        ).iter_rows():
            previous = c / (1 + r)

            def log_ratio(a: float, b: float) -> float:
                ratio = a / b
                return math.log(ratio) if 0 < ratio < math.inf else math.log(a) - math.log(b)

            overnight = log_ratio(o, c) + math.log1p(r)
            range_log = log_ratio(h, low)
            if (a3 > 0 and overnight != 0 and overnight**2 == 0) or (
                a3 < 1 and range_log != 0 and range_log**2 == 0
            ):
                return False
            proxy = a3 / f * overnight**2 + (1 - a3) / (1 - f) * range_log**2 / (4 * math.log(2))
            x = regularized_innovation(r, proxy, kappa)
            if (
                previous <= 0
                or not all(math.isfinite(v) for v in (previous, proxy, x))
                or (r != 0 and proxy > 0 and x == 0)
            ):
                return False
    except (ValueError, OverflowError, InvalidOperation, ZeroDivisionError):
        return False
    return True


def assemble(alignment: Alignment) -> InnovationResult | None:
    request = alignment.request
    if not conventions_available(alignment):
        return None
    assert request.profile is not None
    contexts = request.series
    if any(
        c.currency != "USD"
        or c.interval != "1d"
        or c.timezone != "UTC"
        or c.adjustment not in ("no-actions", "total-return-adjusted")
        or c.return_convention != "simple-total-return-decimal"
        or c.action_convention != "compatible-total-return-and-raw-ohlc"
        for c in contexts
    ):
        return None
    if len({c.vintage for c in contexts}) != 1:
        return None
    rows = []
    for cell in alignment.cells:
        row = cell.observation
        assert row is not None and cell.source_sha256 is not None and cell.total_return is not None
        assert row.action.value is not None
        rows.append(
            OHLCRow(
                session=cell.session,
                security_id=cell.security_id,
                total_return=repr(cell.total_return),
                open=str(row.open.value),
                high=str(row.high.value),
                low=str(row.low.value),
                close=str(row.close.value),
                action=row.action.value,
                action_evidence_sha256=cell.source_sha256,
                return_vintage=contexts[0].vintage,
                ohlc_vintage=contexts[0].vintage,
                action_vintage=contexts[0].vintage,
                compatibility=contexts[0].action_convention,
            )
        )
    context = InnovationContext(
        security_ids=tuple(c.security_id for c in contexts),
        sessions=request.sessions,
        cutoff=request.cutoff,
        calendar=contexts[0].calendar,
        timezone="UTC",
        vintage=contexts[0].vintage,
        source_sha256=fingerprint(alignment.model_dump(mode="json")),
        construction="declared-total-return-compatible-raw-ohlc-v1",
    )
    profile = request.profile
    return transform_ohlc(
        context,
        tuple(rows),
        profile=InnovationProfile(profile.identity, profile.f, profile.a3, profile.kappa),
    )
