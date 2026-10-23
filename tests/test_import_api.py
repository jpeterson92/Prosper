"""Real HTTP/SQLite contract expectations over the protected owning process."""

import copy
import hashlib
import http.client
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from prosper.api_contracts import API_VERSION, CommandResponse, CurrentResponse, PreviewResponse
from prosper.evidence import RuntimeBoundary
from prosper.imports import OUTCOMES
from prosper.local_api import serve
from prosper.persistence import DATABASE_NAME

SOURCE = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]


def document() -> Document:
    return cast(Document, json.loads((SOURCE / "examples/synthetic/F001.json").read_bytes()))


def encoded(data: Document) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


@dataclass(repr=False)
class API:
    process: subprocess.Popen[str]
    origin: str
    port: int
    root: Path
    token: str = ""

    def request(
        self,
        path: str,
        method: str = "GET",
        data: Document | bytes | None = None,
        headers: dict[str, str | None] | None = None,
        *,
        authorized: bool = True,
    ) -> tuple[int, Document]:
        request_headers = {"Origin": self.origin}
        if authorized:
            request_headers["Authorization"] = "Bearer " + self.token
        body: bytes | None = None
        if isinstance(data, dict):
            body = encoded(data)
            request_headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            body = data
            request_headers["Content-Type"] = "application/octet-stream"
        for key, value in (headers or {}).items():
            if value is None:
                request_headers.pop(key, None)
            else:
                request_headers[key] = value
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=12)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            raw = response.read()
            if response.status == 200:
                assert response.getheader("cache-control") == "no-store"
                assert response.getheader("content-type") == "application/json"
                assert response.getheader("x-content-type-options") == "nosniff"
            parsed = cast(Document, json.loads(raw))
            if path == "/api/v1/previews" or path.startswith("/api/v1/previews/"):
                if response.status == 200:
                    PreviewResponse.model_validate_json(raw)
            elif path == "/api/v1/commit" and response.status == 200:
                CommandResponse.model_validate_json(raw)
            elif path == "/api/v1/current" and response.status == 200:
                CurrentResponse.model_validate_json(raw)
            return response.status, parsed
        finally:
            connection.close()

    def stage(self, data: Document | bytes | None = None) -> Document:
        raw = (
            encoded(document())
            if data is None
            else encoded(data)
            if isinstance(data, dict)
            else data
        )
        status, preview = self.request("/api/v1/previews", "POST", raw)
        assert status == 200
        assert preview["receipt"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert preview["receipt"]["byte_length"] == len(raw)
        assert not preview["planning_ready"]
        return preview

    def commit(
        self, identity: str, key: str = "command", generation: int = 0
    ) -> tuple[int, Document]:
        return self.request(
            "/api/v1/commit",
            "POST",
            {
                "schema_version": API_VERSION,
                "preview_sha256": identity,
                "command_key": key,
                "expected_generation": generation,
            },
        )

    def current(self) -> Document:
        status, current = self.request("/api/v1/current")
        assert status == 200
        return current

    def counts(self) -> tuple[int, ...]:
        with closing(sqlite3.connect(self.root / DATABASE_NAME)) as connection:
            return tuple(
                connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in (
                    "import_previews",
                    "checkpoints",
                    "import_activations",
                    "import_commands",
                )
            )


@contextmanager
def running(root: Path, *, port: int = 0, fault: bool = False) -> Iterator[API]:
    if fault:
        code = (
            "import sys; from pathlib import Path; import prosper.imports as module; "
            "from prosper.persistence import PersistenceError; "
            "from prosper.evidence import RuntimeBoundary; from prosper.local_api import serve; "
            "exec('def fail(connection):\\n "
            'raise PersistenceError("synthetic_transaction_failure")\'); '
            "module._before_activation_commit=fail; "
            "serve(runtime=RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'))"
        )
        command = [sys.executable, "-I", "-c", code, str(root), str(SOURCE)]
    else:
        command = [
            sys.executable,
            "-I",
            "-m",
            "prosper.local_api",
            "--port",
            str(port),
            "--synthetic-runtime",
            str(root),
            "--source-root",
            str(SOURCE),
        ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "FASTAPI_OTEL_AUTO_CONFIGURE": "true"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    output = process.stdout
    messages: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: messages.put(output.readline()), daemon=True).start()
    api: API | None = None
    try:
        line = messages.get(timeout=12)
        origin: str = json.loads(line)["origin"]
        api = API(process, origin, int(origin.rsplit(":", 1)[1]), root)
        status, session = api.request(
            "/session", "POST", headers={"X-Prosper-Bootstrap": "1"}, authorized=False
        )
        assert status == 200
        api.token = session["token"]
        yield api
    finally:
        if process.poll() is None:
            if api:
                api.request("/shutdown", "POST")
                process.wait(timeout=8)
            else:
                process.terminate()
        stdout, stderr = process.communicate(timeout=8)
        assert process.returncode == 0
        assert stdout == stderr == ""


@pytest.fixture
def api(tmp_path: Path) -> Iterator[API]:
    with running(tmp_path / "runtime") as instance:
        yield instance


def test_f001_raw_source_exact_unknown_lifecycle_and_retry(api: API) -> None:
    assert api.current() == {
        "schema_version": API_VERSION,
        "generation": 0,
        "checkpoint": None,
        "planning_ready": False,
    }
    data = document()
    data["positions"][0]["quantity"]["value"] = "00012.0000"
    preview = api.stage(data)
    identity = preview["receipt"]["raw_sha256"]
    assert api.counts() == (1, 0, 0, 0)
    assert preview["source"]["document"]["positions"][0]["quantity"]["value"] == "12"
    source_value = next(
        item["exact"]
        for item in preview["source"]["source_values"]
        if item["path"] == ["positions", 0, "quantity", "value"]
    )
    assert source_value == {
        "state": "known",
        "value": "12",
        "original_text": "00012.0000",
        "source_quantum": "0.0001",
    }
    inspection = preview["inspection"]
    assert inspection["inspection_valid"]
    assert not inspection["readiness"]["planning_ready"]
    assert [p["quantity"]["value"] for p in inspection["positions"]] == ["12", "5"]
    assert inspection["cash"][0]["settled"]["value"] == "319"
    assert inspection["settled_cash_nav"]["value"] == "2399"
    assert inspection["total_basis"]["value"] == "2181"
    assert inspection["market_minus_basis"]["value"] == "-101"
    assert "raw_bytes" not in json.dumps(preview) and "relative_reference" not in preview["receipt"]
    assert api.stage(data) == preview
    assert api.request("/api/v1/previews/" + identity) == (200, preview)
    status, receipt = api.commit(identity, "first", 0)
    assert status == 200 and receipt["outcome"] == "committed" and receipt["generation"] == 1
    assert api.commit(identity, "first", 0) == (200, receipt)
    assert api.counts() == (1, 1, 1, 1)
    current = api.current()
    assert current["generation"] == 1
    assert current["checkpoint"]["inspection"] == inspection
    assert api.stage(data)["state"] == "committed"
    assert (
        api.request(
            "/api/v1/reject", "POST", {"schema_version": API_VERSION, "preview_sha256": identity}
        )[0]
        == 409
    )
    assert api.commit(identity, "duplicate", 1)[1]["outcome"] == "duplicate"
    assert api.commit(identity, "stale", 0)[1]["outcome"] == "stale_generation"
    assert api.commit(identity, "first", 1)[0] == 409
    assert api.current() == current


@pytest.mark.parametrize(
    "kind", ["F002", "F003", "F004", "F006", "F009", "unknown-schema", "float"]
)
def test_foundation_variants_preserve_unknowns_and_invalidity(api: API, kind: str) -> None:
    data = document()
    if kind == "F002":
        data["metadata"]["inclusion"] = {"value": None, "reason": "not_proven"}
    elif kind == "F003":
        data["lots"][0]["quantity"]["value"] = "11"
    elif kind == "F004":
        data["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    elif kind == "F006":
        data["quotes"][0]["price"]["value"] = "0.1000000000001"
    elif kind == "F009":
        data["coverage"][0]["status"] = "unknown"
        data["coverage"][0]["evidence"] = {"value": None, "reason": "coverage_unknown"}
    elif kind == "float":
        data["positions"][0]["quantity"]["value"] = 12.0
    else:
        data["metadata"]["schema_version"] = "future-schema"
    preview = api.stage(data)
    identity = preview["receipt"]["raw_sha256"]
    status, receipt = api.commit(identity)
    assert status == 200
    if kind in ("F004", "F009"):
        assert receipt["outcome"] == "committed"
        current = api.current()["checkpoint"]
        assert not current["inspection"]["readiness"]["planning_ready"]
        if kind == "F004":
            assert current["inspection"]["total_basis"] == {
                "state": "unknown",
                "value": None,
                "reasons": ["source_missing"],
            }
            assert current["source"]["document"]["lots"][1]["basis"] == {
                "value": None,
                "reason": "source_missing",
            }
        else:
            assert current["inspection"]["readiness"]["coverage"] == "incomplete"
    else:
        assert receipt["outcome"] == "preview_invalid" and api.current()["generation"] == 0
        assert api.counts() == (1, 0, 0, 1)
        if kind in ("F006", "unknown-schema", "float"):
            assert preview["source"] is None and preview["issues"]
        else:
            assert preview["inspection"]["findings"]


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"\xff",
        b'{"metadata":{},"metadata":{}}',
        b'{"unknown_field":"synthetic-payload-marker"}',
    ],
)
def test_malformed_bytes_are_durable_non_ready_evidence(api: API, raw: bytes) -> None:
    preview = api.stage(raw)
    assert preview["source"] is None and preview["issues"] and not preview["inspection"]
    identity = preview["receipt"]["raw_sha256"]
    assert api.stage(raw) == preview
    status, rejected = api.request(
        "/api/v1/reject", "POST", {"schema_version": API_VERSION, "preview_sha256": identity}
    )
    assert status == 200 and rejected["state"] == "rejected" and rejected["rejected_at"]
    assert api.stage(raw) == rejected
    assert api.commit(identity)[1]["outcome"] == "preview_rejected"
    assert api.current()["generation"] == 0


