import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listOperationalConversations } from "../../api/conversations";
import {
  cancelWorkflowPlan,
  createWorkflowPlan,
  listWorkflowDefinitions,
  listWorkflowPlans,
  WORKFLOW_PLAN_SAFETY_NOTICE,
  type WorkflowDefinition,
  type WorkflowDispatchIntent,
  type WorkflowDispatchEventEnvelope,
  type WorkflowDispatchOutboxEntry,
  type WorkflowDispatchOutboxPublicationLease,
  type WorkflowEndpointResolutionAuthorizationLease,
  type WorkflowEventByteArtifact,
  type WorkflowEventLogicalChannelBinding,
  type WorkflowEventTransportAdmission,
  type WorkflowExecutionAttempt,
  type WorkflowExecutionRun,
  type WorkflowOrchestrationLease,
  type WorkflowPhysicalTransportCredentialAccessAuthorizationLease,
  type WorkflowPhysicalTransportCredentialMaterialization,
  type WorkflowPhysicalTransportTargetContextAccessAuthorizationLease,
  type WorkflowPhysicalTransportTargetContextArtifactOpening,
  type WorkflowPhysicalTransportTargetContextCapsuleConsumerBinding,
  type WorkflowPhysicalTransportTargetContextCapsuleHandoffAuthorizationLease,
  type WorkflowPhysicalTransportTargetContextCapsuleHandoff,
  type WorkflowPhysicalTransportTargetContextBinding,
  type WorkflowPhysicalTransportCredentialAssignmentSnapshot,
  type WorkflowPhysicalTransportCredentialAssignmentBinding,
  type WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmission,
  type WorkflowPhysicalTransportRouteBinding,
  type WorkflowPhysicalTransportEndpointMaterialization,
  type WorkflowPhysicalTransportRouteFreshnessAdmission,
  type WorkflowRunPlan,
  type WorkflowTransportCompatibilityAdmission,
  type WorkflowTransportProfileSnapshot,
  type WorkflowTransportRouteSnapshot,
} from "../../api/workflows";
import WorkflowPlanningWorkspace from "./WorkflowPlanningWorkspace";

vi.mock("../../api/conversations", () => ({ listOperationalConversations: vi.fn() }));
vi.mock("../../api/workflows", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/workflows")>();
  return {
    ...original,
    cancelWorkflowPlan: vi.fn(),
    createWorkflowPlan: vi.fn(),
    listWorkflowDefinitions: vi.fn(),
    listWorkflowPlans: vi.fn(),
  };
});

const definition: WorkflowDefinition = {
  definition_id: "workflow.evidence-grounded-query",
  version: 1,
  title: "Evidence-grounded query",
  purpose: "Plan bounded evidence retrieval.",
  input_schema_version: "workflow-input.v1",
  definition_digest: "a".repeat(64),
  steps: [
    {
      step_id: "query-authorized-evidence",
      ordinal: 1,
      title: "Query authorized evidence",
      kind: "evidence_query",
      capability_class: "C1",
      timeout_seconds: 60,
      depends_on: [],
    },
  ],
};

const plan: WorkflowRunPlan = {
  plan_id: "workflow_plan_1234567890abcdef",
  definition_id: definition.definition_id,
  definition_version: 1,
  definition_digest: definition.definition_digest,
  scope: {
    organization_id: "organization.test",
    environment_id: "environment.test",
    site_id: "site.test",
  },
  target_id: "asset.storage.test",
  target_type: "storage",
  canonical_input_digest: "b".repeat(64),
  creator_subject_id: "subject.operator",
  created_at: "2026-08-13T10:00:00Z",
  state: "planned",
  steps: [
    {
      step_id: "query-authorized-evidence",
      ordinal: 1,
      kind: "evidence_query",
      capability_class: "C1",
      state: "not_started",
    },
  ],
  durable: false,
  authority: {
    worker_dispatch_authorized: false,
    connector_invocation_authorized: false,
    approval_creation_authorized: false,
    signal_delivery_authorized: false,
    retry_authorized: false,
    itsm_mutation_authorized: false,
    runbook_execution_authorized: false,
    infrastructure_change_authorized: false,
  },
  safety_notice: WORKFLOW_PLAN_SAFETY_NOTICE,
  canonical_digest: "c".repeat(64),
  transition_history: [],
};

const cancelledPlan: WorkflowRunPlan = {
  ...plan,
  state: "cancelled",
  canonical_digest: "d".repeat(64),
  transition_history: [
    {
      transition_id: "workflow-transition.1234567890abcdef",
      prior_state: "planned",
      new_state: "cancelled",
      actor_subject_id: "subject.operator",
      scope: plan.scope,
      target_id: plan.target_id,
      target_type: "storage",
      reason: "The assessment is no longer required.",
      reason_digest: "e".repeat(64),
      correlation_id: "correlation.workflow.cancel",
      occurred_at: "2026-08-13T10:05:00Z",
      canonical_digest: "f".repeat(64),
    },
  ],
};

const activeLease: WorkflowOrchestrationLease = {
  lease_id: "workflow-lease.1234567890abcdef",
  plan_id: plan.plan_id,
  plan_digest: plan.canonical_digest,
  scope: plan.scope,
  target_id: plan.target_id,
  target_type: "storage",
  worker_subject_id: "workload.worker",
  acquired_at: "2026-08-13T10:01:00Z",
  last_heartbeat_at: "2026-08-13T10:02:00Z",
  expires_at: "2026-08-13T10:07:00Z",
  fencing_token: 7,
  state: "active",
  effective_state: "active",
  canonical_digest: "8".repeat(64),
  grants_execution_authority: false,
};

const materializedRun: WorkflowExecutionRun = {
  run_id: "workflow-run.1234567890abcdef",
  plan_id: plan.plan_id,
  plan_digest: plan.canonical_digest,
  definition_id: plan.definition_id,
  definition_version: plan.definition_version,
  definition_digest: plan.definition_digest,
  scope: plan.scope,
  target_id: plan.target_id,
  target_type: "storage",
  lease_id: activeLease.lease_id,
  lease_digest: activeLease.canonical_digest,
  fencing_token: activeLease.fencing_token,
  materialized_by_subject_id: "workload.workflow.materializer",
  created_at: "2026-08-13T10:03:00Z",
  state: "created",
  step_runs: [
    {
      step_run_id: "workflow-step-run.1234567890abcdef",
      run_id: "workflow-run.1234567890abcdef",
      step_id: plan.steps[0]!.step_id,
      ordinal: 1,
      kind: plan.steps[0]!.kind,
      capability_class: plan.steps[0]!.capability_class,
      timeout_seconds: 60,
      depends_on: [],
      state: "not_started",
      canonical_digest: "9".repeat(64),
    },
  ],
  authority: { ...plan.authority },
  grants_execution_authority: false,
  canonical_digest: "1".repeat(64),
};

const materializedAttempt: WorkflowExecutionAttempt = {
  attempt_id: "workflow-attempt.1234567890abcdef",
  run_id: materializedRun.run_id,
  run_digest: materializedRun.canonical_digest,
  step_run_id: materializedRun.step_runs[0]!.step_run_id,
  step_run_digest: materializedRun.step_runs[0]!.canonical_digest,
  step_id: materializedRun.step_runs[0]!.step_id,
  attempt_number: 1,
  plan_id: materializedRun.plan_id,
  plan_digest: materializedRun.plan_digest,
  definition_id: materializedRun.definition_id,
  definition_version: materializedRun.definition_version,
  definition_digest: materializedRun.definition_digest,
  scope: materializedRun.scope,
  target_id: materializedRun.target_id,
  target_type: "storage",
  lease_id: materializedRun.lease_id,
  lease_digest: materializedRun.lease_digest,
  fencing_token: materializedRun.fencing_token,
  materialized_by_subject_id: materializedRun.materialized_by_subject_id,
  created_at: "2026-08-13T10:05:00Z",
  state: "created",
  authority: { ...materializedRun.authority },
  grants_execution_authority: false,
  canonical_digest: "2".repeat(64),
};

