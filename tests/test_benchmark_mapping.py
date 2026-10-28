"""Fictional preparation, independent coverage expectations and strict refusals."""

import base64
import csv
import io
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from prosper.benchmark import BenchmarkImport, BenchmarkObservation
from prosper.benchmark_review_context import BenchmarkReviewContext, review_context
from prosper.record_types import Identifier
from prosper.workspace import Workspace
from tests.test_benchmark_workflow import ROOT, fixture, workspace

FOLDER = ROOT / "examples/synthetic/blackrock"


def prepared(
    tmp_path: Path, changes: dict[tuple[int, str], str] | None = None
) -> tuple[Workspace, BenchmarkObservation, bytes, BenchmarkReviewContext]:
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    records = list(csv.reader(io.StringIO(base64.b64decode(source.source_base64).decode())))
    header = records[4]
    for (row, field), value in (changes or {}).items():
        records[row + 5][header.index(field)] = value
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerows(records)
    raw = out.getvalue().encode()
    source = source.model_copy(update={"source_base64": base64.b64encode(raw).decode()})
    service = workspace(tmp_path)
    observed = service.import_benchmark(source)
    return service, observed, raw, review_context(observed, raw)


def test_full_policy_result_keeps_original_unknowns_source_keys_and_read_only_state(
    tmp_path: Path,
) -> None:
    service, observed, raw, context = prepared(tmp_path / "source")
    result = context.mapping
    assert result is not None
    assert (result.included_count, result.excluded_count) == (2, 4)
    assert [(x.security_id, x.action) for x in result.rows[:2]] == [
        ("FIAA", "include"),
        ("FIBB", "include"),
    ]
    assert [x.index for x in result.rows] == list(range(6))
    assert [x.row_sha256 for x in result.rows] == [x.row_sha256 for x in context.rows]
    assert len({x.source_key for x in result.rows}) == 6
    assert result.rows[0].name == "Fictional\nAlpha"
    assert result.rows[0].raw_market_value == "60,000.00"
    assert result.rows[0].value_usd == 60000.0
    assert result.rows[2].value_usd == -1.0
    assert result.rows[3].value_usd is None
    assert result.retained_known_value_usd == 90000.0
    assert result.excluded_known_value_usd == 4.0
    assert result.unknown_value_rows == (3,)
    assert result.source_value_usd is result.aggregate_excluded_bps is None
    assert result.aggregate_highlight is None
    assert result.coverage_unknown_reasons == ("negative_source_value", "unknown_source_usd_value")
    assert result.history_status == result.tax_status == "not_assessed"
    assert review_context(observed, raw) == context
    assert service.store.source_bytes(str(observed.source_sha256)) == raw
    assert service.store.current()["revision"] == 0
    assert service.store.current()["settings"] == {}


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("Ticker", "-", "source_ticker_missing_or_unsupported"),
        ("Name", "", "source_name_missing"),
        ("Currency", "EUR", "unsupported_or_unknown_currency"),
        ("Market Currency", "-", "unsupported_or_unknown_currency"),
        ("Location", "-", "unsupported_or_unknown_source_location"),
        ("Exchange", "NO MARKET (E.G. UNLISTED)", "source_exchange_unavailable"),
        ("Type", "WARRANT", "unsupported_source_instrument"),
    ],
)
def test_ambiguous_missing_and_unsupported_facts_exclude_the_affected_row(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    _, _, _, context = prepared(tmp_path / "source", {(0, field): value})
    assert context.mapping is not None
    first = context.mapping.rows[0]
    assert first.action == "exclude" and first.security_id is None and first.reason == reason
    assert len(context.mapping.rows) == 6
    assert context.mapping.rows[1].action == "include"


def test_duplicate_ticker_refuses_both_mappings_without_first_match_or_value_double_count_claim(
    tmp_path: Path,
) -> None:
    _, _, _, context = prepared(tmp_path / "source", {(1, "Ticker"): "FIAA"})
    result = context.mapping
    assert result is not None
    assert all(x.reason == "ambiguous_source_ticker" for x in result.rows[:2])
    assert result.included_count == 0 and result.excluded_count == 6
    assert "duplicate_source_ticker" in result.coverage_unknown_reasons
    assert result.source_value_usd is result.aggregate_highlight is None


@pytest.mark.parametrize("over", [False, True])
def test_single_and_aggregate_thresholds_are_strict_and_use_pre_exclusion_value(
    tmp_path: Path, over: bool
) -> None:
    # Independent denominator 100,000; per-name 100 is exactly 10 bps,
    # all exclusions 1,000 are exactly 100 bps. Move one cent from retained
    # value to the first exclusion without changing the original denominator.
    changes = {
        (0, "Market Value"): "59,000.00" if not over else "58,999.99",
        (1, "Market Value"): "40,000.00",
        (2, "Market Value"): "100.00" if not over else "100.01",
        (3, "Market Value"): "0.00",
        (4, "Market Value"): "0.00",
        (5, "Market Value"): "900.00",
    }
    _, _, _, context = prepared(tmp_path / "source", changes)
    result = context.mapping
    assert result is not None
    assert result.source_value_usd == pytest.approx(100000.0, abs=1e-9)
    assert result.coverage_unknown_reasons == ()
    assert result.rows[2].highlight is over
    assert result.aggregate_highlight is over
    assert result.rows[5].highlight is True
    assert result.aggregate_excluded_bps == pytest.approx(100.0000 if not over else 100.0010)
    assert result.rows[2].excluded_bps == pytest.approx(10.0000 if not over else 10.0010)


def test_uninspected_provider_keeps_explicit_review_path(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    source = fixture()
    observed = service.import_benchmark(source)
    assert review_context(observed, base64.b64decode(source.source_base64)).mapping is None


def test_share_class_spaces_keep_exact_identity_without_guessing_provider_alias(
    tmp_path: Path,
) -> None:
    _, _, _, context = prepared(tmp_path / "source", {(0, "Ticker"): "FIAA B"})
    assert context.mapping is not None
    first = context.mapping.rows[0]
    assert first.action == "include" and first.ticker == "FIAA B"
    assert first.security_id == "issuer-" + first.source_key
    assert TypeAdapter(Identifier).validate_python(first.security_id) == first.security_id
    assert first.security_id != "FIAA-B" and first.security_id != "FIAA.B"
