from __future__ import annotations

import asyncio

from atlas.modules.itsm.domain.models import (
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmSandboxConformanceAssessment,
)


class InMemoryItsmIntegrationProfileRepository:
    durable = False

    def __init__(self) -> None:
        self._profiles: dict[str, ItsmIntegrationProfile] = {}
        self._sandbox_assessments: dict[str, ItsmSandboxConformanceAssessment] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, profile_id: str) -> ItsmIntegrationProfile | None:
        return self._profiles.get(profile_id)

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, profile_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.organization_id == organization_id
                and item.environment_id == environment_id
                and item.profile_key == profile_key
            ),
            None,
        )

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.created_by == created_by and item.create_idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.retired_by == retired_by
                and item.retirement_idempotency_key == idempotency_key
            ),
            None,
        )

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
    ) -> tuple[ItsmIntegrationProfile, ...]:
        records = (
            item
            for item in self._profiles.values()
            if item.organization_id == organization_id
            and item.environment_id == environment_id
            and (lifecycle is None or item.lifecycle is lifecycle)
        )
        return tuple(sorted(records, key=lambda item: item.profile_key)[:limit])

    async def add(self, profile: ItsmIntegrationProfile) -> bool:
        async with self._lock:
            if profile.profile_id in self._profiles or any(
                item.organization_id == profile.organization_id
                and item.environment_id == profile.environment_id
                and (
                    item.profile_key == profile.profile_key
                    or (
                        item.created_by == profile.created_by
                        and item.create_idempotency_key == profile.create_idempotency_key
                    )
                )
                for item in self._profiles.values()
            ):
                return False
            self._profiles[profile.profile_id] = profile
            return True

    async def update(self, profile: ItsmIntegrationProfile, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._profiles.get(profile.profile_id)
            if current is None or current.version != expected_version:
                return False
            self._profiles[profile.profile_id] = profile
            return True

    async def get_latest_sandbox_conformance(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        profile_id: str,
    ) -> ItsmSandboxConformanceAssessment | None:
        candidates = (
            item
            for item in self._sandbox_assessments.values()
            if item.organization_id == organization_id
            and item.environment_id == environment_id
            and item.site_id == site_id
            and item.profile_id == profile_id
        )
        return next(
            iter(
                sorted(
                    candidates,
                    key=lambda item: (item.observed_at, item.assessment_id),
                    reverse=True,
                )
            ),
            None,
        )

    async def get_sandbox_conformance_by_key(
        self, *, assessed_by: str, idempotency_key: str
    ) -> ItsmSandboxConformanceAssessment | None:
        return next(
            (
                item
                for item in self._sandbox_assessments.values()
                if item.assessed_by == assessed_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add_sandbox_conformance(self, assessment: ItsmSandboxConformanceAssessment) -> bool:
        async with self._lock:
            if assessment.assessment_id in self._sandbox_assessments or any(
                item.assessed_by == assessment.assessed_by
                and item.idempotency_key == assessment.idempotency_key
                for item in self._sandbox_assessments.values()
            ):
                return False
            self._sandbox_assessments[assessment.assessment_id] = assessment
            return True

    async def close(self) -> None:
        return None
