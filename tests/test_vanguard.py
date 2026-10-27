"""Fictional full-portfolio response cases; no network or financial acceptance."""

import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from email.message import Message
from fractions import Fraction
from http.client import IncompleteRead
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import prosper.vanguard as vanguard
from prosper.vanguard import (
    DEFAULT_BENCHMARK_SOURCE,
    Fund,
    JsonNumber,
    JsonObject,
    Response,
    Selection,
    acquire,
    fetch_https,
    select_fund,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)
SELECTION = select_fund("VTI", date(2026, 9, 30))
BODY = b"""{"2026-09-30":{
"equity":[
{"holdingName":"Fictional Alpha","ticker":"SAAA","cusip":"FICT00001",
"percentOfFunds":60.0000,"quantity":1.2000e+1,"sector":"Stipulated Group"},
{"holdingName":"Fictional Beta","ticker":"SBBB","cusip":"FICT00002",
"percentOfFunds":40,"unmappedSourceField":"retain this"}],
"fixedIncome":[],"shortTermReserves":[],"shortTermReservesMoneyMarket":[],
"formattedFundOfFundsHoldings":[],"allocationToUnderlyingFunds":[],"derivatives":[]}}"""


def inspect(raw: bytes = BODY, selection: Selection = SELECTION) -> vanguard.Acquisition:
    return acquire(
        selection,
        collected_at=NOW,
        transport=lambda selected: Response(
            200, selected.url, "application/json; charset=utf-8", raw
        ),
    )


def test_standard_source_and_explicit_fund_date_selection() -> None:
    assert DEFAULT_BENCHMARK_SOURCE == "vanguard-full-holdings"
    assert SELECTION.source == DEFAULT_BENCHMARK_SOURCE
    assert SELECTION.url == (
        "https://advisors.vanguard.com/investments/products/api/funds/0970/holdings/"
        "historical?effectiveDate=2026-09-30"
    )
    assert select_fund(" voo ").url.endswith("/0968/holdings/latest")
    with pytest.raises(ValueError, match="unsupported_vanguard_fund"):
        select_fund("https://untrusted.invalid/")
    with pytest.raises(ValueError, match="unsupported_vanguard_fund"):
        Selection(Fund("VTI", "../../other"))


def test_full_response_exact_lexemes_source_identity_and_replay() -> None:
    result = inspect()
    assert result == inspect()
    assert result.response is not None and result.response.body == BODY
    snapshot = result.snapshot
    assert snapshot is not None and result.issues == ()
    assert snapshot.raw_sha256 == hashlib.sha256(BODY).hexdigest()
    assert snapshot.effective_date == date(2026, 9, 30) and snapshot.collected_at == NOW
    equity = snapshot.sections[0]
    assert len(equity.rows) == 2 and equity.known_weight_percent_sum == 100
    first = equity.rows[0]
    second = equity.rows[1]
    assert isinstance(first, JsonObject) and isinstance(second, JsonObject)
    assert type(first.get("quantity")) is JsonNumber
    assert first.get("quantity") == "1.2000e+1"
    assert first.get("percentOfFunds") == "60.0000"
    assert second.get("unmappedSourceField") == "retain this"
    assert not result.benchmark_ready and not snapshot.benchmark_ready
    assert "fund_identity_request_bound_only" in snapshot.qualification_gaps
    with pytest.raises(FrozenInstanceError):
        snapshot.effective_date = date(2020, 1, 1)  # type: ignore[misc]
    assert "Fictional Alpha" not in repr(result)
    assert snapshot.raw_sha256 != inspect(BODY.replace(b"60.0000", b"60")).snapshot.raw_sha256  # type: ignore[union-attr]


def test_unknown_weights_and_identifiers_preserved_with_partial_sum() -> None:
    raw = BODY.replace(b'"percentOfFunds":40', b'"percentOfFunds":""').replace(
        b'"ticker":"SBBB","cusip":"FICT00002"', b'"ticker":"","cusip":null'
    )
    result = inspect(raw)
    assert result.snapshot is not None
    equity = result.snapshot.sections[0]
    assert len(equity.rows) == 2
    assert equity.known_weight_percent_sum == 60 and equity.unknown_weight_rows == (1,)
    assert set(result.issues) == {
        "unknown_weights:equity",
        "missing_ticker:equity:1",
        "missing_cusip:equity:1",
    }
    assert result.response is not None and result.response.body == raw


