"""Synthetic diagnostic runtime. Use this launcher; arbitrary ASGI hosting is unqualified."""

import argparse
import asyncio
import json
import secrets
import socket
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
BODY_TIMEOUT_SECONDS = 3.0
HOST = "127.0.0.1"


@dataclass(frozen=True)
class LocalPolicy:
    """Trusted launcher configuration; no wildcards, names, proxies or remote origins."""

    port: int
    development_port: int | None = None

    def __post_init__(self) -> None:
        for port in (self.port, self.development_port):
            if port is not None and (type(port) is not int or not 1 <= port <= 65535):
                raise ValueError("invalid_local_port")
        if self.development_port == self.port:
            raise ValueError("development_port_conflict")

    @property
    def authority(self) -> str:
        return f"{HOST}:{self.port}"

    @property
    def origin(self) -> str:
        return f"http://{self.authority}"

    @property
    def origins(self) -> tuple[str, ...]:
        if self.development_port is None:
            return (self.origin,)
        return (self.origin, f"http://{HOST}:{self.development_port}")


@dataclass(repr=False)
class _Session:
    token: bytes = field(default_factory=lambda: secrets.token_urlsafe(32).encode("ascii"))
    active: bool = True


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["synthetic_diagnostic"] = "synthetic_diagnostic"
    planning_ready: Literal[False] = False


class _RequestBoundary:
    """Reject before routing/body parsing; buffer only a bounded, timed byte stream."""

    def __init__(self, app: ASGIApp, policy: LocalPolicy, session: _Session) -> None:
        self.app = app
        self.policy = policy
        self.session = session

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        origin: str | None = None

        async def protected_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"connection", b"close"),
                        (b"vary", b"Origin"),
                    ]
                )
                if origin is not None:
                    headers.append((b"access-control-allow-origin", origin.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        async def deny(status: int, code: str) -> None:
            await JSONResponse({"error": code}, status_code=status)(scope, receive, protected_send)

        pairs: list[tuple[bytes, bytes]] = scope["headers"]
        if sum(len(k) + len(v) for k, v in pairs) > MAX_HEADER_BYTES:
            await deny(431, "headers_too_large")
            return
        headers: dict[bytes, bytes] = {}
        for key, value in pairs:
            if key in headers:
                await deny(400, "duplicate_header")
                return
            headers[key] = value
        client = scope.get("client")
        if client is None or client[0] != HOST:
            await deny(403, "peer_denied")
            return
        if headers.get(b"host") != self.policy.authority.encode("ascii"):
            await deny(403, "host_denied")
            return
        candidate = headers.get(b"origin", b"").decode("latin-1")
        # Same-origin browser GETs can omit Origin. Fetch Metadata is browser-controlled;
        # require an explicit same-origin assertion as well as the bearer check below.
        same_origin_get = (
            b"origin" not in headers
            and scope["method"] == "GET"
            and headers.get(b"sec-fetch-site") == b"same-origin"
        )
        if candidate not in self.policy.origins and not same_origin_get:
            await deny(403, "origin_denied")
            return
        origin = candidate if candidate else None
        if headers.get(b"sec-fetch-site", b"same-origin") not in (
            b"same-origin",
            b"same-site",
            b"none",
        ):
            await deny(403, "fetch_site_denied")
            return
        if scope.get("query_string"):
            await deny(400, "query_denied")
            return
        if not self.session.active:
            await deny(401, "session_closed")
            return
        method = scope["method"]
        if method == "OPTIONS":
            requested = headers.get(b"access-control-request-method")
            requested_headers = {
                h.strip().lower()
                for h in headers.get(b"access-control-request-headers", b"").split(b",")
                if h.strip()
            }
            if requested not in (b"GET", b"POST") or not requested_headers <= {
                b"authorization",
                b"x-prosper-bootstrap",
                b"content-type",
            }:
                await deny(403, "preflight_denied")
                return
            response = JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Methods": "GET, POST",
                    "Access-Control-Allow-Headers": (
                        "Authorization, X-Prosper-Bootstrap, Content-Type"
                    ),
                },
            )
            await response(scope, receive, protected_send)
            return
        if method not in ("GET", "POST"):
            await deny(405, "method_denied")
            return
        bootstrap = scope["path"] == "/session" and method == "POST"
        if bootstrap:
            if headers.get(b"x-prosper-bootstrap") != b"1":
                await deny(403, "bootstrap_denied")
                return
        elif not secrets.compare_digest(
            headers.get(b"authorization", b""), b"Bearer " + self.session.token
        ):
            await deny(401, "session_denied")
            return
        length = headers.get(b"content-length")
        if length is not None:
            if not length.isdigit() or len(length) > 10:
                await deny(400, "length_denied")
                return
            if int(length) > MAX_BODY_BYTES:
                await deny(413, "body_too_large")
                return
        buffered = bytearray()
        total = 0
        try:
            async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body = message.get("body", b"")
                    total += len(body)
                    if total > MAX_BODY_BYTES:
                        await deny(413, "body_too_large")
                        return
                    buffered.extend(body)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await deny(408, "body_timeout")
            return
        # This diagnostic slice accepts no request payloads. Later typed routes may consume
        # this bounded stream, retaining the same size/time checks before parser allocation.
        if total:
            await deny(400, "body_not_allowed")
            return

        async def bounded_receive() -> Message:
            return {"type": "http.request", "body": bytes(buffered), "more_body": False}

        await self.app(scope, bounded_receive, protected_send)


