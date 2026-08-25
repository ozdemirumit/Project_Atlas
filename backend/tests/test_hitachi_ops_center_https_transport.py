from __future__ import annotations

import asyncio
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from types import TracebackType

import pytest

from atlas.modules.connectors.vendors.hitachi_ops_center import https as transport_module
from atlas.modules.connectors.vendors.hitachi_ops_center.https import (
    HitachiOpsCenterHttpsTransport,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiTransportError


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.requested_amounts: list[int] = []

    def read(self, amount: int = -1) -> bytes:
        self.requested_amounts.append(amount)
        return self.body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeOpener:
    def __init__(self, outcome: FakeResponse | BaseException) -> None:
        self.outcome = outcome
        self.requests: list[urllib.request.Request] = []
        self.authorization_headers_during_open: list[str | None] = []
        self.timeouts: list[float] = []

    def open(
        self,
        request: urllib.request.Request,
        data: bytes | None = None,
        timeout: float = 0.0,
    ) -> FakeResponse:
        self.requests.append(request)
        self.authorization_headers_during_open.append(request.get_header("Authorization"))
        self.timeouts.append(timeout)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def verified_context() -> ssl.SSLContext:
    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def build_transport(
    monkeypatch: pytest.MonkeyPatch,
    outcome: FakeResponse | BaseException,
    **overrides: object,
) -> tuple[HitachiOpsCenterHttpsTransport, FakeOpener, list[object]]:
    opener = FakeOpener(outcome)
    handlers: list[object] = []

    def fake_build_opener(*configured_handlers: object) -> FakeOpener:
        handlers.extend(configured_handlers)
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    arguments: dict[str, object] = {
        "hostname": "opscenter.lab.example",
        "port": 23451,
        "ssl_context": verified_context(),
        "timeout_seconds": 7.5,
        "maximum_response_bytes": 1_024,
    }
    arguments.update(overrides)
    transport = HitachiOpsCenterHttpsTransport(**arguments)  # type: ignore[arg-type]
    return transport, opener, handlers


@pytest.mark.asyncio
async def test_get_uses_fixed_https_origin_json_accept_and_ephemeral_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_marker = "Bearer SYNTHETIC_SECRET_MUST_NOT_ESCAPE"
    response = FakeResponse(b'{"data":[]}')
    transport, opener, handlers = build_transport(
        monkeypatch,
        response,
        authorization_header_provider=lambda: secret_marker,
    )

    payload = await transport.get("/v1/objects/storages")

    assert payload == {"data": []}
    assert opener.requests[0].full_url == (
        "https://opscenter.lab.example:23451/v1/objects/storages"
    )
    assert opener.requests[0].method == "GET"
    assert opener.requests[0].get_header("Accept") == "application/json"
    assert opener.authorization_headers_during_open == [secret_marker]
    assert opener.requests[0].get_header("Authorization") is None
    assert opener.timeouts == [7.5]
    assert response.requested_amounts == [1_025]
    assert any(isinstance(handler, urllib.request.HTTPSHandler) for handler in handlers)
    assert any(isinstance(handler, transport_module._NoRedirectHandler) for handler in handlers)
    assert secret_marker not in repr(transport)
    assert secret_marker not in transport.__dict__.values()


@pytest.mark.asyncio
async def test_get_moves_blocking_urllib_work_to_a_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, _, _ = build_transport(monkeypatch, FakeResponse(b'{"ok":true}'))
    calls: list[tuple[Callable[..., object], tuple[object, ...]]] = []

    async def fake_to_thread(function: Callable[..., object], *arguments: object) -> object:
        calls.append((function, arguments))
        return function(*arguments)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    payload = await transport.get("/configuration/version")

    assert payload == {"ok": True}
    assert len(calls) == 1
    assert calls[0][1] == ("/configuration/version",)


@pytest.mark.parametrize(
    "path",
    [
        "relative/path",
        "//other.example/path",
        "/path?query=value",
        "/path#fragment",
        "/https://other.example/path",
        "/safe/%2e%2e/path",
        "/%2f%2fother.example/path",
        "/path\\other",
        "/invalid%escape",
    ],
)
@pytest.mark.asyncio
async def test_path_cannot_change_or_abuse_the_configured_origin(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    transport, opener, _ = build_transport(monkeypatch, FakeResponse(b"{}"))

    with pytest.raises(HitachiTransportError) as error:
        await transport.get(path)

    assert error.value.code == "malformed_vendor_response"
    assert error.value.retryable is False
    assert opener.requests == []


@pytest.mark.parametrize(
    "hostname",
    [
        "https://opscenter.example",
        "user@opscenter.example",
        "opscenter.example/path",
        "opscenter.example?query",
        "opscenter.example#fragment",
        "-opscenter.example",
        "opscenter..example",
    ],
)
def test_constructor_rejects_non_hostname_destinations(
    monkeypatch: pytest.MonkeyPatch, hostname: str
) -> None:
    with pytest.raises(ValueError, match="fixed DNS hostname"):
        build_transport(monkeypatch, FakeResponse(b"{}"), hostname=hostname)


def test_constructor_requires_exactly_one_verified_trust_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insecure_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure_context.check_hostname = False
    insecure_context.verify_mode = ssl.CERT_NONE

    with pytest.raises(ValueError, match="exactly one"):
        build_transport(monkeypatch, FakeResponse(b"{}"), ssl_context=None)
    with pytest.raises(ValueError, match="exactly one"):
        build_transport(
            monkeypatch,
            FakeResponse(b"{}"),
            ca_file="synthetic-ca.pem",
        )
    with pytest.raises(ValueError, match="verification must remain enabled"):
        build_transport(monkeypatch, FakeResponse(b"{}"), ssl_context=insecure_context)


def test_constructor_builds_verified_context_from_ca_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_files: list[str] = []

    def fake_create_default_context(*, cafile: str) -> ssl.SSLContext:
        ca_files.append(cafile)
        return verified_context()

    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)

    build_transport(
        monkeypatch,
        FakeResponse(b"{}"),
        ssl_context=None,
        ca_file="synthetic-ca.pem",
    )

    assert ca_files == ["synthetic-ca.pem"]


@pytest.mark.parametrize("body", [b"[]", b"null", b"not-json", b'{"value":NaN}'])
@pytest.mark.asyncio
async def test_response_must_be_a_strict_json_object(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    transport, _, _ = build_transport(monkeypatch, FakeResponse(body))

    with pytest.raises(HitachiTransportError) as error:
        await transport.get("/configuration/version")

    assert error.value.code == "malformed_vendor_response"
    assert error.value.retryable is False


@pytest.mark.asyncio
async def test_response_byte_limit_is_enforced_before_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, _, _ = build_transport(
        monkeypatch,
        FakeResponse(b'{"padding":"xxxxxxxxxxxxxxxx"}'),
        maximum_response_bytes=16,
    )

    with pytest.raises(HitachiTransportError) as error:
        await transport.get("/configuration/version")

    assert error.value.code == "vendor_response_limit_exceeded"
    assert error.value.retryable is False


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (302, "target_unavailable", False),
        (401, "vendor_permission_denied", False),
        (403, "vendor_permission_denied", False),
        (408, "target_timeout", True),
        (429, "vendor_rate_limited", True),
        (503, "target_unavailable", True),
        (504, "target_timeout", True),
    ],
)
@pytest.mark.asyncio
async def test_http_failures_use_safe_existing_error_codes(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    code: str,
    retryable: bool,
) -> None:
    transport, _, _ = build_transport(
        monkeypatch,
        urllib.error.HTTPError(
            "https://opscenter.lab.example:23451/safe",
            status,
            "synthetic failure",
            Message(),
            None,
        ),
    )

    with pytest.raises(HitachiTransportError) as error:
        await transport.get("/configuration/version")

    assert error.value.code == code
    assert error.value.retryable is retryable
    assert "synthetic failure" not in error.value.detail


