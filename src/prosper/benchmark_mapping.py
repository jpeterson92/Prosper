"""Dated issuer-record preparation under the owner's best-effort policy.

No provider-symbol conversion, history/tax clearance or financial selection.
Polars owns cardinality/duplicate checks and Float64 coverage aggregation;
source decimals supply only the strict final coverage-warning comparisons.
"""

import hashlib
import json
import math
import re
from decimal import Decimal, localcontext
from typing import Literal

import polars as pl

from prosper import benchmark_reconciliation as r
from prosper import blackrock
from prosper import vanguard as v
from prosper.advisory_records import Digest, Record


class PreparedRow(Record):
    section: str
    index: int
    row_sha256: Digest
    source_key: Digest
    source_ref: str | None
    ticker: str | None
    name: str | None
    source_type: str | None
    asset_class: str | None
    location: str | None
    currency: str | None
    market_currency: str | None
    exchange: str | None
    raw_market_value: str | None
    value_usd: float | None
    security_id: str | None
    action: Literal["include", "exclude"]
    reason: str
    excluded_bps: float | None
    highlight: bool | None


class PreparedMapping(Record):
    method: Literal["dated-issuer-ivv-v1"] = "dated-issuer-ivv-v1"
    rows: tuple[PreparedRow, ...]
    included_count: int
    excluded_count: int
    source_value_usd: float | None
    retained_known_value_usd: float
    excluded_known_value_usd: float
    unknown_value_rows: tuple[int, ...]
    aggregate_excluded_bps: float | None
    aggregate_highlight: bool | None
    highlighted_rows: tuple[int, ...]
    coverage_unknown_reasons: tuple[str, ...]
    history_status: Literal["not_assessed"] = "not_assessed"
    tax_status: Literal["not_assessed"] = "not_assessed"


