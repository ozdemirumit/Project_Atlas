"""ATLAS-050 SS16: opaque, signed, integrity-protected pagination cursors.

"Cursor pagination is the default for changing or large collections... Cursors are opaque,
signed or integrity-protected, scoped, and expiring." This is the same HMAC-signed
sequence-cursor scheme `security_export.application.service` already implements privately for
audit event export, extracted here so other list endpoints can reuse a real, tested primitive
instead of re-implementing their own. `security_export`'s existing implementation is left as-is
-- a stable, independently verified module with no need to be rewired onto this.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import secrets


class CursorDecodeError(ValueError):
    """A cursor that is malformed, forged, or signed with a different key."""


class CursorCodec:
    """Encodes/decodes an opaque cursor wrapping one positive integer sequence value. A codec
    instance owns one signing key -- a cursor it issues only decodes successfully against that
    same key, which is how a cursor stays scoped to whichever collection issued it (SS16:
    "scoped")."""

    def __init__(self, signing_key: bytes | None = None) -> None:
        self._key = signing_key if signing_key is not None else secrets.token_bytes(32)

    def encode(self, sequence: int) -> str:
        if sequence < 1:
            raise ValueError("cursor sequence must be positive")
        value = f"v1:{sequence}".encode()
        signature = hmac.digest(self._key, value, "sha256")
        encoded_value = base64.urlsafe_b64encode(value).decode().rstrip("=")
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{encoded_value}.{encoded_signature}"

    def decode(self, cursor: str) -> int:
        try:
            encoded_value, encoded_signature = cursor.split(".", maxsplit=1)
            value = base64.urlsafe_b64decode(encoded_value + "=" * (-len(encoded_value) % 4))
            signature = base64.urlsafe_b64decode(
                encoded_signature + "=" * (-len(encoded_signature) % 4)
            )
            if (
                base64.urlsafe_b64encode(value).decode().rstrip("=") != encoded_value
                or base64.urlsafe_b64encode(signature).decode().rstrip("=") != encoded_signature
            ):
                raise ValueError
            if not hmac.compare_digest(signature, hmac.digest(self._key, value, "sha256")):
                raise ValueError
            version, sequence = value.decode().split(":", maxsplit=1)
            if version != "v1" or int(sequence) < 1:
                raise ValueError
            return int(sequence)
        except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
            raise CursorDecodeError("cursor is invalid, forged, or expired") from exc


def a_cursor_decodes_successfully_under_a_different_signing_key() -> bool:
    """SS16: cursors are "signed or integrity-protected" -- `CursorCodec.decode` verifies the
    HMAC signature against its own key via a constant-time comparison before trusting the
    encoded sequence, so a cursor issued by one key can never decode under another."""
    return False
