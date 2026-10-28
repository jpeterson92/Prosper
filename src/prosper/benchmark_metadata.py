"""Bounded official IVV metadata and current review-draft preparation."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from http.client import IncompleteRead
from typing import TYPE_CHECKING, Literal
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from pydantic import Field

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import blackrock
from prosper import equity_benchmark as e
from prosper import vanguard as v
from prosper.advisory_records import Digest, Record
from prosper.record_types import DateText, Identifier, Timestamp

if TYPE_CHECKING:
    from prosper.benchmark import BenchmarkObservation, BenchmarkReview

IVV_URL = "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf"
IVV_CANONICAL_URL = "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf"
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_METADATA_BASE64 = ((MAX_METADATA_BYTES + 2) // 3) * 4


class MetadataImport(Record):
    collected_at: Timestamp
    response_url: str
    content_type: str
    http_status: int
    body_complete: bool
    source_base64: str = Field(max_length=MAX_METADATA_BASE64, repr=False)


class PrepareRequest(Record):
    observation_id: Identifier
    metadata_response: MetadataImport | None = None


class FundMetadata(Record):
    ticker: Literal["IVV"] = "IVV"
    port_id: Literal["239726"] = "239726"
    cusip: Literal["464287200"] = "464287200"
    response_url: str = IVV_URL
    canonical_url: str
    content_type: str
    collected_at: Timestamp
    holdings_date: DateText
    source_sha256: Digest
    byte_count: int = Field(gt=0, le=MAX_METADATA_BYTES)


def decode_metadata(encoded: str) -> bytes:
    raw = base64.b64decode(encoded, validate=True)
    if not 0 < len(raw) <= MAX_METADATA_BYTES:
        raise ValueError("benchmark_metadata_size_limit")
    return raw


def fetch_metadata() -> v.Response:
    """One fixed public HTTPS URL; no credentials, redirects or fallback."""
    request = Request(IVV_URL, headers={"Accept": "text/html"})
    opener = build_opener(v._NoRedirect())
    try:
        response = opener.open(request, timeout=30)
    except HTTPError as error:
        response = error
    with response:
        try:
            raw = response.read(MAX_METADATA_BYTES + 1)
            complete = len(raw) <= MAX_METADATA_BYTES
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None:
                length = declared_length.strip()
                complete = (
                    complete
                    and length.isascii()
                    and length.isdecimal()
                    and (length.lstrip("0") or "0") == str(len(raw))
                )
        except IncompleteRead as error:
            raw, complete = error.partial, False
        return v.Response(
            response.code,
            response.url,
            response.headers.get("Content-Type", ""),
            raw,
            complete,
        )


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise ValueError("ambiguous_metadata_json")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("nonfinite_metadata_json")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.current: list[str] = []
        self.scripts: list[str] = []
        self.dates: list[str] = []
        self.canonicals: list[str] = []
        self.primary_head = False
        self.head_complete = False
        self.cusips: list[str] = []
        self.cusip_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "head" and not self.head_complete:
            self.primary_head = True
        if tag == "link" and self.primary_head and attributes.get("rel") == "canonical":
            self.canonicals.append(attributes.get("href") or "")
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.active = True
            self.current = []
        if attributes.get("webqc-datapoint") == "holdings-as-of-dates":
            self.dates.append(attributes.get("data-as-of-dates") or "")
        if tag == "span" and attributes.get("webqc-datapoint") == "keyFundFacts-cusip":
            if self.cusip_parts is not None:
                raise ValueError("metadata_cusip_ambiguous")
            self.cusip_parts = []

    def handle_data(self, data: str) -> None:
        if self.active:
            self.current.append(data)
        if self.cusip_parts is not None:
            self.cusip_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "head" and self.primary_head:
            self.primary_head = False
            self.head_complete = True
        if tag == "span" and self.cusip_parts is not None:
            self.cusips.append("".join(self.cusip_parts).strip())
            self.cusip_parts = None
        if tag == "script" and self.active:
            self.scripts.append("".join(self.current))
            self.active = False


def inspect_metadata(
    observation: BenchmarkObservation, response: v.Response, collected: datetime
) -> FundMetadata:
    if observation.status != "observed" or observation.request.ticker != "IVV":
        raise ValueError("unsupported_metadata_preparation")
    if (
        response.status != 200
        or response.url != IVV_URL
        or response.content_type.partition(";")[0].strip().lower() != "text/html"
        or not response.body_complete
        or not 0 < len(response.body) <= MAX_METADATA_BYTES
    ):
        raise ValueError("benchmark_metadata_response_invalid")
    if collected.tzinfo is None or collected > datetime.now(UTC):
        raise ValueError("benchmark_metadata_collection_invalid")
    page = _Page()
    try:
        page.feed(response.body.decode("utf-8"))
        if (
            page.active
            or len(page.scripts) != 1
            or len(page.dates) != 1
            or len(page.canonicals) != 1
        ):
            raise ValueError("metadata_structure_unavailable")
        canonical = page.canonicals[0]
        if canonical not in (IVV_URL, IVV_CANONICAL_URL):
            raise ValueError("benchmark_metadata_fund_mismatch")
        document = json.loads(page.scripts[0], object_pairs_hook=_pairs, parse_constant=_constant)
        graph = document["@graph"]
        if not isinstance(graph, list):
            raise ValueError("metadata_graph_invalid")

        def node(suffix: str) -> dict[str, object]:
            found = [x for x in graph if isinstance(x, dict) and x.get("@id") == canonical + suffix]
            if len(found) != 1:
                raise ValueError("metadata_identity_ambiguous")
            return found[0]

        fund, holdings, facts = node("#fund"), node("#holdings"), node("#key-facts")
        if (
            fund.get("name") != blackrock.NAMES["IVV"]
            or fund.get("alternateName") != "IVV"
            or fund.get("url") != canonical
            or holdings.get("about") != {"@id": canonical + "#fund"}
            or facts.get("about") != {"@id": canonical + "#fund"}
        ):
            raise ValueError("benchmark_metadata_fund_mismatch")
        properties = facts.get("additionalProperty")
        if not isinstance(properties, list):
            raise ValueError("metadata_facts_unavailable")
        cusips = [
            x.get("value") for x in properties if isinstance(x, dict) and x.get("name") == "CUSIP"
        ]
        if page.cusips != ["464287200"] or (cusips and cusips != ["464287200"]):
            raise ValueError("benchmark_metadata_fund_mismatch")
        entity = holdings["mainEntity"]
        if not isinstance(entity, dict):
            raise ValueError("metadata_date_unavailable")
        modified = entity["dateModified"]
        dates = json.loads(page.dates[0], object_pairs_hook=_pairs, parse_constant=_constant)
        if type(modified) is not int or len(str(modified)) != 8 or dates != {"all": modified}:
            raise ValueError("metadata_date_ambiguous")
        effective = datetime.strptime(str(modified), "%Y%m%d").date().isoformat()
        if effective != observation.effective_date or effective > collected.date().isoformat():
            raise ValueError("benchmark_metadata_date_mismatch")
    except (UnicodeError, KeyError, TypeError, json.JSONDecodeError, RecursionError):
        raise ValueError("benchmark_metadata_structure_invalid") from None
    return FundMetadata(
        canonical_url=canonical,
        content_type=response.content_type,
        collected_at=collected.astimezone(UTC).isoformat(),
        holdings_date=effective,
        source_sha256=hashlib.sha256(response.body).hexdigest(),
        byte_count=len(response.body),
    )


def draft(observation: BenchmarkObservation, raw: bytes, metadata_raw: bytes) -> BenchmarkReview:
    from prosper.benchmark import BenchmarkReview
    from prosper.benchmark_review_context import review_context

    metadata = observation.metadata
    if metadata is None:
        raise ValueError("benchmark_metadata_unavailable")
    checked = inspect_metadata(
        observation,
        v.Response(200, metadata.response_url, metadata.content_type, metadata_raw),
        datetime.fromisoformat(metadata.collected_at),
    )
    if checked != metadata:
        raise ValueError("benchmark_metadata_binding_invalid")
    context = review_context(observation, raw)
    mapping = context.mapping
    if mapping is None:
        raise ValueError("unsupported_metadata_preparation")
    reference = metadata.canonical_url + "#fund"
    fund = b.Evidence(
        metadata.source_sha256,
        reference,
        metadata.holdings_date,
        metadata.collected_at[:10],
        metadata.holdings_date,
    )
    source = b.Evidence(
        context.source_sha256,
        "Retained IVV holdings " + context.effective_date,
        context.effective_date,
        context.collected_at[:10],
        context.effective_date,
    )
    # Zero cash is the definition of the modeled 100%-equity proxy, not the
    # fund's disclosed cash balance and never additional portfolio funding.
    proxy = b.Evidence(
        metadata.source_sha256,
        "Owner-adopted equity-only proxy: zero modeled cash",
        metadata.holdings_date,
        metadata.collected_at[:10],
        metadata.holdings_date,
    )
    return BenchmarkReview(
        observation_id=context.observation_id,
        reviewed_at=datetime.now(UTC).isoformat(),
        metadata_base64=base64.b64encode(metadata_raw).decode(),
        metadata_reference=reference,
        metadata_ticker="IVV",
        metadata_port_id="239726",
        metadata_cusip="464287200",
        metadata_as_of=metadata.holdings_date,
        metadata_reviewed=True,
        stipulation=r.Stipulation(
            context.source_sha256,
            v.Fund("IVV", "239726"),
            context.requested_date,
            context.effective_date,
            context.collected_at,
            fund,
            (r.SectionRule("holdings", "primary", "percentOfFunds", "percent", source),),
            tuple(
                r.RowRule(
                    r.Locator(x.section, x.index),
                    x.row_sha256,
                    b.Security(x.security_id, "USD", "stock", source) if x.security_id else None,
                    None,
                    source,
                )
                for x in mapping.rows
            ),
            b.Fact("0", proxy),
            "decimal",
        ),
        policy=e.Policy(
            (e.ValueField("holdings", "marketValue", "USD"),),
            tuple(
                e.Decision(r.Locator(x.section, x.index), x.action, x.reason) for x in mapping.rows
            ),
        ),
    )