@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (TimeoutError("synthetic timeout"), "target_timeout", True),
        (urllib.error.URLError(TimeoutError()), "target_timeout", True),
        (urllib.error.URLError(socket.gaierror()), "target_unavailable", True),
        (
            urllib.error.URLError(ssl.SSLCertVerificationError("certificate rejected")),
            "target_unavailable",
            False,
        ),
        (ConnectionRefusedError("synthetic refusal"), "target_unavailable", True),
    ],
)
@pytest.mark.asyncio
async def test_network_failures_are_sanitized_and_classified(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    code: str,
    retryable: bool,
) -> None:
    transport, _, _ = build_transport(monkeypatch, failure)

    with pytest.raises(HitachiTransportError) as error:
        await transport.get("/configuration/version")

    assert error.value.code == code
    assert error.value.retryable is retryable
    assert "synthetic" not in error.value.detail
    assert "certificate rejected" not in error.value.detail


@pytest.mark.asyncio
async def test_authorization_provider_failure_does_not_expose_its_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_marker = "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"

    def failed_provider() -> str:
        raise RuntimeError(secret_marker)

    transport, opener, _ = build_transport(
        monkeypatch,
        FakeResponse(b"{}"),
        authorization_header_provider=failed_provider,
    )

    with pytest.raises(HitachiTransportError) as error:
        await transport.get("/configuration/version")

    assert error.value.code == "vendor_permission_denied"
    assert secret_marker not in error.value.detail
    assert error.value.__cause__ is None
    assert opener.requests == []
