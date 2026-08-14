import { ApiRequestError, apiFetch } from "./client";

export const WORKFLOW_PLAN_SAFETY_NOTICE =
  "Planning only. This record cannot dispatch workers, invoke connectors, create approvals, mutate ITSM, execute runbooks, or change infrastructure.";

export type WorkflowCapabilityClass = "C0" | "C1" | "C2";
export type WorkflowStepKind =
  | "evidence_query"
  | "health_assessment"
  | "report_generation";

export type WorkflowScope = {
  organizationId: string;
  environmentId: string;
  siteId: string;
};

export type WorkflowStepDefinition = {
  step_id: string;
  ordinal: number;
  title: string;
  kind: WorkflowStepKind;
  capability_class: WorkflowCapabilityClass;
  timeout_seconds: number;
  depends_on: string[];
};

export type WorkflowDefinition = {
  definition_id: string;
  version: number;
  title: string;
  purpose: string;
  input_schema_version: string;
  definition_digest: string;
  steps: WorkflowStepDefinition[];
};

export type WorkflowPlanAuthority = {
  worker_dispatch_authorized: false;
  connector_invocation_authorized: false;
  approval_creation_authorized: false;
  signal_delivery_authorized: false;
  retry_authorized: false;
  itsm_mutation_authorized: false;
  runbook_execution_authorized: false;
  infrastructure_change_authorized: false;
};

export type WorkflowPlanStep = {
  step_id: string;
  ordinal: number;
  kind: WorkflowStepKind;
  capability_class: WorkflowCapabilityClass;
  state: "not_started";
};

export type WorkflowPlanTransition = {
  transition_id: string;
  prior_state: "planned";
  new_state: "cancelled";
  actor_subject_id: string;
  scope: {
    organization_id: string;
    environment_id: string;
    site_id: string;
  };
  target_id: string;
  target_type: "storage";
  reason: string;
  reason_digest: string;
  correlation_id: string;
  occurred_at: string;
  canonical_digest: string;
};

export type WorkflowRunPlan = {
  plan_id: string;
  definition_id: string;
  definition_version: number;
  definition_digest: string;
  scope: {
    organization_id: string;
    environment_id: string;
    site_id: string;
  };
  target_id: string;
  target_type: "storage";
  canonical_input_digest: string;
  creator_subject_id: string;
  created_at: string;
  state: "planned" | "cancelled";
  steps: WorkflowPlanStep[];
  durable: boolean;
  authority: WorkflowPlanAuthority;
  safety_notice: typeof WORKFLOW_PLAN_SAFETY_NOTICE;
  canonical_digest: string;
  transition_history: WorkflowPlanTransition[];
};

export type WorkflowDefinitionInventory = {
  definitions: WorkflowDefinition[];
};

export type WorkflowPlanInventory = {
  plans: WorkflowRunPlan[];
  durable: boolean;
  truncated: boolean;
};

export type WorkflowOrchestrationLeaseEffectiveState = "active" | "expired" | "released";

export type WorkflowOrchestrationLease = {
  lease_id: string;
  plan_id: string;
  plan_digest: string;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  worker_subject_id: string;
  acquired_at: string;
  last_heartbeat_at: string;
  expires_at: string;
  fencing_token: number;
  state: "active" | "released";
  effective_state: WorkflowOrchestrationLeaseEffectiveState;
  canonical_digest: string;
  grants_execution_authority: false;
};

export type WorkflowOrchestrationLeaseStatus = {
  plan_id: string;
  server_time: string;
  durable: boolean;
  lease: WorkflowOrchestrationLease | null;
};

export type WorkflowExecutionStepRun = {
  step_run_id: string;
  run_id: string;
  step_id: string;
  ordinal: number;
  kind: WorkflowStepKind;
  capability_class: WorkflowCapabilityClass;
  timeout_seconds: number;
  depends_on: string[];
  state: "not_started";
  canonical_digest: string;
};

