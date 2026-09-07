"""ATLAS-036 SS9: persistence port for outbound dispatch authorization decisions.

`atlas.modules.itsm.domain.dispatch.ItsmOutboundDispatchAuthorization` is a deliberately minimal
frozen dataclass -- it carries only the decision itself, none of the request-bookkeeping fields
(requester, idempotency key, request fingerprint) that every other mutation repository in this
module persists alongside its domain record. `StoredItsmDispatchAuthorization` is that bookkeeping
wrapper, kept out of the domain type so the domain type stays exactly what SS9 needs it to be: a
decision, not a request record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atlas.modules.itsm.domain.dispatch import ItsmOutboundDispatchAuthorization


@dataclass(frozen=True, slots=True)
class StoredItsmDispatchAuthorization:
    authorization: ItsmOutboundDispatchAuthorization
    requested_by: str
    idempotency_key: str
    request_fingerprint: str


class ItsmDispatchAuthorizationRepository(Protocol):
    durable: bool

    async def get(self, *, authorization_id: str) -> StoredItsmDispatchAuthorization | None: ...

    async def get_by_idempotency_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> StoredItsmDispatchAuthorization | None: ...

    async def add(self, record: StoredItsmDispatchAuthorization) -> bool: ...

    async def close(self) -> None: ...
