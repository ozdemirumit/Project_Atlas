from __future__ import annotations

import pytest

from atlas.core.pagination import (
    CursorCodec,
    CursorDecodeError,
    a_cursor_decodes_successfully_under_a_different_signing_key,
)


def test_absolute_rule_is_false() -> None:
    assert a_cursor_decodes_successfully_under_a_different_signing_key() is False


def test_round_trip() -> None:
    codec = CursorCodec(signing_key=b"a" * 32)
    cursor = codec.encode(42)
    assert codec.decode(cursor) == 42


def test_cursor_is_opaque_and_stable() -> None:
    codec = CursorCodec(signing_key=b"a" * 32)
    first = codec.encode(7)
    second = codec.encode(7)
    assert first == second
    assert "7" not in first.split(".")[1]


def test_encode_rejects_non_positive_sequence() -> None:
    codec = CursorCodec(signing_key=b"a" * 32)
    with pytest.raises(ValueError, match="must be positive"):
        codec.encode(0)


def test_decode_rejects_malformed_input() -> None:
    codec = CursorCodec(signing_key=b"a" * 32)
    with pytest.raises(CursorDecodeError):
        codec.decode("not-a-real-cursor")


def test_decode_rejects_a_cursor_signed_by_a_different_key() -> None:
    issuer = CursorCodec(signing_key=b"a" * 32)
    verifier = CursorCodec(signing_key=b"b" * 32)
    cursor = issuer.encode(5)
    with pytest.raises(CursorDecodeError):
        verifier.decode(cursor)


def test_decode_rejects_a_tampered_cursor() -> None:
    codec = CursorCodec(signing_key=b"a" * 32)
    cursor = codec.encode(5)
    value_part, signature_part = cursor.split(".", maxsplit=1)
    tampered = f"{value_part}x.{signature_part}"
    with pytest.raises(CursorDecodeError):
        codec.decode(tampered)


def test_default_key_is_random_per_instance() -> None:
    first = CursorCodec()
    second = CursorCodec()
    cursor = first.encode(3)
    with pytest.raises(CursorDecodeError):
        second.decode(cursor)
