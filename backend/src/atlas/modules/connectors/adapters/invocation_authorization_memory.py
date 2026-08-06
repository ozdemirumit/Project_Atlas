from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)


class InMemoryConnectorInvocationAuthorizationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorInvocationAuthorizationRecord] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, authorization_id: str) -> ConnectorInvocationAuthorizationRecord | None:
        return self._records.get(authorization_id)

    async def get_by_target_session(
        self, *, source_target_session_verification_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        authorization_id = self._source_index.get(source_target_session_verification_id)
        return self._records.get(authorization_id) if authorization_id else None

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        authorization_id = self._create_index.get((authorized_by, idempotency_key))
        return self._records.get(authorization_id) if authorization_id else None

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool:
        async with self._lock:
            create_key = (record.authorized_by, record.idempotency_key)
            if (
                record.authorization_id in self._records
                or record.source_target_session_verification_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.authorization_id] = record
            self._source_index[record.source_target_session_verification_id] = (
                record.authorization_id
            )
            self._create_index[create_key] = record.authorization_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorInvocationProfileSource:
    def __init__(self, profiles: tuple[ConnectorInvocationProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorInvocationProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorInvocationInputEnvelopeSource:
    def __init__(self, envelopes: tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]) -> None:
        self._envelopes = {item.envelope_id: item for item in envelopes}

    async def get_by_id(
        self, *, envelope_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None:
        return self._envelopes.get(envelope_id)


class InMemoryConnectorInvocationAuthorizationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorInvocationAuthorizationPolicySnapshot, ...]
    ) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorInvocationAuthorizationPolicySnapshot | None:
        return self._policies.get(policy_id)