export type WorkflowExecutionRun = {
  run_id: string;
  plan_id: string;
  plan_digest: string;
  definition_id: string;
  definition_version: number;
  definition_digest: string;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  lease_id: string;
  lease_digest: string;
  fencing_token: number;
  materialized_by_subject_id: string;
  created_at: string;
  state: "created";
  step_runs: WorkflowExecutionStepRun[];
  authority: WorkflowPlanAuthority;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowMaterializedRunStatus = {
  plan_id: string;
  run: WorkflowExecutionRun | null;
  server_time: string;
  durable: boolean;
};

export type WorkflowExecutionAttempt = {
  attempt_id: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_number: 1;
  plan_id: string;
  plan_digest: string;
  definition_id: string;
  definition_version: number;
  definition_digest: string;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  lease_id: string;
  lease_digest: string;
  fencing_token: number;
  materialized_by_subject_id: string;
  created_at: string;
  state: "created";
  authority: WorkflowPlanAuthority;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowExecutionAttemptInventory = {
  run_id: string;
  attempts: WorkflowExecutionAttempt[];
  server_time: string;
  durable: boolean;
};

export type WorkflowDispatchIntent = {
  dispatch_intent_id: string;
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  lease_id: string;
  lease_digest: string;
  fencing_token: number;
  worker_subject_id: string;
  staged_at: string;
  state: "staged";
  authority: WorkflowPlanAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowDispatchIntentInventory = {
  attempt_id: string;
  dispatch_intents: WorkflowDispatchIntent[];
  server_time: string;
  durable: boolean;
};

export type WorkflowDispatchOutboxEntry = {
  outbox_entry_id: string;
  dispatch_intent_id: string;
  dispatch_intent_digest: string;
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  lease_id: string;
  lease_digest: string;
  fencing_token: number;
  worker_subject_id: string;
  admitted_at: string;
  state: "pending_publication";
  authority: WorkflowPlanAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowDispatchOutboxInventory = {
  dispatch_intent_id: string;
  outbox_entries: WorkflowDispatchOutboxEntry[];
  server_time: string;
  durable: boolean;
};

export type WorkflowDispatchOutboxPublicationLease = {
  publication_lease_id: string;
  outbox_entry_id: string;
  outbox_entry_digest: string;
  dispatch_intent_id: string;
  dispatch_intent_digest: string;
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  orchestration_lease_id: string;
  orchestration_lease_digest: string;
  orchestration_fencing_token: number;
  publisher_subject_id: string;
  acquired_at: string;
  last_heartbeat_at: string;
  expires_at: string;
  publication_fencing_token: number;
  state: "active" | "released";
  authority: WorkflowPlanAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
  effective_state: "active" | "expired" | "released";
};

export type WorkflowDispatchOutboxPublicationLeaseInventory = {
  outbox_entry_id: string;
  publication_leases: WorkflowDispatchOutboxPublicationLease[];
  server_time: string;
  durable: boolean;
};

export type WorkflowDispatchEventEnvelopePayload = {
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  dispatch_intent_id: string;
  dispatch_intent_digest: string;
  outbox_entry_id: string;
  outbox_entry_digest: string;
};

export type WorkflowDispatchEventAuthority = {
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowDispatchEventEnvelope = {
  event_id: string;
  event_type: "WorkflowStepDispatchRequested";
  event_version: "1.0";
  producer: string;
  producer_version: string;
  occurred_at: string;
  recorded_at: string;
  subject_type: "workflow-execution-attempt";
  subject_id: string;
  organization_id: string;
  environment_id: string;
  correlation_id: string;
  causation_id: string;
  workflow_id: string;
  data_classification: "internal";
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0";
  payload: WorkflowDispatchEventEnvelopePayload;
  extensions: Record<string, never>;
  orchestration_lease_id: string;
  orchestration_lease_digest: string;
  orchestration_fencing_token: number;
  publication_lease_id: string;
  publication_lease_digest: string;
  publication_fencing_token: number;
  publisher_subject_id: string;
  prepared_at: string;
  state: "prepared";
  authority: WorkflowDispatchEventAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowDispatchEventEnvelopeInventory = {
  outbox_entry_id: string;
  event_envelopes: WorkflowDispatchEventEnvelope[];
  durable: boolean;
};

export type WorkflowEventTransportAdmissionPolicy = {
  policy_id: "policy.workflow-event-transport-admission";
  policy_version: "1.0";
  policy_digest: string;
  allowed_event_type: "WorkflowStepDispatchRequested";
  allowed_event_version: "1.0";
  allowed_schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0";
  allowed_data_classification: "internal";
  representation_name: "canonical-json";
  encoding: "utf-8";
  maximum_canonical_byte_count: 65_536;
};

export type WorkflowEventTransportAdmission = {
  transport_admission_id: string;
  event_id: string;
  event_digest: string;
  outbox_entry_id: string;
  outbox_entry_digest: string;
  dispatch_intent_id: string;
  dispatch_intent_digest: string;
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  policy: WorkflowEventTransportAdmissionPolicy;
  canonical_byte_count: number;
  publisher_subject_id: string;
  orchestration_lease_id: string;
  orchestration_lease_digest: string;
  orchestration_fencing_token: number;
  publication_lease_id: string;
  publication_lease_digest: string;
  publication_fencing_token: number;
  admitted_at: string;
  state: "admitted";
  authority: WorkflowDispatchEventAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowEventTransportAdmissionInventory = {
  event_id: string;
  transport_admissions: WorkflowEventTransportAdmission[];
  durable: boolean;
};

export type WorkflowEventByteArtifact = {
  byte_artifact_id: string;
  transport_admission_id: string;
  transport_admission_digest: string;
  event_id: string;
  event_digest: string;
  outbox_entry_id: string;
  outbox_entry_digest: string;
  dispatch_intent_id: string;
  dispatch_intent_digest: string;
  plan_id: string;
  plan_digest: string;
  run_id: string;
  run_digest: string;
  step_run_id: string;
  step_run_digest: string;
  step_id: string;
  attempt_id: string;
  attempt_digest: string;
  attempt_number: 1;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  policy_id: "policy.workflow-event-transport-admission";
  policy_version: "1.0";
  policy_digest: string;
  representation_name: "canonical-json";
  encoding: "utf-8";
  media_type: "application/json";
  byte_count: number;
  content_sha256: string;
  publisher_subject_id: string;
  orchestration_lease_id: string;
  orchestration_lease_digest: string;
  orchestration_fencing_token: number;
  publication_lease_id: string;
  publication_lease_digest: string;
  publication_fencing_token: number;
  materialized_at: string;
  state: "materialized";
  authority: WorkflowDispatchEventAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowEventByteArtifactInventory = {
  transport_admission_id: string;
  byte_artifacts: WorkflowEventByteArtifact[];
  durable: boolean;
};

const digest = /^[a-f0-9]{64}$/;
const capabilityClasses = new Set<WorkflowCapabilityClass>(["C0", "C1", "C2"]);
const stepKinds = new Set<WorkflowStepKind>([
  "evidence_query",
  "health_assessment",
  "report_generation",
]);
const authorityFields = [
  "worker_dispatch_authorized",
  "connector_invocation_authorized",
  "approval_creation_authorized",
  "signal_delivery_authorized",
  "retry_authorized",
  "itsm_mutation_authorized",
  "runbook_execution_authorized",
  "infrastructure_change_authorized",
] as const;
const runFields = [
  "run_id",
  "plan_id",
  "plan_digest",
  "definition_id",
  "definition_version",
  "definition_digest",
  "scope",
  "target_id",
  "target_type",
  "lease_id",
  "lease_digest",
  "fencing_token",
  "materialized_by_subject_id",
  "created_at",
  "state",
  "step_runs",
  "authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const stepRunFields = [
  "step_run_id",
  "run_id",
  "step_id",
  "ordinal",
  "kind",
  "capability_class",
  "timeout_seconds",
  "depends_on",
  "state",
  "canonical_digest",
] as const;
const attemptFields = [
  "attempt_id",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_number",
  "plan_id",
  "plan_digest",
  "definition_id",
  "definition_version",
  "definition_digest",
  "scope",
  "target_id",
  "target_type",
  "lease_id",
  "lease_digest",
  "fencing_token",
  "materialized_by_subject_id",
  "created_at",
  "state",
  "authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const attemptInventoryFields = ["run_id", "attempts", "server_time", "durable"] as const;
const dispatchIntentFields = [
  "dispatch_intent_id",
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "lease_id",
  "lease_digest",
  "fencing_token",
  "worker_subject_id",
  "staged_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const dispatchIntentInventoryFields = [
  "attempt_id",
  "dispatch_intents",
  "server_time",
  "durable",
] as const;
const dispatchOutboxEntryFields = [
  "outbox_entry_id",
  "dispatch_intent_id",
  "dispatch_intent_digest",
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "lease_id",
  "lease_digest",
  "fencing_token",
  "worker_subject_id",
  "admitted_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const dispatchOutboxInventoryFields = [
  "dispatch_intent_id",
  "outbox_entries",
  "server_time",
  "durable",
] as const;
const dispatchOutboxPublicationLeaseFields = [
  "publication_lease_id",
  "outbox_entry_id",
  "outbox_entry_digest",
  "dispatch_intent_id",
  "dispatch_intent_digest",
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "orchestration_lease_id",
  "orchestration_lease_digest",
  "orchestration_fencing_token",
  "publisher_subject_id",
  "acquired_at",
  "last_heartbeat_at",
  "expires_at",
  "publication_fencing_token",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
  "effective_state",
] as const;
const dispatchOutboxPublicationLeaseInventoryFields = [
  "outbox_entry_id",
  "publication_leases",
  "server_time",
  "durable",
] as const;
const dispatchEventEnvelopePayloadFields = [
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "dispatch_intent_id",
  "dispatch_intent_digest",
  "outbox_entry_id",
  "outbox_entry_digest",
] as const;
const dispatchEventEnvelopeFields = [
  "event_id",
  "event_type",
  "event_version",
  "producer",
  "producer_version",
  "occurred_at",
  "recorded_at",
  "subject_type",
  "subject_id",
  "organization_id",
  "environment_id",
  "correlation_id",
  "causation_id",
  "workflow_id",
  "data_classification",
  "schema_uri",
  "payload",
  "extensions",
  "orchestration_lease_id",
  "orchestration_lease_digest",
  "orchestration_fencing_token",
  "publication_lease_id",
  "publication_lease_digest",
  "publication_fencing_token",
  "publisher_subject_id",
  "prepared_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const dispatchEventEnvelopeInventoryFields = [
  "outbox_entry_id",
  "event_envelopes",
  "durable",
] as const;
const eventTransportAdmissionPolicyFields = [
  "policy_id",
  "policy_version",
  "policy_digest",
  "allowed_event_type",
  "allowed_event_version",
  "allowed_schema_uri",
  "allowed_data_classification",
  "representation_name",
  "encoding",
  "maximum_canonical_byte_count",
] as const;
const eventTransportAdmissionFields = [
  "transport_admission_id",
  "event_id",
  "event_digest",
  "outbox_entry_id",
  "outbox_entry_digest",
  "dispatch_intent_id",
  "dispatch_intent_digest",
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "policy",
  "canonical_byte_count",
  "publisher_subject_id",
  "orchestration_lease_id",
  "orchestration_lease_digest",
  "orchestration_fencing_token",
  "publication_lease_id",
  "publication_lease_digest",
  "publication_fencing_token",
  "admitted_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const eventTransportAdmissionInventoryFields = [
  "event_id",
  "transport_admissions",
  "durable",
] as const;
const eventByteArtifactFields = [
  "byte_artifact_id",
  "transport_admission_id",
  "transport_admission_digest",
  "event_id",
  "event_digest",
  "outbox_entry_id",
  "outbox_entry_digest",
  "dispatch_intent_id",
  "dispatch_intent_digest",
  "plan_id",
  "plan_digest",
  "run_id",
  "run_digest",
  "step_run_id",
  "step_run_digest",
  "step_id",
  "attempt_id",
  "attempt_digest",
  "attempt_number",
  "scope",
  "target_id",
  "target_type",
  "policy_id",
  "policy_version",
  "policy_digest",
  "representation_name",
  "encoding",
  "media_type",
  "byte_count",
  "content_sha256",
  "publisher_subject_id",
  "orchestration_lease_id",
  "orchestration_lease_digest",
  "orchestration_fencing_token",
  "publication_lease_id",
  "publication_lease_digest",
  "publication_fencing_token",
  "materialized_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const eventByteArtifactInventoryFields = [
  "transport_admission_id",
  "byte_artifacts",
  "durable",
] as const;
const dispatchEventAuthorityFields = [
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const scopeFields = ["organization_id", "environment_id", "site_id"] as const;
const forbiddenCredentialFields = new Set([
  "api_key",
  "access_token",
  "bearer_token",
  "credential",
  "credentials",
  "password",
  "refresh_token",
  "secret",
  "secrets",
  "token",
  "workload_token",
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, fields: readonly string[]): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.length && fields.every((field) => field in value);
}

function containsCredentialMaterial(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(containsCredentialMaterial);
  if (!isObject(value)) return false;
  return Object.entries(value).some(
    ([key, nested]) =>
      forbiddenCredentialFields.has(key.toLowerCase()) || containsCredentialMaterial(nested),
  );
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 240 && !/\s/.test(value);
}

function isText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maximum;
}

function isDigest(value: unknown): value is string {
  return typeof value === "string" && digest.test(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isScope(value: unknown): value is WorkflowRunPlan["scope"] {
  return (
    isObject(value) &&
    isIdentifier(value.organization_id) &&
    isIdentifier(value.environment_id) &&
    isIdentifier(value.site_id)
  );
}

function isExactScope(value: unknown): value is WorkflowRunPlan["scope"] {
  return isObject(value) && hasExactKeys(value, scopeFields) && isScope(value);
}

function isCapabilityClass(value: unknown): value is WorkflowCapabilityClass {
  return capabilityClasses.has(value as WorkflowCapabilityClass);
}

function isStepKind(value: unknown): value is WorkflowStepKind {
  return stepKinds.has(value as WorkflowStepKind);
}

function isDefinitionStep(value: unknown, index: number): value is WorkflowStepDefinition {
  if (!isObject(value)) return false;
  return (
    isIdentifier(value.step_id) &&
    value.ordinal === index + 1 &&
    isText(value.title, 120) &&
    isStepKind(value.kind) &&
    isCapabilityClass(value.capability_class) &&
    Number.isInteger(value.timeout_seconds) &&
    Number(value.timeout_seconds) >= 1 &&
    Number(value.timeout_seconds) <= 3_600 &&
    Array.isArray(value.depends_on) &&
    value.depends_on.every(isIdentifier)
  );
}

function isDefinition(value: unknown): value is WorkflowDefinition {
  if (!isObject(value) || !Array.isArray(value.steps) || value.steps.length < 1) return false;
  const stepsValid = value.steps.every(isDefinitionStep);
  const seen = new Set(value.steps.map((step) => (isObject(step) ? step.step_id : undefined)));
  return (
    isIdentifier(value.definition_id) &&
    Number.isInteger(value.version) &&
    Number(value.version) >= 1 &&
    isText(value.title, 120) &&
    isText(value.purpose, 500) &&
    isIdentifier(value.input_schema_version) &&
    isDigest(value.definition_digest) &&
    stepsValid &&
    seen.size === value.steps.length
  );
}

function hasSafeAuthority(value: unknown): value is WorkflowPlanAuthority {
  if (!isObject(value)) return false;
  return (
    Object.keys(value).length === authorityFields.length &&
    authorityFields.every((field) => value[field] === false)
  );
}

function isPlanStep(value: unknown, index: number): value is WorkflowPlanStep {
  return (
    isObject(value) &&
    isIdentifier(value.step_id) &&
    value.ordinal === index + 1 &&
    isStepKind(value.kind) &&
    isCapabilityClass(value.capability_class) &&
    value.state === "not_started"
  );
}

function isTransition(
  value: unknown,
  planScope: WorkflowRunPlan["scope"],
  targetId: string,
): value is WorkflowPlanTransition {
  if (!isObject(value) || !isObject(value.scope)) return false;
  return (
    isIdentifier(value.transition_id) &&
    value.prior_state === "planned" &&
    value.new_state === "cancelled" &&
    isIdentifier(value.actor_subject_id) &&
    value.scope.organization_id === planScope.organization_id &&
    value.scope.environment_id === planScope.environment_id &&
    value.scope.site_id === planScope.site_id &&
    value.target_id === targetId &&
    value.target_type === "storage" &&
    isText(value.reason, 500) &&
    value.reason === value.reason.trim().replace(/\s+/g, " ") &&
    isDigest(value.reason_digest) &&
    isIdentifier(value.correlation_id) &&
    typeof value.occurred_at === "string" &&
    !Number.isNaN(Date.parse(value.occurred_at)) &&
    isDigest(value.canonical_digest)
  );
}

function isBoundToScope(value: WorkflowRunPlan, scope: WorkflowScope): boolean {
  return (
    value.scope.organization_id === scope.organizationId &&
    value.scope.environment_id === scope.environmentId &&
    value.scope.site_id === scope.siteId
  );
}

function isLeaseBoundToPlan(
  value: unknown,
  plan: WorkflowRunPlan,
): value is WorkflowOrchestrationLease {
  if (!isObject(value) || !isScope(value.scope)) return false;
  const effectiveState = value.effective_state;
  const stateIsConsistent =
    (value.state === "active" && (effectiveState === "active" || effectiveState === "expired")) ||
    (value.state === "released" && effectiveState === "released");
  return (
    isIdentifier(value.lease_id) &&
    value.plan_id === plan.plan_id &&
    value.plan_digest === plan.canonical_digest &&
    value.scope.organization_id === plan.scope.organization_id &&
    value.scope.environment_id === plan.scope.environment_id &&
    value.scope.site_id === plan.scope.site_id &&
    value.target_id === plan.target_id &&
    value.target_type === plan.target_type &&
    isIdentifier(value.worker_subject_id) &&
    isTimestamp(value.acquired_at) &&
    isTimestamp(value.last_heartbeat_at) &&
    isTimestamp(value.expires_at) &&
    Date.parse(value.acquired_at) <= Date.parse(value.last_heartbeat_at) &&
    Date.parse(value.last_heartbeat_at) < Date.parse(value.expires_at) &&
    Number.isSafeInteger(value.fencing_token) &&
    Number(value.fencing_token) >= 1 &&
    stateIsConsistent &&
    isDigest(value.canonical_digest) &&
    value.grants_execution_authority === false &&
    !("token" in value) &&
    !("credential" in value) &&
    !("secret" in value)
  );
}

function isStepRunBoundToPlan(
  value: unknown,
  index: number,
  runId: string,
  plan: WorkflowRunPlan,
): value is WorkflowExecutionStepRun {
  if (!isObject(value) || !hasExactKeys(value, stepRunFields)) return false;
  const planStep = plan.steps[index];
  if (!planStep) return false;
  return (
    isIdentifier(value.step_run_id) &&
    value.run_id === runId &&
    value.step_id === planStep.step_id &&
    value.ordinal === index + 1 &&
    value.ordinal === planStep.ordinal &&
    value.kind === planStep.kind &&
    value.capability_class === planStep.capability_class &&
    Number.isSafeInteger(value.timeout_seconds) &&
    Number(value.timeout_seconds) >= 1 &&
    Number(value.timeout_seconds) <= 3_600 &&
    Array.isArray(value.depends_on) &&
    value.depends_on.every(isIdentifier) &&
    value.depends_on.every((dependency) =>
      plan.steps.slice(0, index).some((step) => step.step_id === dependency),
    ) &&
    new Set(value.depends_on).size === value.depends_on.length &&
    value.state === "not_started" &&
    isDigest(value.canonical_digest)
  );
}

function isRunBoundToPlan(value: unknown, plan: WorkflowRunPlan): value is WorkflowExecutionRun {
  if (
    !isObject(value) ||
    !hasExactKeys(value, runFields) ||
    !isScope(value.scope) ||
    !Array.isArray(value.step_runs) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  return (
    isIdentifier(value.run_id) &&
    value.plan_id === plan.plan_id &&
    value.plan_digest === plan.canonical_digest &&
    value.definition_id === plan.definition_id &&
    value.definition_version === plan.definition_version &&
    value.definition_digest === plan.definition_digest &&
    value.scope.organization_id === plan.scope.organization_id &&
    value.scope.environment_id === plan.scope.environment_id &&
    value.scope.site_id === plan.scope.site_id &&
    value.target_id === plan.target_id &&
    value.target_type === plan.target_type &&
    isIdentifier(value.lease_id) &&
    isDigest(value.lease_digest) &&
    Number.isSafeInteger(value.fencing_token) &&
    Number(value.fencing_token) >= 1 &&
    isIdentifier(value.materialized_by_subject_id) &&
    isTimestamp(value.created_at) &&
    value.state === "created" &&
    value.step_runs.length === plan.steps.length &&
    value.step_runs.every((stepRun, index) =>
      isStepRunBoundToPlan(stepRun, index, value.run_id as string, plan),
    ) &&
    hasSafeAuthority(value.authority) &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function isAttemptBoundToRun(
  value: unknown,
  run: WorkflowExecutionRun,
): value is WorkflowExecutionAttempt {
  if (
    !isObject(value) ||
    !hasExactKeys(value, attemptFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const stepRun = run.step_runs.find((candidate) => candidate.step_run_id === value.step_run_id);
  return Boolean(
    stepRun &&
      isIdentifier(value.attempt_id) &&
      value.run_id === run.run_id &&
      value.run_digest === run.canonical_digest &&
      value.step_run_digest === stepRun.canonical_digest &&
      value.step_id === stepRun.step_id &&
      value.attempt_number === 1 &&
      value.plan_id === run.plan_id &&
      value.plan_digest === run.plan_digest &&
      value.definition_id === run.definition_id &&
      value.definition_version === run.definition_version &&
      value.definition_digest === run.definition_digest &&
      value.scope.organization_id === run.scope.organization_id &&
      value.scope.environment_id === run.scope.environment_id &&
      value.scope.site_id === run.scope.site_id &&
      value.target_id === run.target_id &&
      value.target_type === run.target_type &&
      value.lease_id === run.lease_id &&
      isDigest(value.lease_digest) &&
      value.fencing_token === run.fencing_token &&
      value.materialized_by_subject_id === run.materialized_by_subject_id &&
      isTimestamp(value.created_at) &&
      Date.parse(value.created_at) >= Date.parse(run.created_at) &&
      value.state === "created" &&
      hasSafeAuthority(value.authority) &&
      value.grants_execution_authority === false &&
      isDigest(value.canonical_digest),
  );
}

function areAttemptsBoundToRun(
  attempts: unknown[],
  run: WorkflowExecutionRun,
): attempts is WorkflowExecutionAttempt[] {
  const seenAttempts = new Set<string>();
  const seenStepRuns = new Set<string>();
  let priorStepIndex = -1;
  return attempts.every((attempt) => {
    if (!isAttemptBoundToRun(attempt, run)) return false;
    const stepIndex = run.step_runs.findIndex((stepRun) => stepRun.step_run_id === attempt.step_run_id);
    if (
      stepIndex <= priorStepIndex ||
      seenAttempts.has(attempt.attempt_id) ||
      seenStepRuns.has(attempt.step_run_id)
    ) {
      return false;
    }
    priorStepIndex = stepIndex;
    seenAttempts.add(attempt.attempt_id);
    seenStepRuns.add(attempt.step_run_id);
    return true;
  });
}

function isDispatchIntentBoundToAttempt(
  value: unknown,
  attempt: WorkflowExecutionAttempt,
): value is WorkflowDispatchIntent {
  if (
    !isObject(value) ||
    !hasExactKeys(value, dispatchIntentFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  return (
    isIdentifier(value.dispatch_intent_id) &&
    value.plan_id === attempt.plan_id &&
    value.plan_digest === attempt.plan_digest &&
    value.run_id === attempt.run_id &&
    value.run_digest === attempt.run_digest &&
    value.step_run_id === attempt.step_run_id &&
    value.step_run_digest === attempt.step_run_digest &&
    value.step_id === attempt.step_id &&
    value.attempt_id === attempt.attempt_id &&
    value.attempt_digest === attempt.canonical_digest &&
    value.attempt_number === attempt.attempt_number &&
    value.scope.organization_id === attempt.scope.organization_id &&
    value.scope.environment_id === attempt.scope.environment_id &&
    value.scope.site_id === attempt.scope.site_id &&
    value.target_id === attempt.target_id &&
    value.target_type === attempt.target_type &&
    value.lease_id === attempt.lease_id &&
    isDigest(value.lease_digest) &&
    value.fencing_token === attempt.fencing_token &&
    isIdentifier(value.worker_subject_id) &&
    isTimestamp(value.staged_at) &&
    Date.parse(value.staged_at) >= Date.parse(attempt.created_at) &&
    value.state === "staged" &&
    hasSafeAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function areDispatchIntentsBoundToAttempt(
  intents: unknown[],
  attempt: WorkflowExecutionAttempt,
): intents is WorkflowDispatchIntent[] {
  const seen = new Set<string>();
  return intents.every((intent) => {
    if (!isDispatchIntentBoundToAttempt(intent, attempt) || seen.has(intent.dispatch_intent_id)) {
      return false;
    }
    seen.add(intent.dispatch_intent_id);
    return true;
  });
}

function isDispatchOutboxEntryBoundToIntent(
  value: unknown,
  intent: WorkflowDispatchIntent,
): value is WorkflowDispatchOutboxEntry {
  if (
    !isObject(value) ||
    !hasExactKeys(value, dispatchOutboxEntryFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  return (
    isIdentifier(value.outbox_entry_id) &&
    value.dispatch_intent_id === intent.dispatch_intent_id &&
    value.dispatch_intent_digest === intent.canonical_digest &&
    value.plan_id === intent.plan_id &&
    value.plan_digest === intent.plan_digest &&
    value.run_id === intent.run_id &&
    value.run_digest === intent.run_digest &&
    value.step_run_id === intent.step_run_id &&
    value.step_run_digest === intent.step_run_digest &&
    value.step_id === intent.step_id &&
    value.attempt_id === intent.attempt_id &&
    value.attempt_digest === intent.attempt_digest &&
    value.attempt_number === intent.attempt_number &&
    value.scope.organization_id === intent.scope.organization_id &&
    value.scope.environment_id === intent.scope.environment_id &&
    value.scope.site_id === intent.scope.site_id &&
    value.target_id === intent.target_id &&
    value.target_type === intent.target_type &&
    value.lease_id === intent.lease_id &&
    value.lease_digest === intent.lease_digest &&
    value.fencing_token === intent.fencing_token &&
    value.worker_subject_id === intent.worker_subject_id &&
    isTimestamp(value.admitted_at) &&
    Date.parse(value.admitted_at) === Date.parse(intent.staged_at) &&
    value.state === "pending_publication" &&
    hasSafeAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function areDispatchOutboxEntriesBoundToIntent(
  entries: unknown[],
  intent: WorkflowDispatchIntent,
): entries is WorkflowDispatchOutboxEntry[] {
  const seen = new Set<string>();
  return entries.every((entry) => {
    if (
      !isDispatchOutboxEntryBoundToIntent(entry, intent) ||
      seen.has(entry.outbox_entry_id)
    ) {
      return false;
    }
    seen.add(entry.outbox_entry_id);
    return true;
  });
}

function isDispatchOutboxPublicationLeaseBoundToEntry(
  value: unknown,
  entry: WorkflowDispatchOutboxEntry,
  serverTime: string,
): value is WorkflowDispatchOutboxPublicationLease {
  if (
    !isObject(value) ||
    !hasExactKeys(value, dispatchOutboxPublicationLeaseFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  if (
    !isTimestamp(value.acquired_at) ||
    !isTimestamp(value.last_heartbeat_at) ||
    !isTimestamp(value.expires_at)
  ) {
    return false;
  }
  const acquiredAt = Date.parse(value.acquired_at);
  const lastHeartbeatAt = Date.parse(value.last_heartbeat_at);
  const expiresAt = Date.parse(value.expires_at);
  const expectedEffectiveState =
    value.state === "released"
      ? "released"
      : Date.parse(serverTime) >= expiresAt
        ? "expired"
        : "active";
  return (
    isIdentifier(value.publication_lease_id) &&
    value.outbox_entry_id === entry.outbox_entry_id &&
    value.outbox_entry_digest === entry.canonical_digest &&
    value.dispatch_intent_id === entry.dispatch_intent_id &&
    value.dispatch_intent_digest === entry.dispatch_intent_digest &&
    value.plan_id === entry.plan_id &&
    value.plan_digest === entry.plan_digest &&
    value.run_id === entry.run_id &&
    value.run_digest === entry.run_digest &&
    value.step_run_id === entry.step_run_id &&
    value.step_run_digest === entry.step_run_digest &&
    value.step_id === entry.step_id &&
    value.attempt_id === entry.attempt_id &&
    value.attempt_digest === entry.attempt_digest &&
    value.attempt_number === entry.attempt_number &&
    value.scope.organization_id === entry.scope.organization_id &&
    value.scope.environment_id === entry.scope.environment_id &&
    value.scope.site_id === entry.scope.site_id &&
    value.target_id === entry.target_id &&
    value.target_type === entry.target_type &&
    value.orchestration_lease_id === entry.lease_id &&
    value.orchestration_lease_digest === entry.lease_digest &&
    value.orchestration_fencing_token === entry.fencing_token &&
    isIdentifier(value.publisher_subject_id) &&
    acquiredAt >= Date.parse(entry.admitted_at) &&
    acquiredAt <= lastHeartbeatAt &&
    lastHeartbeatAt < expiresAt &&
    Number.isInteger(value.publication_fencing_token) &&
    Number(value.publication_fencing_token) >= 1 &&
    (value.state === "active" || value.state === "released") &&
    hasSafeAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest) &&
    value.effective_state === expectedEffectiveState
  );
}

function hasSafeDispatchEventAuthority(value: unknown): value is WorkflowDispatchEventAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, dispatchEventAuthorityFields) &&
    dispatchEventAuthorityFields.every((field) => value[field] === false)
  );
}

function isDispatchEventEnvelopeBoundToEntry(
  value: unknown,
  entry: WorkflowDispatchOutboxEntry,
  publicationLease: WorkflowDispatchOutboxPublicationLease | null,
): value is WorkflowDispatchEventEnvelope {
  if (
    !isObject(value) ||
    !hasExactKeys(value, dispatchEventEnvelopeFields) ||
    !isObject(value.payload) ||
    !hasExactKeys(value.payload, dispatchEventEnvelopePayloadFields) ||
    !isExactScope(value.payload.scope) ||
    !isObject(value.extensions) ||
    Object.keys(value.extensions).length !== 0 ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const payload = value.payload;
  const payloadScope = payload.scope as WorkflowRunPlan["scope"];
  return (
    publicationLease !== null &&
    isIdentifier(value.event_id) &&
    value.event_type === "WorkflowStepDispatchRequested" &&
    value.event_version === "1.0" &&
    isIdentifier(value.producer) &&
    isIdentifier(value.producer_version) &&
    isTimestamp(value.occurred_at) &&
    Date.parse(value.occurred_at) === Date.parse(entry.admitted_at) &&
    isTimestamp(value.recorded_at) &&
    isTimestamp(value.prepared_at) &&
    Date.parse(value.recorded_at) === Date.parse(value.prepared_at) &&
    Date.parse(value.recorded_at) >= Date.parse(value.occurred_at) &&
    value.subject_type === "workflow-execution-attempt" &&
    value.subject_id === entry.attempt_id &&
    value.organization_id === entry.scope.organization_id &&
    value.environment_id === entry.scope.environment_id &&
    value.correlation_id === entry.run_id &&
    value.causation_id === entry.dispatch_intent_id &&
    value.workflow_id === entry.run_id &&
    value.data_classification === "internal" &&
    value.schema_uri === "urn:project-atlas:event:workflow-step-dispatch-requested:1.0" &&
    payload.plan_id === entry.plan_id &&
    payload.plan_digest === entry.plan_digest &&
    payload.run_id === entry.run_id &&
    payload.run_digest === entry.run_digest &&
    payload.step_run_id === entry.step_run_id &&
    payload.step_run_digest === entry.step_run_digest &&
    payload.step_id === entry.step_id &&
    payload.attempt_id === entry.attempt_id &&
    payload.attempt_digest === entry.attempt_digest &&
    payload.attempt_number === entry.attempt_number &&
    payloadScope.organization_id === entry.scope.organization_id &&
    payloadScope.environment_id === entry.scope.environment_id &&
    payloadScope.site_id === entry.scope.site_id &&
    payload.target_id === entry.target_id &&
    payload.target_type === entry.target_type &&
    payload.dispatch_intent_id === entry.dispatch_intent_id &&
    payload.dispatch_intent_digest === entry.dispatch_intent_digest &&
    payload.outbox_entry_id === entry.outbox_entry_id &&
    payload.outbox_entry_digest === entry.canonical_digest &&
    value.orchestration_lease_id === entry.lease_id &&
    value.orchestration_lease_digest === entry.lease_digest &&
    value.orchestration_fencing_token === entry.fencing_token &&
    value.publication_lease_id === publicationLease.publication_lease_id &&
    value.publication_lease_digest === publicationLease.canonical_digest &&
    value.publication_fencing_token === publicationLease.publication_fencing_token &&
    value.publisher_subject_id === publicationLease.publisher_subject_id &&
    value.state === "prepared" &&
    hasSafeDispatchEventAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function isEventTransportAdmissionBoundToEnvelope(
  value: unknown,
  envelope: WorkflowDispatchEventEnvelope,
  entry: WorkflowDispatchOutboxEntry,
  publicationLease: WorkflowDispatchOutboxPublicationLease,
): value is WorkflowEventTransportAdmission {
  if (
    !isObject(value) ||
    !hasExactKeys(value, eventTransportAdmissionFields) ||
    !isExactScope(value.scope) ||
    !isObject(value.policy) ||
    !hasExactKeys(value.policy, eventTransportAdmissionPolicyFields) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const policy = value.policy;
  const admissionScope = value.scope;
  return (
    isIdentifier(value.transport_admission_id) &&
    value.event_id === envelope.event_id &&
    value.event_digest === envelope.canonical_digest &&
    value.outbox_entry_id === entry.outbox_entry_id &&
    value.outbox_entry_digest === entry.canonical_digest &&
    value.dispatch_intent_id === entry.dispatch_intent_id &&
    value.dispatch_intent_digest === entry.dispatch_intent_digest &&
    value.plan_id === entry.plan_id &&
    value.plan_digest === entry.plan_digest &&
    value.run_id === entry.run_id &&
    value.run_digest === entry.run_digest &&
    value.step_run_id === entry.step_run_id &&
    value.step_run_digest === entry.step_run_digest &&
    value.step_id === entry.step_id &&
    value.attempt_id === entry.attempt_id &&
    value.attempt_digest === entry.attempt_digest &&
    value.attempt_number === entry.attempt_number &&
    admissionScope.organization_id === entry.scope.organization_id &&
    admissionScope.environment_id === entry.scope.environment_id &&
    admissionScope.site_id === entry.scope.site_id &&
    value.target_id === entry.target_id &&
    value.target_type === entry.target_type &&
    policy.policy_id === "policy.workflow-event-transport-admission" &&
    policy.policy_version === "1.0" &&
    isDigest(policy.policy_digest) &&
    policy.allowed_event_type === envelope.event_type &&
    policy.allowed_event_version === envelope.event_version &&
    policy.allowed_schema_uri === envelope.schema_uri &&
    policy.allowed_data_classification === envelope.data_classification &&
    policy.representation_name === "canonical-json" &&
    policy.encoding === "utf-8" &&
    policy.maximum_canonical_byte_count === 65_536 &&
    Number.isInteger(value.canonical_byte_count) &&
    Number(value.canonical_byte_count) >= 1 &&
    Number(value.canonical_byte_count) <= Number(policy.maximum_canonical_byte_count) &&
    value.publisher_subject_id === publicationLease.publisher_subject_id &&
    value.orchestration_lease_id === envelope.orchestration_lease_id &&
    value.orchestration_lease_digest === envelope.orchestration_lease_digest &&
    value.orchestration_fencing_token === envelope.orchestration_fencing_token &&
    value.publication_lease_id === envelope.publication_lease_id &&
    value.publication_lease_digest === envelope.publication_lease_digest &&
    value.publication_fencing_token === envelope.publication_fencing_token &&
    isTimestamp(value.admitted_at) &&
    Date.parse(value.admitted_at) >= Date.parse(envelope.prepared_at) &&
    value.state === "admitted" &&
    hasSafeDispatchEventAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function isEventByteArtifactBoundToAdmission(
  value: unknown,
  admission: WorkflowEventTransportAdmission,
  envelope: WorkflowDispatchEventEnvelope,
  entry: WorkflowDispatchOutboxEntry,
  publicationLease: WorkflowDispatchOutboxPublicationLease,
): value is WorkflowEventByteArtifact {
  if (
    !isObject(value) ||
    !hasExactKeys(value, eventByteArtifactFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value) ||
    !isEventTransportAdmissionBoundToEnvelope(admission, envelope, entry, publicationLease)
  ) {
    return false;
  }
  const artifactScope = value.scope;
  return (
    isIdentifier(value.byte_artifact_id) &&
    value.transport_admission_id === admission.transport_admission_id &&
    value.transport_admission_digest === admission.canonical_digest &&
    value.event_id === admission.event_id &&
    value.event_digest === admission.event_digest &&
    value.outbox_entry_id === admission.outbox_entry_id &&
    value.outbox_entry_digest === admission.outbox_entry_digest &&
    value.dispatch_intent_id === admission.dispatch_intent_id &&
    value.dispatch_intent_digest === admission.dispatch_intent_digest &&
    value.plan_id === admission.plan_id &&
    value.plan_digest === admission.plan_digest &&
    value.run_id === admission.run_id &&
    value.run_digest === admission.run_digest &&
    value.step_run_id === admission.step_run_id &&
    value.step_run_digest === admission.step_run_digest &&
    value.step_id === admission.step_id &&
    value.attempt_id === admission.attempt_id &&
    value.attempt_digest === admission.attempt_digest &&
    value.attempt_number === admission.attempt_number &&
    artifactScope.organization_id === admission.scope.organization_id &&
    artifactScope.environment_id === admission.scope.environment_id &&
    artifactScope.site_id === admission.scope.site_id &&
    value.target_id === admission.target_id &&
    value.target_type === admission.target_type &&
    value.policy_id === admission.policy.policy_id &&
    value.policy_version === admission.policy.policy_version &&
    value.policy_digest === admission.policy.policy_digest &&
    value.representation_name === admission.policy.representation_name &&
    value.encoding === admission.policy.encoding &&
    value.media_type === "application/json" &&
    Number.isInteger(value.byte_count) &&
    Number(value.byte_count) === admission.canonical_byte_count &&
    Number(value.byte_count) >= 1 &&
    Number(value.byte_count) <= admission.policy.maximum_canonical_byte_count &&
    isDigest(value.content_sha256) &&
    value.publisher_subject_id === admission.publisher_subject_id &&
    value.orchestration_lease_id === admission.orchestration_lease_id &&
    value.orchestration_lease_digest === admission.orchestration_lease_digest &&
    value.orchestration_fencing_token === admission.orchestration_fencing_token &&
    value.publication_lease_id === admission.publication_lease_id &&
    value.publication_lease_digest === admission.publication_lease_digest &&
    value.publication_fencing_token === admission.publication_fencing_token &&
    isTimestamp(value.materialized_at) &&
    Date.parse(value.materialized_at) >= Date.parse(admission.admitted_at) &&
    value.state === "materialized" &&
    hasSafeDispatchEventAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function isRunPlan(value: unknown): value is WorkflowRunPlan {
  if (
    !isObject(value) ||
    !isObject(value.scope) ||
    !Array.isArray(value.steps) ||
    !Array.isArray(value.transition_history)
  ) {
    return false;
  }
  const baseValid =
    isIdentifier(value.plan_id) &&
    isIdentifier(value.definition_id) &&
    Number.isInteger(value.definition_version) &&
    Number(value.definition_version) >= 1 &&
    isDigest(value.definition_digest) &&
    isIdentifier(value.scope.organization_id) &&
    isIdentifier(value.scope.environment_id) &&
    isIdentifier(value.scope.site_id) &&
    isIdentifier(value.target_id) &&
    value.target_type === "storage" &&
    isDigest(value.canonical_input_digest) &&
    isIdentifier(value.creator_subject_id) &&
    typeof value.created_at === "string" &&
    !Number.isNaN(Date.parse(value.created_at)) &&
    (value.state === "planned" || value.state === "cancelled") &&
    value.steps.length >= 1 &&
    value.steps.every(isPlanStep) &&
    typeof value.durable === "boolean" &&
    hasSafeAuthority(value.authority) &&
    value.safety_notice === WORKFLOW_PLAN_SAFETY_NOTICE &&
    isDigest(value.canonical_digest);
  if (!baseValid) return false;
  const transitionsValid = value.transition_history.every((transition) =>
    isTransition(
      transition,
      value.scope as WorkflowRunPlan["scope"],
      value.target_id as string,
    ),
  );
  return (
    transitionsValid &&
    ((value.state === "planned" && value.transition_history.length === 0) ||
      (value.state === "cancelled" && value.transition_history.length === 1))
  );
}

async function readData(response: Response, failure: string): Promise<unknown> {
  if (!response.ok) throw new ApiRequestError(failure, response.status);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiRequestError(`${failure}: malformed JSON`, response.status);
  }
  if (!isObject(payload) || !("data" in payload)) {
    throw new ApiRequestError(`${failure}: malformed envelope`, response.status);
  }
  return payload.data;
}

export async function listWorkflowDefinitions(): Promise<WorkflowDefinitionInventory> {
  const response = await apiFetch("/api/v1/workflows/definitions", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow definition list failed");
  if (!isObject(data) || !Array.isArray(data.definitions) || !data.definitions.every(isDefinition)) {
    throw new ApiRequestError("Workflow definition list was unsafe", response.status);
  }
  return { definitions: data.definitions };
}

export async function listWorkflowPlans(input: {
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowPlanInventory> {
  const response = await apiFetch("/api/v1/workflows/plans?limit=50", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow plan list failed");
  if (!isObject(data) || !Array.isArray(data.plans) || !data.plans.every(isRunPlan)) {
    throw new ApiRequestError("Workflow plan list was unsafe", response.status);
  }
  if (
    typeof data.durable !== "boolean" ||
    typeof data.truncated !== "boolean" ||
    !data.plans.every(
      (plan) =>
        isBoundToScope(plan, input.scope) &&
        input.authorizedTargetIds.includes(plan.target_id) &&
        plan.durable === data.durable,
    )
  ) {
    throw new ApiRequestError("Workflow plan list was outside the authorized scope", response.status);
  }
  return data as WorkflowPlanInventory;
}

export async function getWorkflowPlan(input: {
  planId: string;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  const response = await apiFetch(`/api/v1/workflows/plans/${encodeURIComponent(input.planId)}`, {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow plan retrieval failed");
  if (
    !isRunPlan(data) ||
    data.plan_id !== input.planId ||
    !isBoundToScope(data, input.scope) ||
    !input.authorizedTargetIds.includes(data.target_id)
  ) {
    throw new ApiRequestError("Workflow plan response was unsafe", response.status);
  }
  return data;
}

export async function getWorkflowOrchestrationLease(input: {
  plan: WorkflowRunPlan;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowOrchestrationLeaseStatus> {
  if (
    !isBoundToScope(input.plan, input.scope) ||
    !input.authorizedTargetIds.includes(input.plan.target_id)
  ) {
    throw new ApiRequestError("Workflow plan is outside the authorized lease scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.plan.plan_id)}/orchestration-lease`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow orchestration lease retrieval failed");
  if (
    !isObject(data) ||
    data.plan_id !== input.plan.plan_id ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean" ||
    !(data.lease === null || isLeaseBoundToPlan(data.lease, input.plan))
  ) {
    throw new ApiRequestError("Workflow orchestration lease response was unsafe", response.status);
  }
  return data as WorkflowOrchestrationLeaseStatus;
}

export async function getWorkflowMaterializedRun(input: {
  plan: WorkflowRunPlan;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowMaterializedRunStatus> {
  if (
    !isBoundToScope(input.plan, input.scope) ||
    !input.authorizedTargetIds.includes(input.plan.target_id)
  ) {
    throw new ApiRequestError("Workflow plan is outside the authorized run scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.plan.plan_id)}/materialized-run`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow materialized run retrieval failed");
  if (
    !isObject(data) ||
    data.plan_id !== input.plan.plan_id ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean" ||
    !(data.run === null || isRunBoundToPlan(data.run, input.plan))
  ) {
    throw new ApiRequestError("Workflow materialized run response was unsafe", response.status);
  }
  return data as WorkflowMaterializedRunStatus;
}

export async function listWorkflowRunAttempts(input: {
  run: WorkflowExecutionRun;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowExecutionAttemptInventory> {
  if (
    input.run.scope.organization_id !== input.scope.organizationId ||
    input.run.scope.environment_id !== input.scope.environmentId ||
    input.run.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(input.run.target_id) ||
    !hasSafeAuthority(input.run.authority) ||
    input.run.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow run is outside the authorized attempt scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.run.plan_id)}/runs/${encodeURIComponent(input.run.run_id)}/attempts`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow attempt evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, attemptInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.run_id !== input.run.run_id ||
    !Array.isArray(data.attempts) ||
    !areAttemptsBoundToRun(data.attempts, input.run) ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError("Workflow attempt evidence response was unsafe", response.status);
  }
  return data as WorkflowExecutionAttemptInventory;
}

export async function listWorkflowAttemptDispatchIntents(input: {
  attempt: WorkflowExecutionAttempt;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowDispatchIntentInventory> {
  if (
    input.attempt.scope.organization_id !== input.scope.organizationId ||
    input.attempt.scope.environment_id !== input.scope.environmentId ||
    input.attempt.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(input.attempt.target_id) ||
    !hasSafeAuthority(input.attempt.authority) ||
    input.attempt.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow attempt is outside the authorized dispatch-intent scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.attempt.plan_id)}/runs/${encodeURIComponent(input.attempt.run_id)}/attempts/${encodeURIComponent(input.attempt.attempt_id)}/dispatch-intents`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow dispatch-intent evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, dispatchIntentInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.attempt_id !== input.attempt.attempt_id ||
    !Array.isArray(data.dispatch_intents) ||
    !areDispatchIntentsBoundToAttempt(data.dispatch_intents, input.attempt) ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError("Workflow dispatch-intent evidence response was unsafe", response.status);
  }
  return data as WorkflowDispatchIntentInventory;
}

export async function listWorkflowDispatchOutboxEntries(input: {
  dispatchIntent: WorkflowDispatchIntent;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowDispatchOutboxInventory> {
  const intent = input.dispatchIntent;
  if (
    intent.scope.organization_id !== input.scope.organizationId ||
    intent.scope.environment_id !== input.scope.environmentId ||
    intent.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(intent.target_id) ||
    !hasSafeAuthority(intent.authority) ||
    intent.grants_publication_authority !== false ||
    intent.grants_delivery_authority !== false ||
    intent.grants_dispatch_authority !== false ||
    intent.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow dispatch intent is outside the authorized outbox scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(intent.plan_id)}/runs/${encodeURIComponent(intent.run_id)}/attempts/${encodeURIComponent(intent.attempt_id)}/dispatch-intents/${encodeURIComponent(intent.dispatch_intent_id)}/outbox`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow dispatch outbox evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, dispatchOutboxInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.dispatch_intent_id !== intent.dispatch_intent_id ||
    !Array.isArray(data.outbox_entries) ||
    data.outbox_entries.length !== 1 ||
    !areDispatchOutboxEntriesBoundToIntent(data.outbox_entries, intent) ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError("Workflow dispatch outbox evidence response was unsafe", response.status);
  }
  return data as WorkflowDispatchOutboxInventory;
}

export async function listWorkflowDispatchOutboxPublicationLeases(input: {
  outboxEntry: WorkflowDispatchOutboxEntry;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowDispatchOutboxPublicationLeaseInventory> {
  const entry = input.outboxEntry;
  if (
    entry.scope.organization_id !== input.scope.organizationId ||
    entry.scope.environment_id !== input.scope.environmentId ||
    entry.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(entry.target_id) ||
    !hasSafeAuthority(entry.authority) ||
    entry.grants_publication_authority !== false ||
    entry.grants_delivery_authority !== false ||
    entry.grants_dispatch_authority !== false ||
    entry.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow outbox entry is outside the authorized publication-lease scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(entry.plan_id)}/runs/${encodeURIComponent(entry.run_id)}/attempts/${encodeURIComponent(entry.attempt_id)}/dispatch-intents/${encodeURIComponent(entry.dispatch_intent_id)}/outbox/${encodeURIComponent(entry.outbox_entry_id)}/publication-lease`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow publication lease evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, dispatchOutboxPublicationLeaseInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.outbox_entry_id !== entry.outbox_entry_id ||
    !Array.isArray(data.publication_leases) ||
    data.publication_leases.length > 1 ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError("Workflow publication lease evidence response was unsafe", response.status);
  }
  const serverTime = data.server_time;
  if (
    !data.publication_leases.every((lease) =>
      isDispatchOutboxPublicationLeaseBoundToEntry(lease, entry, serverTime),
    )
  ) {
    throw new ApiRequestError("Workflow publication lease evidence response was unsafe", response.status);
  }
  return data as WorkflowDispatchOutboxPublicationLeaseInventory;
}

export async function listWorkflowDispatchEventEnvelopes(input: {
  outboxEntry: WorkflowDispatchOutboxEntry;
  publicationLease: WorkflowDispatchOutboxPublicationLease | null;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowDispatchEventEnvelopeInventory> {
  const entry = input.outboxEntry;
  if (
    entry.scope.organization_id !== input.scope.organizationId ||
    entry.scope.environment_id !== input.scope.environmentId ||
    entry.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(entry.target_id) ||
    !hasSafeAuthority(entry.authority) ||
    entry.grants_publication_authority !== false ||
    entry.grants_delivery_authority !== false ||
    entry.grants_dispatch_authority !== false ||
    entry.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow outbox entry is outside the authorized event-envelope scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(entry.plan_id)}/runs/${encodeURIComponent(entry.run_id)}/attempts/${encodeURIComponent(entry.attempt_id)}/dispatch-intents/${encodeURIComponent(entry.dispatch_intent_id)}/outbox/${encodeURIComponent(entry.outbox_entry_id)}/event-envelope`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow event-envelope evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, dispatchEventEnvelopeInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.outbox_entry_id !== entry.outbox_entry_id ||
    !Array.isArray(data.event_envelopes) ||
    data.event_envelopes.length > 1 ||
    typeof data.durable !== "boolean" ||
    !data.event_envelopes.every((envelope) =>
      isDispatchEventEnvelopeBoundToEntry(envelope, entry, input.publicationLease),
    )
  ) {
    throw new ApiRequestError("Workflow event-envelope evidence response was unsafe", response.status);
  }
  return data as WorkflowDispatchEventEnvelopeInventory;
}

export async function listWorkflowEventTransportAdmissions(input: {
  eventEnvelope: WorkflowDispatchEventEnvelope;
  outboxEntry: WorkflowDispatchOutboxEntry;
  publicationLease: WorkflowDispatchOutboxPublicationLease | null;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowEventTransportAdmissionInventory> {
  const { eventEnvelope: envelope, outboxEntry: entry, publicationLease } = input;
  if (
    publicationLease === null ||
    entry.scope.organization_id !== input.scope.organizationId ||
    entry.scope.environment_id !== input.scope.environmentId ||
    entry.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(entry.target_id) ||
    !isDispatchEventEnvelopeBoundToEntry(envelope, entry, publicationLease)
  ) {
    throw new ApiRequestError("Workflow event envelope is outside the authorized transport-admission scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(entry.plan_id)}/runs/${encodeURIComponent(entry.run_id)}/attempts/${encodeURIComponent(entry.attempt_id)}/dispatch-intents/${encodeURIComponent(entry.dispatch_intent_id)}/outbox/${encodeURIComponent(entry.outbox_entry_id)}/event-envelope/${encodeURIComponent(envelope.event_id)}/transport-admission`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow transport-admission evidence retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, eventTransportAdmissionInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.event_id !== envelope.event_id ||
    !Array.isArray(data.transport_admissions) ||
    data.transport_admissions.length > 1 ||
    typeof data.durable !== "boolean" ||
    !data.transport_admissions.every((admission) =>
      isEventTransportAdmissionBoundToEnvelope(admission, envelope, entry, publicationLease),
    )
  ) {
    throw new ApiRequestError("Workflow transport-admission evidence response was unsafe", response.status);
  }
  return data as WorkflowEventTransportAdmissionInventory;
}

export async function listWorkflowEventByteArtifacts(input: {
  transportAdmission: WorkflowEventTransportAdmission;
  eventEnvelope: WorkflowDispatchEventEnvelope;
  outboxEntry: WorkflowDispatchOutboxEntry;
  publicationLease: WorkflowDispatchOutboxPublicationLease | null;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowEventByteArtifactInventory> {
  const {
    transportAdmission: admission,
    eventEnvelope: envelope,
    outboxEntry: entry,
    publicationLease,
  } = input;
  if (
    publicationLease === null ||
    entry.scope.organization_id !== input.scope.organizationId ||
    entry.scope.environment_id !== input.scope.environmentId ||
    entry.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(entry.target_id) ||
    !isEventTransportAdmissionBoundToEnvelope(admission, envelope, entry, publicationLease)
  ) {
    throw new ApiRequestError("Workflow transport admission is outside the authorized byte-artifact scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(entry.plan_id)}/runs/${encodeURIComponent(entry.run_id)}/attempts/${encodeURIComponent(entry.attempt_id)}/dispatch-intents/${encodeURIComponent(entry.dispatch_intent_id)}/outbox/${encodeURIComponent(entry.outbox_entry_id)}/event-envelope/${encodeURIComponent(envelope.event_id)}/transport-admission/${encodeURIComponent(admission.transport_admission_id)}/byte-artifact`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow event byte-artifact metadata retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, eventByteArtifactInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.transport_admission_id !== admission.transport_admission_id ||
    !Array.isArray(data.byte_artifacts) ||
    data.byte_artifacts.length > 1 ||
    typeof data.durable !== "boolean" ||
    !data.byte_artifacts.every((artifact) =>
      isEventByteArtifactBoundToAdmission(
        artifact,
        admission,
        envelope,
        entry,
        publicationLease,
      ),
    )
  ) {
    throw new ApiRequestError("Workflow event byte-artifact metadata response was unsafe", response.status);
  }
  return data as WorkflowEventByteArtifactInventory;
}

export async function createWorkflowPlan(input: {
  definition: WorkflowDefinition;
  targetId: string;
  purpose: string;
  inputSummary: string;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  if (!input.authorizedTargetIds.includes(input.targetId)) {
    throw new ApiRequestError("Storage target is outside the authorized workflow scope", 403);
  }
  const response = await apiFetch("/api/v1/workflows/plans", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `workflow-plan-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.workflow-run-plan-create-input.v1",
      definition_id: input.definition.definition_id,
      definition_version: input.definition.version,
      target_id: input.targetId,
      target_type: "storage",
      inputs: {
        purpose: input.purpose.trim(),
        input_summary: input.inputSummary.trim(),
      },
      acknowledged_planning_only_no_execution_authority: true,
    }),
  });
  const data = await readData(response, "Workflow plan creation failed");
  if (
    !isRunPlan(data) ||
    data.definition_id !== input.definition.definition_id ||
    data.definition_version !== input.definition.version ||
    data.definition_digest !== input.definition.definition_digest ||
    data.target_id !== input.targetId ||
    !isBoundToScope(data, input.scope)
  ) {
    throw new ApiRequestError("Workflow plan creation response was not request-bound", response.status);
  }
  return data;
}

export async function cancelWorkflowPlan(input: {
  plan: WorkflowRunPlan;
  reason: string;
  acknowledgeNoExternalUndo: boolean;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  if (
    input.plan.state !== "planned" ||
    !isBoundToScope(input.plan, input.scope) ||
    !input.authorizedTargetIds.includes(input.plan.target_id)
  ) {
    throw new ApiRequestError("Workflow plan is not cancellable in this scope", 409);
  }
  const reason = input.reason.trim().replace(/\s+/g, " ");
  if (!reason || reason.length > 500 || input.acknowledgeNoExternalUndo !== true) {
    throw new ApiRequestError("Workflow cancellation requires a reason and acknowledgement", 422);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.plan.plan_id)}/cancellation`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `workflow-plan-cancel.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.workflow-run-plan-cancellation-input.v1",
        reason,
        acknowledge_no_external_undo: true,
      }),
    },
  );
  const data = await readData(response, "Workflow plan cancellation failed");
  if (
    !isRunPlan(data) ||
    data.plan_id !== input.plan.plan_id ||
    data.state !== "cancelled" ||
    data.target_id !== input.plan.target_id ||
    !isBoundToScope(data, input.scope) ||
    !input.authorizedTargetIds.includes(data.target_id) ||
    data.transition_history.length !== 1 ||
    data.transition_history.at(0)?.reason !== reason
  ) {
    throw new ApiRequestError(
      "Workflow plan cancellation response was not request-bound",
      response.status,
    );
  }
  return data;
}
