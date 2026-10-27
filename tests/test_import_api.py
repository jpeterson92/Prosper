"""Actual protected HTTP process over the current advisory SQLite authority."""

import base64
import http.client
import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

SOURCE = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]


def document() -> Document:
    return cast(
        Document, json.loads((SOURCE / "examples/synthetic/advisory-workspace.json").read_bytes())
    )


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
        body = json.dumps(data).encode() if isinstance(data, dict) else data
        if data is not None:
            request_headers["Content-Type"] = (
                "application/json" if isinstance(data, dict) else "application/octet-stream"
            )
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
            assert response.getheader("cache-control") == "no-store"
            assert response.getheader("x-content-type-options") == "nosniff"
            return response.status, cast(Document, json.loads(raw))
        finally:
            connection.close()

    def stage(self, data: Document | None = None) -> Document:
        status, result = self.request(
            "/api/v1/previews", "POST", document() if data is None else data
        )
        assert status == 200
        return result

    def select(self, identity: str, key: str = "first", revision: int = 0) -> tuple[int, Document]:
        return self.request(
            "/api/v1/select",
            "POST",
            {"snapshot_id": identity, "command_key": key, "expected_revision": revision},
        )

    def current(self) -> Document:
        status, result = self.request("/api/v1/current")
        assert status == 200
        return result


@contextmanager
def running(root: Path, *, port: int = 0, fault: bool = False) -> Iterator[API]:
    if fault:
        code = (
            "import sys; from pathlib import Path; import prosper.advisory_store as module; "
            "from prosper.storage import PersistenceError; "
            "from prosper.storage import RuntimeBoundary; from prosper.local_api import serve; "
            "exec('def fail(connection):\\n "
            'raise PersistenceError("synthetic_transaction_failure")\'); '
            "module._before_commit=fail; "
            "serve(runtime=RuntimeBoundary(Path(sys.argv[1])))"
        )
        command = [sys.executable, "-I", "-c", code, str(root), str(SOURCE)]
    else:
        initialize = not root.exists()
        command = [
            sys.executable,
            "-I",
            "-m",
            "prosper.local_api",
            "--port",
            str(port),
            "--runtime",
            str(root),
        ]
        if initialize:
            command.append("--initialize")
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


def test_normalized_preview_selection_settings_diagnostics_restart(api: API) -> None:
    assert api.current() == {
        "revision": 0,
        "snapshot_id": None,
        "settings": {},
        "current_run_id": None,
    }
    preview = api.stage()
    identity = preview["id"]
    assert api.current()["snapshot_id"] is None
    assert preview["snapshot"]["lots"][0]["quantity"]["value"] == "12.5000"
    assert preview["snapshot"]["lots"][0]["total_basis"] == {
        "value": None,
        "reason": "basis not supplied",
    }
    assert api.select(identity) == (200, {"outcome": "changed", "revision": 1})
    # A response lost by the caller can be replayed without another selection.
    assert api.select(identity) == (200, {"outcome": "changed", "revision": 1})
    settings = {
        "settings": {"additional_cash": "100.00", "risk_enabled": False},
        "command_key": "settings",
        "expected_revision": 1,
    }
    assert api.request("/api/v1/settings", "POST", settings) == (
        200,
        {"outcome": "changed", "revision": 2},
    )
    command = {
        "run_id": "source-diagnostic",
        "expected_revision": 2,
        "as_of": "2026-10-25T20:00:00Z",
    }
    status, run = api.request("/api/v1/diagnostics", "POST", command)
    assert status == 200 and run["status"] == "partial"
    assert run["outputs"]["counts"] == {"securities": 1, "lots": 1, "positions": 1, "cash": 0}
    assert run["outputs"]["financial_metrics"] is None
    assert any(f["locator"] == "lots/lot-a/total_basis" for f in run["outputs"]["findings"])
    assert run["exclusions"][0]["code"] == "unsupported_tax_class"
    assert api.request("/api/v1/diagnostics", "POST", command) == (200, run)
    assert api.request("/api/v1/runs/source-diagnostic") == (200, run)
    assert api.current()["current_run_id"] == "source-diagnostic"
    assert (
        api.request(
            "/api/v1/settings",
            "POST",
            {**settings, "command_key": "later", "expected_revision": 2, "settings": {}},
        )[0]
        == 200
    )
    assert api.current()["current_run_id"] is None
    assert api.request("/api/v1/runs/source-diagnostic") == (200, run)
    with running(api.root) as reopened:
        assert reopened.current() == api.current()
        assert reopened.request("/api/v1/runs/source-diagnostic") == (200, run)


