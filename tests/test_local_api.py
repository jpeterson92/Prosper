"""Real HTTP/process expectations; no TestClient or mocked HTTP server."""

import http.client
import json
import os
import queue
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from prosper.local_api import MAX_BODY_BYTES, LocalPolicy
from prosper.web_assets import CONTENT_POLICY, MAX_ASSET_BYTES, WebAssets


def build_fixture(root: Path) -> Path:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(b"<!doctype html><title>Synthetic probe</title>")
    (root / "assets" / "index-demo.js").write_bytes(b"export const synthetic = true;")
    return root


def test_asset_snapshot_stays_immutable(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "dist")
    assets = WebAssets.load(root)
    (root / "assets" / "index-demo.js").write_bytes(b"changed")
    assert assets.files["/assets/index-demo.js"][0] == b"export const synthetic = true;"
    assert set(assets.files) == {"/", "/assets/index-demo.js"}


@pytest.mark.parametrize("name", ["secret.json", "runtime.sqlite", "source.js.map", "nested"])
def test_asset_non_build_files_refused(tmp_path: Path, name: str) -> None:
    root = build_fixture(tmp_path / "dist")
    (root / "assets" / name).write_bytes(b"synthetic-private")
    with pytest.raises(ValueError, match="unsupported_build_asset"):
        WebAssets.load(root)


def test_asset_hardlink_refused(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "dist")
    (root / "alias.js").hardlink_to(root / "assets" / "index-demo.js")
    with pytest.raises(ValueError, match="plain_asset_required"):
        WebAssets.load(root)


def test_asset_oversize_refused(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "dist")
    (root / "assets" / "index-demo.js").write_bytes(b"x" * (MAX_ASSET_BYTES + 1))
    with pytest.raises(ValueError, match="asset_size_limit"):
        WebAssets.load(root)


def test_asset_redirected_directory_refused(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "dist")
    # Windows junctions exercise the same reparse boundary without symlink privileges.
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(tmp_path / "alias"), str(root)],
            capture_output=True,
        )
        assert result.returncode == 0
    else:
        (tmp_path / "alias").symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="redirected_asset"):
        WebAssets.load(tmp_path / "alias")


def test_real_asset_bootstrap_keeps_api_protected(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "dist")
    with runtime("--ui-dist", str(root)) as api:
        status, headers, body = api.request("GET", "/", {"Sec-Fetch-Site": "none"})
        assert status == 200 and body.startswith(b"<!doctype html>")
        assert headers["content-security-policy"] == CONTENT_POLICY
        assert headers["cache-control"] == "no-store"
        assert headers["x-content-type-options"] == "nosniff"
        status, _, body = api.request(
            "GET", "/assets/index-demo.js", {"Sec-Fetch-Site": "same-origin"}
        )
        assert status == 200 and body == b"export const synthetic = true;"
        for route in ("/session", "/diagnostic", "/runtime", "/api/v1/current", "/openapi.json"):
            status, _, _ = api.request("GET", route, {"Sec-Fetch-Site": "same-origin"})
            assert status == 401
        token = api.session()
        assert api.request("GET", "/diagnostic", api.authorized(token))[0] == 200
        for route in (
            "/assets/../index.html",
            "/assets/%2e%2e/index.html",
            "/index.html",
            "/assets/runtime.sqlite",
            "/.local/state.sqlite",
            "/assets/index-demo.js/extra",
        ):
            status, _, body = api.request("GET", route, api.authorized(token))
            assert status == 404 and b"synthetic-private" not in body
        assert api.request("GET", "/?token=blocked", api.authorized(token))[0] == 400
        assert api.request("GET", "/", {"Origin": "http://127.0.0.1:12345"})[0] == 403
        assert api.request("GET", "/", {"Origin": api.origin, "Host": "localhost"})[0] == 403
        assert api.request("POST", "/", {"Origin": api.origin})[0] == 401
        assert api.request("GET", "/", {"Origin": api.origin}, b"x")[0] == 400


