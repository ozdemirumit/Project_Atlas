from __future__ import annotations

import asyncio
import base64
import contextlib
import http.client
import json
import math
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from types import TracebackType
from typing import Never, Protocol, Self, cast

from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransportError

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*(?:\?[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?$")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MAXIMUM_TIMEOUT_SECONDS = 300.0
_MAXIMUM_CONFIGURED_RESPONSE_BYTES = 16_777_216
_SESSION_PATH = "/api/session"
_SESSION_HEADER = "vmware-api-session-id"


class _HttpsResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def read(self, amount: int = -1) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class _HttpsOpener(Protocol):
    def open(
        self,
        request: urllib.request.Request,
        data: bytes | None = None,
        timeout: float = 0.0,
    ) -> _HttpsResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        response: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        return None


class VCenterHttpsTransport:
    """Endpoint-bound HTTPS transport for one vCenter Server, implementing the vendor's real
    session lifecycle internally. Mirrors HuaweiPacificHttpsTransport's login -> read -> logout
    cycle and security posture, with two confirmed real differences: the session token comes back
    on the `vmware-api-session-id` response header rather than in a JSON response body, and every
    list endpoint this connector reads returns a JSON array at the top level rather than an
    object."""

    network_access = True
    secret_access = False

    def __init__(
        self,
        *,
        hostname: str,
        port: int,
        ssl_context: ssl.SSLContext | None = None,
        ca_file: str | os.PathLike[str] | None = None,
        credential_provider: Callable[[], str] | None = None,
        timeout_seconds: float = 30.0,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if not isinstance(hostname, str) or not _HOSTNAME.fullmatch(hostname):
            raise ValueError("hostname must be one fixed DNS hostname or IPv4 address")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65_535:
            raise ValueError("port must be between 1 and 65535")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= _MAXIMUM_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be greater than zero and at most 300")
        if (
            isinstance(maximum_response_bytes, bool)
            or not isinstance(maximum_response_bytes, int)
            or not 1 <= maximum_response_bytes <= _MAXIMUM_CONFIGURED_RESPONSE_BYTES
        ):
            raise ValueError("maximum_response_bytes must be between 1 and 16777216")
        if credential_provider is not None and not callable(credential_provider):
            raise ValueError("credential_provider must be callable")
        if (ssl_context is None) == (ca_file is None):
            raise ValueError("provide exactly one verified SSL context or CA file")

        verified_context = self._verified_context(ssl_context=ssl_context, ca_file=ca_file)
        self._base_url = f"https://{hostname.lower()}:{port}"
        self._credential_provider = credential_provider
        self._per_request_timeout = max(2.0, float(timeout_seconds) / 3)
        self._maximum_response_bytes = maximum_response_bytes
        self._opener = cast(
            _HttpsOpener,
            urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=verified_context),
                _NoRedirectHandler(),
            ),
        )

    async def get(self, path: str) -> Sequence[object]:
        validated_path = self._validated_path(path)
        return await asyncio.to_thread(self._bounded_read, validated_path)

    def _bounded_read(self, path: str) -> Sequence[object]:
        username, password = self._credential_pair()
        token = self._login(username, password)
        try:
            _status, _headers, body = self._raw_request(
                "GET", path, body=None, extra_headers={_SESSION_HEADER: token}
            )
        finally:
            self._logout(token)
        return self._decoded_array(body)

    def _login(self, username: str, password: str) -> str:
        credential = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        _status, headers, _body = self._raw_request(
            "POST",
            _SESSION_PATH,
            body=b"",
            extra_headers={"Authorization": f"Basic {credential}"},
        )
        token = headers.get(_SESSION_HEADER)
        if not isinstance(token, str) or not token:
            raise VCenterTransportError(
                "vendor_permission_denied",
                "The vendor did not return a usable session token.",
                retryable=False,
            )
        return token

    def _logout(self, token: str) -> None:
        with contextlib.suppress(VCenterTransportError):
            self._raw_request(
                "DELETE", _SESSION_PATH, body=None, extra_headers={_SESSION_HEADER: token}
            )

    def _credential_pair(self) -> tuple[str, str]:
        if self._credential_provider is None:
            raise VCenterTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            )
        try:
            value = self._credential_provider()
        except Exception:
            raise VCenterTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            ) from None
        if (
            not isinstance(value, str)
            or ":" not in value
            or len(value) > 8_192
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise VCenterTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            )
        username, _, password = value.partition(":")
        if not username or not password:
            raise VCenterTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            )
        return username, password

    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        extra_headers: Mapping[str, str] | None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        headers = {"Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(
            url=f"{self._base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with self._opener.open(request, timeout=self._per_request_timeout) as response:
                if response.status not in (200, 204):
                    raise self._http_status_error(response.status)
                response_status = response.status
                response_body = response.read(self._maximum_response_bytes + 1)
                response_headers = dict(response.headers)
        except urllib.error.HTTPError as error:
            raise self._http_status_error(error.code) from None
        except VCenterTransportError:
            raise
        except TimeoutError as error:
            raise self._connection_error(error) from None
        except urllib.error.URLError as error:
            raise self._connection_error(error) from None
        except (ssl.SSLError, socket.gaierror, ConnectionError, OSError) as error:
            raise self._connection_error(error) from None
        except (http.client.HTTPException, EOFError):
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor response could not be read safely.",
                retryable=False,
            ) from None

        if len(response_body) > self._maximum_response_bytes:
            raise VCenterTransportError(
                "vendor_response_limit_exceeded",
                "The vendor response exceeds its byte limit.",
                retryable=False,
            )
        return response_status, response_headers, response_body

    def _decoded_array(self, body: bytes) -> Sequence[object]:
        if not body:
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor response is not a valid JSON array.",
                retryable=False,
            )
        try:
            payload: object = json.loads(
                body.decode("utf-8"), parse_constant=self._reject_json_constant
            )
        except (UnicodeError, json.JSONDecodeError, ValueError):
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor response is not a valid JSON array.",
                retryable=False,
            ) from None
        if not isinstance(payload, list):
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor response must be a JSON array.",
                retryable=False,
            )
        return cast(list[object], payload)

    @staticmethod
    def _verified_context(
        *,
        ssl_context: ssl.SSLContext | None,
        ca_file: str | os.PathLike[str] | None,
    ) -> ssl.SSLContext:
        if ssl_context is None:
            if ca_file is None:
                raise ValueError("a CA file is required when no SSL context is provided")
            try:
                ssl_context = ssl.create_default_context(cafile=os.fspath(ca_file))
            except (OSError, ssl.SSLError, TypeError):
                raise ValueError("the CA file could not be loaded safely") from None
        if not ssl_context.check_hostname or ssl_context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("TLS hostname and certificate verification must remain enabled")
        return ssl_context

    @staticmethod
    def _validated_path(path: str) -> str:
        if not isinstance(path, str) or not _PATH.fullmatch(path):
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor request path is invalid.",
                retryable=False,
            )
        parsed = urllib.parse.urlsplit(path)
        reconstructed = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        decoded_path = urllib.parse.unquote(parsed.path)
        segments = decoded_path.split("/")
        if (
            path.startswith("//")
            or reconstructed != path
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or _INVALID_PERCENT_ESCAPE.search(path)
            or decoded_path.startswith("//")
            or "://" in decoded_path
            or "\\" in decoded_path
            or "#" in decoded_path
            or any(segment in {".", ".."} for segment in segments)
            or any(ord(character) < 32 or ord(character) == 127 for character in decoded_path)
            or (
                parsed.query
                and not re.fullmatch(r"[A-Za-z0-9._~%-]+=[A-Za-z0-9._~:%-]+", parsed.query)
            )
        ):
            raise VCenterTransportError(
                "malformed_vendor_response",
                "The vendor request path is invalid.",
                retryable=False,
            )
        return path

    @staticmethod
    def _http_status_error(status: int) -> VCenterTransportError:
        if status in {401, 403}:
            return VCenterTransportError(
                "vendor_permission_denied",
                "The vendor denied this read request.",
                retryable=False,
            )
        if status == 429:
            return VCenterTransportError(
                "vendor_rate_limited",
                "The vendor rate limit was reached.",
                retryable=True,
            )
        if status in {408, 504}:
            return VCenterTransportError(
                "target_timeout",
                "The vendor request timed out.",
                retryable=True,
            )
        return VCenterTransportError(
            "target_unavailable",
            "The vendor endpoint did not return a successful response.",
            retryable=status in {425, 500, 502, 503},
        )

    @staticmethod
    def _connection_error(error: BaseException) -> VCenterTransportError:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, TimeoutError):
            return VCenterTransportError(
                "target_timeout",
                "The vendor request timed out.",
                retryable=True,
            )
        return VCenterTransportError(
            "target_unavailable",
            "The vendor endpoint is unavailable.",
            retryable=not isinstance(reason, ssl.SSLError),
        )

    @staticmethod
    def _reject_json_constant(value: str) -> Never:
        raise ValueError(f"non-standard JSON constant is prohibited: {value}")
