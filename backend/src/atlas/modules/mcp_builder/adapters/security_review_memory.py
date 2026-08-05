from __future__ import annotations

import asyncio
from dataclasses import replace

from atlas.modules.mcp_builder.domain.security_review import McpBuilderSecurityReview


class InMemoryMcpBuilderSecurityReviewRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, McpBuilderSecurityReview] = {}
        self._by_project: dict[str, McpBuilderSecurityReview] = {}
        self._by_domain_review: dict[str, McpBuilderSecurityReview] = {}
        self._by_create_key: dict[tuple[str, str], McpBuilderSecurityReview] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, review_id: str) -> McpBuilderSecurityReview | None:
        return self._copy(self._by_id.get(review_id))

    async def get_by_project(self, *, project_id: str) -> McpBuilderSecurityReview | None:
        return self._copy(self._by_project.get(project_id))

    async def get_by_domain_review(
        self, *, domain_review_id: str
    ) -> McpBuilderSecurityReview | None:
        return self._copy(self._by_domain_review.get(domain_review_id))

    async def get_by_create_key(
        self, *, reviewed_by: str, idempotency_key: str
    ) -> McpBuilderSecurityReview | None:
        return self._copy(self._by_create_key.get((reviewed_by, idempotency_key)))

    async def add(self, review: McpBuilderSecurityReview) -> bool:
        async with self._lock:
            create_key = (review.reviewed_by, review.idempotency_key)
            if (
                review.review_id in self._by_id
                or review.project_id in self._by_project
                or review.domain_review_id in self._by_domain_review
                or create_key in self._by_create_key
            ):
                return False
            stored = replace(review, reused=False)
            self._by_id[stored.review_id] = stored
            self._by_project[stored.project_id] = stored
            self._by_domain_review[stored.domain_review_id] = stored
            self._by_create_key[create_key] = stored
            return True

    async def close(self) -> None:
        return None

    @staticmethod
    def _copy(value: McpBuilderSecurityReview | None) -> McpBuilderSecurityReview | None:
        return replace(value) if value is not None else None