def prepare(snapshot: v.Snapshot) -> PreparedMapping | None:
    # This policy is deliberately limited to the actually inspected IVV layout.
    # Other providers/layouts retain their explicit review path, not an inferred
    # section/type/currency policy copied from a different transport.
    if not isinstance(snapshot.selection, blackrock.Selection) or (
        snapshot.selection.fund.ticker != "IVV"
    ):
        return None
    if len(snapshot.sections) != 1 or snapshot.sections[0].name != "holdings":
        return None
    originals = snapshot.sections[0].rows
    records: list[dict[str, str | int | float | None]] = []
    for index, original in enumerate(originals):

        def cell(name: str, row: v.JsonValue = original) -> str | None:
            value = row.get(name) if isinstance(row, v.JsonObject) else None
            return value if type(value) is str else None

        raw = cell("marketValue")
        value = None
        if raw is not None:
            try:
                parsed = float(raw)
                if math.isfinite(parsed):
                    value = parsed
            except ValueError:
                pass
        records.append(
            {
                "index": index,
                "ticker": cell("Ticker"),
                "name": cell("Name"),
                "source_type": cell("Type"),
                "asset_class": cell("Asset Class"),
                "location": cell("Location"),
                "currency": cell("Currency"),
                "market_currency": cell("Market Currency"),
                "exchange": cell("Exchange"),
                "raw_market_value": cell("Market Value"),
                "numeric_value": raw,
                "value_usd": value if cell("Currency") == "USD" else None,
                "source_ref": cell("source_ref"),
            }
        )
    if not records:
        return None
    table = pl.DataFrame(records, schema_overrides={"value_usd": pl.Float64})
    counts = table.group_by("ticker", maintain_order=True).len()
    table = table.join(counts, on="ticker", how="left", validate="m:1", maintain_order="left")
    assert table.height == len(originals)
    assert table["index"].to_list() == list(range(len(originals)))
    rows: list[PreparedRow] = []
    reasons: set[str] = set()
    if table.filter(pl.col("len") > 1).height:
        reasons.add("duplicate_source_ticker")
    for item in table.iter_rows(named=True):
        ticker, name = item["ticker"], item["name"]
        if item["source_type"] not in ("EQUITY",) or item["asset_class"] != "Equity":
            reason = "unsupported_source_instrument"
        elif not ticker or not re.fullmatch(r"[A-Z0-9][A-Z0-9./-]{0,31}(?: [A-Z])?", ticker):
            reason = "source_ticker_missing_or_unsupported"
        elif item["len"] != 1:
            reason = "ambiguous_source_ticker"
        elif not name or not name.strip():
            reason = "source_name_missing"
        elif item["currency"] != "USD" or item["market_currency"] != "USD":
            reason = "unsupported_or_unknown_currency"
        elif item["location"] != "United States":
            reason = "unsupported_or_unknown_source_location"
        elif item["exchange"] in (None, "", "-", "NO MARKET (E.G. UNLISTED)"):
            reason = "source_exchange_unavailable"
        else:
            reason = "dated_issuer_equity_mapping"
        include = reason == "dated_issuer_equity_mapping"
        key = [
            snapshot.selection.fund.ticker,
            snapshot.selection.fund.port_id,
            snapshot.effective_date.isoformat(),
            ticker,
            name,
            item["source_type"],
            item["currency"],
        ]
        source_key = hashlib.sha256(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        # Some exact issuer symbols (e.g. a space before the share class) do
        # not fit the current canonical-ID alphabet. An opaque local key is
        # not a guessed provider symbol or an asserted cross-date alias.
        security_id = (
            ticker
            if ticker and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", ticker)
            else "issuer-" + source_key
        )
        rows.append(
            PreparedRow(
                section="holdings",
                index=item["index"],
                row_sha256=r.row_identity(originals[item["index"]]),
                source_key=source_key,
                source_ref=item["source_ref"],
                ticker=ticker,
                name=name,
                source_type=item["source_type"],
                asset_class=item["asset_class"],
                location=item["location"],
                currency=item["currency"],
                market_currency=item["market_currency"],
                exchange=item["exchange"],
                raw_market_value=item["raw_market_value"],
                value_usd=item["value_usd"],
                security_id=security_id if include else None,
                action="include" if include else "exclude",
                reason=reason,
                excluded_bps=None,
                highlight=None,
            )
        )
    unknown = tuple(row.index for row in rows if row.value_usd is None)
    if unknown:
        reasons.add("unknown_source_usd_value")
    if any(row.value_usd is not None and row.value_usd < 0 for row in rows):
        reasons.add("negative_source_value")
    coverage = table.with_columns(pl.Series("included", [x.action == "include" for x in rows]))
    retained = float(coverage.filter(pl.col("included"))["value_usd"].sum())
    excluded = float(coverage.filter(~pl.col("included"))["value_usd"].sum())
    source = float(coverage["value_usd"].sum())
    if not math.isfinite(source) or source <= 0:
        reasons.add("nonpositive_or_unrepresentable_source_value")
    if not math.isfinite(retained) or not math.isfinite(excluded):
        raise ValueError("unrepresentable_mapping_coverage")
    aggregate_bps: float | None = None
    aggregate_highlight: bool | None = None
    if not reasons:
        # A narrow supplied-decimal boundary makes >10/>100 strict even at
        # exact thresholds. Float64 remains the reported derived-analytics path.
        with localcontext() as context:
            context.prec = 160
            values = [Decimal(str(x["numeric_value"])) for x in records]
            denominator = sum(values, Decimal(0))
            total_out = sum((values[x.index] for x in rows if x.action == "exclude"), Decimal(0))
            aggregate_highlight = total_out * 10000 > denominator * 100
            aggregate_bps = excluded / source * 10000
            rows = [
                row.model_copy(
                    update={
                        "excluded_bps": row.value_usd / source * 10000,
                        "highlight": values[row.index] * 10000 > denominator * 10,
                    }
                )
                if row.action == "exclude" and row.value_usd is not None
                else row
                for row in rows
            ]
    return PreparedMapping(
        rows=tuple(rows),
        included_count=sum(x.action == "include" for x in rows),
        excluded_count=sum(x.action == "exclude" for x in rows),
        source_value_usd=None if reasons else source,
        retained_known_value_usd=retained,
        excluded_known_value_usd=excluded,
        unknown_value_rows=unknown,
        aggregate_excluded_bps=aggregate_bps,
        aggregate_highlight=aggregate_highlight,
        highlighted_rows=tuple(x.index for x in rows if x.highlight),
        coverage_unknown_reasons=tuple(sorted(reasons)),
    )