def test_replacement_errors_unknowns_and_two_window_stale_commands(api: API) -> None:
    identity = api.stage()["id"]
    api.select(identity)
    before = api.current()
    wrong = document()
    wrong["snapshot"]["source_sha256"] = "0" * 64
    assert api.request("/api/v1/previews", "POST", wrong)[0] == 422
    assert api.current() == before
    assert api.select(identity, "stale-window", 0) == (
        200,
        {"outcome": "stale_revision", "revision": 1},
    )
    assert api.select(identity, "first", 1)[0] == 409
    other = document()
    other["snapshot"]["account_id"] = "other"
    for group in ("lots", "positions"):
        other["snapshot"][group][0]["account_id"] = "other"
    second = api.stage(other)["id"]
    assert api.select(second, "other-account", 1)[1]["outcome"] == "account_review_required"
    assert api.current() == before
    assert api.request("/api/v1/reject", "POST", {"snapshot_id": second})[0] == 200
    assert api.select(second, "rejected", 1)[1]["outcome"] == "preview_rejected"
    assert api.request("/api/v1/reject", "POST", {"snapshot_id": identity})[0] == 409


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/current",
        "/api/v1/catalog",
        "/api/v1/backup",
        "/api/v1/runs/x",
        "/api/v1/input-records/x",
        "/api/v1/benchmarks/observations/x",
        "/api/v1/benchmarks/observations/x/source",
    ],
)
def test_current_routes_require_session(api: API, path: str) -> None:
    assert api.request(path, authorized=False)[0] == 401
    assert api.request(path, headers={"Origin": "https://foreign.invalid"})[0] == 403


def test_benchmark_review_selection_retries_and_safe_malformed_inputs(api: API) -> None:
    folder = SOURCE / "examples/synthetic/benchmark"
    observation = json.loads((folder / "current-observation.json").read_bytes())
    review = json.loads((folder / "current-review.json").read_bytes())
    preview = api.stage()
    assert api.select(preview["id"])[0] == 200
    assert api.request("/api/v1/benchmarks/import", "POST", observation)[0] == 200
    assert (
        api.request("/api/v1/benchmarks/review", "POST", review)[1]["status"]
        == "estimated-equity-benchmark"
    )
    command = {
        "run_id": "proxy",
        "expected_revision": 1,
        "as_of": "2026-10-25T22:00:00Z",
        "review": review,
    }
    status, run = api.request("/api/v1/benchmarks/diagnostics", "POST", command)
    assert status == 200 and run["outputs"]["source_row_count"] == 8
    assert "metadata_base64" not in run["inputs"]["benchmark_request"]["review"]
    assert api.request("/api/v1/benchmarks/diagnostics", "POST", command) == (status, run)
    choose = {"run_id": "proxy", "command_key": "choose-proxy", "expected_revision": 1}
    assert api.request("/api/v1/benchmarks/select", "POST", choose)[1] == {
        "outcome": "changed",
        "revision": 2,
    }
    assert api.request("/api/v1/benchmarks/select", "POST", choose)[1] == {
        "outcome": "changed",
        "revision": 2,
    }
    assert api.current()["settings"]["benchmark_run_id"] == "proxy"
    for route in ("fetch", "import", "review", "diagnostics", "select"):
        assert api.request(f"/api/v1/benchmarks/{route}", "POST", {}, authorized=False)[0] == 401
    for route, body in (
        ("import", {**observation, "source_base64": "!"}),
        ("diagnostics", {**command, "review": {**review, "metadata_base64": "!"}}),
    ):
        assert api.request(f"/api/v1/benchmarks/{route}", "POST", body)[0] == 422
    status, error = api.request("/api/v1/benchmarks/review", "POST", {"PRIVATE-KEY": "DO-NOT-ECHO"})
    assert (
        status == 422
        and "PRIVATE-KEY" not in json.dumps(error)
        and "DO-NOT-ECHO" not in json.dumps(error)
    )


