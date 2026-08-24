from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from atlas.modules.connectors.application.invocation_authorization import (
    build_connector_invocation_input_envelope,
    build_connector_invocation_profile,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)


class InMemoryConnectorInvocationAuthorizationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorInvocationAuthorizationRecord] = {}
        self._source_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self, *, authorization_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        record = self._records.get(authorization_id)
        return (
            record
            if record is not None
            and record.organization_id == organization_id
            and record.environment_id == environment_id
            else None
        )

    async def get_by_target_session_in_scope(
        self,
        *,
        source_target_session_verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None:
        authorization_id = self._source_index.get(
            (organization_id, environment_id, source_target_session_verification_id)
        )
        return self._records.get(authorization_id) if authorization_id else None

    async def get_by_create_key_in_scope(
        self,
        *,
        authorized_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None:
        authorization_id = self._create_index.get(
            (organization_id, environment_id, authorized_by, idempotency_digest)
        )
        return self._records.get(authorization_id) if authorization_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.authorization_id,
            )
        )

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool:
        async with self._lock:
            source_key = (
                record.organization_id,
                record.environment_id,
                record.source_target_session_verification_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                record.authorized_by,
                record.idempotency_digest,
            )
            if (
                record.authorization_id in self._records
                or source_key in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.authorization_id] = record
            self._source_index[source_key] = record.authorization_id
            self._create_index[create_key] = record.authorization_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorInvocationProfileSource:
    def __init__(self, profiles: tuple[ConnectorInvocationProfileSnapshot, ...]) -> None:
        self._profiles = {
            (item.organization_id, item.environment_id, item.profile_id): item for item in profiles
        }

    async def get_by_id_in_scope(
        self, *, profile_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationProfileSnapshot | None:
        return self._profiles.get((organization_id, environment_id, profile_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationProfileSnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._profiles.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.profile_id,
            )
        )


class InMemoryConnectorInvocationInputEnvelopeSource:
    def __init__(self, envelopes: tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]) -> None:
        self._envelopes = {
            (item.organization_id, item.environment_id, item.envelope_id): item
            for item in envelopes
        }

    async def get_by_id_in_scope(
        self, *, envelope_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None:
        return self._envelopes.get((organization_id, environment_id, envelope_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._envelopes.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.envelope_id,
            )
        )


class InMemoryConnectorInvocationAuthorizationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorInvocationAuthorizationPolicySnapshot, ...]
    ) -> None:
        self._policies = {
            (item.organization_id, item.environment_id, item.policy_id): item for item in policies
        }

    async def get_by_id_in_scope(
        self, *, policy_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationAuthorizationPolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationPolicySnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._policies.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.policy_id,
            )
        )


class DevelopmentConnectorInvocationEvidenceStore:
    """Synthetic server-side preparation for local development only."""

    def __init__(self) -> None:
        self._profiles = InMemoryConnectorInvocationProfileSource(())
        self._envelopes = InMemoryConnectorInvocationInputEnvelopeSource(())

    async def prepare(
        self,
        *,
        source: ConnectorTargetSessionVerificationRecord,
        enablement: ConnectorCapabilityEnablementRecord,
        issued_at: datetime,
    ) -> None:
        for capability in enablement.capabilities:
            profile = build_connector_invocation_profile(
                source=source,
                capability=capability,
                issued_at=issued_at,
                expires_at=issued_at + timedelta(hours=4),
            )
            envelope = build_connector_invocation_input_envelope(
                profile=profile,
                issued_at=issued_at,
                expires_at=issued_at + timedelta(hours=2),
            )
            self._profiles._profiles[
                (profile.organization_id, profile.environment_id, profile.profile_id)
            ] = profile
            self._envelopes._envelopes[
                (envelope.organization_id, envelope.environment_id, envelope.envelope_id)
            ] = envelope

    async def get_profile_by_id_in_scope(
        self, *, profile_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationProfileSnapshot | None:
        return await self._profiles.get_by_id_in_scope(
            profile_id=profile_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def list_profiles_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationProfileSnapshot, ...]:
        return await self._profiles.list_scope(
            organization_id=organization_id, environment_id=environment_id
        )

    async def get_envelope_by_id_in_scope(
        self, *, envelope_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None:
        return await self._envelopes.get_by_id_in_scope(
            envelope_id=envelope_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def list_envelopes_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]:
        return await self._envelopes.list_scope(
            organization_id=organization_id, environment_id=environment_id
        )


class DevelopmentConnectorInvocationProfileSource:
    def __init__(self, store: DevelopmentConnectorInvocationEvidenceStore) -> None:
        self._store = store

    async def get_by_id_in_scope(
        self, *, profile_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationProfileSnapshot | None:
        return await self._store.get_profile_by_id_in_scope(
            profile_id=profile_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationProfileSnapshot, ...]:
        return await self._store.list_profiles_scope(
            organization_id=organization_id, environment_id=environment_id
        )


class DevelopmentConnectorInvocationInputEnvelopeSource:
    def __init__(self, store: DevelopmentConnectorInvocationEvidenceStore) -> None:
        self._store = store

    async def get_by_id_in_scope(
        self, *, envelope_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None:
        return await self._store.get_envelope_by_id_in_scope(
            envelope_id=envelope_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]:
        return await self._store.list_envelopes_scope(
            organization_id=organization_id, environment_id=environment_id
        )
