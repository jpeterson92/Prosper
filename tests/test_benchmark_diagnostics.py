"""Lossless pre-review source inspection and read-only recovery consumers."""

import base64
from pathlib import Path

import pytest

from prosper.advisory_recovery import backup, restore
from prosper.benchmark import BenchmarkFetch, BenchmarkImport
from prosper.benchmark_diagnostics import source_page
from prosper.storage import PersistenceError
from tests.test_benchmark_workflow import ROOT, fixture, workspace


def test_source_pages_keep_exact_tokens_sections_and_located_unknowns(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    observation = service.import_benchmark(fixture())
    raw = service.store.source_bytes(str(observation.source_sha256))
    page = source_page(observation, raw, limit=2)
    assert page.rows_available and page.total_rows == page.matched_rows == 8
    assert [(row.section, row.index) for row in page.rows] == [("equity", 0), ("equity", 1)]
    first = {c.name: c for c in page.rows[0].cells}
    assert first["percentOfFunds"].kind == "number"
    assert first["percentOfFunds"].value == "60.0000"
    assert first["marketValue"].kind == "string" and first["marketValue"].value == "60.00"
    assert page.rows[1].cells[-1].value == ""
    assert "unknown_weights:equity" in page.rows[1].issues
    unknown = source_page(observation, raw, issue="unknown_weights")
    assert [(r.section, r.index) for r in unknown.rows] == [("equity", 1), ("shortTermReserves", 1)]
    groups = {g.code: g for g in page.issue_groups}
    assert groups["unknown_weights"].occurrences == 2
    assert groups["unknown_weights"].affected_rows == 2
    assert groups["missing_ticker"].affected_rows == 2
    assert source_page(observation, raw, offset=2, limit=2).rows[0].index == 2
    assert source_page(observation, raw, section="derivatives").matched_rows == 1
    assert source_page(observation, raw, section="shortTermReservesMoneyMarket").matched_rows == 0
    assert source_page(observation, raw, query="fIaA").matched_rows == 1
    assert source_page(observation, raw, query="no such value").matched_rows == 0
    assert source_page(observation, raw, offset=100).rows == ()
    assert service.store.current()["revision"] == 0
    assert service.store.current()["snapshot_id"] is None
    target = workspace(tmp_path / "restored")
    restore(target.store, backup(service.store))
    saved = target.store.benchmark_observation(observation.request.observation_id)
    assert source_page(saved, target.store.source_bytes(str(saved.source_sha256)), limit=2) == page
    assert (
        workspace(tmp_path / "source").store.benchmark_observation(saved.request.observation_id)
        == saved
    )
    with pytest.raises(PersistenceError, match="benchmark_source_unavailable"):
        source_page(observation, raw.replace(b"60.0000", b"61.0000"))
    with pytest.raises(PersistenceError, match="benchmark_source_unavailable"):
        source_page(observation, None)


def test_csv_fields_preserve_original_values_separately_from_aliases(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    imported = BenchmarkImport.model_validate_json(
        (ROOT / "examples/synthetic/blackrock/current-observation.json").read_bytes()
    )
    observation = service.import_benchmark(imported)
    page = source_page(observation, base64.b64decode(imported.source_base64))
    row = page.rows[0]
    assert row.source_ref == "csv:record:0:lines:6-7"
    cells = {c.name: c for c in row.cells}
    assert cells["Name"].value == "Fictional\nAlpha"
    assert cells["Market Value"].value == "60,000.00" and cells["Market Value"].origin == "source"
    assert cells["marketValue"].value == "60000.00" and cells["marketValue"].origin == "adapter"
    raw = base64.b64decode(imported.source_base64)
    assert source_page(observation, raw, query="60,000.00").matched_rows == 1
    assert source_page(observation, raw, query="60000.00").matched_rows == 0
    missing = {c.name: c for c in page.rows[1].cells}
    assert missing["Market Weight"].value == "-" and missing["Market Weight"].kind == "string"
    assert missing["percentOfFunds"].kind == "null"
    assert page.rows[1].issues == ("unknown_weights:holdings",)


def test_nonobject_rows_nested_tokens_and_empty_sections_remain_inspectable(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    raw = (
        b'{"2000-01-03":{"equity":[null,{"ticker":null,'
        b'"extra":{"n":1.2300e+2,"b":false,"a":[null,""]}}],"fixedIncome":[]}}'
    )
    imported = fixture().model_copy(update={"source_base64": base64.b64encode(raw).decode()})
    observed = service.import_benchmark(imported)
    page = source_page(observed, raw)
    assert page.total_rows == 2 and page.section_counts["fixedIncome"] == 0
    assert page.rows[0].cells[0].kind == "null"
    assert "invalid_row:equity:0" in page.rows[0].issues
    assert page.rows[1].cells[0].kind == "null"
    assert page.rows[1].cells[1].value == '{"n":1.2300e+2,"b":false,"a":[null,""]}'
    assert source_page(observed, raw, query="1.2300e+2").matched_rows == 1


def test_pending_and_unavailable_are_not_empty_holdings(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    pending, _ = service.store.begin_benchmark(
        BenchmarkFetch(observation_id="pending", ticker="VTI", requested_date=None)
    )
    page = source_page(pending, None)
    assert not page.rows_available and page.rows == () and page.section_counts == {}
    assert page.total_rows is None and page.matched_rows is None
    failed = service.import_benchmark(fixture().model_copy(update={"http_status": 404}))
    page = source_page(failed, base64.b64decode(fixture().source_base64))
    assert not page.rows_available and page.total_rows is None and page.matched_rows is None
    assert page.issue_groups[0].code == "date_unavailable"


@pytest.mark.parametrize("offset,limit", [(-1, 20), (0, 0), (0, 101)])
def test_invalid_page_refuses(tmp_path: Path, offset: int, limit: int) -> None:
    service = workspace(tmp_path / "source")
    observed = service.import_benchmark(fixture())
    with pytest.raises(ValueError, match="invalid_source_page"):
        source_page(observed, base64.b64decode(fixture().source_base64), offset=offset, limit=limit)
