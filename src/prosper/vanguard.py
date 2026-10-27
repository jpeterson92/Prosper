"""Vanguard full-portfolio acquisition evidence, never an activated risk benchmark.

The public holdings response does not identify its fund independently of the URL.
Request binding, structural inspection and financial qualification are distinct.
"""

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from http.client import HTTPException, IncompleteRead
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_BENCHMARK_SOURCE: Literal["vanguard-full-holdings"] = "vanguard-full-holdings"
ADAPTER_VERSION = "vanguard-full-holdings-observation-v1"
BASE_URL = "https://advisors.vanguard.com/investments/products/api/funds"
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 50_000
SECTIONS = (
    "equity",
    "fixedIncome",
    "shortTermReserves",
    "shortTermReservesMoneyMarket",
    "formattedFundOfFundsHoldings",
    "allocationToUnderlyingFunds",
    "derivatives",
)
WEIGHT_SECTIONS = frozenset(
    ("equity", "fixedIncome", "shortTermReserves", "allocationToUnderlyingFunds", "derivatives")
)


@dataclass(frozen=True)
class Fund:
    ticker: str
    port_id: str


# Initial request candidates, not a claim of qualified universe/financial support.
FUNDS = (Fund("VTI", "0970"), Fund("VOO", "0968"))


@dataclass(frozen=True)
class Selection:
    fund: Fund
    effective_date: date | None = None

    def __post_init__(self) -> None:
        if self.fund not in FUNDS:
            raise ValueError("unsupported_vanguard_fund")
        if self.effective_date is not None and type(self.effective_date) is not date:
            raise ValueError("effective_date_must_be_date")

    @property
    def source(self) -> Literal["vanguard-full-holdings"]:
        return DEFAULT_BENCHMARK_SOURCE

    @property
    def url(self) -> str:
        base = f"{BASE_URL}/{self.fund.port_id}/holdings"
        if self.effective_date is None:
            return f"{base}/latest"
        return f"{base}/historical?effectiveDate={self.effective_date.isoformat()}"


def select_fund(ticker: str, effective_date: date | None = None) -> Selection:
    """Select a fund explicitly; the source defaults to Vanguard, not a fund ticker."""
    for fund in FUNDS:
        if ticker.strip().upper() == fund.ticker:
            return Selection(fund, effective_date)
    raise ValueError("unsupported_vanguard_fund")


class JsonNumber(str):
    """The exact JSON number token, distinguished from a JSON string."""


@dataclass(frozen=True)
class JsonObject:
    fields: tuple[tuple[str, "JsonValue"], ...]

    def get(self, key: str) -> "JsonValue":
        return next((value for name, value in self.fields if name == key), None)


type JsonValue = None | bool | str | JsonObject | tuple[JsonValue, ...]


@dataclass(frozen=True)
class Response:
    status: int
    url: str
    content_type: str
    body: bytes = field(repr=False)
    body_complete: bool = True


@dataclass(frozen=True)
class Section:
    name: str
    rows: tuple[JsonValue, ...] = field(repr=False)
    # Partial sum of explicitly numeric source percentages, never a normalized weight.
    known_weight_percent_sum: float | None
    unknown_weight_rows: tuple[int, ...]


@dataclass(frozen=True)
class Snapshot:
    selection: Selection
    effective_date: date
    collected_at: datetime
    raw_sha256: str
    document: JsonObject = field(repr=False)
    sections: tuple[Section, ...] = field(repr=False)
    issues: tuple[str, ...]

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False

    @property
    def qualification_gaps(self) -> tuple[str, ...]:
        return (
            "fund_identity_request_bound_only",
            "complete_source_reconciliation_unqualified",
            "security_identity_and_classification_unqualified",
            "reserves_derivatives_and_residual_policy_unqualified",
            "freshness_publication_and_capacity_unqualified",
            "canonical_benchmark_activation_not_implemented",
        )


@dataclass(frozen=True)
class Acquisition:
    selection: Selection
    collected_at: datetime
    response: Response | None = field(repr=False)
    snapshot: Snapshot | None
    issues: tuple[str, ...]

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False


class _Invalid(ValueError):
    pass


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _Invalid("duplicate_json_key")
        result[key] = value
    return result


def _constant(_: str) -> object:
    raise _Invalid("nonfinite_json_number")