def test_f005_conflict_and_safe_imported_text(api: API) -> None:
    base = document()
    base["accounts"][0]["alias"] = "<script>synthetic-no-execution()</script>"
    first = api.stage(base)
    assert api.commit(first["receipt"]["raw_sha256"])[1]["outcome"] == "committed"
    before = api.current()
    changed = copy.deepcopy(base)
    changed["metadata"]["source_version"] = "changed-source"
    changed["activity"][0]["fees"]["value"] = "2"
    changed["activity"][0]["cash_movement"]["value"] = "-182"
    preview = api.stage(changed)
    assert preview["inspection"]["inspection_valid"]
    assert (
        api.commit(preview["receipt"]["raw_sha256"], "conflict", 1)[1]["outcome"]
        == "source_conflict"
    )
    assert api.current() == before
    assert (
        before["checkpoint"]["source"]["document"]["accounts"][0]["alias"]
        == base["accounts"][0]["alias"]
    )


def test_oversized_error_field_location_reports_truncation_without_losing_evidence(
    api: API,
) -> None:
    raw = b'{"' + b"synthetic-field-" * 30 + b'":1}'
    preview = api.stage(raw)
    assert any(issue["path_truncated"] for issue in preview["issues"])
    assert all(
        len(part) <= 128
        for issue in preview["issues"]
        for part in issue["path"]
        if isinstance(part, str)
    )
    identity = preview["receipt"]["raw_sha256"]
    assert (api.root / "evidence-bytes-v1" / "objects" / (identity + ".bin")).read_bytes() == raw


