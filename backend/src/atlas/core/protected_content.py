"""Real encrypted-content-at-rest boundary.

No component outside this module may read or write raw protected content.
Ordinary application persistence stores only the SHA-256 digest this module
returns from ``store`` — never the plaintext, never the ciphertext, never a
key. See ADR-184.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import ProtectedContentBlobModel

_NONCE_BYTES = 12


class ProtectedContentError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ProtectedContentStore(Protocol):
    async def store(self, *, organization_id: str, environment_id: str, content: bytes) -> str:
        """Encrypts and persists ``content``; returns its SHA-256 digest."""
        ...

    async def retrieve(
        self, *, organization_id: str, environment_id: str, digest: str
    ) -> bytes | None:
        """Returns the exact original plaintext for ``digest``, or ``None`` if absent."""
        ...


class UnavailableProtectedContentStore:
    async def store(self, *, organization_id: str, environment_id: str, content: bytes) -> str:
        del organization_id, environment_id, content
        raise ProtectedContentError(
            "protected_content_store_unavailable",
            "No approved protected-content store is configured for this environment.",
        )

    async def retrieve(
        self, *, organization_id: str, environment_id: str, digest: str
    ) -> bytes | None:
        del organization_id, environment_id, digest
        raise ProtectedContentError(
            "protected_content_store_unavailable",
            "No approved protected-content store is configured for this environment.",
        )


class InMemoryProtectedContentStore:
    """Process-local development/test store. Never used in production."""

    def __init__(self, *, key: bytes | None = None) -> None:
        self._key = key or AESGCM.generate_key(bit_length=256)
        self._aead = AESGCM(self._key)
        self._blobs: dict[tuple[str, str, str], bytes] = {}

    async def store(self, *, organization_id: str, environment_id: str, content: bytes) -> str:
        digest = content_digest(content)
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aead.encrypt(nonce, content, None)
        self._blobs[(organization_id, environment_id, digest)] = nonce + ciphertext
        return digest

    async def retrieve(
        self, *, organization_id: str, environment_id: str, digest: str
    ) -> bytes | None:
        stored = self._blobs.get((organization_id, environment_id, digest))
        if stored is None:
            return None
        nonce, ciphertext = stored[:_NONCE_BYTES], stored[_NONCE_BYTES:]
        try:
            plaintext = self._aead.decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ProtectedContentError(
                "protected_content_integrity_check_failed",
                "The stored protected content failed authenticated decryption.",
            ) from exc
        if content_digest(plaintext) != digest:
            raise ProtectedContentError(
                "protected_content_digest_mismatch",
                "The decrypted content does not match its recorded digest.",
            )
        return plaintext


class PostgreSQLProtectedContentStore:
    """Real, durable, AES-256-GCM encrypted-content-at-rest store.

    The encryption key never leaves process memory and is never persisted; only the
    nonce and ciphertext are written to the database, keyed by the plaintext's SHA-256
    digest so ordinary application records can reference content without ever holding it.
    """

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        key: bytes,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        if len(key) != 32:
            raise ValueError("protected content encryption key must be 32 bytes")
        self._aead = AESGCM(key)
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url_and_key_b64(
        cls, database_url: str, *, key_b64: str
    ) -> PostgreSQLProtectedContentStore:
        return cls(
            engine=create_async_engine(database_url, pool_pre_ping=True),
            key=base64.b64decode(key_b64),
        )

    async def store(self, *, organization_id: str, environment_id: str, content: bytes) -> str:
        digest = content_digest(content)
        async with self._sessions() as session:
            existing = await session.get(
                ProtectedContentBlobModel, (organization_id, environment_id, digest)
            )
            if existing is not None:
                return digest
            nonce = os.urandom(_NONCE_BYTES)
            ciphertext = self._aead.encrypt(nonce, content, None)
            session.add(
                ProtectedContentBlobModel(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    digest=digest,
                    nonce=nonce,
                    ciphertext=ciphertext,
                    byte_count=len(content),
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        return digest

    async def retrieve(
        self, *, organization_id: str, environment_id: str, digest: str
    ) -> bytes | None:
        async with self._sessions() as session:
            row = await session.get(
                ProtectedContentBlobModel, (organization_id, environment_id, digest)
            )
        if row is None:
            return None
        try:
            plaintext = self._aead.decrypt(row.nonce, row.ciphertext, None)
        except InvalidTag as exc:
            raise ProtectedContentError(
                "protected_content_integrity_check_failed",
                "The stored protected content failed authenticated decryption.",
            ) from exc
        if content_digest(plaintext) != digest:
            raise ProtectedContentError(
                "protected_content_digest_mismatch",
                "The decrypted content does not match its recorded digest.",
            )
        return plaintext

    async def close(self) -> None:
        await self._engine.dispose()