def _application(policy: LocalPolicy, request_shutdown: Callable[[], None]) -> ASGIApp:
    session = _Session()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            session.active = False
            session.token = b""

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        telemetry={
            "auto_configure": False,
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
        },
    )

    @app.post("/session")
    async def acquire_session() -> dict[str, str]:
        return {"token": session.token.decode("ascii"), "token_type": "Bearer"}

    @app.get("/diagnostic", response_model=Diagnostic)
    async def diagnostic() -> Diagnostic:
        return Diagnostic()

    @app.post("/shutdown")
    async def shutdown() -> dict[str, str]:
        session.active = False
        request_shutdown()
        return {"status": "stopping"}

    return _RequestBoundary(app, policy, session)


def serve(*, port: int = 0, development_port: int | None = None) -> None:
    """Own the socket for one process lifetime; publish only a public origin on stdout."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("invalid_local_port")
    # Validate before binding; zero is only the launcher's OS-selected API port.
    if development_port is not None:
        LocalPolicy(1 if development_port != 1 else 2, development_port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, port))
        listener.listen(16)
        actual_port = listener.getsockname()[1]
        policy = LocalPolicy(actual_port, development_port)

        def request_shutdown() -> None:
            server.should_exit = True

        config = uvicorn.Config(
            _application(policy, request_shutdown),
            host=HOST,
            port=actual_port,
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
            proxy_headers=False,
            access_log=False,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {"null": {"class": "logging.NullHandler"}},
                "loggers": {
                    name: {"handlers": ["null"], "propagate": False}
                    for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
                },
            },
            server_header=False,
            date_header=False,
            h11_max_incomplete_event_size=MAX_HEADER_BYTES,
            limit_concurrency=16,
            timeout_keep_alive=2,
            timeout_graceful_shutdown=3,
        )
        server = uvicorn.Server(config)
        print(json.dumps({"origin": policy.origin}), flush=True)
        server.run(sockets=[listener])


def main() -> None:
    parser = argparse.ArgumentParser(description="Prosper synthetic loopback diagnostic")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--development-port", type=int, default=None)
    args = parser.parse_args()
    try:
        serve(port=args.port, development_port=args.development_port)
    except (ValueError, OSError):
        parser.exit(2, "local_runtime_start_failed\n")


if __name__ == "__main__":
    main()
