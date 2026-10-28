"""Explicit bounded provider routing; no fund, date, basket or source fallback."""

from collections.abc import Callable
from datetime import date, datetime

from prosper import blackrock, vanguard

CUSIPS = {"ITOT": "464287150", "IVV": "464287200", "VTI": "922908769", "VOO": "922908363"}


def select_fund(ticker: str, effective_date: date | None = None) -> vanguard.Selection:
    if ticker in ("ITOT", "IVV"):
        return blackrock.select_fund(ticker, effective_date)
    return vanguard.select_fund(ticker, effective_date)


def acquire(
    selection: vanguard.Selection,
    *,
    transport: Callable[[vanguard.Selection], vanguard.Response] | None = None,
    collected_at: datetime | None = None,
) -> vanguard.Acquisition:
    if isinstance(selection, blackrock.Selection):
        return blackrock.acquire(
            selection, transport=transport or vanguard.fetch_https, collected_at=collected_at
        )
    return vanguard.acquire(
        selection, transport=transport or vanguard.fetch_https, collected_at=collected_at
    )