@dataclass(repr=False)
class Running:
    process: subprocess.Popen[str]
    origin: str
    port: int
    tokens: list[str] = field(default_factory=list, repr=False)

    def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def session(self, origin: str | None = None) -> str:
        status, headers, body = self.request(
            "POST", "/session", {"Origin": origin or self.origin, "X-Prosper-Bootstrap": "1"}
        )
        assert status == 200
        assert headers["cache-control"] == "no-store"
        parsed = json.loads(body)
        assert set(parsed) == {"token", "token_type"}
        assert parsed["token_type"] == "Bearer"
        token: str = parsed["token"]
        assert len(token) >= 43
        self.tokens.append(token)
        return token

    def authorized(self, token: str) -> dict[str, str]:
        return {"Origin": self.origin, "Authorization": "Bearer " + token}

    def raw(self, request: bytes) -> bytes:
        with socket.create_connection(("127.0.0.1", self.port), timeout=8) as connection:
            connection.sendall(request)
            result = bytearray()
            while chunk := connection.recv(65536):
                result.extend(chunk)
            return bytes(result)


@contextmanager
def runtime(*args: str) -> Iterator[Running]:
    process = subprocess.Popen(
        [sys.executable, "-I", "-m", "prosper.local_api", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "FASTAPI_OTEL_AUTO_CONFIGURE": "true"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    output = process.stdout
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: lines.put(output.readline()), daemon=True).start()
    running: Running | None = None
    try:
        line = lines.get(timeout=12)
        parsed = json.loads(line)
        origin = parsed["origin"]
        assert set(parsed) == {"origin"}
        assert origin.startswith("http://127.0.0.1:")
        running = Running(process, origin, int(origin.rsplit(":", 1)[1]))
        # Listening socket exists before the public line; HTTP waits for Uvicorn startup.
        yield running
    finally:
        if process.poll() is None:
            if running is not None:
                try:
                    token = running.session()
                    running.request("POST", "/shutdown", running.authorized(token))
                    process.wait(timeout=8)
                except (OSError, TimeoutError, subprocess.TimeoutExpired):
                    process.terminate()
            else:
                process.terminate()
        stdout, stderr = process.communicate(timeout=8)
        assert process.returncode == 0
        assert stdout == ""
        assert stderr == ""
        if running:
            assert all(token not in stdout + stderr for token in running.tokens)


@pytest.fixture
def api() -> Iterator[Running]:
    with runtime() as running:
        yield running


def test_session_diagnostic_shutdown_and_no_remote_bind(api: Running) -> None:
    token = api.session()
    assert api.session() == token  # Bounded one-session memory; repeated bootstrap is stable.
    status, headers, body = api.request("GET", "/diagnostic", api.authorized(token))
    assert status == 200
    assert json.loads(body) == {"status": "local_diagnostic", "planning_ready": False}
    status, _, info = api.request("GET", "/runtime", api.authorized(token))
    assert status == 200
    assert json.loads(info) == {"purpose": "exploratory", "financial_use_authorized": False}
    assert headers["access-control-allow-origin"] == api.origin
    assert headers["cache-control"] == "no-store"
    assert "set-cookie" not in headers
    assert "server" not in headers
    assert "access-control-allow-credentials" not in headers
    # The exact loopback port cannot be rebound by another local process.
    with socket.socket() as competing:
        with pytest.raises(OSError):
            competing.bind(("127.0.0.1", api.port))
    # Use a local non-loopback interface if one exists; no external host is contacted.
    addresses = {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    for address in addresses - {"127.0.0.1", "0.0.0.0"}:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            assert probe.connect_ex((address, api.port)) != 0
    assert api.request("POST", "/shutdown", api.authorized(token))[0] == 200
    assert api.process.wait(timeout=8) == 0
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", api.port), timeout=0.3)


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        "https://evil.example",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:1",
    ],
)
def test_origin_cannot_bootstrap_or_read(api: Running, origin: str | None) -> None:
    token = api.session()
    headers = {} if origin is None else {"Origin": origin}
    headers["X-Prosper-Bootstrap"] = "1"
    assert api.request("POST", "/session", headers)[0] == 403
    headers["Authorization"] = "Bearer " + token
    status, response_headers, _ = api.request("GET", "/diagnostic", headers)
    assert status == 403
    assert "access-control-allow-origin" not in response_headers
    assert api.request("POST", "/shutdown", headers)[0] == 403
    assert api.process.poll() is None


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "localhost",
        "127.0.0.1",
        "127.0.0.1:1",
        "127.0.0.1.evil.example",
        "[::1]:8000",
    ],
)
def test_host_and_forwarding_do_not_bypass(api: Running, host: str) -> None:
    headers = api.authorized(api.session())
    headers.update(
        {
            "Host": host,
            "X-Forwarded-Host": api.origin.removeprefix("http://"),
            "X-Forwarded-For": "127.0.0.1",
            "Forwarded": "host=127.0.0.1",
        }
    )
    assert api.request("GET", "/diagnostic", headers)[0] == 403
    headers["X-Prosper-Bootstrap"] = "1"
    assert api.request("POST", "/session", headers)[0] == 403


