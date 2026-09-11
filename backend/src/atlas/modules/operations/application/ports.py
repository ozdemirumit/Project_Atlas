from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.operations.domain.models import OperationResource


class OperationResourceError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code


class OperationResourceRepository(Protocol):
    durable: bool

    async def get(
        self, *, operation_id: str, organization_id: str, environment_id: str
    ) -> OperationResource | None: ...

    async def add(self, resource: OperationResource) -> bool: ...

    async def update(
        self, *, expected: OperationResource, replacement: OperationResource
    ) -> bool: ...

    async def close(self) -> None: ...


class OperationResourcePermissionAuthorizer(Protocol):
    """Mirrors `DocumentKnowledgePermissionAuthorizer`/`ItsmAttachmentPermissionAuthorizer`'s
    shape: one reusable `authorize()` for every operation's own permission, plus a dedicated
    `cross_subject_access_allowed()` gated behind its own elevated permission -- evaluated only
    when the acting subject does not own the operation resource it is trying to read or cancel,
    mirroring `document_retrieval.py`'s read-time-only use of the same "own permission plus a
    separately-gated elevated check" pattern (see `classification_ceiling()`).
    """

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None: ...

    async def cross_subject_access_allowed(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> bool: ...


__all__ = [
    "OperationResourceError",
    "OperationResourcePermissionAuthorizer",
    "OperationResourceRepository",
]
