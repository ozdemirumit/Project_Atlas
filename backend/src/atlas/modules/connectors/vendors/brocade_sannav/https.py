from __future__ import annotations

import asyncio
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
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Never, Protocol, Self, cast

from atlas.modules.connectors.vendors.brocade_sannav.ports import BrocadeTransportError

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
# Includes "?" unlike the equivalent Hitachi pattern: SANnav's fabric-members endpoint requires a
# query parameter (principalSwitchWWN), so the allowed charset must permit exactly one query
# string, validated further below.
_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*(?:\?[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?$")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MAXIMUM_TIMEOUT_SECONDS = 300.0
_MAXIMUM_CONFIGURED_RESPONSE_BYTES = 16_777_216


class _HttpsResponse(Protocol):
    status: int

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


class BrocadeSanNavHttpsTransport:
    """Endpoint-bound, pre-authenticated HTTPS transport for read-only vendor requests. Mirrors
    HitachiOpsCenterHttpsTransport's security posture exactly (hostname/path validation, enforced
    TLS verification, no redirects, bounded response size, rejected non-standard JSON constants),
    with POST added for SANnav's fault/events endpoint, which requires a request body."""

    network_access = True
    secret_access = False

    def __init__(
        self,
        *,
        hostname: str,
        port: int,
        ssl_context: ssl.SSLContext | None = None,
        ca_file: str | os.PathLike[str] | None = None,
        authorization_header_provider: Callable[[], str] | None = None,
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
        if authorization_header_provider is not None and not callable(
            authorization_header_provider
        ):
            raise ValueError("authorization_header_provider must be callable")
        if (ssl_context is None) == (ca_file is None):
            raise ValueError("provide exactly one verified SSL context or CA file")

        verified_context = self._verified_context(ssl_context=ssl_context, ca_file=ca_file)
        self._base_url = f"https://{hostname.lower()}:{port}"
        self._authorization_header_provider = authorization_header_provider
        self._timeout_seconds = float(timeout_seconds)
        self._maximum_response_bytes = maximum_response_bytes
        self._opener = cast(
            _HttpsOpener,
            urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=verified_context),
                _NoRedirectHandler(),
            ),
        )

    async def get(self, path: str) -> Mapping[str, object]:
        validated_path = self._validated_path(path)
        return await asyncio.to_thread(self._request_sync, validated_path, "GET", None)

    async def post(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]:
        validated_path = self._validated_path(path)
        try:
            encoded_body = json.dumps(
                dict(body), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BrocadeTransportError(
                "malformed_request_body",
                "The request body is not valid JSON data.",
                retryable=False,
            ) from exc
        return await asyncio.to_thread(self._request_sync, validated_path, "POST", encoded_body)

    def _request_sync(self, path: str, method: str, body: bytes | None) -> Mapping[str, object]:
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url=f"{self._base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        authorization: str | None = None
        try:
            authorization = self._authorization_header()
            if authorization is not None:
                request.add_unredirected_header("Authorization", authorization)
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                if response.status != 200:
                    raise self._http_status_error(response.status)
                response_body = response.read(self._maximum_response_bytes + 1)
        except urllib.error.HTTPError as error:
            raise self._http_status_error(error.code) from None
        except BrocadeTransportError:
            raise
        except TimeoutError as error:
            raise self._connection_error(error) from None
        except urllib.error.URLError as error:
            raise self._connection_error(error) from None
        except (ssl.SSLError, socket.gaierror, ConnectionError, OSError) as error:
            raise self._connection_error(error) from None
        except (http.client.HTTPException, EOFError):
            raise BrocadeTransportError(
                "malformed_vendor_response",
                "The vendor response could not be read safely.",
                retryable=False,
            ) from None
        finally:
            request.remove_header("Authorization")
            authorization = None

        if len(response_body) > self._maximum_response_bytes:
            raise BrocadeTransportError(
                "vendor_response_limit_exceeded",
                "The vendor response exceeds its byte limit.",
                retryable=False,
            )
        try:
            payload: object = json.loads(
                response_body.decode("utf-8"),
                parse_constant=self._reject_json_constant,
            )
        except (UnicodeError, json.JSONDecodeError, ValueError):
            raise BrocadeTransportError(
                "malformed_vendor_response",
                "The vendor response is not a valid JSON object.",
                retryable=False,
            ) from None
        if not isinstance(payload, dict):
            raise BrocadeTransportError(
                "malformed_vendor_response",
                "The vendor response must be a JSON object.",
                retryable=False,
            )
        return cast(dict[str, object], payload)

    def _authorization_header(self) -> str | None:
        if self._authorization_header_provider is None:
            return None
        try:
            value = self._authorization_header_provider()
        except Exception:
            raise BrocadeTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            ) from None
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 8_192
            or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise BrocadeTransportError(
                "vendor_permission_denied",
                "The vendor credential could not be applied safely.",
                retryable=False,
            )
        return value

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
            raise BrocadeTransportError(
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
            raise BrocadeTransportError(
                "malformed_vendor_response",
                "The vendor request path is invalid.",
                retryable=False,
            )
        return path

    @staticmethod
    def _http_status_error(status: int) -> BrocadeTransportError:
        if status in {401, 403}:
            return BrocadeTransportError(
                "vendor_permission_denied",
                "The vendor denied this read request.",
                retryable=False,
            )
        if status == 429:
            return BrocadeTransportError(
                "vendor_rate_limited",
                "The vendor rate limit was reached.",
                retryable=True,
            )
        if status in {408, 504}:
            return BrocadeTransportError(
                "target_timeout",
                "The vendor request timed out.",
                retryable=True,
            )
        return BrocadeTransportError(
            "target_unavailable",
            "The vendor endpoint did not return a successful response.",
            retryable=status in {425, 500, 502, 503},
        )

    @staticmethod
    def _connection_error(error: BaseException) -> BrocadeTransportError:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, TimeoutError):
            return BrocadeTransportError(
                "target_timeout",
                "The vendor request timed out.",
                retryable=True,
            )
        return BrocadeTransportError(
            "target_unavailable",
            "The vendor endpoint is unavailable.",
            retryable=not isinstance(reason, ssl.SSLError),
        )

    @staticmethod
    def _reject_json_constant(value: str) -> Never:
        raise ValueError(f"non-standard JSON constant is prohibited: {value}")
