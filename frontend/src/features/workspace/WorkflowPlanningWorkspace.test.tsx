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
  type WorkflowEventByteArtifact,
  type WorkflowEventLogicalChannelBinding,
  type WorkflowEventTransportAdmission,
  type WorkflowExecutionAttempt,
  type WorkflowExecutionRun,
  type WorkflowOrchestrationLease,
  type WorkflowPhysicalTransportRouteBinding,
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
  physicalTransportRouteFreshnessAdmissions?: unknown[];
  transportCompatibilityAdmissions?: unknown[];
  pendingTransportAdmissionResponse?: Promise<Response>;
  pendingByteArtifactResponse?: Promise<Response>;
  pendingLogicalChannelBindingResponse?: Promise<Response>;
  pendingTransportProfileResponse?: Promise<Response>;
  pendingTransportRouteSnapshotResponse?: Promise<Response>;
  pendingPhysicalTransportRouteBindingResponse?: Promise<Response>;
  pendingPhysicalTransportRouteFreshnessAdmissionResponse?: Promise<Response>;
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
  physicalTransportRouteFreshnessAdmissionStatus?: number;
  physicalTransportRouteFreshnessAdmissionStatuses?: number[];
  transportCompatibilityAdmissionStatus?: number;
  transportCompatibilityAdmissionStatuses?: number[];
}) {
  let transportAdmissionReadCount = 0;
  let byteArtifactReadCount = 0;
  let logicalChannelBindingReadCount = 0;
  let transportProfileReadCount = 0;
  let transportRouteSnapshotReadCount = 0;
  let physicalTransportRouteBindingReadCount = 0;
  let physicalTransportRouteFreshnessAdmissionReadCount = 0;
  let transportCompatibilityAdmissionReadCount = 0;
  vi.mocked(fetch).mockImplementation((request) => {
    const url = request instanceof Request ? request.url : request.toString();
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