@pytest.mark.parametrize(
    "change",
    ["extra", "version", "missing", "bool", "float", "negative", "huge", "key", "identity"],
)
def test_closed_control_requests_do_not_write(api: API, change: str) -> None:
    identity = api.stage()["receipt"]["raw_sha256"]
    command: Document = {
        "schema_version": API_VERSION,
        "preview_sha256": identity,
        "command_key": "valid",
        "expected_generation": 0,
    }
    if change == "extra":
        command["synthetic-secret-marker"] = "not-to-be-echoed"
    elif change == "version":
        command["schema_version"] = "future"
    elif change == "missing":
        del command["schema_version"]
    elif change in ("bool", "float", "negative", "huge"):
        command["expected_generation"] = {
            "bool": True,
            "float": 0.0,
            "negative": -1,
            "huge": 2**63,
        }[change]
    elif change == "key":
        command["command_key"] = "../../synthetic-secret-marker"
    else:
        command["preview_sha256"] = "../../synthetic-secret-marker"
    status, error = api.request("/api/v1/commit", "POST", command)
    assert status == 422 and error["error"] == "request_invalid" and error["issues"]
    assert "synthetic-secret-marker" not in json.dumps(error)
    assert "not-to-be-echoed" not in json.dumps(error)
    assert api.counts() == (1, 0, 0, 0)