def test_modeled_inputs_protected_preview_saved_diagnostic_and_retry(api: API) -> None:
    staged = api.stage()
    assert api.select(staged["id"])[0] == 200
    folder = SOURCE / "examples/synthetic/modeled-inputs"
    upload = json.loads((folder / "current.json").read_bytes())
    status, result = api.request("/api/v1/inputs/preview", "POST", upload)
    assert status == 200 and result["software_inputs_complete"] is False
    assert "selected_benchmark_required" in {i["code"] for i in result["issues"]}
    request = {
        **upload,
        "run_id": "inputs",
        "expected_revision": 1,
        "as_of": "2026-10-25T22:00:00Z",
    }
    status, run = api.request("/api/v1/inputs/diagnostics", "POST", request)
    assert status == 200 and run["outputs"]["risk_available"] is False
    assert api.request("/api/v1/inputs/diagnostics", "POST", request) == (status, run)
    for route in ("preview", "diagnostics"):
        assert api.request(f"/api/v1/inputs/{route}", "POST", {}, authorized=False)[0] == 401
        status, error = api.request(
            f"/api/v1/inputs/{route}", "POST", {"PRIVATE-KEY": "DO-NOT-ECHO"}
        )
        assert (
            status == 422
            and "PRIVATE-KEY" not in json.dumps(error)
            and "DO-NOT-ECHO" not in json.dumps(error)
        )
    broken = json.loads(json.dumps(upload))
    broken["sources"][0]["source_base64"] = "!"
    assert api.request("/api/v1/inputs/preview", "POST", broken)[0] == 422


def test_closed_request_size_duplicate_keys_and_safe_errors(api: API) -> None:
    bad = document()
    bad["secret-account-value"] = "DO-NOT-ECHO"
    status, result = api.request("/api/v1/previews", "POST", bad)
    assert (
        status == 422
        and "DO-NOT-ECHO" not in json.dumps(result)
        and "secret-account-value" not in json.dumps(result)
    )
    assert (
        api.request(
            "/api/v1/previews",
            "POST",
            b'{"version":"a","version":"b"}',
            {"Content-Type": "application/json"},
        )[0]
        == 400
    )
    assert (
        api.request(
            "/api/v1/settings",
            "POST",
            b'{"settings":{"x":NaN}}',
            {"Content-Type": "application/json"},
        )[0]
        == 400
    )
    assert (
        api.request(
            "/api/v1/previews",
            "POST",
            b"",
            {"Content-Type": "application/json", "Content-Length": str(2 * 1024 * 1024 + 1)},
        )[0]
        == 413
    )
    assert api.request("/api/v1/previews", "POST", b"wrong-media")[0] == 415
    assert api.request("/api/v1/commit", "POST")[0] == 404


def test_decimal_shape_error_retains_safe_row_locator(api: API) -> None:
    wrong = document()
    wrong["snapshot"]["lots"][0]["quantity"]["value"] = 12.5
    code, result = api.request("/api/v1/previews", "POST", wrong)
    assert code == 422
    assert result["issues"][0]["path"] == ["body", "snapshot", "lots", 0, "quantity", "value"]
    assert "12.5" not in json.dumps(result)


def lots_seed(api: API) -> dict[str, Any]:
    raw = (SOURCE / "examples/synthetic/fidelity/combined-stocks.csv").read_bytes()
    body = {
        "source_base64": base64.b64encode(raw).decode(),
        "context": json.loads(
            (SOURCE / "examples/synthetic/fidelity/current-context.json").read_bytes()
        ),
    }
    status, staged = api.request("/api/v1/fidelity/previews", "POST", body)
    assert status == 200 and staged["preview"]
    preview: dict[str, Any] = staged["preview"]
    assert api.select(preview["id"])[1]["revision"] == 1
    cfg = {
        "settings": json.loads(
            (SOURCE / "examples/synthetic/fidelity/current-lot-settings.json").read_bytes()
        ),
        "command_key": "lot-settings",
        "expected_revision": 1,
    }
    status, result = api.request("/api/v1/lots/settings", "POST", cfg)
    assert status == 200 and result["revision"] == 2
    assert api.request("/api/v1/lots/settings", "POST", cfg) == (status, result)
    return preview


