from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256

from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.domain.bootstrap_invalidation import compare_bootstrap_run
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
    BootstrapRunRecord,
    BootstrapRunState,
)


class InMemoryBootstrapStateRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], BootstrapRunRecord] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, BootstrapMutationResult]] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def close(self) -> None:
        return None

    async def get_current(
        self, *, organization_id: str, environment_id: str, site_id: str
    ) -> BootstrapRunRecord | None:
        async with self._lock:
            return self._records.get((organization_id, environment_id, site_id))

    async def claim(
        self,
        *,
        identity: BootstrapRunIdentity,
        lease_holder_id: str,
        lease_duration: timedelta,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key = (identity.organization_id, identity.environment_id, identity.site_id)
            current = self._records.get(key)
            reclaimed = False
            if current is None:
                run_digest = sha256(
                    "/".join((*key, identity.resume_key)).encode("utf-8")
                ).hexdigest()[:24]
                updated = BootstrapRunRecord(
                    run_id=f"bootstrap-run.{run_digest}",
                    version=1,
                    identity=identity,
                    state=BootstrapRunState.ACTIVE,
                    checkpoints=(),
                    lease_holder_id=lease_holder_id,
                    lease_acquired_at=now,
                    lease_expires_at=now + lease_duration,
                    created_at=now,
                    updated_at=now,
                )
            else:
                if current.identity != identity:
                    raise BootstrapRepositoryError("bootstrap_plan_mismatch")
                if current.state is BootstrapRunState.COMPLETED:
                    raise BootstrapRepositoryError("bootstrap_run_completed")
                if current.lease_is_active(now):
                    raise BootstrapRepositoryError("bootstrap_lease_unavailable")
                reclaimed = current.lease_expires_at is not None
                updated = replace(
                    current,
                    version=current.version + 1,
                    state=(
                        BootstrapRunState.FAILED
                        if current.failed_phase_id is not None
                        else BootstrapRunState.ACTIVE
                    ),
                    lease_holder_id=lease_holder_id,
                    lease_acquired_at=now,
                    lease_expires_at=now + lease_duration,
                    updated_at=now,
                )
            result = BootstrapMutationResult(
                record=updated, replayed=False, reclaimed_expired_lease=reclaimed
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def checkpoint(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        phase_id: str,
        state: BootstrapCheckpointState,
        safe_output_references: tuple[str, ...],
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if phase_id not in current.identity.phase_ids:
                raise BootstrapRepositoryError("bootstrap_phase_unavailable")
            phase_index = current.identity.phase_ids.index(phase_id)
            completed = set(current.completed_phase_ids)
            if any(item not in completed for item in current.identity.phase_ids[:phase_index]):
                raise BootstrapRepositoryError("bootstrap_dependency_unsatisfied")
            if current.current_phase_id != phase_id:
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id=phase_id,
                state=state,
                safe_output_references=safe_output_references,
                recorded_at=now,
            )
            checkpoints = (
                *(item for item in current.checkpoints if item.phase_id != phase_id),
                checkpoint,
            )
            completed_after = {
                item.phase_id
                for item in checkpoints
                if item.state is BootstrapCheckpointState.COMPLETED
            }
            if state is BootstrapCheckpointState.FAILED:
                run_state = BootstrapRunState.FAILED
            elif len(completed_after) == len(current.identity.phase_ids):
                run_state = BootstrapRunState.COMPLETED
            else:
                run_state = BootstrapRunState.ACTIVE
            updated = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=checkpoints,
                updated_at=now,
            )
            result = BootstrapMutationResult(record=updated, replayed=False)
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def release(
        self,
        *,
        run_id: str,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            updated = replace(
                current,
                version=current.version + 1,
                lease_holder_id=None,
                lease_acquired_at=None,
                lease_expires_at=None,
                updated_at=now,
            )
            result = BootstrapMutationResult(record=updated, replayed=False)
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def rebase(
        self,
        *,
        run_id: str,
        candidate: BootstrapRunIdentity,
        lease_holder_id: str,
        expected_version: int,
        preview_source_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
            if (
                candidate.organization_id != current.identity.organization_id
                or candidate.environment_id != current.identity.environment_id
                or candidate.site_id != current.identity.site_id
            ):
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version or current.version != preview_source_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            impact = compare_bootstrap_run(current.identity, candidate, current)
            if impact.earliest_affected_phase_id is None:
                raise BootstrapRepositoryError("bootstrap_plan_unchanged")
            reusable = set(impact.reusable_checkpoint_phase_ids)
            checkpoints = tuple(
                item
                for item in current.checkpoints
                if item.state is BootstrapCheckpointState.COMPLETED and item.phase_id in reusable
            )
            updated = replace(
                current,
                version=current.version + 1,
                identity=candidate,
                state=BootstrapRunState.ACTIVE,
                checkpoints=checkpoints,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                preserved_checkpoint_phase_ids=impact.reusable_checkpoint_phase_ids,
                invalidated_checkpoint_phase_ids=impact.invalidated_checkpoint_phase_ids,
                invalidation_reason_codes=tuple(item.reason_code for item in impact.changes),
                earliest_affected_phase_id=impact.earliest_affected_phase_id,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    def _find(self, run_id: str) -> tuple[tuple[str, str, str], BootstrapRunRecord]:
        found = next(
            ((key, record) for key, record in self._records.items() if record.run_id == run_id),
            None,
        )
        if found is None:
            raise BootstrapRepositoryError("bootstrap_run_unavailable")
        return found

    @staticmethod
    def _require_lease(record: BootstrapRunRecord, lease_holder_id: str, now: datetime) -> None:
        if not record.lease_is_active(now) or record.lease_holder_id != lease_holder_id:
            raise BootstrapRepositoryError("bootstrap_lease_unavailable")

    def _replay(
        self, lease_holder_id: str, idempotency_key: str, request_fingerprint: str
    ) -> BootstrapMutationResult | None:
        prior = self._idempotency.get((lease_holder_id, idempotency_key))
        if prior is None:
            return None
        fingerprint, result = prior
        if fingerprint != request_fingerprint:
            raise BootstrapRepositoryError("bootstrap_idempotency_conflict")
        return replace(result, replayed=True)

    def _remember(
        self,
        lease_holder_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        result: BootstrapMutationResult,
    ) -> None:
        self._idempotency[(lease_holder_id, idempotency_key)] = (
            request_fingerprint,
            result,
        )