def test_control_json_media_depth_limits_and_missing_identity(api: API) -> None:
    identity = api.stage()["receipt"]["raw_sha256"]
    for raw in (
        b'{"schema_version":"x","schema_version":"y"}',
        b'{"x":NaN}',
        b"{",
    ):
        status, error = api.request(
            "/api/v1/commit", "POST", raw, {"Content-Type": "application/json"}
        )
        assert status == 400, (raw[:24], error)
    assert (
        api.request(
            "/api/v1/commit",
            "POST",
            b"[" * 1500 + b"]" * 1500,
            {"Content-Type": "application/json"},
        )[0]
        == 422
    )
    assert (
        api.request("/api/v1/commit", "POST", b"x" * 4097, {"Content-Type": "application/json"})[0]
        == 413
    )
    assert (
        api.request(
            "/api/v1/previews", "POST", encoded(document()), {"Content-Type": "application/json"}
        )[0]
        == 415
    )
    assert (
        api.request(
            "/api/v1/previews",
            "POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(2 * 1024 * 1024 + 1),
            },
        )[0]
        == 413
    )
    # A sender continuing a full oversized upload after early rejection can observe a
    # Windows TCP reset instead of the already-sent 413; either way no evidence is stored.
    try:
        assert api.request("/api/v1/previews", "POST", b"x" * (2 * 1024 * 1024 + 1))[0] == 413
    except (ConnectionResetError, BrokenPipeError):
        pass
    assert api.request("/api/v1/previews/not-a-digest")[0] == 422
    missing = "0" * 64
    assert api.request("/api/v1/previews/" + missing)[0] == 404
    assert api.commit(missing)[0] == 404
    assert (
        api.request(
            "/api/v1/reject", "POST", {"schema_version": API_VERSION, "preview_sha256": missing}
        )[0]
        == 404
    )
    assert api.counts() == (1, 0, 0, 0)
    assert api.commit(identity)[1]["outcome"] == "committed"


@pytest.mark.parametrize(
    "denial", ["origin", "host", "missing-origin", "missing-session", "wrong-session"]
)
def test_each_financial_route_and_schema_denies_before_read_or_mutation(
    api: API, denial: str
) -> None:
    identity = api.stage()["receipt"]["raw_sha256"]
    denial_headers: dict[str, dict[str, str | None]] = {
        "origin": {"Origin": "https://evil.example"},
        "host": {"Host": "evil.example"},
        "missing-origin": {"Origin": None},
        "missing-session": {"Authorization": None},
        "wrong-session": {"Authorization": "Bearer synthetic-wrong"},
    }
    headers = denial_headers[denial]
    command = {
        "schema_version": API_VERSION,
        "preview_sha256": identity,
        "command_key": "denied",
        "expected_generation": 0,
    }
    before = api.counts()
    for path, method, data in (
        ("/api/v1/current", "GET", None),
        ("/api/v1/previews/" + identity, "GET", None),
        ("/api/v1/previews", "POST", encoded(document())),
        ("/api/v1/commit", "POST", command),
        ("/api/v1/reject", "POST", {"schema_version": API_VERSION, "preview_sha256": identity}),
        ("/openapi.json", "GET", None),
    ):
        status, response = api.request(path, method, data, headers)
        assert status in (401, 403)
        assert set(response) == {"error"}
    assert api.counts() == before and api.current()["generation"] == 0


