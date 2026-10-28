"""Fictional CSV semantics, exact dates and source-preserving application recovery."""

import base64
import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from prosper import blackrock as b
from prosper import vanguard as v
from prosper.advisory_recovery import backup, restore
from prosper.api_contracts import Upload
from prosper.benchmark import (
    BenchmarkDiagnostic,
    BenchmarkFetch,
    BenchmarkImport,
    BenchmarkObservation,
    BenchmarkReview,
    review_result,
)
from prosper.benchmark_reconciliation import row_identity
from tests.test_benchmark_workflow import ROOT, workspace

FOLDER = ROOT / "examples/synthetic/blackrock"


def acquire(raw: bytes, **changes: Any) -> v.Acquisition:
    selection = b.select_fund("IVV", date(2026, 10, 20))
    response = v.Response(200, selection.url, "text/csv", raw)
    from dataclasses import replace

    return b.acquire(
        selection,
        transport=lambda _: replace(response, **changes),
        collected_at=datetime(2026, 10, 22, tzinfo=UTC),
    )


def test_csv_original_cells_multiline_locators_and_unknowns_survive() -> None:
    raw = (FOLDER / "current.csv").read_bytes()
    observed = acquire(raw)
    assert observed.response and observed.response.body == raw
    assert observed.snapshot and observed.snapshot.effective_date.isoformat() == "2026-10-20"
    rows = observed.snapshot.sections[0].rows
    assert len(rows) == 6 and isinstance(rows[0], v.JsonObject)
    assert rows[0].get("Name") == "Fictional\nAlpha"
    assert rows[0].get("Market Value") == "60,000.00"
    assert rows[0].get("marketValue") == "60000.00"
    assert "lines:6-7" in str(rows[0].get("source_ref"))
    assert isinstance(rows[1], v.JsonObject) and rows[1].get("percentOfFunds") is None
    assert isinstance(rows[2], v.JsonObject) and rows[2].get("marketValue") == "-1.00"
    assert isinstance(rows[3], v.JsonObject) and rows[3].get("marketValue") is None
    assert isinstance(rows[4], v.JsonObject) and rows[4].get("Market Weight") == "0.00"
    assert rows[4].get("Notional Weight") == "0.50"


@pytest.mark.parametrize(
    "case,code",
    [
        ("wrong-date", "returned_date_mismatch"),
        ("no-date", "date_unavailable"),
        ("wrong-fund", "fund_name_mismatch"),
        ("html", "unexpected_content_type"),
        ("redirect", "unexpected_response_url"),
        ("truncated", "incomplete_response"),
        ("throttle", "http_error"),
        ("schema", "unsupported_holdings_columns"),
        ("bad-record", "holdings_record_cardinality_invalid"),
    ],
)
def test_no_silent_date_source_or_schema_fallback(case: str, code: str) -> None:
    raw = (FOLDER / "current.csv").read_bytes()
    changes: dict[str, Any] = {}
    if case == "wrong-date":
        raw = raw.replace(b"Oct 20, 2026", b"Oct 19, 2026")
    elif case == "no-date":
        raw = raw.replace(b"Oct 20, 2026", b"-")
    elif case == "wrong-fund":
        raw = raw.replace(b"iShares Core S&P 500 ETF", b"Another fund")
    elif case == "html":
        changes["content_type"] = "text/html"
    elif case == "redirect":
        changes["url"] = "https://example.invalid/holdings"
    elif case == "truncated":
        changes["body_complete"] = False
    elif case == "throttle":
        changes["status"] = 429
    elif case == "schema":
        raw = raw.replace(b"Market Weight", b"Unexpected Weight")
    else:
        raw += b'"Unaccounted footer",extra\n'
    result = acquire(raw, **changes)
    assert result.snapshot is None and result.issues == (code,)
    assert result.response and result.response.body == raw


def test_alternate_itot_columns_and_older_missing_values_are_not_reconstructed() -> None:
    records = list(csv.reader(io.StringIO((FOLDER / "current.csv").read_text(), newline="")))
    header = records[4]
    records[0] = [b.NAMES["ITOT"]]
    indices = [
        header.index("Market Weight" if name == "Weight (%)" else name)
        for name in b.ALTERNATE_COLUMNS
    ]
    records[4] = list(b.ALTERNATE_COLUMNS)
    for i in range(5, len(records)):
        records[i] = [records[i][j] for j in indices]
    records[5][b.ALTERNATE_COLUMNS.index("Market Value")] = "-"
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(records)
    selection = b.select_fund("ITOT")
    result = b.acquire(
        selection,
        transport=lambda _: v.Response(200, selection.url, "text/csv", stream.getvalue().encode()),
        collected_at=datetime(2026, 10, 22, tzinfo=UTC),
    )
    assert result.snapshot and len(result.snapshot.sections[0].rows) == 6
    first = result.snapshot.sections[0].rows[0]
    assert isinstance(first, v.JsonObject) and first.get("marketValue") is None
    assert first.get("quantity") == "6000.00" and first.get("price") == "10.00"
    assert "missing_column:Type" in result.issues


