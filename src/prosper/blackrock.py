"""Bounded iShares full-holdings CSV observation, without benchmark activation.

Reuse the common observation/row records alongside the Vanguard adapter. CSV's
preamble and quoted logical records require stdlib csv; Polars checks table
cardinality and summarizes source fields. Original response bytes and cells stay
retained; canonical numeric aliases only remove validated grouping commas.
"""

import csv
import hashlib
import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode

import polars as pl

from prosper import vanguard as v

BASE_URL = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data/"
    "product-data/api/v1/get-fund-document"
)
FUNDS = (v.Fund("ITOT", "239724"), v.Fund("IVV", "239726"))
NAMES = {
    "ITOT": "iShares Core S&P Total U.S. Stock Market ETF",
    "IVV": "iShares Core S&P 500 ETF",
}
COLUMNS = (
    "Ticker",
    "Name",
    "Type",
    "Sector",
    "Asset Class",
    "Market Value",
    "Notional Value",
    "Quantity",
    "Price",
    "Location",
    "Exchange",
    "Currency",
    "FX Rate",
    "Market Currency",
    "Accrual Date",
    "Market Weight",
    "Notional Weight",
)
ALTERNATE_COLUMNS = (
    "Ticker",
    "Name",
    "Sector",
    "Asset Class",
    "Market Value",
    "Weight (%)",
    "Notional Value",
    "Quantity",
    "Price",
    "Location",
    "Exchange",
    "Currency",
    "FX Rate",
    "Market Currency",
    "Accrual Date",
)


@dataclass(frozen=True)
class Selection(v.Selection):
    def __post_init__(self) -> None:
        if self.fund not in FUNDS:
            raise ValueError("unsupported_blackrock_fund")
        if self.effective_date is not None and type(self.effective_date) is not date:
            raise ValueError("effective_date_must_be_date")

    @property
    def source(self) -> str:
        return "blackrock-full-holdings"

    @property
    def url(self) -> str:
        params = {
            "appType": "PRODUCT_PAGE",
            "appSubType": "ISHARES",
            "targetSite": "us-ishares",
            "locale": "en_US",
            "portfolioId": self.fund.port_id,
            "userType": "individual",
            "component": "holdings",
        }
        if self.effective_date is not None:
            params["asOfDate"] = self.effective_date.strftime("%Y%m%d")
        return BASE_URL + "?" + urlencode(params)


def select_fund(ticker: str, effective_date: date | None = None) -> Selection:
    for fund in FUNDS:
        if ticker == fund.ticker:
            return Selection(fund, effective_date)
    raise ValueError("unsupported_blackrock_fund")


def _number(raw: str) -> str | None:
    if raw in ("", "-"):
        return None
    if len(raw) > 128 or not re.fullmatch(
        r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", raw
    ):
        raise ValueError("invalid_numeric_cell")
    return raw.replace(",", "")


def _date(raw: str) -> date:
    months = dict(
        zip(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
            range(1, 13),
            strict=True,
        )
    )
    match = re.fullmatch(r"([A-Z][a-z]{2}) ([0-9]{1,2}), ([0-9]{4})", raw)
    if match is None or match[1] not in months:
        raise ValueError("invalid_effective_date")
    return date(int(match[3]), months[match[1]], int(match[2]))