def test_openapi_actual_closed_schema_and_decimal_string_contract(api: API) -> None:
    status, schema = api.request("/openapi.json")
    assert status == 200
    expected = {
        "/api/v1/previews",
        "/api/v1/previews/{identity}",
        "/api/v1/current",
        "/api/v1/commit",
        "/api/v1/reject",
    }
    assert expected <= schema["paths"].keys()
    for path in expected:
        operation = next(iter(schema["paths"][path].values()))
        assert operation["security"] == [{"HTTPBearer": []}]
    models = schema["components"]["schemas"]
    for name in (
        "CommitRequest",
        "RejectRequest",
        "PreviewResponse",
        "CurrentResponse",
        "CommandResponse",
        "KnownValue",
        "UnknownValue",
        "BundleDocument",
        "Metadata",
    ):
        assert models[name]["additionalProperties"] is False
    assert models["KnownValue"]["properties"]["value"]["type"] == "string"
    assert models["UnknownValue"]["properties"]["value"]["type"] == "null"
    assert set(models["CommandResponse"]["properties"]["outcome"]["enum"]) == OUTCOMES
    assert "schema_version" in models["CommitRequest"]["required"]
    request_body = schema["paths"]["/api/v1/previews"]["post"]["requestBody"]["content"]
    assert set(request_body) == {"application/octet-stream"}
    upload_schema = request_body["application/octet-stream"]["schema"]
    assert upload_schema["type"] == "string"
    assert upload_schema["contentMediaType"] == "application/octet-stream"
    assert upload_schema.get("contentEncoding") != "base64"


def test_f008_two_http_windows_and_same_key_retry(api: API) -> None:
    first = api.stage()["receipt"]["raw_sha256"]
    data = document()
    data["metadata"]["source_version"] = "second"
    second = api.stage(data)["receipt"]["raw_sha256"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(api.commit, identity, key, 0)
            for identity, key in ((first, "window-a"), (second, "window-b"))
        ]
        results = [future.result() for future in futures]
    assert all(status == 200 for status, _ in results)
    assert sorted(r["outcome"] for _, r in results) == ["committed", "stale_generation"]
    assert api.counts() == (2, 1, 1, 2)
    winning = next(r for _, r in results if r["outcome"] == "committed")
    with ThreadPoolExecutor(max_workers=2) as executor:
        retries = list(
            executor.map(
                lambda _: api.commit(winning["preview_sha256"], winning["command_key"], 0), range(2)
            )
        )
    assert retries == [(200, winning), (200, winning)]
    assert api.counts() == (2, 1, 1, 2)