def test_import_review_selection_retry_and_recovery_use_original_csv(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    staged = service.stage(
        Upload.model_validate_json(
            (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
        )
    )
    service.store.select(staged.id, "holdings", 0)
    imported = BenchmarkImport.model_validate_json(
        (FOLDER / "current-observation.json").read_bytes()
    )
    observed = service.import_benchmark(imported)
    assert observed.status == "observed" and observed.section_counts == {"holdings": 6}
    assert service.import_benchmark(imported) == observed
    reviewed = BenchmarkReview.model_validate_json((FOLDER / "current-review.json").read_bytes())
    command = BenchmarkDiagnostic(
        run_id="ivv", expected_revision=1, as_of="2026-10-25T22:00:00Z", review=reviewed
    )
    result = service.diagnose_benchmark(command)
    assert result.outputs["status"] == "estimated-equity-benchmark", result.outputs
    assert result.outputs["weights"] == pytest.approx([2 / 3, 1 / 3])
    assert result.outputs["source_row_count"] == 6 and result.outputs["excluded_count"] == 4
    assert result.outputs["equity_value_total"] == "90000.0"
    assert service.diagnose_benchmark(command) == result
    service.store.select_benchmark(result.id, "choose-ivv", 1)
    target = workspace(tmp_path / "restored")
    restore(target.store, backup(service.store))
    assert target.store.run(result.id) == result
    assert (
        target.store.source_bytes(str(observed.source_sha256))
        == (FOLDER / "current.csv").read_bytes()
    )
    settings = target.store.current()["settings"]
    assert isinstance(settings, dict) and settings["benchmark_run_id"] == result.id


def test_included_missing_value_blocks_proxy_despite_supplied_quantity_and_price() -> None:
    raw = (FOLDER / "current.csv").read_bytes().replace(b"60,000.00", b"-")
    acquired = acquire(raw)
    assert acquired.snapshot is not None and acquired.response is not None
    observed = BenchmarkObservation(
        request=BenchmarkFetch(
            observation_id="fictional-ivv", ticker="IVV", requested_date="2026-10-20"
        ),
        collected_at="2026-10-22T00:00:00Z",
        status="observed",
        effective_date="2026-10-20",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        http_status=200,
        response_url=acquired.response.url,
        content_type="text/csv",
        request_sha256="a" * 64,
    )
    review = json.loads((FOLDER / "current-review.json").read_bytes())
    review["stipulation"]["raw_sha256"] = observed.source_sha256
    review["stipulation"]["rows"][0]["row_sha256"] = row_identity(
        acquired.snapshot.sections[0].rows[0]
    )
    review["stipulation"]["collected_at"] = "2026-10-22T00:00:00+00:00"
    review["reviewed_at"] = "2026-10-22T00:00:00Z"
    reviewed = BenchmarkReview.model_validate_json(json.dumps(review))
    result = review_result(
        observed,
        raw,
        reviewed,
        hashlib.sha256(base64.b64decode(reviewed.metadata_base64)).hexdigest(),
    )
    assert result.status != "estimated-equity-benchmark"
    assert result.weights == () and result.security_ids == ()
    assert any("value" in issue.code for issue in result.issues)


def test_fetched_blackrock_request_is_persisted_and_identical_retry_does_not_refetch(
    tmp_path: Path,
) -> None:
    service = workspace(tmp_path / "workspace")
    raw = (FOLDER / "current.csv").read_bytes()
    command = BenchmarkFetch(observation_id="fetch-ivv", ticker="IVV", requested_date="2026-10-20")
    with patch(
        "prosper.vanguard.fetch_https",
        side_effect=lambda s: v.Response(200, s.url, "text/csv", raw),
    ) as fetch:
        observed = service.fetch_benchmark(command)
        assert observed.status == "observed"
        assert service.fetch_benchmark(command) == observed
        assert fetch.call_count == 1
    assert service.store.source_bytes(str(observed.source_sha256)) == base64.b64decode(
        json.loads((FOLDER / "current-observation.json").read_bytes())["source_base64"]
    )