def test_bootstrap_and_bearer_required_on_all_other_paths(api: Running) -> None:
    assert api.request("POST", "/session", {"Origin": api.origin})[0] == 403
    token = api.session()
    for path in ("/diagnostic", "/shutdown", "/docs", "/openapi.json", "/unknown"):
        method = "POST" if path == "/shutdown" else "GET"
        for authorization in ("", "Bearer wrong", token, "bearer " + token):
            assert (
                api.request(method, path, {"Origin": api.origin, "Authorization": authorization})[0]
                == 401
            )
    for path in ("/docs", "/redoc", "/openapi.json", "/unknown"):
        assert api.request("GET", path, api.authorized(token))[0] == 404
    assert api.request("DELETE", "/diagnostic", api.authorized(token))[0] == 405


def test_query_fetch_site_and_cookies(api: Running) -> None:
    token = api.session()
    headers = api.authorized(token)
    assert api.request("GET", "/diagnostic?token=" + token, headers)[0] == 400
    headers["Sec-Fetch-Site"] = "cross-site"
    assert api.request("GET", "/diagnostic", headers)[0] == 403
    assert api.request("POST", "/session", {**headers, "X-Prosper-Bootstrap": "1"})[0] == 403
    assert (
        api.request("GET", "/diagnostic", {"Origin": api.origin, "Cookie": "token=" + token})[0]
        == 401
    )