def inspect(selection: Selection, response: v.Response, collected_at: datetime) -> v.Snapshot:
    if response.url != selection.url:
        raise ValueError("unexpected_response_url")
    if response.status != 200:
        raise ValueError("date_unavailable" if response.status in (204, 404) else "http_error")
    if response.content_type.split(";", 1)[0].strip().lower() != "text/csv":
        raise ValueError("unexpected_content_type")
    if not response.body or len(response.body) > v.MAX_BYTES:
        raise ValueError("response_size_limit")
    if not response.body_complete:
        raise ValueError("incomplete_response")
    records: list[tuple[int, int, list[str]]] = []
    try:
        reader = csv.reader(io.StringIO(response.body.decode("utf-8-sig"), newline=""), strict=True)
        end = 0
        for cells in reader:
            start, end = end + 1, reader.line_num
            if len(records) > v.MAX_ROWS + 32:
                raise ValueError("row_limit")
            if any(len(cell) > 4096 for cell in cells):
                raise ValueError("cell_size_limit")
            records.append((start, end, cells))
    except (UnicodeError, csv.Error) as error:
        raise ValueError("invalid_csv") from error
    if not records or records[0][2] != [NAMES[selection.fund.ticker]]:
        raise ValueError("fund_name_mismatch")
    headers = [i for i, (_, _, cells) in enumerate(records) if cells and cells[0] == "Ticker"]
    if len(headers) != 1 or headers[0] > 31:
        raise ValueError("holdings_header_missing_or_duplicate")
    header = headers[0]
    columns = tuple(records[header][2])
    if columns not in (COLUMNS, ALTERNATE_COLUMNS):
        raise ValueError("unsupported_holdings_columns")
    weight_column = "Market Weight" if columns == COLUMNS else "Weight (%)"
    stamps = [
        cells[1]
        for _, _, cells in records[:header]
        if len(cells) == 2 and cells[0] == "Fund Holdings as of"
    ]
    if len(stamps) != 1:
        raise ValueError("holdings_date_missing_or_duplicate")
    if stamps[0] == "-":
        raise ValueError("date_unavailable")
    effective = _date(stamps[0])
    if selection.effective_date is not None and effective != selection.effective_date:
        raise ValueError("returned_date_mismatch")
    if effective > collected_at.date():
        raise ValueError("future_effective_date")
    rows: list[v.JsonValue] = []
    raw_rows: list[dict[str, str]] = []
    issues = []
    for start, end, cells in records[header + 1 :]:
        if not cells or all(not value.strip() for value in cells):
            continue  # Blank separators have no holding; their bytes remain original.
        if len(cells) != len(columns):
            raise ValueError("holdings_record_cardinality_invalid")
        source = dict(zip(columns, cells, strict=True))
        raw_rows.append(source)
        index = len(rows)
        aliases: list[tuple[str, v.JsonValue]] = [
            ("source_ref", f"csv:record:{index}:lines:{start}-{end}"),
            ("holdingName", source["Name"]),
            ("ticker", source["Ticker"]),
            ("currency", source["Currency"]),
        ]
        for alias, column in (
            ("marketValue", "Market Value"),
            ("percentOfFunds", weight_column),
            ("notionalValue", "Notional Value"),
            ("quantity", "Quantity"),
            ("price", "Price"),
        ):
            try:
                value = _number(source[column])
            except ValueError:
                issues.append(f"invalid_numeric_cell:holdings:{index}:{column}")
                value = None
            aliases.append((alias, value))
        rows.append(v.JsonObject((*tuple(source.items()), *aliases)))
    if not rows:
        raise ValueError("holdings_missing_or_empty")
    if len(rows) > v.MAX_ROWS:
        raise ValueError("row_limit")
    frame = pl.DataFrame(raw_rows, schema={name: pl.String for name in columns})
    if frame.height != len(rows):
        raise ValueError("holdings_record_cardinality_invalid")
    for column in ("Ticker", "Name", "Type", "Asset Class"):
        if column not in columns:
            issues.append(f"missing_column:{column}")
            continue
        for index in frame.with_row_index().filter(pl.col(column).is_in(["", "-"]))["index"]:
            issues.append(f"missing_{column}:holdings:{index}")
    weights = [
        v._weight(row.get("percentOfFunds")) if isinstance(row, v.JsonObject) else None
        for row in rows
    ]
    unknown = tuple(i for i, weight in enumerate(weights) if weight is None)
    if unknown:
        issues.append("unknown_weights:holdings")
    total = math.fsum(weight for weight in weights if weight is not None)
    if not math.isfinite(total):
        issues.append("unrepresentable_weight_sum:holdings")
        known_total = None
    else:
        known_total = total
    document = v.JsonObject(
        (
            (
                "preamble",
                tuple(
                    v.JsonObject((("line", str(start)), ("cells", tuple(cells))))
                    for start, _, cells in records[:header]
                ),
            ),
            (effective.isoformat(), v.JsonObject((("holdings", tuple(rows)),))),
        )
    )
    return v.Snapshot(
        selection,
        effective,
        collected_at,
        hashlib.sha256(response.body).hexdigest(),
        document,
        (v.Section("holdings", tuple(rows), known_total, unknown),),
        tuple(issues),
    )


def acquire(
    selection: Selection,
    *,
    transport: Callable[[v.Selection], v.Response] = v.fetch_https,
    collected_at: datetime | None = None,
) -> v.Acquisition:
    collected = datetime.now(UTC) if collected_at is None else collected_at
    if collected.tzinfo is None or collected.utcoffset() is None:
        raise ValueError("collection_time_requires_timezone")
    collected = collected.astimezone(UTC)
    try:
        response = transport(selection)
    except (OSError, URLError, HTTPException):
        return v.Acquisition(selection, collected, None, None, ("transport_error",))
    try:
        snapshot = inspect(selection, response, collected)
        return v.Acquisition(selection, collected, response, snapshot, snapshot.issues)
    except ValueError as error:
        return v.Acquisition(selection, collected, response, None, (str(error),))
