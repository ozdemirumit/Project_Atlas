from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanningError,
    WorkflowRunMaterializationError,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
)
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactIdempotencyRecord,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactResult,
)
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingIdempotencyRecord,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingResult,
)
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingError,
    WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteBindingRequest,
    WorkflowEventPhysicalTransportRouteBindingResult,
)
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
)
from atlas.modules.workflows.application.route_freshness_admission_ports import (
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult,
)
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionError,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
)
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionError,
    WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionResult,
)
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotIdempotencyRecord,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotResult,
)
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotIdempotencyRecord,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotResult,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchIntent,
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowExecutionAttempt,
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowRunPlan,
    WorkflowScope,
)


class UnavailableWorkflowPlanRepository:
    """Fail-closed adapter used when durable production storage is unavailable."""

    @property
    def durable(self) -> bool:
        return False

    @staticmethod
    def _raise() -> NoReturn:
        raise WorkflowPlanningError(
            "workflow_repository_unavailable",
            "Durable workflow plan storage is not configured.",
        )

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        self._raise()

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        self._raise()

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        self._raise()

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        self._raise()

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        self._raise()

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        self._raise()

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        self._raise()

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        self._raise_run()

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        self._raise_run()

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        self._raise_run()

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        self._raise_attempt()

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        self._raise_attempt()

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        self._raise_attempt()

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        self._raise_dispatch_intent()

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        self._raise_dispatch_intent()

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        self._raise_publication_lease()

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        self._raise_publication_lease()

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        self._raise_publication_lease()

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        self._raise_dispatch_event_envelope()

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        self._raise_dispatch_event_envelope()

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        self._raise_dispatch_event_envelope()

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        self._raise_event_transport_admission()

    async def get_event_transport_admission_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowEventTransportAdmission | None:
        self._raise_event_transport_admission()

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        self._raise_event_transport_admission()

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        self._raise_event_transport_admission()

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None:
        self._raise_event_byte_artifact()

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None:
        self._raise_event_byte_artifact()

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult:
        self._raise_event_byte_artifact()

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None:
        self._raise_event_logical_channel_binding()

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        self._raise_event_logical_channel_binding()

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None:
        self._raise_event_logical_channel_binding()

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult:
        self._raise_event_logical_channel_binding()

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None:
        self._raise_transport_profile_snapshot()

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None:
        self._raise_transport_profile_snapshot()

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult:
        self._raise_transport_profile_snapshot()

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        self._raise_transport_route_snapshot()

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None:
        self._raise_transport_route_snapshot()

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult:
        self._raise_transport_route_snapshot()

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        self._raise_transport_compatibility_admission()

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None:
        self._raise_transport_compatibility_admission()

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        self._raise_transport_compatibility_admission()

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]:
        self._raise_transport_compatibility_admission()

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None:
        self._raise_transport_compatibility_admission()

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult:
        self._raise_transport_compatibility_admission()

    async def get_transport_compatibility_admission_by_id(
        self, *, admission_id: str
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        self._raise_physical_transport_route_binding()

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None:
        self._raise_physical_transport_route_binding()

    async def get_physical_transport_route_binding(
        self, *, logical_channel_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        self._raise_physical_transport_route_binding()

    async def list_physical_transport_route_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportRouteBinding, ...]:
        self._raise_physical_transport_route_binding()

    async def get_physical_transport_route_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord | None:
        self._raise_physical_transport_route_binding()

    async def bind_physical_transport_route(
        self, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingResult:
        self._raise_physical_transport_route_binding()

    async def synchronize_route_selection_heads(
        self, heads: tuple[DeploymentEventTransportRouteSelectionHead, ...]
    ) -> None:
        self._raise_route_freshness_admission()

    async def get_physical_transport_route_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        self._raise_route_freshness_admission()

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None:
        self._raise_route_freshness_admission()

    async def get_route_freshness_admission(
        self, *, physical_transport_route_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        self._raise_route_freshness_admission()

    async def list_route_freshness_admissions(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportRouteFreshnessAdmission, ...]:
        self._raise_route_freshness_admission()

    async def get_route_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord | None:
        self._raise_route_freshness_admission()

    async def admit_physical_transport_route_freshness(
        self, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
        self._raise_route_freshness_admission()

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        self._raise_publication_lease()

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._raise_publication_lease()

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._raise_publication_lease()

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        self._raise_dispatch_intent()

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        self._raise_dispatch_intent()

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        self._raise()

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        self._raise()

    async def heartbeat_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        self._raise()

    async def release_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        self._raise()

    async def close(self) -> None:
        return None

    @staticmethod
    def _raise_run() -> NoReturn:
        raise WorkflowRunMaterializationError(
            "workflow_run_repository_unavailable",
            "Durable workflow run materialization storage is not configured.",
        )

    @staticmethod
    def _raise_attempt() -> NoReturn:
        raise WorkflowAttemptMaterializationError(
            "workflow_attempt_repository_unavailable",
            "Durable workflow attempt materialization storage is not configured.",
        )

    @staticmethod
    def _raise_dispatch_intent() -> NoReturn:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_intent_repository_unavailable",
            "Durable workflow dispatch intent staging storage is not configured.",
        )

    @staticmethod
    def _raise_publication_lease() -> NoReturn:
        raise WorkflowOutboxPublicationLeaseError(
            "workflow_outbox_publication_lease_repository_unavailable",
            "Durable workflow outbox publication lease storage is not configured.",
        )

    @staticmethod
    def _raise_dispatch_event_envelope() -> NoReturn:
        raise WorkflowDispatchEventEnvelopeError(
            "workflow_dispatch_event_envelope_repository_unavailable",
            "Durable workflow dispatch event envelope storage is not configured.",
        )

    @staticmethod
    def _raise_event_transport_admission() -> NoReturn:
        raise WorkflowEventTransportAdmissionError(
            "workflow_event_transport_admission_repository_unavailable",
            "Durable workflow event transport admission storage is not configured.",
        )

    @staticmethod
    def _raise_event_byte_artifact() -> NoReturn:
        raise WorkflowEventByteArtifactError(
            "workflow_event_byte_artifact_repository_unavailable",
            "Durable workflow event byte artifact storage is not configured.",
        )

    @staticmethod
    def _raise_event_logical_channel_binding() -> NoReturn:
        raise WorkflowEventLogicalChannelBindingError(
            "workflow_event_logical_channel_binding_repository_unavailable",
            "Durable workflow event logical channel binding storage is not configured.",
        )

    @staticmethod
    def _raise_transport_profile_snapshot() -> NoReturn:
        raise WorkflowTransportProfileSnapshotError(
            "workflow_transport_profile_snapshot_repository_unavailable",
            "Durable event transport profile snapshot storage is not configured.",
        )

    @staticmethod
    def _raise_transport_route_snapshot() -> NoReturn:
        raise WorkflowTransportRouteSnapshotError(
            "workflow_transport_route_snapshot_repository_unavailable",
            "Durable event transport route snapshot storage is not configured.",
        )

    @staticmethod
    def _raise_transport_compatibility_admission() -> NoReturn:
        raise WorkflowEventTransportCompatibilityAdmissionError(
            "workflow_transport_compatibility_admission_repository_unavailable",
            "Durable workflow transport compatibility storage is not configured.",
        )

    @staticmethod
    def _raise_physical_transport_route_binding() -> NoReturn:
        raise WorkflowEventPhysicalTransportRouteBindingError(
            "workflow_physical_transport_route_binding_repository_unavailable",
            "Durable workflow physical transport route binding storage is not configured.",
        )

    @staticmethod
    def _raise_route_freshness_admission() -> NoReturn:
        raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
            "workflow_route_freshness_admission_repository_unavailable",
            "Durable workflow route freshness admission storage is not configured.",
        )