def test_protected_lot_routes_empty_json_arrays_retries_and_stale_windows(api: API) -> None:
    lots_seed(api)
    command = {
        "run_id": "first",
        "expected_revision": 2,
        "as_of": "2026-10-25T00:00:00Z",
        "sale_quantities": {},
        "replacement_security_ids": [],
    }
    status, saved = api.request("/api/v1/lots/diagnostics", "POST", command)
    assert status == 200 and saved["outputs"]["conditional_price_loss_subtotal"]["value"] == 10
    assert api.request("/api/v1/lots/diagnostics", "POST", command) == (200, saved)
    assert api.request("/api/v1/lots/results/first") == (200, saved["outputs"])
    assert api.request("/api/v1/lots/diagnostics", "POST", command, authorized=False)[0] == 401
    changed = {
        "settings": json.loads(
            (SOURCE / "examples/synthetic/fidelity/current-lot-settings.json").read_bytes()
        ),
        "command_key": "change",
        "expected_revision": 2,
    }
    changed["settings"]["cash_to_invest"] = "3"
    assert api.request("/api/v1/lots/settings", "POST", changed)[1]["revision"] == 3
    assert api.current()["current_run_id"] is None
    assert api.request("/api/v1/lots/diagnostics", "POST", command) == (200, saved)
    assert api.request("/api/v1/lots/diagnostics", "POST", {**command, "run_id": "stale"})[0] == 409
    before_stale = api.current()
    assert api.request(
        "/api/v1/lots/settings",
        "POST",
        {
            **changed,
            "command_key": "stale",
            "settings": {**changed["settings"], "cash_to_invest": "7"},
        },
    ) == (200, {"outcome": "stale_revision", "revision": 3})
    assert api.current() == before_stale

    assert (
        api.request("/api/v1/lots/diagnostics", "POST", {**command, "sale_quantities": {"x": 1}})[0]
        == 409
    )


@pytest.mark.parametrize("change", ["unknown-lot", "future", "fraction", "boolean", "id-type"])
def test_invalid_lot_command_cannot_create_a_run_or_clear_work(api: API, change: str) -> None:
    lots_seed(api)
    command: dict[str, Any] = {
        "run_id": "invalid",
        "expected_revision": 2,
        "as_of": "2026-10-25T00:00:00Z",
    }
    if change == "unknown-lot":
        command["sale_quantities"] = {"not-held": 1}
    elif change == "future":
        command["as_of"] = "2020-01-01T00:00:00Z"
    elif change in ("fraction", "boolean"):
        command["sale_quantities"] = {"x": 1.5 if change == "fraction" else True}
    else:
        command["replacement_security_ids"] = [1]
    before = api.current()
    assert api.request("/api/v1/lots/diagnostics", "POST", command)[0] == 422
    assert api.current() == before
    assert api.request("/api/v1/catalog")[1]["runs"] == []


def test_invalid_source_and_settings_are_sanitized_without_replacement(api: API) -> None:
    lots_seed(api)
    before = api.current()
    bad = {
        "settings": {
            **json.loads(
                (SOURCE / "examples/synthetic/fidelity/current-lot-settings.json").read_bytes()
            ),
            "cash_to_invest": -1,
        },
        "command_key": "invalid",
        "expected_revision": 2,
    }
    status, refused = api.request("/api/v1/lots/settings", "POST", bad)
    assert status == 422 and "-1" not in json.dumps(refused)
    raw = (SOURCE / "examples/synthetic/fidelity/combined-stocks.csv").read_bytes()
    bad_source = {
        "source_base64": base64.b64encode(raw + b"\n").decode(),
        "context": json.loads(
            (SOURCE / "examples/synthetic/fidelity/current-context.json").read_bytes()
        ),
    }
    assert api.request("/api/v1/fidelity/previews", "POST", bad_source)[0] == 422
    duplicate = b'{"settings":{"private-key":"do-not-echo","private-key":2}}'
    status, refused = api.request(
        "/api/v1/lots/settings/preview", "POST", duplicate, {"Content-Type": "application/json"}
    )
    assert status == 400 and "do-not-echo" not in json.dumps(refused)
    assert api.current() == before


@pytest.mark.parametrize("reserved", ["screening", "lot_context"])
def test_invalid_reserved_lot_facts_are_refused_before_staging(api: API, reserved: str) -> None:
    before = api.current()
    invalid = document()
    invalid["snapshot"]["observations"][reserved] = {"private-key": "do-not-echo"}
    status, refused = api.request("/api/v1/previews", "POST", invalid)
    assert status == 422 and "do-not-echo" not in json.dumps(refused)
    assert api.current() == before and api.request("/api/v1/catalog")[1]["snapshots"] == []


def test_removed_data_category_is_not_an_api_field(api: API) -> None:
    value = document()
    assert "fictional" not in value["snapshot"]
    before = api.current()
    value["snapshot"]["fictional"] = "do-not-echo"
    status, error = api.request("/api/v1/previews", "POST", value)
    assert status == 422 and "do-not-echo" not in json.dumps(error)
    assert api.current() == before
