"""Independent value expectations, explicit selection and source-preserving recovery."""

import base64
import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from prosper import vanguard as v
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import Upload
from prosper.benchmark import (
    BenchmarkDiagnostic,
    BenchmarkFetch,
    BenchmarkImport,
    BenchmarkResult,
    BenchmarkReview,
)
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/synthetic/benchmark"


def fixture() -> BenchmarkImport:
    return BenchmarkImport.model_validate_json((FIXTURE / "current-observation.json").read_bytes())


def review() -> BenchmarkReview:
    return BenchmarkReview.model_validate_json((FIXTURE / "current-review.json").read_bytes())


def workspace(path: Path) -> Workspace:
    return Workspace(AdvisoryStore(RuntimeBoundary(path)))


def seed(service: Workspace) -> None:
    upload = Upload.model_validate_json(
        (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
    )
    staged = service.stage(upload)
    service.store.select(staged.id, "holdings", 0)
    service.import_benchmark(fixture())


def command(
    run_id: str = "benchmark", revision: int = 1, reviewed: BenchmarkReview | None = None
) -> BenchmarkDiagnostic:
    return BenchmarkDiagnostic(
        run_id=run_id,
        expected_revision=revision,
        as_of="2026-10-25T22:00:00Z",
        review=reviewed or review(),
    )


def test_review_keeps_all_rows_and_derives_value_weights_without_percentage_normalization(
    tmp_path: Path,
) -> None:
    service = workspace(tmp_path / "runtime")
    seed(service)
    saved = service.diagnose_benchmark(command())
    result = BenchmarkResult.model_validate_json(json.dumps(saved.outputs))
    assert result.status == "estimated-equity-benchmark"
    assert result.source_row_count == 8 and result.included_count == 2
    assert result.excluded_count == 6 and result.unresolved_count == 0
    # Hand-derived: 60/(60+30), 30/(60+30); blanks never become source zero.
    assert result.weights == pytest.approx((2 / 3, 1 / 3))
    assert result.equity_value_total == "90.0"
    assert result.ledger[0].raw_percentage == "60.0000"
    assert result.ledger[0].percentage_token_kind == "number"
    assert result.ledger[1].raw_percentage == "" and result.ledger[1].published_weight is None
    assert result.excluded_known_usd_value == "10.0"
    assert len(result.excluded_unknown_usd_values) == 1
    assert service.store.current()["settings"] == {}
    assert service.diagnose_benchmark(command()) == saved
    assert service.store.select_benchmark(saved.id, "choose", 1) == {
        "outcome": "changed",
        "revision": 2,
    }
    service.store.configure({"benchmark_run_id": saved.id, "other": "later"}, "later", 2)
    assert service.store.select_benchmark(saved.id, "choose", 1) == {
        "outcome": "changed",
        "revision": 2,
    }
    assert service.store.current()["revision"] == 3
    reopened = workspace(tmp_path / "runtime")
    assert reopened.store.run(saved.id) == saved
    target = workspace(tmp_path / "restored")
    restore(target.store, backup(reopened.store))
    assert target.store.run(saved.id) == saved
    assert target.store.current()["settings"] == {"benchmark_run_id": saved.id, "other": "later"}
    observation = target.store.benchmark_observation("fictional-vti-2000")
    assert target.store.source_bytes(str(observation.source_sha256)) == base64.b64decode(
        fixture().source_base64
    )


@pytest.mark.parametrize(
    "change",
    ["fund", "date", "metadata", "row", "mapping", "missing-decision", "included-value"],
)
def test_wrong_or_incomplete_review_does_not_replace_selected_benchmark(
    tmp_path: Path, change: str
) -> None:
    service = workspace(tmp_path / "runtime")
    seed(service)
    good = service.diagnose_benchmark(command())
    service.store.select_benchmark(good.id, "choose", 1)
    before = service.store.current()
    data: dict[str, Any] = json.loads(review().model_dump_json())
    if change == "fund":
        data["metadata_ticker"] = "VOO"
    elif change == "date":
        data["metadata_as_of"] = "2000-01-02"
    elif change == "metadata":
        data["metadata_base64"] = base64.b64encode(b"wrong").decode()
    elif change == "row":
        data["stipulation"]["rows"][0]["row_sha256"] = "0" * 64
    elif change == "mapping":
        data["stipulation"]["rows"][0]["security"]["security_id"] = None
    elif change == "missing-decision":
        data["policy"]["decisions"].pop()
    else:
        data["policy"]["values"][0]["field"] = "nonexistent"
    bad = BenchmarkReview.model_validate_json(json.dumps(data))
    if change in ("fund", "date", "metadata"):
        with pytest.raises(PersistenceError, match="benchmark_review_invalid"):
            service.diagnose_benchmark(command("bad", 2, bad))
    else:
        saved = service.diagnose_benchmark(command("bad", 2, bad))
        assert saved.outputs["status"] == "incomplete"
        with pytest.raises(PersistenceError, match="benchmark_selection_unavailable"):
            service.store.select_benchmark(saved.id, "bad-choice", 2)
    assert service.store.current()["settings"] == before["settings"]
    assert service.store.current()["revision"] == before["revision"]


@pytest.mark.parametrize(
    "case",
    [
        "latest",
        "historical",
        "wrong-date",
        "empty",
        "throttle",
        "schema",
        "duplicate",
        "interrupted",
        "redirect",
    ],
)
def test_fetch_is_bounded_persistent_and_never_falls_back_or_refetches(
    tmp_path: Path, case: str
) -> None:
    service = workspace(tmp_path / "runtime")
    requested = None if case == "latest" else "2000-01-03"
    request = BenchmarkFetch(observation_id="fetch", ticker="VOO", requested_date=requested)
    body = base64.b64decode(fixture().source_base64)
    if case == "latest":
        body = (
            body[:-1] + b',"latestEffectiveDate":"2000-01-03"}'
            if body.endswith(b"}")
            else json.dumps({**json.loads(body), "latestEffectiveDate": "2000-01-03"}).encode()
        )
    if case == "wrong-date":
        body = body.replace(b"2000-01-03", b"2000-01-04")
    if case == "empty":
        body = b"{}"
    if case == "schema":
        body = b'{"2000-01-03":{"equity":[]}}'
    if case == "duplicate":
        body = b'{"2000-01-03":{},"2000-01-03":{}}'
    status = 429 if case == "throttle" else 302 if case == "redirect" else 200

    def transport(selection: v.Selection) -> v.Response:
        return v.Response(status, selection.url, "application/json", body, case != "interrupted")

    with patch("prosper.vanguard.fetch_https", side_effect=transport) as fetch:
        # acquire's default transport is resolved at call time.
        first = service.fetch_benchmark(request)
        assert service.fetch_benchmark(request) == first
        assert fetch.call_count == 1
    assert first.request.ticker == "VOO" and first.request.requested_date == requested
    assert first.status == ("observed" if case in ("latest", "historical") else "unavailable")
    assert first.source_sha256 is not None
    assert service.store.source_bytes(first.source_sha256) == body
    assert service.store.current()["settings"] == {}
    with pytest.raises(PersistenceError, match="command_key_reused"):
        service.fetch_benchmark(request.model_copy(update={"ticker": "VTI"}))


def test_pending_fetch_and_interrupted_result_resume_without_reacquisition(tmp_path: Path) -> None:
    service = workspace(tmp_path / "runtime")
    seed(service)
    request = BenchmarkFetch(observation_id="interrupted", ticker="VTI", requested_date=None)
    pending, fresh = service.store.begin_benchmark(request)
    assert fresh and pending.status == "pending"
    with patch("prosper.vanguard.fetch_https", side_effect=AssertionError("must not reacquire")):
        assert workspace(tmp_path / "runtime").fetch_benchmark(request) == pending
    with patch.object(service.store, "complete_run", side_effect=RuntimeError("interrupted")):
        with pytest.raises(RuntimeError):
            service.diagnose_benchmark(command())
    assert service.store.run("benchmark").status == "running"
    resumed = workspace(tmp_path / "runtime").diagnose_benchmark(command())
    assert resumed.status == "partial" and resumed.outputs["equity_value_total"] == "90.0"


def test_review_knowledge_can_follow_collection_but_cannot_follow_saved_analysis(
    tmp_path: Path,
) -> None:
    service = workspace(tmp_path / "runtime")
    seed(service)
    data = json.loads(review().model_dump_json())
    data["reviewed_at"] = "2000-01-05T12:00:00Z"
    for row in data["stipulation"]["rows"]:
        row["evidence"]["recorded"] = "2000-01-05"
        if row["security"]:
            row["security"]["evidence"]["recorded"] = "2000-01-05"
    reviewed = BenchmarkReview.model_validate_json(json.dumps(data))
    assert (
        service.diagnose_benchmark(command(reviewed=reviewed)).outputs["status"]
        == "estimated-equity-benchmark"
    )
    future = reviewed.model_copy(update={"reviewed_at": "2026-10-26T22:00:00Z"})
    with pytest.raises(PersistenceError, match="benchmark_knowledge_after_analysis"):
        service.diagnose_benchmark(command("future", reviewed=future))


def test_cache_clear_preserves_unselected_observations_and_corruption_blocks_backup(
    tmp_path: Path,
) -> None:
    service = workspace(tmp_path / "runtime")
    seed(service)
    saved = service.diagnose_benchmark(command())
    service.store.clear_history_cache("clear", 1)
    assert service.store.benchmark_observation("fictional-vti-2000").source_sha256
    assert service.diagnose_benchmark(command()) == saved
    with sqlite3.connect(service.store.runtime.path(DATABASE_NAME)) as connection:
        connection.execute(
            "UPDATE sources SET zlib_bytes=? WHERE sha256="
            "(SELECT source_sha256 FROM benchmark_observations)",
            (b"corrupt",),
        )
    assert service.store.run(saved.id) == saved
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        service.store.select_benchmark(saved.id, "choose", 2)
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        backup(service.store)