const stagedDispatchIntent: WorkflowDispatchIntent = {
  dispatch_intent_id: "workflow-dispatch-intent.1234567890abcdef",
  plan_id: materializedAttempt.plan_id,
  plan_digest: materializedAttempt.plan_digest,
  run_id: materializedAttempt.run_id,
  run_digest: materializedAttempt.run_digest,
  step_run_id: materializedAttempt.step_run_id,
  step_run_digest: materializedAttempt.step_run_digest,
  step_id: materializedAttempt.step_id,
  attempt_id: materializedAttempt.attempt_id,
  attempt_digest: materializedAttempt.canonical_digest,
  attempt_number: 1,
  scope: materializedAttempt.scope,
  target_id: materializedAttempt.target_id,
  target_type: "storage",
  lease_id: materializedAttempt.lease_id,
  lease_digest: "3".repeat(64),
  fencing_token: materializedAttempt.fencing_token,
  worker_subject_id: "workload.workflow.worker",
  staged_at: "2026-08-13T10:07:00Z",
  state: "staged",
  authority: { ...materializedAttempt.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "4".repeat(64),
};

const pendingOutboxEntry: WorkflowDispatchOutboxEntry = {
  outbox_entry_id: "workflow-dispatch-outbox.1234567890abcdef",
  dispatch_intent_id: stagedDispatchIntent.dispatch_intent_id,
  dispatch_intent_digest: stagedDispatchIntent.canonical_digest,
  plan_id: stagedDispatchIntent.plan_id,
  plan_digest: stagedDispatchIntent.plan_digest,
  run_id: stagedDispatchIntent.run_id,
  run_digest: stagedDispatchIntent.run_digest,
  step_run_id: stagedDispatchIntent.step_run_id,
  step_run_digest: stagedDispatchIntent.step_run_digest,
  step_id: stagedDispatchIntent.step_id,
  attempt_id: stagedDispatchIntent.attempt_id,
  attempt_digest: stagedDispatchIntent.attempt_digest,
  attempt_number: 1,
  scope: stagedDispatchIntent.scope,
  target_id: stagedDispatchIntent.target_id,
  target_type: "storage",
  lease_id: stagedDispatchIntent.lease_id,
  lease_digest: stagedDispatchIntent.lease_digest,
  fencing_token: stagedDispatchIntent.fencing_token,
  worker_subject_id: stagedDispatchIntent.worker_subject_id,
  admitted_at: stagedDispatchIntent.staged_at,
  state: "pending_publication",
  authority: { ...stagedDispatchIntent.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "6".repeat(64),
};

const activePublicationLease: WorkflowDispatchOutboxPublicationLease = {
  publication_lease_id: "workflow-publication-lease.1234567890abcdef",
  outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
  outbox_entry_digest: pendingOutboxEntry.canonical_digest,
  dispatch_intent_id: pendingOutboxEntry.dispatch_intent_id,
  dispatch_intent_digest: pendingOutboxEntry.dispatch_intent_digest,
  plan_id: pendingOutboxEntry.plan_id,
  plan_digest: pendingOutboxEntry.plan_digest,
  run_id: pendingOutboxEntry.run_id,
  run_digest: pendingOutboxEntry.run_digest,
  step_run_id: pendingOutboxEntry.step_run_id,
  step_run_digest: pendingOutboxEntry.step_run_digest,
  step_id: pendingOutboxEntry.step_id,
  attempt_id: pendingOutboxEntry.attempt_id,
  attempt_digest: pendingOutboxEntry.attempt_digest,
  attempt_number: 1,
  scope: pendingOutboxEntry.scope,
  target_id: pendingOutboxEntry.target_id,
  target_type: "storage",
  orchestration_lease_id: pendingOutboxEntry.lease_id,
  orchestration_lease_digest: pendingOutboxEntry.lease_digest,
  orchestration_fencing_token: pendingOutboxEntry.fencing_token,
  publisher_subject_id: "workload.workflow.publisher",
  acquired_at: "2026-08-13T10:11:00Z",
  last_heartbeat_at: "2026-08-13T10:12:00Z",
  expires_at: "2026-08-13T10:20:00Z",
  publication_fencing_token: 1,
  state: "active",
  authority: { ...pendingOutboxEntry.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "7".repeat(64),
  effective_state: "active",
};

const preparedEventEnvelope: WorkflowDispatchEventEnvelope = {
  event_id: "workflow-event.1234567890abcdef",
  event_type: "WorkflowStepDispatchRequested",
  event_version: "1.0",
  producer: "atlas.workflow",
  producer_version: "1.0.0",
  occurred_at: pendingOutboxEntry.admitted_at,
  recorded_at: "2026-08-13T10:14:00Z",
  subject_type: "workflow-execution-attempt",
  subject_id: pendingOutboxEntry.attempt_id,
  organization_id: pendingOutboxEntry.scope.organization_id,
  environment_id: pendingOutboxEntry.scope.environment_id,
  correlation_id: pendingOutboxEntry.run_id,
  causation_id: pendingOutboxEntry.dispatch_intent_id,
  workflow_id: pendingOutboxEntry.run_id,
  data_classification: "internal",
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
  payload: {
    plan_id: pendingOutboxEntry.plan_id,
    plan_digest: pendingOutboxEntry.plan_digest,
    run_id: pendingOutboxEntry.run_id,
    run_digest: pendingOutboxEntry.run_digest,
    step_run_id: pendingOutboxEntry.step_run_id,
    step_run_digest: pendingOutboxEntry.step_run_digest,
    step_id: pendingOutboxEntry.step_id,
    attempt_id: pendingOutboxEntry.attempt_id,
    attempt_digest: pendingOutboxEntry.attempt_digest,
    attempt_number: pendingOutboxEntry.attempt_number,
    scope: pendingOutboxEntry.scope,
    target_id: pendingOutboxEntry.target_id,
    target_type: pendingOutboxEntry.target_type,
    dispatch_intent_id: pendingOutboxEntry.dispatch_intent_id,
    dispatch_intent_digest: pendingOutboxEntry.dispatch_intent_digest,
    outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
    outbox_entry_digest: pendingOutboxEntry.canonical_digest,
  },
  extensions: {},
  orchestration_lease_id: activePublicationLease.orchestration_lease_id,
  orchestration_lease_digest: activePublicationLease.orchestration_lease_digest,
  orchestration_fencing_token: activePublicationLease.orchestration_fencing_token,
  publication_lease_id: activePublicationLease.publication_lease_id,
  publication_lease_digest: activePublicationLease.canonical_digest,
  publication_fencing_token: activePublicationLease.publication_fencing_token,
  publisher_subject_id: activePublicationLease.publisher_subject_id,
  prepared_at: "2026-08-13T10:14:00Z",
  state: "prepared",
  authority: {
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "9".repeat(64),
};

const admittedTransport: WorkflowEventTransportAdmission = {
  transport_admission_id: "workflow-transport-admission.1234567890abcdef",
  event_id: preparedEventEnvelope.event_id,
  event_digest: preparedEventEnvelope.canonical_digest,
  outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
  outbox_entry_digest: pendingOutboxEntry.canonical_digest,
  dispatch_intent_id: pendingOutboxEntry.dispatch_intent_id,
  dispatch_intent_digest: pendingOutboxEntry.dispatch_intent_digest,
  plan_id: pendingOutboxEntry.plan_id,
  plan_digest: pendingOutboxEntry.plan_digest,
  run_id: pendingOutboxEntry.run_id,
  run_digest: pendingOutboxEntry.run_digest,
  step_run_id: pendingOutboxEntry.step_run_id,
  step_run_digest: pendingOutboxEntry.step_run_digest,
  step_id: pendingOutboxEntry.step_id,
  attempt_id: pendingOutboxEntry.attempt_id,
  attempt_digest: pendingOutboxEntry.attempt_digest,
  attempt_number: pendingOutboxEntry.attempt_number,
  scope: pendingOutboxEntry.scope,
  target_id: pendingOutboxEntry.target_id,
  target_type: pendingOutboxEntry.target_type,
  policy: {
    policy_id: "policy.workflow-event-transport-admission",
    policy_version: "1.0",
    policy_digest: "a".repeat(64),
    allowed_event_type: preparedEventEnvelope.event_type,
    allowed_event_version: preparedEventEnvelope.event_version,
    allowed_schema_uri: preparedEventEnvelope.schema_uri,
    allowed_data_classification: preparedEventEnvelope.data_classification,
    representation_name: "canonical-json",
    encoding: "utf-8",
    maximum_canonical_byte_count: 65_536,
  },
  canonical_byte_count: 2_048,
  publisher_subject_id: activePublicationLease.publisher_subject_id,
  orchestration_lease_id: preparedEventEnvelope.orchestration_lease_id,
  orchestration_lease_digest: preparedEventEnvelope.orchestration_lease_digest,
  orchestration_fencing_token: preparedEventEnvelope.orchestration_fencing_token,
  publication_lease_id: preparedEventEnvelope.publication_lease_id,
  publication_lease_digest: preparedEventEnvelope.publication_lease_digest,
  publication_fencing_token: preparedEventEnvelope.publication_fencing_token,
  admitted_at: "2026-08-13T10:16:00Z",
  state: "admitted",
  authority: { ...preparedEventEnvelope.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "b".repeat(64),
};

const materializedByteArtifact: WorkflowEventByteArtifact = {
  byte_artifact_id: "workflow-event-byte-artifact.1234567890abcdef",
  transport_admission_id: admittedTransport.transport_admission_id,
  transport_admission_digest: admittedTransport.canonical_digest,
  event_id: admittedTransport.event_id,
  event_digest: admittedTransport.event_digest,
  outbox_entry_id: admittedTransport.outbox_entry_id,
  outbox_entry_digest: admittedTransport.outbox_entry_digest,
  dispatch_intent_id: admittedTransport.dispatch_intent_id,
  dispatch_intent_digest: admittedTransport.dispatch_intent_digest,
  plan_id: admittedTransport.plan_id,
  plan_digest: admittedTransport.plan_digest,
  run_id: admittedTransport.run_id,
  run_digest: admittedTransport.run_digest,
  step_run_id: admittedTransport.step_run_id,
  step_run_digest: admittedTransport.step_run_digest,
  step_id: admittedTransport.step_id,
  attempt_id: admittedTransport.attempt_id,
  attempt_digest: admittedTransport.attempt_digest,
  attempt_number: admittedTransport.attempt_number,
  scope: admittedTransport.scope,
  target_id: admittedTransport.target_id,
  target_type: admittedTransport.target_type,
  policy_id: admittedTransport.policy.policy_id,
  policy_version: admittedTransport.policy.policy_version,
  policy_digest: admittedTransport.policy.policy_digest,
  representation_name: admittedTransport.policy.representation_name,
  encoding: admittedTransport.policy.encoding,
  media_type: "application/json",
  byte_count: admittedTransport.canonical_byte_count,
  content_sha256: "d".repeat(64),
  publisher_subject_id: admittedTransport.publisher_subject_id,
  orchestration_lease_id: admittedTransport.orchestration_lease_id,
  orchestration_lease_digest: admittedTransport.orchestration_lease_digest,
  orchestration_fencing_token: admittedTransport.orchestration_fencing_token,
  publication_lease_id: admittedTransport.publication_lease_id,
  publication_lease_digest: admittedTransport.publication_lease_digest,
  publication_fencing_token: admittedTransport.publication_fencing_token,
  materialized_at: "2026-08-13T10:18:00Z",
  state: "materialized",
  authority: { ...admittedTransport.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "e".repeat(64),
};

const logicalChannelBinding: WorkflowEventLogicalChannelBinding = {
  logical_channel_binding_id: "workflow-event-logical-channel-binding.1234567890abcdef",
  byte_artifact_id: materializedByteArtifact.byte_artifact_id,
  byte_artifact_digest: materializedByteArtifact.canonical_digest,
  content_sha256: materializedByteArtifact.content_sha256,
  byte_count: materializedByteArtifact.byte_count,
  transport_admission_id: materializedByteArtifact.transport_admission_id,
  transport_admission_digest: materializedByteArtifact.transport_admission_digest,
  event_id: materializedByteArtifact.event_id,
  event_digest: materializedByteArtifact.event_digest,
  outbox_entry_id: materializedByteArtifact.outbox_entry_id,
  outbox_entry_digest: materializedByteArtifact.outbox_entry_digest,
  dispatch_intent_id: materializedByteArtifact.dispatch_intent_id,
  dispatch_intent_digest: materializedByteArtifact.dispatch_intent_digest,
  plan_id: materializedByteArtifact.plan_id,
  plan_digest: materializedByteArtifact.plan_digest,
  run_id: materializedByteArtifact.run_id,
  run_digest: materializedByteArtifact.run_digest,
  step_run_id: materializedByteArtifact.step_run_id,
  step_run_digest: materializedByteArtifact.step_run_digest,
  step_id: materializedByteArtifact.step_id,
  attempt_id: materializedByteArtifact.attempt_id,
  attempt_digest: materializedByteArtifact.attempt_digest,
  attempt_number: materializedByteArtifact.attempt_number,
  scope: materializedByteArtifact.scope,
  target_id: materializedByteArtifact.target_id,
  target_type: materializedByteArtifact.target_type,
  policy_id: "policy.workflow-event-logical-channel",
  policy_version: "1.0",
  policy_digest: "f".repeat(64),
  logical_channel_id: "channel.workflow-dispatch.internal",
  logical_channel_version: "1.0",
  delivery_semantics: "at-least-once",
  durability_required: true,
  ordering_key_kind: "workflow-run",
  ordering_key_value: materializedByteArtifact.run_id,
  retention_class: "workflow-operational",
  publisher_subject_id: materializedByteArtifact.publisher_subject_id,
  orchestration_lease_id: materializedByteArtifact.orchestration_lease_id,
  orchestration_lease_digest: materializedByteArtifact.orchestration_lease_digest,
  orchestration_fencing_token: materializedByteArtifact.orchestration_fencing_token,
  publication_lease_id: materializedByteArtifact.publication_lease_id,
  publication_lease_digest: materializedByteArtifact.publication_lease_digest,
  publication_fencing_token: materializedByteArtifact.publication_fencing_token,
  bound_at: "2026-08-13T10:20:00Z",
  state: "bound",
  authority: { ...materializedByteArtifact.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "1".repeat(64),
};

const transportProfileSnapshot: WorkflowTransportProfileSnapshot = {
  snapshot_id: "workflow-transport-profile-snapshot.1234567890abcdef",
  transport_profile_id: "transport-profile.primary-event-backbone",
  transport_profile_revision: "revision.17",
  source_profile_digest: "2".repeat(64),
  deployment_release_id: "atlas-release.2026.08.14",
  deployment_profile: "enterprise-test",
  scope: { ...plan.scope },
  transport_resource_id: "transport-resource.event-backbone-primary",
  transport_resource_digest: "3".repeat(64),
  transport_implementation_id: "transport.apache-kafka",
  transport_implementation_version: "4.1.0",
  adapter_contract_id: "atlas-transport-adapter.kafka",
  adapter_contract_version: "1.0",
  adapter_contract_digest: "4".repeat(64),
  supported_event_contracts: [
    {
      event_type: "WorkflowStepDispatchRequested",
      event_version: "1.0",
      schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
    },
  ],
  supported_classifications: ["internal"],
  supported_representations: ["canonical-json"],
  supported_encodings: ["utf-8"],
  supported_delivery_semantics: ["at-least-once"],
  durable_delivery_supported: true,
  supported_ordering_key_kinds: ["workflow-run"],
  supported_retention_classes: ["workflow-operational"],
  maximum_message_byte_count: 65_536,
  transport_encryption_required: true,
  restricted_network_supported: true,
  snapshotter_subject_id: "workload.workflow.transport-profile-registry",
  captured_at: "2026-08-14T10:00:00Z",
  state: "snapshotted",
  authority: {
    route_selection_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  canonical_digest: "5".repeat(64),
};

const transportRouteSnapshot: WorkflowTransportRouteSnapshot = {
  snapshot_id: "workflow-transport-route-snapshot.1234567890abcdef",
  route_id: "transport-route.primary-event-backbone",
  route_revision: "revision.9",
  route_set_id: "transport-route-set.primary-event-backbone",
  route_set_revision: "revision.3",
  selection_epoch_id: "selection-epoch.primary-event-backbone",
  selection_epoch_revision: "revision.2",
  source_route_digest: "9".repeat(64),
  deployment_release_id: "atlas-release.2026.08.14",
  deployment_profile: "enterprise-test",
  scope: { ...plan.scope },
  transport_profile_id: transportProfileSnapshot.transport_profile_id,
  transport_profile_revision: transportProfileSnapshot.transport_profile_revision,
  transport_resource_id: transportProfileSnapshot.transport_resource_id,
  transport_implementation_id: transportProfileSnapshot.transport_implementation_id,
  transport_implementation_version: transportProfileSnapshot.transport_implementation_version,
  adapter_contract_id: transportProfileSnapshot.adapter_contract_id,
  adapter_contract_version: transportProfileSnapshot.adapter_contract_version,
  route_kind: "message-broker",
  endpoint_set_id: "opaque-endpoint-set.primary-event-backbone.internal",
  endpoint_set_revision: "revision.4",
  destination_id: "opaque-destination.workflow-dispatch.internal",
  destination_revision: "revision.12",
  routing_contract_id: "opaque-routing-contract.workflow-run-ordering.internal",
  routing_contract_revision: "revision.6",
  transport_security_policy_id: "policy.transport-security.internal-tls",
  transport_security_policy_version: "1.0",
  minimum_tls_version: "1.3",
  server_authentication_required: true,
  client_authentication_required: true,
  plaintext_fallback_prohibited: true,
  network_policy_id: "policy.transport-network.restricted-internal",
  network_policy_version: "1.0",
  source_zone_class: "zone.workload-internal",
  destination_zone_class: "zone.event-backbone-internal",
  restricted_network_enforced: true,
  public_egress_prohibited: true,
  proxy_mode: "prohibited",
  credential_requirement_profile_id: "policy.transport-credential.brokered-workload",
  credential_requirement_profile_version: "1.0",
  authentication_mechanism_class: "mutual-tls",
  principal_class: "service-workload",
  snapshotter_subject_id: "workload.workflow.transport-route-registry",
  captured_at: "2026-08-14T10:02:00Z",
  state: "snapshotted",
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    endpoint_resolution_authorized: false,
    credential_access_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  canonical_digest: "8".repeat(64),
};

const physicalTransportRouteBinding: WorkflowPhysicalTransportRouteBinding = {
  binding_id: "workflow-physical-transport-route-binding.1234567890abcdef",
  logical_channel_binding_id: logicalChannelBinding.logical_channel_binding_id,
  compatibility_admission_id:
    "workflow-transport-compatibility-admission.1234567890abcdef",
  transport_profile_snapshot_id: transportProfileSnapshot.snapshot_id,
  transport_route_snapshot_id: transportRouteSnapshot.snapshot_id,
  policy_id: "policy.workflow-physical-transport-route-binding",
  policy_version: "1.0",
  scope: { ...plan.scope },
  binder_subject_id: "workload.workflow-physical-route-binder",
  bound_at: "2026-08-14T10:06:00Z",
  state: "bound",
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    endpoint_resolution_authorized: false,
    credential_access_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  integrity_reference: "integrity-ref.workflow-physical-route-binding.1234567890abcdef",
};

const physicalTransportCredentialAssignmentBinding: WorkflowPhysicalTransportCredentialAssignmentBinding = {
  binding_id: "workflow-physical-transport-credential-assignment-binding.1234567890abcdef",
  physical_transport_route_binding_id: physicalTransportRouteBinding.binding_id,
  credential_assignment_snapshot_id:
    "workflow-credential-assignment-snapshot.1234567890abcdef",
  state: "bound",
  bound_at: "2026-08-14T10:08:00Z",
  integrity_reference:
    "integrity-ref.workflow-physical-transport-credential-assignment-binding.1234567890abcdef",
};

const physicalTransportCredentialAssignmentFreshnessAdmission: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmission = {
  freshness_admission_id:
    "workflow-physical-transport-credential-assignment-freshness-admission.1234567890abcdef",
  physical_transport_credential_assignment_binding_id:
    physicalTransportCredentialAssignmentBinding.binding_id,
  credential_assignment_snapshot_id:
    physicalTransportCredentialAssignmentBinding.credential_assignment_snapshot_id,
  assignment_id: "deployment-physical-transport-credential-assignment.1234567890abcdef",
  assignment_revision: "revision.7",
  credential_generation: 7,
  rotation_epoch: 3,
  policy_id: "policy.workflow-event-physical-transport-credential-assignment-freshness",
  policy_version: "1.0",
  scope: { ...plan.scope },
  admitter_subject_id:
    "workload.workflow-physical-transport-credential-assignment-freshness-admitter",
  evaluated_at: "2099-08-14T10:08:00Z",
  valid_until: "2099-08-14T10:08:45Z",
  state: "admitted_current",
  authority: {
    endpoint_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference:
    "integrity-ref.workflow-physical-transport-credential-assignment-freshness.1234567890abcdef",
};

const physicalTransportRouteFreshnessAdmission: WorkflowPhysicalTransportRouteFreshnessAdmission = {
  freshness_admission_id: "workflow-physical-route-freshness-admission.1234567890abcdef",
  physical_transport_route_binding_id: physicalTransportRouteBinding.binding_id,
  transport_route_snapshot_id: transportRouteSnapshot.snapshot_id,
  selection_head_id: "workflow-transport-route-selection-head.1234567890abcdef",
  selection_generation: 7,
  policy_id: "policy.workflow-event-physical-transport-route-freshness",
  policy_version: "1.0",
  scope: { ...plan.scope },
  admitter_subject_id: "workload.workflow-physical-route-freshness-admitter",
  evaluated_at: "2026-08-14T10:07:00Z",
  valid_until: "2026-08-14T10:08:00Z",
  state: "admitted_current",
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    endpoint_resolution_authorized: false,
    credential_access_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  integrity_reference: "integrity-ref.workflow-route-freshness.1234567890abcdef",
};

const endpointResolutionAuthorizationLease: WorkflowEndpointResolutionAuthorizationLease = {
  lease_id: "workflow-endpoint-resolution-authorization-lease.1234567890abcdef",
  freshness_admission_id: physicalTransportRouteFreshnessAdmission.freshness_admission_id,
  selection_generation: physicalTransportRouteFreshnessAdmission.selection_generation,
  policy_id: "policy.workflow-event-physical-transport-endpoint-resolution-authorization",
  policy_version: "1.0",
  scope: { ...plan.scope },
  resolver_subject_id: "workload.workflow-physical-transport-endpoint-resolver",
  authorized_at: "2026-08-14T10:07:30Z",
  expires_at: "2026-08-14T10:07:45Z",
  state: "authorized_unconsumed",
  effective_state: "active",
  single_use: true,
  renewable: false,
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    endpoint_resolution_authorized: true,
    credential_access_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  integrity_reference: "integrity.workflow-endpoint-resolution-lease.1234567890abcdef",
};

const consumedEndpointResolutionAuthorizationLease: WorkflowEndpointResolutionAuthorizationLease = {
  ...endpointResolutionAuthorizationLease,
  effective_state: "consumed",
};

const credentialAccessAuthorizationLease: WorkflowPhysicalTransportCredentialAccessAuthorizationLease = {
  lease_id: "workflow-credential-access-authorization-lease.1234567890abcdef",
  freshness_admission_id:
    physicalTransportCredentialAssignmentFreshnessAdmission.freshness_admission_id,
  assignment_revision:
    physicalTransportCredentialAssignmentFreshnessAdmission.assignment_revision,
  credential_generation:
    physicalTransportCredentialAssignmentFreshnessAdmission.credential_generation,
  rotation_epoch: physicalTransportCredentialAssignmentFreshnessAdmission.rotation_epoch,
  policy_id: "policy.workflow-event-credential-access-authorization.historical",
  policy_version: "0.9",
  scope: { ...plan.scope },
  accessor_subject_id: "workload.workflow-physical-transport-credential-accessor",
  issued_at: "2026-08-14T10:08:00Z",
  valid_until: "2026-08-14T10:08:15Z",
  state: "authorized_unconsumed",
  effective_state: "active",
  single_use: true,
  renewable: false,
  authority: {
    endpoint_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: true,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-credential-access-lease.1234567890abcdef",
};

const endpointMaterialization: WorkflowPhysicalTransportEndpointMaterialization = {
  materialization_id: "workflow-endpoint-materialization.1234567890abcdef",
  lease_id: endpointResolutionAuthorizationLease.lease_id,
  freshness_admission_id: endpointResolutionAuthorizationLease.freshness_admission_id,
  selection_generation: endpointResolutionAuthorizationLease.selection_generation,
  policy_id: "policy.workflow-event-physical-transport-endpoint-materialization",
  policy_version: "1.0",
  scope: { ...plan.scope },
  resolver_subject_id: endpointResolutionAuthorizationLease.resolver_subject_id,
  consumed_at: "2026-08-14T10:07:36Z",
  recorded_at: "2026-08-14T10:07:37Z",
  outcome: "materialized_protected",
  lease_consumed: true,
  protected_storage_verified: true,
  raw_endpoint_disclosed: false,
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    endpoint_resolution_authorized: false,
    credential_access_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  integrity_reference: "integrity.workflow-endpoint-materialization.1234567890abcdef",
};

const credentialMaterializationAuthority = {
  endpoint_resolution_authorized: false,
  protected_artifact_access_authorized: false,
  route_selection_authorized: false,
  route_binding_authorized: false,
  credential_selection_authorized: false,
  credential_assignment_binding_authorized: false,
  credential_access_authorized: false,
  credential_brokerage_authorized: false,
  credential_resolution_authorized: false,
  credential_delivery_authorized: false,
  network_access_authorized: false,
  readiness_probe_authorized: false,
  publication_authorized: false,
  delivery_authorized: false,
  dispatch_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_authorized: false,
} as const;

const credentialMaterialization: WorkflowPhysicalTransportCredentialMaterialization = {
  materialization_id: "workflow-credential-materialization.1234567890abcdef",
  lease_id: credentialAccessAuthorizationLease.lease_id,
  freshness_admission_id:
    physicalTransportCredentialAssignmentFreshnessAdmission.freshness_admission_id,
  assignment_revision:
    physicalTransportCredentialAssignmentFreshnessAdmission.assignment_revision,
  credential_generation:
    physicalTransportCredentialAssignmentFreshnessAdmission.credential_generation,
  rotation_epoch: physicalTransportCredentialAssignmentFreshnessAdmission.rotation_epoch,
  scope: { ...plan.scope },
  accessor_subject_id: credentialAccessAuthorizationLease.accessor_subject_id,
  policy_id: "policy.workflow-event-physical-transport-credential-materialization",
  policy_version: "1.0",
  consumed_at: "2026-08-14T10:08:06Z",
  recorded_at: "2026-08-14T10:08:08Z",
  outcome: "materialized_protected",
  lease_consumed: true,
  protected_storage_verified: true,
  raw_credential_disclosed: false,
  authority: credentialMaterializationAuthority,
  integrity_reference: "integrity.workflow-credential-materialization.1234567890abcdef",
};

const targetContextBindingAuthority = {
  endpoint_resolution_authorized: false,
  protected_artifact_access_authorized: false,
  route_selection_authorized: false,
  route_binding_authorized: false,
  credential_selection_authorized: false,
  credential_assignment_binding_authorized: false,
  credential_access_authorized: false,
  credential_brokerage_authorized: false,
  credential_resolution_authorized: false,
  credential_delivery_authorized: false,
  network_access_authorized: false,
  readiness_probe_authorized: false,
  publication_authorized: false,
  delivery_authorized: false,
  dispatch_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_authorized: false,
} as const;

const targetContextBinding: WorkflowPhysicalTransportTargetContextBinding = {
  binding_id: "workflow-target-context-binding.1234567890abcdef",
  endpoint_materialization_id: endpointMaterialization.materialization_id,
  credential_materialization_id: credentialMaterialization.materialization_id,
  state: "bound",
  effective_state: "active",
  scope: { ...plan.scope },
  binder_subject_id: "workload.workflow-target-context-binder",
  bound_at: "2026-08-14T10:08:09Z",
  joint_usable_until: "2026-08-14T10:09:00Z",
  policy_reference: "policy.workflow-event-physical-transport-target-context-binding:1.0",
  target_context_schema_reference: "schema.workflow-physical-transport-target-context:1.0",
  authority: targetContextBindingAuthority,
};

const targetContextAccessAuthorizationLease: WorkflowPhysicalTransportTargetContextAccessAuthorizationLease = {
  authorization_lease_id:
    "workflow-physical-transport-target-context-access-authorization-lease.1234567890abcdef",
  scope: { ...plan.scope },
  accessor_subject_id: "service.workflow-protected-transport-context-accessor",
  state: "authorized_unconsumed",
  effective_state: "active",
  issued_at: "2026-08-14T10:08:20Z",
  valid_until: "2026-08-14T10:08:25Z",
  single_use: true,
  renewable: false,
  transferable: false,
  policy: {
    policy_id: "policy.workflow-event-physical-transport-target-context-access-authorization",
    policy_version: "1.0",
  },
  authority: {
    endpoint_resolution_authorized: false,
    protected_artifact_access_authorized: true,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-target-context-access-lease.1234567890abcdef",
};

const targetContextArtifactOpening: WorkflowPhysicalTransportTargetContextArtifactOpening = {
  opening_id: "workflow-target-context-artifact-opening.1234567890abcdef",
  scope: { ...plan.scope },
  attempt_state: "completed",
  result_state: "opened_protected",
  started_at: "2026-08-14T10:08:23Z",
  completed_at: "2026-08-14T10:08:24Z",
  policy: {
    policy_id: "policy.workflow-event-physical-transport-target-context-artifact-opening",
    policy_version: "1.0",
  },
  authority: {
    endpoint_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-target-context-artifact-opening.1234567890abcdef",
};

const targetContextCapsuleConsumerBinding: WorkflowPhysicalTransportTargetContextCapsuleConsumerBinding = {
  binding_id: "workflow-target-context-capsule-consumer-binding.1234567890abcdef",
  scope: { ...plan.scope },
  state: "bound",
  bound_at: "2026-08-14T10:08:24Z",
  effective_until: "2026-08-14T10:08:27Z",
  consumer_contract_id: "contract.workflow-protected-transport-target-context-capsule-consumer",
  consumer_contract_version: "1.0",
  purpose_id: "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation",
  policy: {
    policy_id: "policy.workflow-protected-transport-target-context-capsule-consumer-binding",
    policy_version: "1.0",
  },
  authority: {
    endpoint_resolution_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-target-context-capsule-consumer-binding.1234567890abcdef",
};

const targetContextCapsuleHandoffAuthorizationLease: WorkflowPhysicalTransportTargetContextCapsuleHandoffAuthorizationLease = {
  authorization_lease_id:
    "workflow-target-context-capsule-handoff-authorization-lease.1234567890abcdef",
  scope: { ...plan.scope },
  consumer_contract_id: "contract.workflow-protected-transport-target-context-capsule-consumer",
  consumer_contract_version: "1.0",
  purpose_id: "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation",
  state: "authorized_unconsumed",
  effective_state: "active",
  issued_at: "2026-08-14T10:08:25Z",
  valid_until: "2026-08-14T10:08:26Z",
  single_use: true,
  renewable: false,
  transferable: false,
  lease_is_bearer_capability: false,
  policy: {
    policy_id:
      "policy.workflow-protected-transport-target-context-capsule-handoff-authorization",
    policy_version: "1.0",
  },
  authority: {
    target_context_capsule_handoff_authorized: true,
    endpoint_resolution_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-target-context-capsule-handoff-lease.1234567890abcdef",
};

const targetContextCapsuleHandoff: WorkflowPhysicalTransportTargetContextCapsuleHandoff = {
  handoff_id: "workflow-target-context-capsule-handoff.1234567890abcdef",
  scope: { ...plan.scope },
  attempt_state: "completed",
  result_state: "handed_off_sealed",
  started_at: "2026-08-14T10:08:25.250Z",
  completed_at: "2026-08-14T10:08:25.500Z",
  consumer_contract_id: "contract.workflow-protected-transport-target-context-capsule-consumer",
  consumer_contract_version: "1.0",
  purpose_id: "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation",
  adapter_contract_id: "adapter.workflow-protected-target-context-capsule-handoff",
  adapter_contract_version: "1.0",
  sealed_capsule_handed_off: true,
  consumer_receipt_is_bearer_capability: false,
  policy: {
    policy_id: "policy.workflow-protected-transport-target-context-capsule-handoff-consumption",
    policy_version: "1.0",
  },
  authority: {
    target_context_capsule_handoff_authorized: false,
    endpoint_resolution_authorized: false,
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_selection_authorized: false,
    credential_assignment_binding_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
  integrity_reference: "integrity.workflow-target-context-capsule-handoff.1234567890abcdef",
};

const credentialAssignmentSnapshot: WorkflowPhysicalTransportCredentialAssignmentSnapshot = {
  snapshot_id: "workflow-credential-assignment-snapshot.1234567890abcdef",
  assignment_id: "deployment-credential-assignment.1234567890abcdef",
  assignment_revision: "revision.9",
  credential_generation: 12,
  rotation_epoch: 4,
  activated_at: "2026-08-14T08:00:00Z",
  expires_at: "2026-09-14T08:00:00Z",
  captured_at: "2026-08-14T10:07:20Z",
  state: "snapshotted",
  authority: {
    endpoint_resolution_authorized: false,
    protected_artifact_access_authorized: false,
    credential_selection_authorized: false,
    credential_access_authorized: false,
    credential_brokerage_authorized: false,
    credential_resolution_authorized: false,
    credential_delivery_authorized: false,
    network_access_authorized: false,
    readiness_probe_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
};

const transportCompatibilityAdmission: WorkflowTransportCompatibilityAdmission = {
  compatibility_admission_id:
    "workflow-transport-compatibility-admission.1234567890abcdef",
  logical_channel_binding_id: logicalChannelBinding.logical_channel_binding_id,
  logical_channel_binding_digest: logicalChannelBinding.canonical_digest,
  transport_profile_snapshot_id: transportProfileSnapshot.snapshot_id,
  transport_profile_snapshot_digest: transportProfileSnapshot.canonical_digest,
  transport_profile_id: transportProfileSnapshot.transport_profile_id,
  transport_profile_revision: transportProfileSnapshot.transport_profile_revision,
  policy_id: "policy.workflow-event-transport-compatibility",
  policy_version: "1.0",
  policy_digest: "6".repeat(64),
  scope: { ...logicalChannelBinding.scope },
  event_type: "WorkflowStepDispatchRequested",
  event_version: "1.0",
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
  data_classification: "internal",
  representation_name: "canonical-json",
  encoding: "utf-8",
  delivery_semantics: logicalChannelBinding.delivery_semantics,
  durability_required: logicalChannelBinding.durability_required,
  ordering_key_kind: logicalChannelBinding.ordering_key_kind,
  retention_class: logicalChannelBinding.retention_class,
  logical_maximum_byte_count: 65_536,
  artifact_byte_count: logicalChannelBinding.byte_count,
  profile_maximum_message_byte_count:
    transportProfileSnapshot.maximum_message_byte_count,
  admitter_subject_id: "workload.workflow.transport-compatibility-admitter",
  admitted_at: "2026-08-14T10:03:00Z",
  state: "admitted",
  authority: {
    route_selection_authorized: false,
    route_binding_authorized: false,
    credential_access_authorized: false,
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  canonical_digest: "7".repeat(64),
};

function leaseResponse(lease: WorkflowOrchestrationLease | null, status = 200): Response {
  return new Response(
    JSON.stringify({
      data: {
        plan_id: plan.plan_id,
        server_time: "2026-08-13T10:03:00Z",
        durable: false,
        lease,
      },
      meta: {
        correlation_id: "correlation.workflow.lease",
        generated_at: "2026-08-13T10:03:00Z",
      },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function materializedRunResponse(run: WorkflowExecutionRun | null, status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            plan_id: plan.plan_id,
            run,
            server_time: "2026-08-13T10:04:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.run",
            generated_at: "2026-08-13T10:04:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function attemptResponse(attempts: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            run_id: materializedRun.run_id,
            attempts,
            server_time: "2026-08-13T10:06:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.attempt",
            generated_at: "2026-08-13T10:06:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function dispatchIntentResponse(dispatchIntents: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            attempt_id: materializedAttempt.attempt_id,
            dispatch_intents: dispatchIntents,
            server_time: "2026-08-13T10:08:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.dispatch-intent",
            generated_at: "2026-08-13T10:08:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function outboxResponse(outboxEntries: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            dispatch_intent_id: stagedDispatchIntent.dispatch_intent_id,
            outbox_entries: outboxEntries,
            server_time: "2026-08-13T10:10:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.dispatch-outbox",
            generated_at: "2026-08-13T10:10:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function publicationLeaseResponse(publicationLeases: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
            publication_leases: publicationLeases,
            server_time: "2026-08-13T10:13:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.publication-lease",
            generated_at: "2026-08-13T10:13:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function eventEnvelopeResponse(eventEnvelopes: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
            event_envelopes: eventEnvelopes,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.event-envelope",
            generated_at: "2026-08-13T10:15:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function transportAdmissionResponse(transportAdmissions: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            event_id: preparedEventEnvelope.event_id,
            transport_admissions: transportAdmissions,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.transport-admission",
            generated_at: "2026-08-13T10:17:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function byteArtifactResponse(byteArtifacts: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            transport_admission_id: admittedTransport.transport_admission_id,
            byte_artifacts: byteArtifacts,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.byte-artifact",
            generated_at: "2026-08-13T10:19:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function logicalChannelBindingResponse(
  logicalChannelBindings: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            byte_artifact_id: materializedByteArtifact.byte_artifact_id,
            logical_channel_bindings: logicalChannelBindings,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.logical-channel-binding",
            generated_at: "2026-08-13T10:21:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function transportProfileSnapshotResponse(
  snapshots: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: { transport_profile_snapshots: snapshots, durable: false },
          meta: {
            correlation_id: "correlation.workflow.transport-profile-snapshot",
            generated_at: "2026-08-14T10:01:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function transportRouteSnapshotResponse(snapshots: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: { transport_route_snapshots: snapshots, durable: false },
          meta: {
            correlation_id: "correlation.workflow.transport-route-snapshot",
            generated_at: "2026-08-14T10:02:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function physicalTransportRouteBindingResponse(bindings: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: { physical_transport_route_bindings: bindings, durable: false },
          meta: {
            correlation_id: "correlation.workflow.physical-transport-route-binding",
            generated_at: "2026-08-14T10:06:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function physicalTransportCredentialAssignmentBindingResponse(
  bindings: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_credential_assignment_bindings: bindings,
            durable: false,
          },
          meta: {
            correlation_id:
              "correlation.workflow.physical-transport-credential-assignment-binding",
            generated_at: "2026-08-14T10:08:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function physicalTransportCredentialAssignmentFreshnessAdmissionResponse(
  admissions: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_credential_assignment_freshness_admissions: admissions,
            durable: false,
          },
          meta: {
            correlation_id:
              "correlation.workflow.physical-transport-credential-assignment-freshness-admission",
            generated_at: "2099-08-14T10:08:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function physicalTransportRouteFreshnessAdmissionResponse(
  admissions: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_route_freshness_admissions: admissions,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.physical-route-freshness-admission",
            generated_at: "2026-08-14T10:07:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function endpointResolutionAuthorizationLeaseResponse(
  leases: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:07:35Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            endpoint_resolution_authorization_leases: leases,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.endpoint-resolution-authorization-lease",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function credentialAccessAuthorizationLeaseResponse(
  leases: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:05Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_credential_access_authorization_leases: leases,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.credential-access-authorization-lease",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function endpointMaterializationResponse(
  materializations: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:07:40Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_endpoint_materializations: materializations,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.endpoint-materialization",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function credentialMaterializationResponse(
  materializations: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:20Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_credential_materializations: materializations,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.credential-materialization",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextBindingResponse(
  bindings: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:20Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_bindings: bindings,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.target-context-binding",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextAccessAuthorizationLeaseResponse(
  leases: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:22Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_access_authorization_leases: leases,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.target-context-access-authorization-lease",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextArtifactOpeningResponse(
  openings: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:25Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_artifact_openings: openings,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.target-context-artifact-opening",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextCapsuleConsumerBindingResponse(
  bindings: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:25Z",
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_capsule_consumer_bindings: bindings,
            server_time: serverTime,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.target-context-capsule-consumer-binding",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextCapsuleHandoffAuthorizationLeaseResponse(
  leases: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:25.500Z",
  durable = true,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_capsule_handoff_authorization_leases: leases,
            server_time: serverTime,
            durable,
          },
          meta: {
            correlation_id:
              "correlation.workflow.target-context-capsule-handoff-authorization-lease",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function targetContextCapsuleHandoffResponse(
  handoffs: unknown[],
  status = 200,
  serverTime = "2026-08-14T10:08:26Z",
  durable = true,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            physical_transport_target_context_capsule_handoffs: handoffs,
            server_time: serverTime,
            durable,
          },
          meta: {
            correlation_id: "correlation.workflow.target-context-capsule-handoff",
            generated_at: serverTime,
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function credentialAssignmentSnapshotResponse(
  snapshots: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            transport_credential_assignment_snapshots: snapshots,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.credential-assignment-snapshot",
            generated_at: "2026-08-14T10:07:40Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function transportCompatibilityAdmissionResponse(
  admissions: unknown[],
  status = 200,
): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            logical_channel_binding_id: logicalChannelBinding.logical_channel_binding_id,
            transport_compatibility_admissions: admissions,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.transport-compatibility-admission",
            generated_at: "2026-08-14T10:04:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function mockReadResponses(input: {
  lease?: WorkflowOrchestrationLease | null;
  run?: WorkflowExecutionRun | null;
  attempts?: unknown[];
  dispatchIntents?: unknown[];
  outboxEntries?: unknown[];
  publicationLeases?: unknown[];
  eventEnvelopes?: unknown[];
  transportAdmissions?: unknown[];
  byteArtifacts?: unknown[];
  logicalChannelBindings?: unknown[];
  transportProfileSnapshots?: unknown[];
  transportRouteSnapshots?: unknown[];
  physicalTransportRouteBindings?: unknown[];
  physicalTransportCredentialAssignmentBindings?: unknown[];
  physicalTransportCredentialAssignmentFreshnessAdmissions?: unknown[];
  credentialAccessAuthorizationLeases?: unknown[];
  credentialAccessAuthorizationLeaseServerTime?: string;
  physicalTransportRouteFreshnessAdmissions?: unknown[];
  endpointResolutionAuthorizationLeases?: unknown[];
  endpointResolutionAuthorizationLeaseServerTime?: string;
  endpointMaterializations?: unknown[];
  endpointMaterializationServerTime?: string;
  credentialMaterializations?: unknown[];
  credentialMaterializationServerTime?: string;
  targetContextBindings?: unknown[];
  targetContextBindingServerTime?: string;
  targetContextAccessAuthorizationLeases?: unknown[];
  targetContextAccessAuthorizationLeaseServerTime?: string;
  targetContextArtifactOpenings?: unknown[];
  targetContextArtifactOpeningServerTime?: string;
  targetContextCapsuleConsumerBindings?: unknown[];
  targetContextCapsuleConsumerBindingServerTime?: string;
  targetContextCapsuleHandoffAuthorizationLeases?: unknown[];
  targetContextCapsuleHandoffAuthorizationLeaseServerTime?: string;
  targetContextCapsuleHandoffAuthorizationLeaseDurable?: boolean;
  targetContextCapsuleHandoffs?: unknown[];
  targetContextCapsuleHandoffServerTime?: string;
  targetContextCapsuleHandoffDurable?: boolean;
  credentialAssignmentSnapshots?: unknown[];
  transportCompatibilityAdmissions?: unknown[];
  pendingTransportAdmissionResponse?: Promise<Response>;
  pendingByteArtifactResponse?: Promise<Response>;
  pendingLogicalChannelBindingResponse?: Promise<Response>;
  pendingTransportProfileResponse?: Promise<Response>;
  pendingTransportRouteSnapshotResponse?: Promise<Response>;
  pendingPhysicalTransportRouteBindingResponse?: Promise<Response>;
  pendingPhysicalTransportCredentialAssignmentBindingResponse?: Promise<Response>;
  pendingPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse?: Promise<Response>;
  pendingCredentialAccessAuthorizationLeaseResponse?: Promise<Response>;
  pendingPhysicalTransportRouteFreshnessAdmissionResponse?: Promise<Response>;
  pendingEndpointResolutionAuthorizationLeaseResponse?: Promise<Response>;
  pendingEndpointMaterializationResponse?: Promise<Response>;
  pendingCredentialMaterializationResponse?: Promise<Response>;
  pendingTargetContextBindingResponse?: Promise<Response>;
  pendingTargetContextAccessAuthorizationLeaseResponse?: Promise<Response>;
  pendingTargetContextArtifactOpeningResponse?: Promise<Response>;
  pendingTargetContextCapsuleConsumerBindingResponse?: Promise<Response>;
  pendingTargetContextCapsuleHandoffAuthorizationLeaseResponse?: Promise<Response>;
  pendingTargetContextCapsuleHandoffResponse?: Promise<Response>;
  pendingCredentialAssignmentSnapshotResponse?: Promise<Response>;
  pendingTransportCompatibilityAdmissionResponse?: Promise<Response>;
  leaseStatus?: number;
  runStatus?: number;
  attemptStatus?: number;
  dispatchIntentStatus?: number;
  outboxStatus?: number;
  publicationLeaseStatus?: number;
  eventEnvelopeStatus?: number;
  transportAdmissionStatus?: number;
  transportAdmissionStatuses?: number[];
  byteArtifactStatus?: number;
  byteArtifactStatuses?: number[];
  logicalChannelBindingStatus?: number;
  logicalChannelBindingStatuses?: number[];
  transportProfileStatus?: number;
  transportProfileStatuses?: number[];
  transportRouteSnapshotStatus?: number;
  transportRouteSnapshotStatuses?: number[];
  physicalTransportRouteBindingStatus?: number;
  physicalTransportRouteBindingStatuses?: number[];
  physicalTransportCredentialAssignmentBindingStatus?: number;
  physicalTransportCredentialAssignmentBindingStatuses?: number[];
  physicalTransportCredentialAssignmentFreshnessAdmissionStatus?: number;
  physicalTransportCredentialAssignmentFreshnessAdmissionStatuses?: number[];
  credentialAccessAuthorizationLeaseStatus?: number;
  credentialAccessAuthorizationLeaseStatuses?: number[];
  physicalTransportRouteFreshnessAdmissionStatus?: number;
  physicalTransportRouteFreshnessAdmissionStatuses?: number[];
  endpointResolutionAuthorizationLeaseStatus?: number;
  endpointResolutionAuthorizationLeaseStatuses?: number[];
  endpointMaterializationStatus?: number;
  endpointMaterializationStatuses?: number[];
  credentialMaterializationStatus?: number;
  credentialMaterializationStatuses?: number[];
  targetContextBindingStatus?: number;
  targetContextBindingStatuses?: number[];
  targetContextAccessAuthorizationLeaseStatus?: number;
  targetContextAccessAuthorizationLeaseStatuses?: number[];
  targetContextArtifactOpeningStatus?: number;
  targetContextArtifactOpeningStatuses?: number[];
  targetContextCapsuleConsumerBindingStatus?: number;
  targetContextCapsuleConsumerBindingStatuses?: number[];
  targetContextCapsuleHandoffAuthorizationLeaseStatus?: number;
  targetContextCapsuleHandoffAuthorizationLeaseStatuses?: number[];
  targetContextCapsuleHandoffStatus?: number;
  targetContextCapsuleHandoffStatuses?: number[];
  credentialAssignmentSnapshotStatus?: number;
  credentialAssignmentSnapshotStatuses?: number[];
  transportCompatibilityAdmissionStatus?: number;
  transportCompatibilityAdmissionStatuses?: number[];
}) {
  let transportAdmissionReadCount = 0;
  let byteArtifactReadCount = 0;
  let logicalChannelBindingReadCount = 0;
  let transportProfileReadCount = 0;
  let transportRouteSnapshotReadCount = 0;
  let physicalTransportRouteBindingReadCount = 0;
  let physicalTransportCredentialAssignmentBindingReadCount = 0;
  let physicalTransportCredentialAssignmentFreshnessAdmissionReadCount = 0;
  let credentialAccessAuthorizationLeaseReadCount = 0;
  let physicalTransportRouteFreshnessAdmissionReadCount = 0;
  let endpointResolutionAuthorizationLeaseReadCount = 0;
  let endpointMaterializationReadCount = 0;
  let credentialMaterializationReadCount = 0;
  let targetContextBindingReadCount = 0;
  let targetContextAccessAuthorizationLeaseReadCount = 0;
  let targetContextArtifactOpeningReadCount = 0;
  let targetContextCapsuleConsumerBindingReadCount = 0;
  let targetContextCapsuleHandoffAuthorizationLeaseReadCount = 0;
  let targetContextCapsuleHandoffReadCount = 0;
  let credentialAssignmentSnapshotReadCount = 0;
  let transportCompatibilityAdmissionReadCount = 0;
  vi.mocked(fetch).mockImplementation((request) => {
    const url = request instanceof Request ? request.url : request.toString();
    if (url.endsWith("/api/v1/workflows/physical-transport-target-context-capsule-handoffs")) {
      if (input.pendingTargetContextCapsuleHandoffResponse) {
        return input.pendingTargetContextCapsuleHandoffResponse;
      }
      const status =
        input.targetContextCapsuleHandoffStatuses?.[
          Math.min(
            targetContextCapsuleHandoffReadCount++,
            input.targetContextCapsuleHandoffStatuses.length - 1,
          )
        ] ?? input.targetContextCapsuleHandoffStatus ?? 200;
      return Promise.resolve(
        targetContextCapsuleHandoffResponse(
          input.targetContextCapsuleHandoffs ?? [],
          status,
          input.targetContextCapsuleHandoffServerTime,
          input.targetContextCapsuleHandoffDurable,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-target-context-capsule-handoff-authorization-leases",
      )
    ) {
      if (input.pendingTargetContextCapsuleHandoffAuthorizationLeaseResponse) {
        return input.pendingTargetContextCapsuleHandoffAuthorizationLeaseResponse;
      }
      const status =
        input.targetContextCapsuleHandoffAuthorizationLeaseStatuses?.[
          Math.min(
            targetContextCapsuleHandoffAuthorizationLeaseReadCount++,
            input.targetContextCapsuleHandoffAuthorizationLeaseStatuses.length - 1,
          )
        ] ?? input.targetContextCapsuleHandoffAuthorizationLeaseStatus ?? 200;
      return Promise.resolve(
        targetContextCapsuleHandoffAuthorizationLeaseResponse(
          input.targetContextCapsuleHandoffAuthorizationLeases ?? [],
          status,
          input.targetContextCapsuleHandoffAuthorizationLeaseServerTime,
          input.targetContextCapsuleHandoffAuthorizationLeaseDurable,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-target-context-capsule-consumer-bindings",
      )
    ) {
      if (input.pendingTargetContextCapsuleConsumerBindingResponse) {
        return input.pendingTargetContextCapsuleConsumerBindingResponse;
      }
      const status =
        input.targetContextCapsuleConsumerBindingStatuses?.[
          Math.min(
            targetContextCapsuleConsumerBindingReadCount++,
            input.targetContextCapsuleConsumerBindingStatuses.length - 1,
          )
        ] ?? input.targetContextCapsuleConsumerBindingStatus ?? 200;
      return Promise.resolve(
        targetContextCapsuleConsumerBindingResponse(
          input.targetContextCapsuleConsumerBindings ?? [],
          status,
          input.targetContextCapsuleConsumerBindingServerTime,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-target-context-artifact-openings",
      )
    ) {
      if (input.pendingTargetContextArtifactOpeningResponse) {
        return input.pendingTargetContextArtifactOpeningResponse;
      }
      const status =
        input.targetContextArtifactOpeningStatuses?.[
          Math.min(
            targetContextArtifactOpeningReadCount++,
            input.targetContextArtifactOpeningStatuses.length - 1,
          )
        ] ?? input.targetContextArtifactOpeningStatus ?? 200;
      return Promise.resolve(
        targetContextArtifactOpeningResponse(
          input.targetContextArtifactOpenings ?? [],
          status,
          input.targetContextArtifactOpeningServerTime,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-target-context-access-authorization-leases",
      )
    ) {
      if (input.pendingTargetContextAccessAuthorizationLeaseResponse) {
        return input.pendingTargetContextAccessAuthorizationLeaseResponse;
      }
      const status =
        input.targetContextAccessAuthorizationLeaseStatuses?.[
          Math.min(
            targetContextAccessAuthorizationLeaseReadCount++,
            input.targetContextAccessAuthorizationLeaseStatuses.length - 1,
          )
        ] ?? input.targetContextAccessAuthorizationLeaseStatus ?? 200;
      return Promise.resolve(
        targetContextAccessAuthorizationLeaseResponse(
          input.targetContextAccessAuthorizationLeases ?? [],
          status,
          input.targetContextAccessAuthorizationLeaseServerTime,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/physical-transport-target-context-bindings")) {
      if (input.pendingTargetContextBindingResponse) {
        return input.pendingTargetContextBindingResponse;
      }
      const status =
        input.targetContextBindingStatuses?.[
          Math.min(
            targetContextBindingReadCount++,
            input.targetContextBindingStatuses.length - 1,
          )
        ] ?? input.targetContextBindingStatus ?? 200;
      return Promise.resolve(
        targetContextBindingResponse(
          input.targetContextBindings ?? [],
          status,
          input.targetContextBindingServerTime,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/physical-transport-credential-materializations")) {
      if (input.pendingCredentialMaterializationResponse) {
        return input.pendingCredentialMaterializationResponse;
      }
      const status =
        input.credentialMaterializationStatuses?.[
          Math.min(
            credentialMaterializationReadCount++,
            input.credentialMaterializationStatuses.length - 1,
          )
        ] ?? input.credentialMaterializationStatus ?? 200;
      return Promise.resolve(
        credentialMaterializationResponse(
          input.credentialMaterializations ?? [],
          status,
          input.credentialMaterializationServerTime,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-credential-access-authorization-leases",
      )
    ) {
      if (input.pendingCredentialAccessAuthorizationLeaseResponse) {
        return input.pendingCredentialAccessAuthorizationLeaseResponse;
      }
      const status =
        input.credentialAccessAuthorizationLeaseStatuses?.[
          Math.min(
            credentialAccessAuthorizationLeaseReadCount++,
            input.credentialAccessAuthorizationLeaseStatuses.length - 1,
          )
        ] ?? input.credentialAccessAuthorizationLeaseStatus ?? 200;
      return Promise.resolve(
        credentialAccessAuthorizationLeaseResponse(
          input.credentialAccessAuthorizationLeases ?? [],
          status,
          input.credentialAccessAuthorizationLeaseServerTime,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/transport-credential-assignment-snapshots")) {
      if (input.pendingCredentialAssignmentSnapshotResponse) {
        return input.pendingCredentialAssignmentSnapshotResponse;
      }
      const status =
        input.credentialAssignmentSnapshotStatuses?.[
          Math.min(
            credentialAssignmentSnapshotReadCount++,
            input.credentialAssignmentSnapshotStatuses.length - 1,
          )
        ] ?? input.credentialAssignmentSnapshotStatus ?? 200;
      return Promise.resolve(
        credentialAssignmentSnapshotResponse(
          input.credentialAssignmentSnapshots ?? [],
          status,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/physical-transport-endpoint-materializations")) {
      if (input.pendingEndpointMaterializationResponse) {
        return input.pendingEndpointMaterializationResponse;
      }
      const status =
        input.endpointMaterializationStatuses?.[
          Math.min(
            endpointMaterializationReadCount++,
            input.endpointMaterializationStatuses.length - 1,
          )
        ] ?? input.endpointMaterializationStatus ?? 200;
      return Promise.resolve(
        endpointMaterializationResponse(
          input.endpointMaterializations ?? [],
          status,
          input.endpointMaterializationServerTime,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-endpoint-resolution-authorization-leases",
      )
    ) {
      if (input.pendingEndpointResolutionAuthorizationLeaseResponse) {
        return input.pendingEndpointResolutionAuthorizationLeaseResponse;
      }
      const status =
        input.endpointResolutionAuthorizationLeaseStatuses?.[
          Math.min(
            endpointResolutionAuthorizationLeaseReadCount++,
            input.endpointResolutionAuthorizationLeaseStatuses.length - 1,
          )
        ] ?? input.endpointResolutionAuthorizationLeaseStatus ?? 200;
      return Promise.resolve(
        endpointResolutionAuthorizationLeaseResponse(
          input.endpointResolutionAuthorizationLeases ?? [],
          status,
          input.endpointResolutionAuthorizationLeaseServerTime,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/physical-transport-route-freshness-admissions")) {
      if (input.pendingPhysicalTransportRouteFreshnessAdmissionResponse) {
        return input.pendingPhysicalTransportRouteFreshnessAdmissionResponse;
      }
      const status =
        input.physicalTransportRouteFreshnessAdmissionStatuses?.[
          Math.min(
            physicalTransportRouteFreshnessAdmissionReadCount++,
            input.physicalTransportRouteFreshnessAdmissionStatuses.length - 1,
          )
        ] ?? input.physicalTransportRouteFreshnessAdmissionStatus ?? 200;
      return Promise.resolve(
        physicalTransportRouteFreshnessAdmissionResponse(
          input.physicalTransportRouteFreshnessAdmissions ?? [],
          status,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-credential-assignment-freshness-admissions",
      )
    ) {
      if (input.pendingPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse) {
        return input.pendingPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse;
      }
      const status =
        input.physicalTransportCredentialAssignmentFreshnessAdmissionStatuses?.[
          Math.min(
            physicalTransportCredentialAssignmentFreshnessAdmissionReadCount++,
            input.physicalTransportCredentialAssignmentFreshnessAdmissionStatuses.length - 1,
          )
        ] ?? input.physicalTransportCredentialAssignmentFreshnessAdmissionStatus ?? 200;
      return Promise.resolve(
        physicalTransportCredentialAssignmentFreshnessAdmissionResponse(
          input.physicalTransportCredentialAssignmentFreshnessAdmissions ?? [],
          status,
        ),
      );
    }
    if (
      url.endsWith(
        "/api/v1/workflows/physical-transport-credential-assignment-bindings",
      )
    ) {
      if (input.pendingPhysicalTransportCredentialAssignmentBindingResponse) {
        return input.pendingPhysicalTransportCredentialAssignmentBindingResponse;
      }
      const status =
        input.physicalTransportCredentialAssignmentBindingStatuses?.[
          Math.min(
            physicalTransportCredentialAssignmentBindingReadCount++,
            input.physicalTransportCredentialAssignmentBindingStatuses.length - 1,
          )
        ] ?? input.physicalTransportCredentialAssignmentBindingStatus ?? 200;
      return Promise.resolve(
        physicalTransportCredentialAssignmentBindingResponse(
          input.physicalTransportCredentialAssignmentBindings ?? [],
          status,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/physical-transport-route-bindings")) {
      if (input.pendingPhysicalTransportRouteBindingResponse) {
        return input.pendingPhysicalTransportRouteBindingResponse;
      }
      const status =
        input.physicalTransportRouteBindingStatuses?.[
          Math.min(
            physicalTransportRouteBindingReadCount++,
            input.physicalTransportRouteBindingStatuses.length - 1,
          )
        ] ?? input.physicalTransportRouteBindingStatus ?? 200;
      return Promise.resolve(
        physicalTransportRouteBindingResponse(
          input.physicalTransportRouteBindings ?? [],
          status,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/transport-route-snapshots")) {
      if (input.pendingTransportRouteSnapshotResponse) {
        return input.pendingTransportRouteSnapshotResponse;
      }
      const status =
        input.transportRouteSnapshotStatuses?.[
          Math.min(
            transportRouteSnapshotReadCount++,
            input.transportRouteSnapshotStatuses.length - 1,
          )
        ] ?? input.transportRouteSnapshotStatus ?? 200;
      return Promise.resolve(
        transportRouteSnapshotResponse(input.transportRouteSnapshots ?? [], status),
      );
    }
    if (url.includes("/api/v1/workflows/transport-compatibility-admissions?")) {
      if (input.pendingTransportCompatibilityAdmissionResponse) {
        return input.pendingTransportCompatibilityAdmissionResponse;
      }
      const status =
        input.transportCompatibilityAdmissionStatuses?.[
          Math.min(
            transportCompatibilityAdmissionReadCount++,
            input.transportCompatibilityAdmissionStatuses.length - 1,
          )
        ] ?? input.transportCompatibilityAdmissionStatus ?? 200;
      return Promise.resolve(
        transportCompatibilityAdmissionResponse(
          input.transportCompatibilityAdmissions ?? [],
          status,
        ),
      );
    }
    if (url.endsWith("/api/v1/workflows/transport-profile-snapshots")) {
      if (input.pendingTransportProfileResponse) return input.pendingTransportProfileResponse;
      const status =
        input.transportProfileStatuses?.[
          Math.min(transportProfileReadCount++, input.transportProfileStatuses.length - 1)
        ] ?? input.transportProfileStatus ?? 200;
      return Promise.resolve(
        transportProfileSnapshotResponse(input.transportProfileSnapshots ?? [], status),
      );
    }
    if (url.endsWith("/logical-channel-binding")) {
      if (input.pendingLogicalChannelBindingResponse) {
        return input.pendingLogicalChannelBindingResponse;
      }
      const status =
        input.logicalChannelBindingStatuses?.[
          Math.min(
            logicalChannelBindingReadCount++,
            input.logicalChannelBindingStatuses.length - 1,
          )
        ] ?? input.logicalChannelBindingStatus ?? 200;
      return Promise.resolve(
        logicalChannelBindingResponse(input.logicalChannelBindings ?? [], status),
      );
    }
    if (url.endsWith("/byte-artifact")) {
      if (input.pendingByteArtifactResponse) {
        return input.pendingByteArtifactResponse;
      }
      const status =
        input.byteArtifactStatuses?.[
          Math.min(byteArtifactReadCount++, input.byteArtifactStatuses.length - 1)
        ] ?? input.byteArtifactStatus ?? 200;
      return Promise.resolve(byteArtifactResponse(input.byteArtifacts ?? [], status));
    }
    if (url.endsWith("/transport-admission")) {
      if (input.pendingTransportAdmissionResponse) {
        return input.pendingTransportAdmissionResponse;
      }
      const status =
        input.transportAdmissionStatuses?.[
          Math.min(transportAdmissionReadCount++, input.transportAdmissionStatuses.length - 1)
        ] ?? input.transportAdmissionStatus ?? 200;
      return Promise.resolve(transportAdmissionResponse(input.transportAdmissions ?? [], status));
    }
    if (url.endsWith("/event-envelope")) {
      return Promise.resolve(
        eventEnvelopeResponse(input.eventEnvelopes ?? [], input.eventEnvelopeStatus ?? 200),
      );
    }
    if (url.endsWith("/publication-lease")) {
      return Promise.resolve(
        publicationLeaseResponse(
          input.publicationLeases ?? [activePublicationLease],
          input.publicationLeaseStatus ?? 200,
        ),
      );
    }
    if (url.endsWith("/outbox")) {
      return Promise.resolve(outboxResponse(input.outboxEntries ?? [], input.outboxStatus ?? 200));
    }
    if (url.endsWith("/dispatch-intents")) {
      return Promise.resolve(
        dispatchIntentResponse(
          input.dispatchIntents ?? [],
          input.dispatchIntentStatus ?? 200,
        ),
      );
    }
    if (url.endsWith("/attempts")) {
      return Promise.resolve(attemptResponse(input.attempts ?? [], input.attemptStatus ?? 200));
    }
    return Promise.resolve(
      url.endsWith("/materialized-run")
        ? materializedRunResponse(input.run ?? null, input.runStatus ?? 200)
        : leaseResponse(input.lease ?? null, input.leaseStatus ?? 200),
    );
  });
}

function renderWorkspace() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <WorkflowPlanningWorkspace
        environmentId="environment.test"
        organizationId="organization.test"
        ownerSubjectId="subject.operator"
        siteId="site.test"
        onBack={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("WorkflowPlanningWorkspace", () => {
  beforeEach(() => {
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [],
      authorizedTargets: [{ targetId: "asset.storage.test", displayName: "Primary storage" }],
      durable: false,
      truncated: false,
    });
    vi.mocked(listWorkflowDefinitions).mockResolvedValue({ definitions: [definition] });
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [], durable: false, truncated: false });
    vi.mocked(createWorkflowPlan).mockResolvedValue(plan);
    vi.mocked(cancelWorkflowPlan).mockResolvedValue(cancelledPlan);
    vi.stubGlobal("fetch", vi.fn());
    mockReadResponses({});
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads global transport capability profiles before any plan is selected", async () => {
    mockReadResponses({ transportProfileSnapshots: [transportProfileSnapshot] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport capability profiles",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Transport capability profiles",
    });
    expect(screen.queryByRole("heading", { name: plan.plan_id })).toBeNull();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/transport-profile-snapshots",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(transportProfileSnapshot.transport_profile_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.snapshot_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.transport_resource_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.transport_implementation_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.adapter_contract_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.snapshotter_subject_id)).toBeVisible();
    expect(within(section).getByTitle(transportProfileSnapshot.canonical_digest)).toBeVisible();
    expect(records).toHaveTextContent("revision.17");
    expect(records).toHaveTextContent("enterprise-test");
    expect(records).toHaveTextContent("WorkflowStepDispatchRequested v1.0");
    expect(records).toHaveTextContent("internal");
    expect(records).toHaveTextContent("canonical-json");
    expect(records).toHaveTextContent("utf-8");
    expect(records).toHaveTextContent("at-least-once");
    expect(records).toHaveTextContent("durable supported");
    expect(records).toHaveTextContent("workflow-run");
    expect(records).toHaveTextContent("workflow-operational");
    expect(records).toHaveTextContent("65,536 bytes");
    expect(records).toHaveTextContent("encryption required");
    expect(records).toHaveTextContent("restricted network supported");
    expect(records).toHaveTextContent(
      "Authority route selection false | publication false | delivery false | dispatch false | execution false",
    );
    expect(
      within(section).queryByRole("button", {
        name: /register|update|remove|select|bind|probe|test connection|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/authorized browser session|MFA|second login/i);
    expect(section).not.toHaveTextContent(/hostname|URL|IP address|namespace|topic|stream|queue|partition|routing key|credential|secret|publication lease|orchestration lease|raw payload/i);
  });

  it("renders an empty transport capability profile inventory as a healthy read-only state", async () => {
    mockReadResponses({ transportProfileSnapshots: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport capability profiles",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("No transport capability profiles are recorded in this scope."),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while transport capability profiles are pending", async () => {
    mockReadResponses({
      pendingTransportProfileResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport capability profiles",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Loading transport capability profiles...")).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed transport capability profile read without mutation controls", async () => {
    mockReadResponses({
      transportProfileSnapshots: [transportProfileSnapshot],
      transportProfileStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport capability profiles",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Transport capability profiles are unavailable")).toBeVisible();
    fireEvent.click(
      within(section).getByRole("button", { name: "Retry transport capability profile read" }),
    );
    expect(await within(section).findByTitle(transportProfileSnapshot.snapshot_id)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /register|update|remove|select|bind|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Transport capability profile permission is missing",
      "current role or scope cannot inspect",
    ],
  ])(
    "handles transport capability profile status %s with the normal session boundary",
    async (status, title, detail) => {
      mockReadResponses({ transportProfileStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Transport capability profiles",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/authorized browser session|MFA|second login/i);
    },
  );

  it.each([
    ["an unexpected physical field", { ...transportProfileSnapshot, topic: "hidden-topic" }],
    ["a credential field", { ...transportProfileSnapshot, credential: "hidden-credential" }],
    [
      "an invalid event contract",
      {
        ...transportProfileSnapshot,
        supported_event_contracts: [
          "WorkflowStepDispatchRequested|1.0|urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        ],
      },
    ],
    [
      "workflow lineage",
      { ...transportProfileSnapshot, event_id: "workflow-event.hidden" },
    ],
    [
      "a changed scope",
      {
        ...transportProfileSnapshot,
        scope: { ...transportProfileSnapshot.scope, site_id: "site.other" },
      },
    ],
    [
      "route authority",
      {
        ...transportProfileSnapshot,
        authority: {
          ...transportProfileSnapshot.authority,
          route_selection_authorized: true,
        },
      },
    ],
  ])("fails closed when a transport capability profile contains %s", async (_case, unsafeProfile) => {
    mockReadResponses({ transportProfileSnapshots: [unsafeProfile] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport capability profiles",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Transport capability profiles are unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Transport capability profiles" })).toBeNull();
    expect(section).not.toHaveTextContent(/hidden-topic|hidden-credential|workflow-event\.hidden|site\.other/i);
  });

  it("loads global immutable transport route snapshots without exposing route locators", async () => {
    mockReadResponses({ transportRouteSnapshots: [transportRouteSnapshot] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport route snapshots",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Transport route snapshots",
    });
    expect(screen.queryByRole("heading", { name: plan.plan_id })).toBeNull();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/transport-route-snapshots",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(transportRouteSnapshot.route_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.snapshot_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.transport_profile_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.transport_resource_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.transport_implementation_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.adapter_contract_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.transport_security_policy_id)).toBeVisible();
    expect(within(section).getByTitle(transportRouteSnapshot.network_policy_id)).toBeVisible();
    expect(
      within(section).getByTitle(transportRouteSnapshot.credential_requirement_profile_id),
    ).toBeVisible();
    expect(records).toHaveTextContent("revision.9");
    expect(records).toHaveTextContent("enterprise-test");
    expect(records).toHaveTextContent("TLS 1.3 minimum");
    expect(records).toHaveTextContent("restricted internal");
    expect(records).toHaveTextContent("mutual-tls");
    expect(records).toHaveTextContent("opaque-endpoin...ternal");
    expect(records).toHaveTextContent("opaque-destina...ternal");
    expect(records).toHaveTextContent("opaque-routing...ternal");
    expect(within(section).queryByTitle(transportRouteSnapshot.endpoint_set_id)).toBeNull();
    expect(within(section).queryByTitle(transportRouteSnapshot.destination_id)).toBeNull();
    expect(within(section).queryByTitle(transportRouteSnapshot.routing_contract_id)).toBeNull();
    expect(records).toHaveTextContent(
      "Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false",
    );
    expect(
      within(section).queryByRole("button", {
        name: /register|update|remove|select|bind|rebind|resolve|probe|credential|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(within(section).queryByRole("heading", { name: /route binding/i })).toBeNull();
    expect(section).not.toHaveTextContent(/authorized browser session|MFA|second login/i);
    expect(section).not.toHaveTextContent(
      /https?:\/\/|\b(?:\d{1,3}\.){3}\d{1,3}\b|broker\.internal|hidden-topic|field digest/i,
    );
  });

  it("renders an empty transport route snapshot inventory as a healthy read-only state", async () => {
    mockReadResponses({ transportRouteSnapshots: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport route snapshots",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("No transport route snapshots are recorded in this scope."),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while transport route snapshots are pending", async () => {
    mockReadResponses({
      pendingTransportRouteSnapshotResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport route snapshots",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Loading transport route snapshots...")).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed transport route snapshot read without mutation controls", async () => {
    mockReadResponses({
      transportRouteSnapshots: [transportRouteSnapshot],
      transportRouteSnapshotStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport route snapshots",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Transport route snapshots are unavailable")).toBeVisible();
    fireEvent.click(
      within(section).getByRole("button", { name: "Retry transport route snapshot read" }),
    );
    expect(await within(section).findByTitle(transportRouteSnapshot.snapshot_id)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /register|update|remove|select|bind|resolve|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Transport route snapshot permission is missing",
      "current role or scope cannot inspect",
    ],
  ])(
    "handles transport route snapshot status %s with the normal session boundary",
    async (status, title, detail) => {
      mockReadResponses({ transportRouteSnapshotStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Transport route snapshots",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/authorized browser session|MFA|second login/i);
    },
  );

  it.each([
    ["a raw endpoint", { ...transportRouteSnapshot, endpoint_url: "https://broker.internal" }],
    ["a raw destination", { ...transportRouteSnapshot, topic: "hidden-topic" }],
    ["a field-level digest", { ...transportRouteSnapshot, endpoint_set_digest: "9".repeat(64) }],
    ["credential material", { ...transportRouteSnapshot, credential: "hidden-credential" }],
    [
      "a changed scope",
      {
        ...transportRouteSnapshot,
        scope: { ...transportRouteSnapshot.scope, site_id: "site.other" },
      },
    ],
    [
      "operational authority",
      {
        ...transportRouteSnapshot,
        authority: { ...transportRouteSnapshot.authority, network_access_authorized: true },
      },
    ],
    [
      "an unknown security requirement class",
      { ...transportRouteSnapshot, minimum_tls_version: "1.2" },
    ],
  ])("fails closed when a transport route snapshot contains %s", async (_case, unsafeRoute) => {
    mockReadResponses({ transportRouteSnapshots: [unsafeRoute] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport route snapshots",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Transport route snapshots are unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Transport route snapshots" })).toBeNull();
    expect(section).not.toHaveTextContent(
      /broker\.internal|hidden-topic|hidden-credential|site\.other|tls-optional/i,
    );
  });

  it("renders credential-assignment snapshots as minimized read-only historical evidence", async () => {
    mockReadResponses({ credentialAssignmentSnapshots: [credentialAssignmentSnapshot] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport credential-assignment snapshots",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Transport credential-assignment snapshots",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/transport-credential-assignment-snapshots",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(credentialAssignmentSnapshot.snapshot_id)).toBeVisible();
    expect(within(section).getByTitle(credentialAssignmentSnapshot.assignment_id)).toBeVisible();
    expect(records).toHaveTextContent("revision.9");
    expect(records).toHaveTextContent("Active when captured");
    expect(records).toHaveTextContent("Historical record state snapshotted");
    expect(records).toHaveTextContent("Generation 12 | rotation epoch 4");
    expect(records).toHaveTextContent("Activated");
    expect(records).toHaveTextContent("Expires");
    expect(records).toHaveTextContent("Captured");
    expect(records).toHaveTextContent(/credential access false.*execution false/i);
    expect(
      within(section).queryByRole("button", {
        name: /create|select|authorize|resolve|reveal|copy|download|network|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /profile-private|requirement-private|target-private|broker-private|digest-private|secret-private|certificate-private|endpoint-private|MFA|second login|authorized browser session/i,
    );
  });

  it("renders an empty credential-assignment snapshot inventory as a healthy read-only state", async () => {
    mockReadResponses({ credentialAssignmentSnapshots: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport credential-assignment snapshots",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No transport credential-assignment snapshots are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows loading while credential-assignment snapshots are pending", async () => {
    mockReadResponses({
      pendingCredentialAssignmentSnapshotResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport credential-assignment snapshots",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading transport credential-assignment snapshots..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a generic credential-assignment snapshot read without operational controls", async () => {
    mockReadResponses({
      credentialAssignmentSnapshots: [credentialAssignmentSnapshot],
      credentialAssignmentSnapshotStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Transport credential-assignment snapshots",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Transport credential-assignment snapshots are unavailable",
      ),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No assignment lifecycle or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry transport credential-assignment snapshot read",
      }),
    );
    expect(await within(section).findByTitle(credentialAssignmentSnapshot.snapshot_id)).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Credential-assignment snapshot permission is missing",
      "current role or scope cannot inspect credential-assignment snapshot evidence",
    ],
  ])(
    "handles credential-assignment snapshot status %s with the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ credentialAssignmentSnapshotStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Transport credential-assignment snapshots",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a credential profile", { ...credentialAssignmentSnapshot, credential_profile_id: "profile-private" }],
    ["a credential requirement", { ...credentialAssignmentSnapshot, credential_requirement_id: "requirement-private" }],
    ["a target commitment", { ...credentialAssignmentSnapshot, target_scope: "target-private" }],
    ["a broker policy", { ...credentialAssignmentSnapshot, broker_policy_id: "broker-private" }],
    ["a digest", { ...credentialAssignmentSnapshot, canonical_digest: "digest-private" }],
    ["secret material", { ...credentialAssignmentSnapshot, secret: "secret-private" }],
    ["a certificate", { ...credentialAssignmentSnapshot, certificate: "certificate-private" }],
    ["an endpoint", { ...credentialAssignmentSnapshot, endpoint: "endpoint-private" }],
    ["an unknown state", { ...credentialAssignmentSnapshot, state: "current" }],
    ["a non-positive generation", { ...credentialAssignmentSnapshot, credential_generation: 0 }],
    ["a non-positive rotation epoch", { ...credentialAssignmentSnapshot, rotation_epoch: 0 }],
    ["an invalid activation timestamp", { ...credentialAssignmentSnapshot, activated_at: "not-a-time" }],
    [
      "capture before activation",
      { ...credentialAssignmentSnapshot, captured_at: "2026-08-14T07:59:59Z" },
    ],
    [
      "capture after expiry",
      { ...credentialAssignmentSnapshot, captured_at: "2026-09-14T08:00:00Z" },
    ],
    [
      "operational authority",
      {
        ...credentialAssignmentSnapshot,
        authority: {
          ...credentialAssignmentSnapshot.authority,
          credential_access_authorized: true,
        },
      },
    ],
    [
      "an extra authority field",
      {
        ...credentialAssignmentSnapshot,
        authority: { ...credentialAssignmentSnapshot.authority, reveal_authorized: false },
      },
    ],
  ])(
    "fails closed when credential-assignment snapshot evidence contains %s",
    async (_case, unsafeSnapshot) => {
      mockReadResponses({ credentialAssignmentSnapshots: [unsafeSnapshot] });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Transport credential-assignment snapshots",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Transport credential-assignment snapshots are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Transport credential-assignment snapshots",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(
        /profile-private|requirement-private|target-private|broker-private|digest-private|secret-private|certificate-private|endpoint-private/i,
      );
    },
  );

  it("fails closed for duplicate snapshot IDs or assignment revisions", async () => {
    for (const duplicate of [
      { ...credentialAssignmentSnapshot, assignment_id: "deployment-credential-assignment.other" },
      { ...credentialAssignmentSnapshot, snapshot_id: "workflow-credential-assignment-snapshot.other" },
    ]) {
      mockReadResponses({
        credentialAssignmentSnapshots: [credentialAssignmentSnapshot, duplicate],
      });
      const view = renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Transport credential-assignment snapshots",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Transport credential-assignment snapshots are unavailable",
        ),
      ).toBeVisible();
      view.unmount();
    }
  });

  it("loads immutable physical route bindings without digests, route details, or mutation controls", async () => {
    mockReadResponses({ physicalTransportRouteBindings: [physicalTransportRouteBinding] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Physical transport route bindings",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-route-bindings",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(physicalTransportRouteBinding.binding_id)).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.logical_channel_binding_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.compatibility_admission_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.transport_profile_snapshot_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.transport_route_snapshot_id),
    ).toBeVisible();
    expect(within(section).getByTitle(physicalTransportRouteBinding.policy_id)).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.binder_subject_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteBinding.integrity_reference),
    ).toBeVisible();
    expect(records).toHaveTextContent("bound");
    expect(records).toHaveTextContent("organization.test");
    expect(records).toHaveTextContent(
      "Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false",
    );
    expect(
      within(section).queryByRole("button", {
        name: /create|register|update|remove|select|bind|rebind|resolve|probe|credential|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/digest|https?:\/\/|hostname|IP address|topic|stream|queue|partition|routing key|MFA|second login|authorized browser session/i);
  });

  it("renders an empty physical route binding inventory as a healthy read-only state", async () => {
    mockReadResponses({ physicalTransportRouteBindings: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No physical transport route bindings are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed physical route binding read without mutation controls", async () => {
    mockReadResponses({
      physicalTransportRouteBindings: [physicalTransportRouteBinding],
      physicalTransportRouteBindingStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Physical transport route bindings are unavailable"),
    ).toBeVisible();
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry physical transport route binding read",
      }),
    );
    expect(await within(section).findByTitle(physicalTransportRouteBinding.binding_id)).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Physical transport route binding permission is missing",
      "current role or scope cannot inspect",
    ],
  ])(
    "handles physical route binding status %s with the normal session boundary",
    async (status, title, detail) => {
      mockReadResponses({ physicalTransportRouteBindingStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport route bindings",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a digest", { ...physicalTransportRouteBinding, canonical_digest: "a".repeat(64) }],
    ["route details", { ...physicalTransportRouteBinding, endpoint_url: "https://broker.internal" }],
    ["credential material", { ...physicalTransportRouteBinding, credential: "hidden-secret" }],
    [
      "a changed scope",
      {
        ...physicalTransportRouteBinding,
        scope: { ...physicalTransportRouteBinding.scope, site_id: "site.other" },
      },
    ],
    [
      "operational authority",
      {
        ...physicalTransportRouteBinding,
        authority: {
          ...physicalTransportRouteBinding.authority,
          route_binding_authorized: true,
        },
      },
    ],
    ["an unbound state", { ...physicalTransportRouteBinding, state: "pending" }],
  ])("fails closed when a physical route binding contains %s", async (_case, unsafeBinding) => {
    mockReadResponses({ physicalTransportRouteBindings: [unsafeBinding] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Physical transport route bindings are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Physical transport route bindings" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/broker\.internal|hidden-secret|site\.other|pending/i);
  });

  it("fails closed when one logical channel has duplicate physical route bindings", async () => {
    mockReadResponses({
      physicalTransportRouteBindings: [
        physicalTransportRouteBinding,
        {
          ...physicalTransportRouteBinding,
          binding_id: "workflow-physical-transport-route-binding.abcdef1234567890",
          integrity_reference:
            "integrity-ref.workflow-physical-route-binding.abcdef1234567890",
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Physical transport route bindings are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Physical transport route bindings" }),
    ).toBeNull();
  });

  it("renders minimized credential-assignment bindings directly after physical route bindings", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentBindings: [
        physicalTransportCredentialAssignmentBinding,
      ],
    });
    renderWorkspace();

    const routeSection = (await screen.findByRole("heading", {
      name: "Physical transport route bindings",
    })).closest("section") as HTMLElement;
    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment bindings",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Physical transport credential-assignment bindings",
    });
    expect(routeSection.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(
      0,
    );
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-credential-assignment-bindings",
        ),
      ),
    ).toBe(true);
    expect(
      within(section).getByTitle(physicalTransportCredentialAssignmentBinding.binding_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportCredentialAssignmentBinding.physical_transport_route_binding_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportCredentialAssignmentBinding.credential_assignment_snapshot_id,
      ),
    ).toBeVisible();
    expect(records).toHaveTextContent("bound");
    expect(records).toHaveTextContent("Bound");
    expect(
      within(section).getByTitle(
        physicalTransportCredentialAssignmentBinding.integrity_reference,
      ),
    ).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /create|select|bind|rebind|reveal|refresh|authorize|resolve|copy|download|network|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /digest-private|profile-private|requirement-private|target-private|broker-private|endpoint-private|artifact-private|secret-private|MFA|second login|authorized browser session/i,
    );
  });

  it("renders an empty credential-assignment binding inventory as a healthy read-only state", async () => {
    mockReadResponses({ physicalTransportCredentialAssignmentBindings: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No physical transport credential-assignment bindings are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows loading while credential-assignment bindings are pending", async () => {
    mockReadResponses({
      pendingPhysicalTransportCredentialAssignmentBindingResponse: new Promise<Response>(
        () => undefined,
      ),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Loading physical transport credential-assignment bindings...",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries an unavailable credential-assignment binding read without authority controls", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentBindings: [
        physicalTransportCredentialAssignmentBinding,
      ],
      physicalTransportCredentialAssignmentBindingStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Physical transport credential-assignment bindings are unavailable",
      ),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No binding or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry physical transport credential-assignment binding read",
      }),
    );
    expect(
      await within(section).findByTitle(physicalTransportCredentialAssignmentBinding.binding_id),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Physical transport credential-assignment binding permission is missing",
      "current role or scope cannot inspect credential-assignment binding evidence",
    ],
  ])(
    "handles credential-assignment binding status %s with the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ physicalTransportCredentialAssignmentBindingStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport credential-assignment bindings",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a digest", { ...physicalTransportCredentialAssignmentBinding, canonical_digest: "digest-private" }],
    ["a credential profile", { ...physicalTransportCredentialAssignmentBinding, credential_profile_id: "profile-private" }],
    ["a credential requirement", { ...physicalTransportCredentialAssignmentBinding, credential_requirement_id: "requirement-private" }],
    ["a target", { ...physicalTransportCredentialAssignmentBinding, target_commitment: "target-private" }],
    ["a broker", { ...physicalTransportCredentialAssignmentBinding, broker_policy_id: "broker-private" }],
    ["an endpoint", { ...physicalTransportCredentialAssignmentBinding, endpoint: "endpoint-private" }],
    ["an artifact", { ...physicalTransportCredentialAssignmentBinding, protected_artifact: "artifact-private" }],
    ["secret content", { ...physicalTransportCredentialAssignmentBinding, secret: "secret-private" }],
    ["an unknown state", { ...physicalTransportCredentialAssignmentBinding, state: "pending" }],
    ["an invalid timestamp", { ...physicalTransportCredentialAssignmentBinding, bound_at: "not-a-time" }],
    ["an invalid binding ID", { ...physicalTransportCredentialAssignmentBinding, binding_id: "unsafe binding" }],
  ])(
    "fails closed when credential-assignment binding evidence contains %s",
    async (_case, unsafeBinding) => {
      mockReadResponses({
        physicalTransportCredentialAssignmentBindings: [unsafeBinding],
      });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport credential-assignment bindings",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Physical transport credential-assignment bindings are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Physical transport credential-assignment bindings",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(
        /digest-private|profile-private|requirement-private|target-private|broker-private|endpoint-private|artifact-private|secret-private|pending|unsafe binding/i,
      );
    },
  );

  it("fails closed for duplicate credential-assignment binding IDs or exact source pairs", async () => {
    for (const duplicate of [
      {
        ...physicalTransportCredentialAssignmentBinding,
        credential_assignment_snapshot_id:
          "workflow-credential-assignment-snapshot.abcdef1234567890",
      },
      {
        ...physicalTransportCredentialAssignmentBinding,
        binding_id:
          "workflow-physical-transport-credential-assignment-binding.abcdef1234567890",
      },
    ]) {
      mockReadResponses({
        physicalTransportCredentialAssignmentBindings: [
          physicalTransportCredentialAssignmentBinding,
          duplicate,
        ],
      });
      const view = renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Physical transport credential-assignment bindings",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Physical transport credential-assignment bindings are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Physical transport credential-assignment bindings",
        }),
      ).toBeNull();
      view.unmount();
    }
  });

  it("renders minimized credential-assignment freshness evidence between binding and route freshness sections", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: [
        physicalTransportCredentialAssignmentFreshnessAdmission,
      ],
    });
    renderWorkspace();

    const bindingHeading = await screen.findByRole("heading", {
      name: "Physical transport credential-assignment bindings",
    });
    const freshnessHeading = await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    });
    const routeFreshnessHeading = await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    });
    expect(
      bindingHeading.compareDocumentPosition(freshnessHeading) & 4,
    ).toBe(4);
    expect(
      freshnessHeading.compareDocumentPosition(routeFreshnessHeading) & 4,
    ).toBe(4);

    const section = freshnessHeading.closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Physical transport credential-assignment freshness admissions",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-credential-assignment-freshness-admissions",
        ),
      ),
    ).toBe(true);
    for (const identifier of [
      physicalTransportCredentialAssignmentFreshnessAdmission.freshness_admission_id,
      physicalTransportCredentialAssignmentFreshnessAdmission
        .physical_transport_credential_assignment_binding_id,
      physicalTransportCredentialAssignmentFreshnessAdmission.credential_assignment_snapshot_id,
      physicalTransportCredentialAssignmentFreshnessAdmission.assignment_id,
      physicalTransportCredentialAssignmentFreshnessAdmission.assignment_revision,
      physicalTransportCredentialAssignmentFreshnessAdmission.policy_id,
      physicalTransportCredentialAssignmentFreshnessAdmission.admitter_subject_id,
      physicalTransportCredentialAssignmentFreshnessAdmission.integrity_reference,
    ]) {
      expect(within(section).getByTitle(identifier)).toBeVisible();
    }
    expect(records).toHaveTextContent("admitted_current");
    expect(records).toHaveTextContent("Time window open");
    expect(records).toHaveTextContent("Rotation epoch 3 | credential generation 7");
    expect(records).toHaveTextContent("revision");
    expect(records).toHaveTextContent("Evaluated");
    expect(records).toHaveTextContent("valid until");
    expect(records).toHaveTextContent("organization.test");
    expect(records).toHaveTextContent(
      "Zero authority: route selection and binding, endpoint resolution, protected-artifact access, credential selection, assignment binding, access, brokerage, resolution and delivery, network access, readiness probes, publication, delivery, dispatch, execution and infrastructure mutation are all false.",
    );
    expect(section).toHaveTextContent(
      "An open time window does not independently prove that the assignment remains the current, active or non-revoked head",
    );
    expect(
      within(section).queryByRole("button", {
        name: /create|admit|renew|override|reveal|authorize|resolve|copy|download|publish|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /digest-private|profile-private|requirement-private|target-private|broker-private|endpoint-private|artifact-private|secret-private|MFA|second login|authorized browser session/i,
    );
  });

  it("renders an empty credential-assignment freshness inventory as a healthy read-only state", async () => {
    mockReadResponses({ physicalTransportCredentialAssignmentFreshnessAdmissions: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No physical transport credential-assignment freshness admissions are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows loading while credential-assignment freshness evidence is pending", async () => {
    mockReadResponses({
      pendingPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse:
        new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Loading physical transport credential-assignment freshness admissions...",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries an unavailable credential-assignment freshness read without operational controls", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: [
        physicalTransportCredentialAssignmentFreshnessAdmission,
      ],
      physicalTransportCredentialAssignmentFreshnessAdmissionStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Credential-assignment freshness admissions are unavailable",
      ),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No current-head, expiry, revocation or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry physical transport credential-assignment freshness admission read",
      }),
    );
    expect(
      await within(section).findByTitle(
        physicalTransportCredentialAssignmentFreshnessAdmission.freshness_admission_id,
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Credential-assignment freshness permission is missing",
      "current role or scope cannot inspect credential-assignment freshness evidence",
    ],
  ])(
    "handles credential-assignment freshness status %s with the normal username/password session",
    async (status, title, detail) => {
      mockReadResponses({
        physicalTransportCredentialAssignmentFreshnessAdmissionStatus: status,
      });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport credential-assignment freshness admissions",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it("marks an elapsed credential-assignment freshness window as expired without inferring currentness", async () => {
    const evaluatedAt = new Date(Date.now() - 120_000);
    const validUntil = new Date(evaluatedAt.getTime() + 45_000);
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: [
        {
          ...physicalTransportCredentialAssignmentFreshnessAdmission,
          evaluated_at: evaluatedAt.toISOString(),
          valid_until: validUntil.toISOString(),
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Expired")).toBeVisible();
    expect(section).not.toHaveTextContent(/current head confirmed|still current/i);
    expect(section).toHaveTextContent("point-in-time evidence only");
  });

  it("accepts multiple historical freshness admissions for the same credential-assignment binding", async () => {
    const historicalAdmission = {
      ...physicalTransportCredentialAssignmentFreshnessAdmission,
      freshness_admission_id:
        "workflow-physical-transport-credential-assignment-freshness-admission.abcdef1234567890",
      evaluated_at: "2099-08-14T10:09:00+00:00",
      valid_until: "2099-08-14T10:10:00+00:00",
      policy_id:
        "policy.workflow-event-physical-transport-credential-assignment-freshness-legacy",
      policy_version: "0.9",
      integrity_reference:
        "integrity-ref.workflow-physical-transport-credential-assignment-freshness.abcdef1234567890",
    };
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: [
        physicalTransportCredentialAssignmentFreshnessAdmission,
        historicalAdmission,
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    const records = await within(section).findAllByRole("listitem");
    expect(records).toHaveLength(2);
    expect(
      within(section).getByTitle(historicalAdmission.freshness_admission_id),
    ).toBeVisible();
    expect(section).toHaveTextContent("v0.9");
  });

  it.each([
    [
      "an extra digest",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        canonical_digest: "a".repeat(64),
      },
    ],
    [
      "a credential profile",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        credential_profile_id: "profile-private",
      },
    ],
    [
      "a credential requirement",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        credential_requirement_id: "requirement-private",
      },
    ],
    [
      "a target",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        target_commitment: "target-private",
      },
    ],
    [
      "a broker",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        broker_policy_id: "broker-private",
      },
    ],
    [
      "an endpoint",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        endpoint: "endpoint-private",
      },
    ],
    [
      "an artifact",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        protected_artifact: "artifact-private",
      },
    ],
    [
      "secret content",
      { ...physicalTransportCredentialAssignmentFreshnessAdmission, secret: "secret-private" },
    ],
    [
      "a changed scope",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        scope: {
          ...physicalTransportCredentialAssignmentFreshnessAdmission.scope,
          site_id: "site.other",
        },
      },
    ],
    [
      "operational authority",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        authority: {
          ...physicalTransportCredentialAssignmentFreshnessAdmission.authority,
          credential_access_authorized: true,
        },
      },
    ],
    [
      "a non-positive credential generation",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        credential_generation: 0,
      },
    ],
    [
      "a non-positive rotation epoch",
      { ...physicalTransportCredentialAssignmentFreshnessAdmission, rotation_epoch: 0 },
    ],
    [
      "an unknown state",
      { ...physicalTransportCredentialAssignmentFreshnessAdmission, state: "expired" },
    ],
    [
      "an empty validity window",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        valid_until: physicalTransportCredentialAssignmentFreshnessAdmission.evaluated_at,
      },
    ],
    [
      "a validity window over 60 seconds",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        valid_until: "2099-08-14T10:09:01Z",
      },
    ],
    [
      "a timezone-naive evaluation timestamp",
      {
        ...physicalTransportCredentialAssignmentFreshnessAdmission,
        evaluated_at: "2099-08-14T10:08:00",
      },
    ],
  ])(
    "fails closed when credential-assignment freshness evidence contains %s",
    async (_case, unsafeAdmission) => {
      mockReadResponses({
        physicalTransportCredentialAssignmentFreshnessAdmissions: [unsafeAdmission],
      });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport credential-assignment freshness admissions",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Credential-assignment freshness admissions are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Physical transport credential-assignment freshness admissions",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(
        /profile-private|requirement-private|target-private|broker-private|endpoint-private|artifact-private|secret-private|site\.other/i,
      );
    },
  );

  it("fails closed when credential-assignment freshness admission IDs are duplicated", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: [
        physicalTransportCredentialAssignmentFreshnessAdmission,
        {
          ...physicalTransportCredentialAssignmentFreshnessAdmission,
          assignment_revision: "revision.8",
          credential_generation: 8,
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Credential-assignment freshness admissions are unavailable",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("list")).toBeNull();
  });

  it("fails closed when credential-assignment freshness inventory exceeds 256 records", async () => {
    mockReadResponses({
      physicalTransportCredentialAssignmentFreshnessAdmissions: Array.from(
        { length: 257 },
        (_, index) => ({
          ...physicalTransportCredentialAssignmentFreshnessAdmission,
          freshness_admission_id: `workflow-credential-freshness-admission.${String(index).padStart(3, "0")}`,
          integrity_reference: `integrity-ref.workflow-credential-freshness.${String(index).padStart(3, "0")}`,
        }),
      ),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport credential-assignment freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Credential-assignment freshness admissions are unavailable",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("list")).toBeNull();
  });

  it("loads read-only physical route freshness admissions without private route details or mutation controls", async () => {
    mockReadResponses({
      physicalTransportRouteFreshnessAdmissions: [physicalTransportRouteFreshnessAdmission],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Physical transport route freshness admissions",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-route-freshness-admissions",
        ),
      ),
    ).toBe(true);
    expect(
      within(section).getByTitle(
        physicalTransportRouteFreshnessAdmission.freshness_admission_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportRouteFreshnessAdmission.physical_transport_route_binding_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportRouteFreshnessAdmission.transport_route_snapshot_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteFreshnessAdmission.selection_head_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(physicalTransportRouteFreshnessAdmission.policy_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportRouteFreshnessAdmission.admitter_subject_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(
        physicalTransportRouteFreshnessAdmission.integrity_reference,
      ),
    ).toBeVisible();
    expect(records).toHaveTextContent("admitted_current");
    expect(records).toHaveTextContent("generation 7");
    expect(records).toHaveTextContent("organization.test");
    expect(records).toHaveTextContent(
      "Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false",
    );
    expect(
      within(section).queryByRole("button", {
        name: /create|admit|register|update|remove|select|bind|rebind|resolve|probe|credential|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /digest|https?:\/\/|hostname|IP address|topic|stream|queue|partition|routing key|credential value|secret|MFA|second login|authorized browser session/i,
    );
  });

  it("renders an empty physical route freshness inventory as a healthy read-only state", async () => {
    mockReadResponses({ physicalTransportRouteFreshnessAdmissions: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No physical transport route freshness admissions are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("marks an elapsed route freshness window as expired without inferring head state", async () => {
    const evaluatedAt = new Date(Date.now() - 120_000);
    const validUntil = new Date(evaluatedAt.getTime() + 60_000);
    mockReadResponses({
      physicalTransportRouteFreshnessAdmissions: [
        {
          ...physicalTransportRouteFreshnessAdmission,
          evaluated_at: evaluatedAt.toISOString(),
          valid_until: validUntil.toISOString(),
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Expired")).toBeVisible();
    expect(section).not.toHaveTextContent(/still current|current head confirmed/i);
  });

  it("shows a loading state while physical route freshness admissions are pending", async () => {
    mockReadResponses({
      pendingPhysicalTransportRouteFreshnessAdmissionResponse: new Promise<Response>(
        () => undefined,
      ),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Loading physical transport route freshness admissions...",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a generic physical route freshness read failure without mutation controls", async () => {
    mockReadResponses({
      physicalTransportRouteFreshnessAdmissions: [physicalTransportRouteFreshnessAdmission],
      physicalTransportRouteFreshnessAdmissionStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Physical transport route freshness admissions are unavailable",
      ),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No freshness or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry physical transport route freshness admission read",
      }),
    );
    expect(
      await within(section).findByTitle(
        physicalTransportRouteFreshnessAdmission.freshness_admission_id,
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Physical transport route freshness permission is missing",
      "current role or scope cannot inspect route freshness evidence",
    ],
  ])(
    "handles physical route freshness status %s with the normal session boundary",
    async (status, title, detail) => {
      mockReadResponses({ physicalTransportRouteFreshnessAdmissionStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport route freshness admissions",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    [
      "an extra digest",
      { ...physicalTransportRouteFreshnessAdmission, canonical_digest: "a".repeat(64) },
    ],
    [
      "private route details",
      {
        ...physicalTransportRouteFreshnessAdmission,
        endpoint_url: "https://broker.internal/private-topic",
      },
    ],
    [
      "credential material",
      { ...physicalTransportRouteFreshnessAdmission, credential: "hidden-secret" },
    ],
    [
      "a changed scope",
      {
        ...physicalTransportRouteFreshnessAdmission,
        scope: { ...physicalTransportRouteFreshnessAdmission.scope, site_id: "site.other" },
      },
    ],
    [
      "operational authority",
      {
        ...physicalTransportRouteFreshnessAdmission,
        authority: {
          ...physicalTransportRouteFreshnessAdmission.authority,
          endpoint_resolution_authorized: true,
        },
      },
    ],
    [
      "a non-positive generation",
      { ...physicalTransportRouteFreshnessAdmission, selection_generation: 0 },
    ],
    [
      "a non-v1 validity window",
      {
        ...physicalTransportRouteFreshnessAdmission,
        valid_until: "2026-08-14T10:12:00Z",
      },
    ],
    [
      "a non-code-owned policy",
      {
        ...physicalTransportRouteFreshnessAdmission,
        policy_id: "policy.workflow-physical-transport-route-freshness-admission",
      },
    ],
    [
      "an unknown state",
      { ...physicalTransportRouteFreshnessAdmission, state: "expired" },
    ],
  ])(
    "fails closed when a physical route freshness admission contains %s",
    async (_case, unsafeAdmission) => {
      mockReadResponses({ physicalTransportRouteFreshnessAdmissions: [unsafeAdmission] });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Physical transport route freshness admissions",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Physical transport route freshness admissions are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Physical transport route freshness admissions",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(
        /broker\.internal|private-topic|hidden-secret|site\.other|expired/i,
      );
    },
  );

  it("fails closed when physical route freshness admission identifiers are duplicated", async () => {
    mockReadResponses({
      physicalTransportRouteFreshnessAdmissions: [
        physicalTransportRouteFreshnessAdmission,
        {
          ...physicalTransportRouteFreshnessAdmission,
          physical_transport_route_binding_id:
            "workflow-physical-route-binding.abcdef1234567890",
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Physical transport route freshness admissions",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Physical transport route freshness admissions are unavailable",
      ),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Physical transport route freshness admissions",
      }),
    ).toBeNull();
  });

  it("renders one active credential-access authorization lease as minimized read-only historical evidence", async () => {
    mockReadResponses({
      credentialAccessAuthorizationLeases: [credentialAccessAuthorizationLease],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Credential-access authorization leases",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-credential-access-authorization-leases",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(credentialAccessAuthorizationLease.lease_id)).toBeVisible();
    expect(
      within(section).getByTitle(credentialAccessAuthorizationLease.freshness_admission_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(credentialAccessAuthorizationLease.assignment_revision),
    ).toBeVisible();
    expect(within(section).getByTitle(credentialAccessAuthorizationLease.policy_id)).toBeVisible();
    expect(
      within(section).getByTitle(credentialAccessAuthorizationLease.accessor_subject_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(credentialAccessAuthorizationLease.integrity_reference),
    ).toBeVisible();
    expect(records).toHaveTextContent("v0.9");
    expect(records).toHaveTextContent("Credential generation 7 | rotation epoch 3");
    expect(records).toHaveTextContent(
      "Immutable state authorized unconsumed | effective state active",
    );
    expect(records).toHaveTextContent("Single use true | renewable false");
    expect(records).toHaveTextContent(/credential access true.*endpoint resolution false/i);
    expect(records).toHaveTextContent(/protected-artifact access false.*route selection false/i);
    expect(records).toHaveTextContent(/credential-assignment binding false/i);
    expect(records).toHaveTextContent(/infrastructure mutation false/i);
    expect(
      within(section).queryByRole("button", {
        name: /issue|renew|transfer|consume|resolve|reveal|download|broker|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /hidden-secret|broker\.internal|vault\/|https?:\/\/|10\.0\.0\.1|private-topic|source digest|policy digest|locator|MFA|second login|authorized browser session/i,
    );
  });

  it("renders credential-access lease expiry from validated server time", async () => {
    mockReadResponses({
      credentialAccessAuthorizationLeases: [
        { ...credentialAccessAuthorizationLease, effective_state: "expired" },
      ],
      credentialAccessAuthorizationLeaseServerTime: "2026-08-14T10:08:15Z",
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Expired")).toBeVisible();
    expect(within(section).queryByText("Active")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows the credential-access authorization lease empty state", async () => {
    mockReadResponses({ credentialAccessAuthorizationLeases: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No credential-access authorization leases are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while credential-access authorization leases are pending", async () => {
    mockReadResponses({
      pendingCredentialAccessAuthorizationLeaseResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading credential-access authorization leases..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a generic credential-access lease read failure without mutation controls", async () => {
    mockReadResponses({
      credentialAccessAuthorizationLeases: [credentialAccessAuthorizationLease],
      credentialAccessAuthorizationLeaseStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential-access authorization leases are unavailable"),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No authorization or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry credential-access authorization lease read",
      }),
    );
    expect(
      await within(section).findByTitle(credentialAccessAuthorizationLease.lease_id),
    ).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /issue|renew|transfer|consume|resolve|reveal|download|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Credential-access lease permission is missing",
      "current role or scope cannot inspect credential-access lease evidence",
    ],
  ])(
    "handles credential-access lease read status %s with the normal browser session boundary",
    async (status, title, detail) => {
      mockReadResponses({ credentialAccessAuthorizationLeaseStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Credential-access authorization leases",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    [
      "an extra source digest",
      { ...credentialAccessAuthorizationLease, source_assignment_digest: "a".repeat(64) },
    ],
    ["secret material", { ...credentialAccessAuthorizationLease, secret: "hidden-secret" }],
    [
      "a changed scope",
      {
        ...credentialAccessAuthorizationLease,
        scope: { ...credentialAccessAuthorizationLease.scope, site_id: "site.other" },
      },
    ],
    [
      "missing credential-access authority",
      {
        ...credentialAccessAuthorizationLease,
        authority: {
          ...credentialAccessAuthorizationLease.authority,
          credential_access_authorized: false,
        },
      },
    ],
    [
      "additional endpoint authority",
      {
        ...credentialAccessAuthorizationLease,
        authority: {
          ...credentialAccessAuthorizationLease.authority,
          endpoint_resolution_authorized: true,
        },
      },
    ],
    [
      "an extra authority field",
      {
        ...credentialAccessAuthorizationLease,
        authority: { ...credentialAccessAuthorizationLease.authority, consume_authorized: false },
      },
    ],
    [
      "a non-v1 lease window",
      { ...credentialAccessAuthorizationLease, valid_until: "2026-08-14T10:08:16Z" },
    ],
    ["a reusable lease", { ...credentialAccessAuthorizationLease, single_use: false }],
    ["a renewable lease", { ...credentialAccessAuthorizationLease, renewable: true }],
    [
      "a non-positive generation",
      { ...credentialAccessAuthorizationLease, credential_generation: 0 },
    ],
    ["a non-positive rotation epoch", { ...credentialAccessAuthorizationLease, rotation_epoch: 0 }],
    ["a changed immutable state", { ...credentialAccessAuthorizationLease, state: "consumed" }],
    [
      "an effective-state mismatch",
      { ...credentialAccessAuthorizationLease, effective_state: "expired" },
    ],
    [
      "a locator-shaped identifier",
      { ...credentialAccessAuthorizationLease, lease_id: "https://broker.internal" },
    ],
  ])(
    "fails closed when credential-access authorization lease evidence contains %s",
    async (_case, unsafeLease) => {
      mockReadResponses({ credentialAccessAuthorizationLeases: [unsafeLease] });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Credential-access authorization leases",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Credential-access authorization leases are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Credential-access authorization leases",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(/hidden-secret|broker\.internal|site\.other/i);
    },
  );

  it("fails closed when credential-access leases duplicate a lease or freshness admission", async () => {
    mockReadResponses({
      credentialAccessAuthorizationLeases: [
        credentialAccessAuthorizationLease,
        {
          ...credentialAccessAuthorizationLease,
          accessor_subject_id: "workload.workflow-physical-transport-credential-accessor.other",
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential-access authorization leases are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Credential-access authorization leases",
      }),
    ).toBeNull();
  });

  it("fails closed when credential-access lease inventory exceeds its bound", async () => {
    mockReadResponses({
      credentialAccessAuthorizationLeases: Array.from({ length: 257 }, (_, index) => ({
        ...credentialAccessAuthorizationLease,
        lease_id: `workflow-credential-access-authorization-lease.${index}`,
        freshness_admission_id: `workflow-credential-assignment-freshness-admission.${index}`,
      })),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential-access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential-access authorization leases are unavailable"),
    ).toBeVisible();
  });

  it("renders one active endpoint-resolution authorization lease as minimized read-only evidence", async () => {
    mockReadResponses({
      endpointResolutionAuthorizationLeases: [endpointResolutionAuthorizationLease],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Endpoint-resolution authorization leases",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-endpoint-resolution-authorization-leases",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(endpointResolutionAuthorizationLease.lease_id)).toBeVisible();
    expect(
      within(section).getByTitle(endpointResolutionAuthorizationLease.freshness_admission_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(endpointResolutionAuthorizationLease.resolver_subject_id),
    ).toBeVisible();
    expect(within(section).getByTitle(endpointResolutionAuthorizationLease.policy_id)).toBeVisible();
    expect(
      within(section).getByTitle(endpointResolutionAuthorizationLease.integrity_reference),
    ).toBeVisible();
    expect(records).toHaveTextContent("Active");
    expect(records).toHaveTextContent("generation 7");
    expect(records).toHaveTextContent("Single use true | renewable false");
    expect(records).toHaveTextContent(/endpoint resolution true for the named resolver workload only/i);
    expect(records).toHaveTextContent(/route selection false.*execution false/i);
    expect(section).toHaveTextContent("The browser cannot issue, renew, transfer, consume, or resolve it");
    expect(
      within(section).queryByRole("button", {
        name: /issue|renew|transfer|consume|resolve|credential|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /https?:\/\/|broker\.internal|10\.0\.0\.1|private-topic|hidden-secret|MFA|second login|authorized browser session/i,
    );
  });

  it("renders an empty endpoint-resolution lease inventory as a healthy read-only state", async () => {
    mockReadResponses({ endpointResolutionAuthorizationLeases: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No endpoint-resolution authorization leases are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while endpoint-resolution authorization leases are pending", async () => {
    mockReadResponses({
      pendingEndpointResolutionAuthorizationLeaseResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading endpoint-resolution authorization leases..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders endpoint-resolution lease expiry from validated server time", async () => {
    mockReadResponses({
      endpointResolutionAuthorizationLeases: [
        { ...endpointResolutionAuthorizationLease, effective_state: "expired" },
      ],
      endpointResolutionAuthorizationLeaseServerTime: "2026-08-14T10:07:45Z",
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Expired")).toBeVisible();
    expect(section).not.toHaveTextContent(/still valid|current head confirmed/i);
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders a consumed endpoint-resolution lease from the authoritative projection", async () => {
    mockReadResponses({
      endpointResolutionAuthorizationLeases: [consumedEndpointResolutionAuthorizationLease],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Consumed")).toBeVisible();
    expect(within(section).queryByText("Active")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a generic endpoint-resolution lease read failure without operational controls", async () => {
    mockReadResponses({
      endpointResolutionAuthorizationLeases: [endpointResolutionAuthorizationLease],
      endpointResolutionAuthorizationLeaseStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Endpoint-resolution authorization leases are unavailable",
      ),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No authorization, endpoint, or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry endpoint-resolution authorization lease read",
      }),
    );
    expect(
      await within(section).findByTitle(endpointResolutionAuthorizationLease.lease_id),
    ).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /issue|renew|transfer|consume|resolve|credential|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Endpoint-resolution lease permission is missing",
      "current role or scope cannot inspect endpoint-resolution lease evidence",
    ],
  ])(
    "handles endpoint-resolution lease read status %s with the normal browser session boundary",
    async (status, title, detail) => {
      mockReadResponses({ endpointResolutionAuthorizationLeaseStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Endpoint-resolution authorization leases",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["an extra digest", { ...endpointResolutionAuthorizationLease, canonical_digest: "a".repeat(64) }],
    [
      "private endpoint material",
      { ...endpointResolutionAuthorizationLease, endpoint_url: "https://broker.internal/private-topic" },
    ],
    ["credential material", { ...endpointResolutionAuthorizationLease, credential: "hidden-secret" }],
    [
      "a changed scope",
      {
        ...endpointResolutionAuthorizationLease,
        scope: { ...endpointResolutionAuthorizationLease.scope, site_id: "site.other" },
      },
    ],
    [
      "missing endpoint-resolution authority",
      {
        ...endpointResolutionAuthorizationLease,
        authority: {
          ...endpointResolutionAuthorizationLease.authority,
          endpoint_resolution_authorized: false,
        },
      },
    ],
    [
      "extra operational authority",
      {
        ...endpointResolutionAuthorizationLease,
        authority: {
          ...endpointResolutionAuthorizationLease.authority,
          network_access_authorized: true,
        },
      },
    ],
    [
      "an extra authority field",
      {
        ...endpointResolutionAuthorizationLease,
        authority: { ...endpointResolutionAuthorizationLease.authority, consume_authorized: false },
      },
    ],
    [
      "a non-v1 lease window",
      { ...endpointResolutionAuthorizationLease, expires_at: "2026-08-14T10:07:46Z" },
    ],
    ["a consumed state", { ...endpointResolutionAuthorizationLease, state: "consumed" }],
    ["a consumption field", { ...endpointResolutionAuthorizationLease, consumed_at: null }],
    ["a reusable lease", { ...endpointResolutionAuthorizationLease, single_use: false }],
    ["a renewable lease", { ...endpointResolutionAuthorizationLease, renewable: true }],
    ["a non-positive generation", { ...endpointResolutionAuthorizationLease, selection_generation: 0 }],
    ["an effective-state mismatch", { ...endpointResolutionAuthorizationLease, effective_state: "expired" }],
    ["a locator-shaped identifier", { ...endpointResolutionAuthorizationLease, lease_id: "https://broker.internal" }],
  ])(
    "fails closed when endpoint-resolution authorization lease evidence contains %s",
    async (_case, unsafeLease) => {
      mockReadResponses({ endpointResolutionAuthorizationLeases: [unsafeLease] });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Endpoint-resolution authorization leases",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText(
          "Endpoint-resolution authorization leases are unavailable",
        ),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", {
          name: "Endpoint-resolution authorization leases",
        }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(/broker\.internal|private-topic|hidden-secret|site\.other/i);
    },
  );

  it("fails closed when endpoint-resolution leases duplicate a lease or freshness admission", async () => {
    mockReadResponses({
      endpointResolutionAuthorizationLeases: [
        endpointResolutionAuthorizationLease,
        {
          ...endpointResolutionAuthorizationLease,
          resolver_subject_id: "workload.workflow-physical-transport-endpoint-resolver.other",
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint-resolution authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Endpoint-resolution authorization leases are unavailable",
      ),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Endpoint-resolution authorization leases",
      }),
    ).toBeNull();
  });

  it("renders protected endpoint materialization as minimized read-only evidence", async () => {
    mockReadResponses({ endpointMaterializations: [endpointMaterialization] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint materialization results",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Endpoint materialization results",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-endpoint-materializations",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(endpointMaterialization.materialization_id)).toBeVisible();
    expect(within(section).getByTitle(endpointMaterialization.lease_id)).toBeVisible();
    expect(within(section).getByTitle(endpointMaterialization.freshness_admission_id)).toBeVisible();
    expect(within(section).getByTitle(endpointMaterialization.resolver_subject_id)).toBeVisible();
    expect(within(section).getByTitle(endpointMaterialization.policy_id)).toBeVisible();
    expect(within(section).getByTitle(endpointMaterialization.integrity_reference)).toBeVisible();
    expect(records).toHaveTextContent("Protected result stored");
    expect(records).toHaveTextContent("Protected storage Verified");
    expect(records).toHaveTextContent("raw endpoint disclosed false");
    expect(records).toHaveTextContent(/endpoint resolution false.*execution false/i);
    expect(section).toHaveTextContent("one-way lease consumption");
    expect(
      within(section).queryByRole("button", {
        name: /materialize|retry materialization|reveal|credential|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /https?:\/\/|broker\.internal|10\.0\.0\.1|private-topic|hidden-secret|artifact|digest|hostname|routing key|provider|MFA|second login|authorized browser session/i,
    );
  });

  it.each([
    [
      "failed_closed_consumed",
      "Failed closed",
      { protected_storage_verified: false, recorded_at: "2026-08-14T10:07:38Z" },
      "Result recorded",
    ],
    [
      "uncertain_consumed",
      "Outcome uncertain",
      { protected_storage_verified: false, recorded_at: null },
      "Result recorded Not recorded",
    ],
  ] as const)(
    "renders the %s endpoint materialization outcome without adding controls",
    async (outcome, label, overrides, recordedText) => {
      mockReadResponses({
        endpointMaterializations: [{ ...endpointMaterialization, ...overrides, outcome }],
      });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Endpoint materialization results",
      })).closest("section") as HTMLElement;
      const records = await within(section).findByRole("list", {
        name: "Endpoint materialization results",
      });
      expect(records).toHaveTextContent(label);
      expect(records).toHaveTextContent(recordedText);
      expect(records).toHaveTextContent("Protected storage Not verified");
      expect(within(section).queryByRole("button")).toBeNull();
    },
  );

  it("renders an empty endpoint materialization inventory as a healthy read-only state", async () => {
    mockReadResponses({ endpointMaterializations: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint materialization results",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No endpoint materialization results are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while endpoint materialization results are pending", async () => {
    mockReadResponses({
      pendingEndpointMaterializationResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint materialization results",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading endpoint materialization results..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a generic endpoint materialization read failure without operational controls", async () => {
    mockReadResponses({
      endpointMaterializations: [endpointMaterialization],
      endpointMaterializationStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint materialization results",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Endpoint materialization results are unavailable"),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No materialization outcome or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry endpoint materialization result read",
      }),
    );
    expect(await within(section).findByTitle(endpointMaterialization.materialization_id)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /materialize|reveal|credential|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Endpoint materialization evidence permission is missing",
      "current role or scope cannot inspect endpoint materialization evidence",
    ],
  ])(
    "handles endpoint materialization read status %s with the normal browser session boundary",
    async (status, title, detail) => {
      mockReadResponses({ endpointMaterializationStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Endpoint materialization results",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["an extra artifact ID", { ...endpointMaterialization, artifact_id: "protected.item" }],
    ["an extra digest", { ...endpointMaterialization, canonical_digest: "a".repeat(64) }],
    ["an endpoint count", { ...endpointMaterialization, endpoint_count: 2 }],
    ["a raw endpoint", { ...endpointMaterialization, hostname: "broker.internal" }],
    ["a URL", { ...endpointMaterialization, url: "https://broker.internal/private-topic" }],
    ["an IP address", { ...endpointMaterialization, ip: "10.0.0.1" }],
    ["a port", { ...endpointMaterialization, port: 443 }],
    ["routing material", { ...endpointMaterialization, routing_key: "private-topic" }],
    ["credential material", { ...endpointMaterialization, credential: "hidden-secret" }],
    ["provider detail", { ...endpointMaterialization, provider_message: "private detail" }],
    ["a changed scope", { ...endpointMaterialization, scope: { ...plan.scope, site_id: "site.other" } }],
    ["an unknown outcome", { ...endpointMaterialization, outcome: "completed" }],
    ["a reusable lease", { ...endpointMaterialization, lease_consumed: false }],
    ["raw disclosure", { ...endpointMaterialization, raw_endpoint_disclosed: true }],
    ["success without verified storage", { ...endpointMaterialization, protected_storage_verified: false }],
    [
      "failure with verified storage",
      {
        ...endpointMaterialization,
        outcome: "failed_closed_consumed",
        protected_storage_verified: true,
      },
    ],
    [
      "uncertainty with a result record",
      {
        ...endpointMaterialization,
        outcome: "uncertain_consumed",
        protected_storage_verified: false,
      },
    ],
    ["an invalid recorded time", { ...endpointMaterialization, recorded_at: "not-a-time" }],
    ["a future consumption time", { ...endpointMaterialization, consumed_at: "2026-08-14T10:07:41Z" }],
    ["a non-positive generation", { ...endpointMaterialization, selection_generation: 0 }],
    [
      "operational authority",
      {
        ...endpointMaterialization,
        authority: { ...endpointMaterialization.authority, network_access_authorized: true },
      },
    ],
    [
      "an extra authority field",
      {
        ...endpointMaterialization,
        authority: { ...endpointMaterialization.authority, materialize_authorized: false },
      },
    ],
  ])(
    "fails closed when endpoint materialization evidence contains %s",
    async (_case, unsafeMaterialization) => {
      mockReadResponses({ endpointMaterializations: [unsafeMaterialization] });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Endpoint materialization results",
      })).closest("section") as HTMLElement;
      expect(
        await within(section).findByText("Endpoint materialization results are unavailable"),
      ).toBeVisible();
      expect(
        within(section).queryByRole("list", { name: "Endpoint materialization results" }),
      ).toBeNull();
      expect(section).not.toHaveTextContent(
        /protected\.item|broker\.internal|private-topic|hidden-secret|private detail|site\.other/i,
      );
    },
  );

  it("fails closed when endpoint materialization IDs or lease IDs are duplicated", async () => {
    mockReadResponses({
      endpointMaterializations: [
        endpointMaterialization,
        {
          ...endpointMaterialization,
          materialization_id: "workflow-endpoint-materialization.abcdef1234567890",
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Endpoint materialization results",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Endpoint materialization results are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Endpoint materialization results" }),
    ).toBeNull();
  });

  it("renders the backend credential materialization inventory contract without controls", async () => {
    mockReadResponses({ credentialMaterializations: [credentialMaterialization] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Credential materialization outcomes",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-credential-materializations",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(credentialMaterialization.materialization_id)).toBeVisible();
    expect(within(section).getByTitle(credentialMaterialization.lease_id)).toBeVisible();
    expect(within(section).getByTitle(credentialMaterialization.assignment_revision)).toBeVisible();
    expect(records).toHaveTextContent("Protected result recorded");
    expect(records).toHaveTextContent("Protected storage verified true");
    expect(records).toHaveTextContent(
      /endpoint resolution false.*protected artifact access false.*route selection false.*route binding false.*credential selection false.*credential assignment binding false.*credential access false.*credential brokerage false.*credential resolution false.*credential delivery false.*network access false.*readiness probe false.*publication false.*delivery false.*dispatch false.*execution false.*infrastructure mutation false/i,
    );
    expect(
      within(section).queryByRole("button", {
        name: /consume|materialize|retry|reveal|copy|download|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent("hidden-secret");
    expect(section).not.toHaveTextContent("vault/private");
    expect(section).not.toHaveTextContent("broker.internal");
    expect(section).not.toHaveTextContent("provider payload");
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders an uncertain consumed outcome as non-retryable evidence", async () => {
    mockReadResponses({
      credentialMaterializations: [
        {
          ...credentialMaterialization,
          recorded_at: null,
          outcome: "uncertain_consumed",
          protected_storage_verified: false,
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Outcome uncertain")).toBeVisible();
    expect(section).toHaveTextContent("Recorded No known result");
    expect(section).toHaveTextContent("normal-session inventory is read-only");
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders a known credential materialization failure as consumed evidence", async () => {
    mockReadResponses({
      credentialMaterializations: [
        {
          ...credentialMaterialization,
          outcome: "failed_closed_consumed",
          protected_storage_verified: false,
        },
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Materialization failed closed")).toBeVisible();
    expect(section).toHaveTextContent("Protected storage verified false");
    expect(section).toHaveTextContent("lease consumed true");
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders an empty credential materialization inventory as a healthy read-only state", async () => {
    mockReadResponses({ credentialMaterializations: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No credential materialization outcomes are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows credential materialization loading without an operation control", async () => {
    mockReadResponses({
      pendingCredentialMaterializationResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading credential materialization evidence..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries only a failed credential materialization evidence read", async () => {
    mockReadResponses({
      credentialMaterializations: [credentialMaterialization],
      credentialMaterializationStatuses: [500, 200],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential materialization evidence is unavailable"),
    ).toBeVisible();
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry credential materialization evidence read",
      }),
    );
    expect(await within(section).findByTitle(credentialMaterialization.materialization_id)).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Credential materialization evidence permission is missing",
      "current role or scope cannot inspect credential materialization evidence",
    ],
  ])(
    "handles credential materialization read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ credentialMaterializationStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Credential materialization outcomes",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["secret material", { ...credentialMaterialization, secret: "hidden-secret" }],
    ["a vault locator", { ...credentialMaterialization, vault_path: "vault/private" }],
    ["provider data", { ...credentialMaterialization, provider_payload: "private" }],
    ["a future consumption", { ...credentialMaterialization, consumed_at: "2026-08-14T10:08:21Z" }],
    [
      "an inconsistent success",
      { ...credentialMaterialization, protected_storage_verified: false },
    ],
    [
      "authority",
      {
        ...credentialMaterialization,
        authority: {
          ...credentialMaterialization.authority,
          credential_access_authorized: true,
        },
      },
    ],
    [
      "an extra authority field",
      {
        ...credentialMaterialization,
        authority: { ...credentialMaterialization.authority, materialize_authorized: false },
      },
    ],
  ])("fails closed when a credential materialization outcome contains %s", async (_case, unsafe) => {
    mockReadResponses({ credentialMaterializations: [unsafe] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential materialization evidence is unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Credential materialization outcomes",
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/hidden-secret|vault\/private|provider payload/i);
  });

  it("rejects the obsolete split attempt/result shape instead of misreading backend JSON", async () => {
    const obsoleteResponse = new Response(
      JSON.stringify({
        data: {
          physical_transport_credential_materialization_attempts: [credentialMaterialization],
          physical_transport_credential_materialization_results: [],
          server_time: "2026-08-14T10:08:20Z",
          durable: true,
        },
        meta: {
          correlation_id: "correlation.workflow.credential-materialization",
          generated_at: "2026-08-14T10:08:20Z",
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    mockReadResponses({
      pendingCredentialMaterializationResponse: Promise.resolve(obsoleteResponse),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Credential materialization outcomes",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Credential materialization evidence is unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Credential materialization outcomes" }),
    ).toBeNull();
  });

  it("renders active and expired target context bindings without operational controls", async () => {
    const expiredBinding: WorkflowPhysicalTransportTargetContextBinding = {
      ...targetContextBinding,
      binding_id: "workflow-target-context-binding.abcdef1234567890",
      endpoint_materialization_id: "workflow-endpoint-materialization.abcdef1234567890",
      credential_materialization_id: "workflow-credential-materialization.abcdef1234567890",
      effective_state: "expired",
      bound_at: "2026-08-14T10:07:00Z",
      joint_usable_until: "2026-08-14T10:08:00Z",
    };
    mockReadResponses({
      targetContextBindings: [targetContextBinding, expiredBinding],
      targetContextBindingServerTime: "2026-08-14T10:08:20Z",
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target context bindings",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target context bindings",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-bindings",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(targetContextBinding.binding_id)).toBeVisible();
    expect(
      within(section).getByTitle(targetContextBinding.endpoint_materialization_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(targetContextBinding.credential_materialization_id),
    ).toBeVisible();
    expect(records).toHaveTextContent("Same target verified");
    expect(records).toHaveTextContent("Binding expired");
    expect(records).toHaveTextContent(
      /endpoint resolution false.*protected artifact access false.*route selection false.*route binding false.*credential selection false.*credential assignment binding false.*credential access false.*credential brokerage false.*credential resolution false.*credential delivery false.*network access false.*readiness probe false.*publication false.*delivery false.*dispatch false.*execution false.*infrastructure mutation false/i,
    );
    expect(
      within(section).queryByRole("button", {
        name: /bind|access|retry|reveal|copy|download|connect|publish|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /artifact[-_ ]?(?:id|digest)|target commitment|canonical digest|source digest|policy digest|hostname|https?:\/\/|\bIP\b|\bport\b|credential detail|secret|provider detail|broker detail|broker\.internal/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders an empty target context binding inventory as a healthy read-only state", async () => {
    mockReadResponses({ targetContextBindings: [] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target context bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("No target context bindings are recorded in this scope."),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows target context binding loading without an operation control", async () => {
    mockReadResponses({
      pendingTargetContextBindingResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target context bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading target context binding evidence..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Target context binding evidence permission is missing",
      "current role or scope cannot inspect target context binding evidence",
    ],
    [
      500,
      "Target context binding evidence is unavailable",
      "No target relationship or operational state is inferred",
    ],
  ])(
    "handles target context binding read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextBindingStatus: status });
      renderWorkspace();

      const section = (await screen.findByRole("heading", {
        name: "Target context bindings",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      if (status !== 401) expect(section).not.toHaveTextContent("Sign in again");
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["an artifact identifier", { ...targetContextBinding, artifact_id: "protected.artifact" }],
    [
      "a target commitment",
      { ...targetContextBinding, target_context_commitment: "a".repeat(64) },
    ],
    ["an endpoint coordinate", { ...targetContextBinding, hostname: "broker.internal" }],
    ["credential detail", { ...targetContextBinding, credential: "hidden-secret" }],
    [
      "authority",
      {
        ...targetContextBinding,
        authority: { ...targetContextBinding.authority, network_access_authorized: true },
      },
    ],
    [
      "an extra authority field",
      {
        ...targetContextBinding,
        authority: { ...targetContextBinding.authority, bind_authorized: false },
      },
    ],
  ])("fails closed when a target context binding contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextBindings: [unsafe] });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target context bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Target context binding evidence is unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Target context bindings" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/protected\.artifact|broker\.internal|hidden-secret/i);
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("rejects the old internal target context binding shape", async () => {
    const obsoleteResponse = new Response(
      JSON.stringify({
        data: {
          target_context_bindings: [
            {
              ...targetContextBinding,
              target_context_commitment: "a".repeat(64),
              canonical_digest: "b".repeat(64),
            },
          ],
          server_time: "2026-08-14T10:08:20Z",
          durable: true,
        },
        meta: {
          correlation_id: "correlation.workflow.target-context-binding",
          generated_at: "2026-08-14T10:08:20Z",
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    mockReadResponses({
      pendingTargetContextBindingResponse: Promise.resolve(obsoleteResponse),
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target context bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Target context binding evidence is unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Target context bindings" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/target context commitment|canonical digest/i);
  });

  it("renders target-context access authorization leases as minimized read-only evidence", async () => {
    const expiredLease: WorkflowPhysicalTransportTargetContextAccessAuthorizationLease = {
      ...targetContextAccessAuthorizationLease,
      authorization_lease_id:
        "workflow-physical-transport-target-context-access-authorization-lease.abcdef1234567890",
      issued_at: "2026-08-14T10:08:10Z",
      valid_until: "2026-08-14T10:08:15Z",
      effective_state: "expired",
    };
    mockReadResponses({
      targetContextAccessAuthorizationLeases: [
        targetContextAccessAuthorizationLease,
        expiredLease,
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target-context access authorization leases",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target-context access authorization leases",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-access-authorization-leases",
        ),
      ),
    ).toBe(true);
    expect(
      within(section).getByTitle(targetContextAccessAuthorizationLease.authorization_lease_id),
    ).toBeVisible();
    expect(
      within(section).getAllByTitle(targetContextAccessAuthorizationLease.policy.policy_id),
    ).toHaveLength(2);
    expect(
      within(section).getAllByTitle(targetContextAccessAuthorizationLease.integrity_reference),
    ).toHaveLength(2);
    expect(records).toHaveTextContent("Active");
    expect(records).toHaveTextContent("Expired");
    expect(records).toHaveTextContent("Single use true | renewable false | transferable false");
    expect(records).toHaveTextContent(
      /endpoint resolution false.*protected artifact access true.*route selection false.*route binding false.*credential selection false.*credential assignment binding false.*credential access false.*credential brokerage false.*credential resolution false.*credential delivery false.*network access false.*readiness probe false.*publication false.*delivery false.*dispatch false.*execution false.*infrastructure mutation false/i,
    );
    expect(
      within(section).queryByRole("button", {
        name: /create|consume|access|reveal|copy|download|deliver|connect|probe|publish|retry|dispatch|execute|mutate/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /binding[-_ ]?(?:id|digest|commitment)|materialization[-_ ]?(?:id|digest)|artifact[-_ ]?(?:id|digest)|attestation|store locator|endpoint coordinate|credential detail|provider|fence|request fingerprint|idempotency|canonical digest|policy digest/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders empty and loading target-context access lease states without controls", async () => {
    mockReadResponses({ targetContextAccessAuthorizationLeases: [] });
    const view = renderWorkspace();
    let section = (await screen.findByRole("heading", {
      name: "Target-context access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No target-context access authorization leases are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();

    view.unmount();
    mockReadResponses({
      pendingTargetContextAccessAuthorizationLeaseResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();
    section = (await screen.findByRole("heading", {
      name: "Target-context access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading target-context access authorization leases..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Target-context access authorization lease permission is missing",
      "current role or scope cannot inspect target-context access authorization leases",
    ],
    [
      500,
      "Target-context access authorization leases are unavailable",
      "No protected-access authority or operational state is inferred",
    ],
  ])(
    "handles target-context access lease read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextAccessAuthorizationLeaseStatus: status });
      renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Target-context access authorization leases",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/MFA|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a binding identifier", { ...targetContextAccessAuthorizationLease, binding_id: "binding.hidden" }],
    [
      "an attestation",
      { ...targetContextAccessAuthorizationLease, attestation_id: "attestation.hidden" },
    ],
    [
      "an extra policy field",
      {
        ...targetContextAccessAuthorizationLease,
        policy: { ...targetContextAccessAuthorizationLease.policy, policy_digest: "a".repeat(64) },
      },
    ],
    [
      "an extra authority",
      {
        ...targetContextAccessAuthorizationLease,
        authority: { ...targetContextAccessAuthorizationLease.authority, consume_authorized: false },
      },
    ],
    [
      "runtime authority",
      {
        ...targetContextAccessAuthorizationLease,
        authority: {
          ...targetContextAccessAuthorizationLease.authority,
          execution_authorized: true,
        },
      },
    ],
  ])("fails closed when a target-context access lease contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextAccessAuthorizationLeases: [unsafe] });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context access authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Target-context access authorization leases are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Target-context access authorization leases",
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/binding\.hidden|attestation\.hidden/i);
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders target-context artifact opening attempts and results as minimized read-only evidence", async () => {
    const pendingOpening: WorkflowPhysicalTransportTargetContextArtifactOpening = {
      ...targetContextArtifactOpening,
      opening_id: "workflow-target-context-artifact-opening.pending1234567890",
      attempt_state: "started",
      result_state: "pending",
      completed_at: null,
    };
    const failedOpening: WorkflowPhysicalTransportTargetContextArtifactOpening = {
      ...targetContextArtifactOpening,
      opening_id: "workflow-target-context-artifact-opening.failed1234567890",
      result_state: "opening_failed",
    };
    const uncertainOpening: WorkflowPhysicalTransportTargetContextArtifactOpening = {
      ...targetContextArtifactOpening,
      opening_id: "workflow-target-context-artifact-opening.uncertain1234567890",
      attempt_state: "started",
      result_state: "outcome_uncertain",
      completed_at: null,
    };
    mockReadResponses({
      targetContextArtifactOpenings: [
        targetContextArtifactOpening,
        pendingOpening,
        failedOpening,
        uncertainOpening,
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target-context artifact openings",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target-context artifact openings",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-artifact-openings",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(targetContextArtifactOpening.opening_id)).toBeVisible();
    expect(within(section).getAllByTitle(targetContextArtifactOpening.policy.policy_id)).toHaveLength(
      4,
    );
    expect(
      within(section).getAllByTitle(targetContextArtifactOpening.integrity_reference),
    ).toHaveLength(4);
    expect(records).toHaveTextContent("opened protected");
    expect(records).toHaveTextContent("pending");
    expect(records).toHaveTextContent("opening failed");
    expect(records).toHaveTextContent("outcome uncertain");
    expect(records).toHaveTextContent("Started");
    expect(records).toHaveTextContent("Completed");
    expect(records).toHaveTextContent("Not recorded");
    expect(records).toHaveTextContent(
      /Zero authority: this evidence grants no protected artifact access.*endpoint or credential disclosure.*delivery.*network.*readiness probe.*publication.*dispatch.*execution.*infrastructure mutation authority/i,
    );
    expect(
      within(section).queryByRole("button", {
        name: /open|retry|reveal|copy|download|connect|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /capsule|artifact[-_ ]?(?:id|digest)|attestation|endpoint[-_ ]?(?:id|coordinate)|credential[-_ ]?(?:id|detail)|route[-_ ]?(?:id|digest)|provider|canonical digest|fence|idempotency/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders empty and loading target-context artifact opening states without controls", async () => {
    mockReadResponses({ targetContextArtifactOpenings: [] });
    const view = renderWorkspace();
    let section = (await screen.findByRole("heading", {
      name: "Target-context artifact openings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No target-context artifact openings are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();

    view.unmount();
    mockReadResponses({
      pendingTargetContextArtifactOpeningResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();
    section = (await screen.findByRole("heading", {
      name: "Target-context artifact openings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading target-context artifact opening evidence..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Target-context artifact opening permission is missing",
      "current role or scope cannot inspect target-context artifact opening evidence",
    ],
    [
      500,
      "Target-context artifact openings are unavailable",
      "No opening result, protected-access authority, or operational state is inferred",
    ],
  ])(
    "handles target-context artifact opening read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextArtifactOpeningStatus: status });
      renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Target-context artifact openings",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a capsule", { ...targetContextArtifactOpening, capsule_id: "capsule.hidden" }],
    ["an artifact", { ...targetContextArtifactOpening, artifact_id: "artifact.hidden" }],
    ["an attestation", { ...targetContextArtifactOpening, attestation_id: "attestation.hidden" }],
    ["a route", { ...targetContextArtifactOpening, route_id: "route.hidden" }],
    ["a provider", { ...targetContextArtifactOpening, provider_id: "provider.hidden" }],
    ["a digest", { ...targetContextArtifactOpening, result_digest: "a".repeat(64) }],
    ["a fence", { ...targetContextArtifactOpening, fencing_token: 9 }],
    ["an idempotency key", { ...targetContextArtifactOpening, idempotency_key: "hidden" }],
    [
      "an extra policy field",
      {
        ...targetContextArtifactOpening,
        policy: { ...targetContextArtifactOpening.policy, policy_digest: "a".repeat(64) },
      },
    ],
    [
      "an extra authority",
      {
        ...targetContextArtifactOpening,
        authority: { ...targetContextArtifactOpening.authority, open_authorized: false },
      },
    ],
    [
      "runtime authority",
      {
        ...targetContextArtifactOpening,
        authority: { ...targetContextArtifactOpening.authority, execution_authorized: true },
      },
    ],
    [
      "an inconsistent pending completion",
      { ...targetContextArtifactOpening, result_state: "pending", completed_at: null },
    ],
  ])("fails closed when a target-context artifact opening contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextArtifactOpenings: [unsafe] });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context artifact openings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Target-context artifact openings are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Target-context artifact openings" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /capsule\.hidden|artifact\.hidden|attestation\.hidden|route\.hidden|provider\.hidden/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders capsule consumer bindings as minimized immutable read-only evidence", async () => {
    mockReadResponses({
      targetContextCapsuleConsumerBindings: [targetContextCapsuleConsumerBinding],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule consumer bindings",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target-context capsule consumer bindings",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-capsule-consumer-bindings",
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(targetContextCapsuleConsumerBinding.binding_id)).toBeVisible();
    expect(
      within(section).getByTitle(targetContextCapsuleConsumerBinding.consumer_contract_id),
    ).toBeVisible();
    expect(within(section).getByTitle(targetContextCapsuleConsumerBinding.purpose_id)).toBeVisible();
    expect(records).toHaveTextContent("bound");
    expect(records).toHaveTextContent(
      /Zero authority: this immutable evidence cannot reveal.*copy.*download.*hand off.*unseal.*deliver.*connect.*probe.*publish.*dispatch.*execute.*mutate infrastructure/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
    expect(section).not.toHaveTextContent(
      /capsule\.secret|opening-result digest|artifact[-_ ]?(?:id|digest)|outbox[-_ ]?(?:id|digest)|route[-_ ]?(?:id|digest)|assignment[-_ ]?(?:id|digest)|idempotency|fencing token/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders empty and fail-closed capsule consumer binding states without controls", async () => {
    mockReadResponses({ targetContextCapsuleConsumerBindings: [] });
    const view = renderWorkspace();
    let section = (await screen.findByRole("heading", {
      name: "Target-context capsule consumer bindings",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("No capsule consumer bindings are recorded in this scope."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();

    view.unmount();
    mockReadResponses({ targetContextCapsuleConsumerBindingStatus: 503 });
    renderWorkspace();
    section = (await screen.findByRole("heading", {
      name: "Target-context capsule consumer bindings",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Capsule consumer bindings are unavailable")).toBeVisible();
    expect(
      within(section).getByText(/No capsule, consumer authority, handoff readiness/i),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Capsule consumer binding permission is missing",
      "current role or scope cannot inspect capsule consumer binding evidence",
    ],
  ])(
    "handles capsule consumer binding read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextCapsuleConsumerBindingStatus: status });
      renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Target-context capsule consumer bindings",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a capsule id", { ...targetContextCapsuleConsumerBinding, sealed_capsule_id: "capsule.secret" }],
    ["an opening digest", { ...targetContextCapsuleConsumerBinding, opening_result_digest: "a".repeat(64) }],
    ["an artifact", { ...targetContextCapsuleConsumerBinding, event_artifact_id: "artifact.secret" }],
    ["an outbox", { ...targetContextCapsuleConsumerBinding, outbox_entry_id: "outbox.secret" }],
    ["a route", { ...targetContextCapsuleConsumerBinding, route_binding_id: "route.secret" }],
    ["an assignment", { ...targetContextCapsuleConsumerBinding, assignment_id: "assignment.secret" }],
    [
      "an unrecognized consumer contract",
      {
        ...targetContextCapsuleConsumerBinding,
        consumer_contract_id: "contract.workflow-unrecognized-consumer",
      },
    ],
    [
      "an unrecognized purpose",
      {
        ...targetContextCapsuleConsumerBinding,
        purpose_id: "purpose.workflow-unrecognized-consumer",
      },
    ],
    [
      "runtime authority",
      {
        ...targetContextCapsuleConsumerBinding,
        authority: {
          ...targetContextCapsuleConsumerBinding.authority,
          execution_authorized: true,
        },
      },
    ],
    [
      "an extra policy field",
      {
        ...targetContextCapsuleConsumerBinding,
        policy: { ...targetContextCapsuleConsumerBinding.policy, policy_digest: "b".repeat(64) },
      },
    ],
  ])("fails closed when a capsule consumer binding contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextCapsuleConsumerBindings: [unsafe] });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule consumer bindings",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Capsule consumer bindings are unavailable")).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Target-context capsule consumer bindings" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(/capsule\.secret|artifact\.secret|outbox\.secret|route\.secret|assignment\.secret/i);
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("renders capsule handoff authorization leases as minimized read-only evidence", async () => {
    const expiredLease: WorkflowPhysicalTransportTargetContextCapsuleHandoffAuthorizationLease = {
      ...targetContextCapsuleHandoffAuthorizationLease,
      authorization_lease_id:
        "workflow-target-context-capsule-handoff-authorization-lease.abcdef1234567890",
      issued_at: "2026-08-14T10:08:20Z",
      valid_until: "2026-08-14T10:08:21Z",
      effective_state: "expired",
    };
    mockReadResponses({
      targetContextCapsuleHandoffAuthorizationLeases: [
        targetContextCapsuleHandoffAuthorizationLease,
        expiredLease,
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoff authorization leases",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target-context capsule handoff authorization leases",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-capsule-handoff-authorization-leases",
        ),
      ),
    ).toBe(true);
    expect(
      within(section).getByTitle(
        targetContextCapsuleHandoffAuthorizationLease.authorization_lease_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getAllByTitle(
        targetContextCapsuleHandoffAuthorizationLease.consumer_contract_id,
      ),
    ).toHaveLength(2);
    expect(
      within(section).getAllByTitle(targetContextCapsuleHandoffAuthorizationLease.purpose_id),
    ).toHaveLength(2);
    expect(records).toHaveTextContent("Active");
    expect(records).toHaveTextContent("Expired");
    expect(records).toHaveTextContent(
      "Single use true | renewable false | transferable false | bearer capability false",
    );
    expect(records).toHaveTextContent(
      /target-context capsule handoff true.*endpoint resolution false.*route selection false.*route binding false.*credential selection false.*credential assignment binding false.*credential access false.*credential brokerage false.*credential resolution false.*protected artifact access false.*credential delivery false.*network access false.*readiness probe false.*publication false.*delivery false.*dispatch false.*execution false.*infrastructure mutation false/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
    expect(section).not.toHaveTextContent(
      /binding[-_ ]?(?:id|digest)|capsule[-_ ]?(?:id|digest)|opening[-_ ]?(?:id|digest)|artifact[-_ ]?(?:id|digest)|outbox[-_ ]?(?:id|digest)|route[-_ ]?(?:id|digest)|assignment[-_ ]?(?:id|digest)|idempotency|fenc(?:e|ing)|attestation|request fingerprint|policy digest/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders empty and loading capsule handoff authorization lease states without controls", async () => {
    mockReadResponses({ targetContextCapsuleHandoffAuthorizationLeases: [] });
    const view = renderWorkspace();
    let section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoff authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "No capsule handoff authorization leases are recorded in this scope.",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();

    view.unmount();
    mockReadResponses({
      pendingTargetContextCapsuleHandoffAuthorizationLeaseResponse: new Promise<Response>(
        () => undefined,
      ),
    });
    renderWorkspace();
    section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoff authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText(
        "Loading capsule handoff authorization lease evidence...",
      ),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
  });

  it("fails closed when capsule handoff authorization storage is not durable", async () => {
    mockReadResponses({
      targetContextCapsuleHandoffAuthorizationLeases: [
        targetContextCapsuleHandoffAuthorizationLease,
      ],
      targetContextCapsuleHandoffAuthorizationLeaseDurable: false,
    });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoff authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Capsule handoff authorization leases are unavailable"),
    ).toBeVisible();
    expect(within(section).queryByRole("list")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Capsule handoff authorization lease permission is missing",
      "current role or scope cannot inspect capsule handoff authorization lease evidence",
    ],
    [
      503,
      "Capsule handoff authorization leases are unavailable",
      "No handoff authority, capsule state, or operational state is inferred",
    ],
  ])(
    "handles capsule handoff authorization lease read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextCapsuleHandoffAuthorizationLeaseStatus: status });
      renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Target-context capsule handoff authorization leases",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(within(section).queryByRole("link")).toBeNull();
      expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
    },
  );

  it.each([
    ["a binding identifier", { ...targetContextCapsuleHandoffAuthorizationLease, binding_id: "binding.hidden" }],
    ["a capsule identifier", { ...targetContextCapsuleHandoffAuthorizationLease, capsule_id: "capsule.hidden" }],
    ["an opening identifier", { ...targetContextCapsuleHandoffAuthorizationLease, opening_id: "opening.hidden" }],
    ["an artifact identifier", { ...targetContextCapsuleHandoffAuthorizationLease, artifact_id: "artifact.hidden" }],
    ["an outbox identifier", { ...targetContextCapsuleHandoffAuthorizationLease, outbox_entry_id: "outbox.hidden" }],
    ["a route identifier", { ...targetContextCapsuleHandoffAuthorizationLease, route_binding_id: "route.hidden" }],
    ["an assignment identifier", { ...targetContextCapsuleHandoffAuthorizationLease, assignment_id: "assignment.hidden" }],
    ["idempotency metadata", { ...targetContextCapsuleHandoffAuthorizationLease, idempotency_key: "hidden" }],
    ["a fence", { ...targetContextCapsuleHandoffAuthorizationLease, fencing_token: 9 }],
    ["an attestation", { ...targetContextCapsuleHandoffAuthorizationLease, attestation_id: "attestation.hidden" }],
    [
      "an extra policy field",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        policy: {
          ...targetContextCapsuleHandoffAuthorizationLease.policy,
          policy_digest: "a".repeat(64),
        },
      },
    ],
    [
      "an extra authority",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        authority: {
          ...targetContextCapsuleHandoffAuthorizationLease.authority,
          consume_authorized: false,
        },
      },
    ],
    [
      "missing handoff authority",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        authority: {
          ...targetContextCapsuleHandoffAuthorizationLease.authority,
          target_context_capsule_handoff_authorized: false,
        },
      },
    ],
    [
      "general delivery authority",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        authority: {
          ...targetContextCapsuleHandoffAuthorizationLease.authority,
          delivery_authorized: true,
        },
      },
    ],
    [
      "bearer capability",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        lease_is_bearer_capability: true,
      },
    ],
    [
      "a shortened lifetime",
      {
        ...targetContextCapsuleHandoffAuthorizationLease,
        valid_until: "2026-08-14T10:08:25.999Z",
      },
    ],
  ])("fails closed when a capsule handoff authorization lease contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextCapsuleHandoffAuthorizationLeases: [unsafe] });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoff authorization leases",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Capsule handoff authorization leases are unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", {
        name: "Target-context capsule handoff authorization leases",
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /binding\.hidden|capsule\.hidden|opening\.hidden|artifact\.hidden|outbox\.hidden|route\.hidden|assignment\.hidden|attestation\.hidden/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
  });

  it("renders sealed capsule handoff outcomes as minimized read-only evidence", async () => {
    const failed: WorkflowPhysicalTransportTargetContextCapsuleHandoff = {
      ...targetContextCapsuleHandoff,
      handoff_id: "workflow-target-context-capsule-handoff.failed1234567890",
      result_state: "handoff_failed",
      sealed_capsule_handed_off: false,
    };
    const uncertain: WorkflowPhysicalTransportTargetContextCapsuleHandoff = {
      ...targetContextCapsuleHandoff,
      handoff_id: "workflow-target-context-capsule-handoff.uncertain1234567890",
      attempt_state: "started",
      result_state: "handoff_outcome_uncertain",
      completed_at: null,
      sealed_capsule_handed_off: false,
    };
    const recordedUncertain: WorkflowPhysicalTransportTargetContextCapsuleHandoff = {
      ...targetContextCapsuleHandoff,
      handoff_id: "workflow-target-context-capsule-handoff.recordeduncertain1234",
      result_state: "handoff_outcome_uncertain",
      sealed_capsule_handed_off: false,
    };
    mockReadResponses({
      targetContextCapsuleHandoffs: [
        targetContextCapsuleHandoff,
        failed,
        uncertain,
        recordedUncertain,
      ],
    });
    renderWorkspace();

    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoffs",
    })).closest("section") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Target-context capsule handoffs",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          "/api/v1/workflows/physical-transport-target-context-capsule-handoffs",
        ),
      ),
    ).toBe(true);
    expect(records).toHaveTextContent("handed off sealed");
    expect(records).toHaveTextContent("handoff failed");
    expect(records).toHaveTextContent("handoff outcome uncertain");
    expect(records).toHaveTextContent("Sealed capsule handed off true");
    expect(records).toHaveTextContent("consumer receipt bearer capability false");
    expect(records).toHaveTextContent(
      /all authorities false: target-context capsule handoff false.*endpoint resolution false.*route selection false.*route binding false.*credential selection false.*credential assignment binding false.*credential access false.*credential brokerage false.*credential resolution false.*protected artifact access false.*credential delivery false.*network access false.*readiness probe false.*publication false.*delivery false.*dispatch false.*execution false.*infrastructure mutation false/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
    expect(section).not.toHaveTextContent(
      /lease[-_ ]?(?:id|digest)|binding[-_ ]?(?:id|digest)|capsule[-_ ]?(?:id|digest)|receipt[-_ ]?(?:id|digest)|attestation|source[-_ ]?(?:id|handle|locator)|destination[-_ ]?(?:id|handle|coordinate)|route[-_ ]?(?:id|digest)|assignment[-_ ]?(?:id|digest)|idempotency|fenc(?:e|ing)/i,
    );
    expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
  });

  it("renders empty and loading sealed capsule handoff states without controls", async () => {
    mockReadResponses({ targetContextCapsuleHandoffs: [] });
    const view = renderWorkspace();
    let section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoffs",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("No sealed capsule handoffs are recorded in this scope."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();

    view.unmount();
    mockReadResponses({
      pendingTargetContextCapsuleHandoffResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();
    section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoffs",
    })).closest("section") as HTMLElement;
    expect(
      await within(section).findByText("Loading sealed capsule handoff evidence..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
  });

  it("fails closed when sealed capsule handoff storage is not durable", async () => {
    mockReadResponses({
      targetContextCapsuleHandoffs: [targetContextCapsuleHandoff],
      targetContextCapsuleHandoffDurable: false,
    });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoffs",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Capsule handoff evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Capsule handoff evidence permission is missing",
      "current role or scope cannot inspect sealed capsule handoff evidence",
    ],
    [
      503,
      "Capsule handoff evidence is unavailable",
      "No handoff result, capsule state, or operational authority is inferred",
    ],
  ])(
    "handles sealed capsule handoff read status %s in the normal browser session",
    async (status, title, detail) => {
      mockReadResponses({ targetContextCapsuleHandoffStatus: status });
      renderWorkspace();
      const section = (await screen.findByRole("heading", {
        name: "Target-context capsule handoffs",
      })).closest("section") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(within(section).queryByRole("link")).toBeNull();
      expect(section).not.toHaveTextContent(/\bMFA\b|second login|authorized browser session/i);
    },
  );

  it.each([
    [
      "an extra lease identifier",
      { ...targetContextCapsuleHandoff, authorization_lease_id: "lease.hidden" },
    ],
    [
      "an extra receipt identifier",
      { ...targetContextCapsuleHandoff, consumer_receipt_id: "receipt.hidden" },
    ],
    [
      "an extra source handle",
      { ...targetContextCapsuleHandoff, source_handle: "source.hidden" },
    ],
    [
      "an extra destination handle",
      { ...targetContextCapsuleHandoff, destination_handle: "destination.hidden" },
    ],
    [
      "an extra destination boundary identity",
      { ...targetContextCapsuleHandoff, destination_boundary_id: "boundary.hidden" },
    ],
    [
      "an extra deployment identity",
      { ...targetContextCapsuleHandoff, deployment_id: "deployment.hidden" },
    ],
    [
      "an extra generation",
      { ...targetContextCapsuleHandoff, destination_generation: 3 },
    ],
    [
      "an extra fencing token",
      { ...targetContextCapsuleHandoff, destination_fencing_token: "fence.hidden" },
    ],
    [
      "an extra custody contract",
      { ...targetContextCapsuleHandoff, custody_contract_id: "custody.hidden" },
    ],
    [
      "an extra signing key",
      { ...targetContextCapsuleHandoff, verification_signing_key_id: "key.hidden" },
    ],
    [
      "an extra trusted profile digest",
      { ...targetContextCapsuleHandoff, trusted_profile_digest: "a".repeat(64) },
    ],
    [
      "a missing attempt identity",
      Object.fromEntries(
        Object.entries(targetContextCapsuleHandoff).filter(([field]) => field !== "handoff_id"),
      ),
    ],
    [
      "a missing authority declaration",
      {
        ...targetContextCapsuleHandoff,
        authority: Object.fromEntries(
          Object.entries(targetContextCapsuleHandoff.authority).filter(
            ([field]) => field !== "target_context_capsule_handoff_authorized",
          ),
        ),
      },
    ],
    [
      "handoff authority",
      {
        ...targetContextCapsuleHandoff,
        authority: {
          ...targetContextCapsuleHandoff.authority,
          target_context_capsule_handoff_authorized: true,
        },
      },
    ],
    [
      "general delivery authority",
      {
        ...targetContextCapsuleHandoff,
        authority: {
          ...targetContextCapsuleHandoff.authority,
          delivery_authorized: true,
        },
      },
    ],
    [
      "an extra authority field",
      {
        ...targetContextCapsuleHandoff,
        authority: { ...targetContextCapsuleHandoff.authority, consume_authorized: false },
      },
    ],
    [
      "a bearer receipt",
      { ...targetContextCapsuleHandoff, consumer_receipt_is_bearer_capability: true },
    ],
    [
      "an inconsistent handed-off result",
      { ...targetContextCapsuleHandoff, sealed_capsule_handed_off: false },
    ],
    [
      "an extra policy field",
      {
        ...targetContextCapsuleHandoff,
        policy: { ...targetContextCapsuleHandoff.policy, policy_digest: "a".repeat(64) },
      },
    ],
  ])("fails closed when a sealed capsule handoff contains %s", async (_case, unsafe) => {
    mockReadResponses({ targetContextCapsuleHandoffs: [unsafe] });
    renderWorkspace();
    const section = (await screen.findByRole("heading", {
      name: "Target-context capsule handoffs",
    })).closest("section") as HTMLElement;
    expect(await within(section).findByText("Capsule handoff evidence is unavailable")).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Target-context capsule handoffs" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /lease\.hidden|receipt\.hidden|source\.hidden|destination\.hidden|boundary\.hidden|deployment\.hidden|fence\.hidden|custody\.hidden|key\.hidden/i,
    );
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByRole("link")).toBeNull();
  });

  it("creates and presents a planned-only workflow without requesting another login", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Available definitions" })).toBeVisible();
    expect(screen.getByText("No execution authority")).toBeVisible();
    expect(screen.queryByText(/authorized browser session/i)).toBeNull();
    fireEvent.change(screen.getByLabelText("Definition"), {
      target: { value: definition.definition_id },
    });
    fireEvent.change(screen.getByLabelText("Authorized storage target"), {
      target: { value: "asset.storage.test" },
    });
    fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Review evidence" } });
    fireEvent.change(screen.getByLabelText("Input summary"), {
      target: { value: "Use current observations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));

    await waitFor(() => expect(createWorkflowPlan).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("heading", { name: plan.plan_id })).toBeVisible();
    expect(screen.getByText(/No connector, approval, ITSM, runbook, worker/i)).toBeVisible();
    expect(screen.getAllByText("planned").length).toBeGreaterThan(0);
  });

  it("cancels a selected planned plan and preserves its immutable history", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    const confirm = screen.getByRole("button", { name: "Confirm cancellation" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Cancellation reason"), {
      target: { value: "  The assessment is no longer required.  " },
    });
    fireEvent.click(
      screen.getByLabelText(
        "I acknowledge that cancellation preserves history and cannot undo external work.",
      ),
    );
    fireEvent.click(confirm);

    await waitFor(() => expect(cancelWorkflowPlan).toHaveBeenCalledTimes(1));
    expect(cancelWorkflowPlan).toHaveBeenCalledWith(
      expect.objectContaining({
        plan,
        reason: "  The assessment is no longer required.  ",
        acknowledgeNoExternalUndo: true,
      }),
    );
    expect(await screen.findByRole("heading", { name: "State transitions" })).toBeVisible();
    expect(screen.getByText("planned to cancelled")).toBeVisible();
    expect(screen.getByText(/The assessment is no longer required/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Cancel this plan" })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it.each([
    ["active", activeLease],
    [
      "expired",
      { ...activeLease, effective_state: "expired" } satisfies WorkflowOrchestrationLease,
    ],
    [
      "released",
      {
        ...activeLease,
        state: "released",
        effective_state: "released",
      } satisfies WorkflowOrchestrationLease,
    ],
  ] as const)("presents %s lease evidence without human mutation controls", async (state, lease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(state)).toBeVisible();
    expect(screen.getByText("7")).toBeVisible();
    expect(screen.getByText("workload.worker")).toBeVisible();
    expect(screen.getByText(/coordinates ownership only/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /acquire|heartbeat|release/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    expect(screen.getAllByText(/not_started/).length).toBeGreaterThan(0);
  });

  it("presents an empty lease result without inferring ownership", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByText("No orchestration lease is recorded for this plan."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /acquire|heartbeat|release/i })).toBeNull();
  });

  it("fails closed when lease evidence is not bound to the selected plan digest", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease: { ...activeLease, plan_digest: "0".repeat(64) } });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Lease status is unavailable")).toBeVisible();
    expect(screen.getByText(/No lease state is inferred/i)).toBeVisible();
    expect(screen.queryByText("workload.worker")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Lease status permission is missing", "current role cannot inspect"],
    [503, "Lease status is unavailable", "No lease state is inferred"],
  ])("handles lease read status %s without inventing another authentication step", async (
    status,
    title,
    detail,
  ) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ leaseStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    }
  });

  it("presents an empty materialized run result without implying execution", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByText("No materialized run is recorded for this plan."),
    ).toBeVisible();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith("/attempts"),
      ),
    ).toBe(false);
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("presents a request-bound created run and its ordered not-started steps read-only", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease: activeLease, run: materializedRun });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByRole("heading", { name: "Materialized run record" })).toBeVisible();
    expect(await screen.findByTitle("workload.workflow.materializer")).toBeVisible();
    expect(screen.getByText("created")).toBeVisible();
    expect(screen.getAllByText("7")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Materialized step records" })).toHaveTextContent(
      "query-authorized-evidence",
    );
    expect(screen.getByRole("list", { name: "Materialized step records" })).toHaveTextContent(
      "not_started",
    );
    expect(screen.getByText(/freezes run and step identities/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("fails closed on an unsafe materialized run response", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: {
        ...materializedRun,
        plan_digest: "0".repeat(64),
        materialized_by_subject_id: "unsafe.subject",
      },
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Run record is unavailable")).toBeVisible();
    expect(screen.getByText(/No run state is inferred/i)).toBeVisible();
    expect(screen.queryByText("unsafe.subject")).toBeNull();
  });

  it("retries a failed read-only run request without exposing mutation controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let runReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (!url.endsWith("/materialized-run")) return Promise.resolve(leaseResponse(null));
      runReads += 1;
      return Promise.resolve(
        runReads === 1 ? materializedRunResponse(null, 503) : materializedRunResponse(null),
      );
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry run record" }));

    expect(
      await screen.findByText("No materialized run is recorded for this plan."),
    ).toBeVisible();
    expect(runReads).toBe(2);
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Run record permission is missing", "current role cannot inspect materialized"],
  ])("handles run read status %s with the existing sign-in and permission model", async (
    status,
    title,
    detail,
  ) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ runStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry run record" })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("presents an empty attempt inventory only after a materialized run exists", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByRole("heading", { name: "Materialized attempt records" }),
    ).toBeVisible();
    expect(
      await screen.findByText("No materialized attempts are recorded for this run."),
    ).toBeVisible();
    expect(screen.getAllByText("No human controls").length).toBeGreaterThan(0);
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
  });

  it("shows read-only loading state while authoritative attempt evidence is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/attempts")) return new Promise<Response>(() => undefined);
      if (url.endsWith("/materialized-run")) {
        return Promise.resolve(materializedRunResponse(materializedRun));
      }
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Loading authoritative attempt records...")).toBeVisible();
    expect(screen.getAllByText("No human controls").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
  });

  it("renders an exact run-bound root-step attempt as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [materializedAttempt] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const records = await screen.findByRole("list", { name: "Materialized attempt records" });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/api/v1/workflows/plans/${plan.plan_id}/runs/${materializedRun.run_id}/attempts`,
        ),
      ),
    ).toBe(true);
    expect(await screen.findByTitle(materializedAttempt.attempt_id)).toBeVisible();
    expect(records).toHaveTextContent("root step query-authorized-evidence");
    expect(records).toHaveTextContent("created");
    expect(records).toHaveTextContent("fence 7");
    expect(records).toHaveTextContent("run 111111111111...11111111");
    expect(records).toHaveTextContent("step 999999999999...99999999");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("fails closed on unsafe or unbound attempt evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [{ ...materializedAttempt, step_run_digest: "0".repeat(64), password: "unsafe" }],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Attempt evidence is unavailable")).toBeVisible();
    expect(screen.getByText(/No attempt state is inferred/i)).toBeVisible();
    expect(screen.queryByText(/workflow-attempt.1234567890abcdef/i)).toBeNull();
    expect(screen.queryByText(/unsafe/i)).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Attempt evidence permission is missing", "current role cannot inspect materialized"],
    [503, "Attempt evidence is unavailable", "No attempt state is inferred"],
  ])("handles attempt read status %s without exposing an action", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attemptStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /materialize|dispatch|execute/i })).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry attempt evidence" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry attempt evidence" })).toBeNull();
    }
  });

  it("retries a generic attempt read failure and keeps the panel control-free", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let attemptReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/attempts")) {
        attemptReads += 1;
        return Promise.resolve(attemptResponse([], attemptReads === 1 ? 503 : 200));
      }
      if (url.endsWith("/materialized-run")) {
        return Promise.resolve(materializedRunResponse(materializedRun));
      }
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry attempt evidence" }));

    expect(
      await screen.findByText("No materialized attempts are recorded for this run."),
    ).toBeVisible();
    expect(attemptReads).toBe(2);
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
  });

  it("shows dispatch-intent evidence only after a materialized attempt exists", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("No materialized attempts are recorded for this run.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Staged dispatch-intent records" })).toBeNull();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith("/dispatch-intents"),
      ),
    ).toBe(false);
  });

  it("presents an empty read-only dispatch-intent inventory", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [materializedAttempt], dispatchIntents: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByRole("heading", { name: "Staged dispatch-intent records" })).toBeVisible();
    expect(await screen.findByText("No dispatch intents are staged for these attempts.")).toBeVisible();
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("shows a control-free loading state for dispatch-intent evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/dispatch-intents")) return new Promise<Response>(() => undefined);
      if (url.endsWith("/attempts")) return Promise.resolve(attemptResponse([materializedAttempt]));
      if (url.endsWith("/materialized-run")) return Promise.resolve(materializedRunResponse(materializedRun));
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Loading authoritative dispatch-intent records...")).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("renders an exact attempt-bound dispatch intent as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const records = await screen.findByRole("list", { name: "Staged dispatch-intent records" });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/api/v1/workflows/plans/${plan.plan_id}/runs/${materializedRun.run_id}/attempts/${materializedAttempt.attempt_id}/dispatch-intents`,
        ),
      ),
    ).toBe(true);
    expect(await screen.findByTitle(stagedDispatchIntent.dispatch_intent_id)).toBeVisible();
    expect(records).toHaveTextContent("step query-authorized-evidence");
    expect(records).toHaveTextContent("staged");
    expect(records).toHaveTextContent("worker workload.workflow.worker");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("fails closed on unsafe or unbound dispatch-intent evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [
        { ...stagedDispatchIntent, attempt_digest: "0".repeat(64), password: "unsafe" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Dispatch-intent evidence is unavailable")).toBeVisible();
    expect(screen.getByText(/No dispatch state is inferred/i)).toBeVisible();
    expect(screen.queryByText(/workflow-dispatch-intent.1234567890abcdef/i)).toBeNull();
    expect(screen.queryByText(/unsafe/i)).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Dispatch-intent evidence permission is missing", "current role cannot inspect staged"],
    [503, "Dispatch-intent evidence is unavailable", "No dispatch state is inferred"],
  ])("handles dispatch-intent read status %s without exposing an action", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntentStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry intent evidence" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry intent evidence" })).toBeNull();
    }
  });

  it("retries a generic dispatch-intent read failure without adding authority controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let dispatchIntentReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/dispatch-intents")) {
        dispatchIntentReads += 1;
        return Promise.resolve(
          dispatchIntentResponse([], dispatchIntentReads === 1 ? 503 : 200),
        );
      }
      if (url.endsWith("/attempts")) return Promise.resolve(attemptResponse([materializedAttempt]));
      if (url.endsWith("/materialized-run")) return Promise.resolve(materializedRunResponse(materializedRun));
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry intent evidence" }));

    expect(await screen.findByText("No dispatch intents are staged for these attempts.")).toBeVisible();
    expect(dispatchIntentReads).toBe(2);
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("renders pending publication as authoritative, control-free database evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Pending publication outbox records",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/dispatch-intents/${stagedDispatchIntent.dispatch_intent_id}/outbox`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(pendingOutboxEntry.outbox_entry_id)).toBeVisible();
    expect(records).toHaveTextContent("pending publication");
    expect(records).toHaveTextContent("fence 7");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(section).toHaveTextContent("durable database evidence only");
    expect(section).toHaveTextContent("No broker is selected");
    expect(section).toHaveTextContent("no broker address, topic, or routing key");
    expect(section).toHaveTextContent("No publication, delivery, dispatch, or execution occurred or is authorized");
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("fails closed when a staged intent has no atomic outbox record", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Outbox evidence is unavailable")).toBeVisible();
    expect(within(section).getByText(/No publication state is inferred/i)).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Outbox evidence permission is missing", "current role cannot inspect pending publication"],
  ])("handles outbox read status %s without another login or an authority control", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders the current publication lease as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Publication lease evidence",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/dispatch-intents/${stagedDispatchIntent.dispatch_intent_id}/outbox/${pendingOutboxEntry.outbox_entry_id}/publication-lease`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(activePublicationLease.publication_lease_id)).toBeVisible();
    expect(within(section).getByTitle(activePublicationLease.publisher_subject_id)).toBeVisible();
    expect(records).toHaveTextContent("active");
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("orchestration fence 7");
    expect(records).toHaveTextContent("outbox 666666666666...66666666");
    expect(section).toHaveTextContent("grants no publication, delivery, dispatch, or execution authority");
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders an empty publication lease state without treating it as an integrity failure", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No publication lease has been acquired.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("fails closed when more than one current publication lease is returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [
        activePublicationLease,
        { ...activePublicationLease, publication_lease_id: "workflow-publication-lease.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Publication lease evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Publication lease evidence" })).toBeNull();
  });

  it.each([
    ["an extra key", { ...activePublicationLease, unexpected: "unsafe" }],
    ["a broken lineage", { ...activePublicationLease, attempt_id: "workflow-attempt.other" }],
    ["a broken digest", { ...activePublicationLease, outbox_entry_digest: "0".repeat(64) }],
    [
      "a different scope",
      {
        ...activePublicationLease,
        scope: { ...activePublicationLease.scope, site_id: "site.other" },
      },
    ],
    [
      "unsafe embedded authority",
      {
        ...activePublicationLease,
        authority: { ...activePublicationLease.authority, worker_dispatch_authorized: true },
      },
    ],
    ["publication authority", { ...activePublicationLease, grants_publication_authority: true }],
  ])("fails closed when publication lease evidence contains %s", async (_case, unsafeLease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [unsafeLease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Publication lease evidence is unavailable")).toBeVisible();
    expect(within(section).getByText(/No lease or publication state is inferred/i)).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Publication lease evidence" })).toBeNull();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it.each([
    [
      "expired",
      {
        ...activePublicationLease,
        expires_at: "2026-08-13T10:12:30Z",
        effective_state: "expired",
      },
    ],
    [
      "released",
      {
        ...activePublicationLease,
        state: "released",
        effective_state: "released",
      },
    ],
  ])("renders %s publication lease state from validated server evidence", async (state, lease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [lease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(state)).toBeVisible();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Publication lease evidence permission is missing", "current role cannot inspect publication lease"],
  ])("handles publication lease read status %s without another login or action controls", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeaseStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it("renders one canonical event envelope with exact preparation lineage and no authority controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Canonical event-envelope evidence",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/outbox/${pendingOutboxEntry.outbox_entry_id}/event-envelope`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(preparedEventEnvelope.event_id)).toBeVisible();
    expect(records).toHaveTextContent("WorkflowStepDispatchRequested v1.0");
    expect(records).toHaveTextContent("atlas.workflow v1.0.0");
    expect(records).toHaveTextContent("workflow-execution-attempt");
    expect(records).toHaveTextContent("organization.test");
    expect(records).toHaveTextContent("environment.test");
    expect(records).toHaveTextContent("correlation");
    expect(records).toHaveTextContent("causation");
    expect(records).toHaveTextContent("internal");
    expect(within(section).getByTitle(preparedEventEnvelope.schema_uri)).toBeVisible();
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("source fence 7");
    expect(records).toHaveTextContent("payload/outbox 666666666666...66666666");
    expect(records).toHaveTextContent("envelope 999999999999...99999999");
    expect(section).toHaveTextContent("Prepared canonical data only");
    expect(section).toHaveTextContent("no bytes were serialized");
    expect(section).toHaveTextContent("no message was published or delivered");
    expect(section).toHaveTextContent("no worker was dispatched");
    expect(section).toHaveTextContent("no action was executed");
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders zero event envelopes as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No event envelope has been prepared.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("fails closed when duplicate event envelopes are returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [
        preparedEventEnvelope,
        { ...preparedEventEnvelope, event_id: "workflow-event.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Event-envelope evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Canonical event-envelope evidence" })).toBeNull();
  });

  it.each([
    ["an extra key", { ...preparedEventEnvelope, unexpected: "unsafe" }],
    [
      "a mismatched payload lineage",
      {
        ...preparedEventEnvelope,
        payload: { ...preparedEventEnvelope.payload, attempt_digest: "0".repeat(64) },
      },
    ],
    [
      "a different scope",
      {
        ...preparedEventEnvelope,
        payload: {
          ...preparedEventEnvelope.payload,
          scope: { ...preparedEventEnvelope.payload.scope, site_id: "site.other" },
        },
      },
    ],
    [
      "a different target",
      {
        ...preparedEventEnvelope,
        payload: { ...preparedEventEnvelope.payload, target_id: "asset.storage.other" },
      },
    ],
    ["a stale publication fence", { ...preparedEventEnvelope, publication_fencing_token: 2 }],
    ["a stale source fence", { ...preparedEventEnvelope, orchestration_fencing_token: 8 }],
    ["a broken envelope digest", { ...preparedEventEnvelope, canonical_digest: "not-a-digest" }],
    [
      "unsafe embedded authority",
      {
        ...preparedEventEnvelope,
        authority: { ...preparedEventEnvelope.authority, worker_dispatch_authorized: true },
      },
    ],
    ["publication authority", { ...preparedEventEnvelope, grants_publication_authority: true }],
  ])("fails closed when event-envelope evidence contains %s", async (_case, unsafeEnvelope) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [unsafeEnvelope],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Event-envelope evidence is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No preparation, publication, delivery, dispatch, or execution state is inferred",
    );
    expect(within(section).queryByRole("list", { name: "Canonical event-envelope evidence" })).toBeNull();
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Event-envelope evidence permission is missing", "current role or scope cannot inspect"],
  ])("handles event-envelope read status %s with the normal session boundary", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopeStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("keeps long envelope evidence responsive and control-free at a narrow viewport", async () => {
    vi.stubGlobal("innerWidth", 390);
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [
        {
          ...preparedEventEnvelope,
          event_id: `workflow-event.${"longsegment".repeat(15)}`,
        },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Canonical event-envelope evidence",
    });
    expect(records).toHaveClass("workflow-event-envelope-list");
    expect(within(section).getByTitle(/workflow-event\.longsegment/)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it("loads and renders one exact transport-admission decision without operational controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Transport-admission evidence",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/outbox/${pendingOutboxEntry.outbox_entry_id}/event-envelope/${preparedEventEnvelope.event_id}/transport-admission`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(admittedTransport.transport_admission_id)).toBeVisible();
    expect(records).toHaveTextContent("admitted");
    expect(within(section).getByTitle(admittedTransport.policy.policy_id)).toBeVisible();
    expect(records).toHaveTextContent("v1.0");
    expect(records).toHaveTextContent("canonical-json");
    expect(records).toHaveTextContent("utf-8");
    expect(records).toHaveTextContent("WorkflowStepDispatchRequested v1.0");
    expect(records).toHaveTextContent("classification internal");
    expect(within(section).getByTitle(preparedEventEnvelope.schema_uri)).toBeVisible();
    expect(records).toHaveTextContent("canonical size 2,048 bytes");
    expect(records).toHaveTextContent("policy maximum 65,536 bytes");
    expect(records).toHaveTextContent("organization organization.test");
    expect(records).toHaveTextContent("environment environment.test");
    expect(records).toHaveTextContent("site site.test");
    expect(records).toHaveTextContent("target asset.storage.test");
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("source fence 7");
    expect(records).toHaveTextContent("policy aaaaaaaaaaaa...aaaaaaaa");
    expect(records).toHaveTextContent("event 999999999999...99999999");
    expect(records).toHaveTextContent("outbox 666666666666...66666666");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(records).toHaveTextContent("run 111111111111...11111111");
    expect(records).toHaveTextContent("step 999999999999...99999999");
    expect(records).toHaveTextContent("plan cccccccccccc...cccccccc");
    expect(section).toHaveTextContent("Admission proves policy eligibility only");
    expect(section).toHaveTextContent("No broker, provider, or route was selected");
    expect(section).toHaveTextContent("no wire bytes or message were created");
    expect(section).toHaveTextContent("nothing was serialized, published, delivered, dispatched, or executed");
    expect(
      within(section).queryByRole("button", {
        name: /admit|serialize|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders zero transport-admission decisions as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("No transport-admission decision has been recorded."),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while the authoritative transport-admission read is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      pendingTransportAdmissionResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Loading authoritative transport-admission evidence..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed transport-admission read without creating an admission action", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      transportAdmissionStatuses: [500, 200],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Transport-admission evidence is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No admission, serialization, publication, delivery, dispatch, or execution state is inferred",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Retry transport-admission read" }));
    expect(await within(section).findByTitle(admittedTransport.transport_admission_id)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /admit|serialize|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Transport-admission evidence permission is missing", "current role or scope cannot inspect"],
  ])("handles transport-admission read status %s with the normal session boundary", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissionStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(
      within(section).queryByRole("button", {
        name: /admit|serialize|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
  });

  it("fails closed when duplicate transport-admission decisions are returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [
        admittedTransport,
        { ...admittedTransport, transport_admission_id: "workflow-transport-admission.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Transport-admission evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Transport-admission evidence" })).toBeNull();
  });

  it.each([
    ["an extra key", { ...admittedTransport, unexpected: "unsafe" }],
    ["a different event digest", { ...admittedTransport, event_digest: "0".repeat(64) }],
    [
      "a changed workflow lineage",
      { ...admittedTransport, attempt_digest: "0".repeat(64) },
    ],
    [
      "a changed policy schema",
      {
        ...admittedTransport,
        policy: {
          ...admittedTransport.policy,
          allowed_schema_uri: "urn:project-atlas:event:unsafe:1.0",
        },
      },
    ],
    [
      "an oversized canonical representation",
      {
        ...admittedTransport,
        canonical_byte_count: admittedTransport.policy.maximum_canonical_byte_count + 1,
      },
    ],
    [
      "publication authority",
      { ...admittedTransport, grants_publication_authority: true },
    ],
  ])("fails closed when transport-admission evidence contains %s", async (_case, unsafeAdmission) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [unsafeAdmission],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport-admission evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Transport-admission evidence is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No admission, serialization, publication, delivery, dispatch, or execution state is inferred",
    );
    expect(within(section).queryByRole("list", { name: "Transport-admission evidence" })).toBeNull();
  });

  it("loads and renders one exact byte-artifact metadata record without sensitive content or operational controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Byte-artifact metadata",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/transport-admission/${admittedTransport.transport_admission_id}/byte-artifact`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(materializedByteArtifact.byte_artifact_id)).toBeVisible();
    expect(records).toHaveTextContent("materialized");
    expect(records).toHaveTextContent("canonical-json");
    expect(records).toHaveTextContent("UTF-8");
    expect(records).toHaveTextContent("application/json");
    expect(records).toHaveTextContent("2,048 bytes");
    expect(within(section).getByTitle(materializedByteArtifact.content_sha256)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.policy_id)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.transport_admission_id)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.event_id)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.outbox_entry_id)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.publication_lease_id)).toBeVisible();
    expect(within(section).getByTitle(materializedByteArtifact.orchestration_lease_id)).toBeVisible();
    expect(records).toHaveTextContent("digest aaaaaaaaaaaa...aaaaaaaa");
    expect(records).toHaveTextContent("digest bbbbbbbbbbbb...bbbbbbbb");
    expect(records).toHaveTextContent("digest 999999999999...99999999");
    expect(records).toHaveTextContent("digest 666666666666...66666666");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(records).toHaveTextContent("run 111111111111...11111111");
    expect(records).toHaveTextContent("step 999999999999...99999999");
    expect(records).toHaveTextContent("plan cccccccccccc...cccccccc");
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("source fence 7");
    expect(section).toHaveTextContent("deterministic bytes exist in Atlas storage only");
    expect(section).toHaveTextContent("Raw bytes and payload content are not exposed");
    expect(section).toHaveTextContent("No provider, route, credential, message");
    expect(
      within(section).queryByRole("button", {
        name: /materialize|serialize|download|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders zero byte artifacts as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No byte artifact has been materialized.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while the authoritative byte-artifact metadata read is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      pendingByteArtifactResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Loading authoritative byte-artifact metadata..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed byte-artifact metadata read without creating a materialization action", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      byteArtifactStatuses: [500, 200],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Byte-artifact metadata is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No materialization, publication, delivery, dispatch, or execution state is inferred",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Retry byte-artifact metadata read" }));
    expect(await within(section).findByTitle(materializedByteArtifact.byte_artifact_id)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /materialize|serialize|download|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Byte-artifact metadata permission is missing", "current role or scope cannot inspect"],
  ])("handles byte-artifact metadata read status %s with the normal session boundary", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifactStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(
      within(section).queryByRole("button", {
        name: /materialize|serialize|download|publish|deliver|dispatch|execute|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
  });

  it("fails closed when duplicate byte-artifact metadata records are returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [
        materializedByteArtifact,
        { ...materializedByteArtifact, byte_artifact_id: "workflow-event-byte-artifact.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Byte-artifact metadata is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Byte-artifact metadata" })).toBeNull();
  });

  it.each([
    ["raw bytes", { ...materializedByteArtifact, raw_bytes: "raw-byte-secret" }],
    ["payload", { ...materializedByteArtifact, payload: { secret: "payload-secret" } }],
    ["base64", { ...materializedByteArtifact, base64: "cGF5bG9hZC1zZWNyZXQ=" }],
    ["provider", { ...materializedByteArtifact, provider: "provider-secret" }],
    ["route", { ...materializedByteArtifact, route: "route-secret" }],
    ["credentials", { ...materializedByteArtifact, credentials: "credential-secret" }],
    [
      "a different admission digest",
      { ...materializedByteArtifact, transport_admission_digest: "0".repeat(64) },
    ],
    ["a different event digest", { ...materializedByteArtifact, event_digest: "0".repeat(64) }],
    ["a different outbox digest", { ...materializedByteArtifact, outbox_entry_digest: "0".repeat(64) }],
    ["a changed workflow lineage", { ...materializedByteArtifact, attempt_digest: "0".repeat(64) }],
    ["a changed policy", { ...materializedByteArtifact, policy_digest: "0".repeat(64) }],
    ["a changed representation", { ...materializedByteArtifact, representation_name: "json" }],
    ["a changed encoding", { ...materializedByteArtifact, encoding: "utf-16" }],
    ["a changed media type", { ...materializedByteArtifact, media_type: "application/octet-stream" }],
    ["a changed byte count", { ...materializedByteArtifact, byte_count: 2_049 }],
    ["an invalid SHA-256", { ...materializedByteArtifact, content_sha256: "not-a-digest" }],
    ["a stale publication fence", { ...materializedByteArtifact, publication_fencing_token: 2 }],
    ["publication authority", { ...materializedByteArtifact, grants_publication_authority: true }],
  ])("fails closed when byte-artifact metadata contains %s", async (_case, unsafeArtifact) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [unsafeArtifact],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Byte-artifact metadata is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No materialization, publication, delivery, dispatch, or execution state is inferred",
    );
    expect(within(section).queryByRole("list", { name: "Byte-artifact metadata" })).toBeNull();
    expect(section).not.toHaveTextContent(/raw-byte-secret|payload-secret|cGF5bG9hZC1zZWNyZXQ=|provider-secret|route-secret|credential-secret/);
  });

  it("loads one exact logical channel binding after byte-artifact metadata with zero authority", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const byteArtifactHeading = await screen.findByRole("heading", {
      name: "Byte-artifact metadata",
    });
    const bindingHeading = await screen.findByRole("heading", {
      name: "Logical channel binding",
    });
    expect(
      byteArtifactHeading.compareDocumentPosition(bindingHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const section = bindingHeading.closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Logical channel binding",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/byte-artifact/${materializedByteArtifact.byte_artifact_id}/logical-channel-binding`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(logicalChannelBinding.logical_channel_binding_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.logical_channel_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.policy_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.byte_artifact_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.content_sha256)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.transport_admission_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.event_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.outbox_entry_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.dispatch_intent_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.attempt_id)).toBeVisible();
    expect(within(section).getAllByTitle(logicalChannelBinding.run_id)).toHaveLength(2);
    expect(within(section).getByTitle(logicalChannelBinding.step_run_id)).toBeVisible();
    expect(within(section).getByTitle(logicalChannelBinding.plan_id)).toBeVisible();
    expect(records).toHaveTextContent("bound");
    expect(records).toHaveTextContent("at-least-once");
    expect(records).toHaveTextContent("durable required");
    expect(records).toHaveTextContent("workflow-run ordering");
    expect(records).toHaveTextContent("workflow-operational");
    expect(records).toHaveTextContent("2,048 bytes");
    expect(records).toHaveTextContent("publication false");
    expect(records).toHaveTextContent("delivery false");
    expect(records).toHaveTextContent("dispatch false");
    expect(records).toHaveTextContent("execution false");
    expect(section).toHaveTextContent("No physical provider, broker, endpoint, topic, stream, queue, partition, routing key");
    expect(section).toHaveTextContent("credential, message, or network publication attempt exists");
    expect(section).toHaveTextContent("authority remain zero");
    expect(
      within(section).queryByRole("button", {
        name: /bind|select|publish|deliver|dispatch|execute|materialize|serialize|download|acquire|heartbeat|release/i,
      }),
    ).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("loads read-only compatibility evidence for the exact logical binding", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      transportCompatibilityAdmissions: [transportCompatibilityAdmission],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const bindingHeading = await screen.findByRole("heading", {
      name: "Logical channel binding",
    });
    const admissionHeading = await screen.findByRole("heading", {
      name: "Transport compatibility admission",
    });
    expect(
      bindingHeading.compareDocumentPosition(admissionHeading) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const section = admissionHeading.closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Transport compatibility admissions",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) => {
        const url = request instanceof Request ? request.url : request.toString();
        return url.includes(
          `/api/v1/workflows/transport-compatibility-admissions?logical_channel_binding_id=${logicalChannelBinding.logical_channel_binding_id}`,
        );
      }),
    ).toBe(true);
    expect(
      within(section).getByTitle(
        transportCompatibilityAdmission.compatibility_admission_id,
      ),
    ).toBeVisible();
    expect(
      within(section).getByTitle(transportCompatibilityAdmission.logical_channel_binding_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(transportCompatibilityAdmission.transport_profile_snapshot_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(transportCompatibilityAdmission.transport_profile_id),
    ).toBeVisible();
    expect(
      within(section).getByTitle(transportCompatibilityAdmission.policy_id),
    ).toBeVisible();
    expect(within(section).getByTitle(transportCompatibilityAdmission.schema_uri)).toBeVisible();
    expect(
      within(section).getByTitle(transportCompatibilityAdmission.admitter_subject_id),
    ).toBeVisible();
    expect(records).toHaveTextContent("admitted");
    expect(records).toHaveTextContent("WorkflowStepDispatchRequested v1.0");
    expect(records).toHaveTextContent("internal");
    expect(records).toHaveTextContent("canonical-json");
    expect(records).toHaveTextContent("utf-8");
    expect(records).toHaveTextContent("at-least-once");
    expect(records).toHaveTextContent("durable required");
    expect(records).toHaveTextContent("workflow-run");
    expect(records).toHaveTextContent("workflow-operational");
    expect(records).toHaveTextContent("logical maximum 65,536 bytes");
    expect(records).toHaveTextContent("artifact 2,048 bytes");
    expect(records).toHaveTextContent("profile maximum 65,536 bytes");
    expect(records).toHaveTextContent(
      "authority route selection false | route binding false | credential access false | publication false | delivery false | dispatch false | execution false",
    );
    expect(section).toHaveTextContent("exact declared contracts match under the named policy");
    expect(
      within(section).queryByRole("button", {
        name: /admit|recalculate|override|select|bind|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(section).not.toHaveTextContent(
      /hostname|URL|IP address|namespace|topic|stream|queue|partition|routing key|vault|certificate|healthy|reachable|ready/i,
    );
    expect(section).not.toHaveTextContent(/authorized browser session|MFA|second login/i);
  });

  it("renders zero compatibility admissions as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      transportCompatibilityAdmissions: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport compatibility admission",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("No transport compatibility admission has been recorded."),
    ).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while compatibility evidence is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      pendingTransportCompatibilityAdmissionResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport compatibility admission",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Loading transport compatibility admission..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed compatibility read without exposing mutation controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      transportCompatibilityAdmissions: [transportCompatibilityAdmission],
      transportCompatibilityAdmissionStatuses: [500, 200],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport compatibility admission",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Transport compatibility admission is unavailable"),
    ).toBeVisible();
    expect(section).toHaveTextContent(
      "No compatibility or operational state is inferred from this failed read.",
    );
    fireEvent.click(
      within(section).getByRole("button", {
        name: "Retry transport compatibility admission read",
      }),
    );
    expect(
      await within(section).findByTitle(
        transportCompatibilityAdmission.compatibility_admission_id,
      ),
    ).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /admit|recalculate|override|select|bind|probe|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [
      403,
      "Transport compatibility admission permission is missing",
      "current role or scope cannot inspect compatibility evidence",
    ],
  ])(
    "handles compatibility status %s at the normal session boundary",
    async (status, title, detail) => {
      vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
      mockReadResponses({
        run: materializedRun,
        attempts: [materializedAttempt],
        dispatchIntents: [stagedDispatchIntent],
        outboxEntries: [pendingOutboxEntry],
        publicationLeases: [activePublicationLease],
        eventEnvelopes: [preparedEventEnvelope],
        transportAdmissions: [admittedTransport],
        byteArtifacts: [materializedByteArtifact],
        logicalChannelBindings: [logicalChannelBinding],
        transportCompatibilityAdmissionStatus: status,
      });
      renderWorkspace();

      fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

      const section = (await screen.findByRole("heading", {
        name: "Transport compatibility admission",
      })).closest("div[aria-labelledby]") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      expect(within(section).queryByRole("button")).toBeNull();
      expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    },
  );

  it.each([
    ["an unexpected endpoint", { ...transportCompatibilityAdmission, endpoint: "broker.internal" }],
    [
      "a different binding digest",
      { ...transportCompatibilityAdmission, logical_channel_binding_digest: "0".repeat(64) },
    ],
    [
      "an insufficient profile maximum",
      { ...transportCompatibilityAdmission, profile_maximum_message_byte_count: 1_024 },
    ],
    ["a readiness state", { ...transportCompatibilityAdmission, state: "ready" }],
    [
      "route selection authority",
      {
        ...transportCompatibilityAdmission,
        authority: {
          ...transportCompatibilityAdmission.authority,
          route_selection_authorized: true,
        },
      },
    ],
  ])("fails closed when compatibility evidence contains %s", async (_case, unsafeAdmission) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      transportCompatibilityAdmissions: [unsafeAdmission],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Transport compatibility admission",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Transport compatibility admission is unavailable"),
    ).toBeVisible();
    expect(
      within(section).queryByRole("list", { name: "Transport compatibility admissions" }),
    ).toBeNull();
    expect(section).not.toHaveTextContent("broker.internal");
  });

  it("renders zero logical channel bindings as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Logical channel binding",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No logical channel binding has been recorded.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("shows a loading state while the logical channel binding read is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      pendingLogicalChannelBindingResponse: new Promise<Response>(() => undefined),
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Logical channel binding",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(
      await within(section).findByText("Loading authoritative logical channel binding..."),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("retries a failed logical channel binding read without exposing a bind action", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [logicalChannelBinding],
      logicalChannelBindingStatuses: [500, 200],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Logical channel binding",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Logical channel binding is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No binding, publication, delivery, dispatch, or execution state is inferred",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Retry logical channel binding read" }));
    expect(await within(section).findByTitle(logicalChannelBinding.logical_channel_binding_id)).toBeVisible();
    expect(within(section).queryByRole("button", { name: /bind|select|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue.", true],
    [403, "Logical channel binding permission is missing", "current role or scope cannot inspect", false],
  ])(
    "handles logical channel binding status %s at the normal session boundary",
    async (status, title, detail, shouldSuggestSignIn) => {
      vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
      mockReadResponses({
        run: materializedRun,
        attempts: [materializedAttempt],
        dispatchIntents: [stagedDispatchIntent],
        outboxEntries: [pendingOutboxEntry],
        publicationLeases: [activePublicationLease],
        eventEnvelopes: [preparedEventEnvelope],
        transportAdmissions: [admittedTransport],
        byteArtifacts: [materializedByteArtifact],
        logicalChannelBindingStatus: status,
      });
      renderWorkspace();

      fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

      const section = (await screen.findByRole("heading", {
        name: "Logical channel binding",
      })).closest("div[aria-labelledby]") as HTMLElement;
      expect(await within(section).findByText(title)).toBeVisible();
      expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
      if (shouldSuggestSignIn) {
        expect(within(section).getByText("Sign in again to continue.")).toBeVisible();
      } else {
        expect(within(section).queryByText(/sign in again/i)).toBeNull();
      }
      expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    },
  );

  it("fails closed when duplicate logical channel bindings are returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [
        logicalChannelBinding,
        {
          ...logicalChannelBinding,
          logical_channel_binding_id: "workflow-event-logical-channel-binding.other",
        },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Logical channel binding",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Logical channel binding is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Logical channel binding" })).toBeNull();
  });

  it.each([
    ["raw bytes", { ...logicalChannelBinding, raw_bytes: "raw-binding-secret" }],
    ["payload", { ...logicalChannelBinding, payload: { value: "payload-binding-secret" } }],
    ["base64", { ...logicalChannelBinding, base64: "cGF5bG9hZC1iaW5kaW5nLXNlY3JldA==" }],
    ["provider", { ...logicalChannelBinding, provider: "provider-binding-secret" }],
    ["route", { ...logicalChannelBinding, route: "route-binding-secret" }],
    ["broker", { ...logicalChannelBinding, broker: "broker-binding-secret" }],
    ["endpoint", { ...logicalChannelBinding, endpoint: "endpoint-binding-secret" }],
    ["topic", { ...logicalChannelBinding, topic: "topic-binding-secret" }],
    ["stream", { ...logicalChannelBinding, stream: "stream-binding-secret" }],
    ["queue", { ...logicalChannelBinding, queue: "queue-binding-secret" }],
    ["partition", { ...logicalChannelBinding, partition: "partition-binding-secret" }],
    ["routing key", { ...logicalChannelBinding, routing_key: "routing-binding-secret" }],
    ["credentials", { ...logicalChannelBinding, credentials: "credential-binding-secret" }],
    ["provider message", { ...logicalChannelBinding, provider_message: "message-binding-secret" }],
    [
      "network publication attempt",
      { ...logicalChannelBinding, network_publication_attempt: "attempt-binding-secret" },
    ],
    ["a different artifact", { ...logicalChannelBinding, byte_artifact_id: "workflow-event-byte-artifact.other" }],
    ["a different artifact digest", { ...logicalChannelBinding, byte_artifact_digest: "0".repeat(64) }],
    ["a different content digest", { ...logicalChannelBinding, content_sha256: "0".repeat(64) }],
    ["a different byte count", { ...logicalChannelBinding, byte_count: 2_049 }],
    ["a different admission digest", { ...logicalChannelBinding, transport_admission_digest: "0".repeat(64) }],
    ["a different event digest", { ...logicalChannelBinding, event_digest: "0".repeat(64) }],
    ["a different outbox digest", { ...logicalChannelBinding, outbox_entry_digest: "0".repeat(64) }],
    ["a different intent digest", { ...logicalChannelBinding, dispatch_intent_digest: "0".repeat(64) }],
    ["a different attempt digest", { ...logicalChannelBinding, attempt_digest: "0".repeat(64) }],
    ["a different run digest", { ...logicalChannelBinding, run_digest: "0".repeat(64) }],
    ["a different step digest", { ...logicalChannelBinding, step_run_digest: "0".repeat(64) }],
    ["a different plan digest", { ...logicalChannelBinding, plan_digest: "0".repeat(64) }],
    ["a changed scope", { ...logicalChannelBinding, scope: { ...logicalChannelBinding.scope, site_id: "site.other" } }],
    ["a changed target", { ...logicalChannelBinding, target_id: "asset.storage.other" }],
    ["an invalid policy digest", { ...logicalChannelBinding, policy_digest: "not-a-digest" }],
    ["a changed policy", { ...logicalChannelBinding, policy_id: "policy.workflow-event.other" }],
    ["a changed policy version", { ...logicalChannelBinding, policy_version: "2.0" }],
    ["a physical channel", { ...logicalChannelBinding, logical_channel_id: "topic.workflow-dispatch" }],
    ["a changed channel version", { ...logicalChannelBinding, logical_channel_version: "2.0" }],
    ["different delivery semantics", { ...logicalChannelBinding, delivery_semantics: "at-most-once" }],
    ["non-durable delivery", { ...logicalChannelBinding, durability_required: false }],
    ["a different ordering kind", { ...logicalChannelBinding, ordering_key_kind: "event" }],
    ["a different ordering value", { ...logicalChannelBinding, ordering_key_value: "workflow-run.other" }],
    ["a different retention class", { ...logicalChannelBinding, retention_class: "ephemeral" }],
    ["a stale source fence", { ...logicalChannelBinding, orchestration_fencing_token: 8 }],
    ["a stale publication fence", { ...logicalChannelBinding, publication_fencing_token: 2 }],
    ["publication authority", { ...logicalChannelBinding, grants_publication_authority: true }],
    [
      "nested publication authority",
      {
        ...logicalChannelBinding,
        authority: { ...logicalChannelBinding.authority, publication_authorized: true },
      },
    ],
  ])("fails closed when logical channel binding contains %s", async (_case, unsafeBinding) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
      transportAdmissions: [admittedTransport],
      byteArtifacts: [materializedByteArtifact],
      logicalChannelBindings: [unsafeBinding],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Logical channel binding",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Logical channel binding is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No binding, publication, delivery, dispatch, or execution state is inferred",
    );
    expect(within(section).queryByRole("list", { name: "Logical channel binding" })).toBeNull();
    expect(section).not.toHaveTextContent(
      /raw-binding-secret|payload-binding-secret|cGF5bG9hZC1iaW5kaW5nLXNlY3JldA==|provider-binding-secret|route-binding-secret|broker-binding-secret|endpoint-binding-secret|topic-binding-secret|stream-binding-secret|queue-binding-secret|partition-binding-secret|routing-binding-secret|credential-binding-secret|message-binding-secret|attempt-binding-secret/,
    );
  });
});