def _freeze(value: object, depth: int = 0) -> JsonValue:
    if depth > 32:
        raise _Invalid("json_depth_limit")
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, list):
        return tuple(_freeze(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return JsonObject(tuple((key, _freeze(item, depth + 1)) for key, item in value.items()))
    raise _Invalid("unsupported_json_value")


def _date(value: JsonValue) -> date:
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise _Invalid("invalid_effective_date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise _Invalid("invalid_effective_date") from exc


def _weight(value: JsonValue) -> float | None:
    if not isinstance(value, str) or not value or len(value) > 128:
        return None
    if not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", value):
        return None
    try:
        decimal = Decimal(value)
        exponent = decimal.as_tuple().exponent
        if not isinstance(exponent, int) or abs(exponent) > 40:
            return None
        result = float(decimal)
        return result if math.isfinite(result) and (decimal == 0 or result != 0) else None
    except (InvalidOperation, ValueError):
        return None


def _inspect(selection: Selection, response: Response, collected_at: datetime) -> Snapshot:
    if response.url != selection.url:
        raise _Invalid("unexpected_response_url")
    if response.status != 200:
        raise _Invalid("date_unavailable" if response.status in (204, 404) else "http_error")
    if response.content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise _Invalid("unexpected_content_type")
    if not response.body or len(response.body) > MAX_BYTES:
        raise _Invalid("response_size_limit")
    if not response.body_complete:
        raise _Invalid("incomplete_response")
    try:
        document = _freeze(
            json.loads(
                response.body.decode("utf-8-sig"),
                parse_int=JsonNumber,
                parse_float=JsonNumber,
                parse_constant=_constant,
                object_pairs_hook=_pairs,
            )
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise _Invalid("invalid_json") from exc
    if not isinstance(document, JsonObject):
        raise _Invalid("invalid_envelope")
    if any(name in ("basketId", "bsktHistId", "holding", "trdDate") for name, _ in document.fields):
        raise _Invalid("basket_feed_forbidden")
    effective = (
        _date(document.get("latestEffectiveDate"))
        if selection.effective_date is None
        else selection.effective_date
    )
    if effective > collected_at.date():
        raise _Invalid("future_effective_date")
    if selection.effective_date is not None and any(
        name == "latestEffectiveDate" and _date(value) != effective
        for name, value in document.fields
    ):
        raise _Invalid("returned_date_mismatch")
    if any(
        name not in (effective.isoformat(), "latestEffectiveDate") for name, _ in document.fields
    ):
        raise _Invalid("unexpected_envelope_or_date")
    holdings = document.get(effective.isoformat())
    if not isinstance(holdings, JsonObject):
        raise _Invalid("requested_date_missing")
    if not isinstance(holdings.get("equity"), tuple) or not holdings.get("equity"):
        raise _Invalid("equity_section_missing_or_empty")
    sections: list[Section] = []
    issues: list[str] = []
    count = 0
    for name, rows in holdings.fields:
        if name not in SECTIONS:
            issues.append(f"unknown_section:{name}")
        if not isinstance(rows, tuple):
            issues.append(f"invalid_section:{name}")
            continue  # The entire original value remains in document and response.body.
        count += len(rows)
        if count > MAX_ROWS:
            raise _Invalid("row_limit")
        total = 0.0 if name in WEIGHT_SECTIONS else None
        unknown: list[int] = []
        for index, row in enumerate(rows):
            if not isinstance(row, JsonObject):
                issues.append(f"invalid_row:{name}:{index}")
                if total is not None:
                    unknown.append(index)
                continue
            if total is not None:
                weight = _weight(row.get("percentOfFunds"))
                if weight is None:
                    unknown.append(index)
                else:
                    total += weight
                    if weight < 0:
                        issues.append(f"negative_source_weight:{name}:{index}")
            if name == "equity":
                for key in ("ticker", "cusip"):
                    if type(row.get(key)) is not str or not str(row.get(key)).strip():
                        issues.append(f"missing_{key}:{name}:{index}")
        if unknown:
            issues.append(f"unknown_weights:{name}")
        sections.append(Section(name, rows, total, tuple(unknown)))
    return Snapshot(
        selection,
        effective,
        collected_at,
        hashlib.sha256(response.body).hexdigest(),
        document,
        tuple(sections),
        tuple(issues),
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def _body(read: Callable[[int], bytes]) -> tuple[bytes, bool]:
    try:
        raw = read(MAX_BYTES + 1)
        return raw, len(raw) <= MAX_BYTES
    except IncompleteRead as exc:
        return exc.partial, False


def fetch_https(selection: Selection) -> Response:
    """One bounded public GET; no credentials, redirects, retries or fallback dates."""
    request = Request(selection.url, headers={"Accept": "application/json"})
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as result:
            raw, complete = _body(result.read)
            return Response(
                result.status,
                result.url,
                result.headers.get("Content-Type", ""),
                raw,
                complete,
            )
    except HTTPError as exc:
        with exc:
            raw, complete = _body(exc.read)
            return Response(
                exc.code,
                selection.url,
                exc.headers.get("Content-Type", ""),
                raw,
                complete,
            )


def acquire(
    selection: Selection,
    *,
    transport: Callable[[Selection], Response] = fetch_https,
    collected_at: datetime | None = None,
) -> Acquisition:
    """Retain source evidence and observations without publishing a benchmark.

    Inject transport/time for deterministic verification. Network failure
    and unavailable dates never initiate another source/date request.
    """
    collected = datetime.now(UTC) if collected_at is None else collected_at
    if collected.tzinfo is None or collected.utcoffset() is None:
        raise ValueError("collection_time_requires_timezone")
    collected = collected.astimezone(UTC)
    try:
        response = transport(selection)
    except (OSError, URLError, HTTPException):
        return Acquisition(selection, collected, None, None, ("transport_error",))
    try:
        snapshot = _inspect(selection, response, collected)
        return Acquisition(selection, collected, response, snapshot, snapshot.issues)
    except _Invalid as exc:
        return Acquisition(selection, collected, response, None, (str(exc),))
