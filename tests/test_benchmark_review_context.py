"""Source bindings for form authoring retain types/unknowns without financial choices."""

import base64
import json
from pathlib import Path

import pytest

from prosper.benchmark import BenchmarkImport
from prosper.benchmark_review_context import review_context
from prosper.storage import PersistenceError
from tests.test_benchmark_workflow import ROOT, fixture, workspace


@pytest.mark.parametrize("provider", ["benchmark", "blackrock"])
def test_context_binds_original_rows_without_adopting_review_choices(
    tmp_path: Path, provider: str
) -> None:
    folder = ROOT / "examples/synthetic" / provider
    source = BenchmarkImport.model_validate_json((folder / "current-observation.json").read_bytes())
    expected = json.loads((folder / "current-review.json").read_bytes())
    service = workspace(tmp_path / "source")
    observed = service.import_benchmark(source)
    raw = service.store.source_bytes(str(observed.source_sha256))
    context = review_context(observed, raw)
    assert context.source_sha256 == expected["stipulation"]["raw_sha256"]
    assert context.collected_at == expected["stipulation"]["collected_at"]
    assert [(r.section, r.index, r.row_sha256) for r in context.rows] == [
        (r["locator"]["section"], r["locator"]["index"], r["row_sha256"])
        for r in expected["stipulation"]["rows"]
    ]
    assert context.sections[0].row_count == (4 if provider == "benchmark" else 6)
    assert "marketValue" in context.sections[0].fields
    assert context.rows[0].source_ticker == "FIAA"
    assert service.store.current()["revision"] == 0
    assert (
        workspace(tmp_path / "source").store.benchmark_observation(observed.request.observation_id)
        == observed
    )
    with pytest.raises(PersistenceError, match="benchmark_source_unavailable"):
        review_context(observed, raw + b" ")


def test_context_preserves_empty_nonarray_and_invalid_rows(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    raw = b'{"2000-01-03":{"equity":[null,{"ticker":""}],"fixedIncome":[],"unknown":null}}'
    imported = fixture().model_copy(update={"source_base64": base64.b64encode(raw).decode()})
    observed = service.import_benchmark(imported)
    context = review_context(observed, raw)
    assert [(s.section, s.row_count) for s in context.sections] == [
        ("equity", 2),
        ("fixedIncome", 0),
        ("unknown", None),
    ]
    assert len(context.rows) == 2
    assert context.rows[0].source_ticker is None and context.rows[1].source_ticker == ""
    assert context.sections[1].fields == context.sections[2].fields == ()


def test_unavailable_context_refuses_instead_of_constructing_empty_review(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    imported = fixture().model_copy(update={"http_status": 404})
    observed = service.import_benchmark(imported)
    with pytest.raises(PersistenceError, match="benchmark_source_unavailable"):
        review_context(observed, base64.b64decode(imported.source_base64))
