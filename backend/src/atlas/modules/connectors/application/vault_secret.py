"""Self-built connector-credential vault application service.

Builds directly on `atlas.core.protected_content` (ADR-184's real AES-256-GCM encrypted-content-
at-rest boundary) -- no new encryption code, no new key. A `ConnectorVaultSecretRepository` row
only ever stores a pointer (a `protected_content_blobs` digest); the plaintext secret value is
never returned by this service to any HTTP caller -- only
`atlas.modules.connectors.adapters.connection_test_credential_local_vault.LocalVaultConnectorCredentialMaterializer`
reads it back, for server-side connector connection tests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.protected_content import ProtectedContentStore
from atlas.modules.connectors.domain.vault_secret import (
    SECRET_REFERENCE_ID_PATTERN,
    ConnectorVaultSecretReference,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

_MAXIMUM_SECRET_VALUE_BYTES = 8_192


class ConnectorVaultError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConnectorVaultSecretRepository(Protocol):
    async def get_digest(
        self, *, organization_id: str, environment_id: str, secret_reference_id: str
    ) -> str | None: ...

    async def upsert(
        self,
        *,
        organization_id: str,
        environment_id: str,
        secret_reference_id: str,
        protected_content_digest: str,
        set_by_subject_digest: str,
        updated_at: datetime,
    ) -> None: ...

    async def list_references(
        self, *, organization_id: str, environment_id: str
    ) -> list[ConnectorVaultSecretReference]: ...


class ConnectorVaultService:
    def __init__(
        self,
        *,
        repository: ConnectorVaultSecretRepository,
        protected_content: ProtectedContentStore,
        audit_sink: AuditSink,
        environment_id: str,
        subject_salt: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._protected_content = protected_content
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._subject_salt = subject_salt
        self._clock = clock or (lambda: datetime.now(UTC))

    async def set_secret(
        self,
        *,
        actor: AuthenticatedSubject,
        secret_reference_id: str,
        value: str,
        correlation_id: str,
    ) -> ConnectorVaultSecretReference:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorVaultError("connector_vault_human_required")
        if not SECRET_REFERENCE_ID_PATTERN.fullmatch(secret_reference_id):
            raise ConnectorVaultError("connector_vault_secret_reference_invalid")
        encoded = value.encode("utf-8")
        if not encoded or len(encoded) > _MAXIMUM_SECRET_VALUE_BYTES:
            raise ConnectorVaultError("connector_vault_secret_value_invalid")
        digest = await self._protected_content.store(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            content=encoded,
        )
        updated_at = self._clock()
        set_by_subject_digest = self._subject_digest(actor)
        await self._repository.upsert(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            secret_reference_id=secret_reference_id,
            protected_content_digest=digest,
            set_by_subject_digest=set_by_subject_digest,
            updated_at=updated_at,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_vault_secret_set",
            secret_reference_id=secret_reference_id,
        )
        return ConnectorVaultSecretReference(
            secret_reference_id=secret_reference_id,
            updated_at=updated_at,
            set_by_subject_digest=set_by_subject_digest,
        )

    async def list_references(
        self, *, actor: AuthenticatedSubject, correlation_id: str
    ) -> list[ConnectorVaultSecretReference]:
        del correlation_id
        return await self._repository.list_references(
            organization_id=actor.organization_id, environment_id=self._environment_id
        )

    def _subject_digest(self, actor: AuthenticatedSubject) -> str:
        return hashlib.sha256(f"{self._subject_salt}:{actor.subject_id}".encode()).hexdigest()

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        secret_reference_id: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.vault-secret.set",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="connectors.vault-secrets.create",
                resource_type="resource.connector.vault-secrets",
                scope_reference=secret_reference_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(("secret_material_logged", "false"),),
            )
        )
