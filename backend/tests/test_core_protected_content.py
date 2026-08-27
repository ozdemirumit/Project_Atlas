from __future__ import annotations

import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.protected_content import (
    InMemoryProtectedContentStore,
    PostgreSQLProtectedContentStore,
    ProtectedContentError,
    UnavailableProtectedContentStore,
    content_digest,
)

CONTENT = b"# Runbook\n\nRestart the read-only diagnostic collector.\n"
ORG = "organization.development"
ENV = "environment.test"
OTHER_ENV = "environment.other"


def test_content_digest_is_deterministic_sha256() -> None:
    assert content_digest(CONTENT) == content_digest(CONTENT)
    assert len(content_digest(CONTENT)) == 64
    assert content_digest(CONTENT) != content_digest(CONTENT + b"x")


@pytest.mark.asyncio
async def test_in_memory_store_round_trips_exact_content() -> None:
    store = InMemoryProtectedContentStore()

    digest = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)

    assert digest == content_digest(CONTENT)
    retrieved = await store.retrieve(organization_id=ORG, environment_id=ENV, digest=digest)
    assert retrieved == CONTENT


@pytest.mark.asyncio
async def test_in_memory_store_isolates_by_organization_and_environment() -> None:
    store = InMemoryProtectedContentStore()
    digest = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)

    assert (
        await store.retrieve(
            organization_id="organization.other", environment_id=ENV, digest=digest
        )
        is None
    )
    assert (
        await store.retrieve(organization_id=ORG, environment_id=OTHER_ENV, digest=digest) is None
    )


@pytest.mark.asyncio
async def test_in_memory_store_returns_none_for_unknown_digest() -> None:
    store = InMemoryProtectedContentStore()
    assert await store.retrieve(organization_id=ORG, environment_id=ENV, digest="0" * 64) is None


@pytest.mark.asyncio
async def test_in_memory_store_is_idempotent_for_identical_content() -> None:
    store = InMemoryProtectedContentStore()
    first = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
    second = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
    assert first == second


@pytest.mark.asyncio
async def test_in_memory_store_detects_ciphertext_tampering() -> None:
    store = InMemoryProtectedContentStore()
    digest = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
    key = (ORG, ENV, digest)
    stored = store._blobs[key]
    store._blobs[key] = stored[:-1] + bytes([stored[-1] ^ 0xFF])

    with pytest.raises(ProtectedContentError) as excinfo:
        await store.retrieve(organization_id=ORG, environment_id=ENV, digest=digest)
    assert excinfo.value.code == "protected_content_integrity_check_failed"


@pytest.mark.asyncio
async def test_unavailable_store_never_touches_content() -> None:
    store = UnavailableProtectedContentStore()

    with pytest.raises(ProtectedContentError) as excinfo:
        await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
    assert excinfo.value.code == "protected_content_store_unavailable"

    with pytest.raises(ProtectedContentError):
        await store.retrieve(organization_id=ORG, environment_id=ENV, digest="0" * 64)


def test_postgres_store_rejects_a_non_256_bit_key() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        PostgreSQLProtectedContentStore(
            engine=create_async_engine("postgresql+psycopg://unused/unused"),
            key=b"too-short",
        )


@pytest.mark.asyncio
async def test_live_postgres_round_trips_and_isolates_by_scope() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    store = PostgreSQLProtectedContentStore(engine=engine, key=AESGCM.generate_key(bit_length=256))
    try:
        digest = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
        assert digest == content_digest(CONTENT)

        retrieved = await store.retrieve(organization_id=ORG, environment_id=ENV, digest=digest)
        assert retrieved == CONTENT

        assert (
            await store.retrieve(organization_id=ORG, environment_id=OTHER_ENV, digest=digest)
            is None
        )

        again = await store.store(organization_id=ORG, environment_id=ENV, content=CONTENT)
        assert again == digest
    finally:
        await store.close()