def test_restart_preserves_receipt_and_current_but_not_token(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    with running(root) as api:
        identity = api.stage()["receipt"]["raw_sha256"]
        receipt = api.commit(identity, "restart", 0)
        current = api.current()
        token, port = api.token, api.port
    with running(root, port=port) as api:
        assert (
            api.request("/api/v1/current", headers={"Authorization": "Bearer " + token})[0] == 401
        )
        assert api.current() == current
        assert api.commit(identity, "restart", 0) == receipt


def test_historical_retry_and_raw_noop_never_restore_older_active_checkpoint(api: API) -> None:
    first = api.stage()["receipt"]["raw_sha256"]
    original = api.commit(first, "first", 0)
    data = document()
    data["metadata"]["source_version"] = "later-version"
    second = api.stage(data)["receipt"]["raw_sha256"]
    assert api.commit(second, "second", 1)[1]["outcome"] == "committed"
    assert api.commit(second, "first", 0)[0] == 409
    assert api.commit(first, "first", 0) == original
    duplicate = api.commit(first, "historical-noop", 2)[1]
    assert duplicate["outcome"] == "duplicate"
    assert duplicate["activation_generation"] == 1 and duplicate["generation"] == 2
    assert api.current()["checkpoint"]["receipt"]["raw_sha256"] == second
    assert api.counts() == (2, 2, 2, 3)


def test_chunked_preview_preserves_bytes_and_stream_limit_prevents_publication(api: API) -> None:
    raw = encoded(document())

    def stream(chunks: Iterator[bytes]) -> tuple[int, Document]:
        connection = http.client.HTTPConnection("127.0.0.1", api.port, timeout=12)
        try:
            connection.request(
                "POST",
                "/api/v1/previews",
                body=chunks,
                encode_chunked=True,
                headers={
                    "Origin": api.origin,
                    "Authorization": "Bearer " + api.token,
                    "Content-Type": "application/octet-stream",
                },
            )
            response = connection.getresponse()
            return response.status, cast(Document, json.loads(response.read()))
        finally:
            connection.close()

    status, preview = stream(iter((raw[:71], raw[71:])))
    assert status == 200 and preview["receipt"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert api.counts() == (1, 0, 0, 0)
    try:
        assert stream(b"x" * 65536 for _ in range(33))[0] == 413
    except (ConnectionResetError, BrokenPipeError):
        pass
    assert api.counts() == (1, 0, 0, 0) and api.current()["generation"] == 0


def test_f007_http_failure_rolls_back_then_fresh_process_retries(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    with running(root) as api:
        base = api.stage()["receipt"]["raw_sha256"]
        api.commit(base, "base", 0)
        current = api.current()
    with running(root, fault=True) as api:
        data = document()
        data["metadata"]["source_version"] = "rollback"
        identity = api.stage(data)["receipt"]["raw_sha256"]
        assert api.commit(identity, "retry", 1) == (
            503,
            {"error": "synthetic_transaction_failure", "issues": [], "further_issues": False},
        )
        assert api.current() == current and api.counts() == (2, 1, 1, 1)
    with running(root) as api:
        assert api.commit(identity, "retry", 1)[1]["outcome"] == "committed"
        assert api.current()["generation"] == 2


def test_corrupt_required_evidence_is_safe_error_without_silent_repair(api: API) -> None:
    identity = api.stage()["receipt"]["raw_sha256"]
    api.commit(identity)
    evidence = api.root / "evidence-bytes-v1" / "objects" / (identity + ".bin")
    evidence.write_bytes(b"synthetic-corrupt-marker")
    for path in ("/api/v1/current", "/api/v1/previews/" + identity):
        status, error = api.request(path)
        assert status == 503
        assert "synthetic-corrupt-marker" not in json.dumps(error)
        assert str(api.root) not in json.dumps(error)
        assert api.request(path, authorized=False)[0] == 401
    assert api.request("/api/v1/previews", "POST", encoded(document()))[0] == 503
    assert evidence.read_bytes() == b"synthetic-corrupt-marker"
    assert api.counts() == (1, 1, 1, 1)


def test_launcher_requires_explicit_synthetic_boundary_and_no_runtime_from_http(
    tmp_path: Path,
) -> None:
    for args in (
        ("--synthetic-runtime", str(tmp_path / "one")),
        ("--source-root", str(SOURCE)),
        ("--synthetic-runtime", str(SOURCE / "forbidden-runtime"), "--source-root", str(SOURCE)),
    ):
        result = subprocess.run(
            [sys.executable, "-I", "-m", "prosper.local_api", *args],
            capture_output=True,
            text=True,
            timeout=12,
        )
        assert result.returncode == 2 and result.stdout == ""
        assert result.stderr == "local_runtime_start_failed\n"
    assert not (SOURCE / "forbidden-runtime").exists()
    # Library-only private mode remains outside this synthetic HTTP launcher's scope.
    other_source = tmp_path / "other-source"
    other_source.mkdir()
    private = RuntimeBoundary(tmp_path / "private", other_source, "private")
    with pytest.raises(ValueError, match="synthetic_runtime_required"):
        serve(runtime=private)
    assert not private.root.exists()