def test_overlapping_sections_negative_values_and_nonunit_sums_not_repaired() -> None:
    row = b'[{"holdingName":"Fictional reserve","percentOfFunds":-0.1250}]'
    raw = (
        BODY.replace(b'"shortTermReserves":[]', b'"shortTermReserves":' + row)
        .replace(b'"allocationToUnderlyingFunds":[]', b'"allocationToUnderlyingFunds":' + row)
        .replace(b'"percentOfFunds":40', b'"percentOfFunds":39.8540')
    )
    result = inspect(raw)
    assert result.snapshot is not None
    sections = {section.name: section for section in result.snapshot.sections}
    assert sections["equity"].known_weight_percent_sum == pytest.approx(float(Fraction(49927, 500)))
    assert sections["shortTermReserves"].known_weight_percent_sum == pytest.approx(
        float(Fraction(-1, 8))
    )
    assert sections["shortTermReserves"].rows == sections["allocationToUnderlyingFunds"].rows
    assert len(result.issues) == 2  # One retained negative observation in each source section.
    assert not result.benchmark_ready


def test_unknown_sections_invalid_rows_and_alternate_schemas_survive() -> None:
    raw = (
        BODY.replace(b'"fixedIncome":[]', b'"fixedIncome":[null]')
        .replace(b'"derivatives":[]', b'"derivatives":[],"futureSection":{"unmapped":true}')
        .replace(
            b'"shortTermReservesMoneyMarket":[]',
            b'"shortTermReservesMoneyMarket":[{"issuerName":"Fictional"}]',
        )
    )
    result = inspect(raw)
    assert result.snapshot is not None
    doc = result.snapshot.document.get("2026-09-30")
    assert isinstance(doc, JsonObject) and isinstance(doc.get("futureSection"), JsonObject)
    assert "invalid_row:fixedIncome:0" in result.issues
    assert "unknown_section:futureSection" in result.issues
    alternate = next(
        s for s in result.snapshot.sections if s.name == "shortTermReservesMoneyMarket"
    )
    assert alternate.known_weight_percent_sum is None and alternate.unknown_weight_rows == ()


def test_latest_is_bound_to_returned_effective_date() -> None:
    raw = BODY.replace(b'{"2026-09-30":', b'{"latestEffectiveDate":"2026-09-30","2026-09-30":', 1)
    result = inspect(raw, select_fund("VTI"))
    assert result.snapshot is not None and result.snapshot.effective_date == date(2026, 9, 30)


@pytest.mark.parametrize(
    "raw,reason",
    [
        (BODY.replace(b"2026-09-30", b"2026-08-31"), "unexpected_envelope_or_date"),
        (b'{"basketId":"fictional","holding":[]}', "basket_feed_forbidden"),
        (b'{"holding":[]}', "basket_feed_forbidden"),
        (b'{"trdDate":"09/30/2026","holding":[]}', "basket_feed_forbidden"),
        (b'{"2026-09-30":{},"2026-09-30":{}}', "duplicate_json_key"),
        (b'{"2026-09-30":{"equity":[NaN]}}', "nonfinite_json_number"),
        (b'{"2026-09-30":{"equity":[]}}', "equity_section_missing_or_empty"),
        (b'{"2026-09-30":[]}', "requested_date_missing"),
        (b'{"2026-09-30":', "invalid_json"),
        (b"\xff", "invalid_json"),
        (b"[]", "invalid_envelope"),
        (b"", "response_size_limit"),
    ],
)
def test_rejections_preserve_response_and_never_initiate_fallback(raw: bytes, reason: str) -> None:
    calls: list[Selection] = []

    def transport(selection: Selection) -> Response:
        calls.append(selection)
        return Response(200, selection.url, "application/json", raw)

    result = acquire(SELECTION, transport=transport, collected_at=NOW)
    assert calls == [SELECTION]
    assert result.snapshot is None and result.issues == (reason,)
    assert result.response is not None and result.response.body == raw


@pytest.mark.parametrize("status", [204, 404, 429, 500, 302])
def test_http_failure_or_empty_date_is_not_latest_fallback(status: int) -> None:
    result = acquire(
        SELECTION,
        collected_at=NOW,
        transport=lambda s: Response(status, s.url, "application/json", b"source-error"),
    )
    assert result.snapshot is None
    assert result.issues == (("date_unavailable" if status in (204, 404) else "http_error"),)
    assert result.response is not None and result.response.body == b"source-error"