def test_same_origin_browser_get_and_preflight(api: Running) -> None:
    token = api.session()
    headers = {"Sec-Fetch-Site": "same-origin", "Authorization": "Bearer " + token}
    assert api.request("GET", "/diagnostic", headers)[0] == 200
    assert api.request("GET", "/diagnostic", {"Sec-Fetch-Site": "same-origin"})[0] == 401
    assert api.request("GET", "/diagnostic", {**headers, "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert api.request("GET", "/diagnostic", {**headers, "Sec-Fetch-Site": "same-site"})[0] == 403
    assert api.request("POST", "/session", {**headers, "X-Prosper-Bootstrap": "1"})[0] == 403
    preflight = {
        "Origin": api.origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization, x-prosper-bootstrap",
    }
    status, response_headers, _ = api.request("OPTIONS", "/session", preflight)
    assert status == 200
    assert response_headers["access-control-allow-origin"] == api.origin
    assert api.request("OPTIONS", "/session", {**preflight, "Origin": "null"})[0] == 403
    assert (
        api.request("OPTIONS", "/session", {**preflight, "Access-Control-Request-Method": "PUT"})[0]
        == 403
    )
    assert (
        api.request(
            "OPTIONS", "/session", {**preflight, "Access-Control-Request-Headers": "x-evil"}
        )[0]
        == 403
    )


def test_duplicate_headers_and_header_budget(api: Running) -> None:
    token = api.session()
    base = (
        f"GET /diagnostic HTTP/1.1\r\nHost: 127.0.0.1:{api.port}\r\n"
        f"Origin: {api.origin}\r\nAuthorization: Bearer {token}\r\n"
    )
    for duplicate in (
        f"Origin: {api.origin}",
        "Authorization: Bearer wrong",
        f"Host: 127.0.0.1:{api.port}",
    ):
        response = api.raw((base + duplicate + "\r\n\r\n").encode())
        assert response.startswith(b"HTTP/1.1 400")
    response = api.raw((base + "X-Padding: " + "x" * 17000 + "\r\n\r\n").encode())
    assert response.startswith((b"HTTP/1.1 400", b"HTTP/1.1 431"))


def test_denied_origin_rejects_before_body_and_websocket_never_upgrades(api: Running) -> None:
    base = f"POST /session HTTP/1.1\r\nHost: 127.0.0.1:{api.port}\r\n"
    response = api.raw(
        (
            base + "Origin: https://evil.example\r\n"
            "X-Prosper-Bootstrap: 1\r\nContent-Length: 999999999\r\n\r\n"
        ).encode()
    )
    assert response.startswith(b"HTTP/1.1 403")
    token = api.session()
    response = api.raw(
        (
            f"GET /diagnostic HTTP/1.1\r\nHost: 127.0.0.1:{api.port}\r\n"
            f"Origin: {api.origin}\r\nAuthorization: Bearer {token}\r\n"
            "Connection: Upgrade\r\nUpgrade: websocket\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Key: c3ludGhldGljLWZpeHR1cmU=\r\n\r\n"
        ).encode()
    )
    assert not response.startswith(b"HTTP/1.1 101")
    assert b"local_diagnostic" in response


@pytest.mark.parametrize("route", ["refresh", "preview", "plan", "diagnostics"])
def test_history_http_limit_applies_before_body_parsing(api: Running, route: str) -> None:
    token = api.session()
    body_limit = 16 * 1024 * 1024 if route in ("refresh", "preview") else MAX_BODY_BYTES
    request = (
        f"POST /api/v1/history/{route} HTTP/1.1\r\nHost: 127.0.0.1:{api.port}\r\n"
        f"Origin: {api.origin}\r\nAuthorization: Bearer {token}\r\n"
        f"Content-Type: application/json\r\nContent-Length: {body_limit + 1}\r\n\r\n"
    )
    response = api.raw(request.encode())
    assert response.startswith(b"HTTP/1.1 413")


def test_declared_and_chunked_body_limits_and_timeout(api: Running) -> None:
    token = api.session()
    base = (
        f"POST /shutdown HTTP/1.1\r\nHost: 127.0.0.1:{api.port}\r\n"
        f"Origin: {api.origin}\r\nAuthorization: Bearer {token}\r\n"
    )
    # No bytes follow: rejection must occur from the declared size without waiting/allocation.
    response = api.raw((base + f"Content-Length: {MAX_BODY_BYTES + 1}\r\n\r\n").encode())
    assert response.startswith(b"HTTP/1.1 413")
    # A streaming/chunked request has no trusted Content-Length.
    with socket.create_connection(("127.0.0.1", api.port), timeout=8) as connection:
        connection.sendall((base + "Transfer-Encoding: chunked\r\n\r\n").encode())
        for _ in range(33):
            connection.sendall(b"10000\r\n" + b"x" * 65536 + b"\r\n")
        response = connection.recv(4096)
        assert response.startswith(b"HTTP/1.1 413")
    response = api.raw((base + "Content-Length: 1\r\n\r\n").encode())
    assert response.startswith(b"HTTP/1.1 408")
    assert api.request("POST", "/shutdown", api.authorized(token), b"x")[0] == 400
    assert api.process.poll() is None
    assert api.request("GET", "/diagnostic", api.authorized(token))[0] == 200


def test_optional_development_origin_and_restart_invalidate_session() -> None:
    with runtime("--development-port", "5173") as first:
        token = first.session("http://127.0.0.1:5173")
        headers = {"Origin": "http://127.0.0.1:5173", "Authorization": "Bearer " + token}
        assert first.request("GET", "/diagnostic", headers)[0] == 200
        assert (
            first.request("GET", "/diagnostic", {**headers, "Origin": "http://127.0.0.1:5174"})[0]
            == 403
        )
        port = first.port
    with runtime("--port", str(port)) as second:
        assert second.request("GET", "/diagnostic", second.authorized(token))[0] == 401
        assert second.session() != token
        assert (
            second.request(
                "POST", "/session", {"Origin": "http://127.0.0.1:5173", "X-Prosper-Bootstrap": "1"}
            )[0]
            == 403
        )


@pytest.mark.parametrize(
    "args",
    [("--port", "-1"), ("--port", "65536"), ("--development-port", "0"), ("--host", "0.0.0.0")],
)
def test_launcher_rejects_invalid_or_remote_configuration(args: tuple[str, ...]) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "prosper.local_api", *args],
        capture_output=True,
        text=True,
        timeout=12,
    )
    assert result.returncode == 2
    assert result.stdout == ""


@pytest.mark.parametrize("port,dev", [(0, None), (True, None), (1, 1), (8000, -1)])
def test_policy_rejects_invalid_ports(port: int, dev: int | None) -> None:
    with pytest.raises(ValueError):
        LocalPolicy(port, dev)
