"""Source-bound automatic preparation, strict evidence and current recovery."""

import base64
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from prosper import benchmark_metadata as m
from prosper import vanguard as v
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, review_result
from prosper.storage import PersistenceError, RuntimeBoundary
from tests.test_benchmark_workflow import ROOT, seed, workspace

FOLDER = ROOT / "examples/synthetic/blackrock"


def response(raw: bytes | None = None) -> v.Response:
    return v.Response(
        200, m.IVV_URL, "text/html;charset=UTF-8", raw or (FOLDER / "metadata.html").read_bytes()
    )


def imported(raw: bytes) -> m.MetadataImport:
    return m.MetadataImport(
        collected_at="2026-10-22T12:00:00Z",
        response_url=m.IVV_URL,
        content_type="text/html;charset=UTF-8",
        http_status=200,
        body_complete=True,
        source_base64=base64.b64encode(raw).decode(),
    )


def test_complete_large_metadata_current_review_cache_clear_and_recovery(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    seed(service)
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    observation = service.import_benchmark(source)
    small = (FOLDER / "metadata.html").read_bytes()
    # One meaningful >2 MiB boundary case, matching the measured issuer-page size.
    raw = small.replace(b"</body>", b"<!--" + b"x" * (2996630 - len(small) - 7) + b"--></body>")
    assert len(raw) == 2996630
    command = m.PrepareRequest(
        observation_id=observation.request.observation_id, metadata_response=imported(raw)
    )
    reviewed = service.prepare_benchmark(command)
    saved = service.store.benchmark_observation(observation.request.observation_id)
    assert saved.metadata is not None
    assert saved.metadata.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert saved.metadata.canonical_url == m.IVV_CANONICAL_URL
    assert saved.metadata.byte_count == len(raw)
    assert base64.b64decode(reviewed.metadata_base64) == raw
    assert reviewed.stipulation.benchmark_cash.raw == "0"
    assert "equity-only proxy" in reviewed.stipulation.benchmark_cash.evidence.reference
    assert reviewed.stipulation.benchmark_cash.evidence.reference != reviewed.metadata_reference
    result = review_result(
        saved, base64.b64decode(source.source_base64), reviewed, saved.metadata.source_sha256
    )
    assert result.status == "estimated-equity-benchmark"
    assert result.equity_value_total == "90000.0"
    assert result.weights == pytest.approx((2 / 3, 1 / 3), abs=1e-14)
    run = service.diagnose_benchmark(
        BenchmarkDiagnostic(
            run_id="prepared", expected_revision=1, as_of=reviewed.reviewed_at, review=reviewed
        )
    )
    assert run.outputs["metadata_source_sha256"] == saved.metadata.source_sha256
    assert service.store.current()["settings"] == {}
    with patch.object(m, "fetch_metadata", side_effect=AssertionError("no refetch")):
        cached = service.prepare_benchmark(
            m.PrepareRequest(observation_id=saved.request.observation_id)
        )
    assert cached.stipulation == reviewed.stipulation and cached.policy == reviewed.policy
    service.store.clear_history_cache("clear-history", 1)
    assert service.store.source_bytes(saved.metadata.source_sha256) == raw
    target = workspace(tmp_path / "target")
    restore(target.store, backup(service.store))
    reopened = AdvisoryStore.existing(RuntimeBoundary(tmp_path / "target"))
    assert reopened.benchmark_observation(saved.request.observation_id) == saved
    assert reopened.source_bytes(saved.metadata.source_sha256) == raw
    assert reopened.run("prepared") == run
    # A retained digest cannot silently become absent metadata/empty preparation.
    with sqlite3.connect(tmp_path / "target" / DATABASE_NAME) as connection:
        connection.execute("DELETE FROM sources WHERE sha256=?", (saved.metadata.source_sha256,))
    with pytest.raises(PersistenceError):
        reopened.benchmark_observation(saved.request.observation_id)


def test_native_identical_and_concurrent_retries_acquire_once(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    observation = service.import_benchmark(source)
    command = m.PrepareRequest(observation_id=observation.request.observation_id)
    with patch.object(m, "fetch_metadata", return_value=response()) as fetch:
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(service.prepare_benchmark, [command, command]))
        assert fetch.call_count == 1
    assert values[0].metadata_base64 == values[1].metadata_base64
    assert service.store.current()["revision"] == 0
    assert service.store.current()["settings"] == {}


@pytest.mark.parametrize(
    "case",
    [
        "fund",
        "cusip",
        "date",
        "missing",
        "ambiguous",
        "url",
        "type",
        "partial",
        "oversized",
        "future",
    ],
)
def test_invalid_metadata_does_not_bind_or_mutate_selected_work(tmp_path: Path, case: str) -> None:
    service = workspace(tmp_path / "source")
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    observation = service.import_benchmark(source)
    raw = (FOLDER / "metadata.html").read_bytes()
    if case == "fund":
        raw = raw.replace(b'"alternateName":"IVV"', b'"alternateName":"ITOT"')
    if case == "cusip":
        raw = raw.replace(b">464287200<", b">464287150<")
    if case == "date":
        raw = raw.replace(b"20261020", b"20261019")
    if case == "missing":
        raw = raw.replace(b"keyFundFacts-cusip", b"unknown-field")
    if case == "ambiguous":
        raw = raw.replace(
            b'"dateModified":20261020', b'"dateModified":20261020,"dateModified":20261020'
        )
    if case == "oversized":
        raw = b"x" * (m.MAX_METADATA_BYTES + 1)
    payload = imported(raw)
    if case == "url":
        payload = payload.model_copy(update={"response_url": "https://example.invalid"})
    if case == "type":
        payload = payload.model_copy(update={"content_type": "application/json"})
    if case == "partial":
        payload = payload.model_copy(update={"body_complete": False})
    if case == "future":
        payload = payload.model_copy(update={"collected_at": "2099-01-01T00:00:00Z"})
    with pytest.raises(PersistenceError, match="benchmark_metadata_invalid"):
        service.prepare_benchmark(
            m.PrepareRequest(
                observation_id=observation.request.observation_id, metadata_response=payload
            )
        )
    assert service.store.benchmark_observation(observation.request.observation_id).metadata is None
    assert service.store.current()["revision"] == 0


def test_transport_failure_is_retryable_and_no_replacement_source_is_used(tmp_path: Path) -> None:
    service = workspace(tmp_path / "source")
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    observation = service.import_benchmark(source)
    command = m.PrepareRequest(observation_id=observation.request.observation_id)
    with patch.object(
        m, "fetch_metadata", side_effect=OSError("sensitive transport detail")
    ) as fetch:
        with pytest.raises(PersistenceError, match="benchmark_metadata_unavailable"):
            service.prepare_benchmark(command)
        assert fetch.call_count == 1
    with patch.object(m, "fetch_metadata", return_value=response()) as fetch:
        assert service.prepare_benchmark(command).metadata_ticker == "IVV"
        assert fetch.call_count == 1
    saved = service.store.benchmark_observation(observation.request.observation_id)
    assert saved.metadata is not None
    changed = response().body.replace(b"Fictitious", b"Changed fictitious")
    with pytest.raises(PersistenceError, match="benchmark_metadata_already_bound"):
        service.prepare_benchmark(
            m.PrepareRequest(
                observation_id=observation.request.observation_id,
                metadata_response=imported(changed),
            )
        )


def test_body_bound_and_strict_canonical_dates_are_not_metadata_validity_guesses(
    tmp_path: Path,
) -> None:
    service = workspace(tmp_path / "source")
    source = BenchmarkImport.model_validate_json((FOLDER / "current-observation.json").read_bytes())
    observation = service.import_benchmark(source)
    for raw in [
        response().body.replace(b"&quot;all&quot;:20261020", b"&quot;all&quot;:20261021"),
        response().body.replace(b'"dateModified":20261020', b'"dateModified":NaN'),
    ]:
        with pytest.raises(ValueError):
            m.inspect_metadata(observation, response(raw), datetime(2026, 10, 22, tzinfo=UTC))
    with pytest.raises(ValueError):
        m.decode_metadata("")
    with pytest.raises(ValueError):
        m.decode_metadata(base64.b64encode(b"x" * (m.MAX_METADATA_BYTES + 1)).decode())


@pytest.mark.parametrize("declared", [None, "matching", "short", "long", "invalid"])
def test_native_transport_has_one_fixed_url_no_redirects_and_a_bounded_read(
    declared: str | None,
) -> None:
    from io import BytesIO
    from urllib.request import Request

    class Reply(BytesIO):
        code = 200
        url = m.IVV_URL
        headers = {"Content-Type": "text/html"}

        def read(self, size: int | None = -1) -> bytes:
            assert size == m.MAX_METADATA_BYTES + 1
            return super().read(size)

    class Opener:
        def open(self, request: Request, timeout: int) -> Reply:
            assert request.full_url == m.IVV_URL and timeout == 30
            assert request.header_items() == [("Accept", "text/html")]
            return Reply(response().body)

    def build(handler: object) -> Opener:
        assert isinstance(handler, v._NoRedirect)
        return Opener()

    if declared is not None:
        Reply.headers["Content-Length"] = {
            "matching": str(len(response().body)),
            "short": str(len(response().body) - 1),
            "long": str(len(response().body) + 1),
            "invalid": "unavailable",
        }[declared]
    with patch.object(m, "build_opener", side_effect=build) as factory:
        actual = m.fetch_metadata()
        assert actual.body == response().body
        assert actual.body_complete is (declared in (None, "matching"))
        assert actual.url == m.IVV_URL and factory.call_count == 1