@pytest.mark.parametrize(
    "url,content_type,issue",
    [
        ("https://other.invalid", "application/json", "unexpected_response_url"),
        (SELECTION.url, "text/html", "unexpected_content_type"),
    ],
)
def test_redirect_and_content_type(url: str, content_type: str, issue: str) -> None:
    result = acquire(
        SELECTION, collected_at=NOW, transport=lambda s: Response(200, url, content_type, BODY)
    )
    assert result.issues == (issue,) and result.snapshot is None


def test_transport_failure_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_: Selection) -> Response:
        raise URLError("fictional unavailable network")

    result = acquire(SELECTION, collected_at=NOW, transport=fail)
    assert result.response is None and result.issues == ("transport_error",)
    monkeypatch.setattr(vanguard, "MAX_ROWS", 1)
    assert inspect().issues == ("row_limit",)
    monkeypatch.setattr(vanguard, "MAX_BYTES", 10)
    assert inspect().issues == ("response_size_limit",)


@pytest.mark.parametrize("weight", ['"1e1000000"', '"NaN"', "true", "null", '"<0.01"'])
def test_unusable_source_weights_remain_unknown(weight: str) -> None:
    result = inspect(BODY.replace(b'"percentOfFunds":40', f'"percentOfFunds":{weight}'.encode()))
    assert result.snapshot is not None
    assert result.snapshot.sections[0].known_weight_percent_sum == 60
    assert result.snapshot.sections[0].unknown_weight_rows == (1,)


def test_collection_and_latest_date_validation() -> None:
    with pytest.raises(ValueError, match="collection_time_requires_timezone"):
        acquire(SELECTION, collected_at=datetime(2026, 10, 24))
    raw = BODY.replace(b'{"2026-09-30":', b'{"latestEffectiveDate":"invalid","2026-09-30":', 1)
    assert inspect(raw, select_fund("VTI")).issues == ("invalid_effective_date",)
    raw = BODY.replace(b'{"2026-09-30":', b'{"latestEffectiveDate":"2026-08-31","2026-09-30":', 1)
    assert inspect(raw).issues == ("returned_date_mismatch",)
    future = select_fund("VTI", date(2027, 1, 31))
    assert inspect(BODY.replace(b"2026-09-30", b"2027-01-31"), future).issues == (
        "future_effective_date",
    )


def test_default_http_transport_is_bounded_and_refuses_redirects() -> None:
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.status, response.url = 200, SELECTION.url
    response.headers.get.return_value = "application/json"
    response.read.return_value = BODY
    with patch("prosper.vanguard.build_opener", return_value=opener) as factory:
        result = acquire(SELECTION, collected_at=NOW)
    assert result.snapshot is not None
    response.read.assert_called_once_with(vanguard.MAX_BYTES + 1)
    request = opener.open.call_args.args[0]
    assert request.full_url == SELECTION.url
    assert request.get_header("Accept") == "application/json"
    assert opener.open.call_args.kwargs == {"timeout": 30}
    handler = factory.call_args.args[0]
    assert (
        handler.redirect_request(Request(SELECTION.url), None, 302, "", {}, "https://other.invalid")
        is None
    )


def test_http_error_response_body_is_retained() -> None:
    headers = Message()
    headers["Content-Type"] = "application/json"
    error = HTTPError(SELECTION.url, 404, "not found", headers, BytesIO(b"fictional error"))
    with patch("prosper.vanguard.build_opener") as factory:
        factory.return_value.open.side_effect = error
        response = fetch_https(SELECTION)
    assert response.status == 404 and response.body == b"fictional error"


def test_interrupted_http_body_cannot_become_a_snapshot() -> None:
    with patch("prosper.vanguard.build_opener") as factory:
        response = factory.return_value.open.return_value.__enter__.return_value
        response.status, response.url = 200, SELECTION.url
        response.headers.get.return_value = "application/json"
        response.read.side_effect = IncompleteRead(BODY, 100)
        result = acquire(SELECTION, collected_at=NOW)
    assert result.snapshot is None and result.issues == ("incomplete_response",)
    assert result.response is not None and result.response.body == BODY
    assert not result.response.body_complete


def test_depth_limit_does_not_lose_source_body() -> None:
    raw = json.dumps({"2026-09-30": {"equity": [[[[[[[]]]]]]]}}).encode()
    for _ in range(40):
        raw = b"[" + raw + b"]"
    result = inspect(raw)
    assert result.snapshot is None and result.issues == ("json_depth_limit",)
    assert result.response is not None and result.response.body == raw
