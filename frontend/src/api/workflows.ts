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

export type WorkflowEventLogicalChannelBinding = {
  logical_channel_binding_id: string;
  byte_artifact_id: string;
  byte_artifact_digest: string;
  content_sha256: string;
  byte_count: number;
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
  policy_id: "policy.workflow-event-logical-channel";
  policy_version: "1.0";
  policy_digest: string;
  logical_channel_id: "channel.workflow-dispatch.internal";
  logical_channel_version: "1.0";
  delivery_semantics: "at-least-once";
  durability_required: true;
  ordering_key_kind: "workflow-run";
  ordering_key_value: string;
  retention_class: "workflow-operational";
  publisher_subject_id: string;
  orchestration_lease_id: string;
  orchestration_lease_digest: string;
  orchestration_fencing_token: number;
  publication_lease_id: string;
  publication_lease_digest: string;
  publication_fencing_token: number;
  bound_at: string;
  state: "bound";
  authority: WorkflowDispatchEventAuthority;
  grants_publication_authority: false;
  grants_delivery_authority: false;
  grants_dispatch_authority: false;
  grants_execution_authority: false;
  canonical_digest: string;
};

export type WorkflowEventLogicalChannelBindingInventory = {
  byte_artifact_id: string;
  logical_channel_bindings: WorkflowEventLogicalChannelBinding[];
  durable: boolean;
};

export type WorkflowTransportProfileAuthority = {
  route_selection_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowTransportEventContract = {
  event_type: "WorkflowStepDispatchRequested";
  event_version: "1.0";
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0";
};

export type WorkflowTransportProfileSnapshot = {
  snapshot_id: string;
  transport_profile_id: string;
  transport_profile_revision: string;
  source_profile_digest: string;
  deployment_release_id: string;
  deployment_profile: "developer" | "lab" | "enterprise-test" | "production" | "offline";
  scope: WorkflowRunPlan["scope"];
  transport_resource_id: string;
  transport_resource_digest: string;
  transport_implementation_id: string;
  transport_implementation_version: string;
  adapter_contract_id: string;
  adapter_contract_version: string;
  adapter_contract_digest: string;
  supported_event_contracts: WorkflowTransportEventContract[];
  supported_classifications: "internal"[];
  supported_representations: "canonical-json"[];
  supported_encodings: "utf-8"[];
  supported_delivery_semantics: "at-least-once"[];
  durable_delivery_supported: boolean;
  supported_ordering_key_kinds: "workflow-run"[];
  supported_retention_classes: "workflow-operational"[];
  maximum_message_byte_count: number;
  transport_encryption_required: boolean;
  restricted_network_supported: boolean;
  snapshotter_subject_id: string;
  captured_at: string;
  state: "snapshotted";
  authority: WorkflowTransportProfileAuthority;
  canonical_digest: string;
};

export type WorkflowTransportProfileSnapshotInventory = {
  transport_profile_snapshots: WorkflowTransportProfileSnapshot[];
  durable: boolean;
};

export type WorkflowTransportRouteAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  endpoint_resolution_authorized: false;
  credential_access_authorized: false;
  network_access_authorized: false;
  readiness_probe_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowTransportRouteSnapshot = {
  snapshot_id: string;
  route_id: string;
  route_revision: string;
  route_set_id: string;
  route_set_revision: string;
  selection_epoch_id: string;
  selection_epoch_revision: string;
  source_route_digest: string;
  deployment_release_id: string;
  deployment_profile: "developer" | "lab" | "enterprise-test" | "production" | "offline";
  scope: WorkflowRunPlan["scope"];
  transport_profile_id: string;
  transport_profile_revision: string;
  transport_resource_id: string;
  transport_implementation_id: string;
  transport_implementation_version: string;
  adapter_contract_id: string;
  adapter_contract_version: string;
  route_kind: "message-broker";
  endpoint_set_id: string;
  endpoint_set_revision: string;
  destination_id: string;
  destination_revision: string;
  routing_contract_id: string;
  routing_contract_revision: string;
  transport_security_policy_id: string;
  transport_security_policy_version: string;
  minimum_tls_version: "1.3";
  server_authentication_required: true;
  client_authentication_required: boolean;
  plaintext_fallback_prohibited: true;
  network_policy_id: string;
  network_policy_version: string;
  source_zone_class: string;
  destination_zone_class: string;
  restricted_network_enforced: true;
  public_egress_prohibited: true;
  proxy_mode: "prohibited" | "deployment-managed";
  credential_requirement_profile_id: string;
  credential_requirement_profile_version: string;
  authentication_mechanism_class: "mutual-tls" | "workload-token";
  principal_class: "service-workload";
  snapshotter_subject_id: string;
  captured_at: string;
  state: "snapshotted";
  authority: WorkflowTransportRouteAuthority;
  canonical_digest: string;
};

export type WorkflowTransportRouteSnapshotInventory = {
  transport_route_snapshots: WorkflowTransportRouteSnapshot[];
  durable: boolean;
};

export type WorkflowPhysicalTransportRouteBindingAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  endpoint_resolution_authorized: false;
  credential_access_authorized: false;
  network_access_authorized: false;
  readiness_probe_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowPhysicalTransportRouteBinding = {
  binding_id: string;
  logical_channel_binding_id: string;
  compatibility_admission_id: string;
  transport_profile_snapshot_id: string;
  transport_route_snapshot_id: string;
  policy_id: string;
  policy_version: string;
  scope: WorkflowRunPlan["scope"];
  binder_subject_id: string;
  bound_at: string;
  state: "bound";
  authority: WorkflowPhysicalTransportRouteBindingAuthority;
  integrity_reference: string;
};

export type WorkflowPhysicalTransportRouteBindingInventory = {
  physical_transport_route_bindings: WorkflowPhysicalTransportRouteBinding[];
  durable: boolean;
};

export type WorkflowPhysicalTransportRouteFreshnessAdmissionAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  endpoint_resolution_authorized: false;
  credential_access_authorized: false;
  network_access_authorized: false;
  readiness_probe_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowPhysicalTransportRouteFreshnessAdmission = {
  freshness_admission_id: string;
  physical_transport_route_binding_id: string;
  transport_route_snapshot_id: string;
  selection_head_id: string;
  selection_generation: number;
  policy_id: "policy.workflow-event-physical-transport-route-freshness";
  policy_version: "1.0";
  scope: WorkflowRunPlan["scope"];
  admitter_subject_id: string;
  evaluated_at: string;
  valid_until: string;
  state: "admitted_current";
  authority: WorkflowPhysicalTransportRouteFreshnessAdmissionAuthority;
  integrity_reference: string;
};

export type WorkflowPhysicalTransportRouteFreshnessAdmissionInventory = {
  physical_transport_route_freshness_admissions: WorkflowPhysicalTransportRouteFreshnessAdmission[];
  durable: boolean;
};

export type WorkflowEndpointResolutionAuthorizationLeaseAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  endpoint_resolution_authorized: true;
  credential_access_authorized: false;
  network_access_authorized: false;
  readiness_probe_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowEndpointResolutionAuthorizationLease = {
  lease_id: string;
  freshness_admission_id: string;
  selection_generation: number;
  policy_id: string;
  policy_version: "1.0";
  scope: WorkflowRunPlan["scope"];
  resolver_subject_id: string;
  authorized_at: string;
  expires_at: string;
  state: "authorized_unconsumed";
  effective_state: "active" | "expired" | "consumed";
  single_use: true;
  renewable: false;
  authority: WorkflowEndpointResolutionAuthorizationLeaseAuthority;
  integrity_reference: string;
};

export type WorkflowEndpointResolutionAuthorizationLeaseInventory = {
  endpoint_resolution_authorization_leases: WorkflowEndpointResolutionAuthorizationLease[];
  server_time: string;
  durable: boolean;
};

export type WorkflowPhysicalTransportEndpointMaterializationAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  endpoint_resolution_authorized: false;
  credential_access_authorized: false;
  network_access_authorized: false;
  readiness_probe_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowPhysicalTransportEndpointMaterialization = {
  materialization_id: string;
  lease_id: string;
  freshness_admission_id: string;
  selection_generation: number;
  policy_id: string;
  policy_version: "1.0";
  scope: WorkflowRunPlan["scope"];
  resolver_subject_id: string;
  consumed_at: string;
  recorded_at: string | null;
  outcome: "materialized_protected" | "failed_closed_consumed" | "uncertain_consumed";
  lease_consumed: true;
  protected_storage_verified: boolean;
  raw_endpoint_disclosed: false;
  authority: WorkflowPhysicalTransportEndpointMaterializationAuthority;
  integrity_reference: string;
};

export type WorkflowPhysicalTransportEndpointMaterializationInventory = {
  physical_transport_endpoint_materializations: WorkflowPhysicalTransportEndpointMaterialization[];
  server_time: string;
  durable: boolean;
};

export type WorkflowTransportCompatibilityAuthority = {
  route_selection_authorized: false;
  route_binding_authorized: false;
  credential_access_authorized: false;
  publication_authorized: false;
  delivery_authorized: false;
  dispatch_authorized: false;
  execution_authorized: false;
};

export type WorkflowTransportCompatibilityAdmission = {
  compatibility_admission_id: string;
  logical_channel_binding_id: string;
  logical_channel_binding_digest: string;
  transport_profile_snapshot_id: string;
  transport_profile_snapshot_digest: string;
  transport_profile_id: string;
  transport_profile_revision: string;
  policy_id: "policy.workflow-event-transport-compatibility";
  policy_version: "1.0";
  policy_digest: string;
  scope: WorkflowRunPlan["scope"];
  event_type: "WorkflowStepDispatchRequested";
  event_version: "1.0";
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0";
  data_classification: "internal";
  representation_name: "canonical-json";
  encoding: "utf-8";
  delivery_semantics: "at-least-once";
  durability_required: true;
  ordering_key_kind: "workflow-run";
  retention_class: "workflow-operational";
  logical_maximum_byte_count: number;
  artifact_byte_count: number;
  profile_maximum_message_byte_count: number;
  admitter_subject_id: string;
  admitted_at: string;
  state: "admitted";
  authority: WorkflowTransportCompatibilityAuthority;
  canonical_digest: string;
};

export type WorkflowTransportCompatibilityAdmissionInventory = {
  logical_channel_binding_id: string;
  transport_compatibility_admissions: WorkflowTransportCompatibilityAdmission[];
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
const eventLogicalChannelBindingFields = [
  "logical_channel_binding_id",
  "byte_artifact_id",
  "byte_artifact_digest",
  "content_sha256",
  "byte_count",
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
  "logical_channel_id",
  "logical_channel_version",
  "delivery_semantics",
  "durability_required",
  "ordering_key_kind",
  "ordering_key_value",
  "retention_class",
  "publisher_subject_id",
  "orchestration_lease_id",
  "orchestration_lease_digest",
  "orchestration_fencing_token",
  "publication_lease_id",
  "publication_lease_digest",
  "publication_fencing_token",
  "bound_at",
  "state",
  "authority",
  "grants_publication_authority",
  "grants_delivery_authority",
  "grants_dispatch_authority",
  "grants_execution_authority",
  "canonical_digest",
] as const;
const eventLogicalChannelBindingInventoryFields = [
  "byte_artifact_id",
  "logical_channel_bindings",
  "durable",
] as const;
const transportProfileAuthorityFields = [
  "route_selection_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const transportProfileEventContractFields = ["event_type", "event_version", "schema_uri"] as const;
const transportProfileSnapshotFields = [
  "snapshot_id",
  "transport_profile_id",
  "transport_profile_revision",
  "source_profile_digest",
  "deployment_release_id",
  "deployment_profile",
  "scope",
  "transport_resource_id",
  "transport_resource_digest",
  "transport_implementation_id",
  "transport_implementation_version",
  "adapter_contract_id",
  "adapter_contract_version",
  "adapter_contract_digest",
  "supported_event_contracts",
  "supported_classifications",
  "supported_representations",
  "supported_encodings",
  "supported_delivery_semantics",
  "durable_delivery_supported",
  "supported_ordering_key_kinds",
  "supported_retention_classes",
  "maximum_message_byte_count",
  "transport_encryption_required",
  "restricted_network_supported",
  "snapshotter_subject_id",
  "captured_at",
  "state",
  "authority",
  "canonical_digest",
] as const;
const transportProfileSnapshotInventoryFields = [
  "transport_profile_snapshots",
  "durable",
] as const;
const transportRouteAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "endpoint_resolution_authorized",
  "credential_access_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const transportRouteSnapshotFields = [
  "snapshot_id",
  "route_id",
  "route_revision",
  "route_set_id",
  "route_set_revision",
  "selection_epoch_id",
  "selection_epoch_revision",
  "source_route_digest",
  "deployment_release_id",
  "deployment_profile",
  "scope",
  "transport_profile_id",
  "transport_profile_revision",
  "transport_resource_id",
  "transport_implementation_id",
  "transport_implementation_version",
  "adapter_contract_id",
  "adapter_contract_version",
  "route_kind",
  "endpoint_set_id",
  "endpoint_set_revision",
  "destination_id",
  "destination_revision",
  "routing_contract_id",
  "routing_contract_revision",
  "transport_security_policy_id",
  "transport_security_policy_version",
  "minimum_tls_version",
  "server_authentication_required",
  "client_authentication_required",
  "plaintext_fallback_prohibited",
  "network_policy_id",
  "network_policy_version",
  "source_zone_class",
  "destination_zone_class",
  "restricted_network_enforced",
  "public_egress_prohibited",
  "proxy_mode",
  "credential_requirement_profile_id",
  "credential_requirement_profile_version",
  "authentication_mechanism_class",
  "principal_class",
  "snapshotter_subject_id",
  "captured_at",
  "state",
  "authority",
  "canonical_digest",
] as const;
const transportRouteSnapshotInventoryFields = ["transport_route_snapshots", "durable"] as const;
const physicalTransportRouteBindingAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "endpoint_resolution_authorized",
  "credential_access_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const physicalTransportRouteBindingFields = [
  "binding_id",
  "logical_channel_binding_id",
  "compatibility_admission_id",
  "transport_profile_snapshot_id",
  "transport_route_snapshot_id",
  "policy_id",
  "policy_version",
  "scope",
  "binder_subject_id",
  "bound_at",
  "state",
  "authority",
  "integrity_reference",
] as const;
const physicalTransportRouteBindingInventoryFields = [
  "physical_transport_route_bindings",
  "durable",
] as const;
const physicalTransportRouteFreshnessAdmissionAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "endpoint_resolution_authorized",
  "credential_access_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const physicalTransportRouteFreshnessAdmissionFields = [
  "freshness_admission_id",
  "physical_transport_route_binding_id",
  "transport_route_snapshot_id",
  "selection_head_id",
  "selection_generation",
  "policy_id",
  "policy_version",
  "scope",
  "admitter_subject_id",
  "evaluated_at",
  "valid_until",
  "state",
  "authority",
  "integrity_reference",
] as const;
const physicalTransportRouteFreshnessAdmissionInventoryFields = [
  "physical_transport_route_freshness_admissions",
  "durable",
] as const;
const endpointResolutionAuthorizationLeaseAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "endpoint_resolution_authorized",
  "credential_access_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const endpointResolutionAuthorizationLeaseFields = [
  "lease_id",
  "freshness_admission_id",
  "selection_generation",
  "policy_id",
  "policy_version",
  "scope",
  "resolver_subject_id",
  "authorized_at",
  "expires_at",
  "state",
  "effective_state",
  "single_use",
  "renewable",
  "authority",
  "integrity_reference",
] as const;
const endpointResolutionAuthorizationLeaseInventoryFields = [
  "endpoint_resolution_authorization_leases",
  "server_time",
  "durable",
] as const;
const physicalTransportEndpointMaterializationAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "endpoint_resolution_authorized",
  "credential_access_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const physicalTransportEndpointMaterializationFields = [
  "materialization_id",
  "lease_id",
  "freshness_admission_id",
  "selection_generation",
  "policy_id",
  "policy_version",
  "scope",
  "resolver_subject_id",
  "consumed_at",
  "recorded_at",
  "outcome",
  "lease_consumed",
  "protected_storage_verified",
  "raw_endpoint_disclosed",
  "authority",
  "integrity_reference",
] as const;
const physicalTransportEndpointMaterializationInventoryFields = [
  "physical_transport_endpoint_materializations",
  "server_time",
  "durable",
] as const;
const transportCompatibilityAuthorityFields = [
  "route_selection_authorized",
  "route_binding_authorized",
  "credential_access_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
] as const;
const transportCompatibilityAdmissionFields = [
  "compatibility_admission_id",
  "logical_channel_binding_id",
  "logical_channel_binding_digest",
  "transport_profile_snapshot_id",
  "transport_profile_snapshot_digest",
  "transport_profile_id",
  "transport_profile_revision",
  "policy_id",
  "policy_version",
  "policy_digest",
  "scope",
  "event_type",
  "event_version",
  "schema_uri",
  "data_classification",
  "representation_name",
  "encoding",
  "delivery_semantics",
  "durability_required",
  "ordering_key_kind",
  "retention_class",
  "logical_maximum_byte_count",
  "artifact_byte_count",
  "profile_maximum_message_byte_count",
  "admitter_subject_id",
  "admitted_at",
  "state",
  "authority",
  "canonical_digest",
] as const;
const transportCompatibilityAdmissionInventoryFields = [
  "logical_channel_binding_id",
  "transport_compatibility_admissions",
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

function isStableIdentifier(value: unknown): value is string {
  return typeof value === "string" && /^[a-z][a-z0-9_.:-]{2,239}$/.test(value);
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

function isSortedUniqueArray<T extends string>(
  value: unknown,
  allowed: ReadonlySet<T>,
): value is T[] {
  if (!Array.isArray(value) || value.length < 1) {
    return false;
  }
  const unknownValues: unknown[] = value;
  if (
    !unknownValues.every(
      (item) => typeof item === "string" && allowed.has(item as T),
    )
  ) {
    return false;
  }
  const values = unknownValues as T[];
  return (
    new Set(values).size === values.length &&
    values.every((item, index) => {
      const previous = values[index - 1];
      return index === 0 || (previous !== undefined && previous.localeCompare(item) < 0);
    })
  );
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

function isEventLogicalChannelBindingBoundToArtifact(
  value: unknown,
  artifact: WorkflowEventByteArtifact,
): value is WorkflowEventLogicalChannelBinding {
  if (
    !isObject(value) ||
    !hasExactKeys(value, eventLogicalChannelBindingFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const bindingScope = value.scope;
  return (
    isIdentifier(value.logical_channel_binding_id) &&
    value.byte_artifact_id === artifact.byte_artifact_id &&
    value.byte_artifact_digest === artifact.canonical_digest &&
    value.content_sha256 === artifact.content_sha256 &&
    value.byte_count === artifact.byte_count &&
    value.transport_admission_id === artifact.transport_admission_id &&
    value.transport_admission_digest === artifact.transport_admission_digest &&
    value.event_id === artifact.event_id &&
    value.event_digest === artifact.event_digest &&
    value.outbox_entry_id === artifact.outbox_entry_id &&
    value.outbox_entry_digest === artifact.outbox_entry_digest &&
    value.dispatch_intent_id === artifact.dispatch_intent_id &&
    value.dispatch_intent_digest === artifact.dispatch_intent_digest &&
    value.plan_id === artifact.plan_id &&
    value.plan_digest === artifact.plan_digest &&
    value.run_id === artifact.run_id &&
    value.run_digest === artifact.run_digest &&
    value.step_run_id === artifact.step_run_id &&
    value.step_run_digest === artifact.step_run_digest &&
    value.step_id === artifact.step_id &&
    value.attempt_id === artifact.attempt_id &&
    value.attempt_digest === artifact.attempt_digest &&
    value.attempt_number === artifact.attempt_number &&
    bindingScope.organization_id === artifact.scope.organization_id &&
    bindingScope.environment_id === artifact.scope.environment_id &&
    bindingScope.site_id === artifact.scope.site_id &&
    value.target_id === artifact.target_id &&
    value.target_type === artifact.target_type &&
    value.policy_id === "policy.workflow-event-logical-channel" &&
    value.policy_version === "1.0" &&
    isDigest(value.policy_digest) &&
    value.logical_channel_id === "channel.workflow-dispatch.internal" &&
    value.logical_channel_version === "1.0" &&
    value.delivery_semantics === "at-least-once" &&
    value.durability_required === true &&
    value.ordering_key_kind === "workflow-run" &&
    value.ordering_key_value === artifact.run_id &&
    value.retention_class === "workflow-operational" &&
    value.publisher_subject_id === artifact.publisher_subject_id &&
    value.orchestration_lease_id === artifact.orchestration_lease_id &&
    value.orchestration_lease_digest === artifact.orchestration_lease_digest &&
    value.orchestration_fencing_token === artifact.orchestration_fencing_token &&
    value.publication_lease_id === artifact.publication_lease_id &&
    value.publication_lease_digest === artifact.publication_lease_digest &&
    value.publication_fencing_token === artifact.publication_fencing_token &&
    isTimestamp(value.bound_at) &&
    Date.parse(value.bound_at) >= Date.parse(artifact.materialized_at) &&
    value.state === "bound" &&
    hasSafeDispatchEventAuthority(value.authority) &&
    value.grants_publication_authority === false &&
    value.grants_delivery_authority === false &&
    value.grants_dispatch_authority === false &&
    value.grants_execution_authority === false &&
    isDigest(value.canonical_digest)
  );
}

function hasZeroTransportProfileAuthority(
  value: unknown,
): value is WorkflowTransportProfileAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, transportProfileAuthorityFields) &&
    transportProfileAuthorityFields.every((field) => value[field] === false)
  );
}

function isTransportProfileEventContract(
  value: unknown,
): value is WorkflowTransportEventContract {
  return (
    isObject(value) &&
    hasExactKeys(value, transportProfileEventContractFields) &&
    value.event_type === "WorkflowStepDispatchRequested" &&
    value.event_version === "1.0" &&
    value.schema_uri ===
      "urn:project-atlas:event:workflow-step-dispatch-requested:1.0"
  );
}

function isTransportProfileSnapshot(
  value: unknown,
  scope: WorkflowScope,
): value is WorkflowTransportProfileSnapshot {
  if (
    !isObject(value) ||
    !hasExactKeys(value, transportProfileSnapshotFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const snapshotScope = value.scope;
  return (
    isIdentifier(value.snapshot_id) &&
    isIdentifier(value.transport_profile_id) &&
    isIdentifier(value.transport_profile_revision) &&
    isDigest(value.source_profile_digest) &&
    isIdentifier(value.deployment_release_id) &&
    ["developer", "lab", "enterprise-test", "production", "offline"].includes(
      String(value.deployment_profile),
    ) &&
    snapshotScope.organization_id === scope.organizationId &&
    snapshotScope.environment_id === scope.environmentId &&
    snapshotScope.site_id === scope.siteId &&
    isIdentifier(value.transport_resource_id) &&
    isDigest(value.transport_resource_digest) &&
    isIdentifier(value.transport_implementation_id) &&
    isIdentifier(value.transport_implementation_version) &&
    isIdentifier(value.adapter_contract_id) &&
    isIdentifier(value.adapter_contract_version) &&
    isDigest(value.adapter_contract_digest) &&
    Array.isArray(value.supported_event_contracts) &&
    value.supported_event_contracts.length === 1 &&
    value.supported_event_contracts.every(isTransportProfileEventContract) &&
    isSortedUniqueArray(value.supported_classifications, new Set(["internal"] as const)) &&
    isSortedUniqueArray(value.supported_representations, new Set(["canonical-json"] as const)) &&
    isSortedUniqueArray(value.supported_encodings, new Set(["utf-8"] as const)) &&
    isSortedUniqueArray(value.supported_delivery_semantics, new Set(["at-least-once"] as const)) &&
    typeof value.durable_delivery_supported === "boolean" &&
    isSortedUniqueArray(value.supported_ordering_key_kinds, new Set(["workflow-run"] as const)) &&
    isSortedUniqueArray(
      value.supported_retention_classes,
      new Set(["workflow-operational"] as const),
    ) &&
    Number.isSafeInteger(value.maximum_message_byte_count) &&
    Number(value.maximum_message_byte_count) >= 1 &&
    Number(value.maximum_message_byte_count) <= 16_777_216 &&
    typeof value.transport_encryption_required === "boolean" &&
    typeof value.restricted_network_supported === "boolean" &&
    isIdentifier(value.snapshotter_subject_id) &&
    isTimestamp(value.captured_at) &&
    value.state === "snapshotted" &&
    hasZeroTransportProfileAuthority(value.authority) &&
    isDigest(value.canonical_digest)
  );
}

function hasZeroTransportRouteAuthority(
  value: unknown,
): value is WorkflowTransportRouteAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, transportRouteAuthorityFields) &&
    transportRouteAuthorityFields.every((field) => value[field] === false)
  );
}

function isTransportRouteSnapshot(
  value: unknown,
  scope: WorkflowScope,
): value is WorkflowTransportRouteSnapshot {
  if (
    !isObject(value) ||
    !hasExactKeys(value, transportRouteSnapshotFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const snapshotScope = value.scope;
  return (
    isIdentifier(value.snapshot_id) &&
    isIdentifier(value.route_id) &&
    isIdentifier(value.route_revision) &&
    isIdentifier(value.route_set_id) &&
    isIdentifier(value.route_set_revision) &&
    isIdentifier(value.selection_epoch_id) &&
    isIdentifier(value.selection_epoch_revision) &&
    isDigest(value.source_route_digest) &&
    isIdentifier(value.deployment_release_id) &&
    ["developer", "lab", "enterprise-test", "production", "offline"].includes(
      String(value.deployment_profile),
    ) &&
    snapshotScope.organization_id === scope.organizationId &&
    snapshotScope.environment_id === scope.environmentId &&
    snapshotScope.site_id === scope.siteId &&
    isIdentifier(value.transport_profile_id) &&
    isIdentifier(value.transport_profile_revision) &&
    isIdentifier(value.transport_resource_id) &&
    isIdentifier(value.transport_implementation_id) &&
    isIdentifier(value.transport_implementation_version) &&
    isIdentifier(value.adapter_contract_id) &&
    isIdentifier(value.adapter_contract_version) &&
    value.route_kind === "message-broker" &&
    isIdentifier(value.endpoint_set_id) &&
    isIdentifier(value.endpoint_set_revision) &&
    isIdentifier(value.destination_id) &&
    isIdentifier(value.destination_revision) &&
    isIdentifier(value.routing_contract_id) &&
    isIdentifier(value.routing_contract_revision) &&
    isIdentifier(value.transport_security_policy_id) &&
    isIdentifier(value.transport_security_policy_version) &&
    value.minimum_tls_version === "1.3" &&
    value.server_authentication_required === true &&
    typeof value.client_authentication_required === "boolean" &&
    value.plaintext_fallback_prohibited === true &&
    isIdentifier(value.network_policy_id) &&
    isIdentifier(value.network_policy_version) &&
    isIdentifier(value.source_zone_class) &&
    isIdentifier(value.destination_zone_class) &&
    value.restricted_network_enforced === true &&
    value.public_egress_prohibited === true &&
    ["prohibited", "deployment-managed"].includes(String(value.proxy_mode)) &&
    isIdentifier(value.credential_requirement_profile_id) &&
    isIdentifier(value.credential_requirement_profile_version) &&
    ["mutual-tls", "workload-token"].includes(String(value.authentication_mechanism_class)) &&
    value.principal_class === "service-workload" &&
    isIdentifier(value.snapshotter_subject_id) &&
    isTimestamp(value.captured_at) &&
    value.state === "snapshotted" &&
    hasZeroTransportRouteAuthority(value.authority) &&
    isDigest(value.canonical_digest)
  );
}

function hasZeroPhysicalTransportRouteBindingAuthority(
  value: unknown,
): value is WorkflowPhysicalTransportRouteBindingAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, physicalTransportRouteBindingAuthorityFields) &&
    physicalTransportRouteBindingAuthorityFields.every((field) => value[field] === false)
  );
}

function isPhysicalTransportRouteBinding(
  value: unknown,
  scope: WorkflowScope,
): value is WorkflowPhysicalTransportRouteBinding {
  if (
    !isObject(value) ||
    !hasExactKeys(value, physicalTransportRouteBindingFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const bindingScope = value.scope;
  return (
    isIdentifier(value.binding_id) &&
    isIdentifier(value.logical_channel_binding_id) &&
    isIdentifier(value.compatibility_admission_id) &&
    isIdentifier(value.transport_profile_snapshot_id) &&
    isIdentifier(value.transport_route_snapshot_id) &&
    isIdentifier(value.policy_id) &&
    isIdentifier(value.policy_version) &&
    bindingScope.organization_id === scope.organizationId &&
    bindingScope.environment_id === scope.environmentId &&
    bindingScope.site_id === scope.siteId &&
    isIdentifier(value.binder_subject_id) &&
    isTimestamp(value.bound_at) &&
    value.state === "bound" &&
    hasZeroPhysicalTransportRouteBindingAuthority(value.authority) &&
    isIdentifier(value.integrity_reference)
  );
}

function hasZeroPhysicalTransportRouteFreshnessAdmissionAuthority(
  value: unknown,
): value is WorkflowPhysicalTransportRouteFreshnessAdmissionAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, physicalTransportRouteFreshnessAdmissionAuthorityFields) &&
    physicalTransportRouteFreshnessAdmissionAuthorityFields.every(
      (field) => value[field] === false,
    )
  );
}

function isPhysicalTransportRouteFreshnessAdmission(
  value: unknown,
  scope: WorkflowScope,
): value is WorkflowPhysicalTransportRouteFreshnessAdmission {
  if (
    !isObject(value) ||
    !hasExactKeys(value, physicalTransportRouteFreshnessAdmissionFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const admissionScope = value.scope;
  const evaluatedAt = Date.parse(String(value.evaluated_at));
  const validUntil = Date.parse(String(value.valid_until));
  return (
    isIdentifier(value.freshness_admission_id) &&
    isIdentifier(value.physical_transport_route_binding_id) &&
    isIdentifier(value.transport_route_snapshot_id) &&
    isIdentifier(value.selection_head_id) &&
    Number.isSafeInteger(value.selection_generation) &&
    Number(value.selection_generation) >= 1 &&
    value.policy_id === "policy.workflow-event-physical-transport-route-freshness" &&
    value.policy_version === "1.0" &&
    admissionScope.organization_id === scope.organizationId &&
    admissionScope.environment_id === scope.environmentId &&
    admissionScope.site_id === scope.siteId &&
    isIdentifier(value.admitter_subject_id) &&
    isTimestamp(value.evaluated_at) &&
    isTimestamp(value.valid_until) &&
    validUntil - evaluatedAt === 60_000 &&
    value.state === "admitted_current" &&
    hasZeroPhysicalTransportRouteFreshnessAdmissionAuthority(value.authority) &&
    isIdentifier(value.integrity_reference)
  );
}

function hasEndpointResolutionOnlyAuthority(
  value: unknown,
): value is WorkflowEndpointResolutionAuthorizationLeaseAuthority {
  if (!isObject(value) || !hasExactKeys(value, endpointResolutionAuthorizationLeaseAuthorityFields)) {
    return false;
  }
  return endpointResolutionAuthorizationLeaseAuthorityFields.every((field) =>
    field === "endpoint_resolution_authorized" ? value[field] === true : value[field] === false,
  );
}

function isEndpointResolutionAuthorizationLease(
  value: unknown,
  scope: WorkflowScope,
  serverTime: string,
): value is WorkflowEndpointResolutionAuthorizationLease {
  if (
    !isObject(value) ||
    !hasExactKeys(value, endpointResolutionAuthorizationLeaseFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value) ||
    !isTimestamp(value.authorized_at) ||
    !isTimestamp(value.expires_at)
  ) {
    return false;
  }
  const leaseScope = value.scope;
  const authorizedAt = Date.parse(value.authorized_at);
  const expiresAt = Date.parse(value.expires_at);
  const expectedEffectiveState = Date.parse(serverTime) >= expiresAt ? "expired" : "active";
  return (
    isStableIdentifier(value.lease_id) &&
    isStableIdentifier(value.freshness_admission_id) &&
    Number.isSafeInteger(value.selection_generation) &&
    Number(value.selection_generation) >= 1 &&
    isStableIdentifier(value.policy_id) &&
    value.policy_version === "1.0" &&
    leaseScope.organization_id === scope.organizationId &&
    leaseScope.environment_id === scope.environmentId &&
    leaseScope.site_id === scope.siteId &&
    isStableIdentifier(value.resolver_subject_id) &&
    expiresAt - authorizedAt === 15_000 &&
    value.state === "authorized_unconsumed" &&
    (value.effective_state === "consumed" || value.effective_state === expectedEffectiveState) &&
    value.single_use === true &&
    value.renewable === false &&
    hasEndpointResolutionOnlyAuthority(value.authority) &&
    isStableIdentifier(value.integrity_reference)
  );
}

function hasZeroPhysicalTransportEndpointMaterializationAuthority(
  value: unknown,
): value is WorkflowPhysicalTransportEndpointMaterializationAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, physicalTransportEndpointMaterializationAuthorityFields) &&
    physicalTransportEndpointMaterializationAuthorityFields.every(
      (field) => value[field] === false,
    )
  );
}

function isPhysicalTransportEndpointMaterialization(
  value: unknown,
  scope: WorkflowScope,
  serverTime: string,
): value is WorkflowPhysicalTransportEndpointMaterialization {
  if (
    !isObject(value) ||
    !hasExactKeys(value, physicalTransportEndpointMaterializationFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value) ||
    !isTimestamp(value.consumed_at) ||
    (value.recorded_at !== null && !isTimestamp(value.recorded_at))
  ) {
    return false;
  }
  const materializationScope = value.scope;
  const consumedAt = Date.parse(value.consumed_at);
  const recordedAt = value.recorded_at === null ? null : Date.parse(value.recorded_at);
  const resultIsConsistent =
    (value.outcome === "materialized_protected" &&
      value.protected_storage_verified === true &&
      recordedAt !== null) ||
    (value.outcome === "failed_closed_consumed" &&
      value.protected_storage_verified === false &&
      recordedAt !== null) ||
    (value.outcome === "uncertain_consumed" &&
      value.protected_storage_verified === false &&
      recordedAt === null);
  return (
    isStableIdentifier(value.materialization_id) &&
    isStableIdentifier(value.lease_id) &&
    isStableIdentifier(value.freshness_admission_id) &&
    Number.isSafeInteger(value.selection_generation) &&
    Number(value.selection_generation) >= 1 &&
    isStableIdentifier(value.policy_id) &&
    value.policy_version === "1.0" &&
    materializationScope.organization_id === scope.organizationId &&
    materializationScope.environment_id === scope.environmentId &&
    materializationScope.site_id === scope.siteId &&
    isStableIdentifier(value.resolver_subject_id) &&
    consumedAt <= Date.parse(serverTime) &&
    (recordedAt === null || (recordedAt >= consumedAt && recordedAt <= Date.parse(serverTime))) &&
    resultIsConsistent &&
    value.lease_consumed === true &&
    value.raw_endpoint_disclosed === false &&
    hasZeroPhysicalTransportEndpointMaterializationAuthority(value.authority) &&
    isStableIdentifier(value.integrity_reference)
  );
}

function hasZeroTransportCompatibilityAuthority(
  value: unknown,
): value is WorkflowTransportCompatibilityAuthority {
  return (
    isObject(value) &&
    hasExactKeys(value, transportCompatibilityAuthorityFields) &&
    transportCompatibilityAuthorityFields.every((field) => value[field] === false)
  );
}

function isTransportCompatibilityAdmissionBoundToLogicalChannel(
  value: unknown,
  binding: WorkflowEventLogicalChannelBinding,
): value is WorkflowTransportCompatibilityAdmission {
  if (
    !isObject(value) ||
    !hasExactKeys(value, transportCompatibilityAdmissionFields) ||
    !isExactScope(value.scope) ||
    containsCredentialMaterial(value)
  ) {
    return false;
  }
  const admissionScope = value.scope;
  return (
    isIdentifier(value.compatibility_admission_id) &&
    value.logical_channel_binding_id === binding.logical_channel_binding_id &&
    value.logical_channel_binding_digest === binding.canonical_digest &&
    isIdentifier(value.transport_profile_snapshot_id) &&
    isDigest(value.transport_profile_snapshot_digest) &&
    isIdentifier(value.transport_profile_id) &&
    isIdentifier(value.transport_profile_revision) &&
    value.policy_id === "policy.workflow-event-transport-compatibility" &&
    value.policy_version === "1.0" &&
    isDigest(value.policy_digest) &&
    admissionScope.organization_id === binding.scope.organization_id &&
    admissionScope.environment_id === binding.scope.environment_id &&
    admissionScope.site_id === binding.scope.site_id &&
    value.event_type === "WorkflowStepDispatchRequested" &&
    value.event_version === "1.0" &&
    value.schema_uri ===
      "urn:project-atlas:event:workflow-step-dispatch-requested:1.0" &&
    value.data_classification === "internal" &&
    value.representation_name === "canonical-json" &&
    value.encoding === "utf-8" &&
    value.delivery_semantics === binding.delivery_semantics &&
    value.durability_required === binding.durability_required &&
    value.ordering_key_kind === binding.ordering_key_kind &&
    value.retention_class === binding.retention_class &&
    Number.isSafeInteger(value.logical_maximum_byte_count) &&
    Number(value.logical_maximum_byte_count) === 65_536 &&
    Number.isSafeInteger(value.artifact_byte_count) &&
    Number(value.artifact_byte_count) === binding.byte_count &&
    Number.isSafeInteger(value.profile_maximum_message_byte_count) &&
    Number(value.profile_maximum_message_byte_count) >=
      Number(value.logical_maximum_byte_count) &&
    Number(value.profile_maximum_message_byte_count) <= 16_777_216 &&
    isIdentifier(value.admitter_subject_id) &&
    isTimestamp(value.admitted_at) &&
    Date.parse(value.admitted_at) >= Date.parse(binding.bound_at) &&
    value.state === "admitted" &&
    hasZeroTransportCompatibilityAuthority(value.authority) &&
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

export async function listWorkflowEventLogicalChannelBindings(input: {
  byteArtifact: WorkflowEventByteArtifact;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowEventLogicalChannelBindingInventory> {
  const artifact = input.byteArtifact;
  if (
    artifact.scope.organization_id !== input.scope.organizationId ||
    artifact.scope.environment_id !== input.scope.environmentId ||
    artifact.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(artifact.target_id) ||
    !hasSafeDispatchEventAuthority(artifact.authority) ||
    artifact.grants_publication_authority !== false ||
    artifact.grants_delivery_authority !== false ||
    artifact.grants_dispatch_authority !== false ||
    artifact.grants_execution_authority !== false
  ) {
    throw new ApiRequestError("Workflow byte artifact is outside the authorized logical-channel-binding scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(artifact.plan_id)}/runs/${encodeURIComponent(artifact.run_id)}/attempts/${encodeURIComponent(artifact.attempt_id)}/dispatch-intents/${encodeURIComponent(artifact.dispatch_intent_id)}/outbox/${encodeURIComponent(artifact.outbox_entry_id)}/event-envelope/${encodeURIComponent(artifact.event_id)}/transport-admission/${encodeURIComponent(artifact.transport_admission_id)}/byte-artifact/${encodeURIComponent(artifact.byte_artifact_id)}/logical-channel-binding`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow logical-channel binding retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, eventLogicalChannelBindingInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.byte_artifact_id !== artifact.byte_artifact_id ||
    !Array.isArray(data.logical_channel_bindings) ||
    data.logical_channel_bindings.length > 1 ||
    typeof data.durable !== "boolean" ||
    !data.logical_channel_bindings.every((binding) =>
      isEventLogicalChannelBindingBoundToArtifact(binding, artifact),
    )
  ) {
    throw new ApiRequestError("Workflow logical-channel binding response was unsafe", response.status);
  }
  return data as WorkflowEventLogicalChannelBindingInventory;
}

export async function listWorkflowTransportProfileSnapshots(input: {
  scope: WorkflowScope;
}): Promise<WorkflowTransportProfileSnapshotInventory> {
  const response = await apiFetch("/api/v1/workflows/transport-profile-snapshots", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow transport capability profile retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, transportProfileSnapshotInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.transport_profile_snapshots) ||
    typeof data.durable !== "boolean" ||
    !data.transport_profile_snapshots.every((snapshot) =>
      isTransportProfileSnapshot(snapshot, input.scope),
    )
  ) {
    throw new ApiRequestError("Workflow transport capability profile response was unsafe", response.status);
  }
  const identities = new Set(
    data.transport_profile_snapshots.map((snapshot) =>
      isObject(snapshot)
        ? `${String(snapshot.transport_profile_id)}:${String(snapshot.transport_profile_revision)}`
        : "",
    ),
  );
  if (identities.size !== data.transport_profile_snapshots.length) {
    throw new ApiRequestError("Workflow transport capability profile response was unsafe", response.status);
  }
  return data as WorkflowTransportProfileSnapshotInventory;
}

export async function listWorkflowTransportRouteSnapshots(input: {
  scope: WorkflowScope;
}): Promise<WorkflowTransportRouteSnapshotInventory> {
  const response = await apiFetch("/api/v1/workflows/transport-route-snapshots", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow transport route snapshot retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, transportRouteSnapshotInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.transport_route_snapshots) ||
    typeof data.durable !== "boolean" ||
    !data.transport_route_snapshots.every((snapshot) =>
      isTransportRouteSnapshot(snapshot, input.scope),
    )
  ) {
    throw new ApiRequestError("Workflow transport route snapshot response was unsafe", response.status);
  }
  const snapshotIds = new Set(
    data.transport_route_snapshots.map((snapshot) =>
      isObject(snapshot) ? snapshot.snapshot_id : undefined,
    ),
  );
  const routeRevisions = new Set(
    data.transport_route_snapshots.map((snapshot) =>
      isObject(snapshot)
        ? `${String(snapshot.route_id)}:${String(snapshot.route_revision)}`
        : "",
    ),
  );
  if (
    snapshotIds.size !== data.transport_route_snapshots.length ||
    routeRevisions.size !== data.transport_route_snapshots.length
  ) {
    throw new ApiRequestError("Workflow transport route snapshot response was unsafe", response.status);
  }
  return data as WorkflowTransportRouteSnapshotInventory;
}

export async function listWorkflowPhysicalTransportRouteBindings(input: {
  scope: WorkflowScope;
}): Promise<WorkflowPhysicalTransportRouteBindingInventory> {
  const response = await apiFetch("/api/v1/workflows/physical-transport-route-bindings", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow physical transport route binding retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, physicalTransportRouteBindingInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.physical_transport_route_bindings) ||
    data.physical_transport_route_bindings.length > 256 ||
    typeof data.durable !== "boolean" ||
    !data.physical_transport_route_bindings.every((binding) =>
      isPhysicalTransportRouteBinding(binding, input.scope),
    )
  ) {
    throw new ApiRequestError(
      "Workflow physical transport route binding response was unsafe",
      response.status,
    );
  }
  const bindingIds = new Set(
    data.physical_transport_route_bindings.map((binding) =>
      isObject(binding) ? binding.binding_id : undefined,
    ),
  );
  const logicalBindingIds = new Set(
    data.physical_transport_route_bindings.map((binding) =>
      isObject(binding) ? binding.logical_channel_binding_id : undefined,
    ),
  );
  if (
    bindingIds.size !== data.physical_transport_route_bindings.length ||
    logicalBindingIds.size !== data.physical_transport_route_bindings.length
  ) {
    throw new ApiRequestError(
      "Workflow physical transport route binding response was unsafe",
      response.status,
    );
  }
  return data as WorkflowPhysicalTransportRouteBindingInventory;
}

export async function listWorkflowPhysicalTransportRouteFreshnessAdmissions(input: {
  scope: WorkflowScope;
}): Promise<WorkflowPhysicalTransportRouteFreshnessAdmissionInventory> {
  const response = await apiFetch(
    "/api/v1/workflows/physical-transport-route-freshness-admissions",
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(
    response,
    "Workflow physical transport route freshness admission retrieval failed",
  );
  if (
    !isObject(data) ||
    !hasExactKeys(data, physicalTransportRouteFreshnessAdmissionInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.physical_transport_route_freshness_admissions) ||
    data.physical_transport_route_freshness_admissions.length > 256 ||
    typeof data.durable !== "boolean" ||
    !data.physical_transport_route_freshness_admissions.every((admission) =>
      isPhysicalTransportRouteFreshnessAdmission(admission, input.scope),
    )
  ) {
    throw new ApiRequestError(
      "Workflow physical transport route freshness admission response was unsafe",
      response.status,
    );
  }
  const admissionIds = new Set(
    data.physical_transport_route_freshness_admissions.map((admission) =>
      isObject(admission) ? admission.freshness_admission_id : undefined,
    ),
  );
  if (admissionIds.size !== data.physical_transport_route_freshness_admissions.length) {
    throw new ApiRequestError(
      "Workflow physical transport route freshness admission response was unsafe",
      response.status,
    );
  }
  return data as WorkflowPhysicalTransportRouteFreshnessAdmissionInventory;
}

export async function listWorkflowEndpointResolutionAuthorizationLeases(input: {
  scope: WorkflowScope;
}): Promise<WorkflowEndpointResolutionAuthorizationLeaseInventory> {
  const response = await apiFetch(
    "/api/v1/workflows/physical-transport-endpoint-resolution-authorization-leases",
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(
    response,
    "Workflow endpoint-resolution authorization lease retrieval failed",
  );
  if (
    !isObject(data) ||
    !hasExactKeys(data, endpointResolutionAuthorizationLeaseInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.endpoint_resolution_authorization_leases) ||
    data.endpoint_resolution_authorization_leases.length > 256 ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError(
      "Workflow endpoint-resolution authorization lease response was unsafe",
      response.status,
    );
  }
  const serverTime = data.server_time;
  if (
    !data.endpoint_resolution_authorization_leases.every((lease) =>
      isEndpointResolutionAuthorizationLease(lease, input.scope, serverTime),
    )
  ) {
    throw new ApiRequestError(
      "Workflow endpoint-resolution authorization lease response was unsafe",
      response.status,
    );
  }
  const leaseIds = new Set<string>();
  const freshnessAdmissionIds = new Set<string>();
  for (const lease of data.endpoint_resolution_authorization_leases) {
    if (
      !isObject(lease) ||
      typeof lease.lease_id !== "string" ||
      typeof lease.freshness_admission_id !== "string" ||
      leaseIds.has(lease.lease_id) ||
      freshnessAdmissionIds.has(lease.freshness_admission_id)
    ) {
      throw new ApiRequestError(
        "Workflow endpoint-resolution authorization lease response was unsafe",
        response.status,
      );
    }
    leaseIds.add(lease.lease_id);
    freshnessAdmissionIds.add(lease.freshness_admission_id);
  }
  return data as WorkflowEndpointResolutionAuthorizationLeaseInventory;
}

export async function listWorkflowPhysicalTransportEndpointMaterializations(input: {
  scope: WorkflowScope;
}): Promise<WorkflowPhysicalTransportEndpointMaterializationInventory> {
  const response = await apiFetch(
    "/api/v1/workflows/physical-transport-endpoint-materializations",
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(
    response,
    "Workflow physical transport endpoint materialization retrieval failed",
  );
  if (
    !isObject(data) ||
    !hasExactKeys(data, physicalTransportEndpointMaterializationInventoryFields) ||
    containsCredentialMaterial(data) ||
    !Array.isArray(data.physical_transport_endpoint_materializations) ||
    data.physical_transport_endpoint_materializations.length > 256 ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean"
  ) {
    throw new ApiRequestError(
      "Workflow physical transport endpoint materialization response was unsafe",
      response.status,
    );
  }
  const serverTime = data.server_time;
  if (
    !data.physical_transport_endpoint_materializations.every((materialization) =>
      isPhysicalTransportEndpointMaterialization(materialization, input.scope, serverTime),
    )
  ) {
    throw new ApiRequestError(
      "Workflow physical transport endpoint materialization response was unsafe",
      response.status,
    );
  }
  const materializationIds = new Set<string>();
  const leaseIds = new Set<string>();
  for (const materialization of data.physical_transport_endpoint_materializations) {
    if (
      !isObject(materialization) ||
      typeof materialization.materialization_id !== "string" ||
      typeof materialization.lease_id !== "string" ||
      materializationIds.has(materialization.materialization_id) ||
      leaseIds.has(materialization.lease_id)
    ) {
      throw new ApiRequestError(
        "Workflow physical transport endpoint materialization response was unsafe",
        response.status,
      );
    }
    materializationIds.add(materialization.materialization_id);
    leaseIds.add(materialization.lease_id);
  }
  return data as WorkflowPhysicalTransportEndpointMaterializationInventory;
}

export async function listWorkflowTransportCompatibilityAdmissions(input: {
  logicalChannelBinding: WorkflowEventLogicalChannelBinding;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowTransportCompatibilityAdmissionInventory> {
  const binding = input.logicalChannelBinding;
  if (
    binding.scope.organization_id !== input.scope.organizationId ||
    binding.scope.environment_id !== input.scope.environmentId ||
    binding.scope.site_id !== input.scope.siteId ||
    !input.authorizedTargetIds.includes(binding.target_id) ||
    !hasSafeDispatchEventAuthority(binding.authority) ||
    binding.grants_publication_authority !== false ||
    binding.grants_delivery_authority !== false ||
    binding.grants_dispatch_authority !== false ||
    binding.grants_execution_authority !== false
  ) {
    throw new ApiRequestError(
      "Workflow logical channel binding is outside the authorized compatibility-admission scope",
      403,
    );
  }
  const response = await apiFetch(
    `/api/v1/workflows/transport-compatibility-admissions?logical_channel_binding_id=${encodeURIComponent(binding.logical_channel_binding_id)}`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow transport compatibility admission retrieval failed");
  if (
    !isObject(data) ||
    !hasExactKeys(data, transportCompatibilityAdmissionInventoryFields) ||
    containsCredentialMaterial(data) ||
    data.logical_channel_binding_id !== binding.logical_channel_binding_id ||
    !Array.isArray(data.transport_compatibility_admissions) ||
    typeof data.durable !== "boolean" ||
    !data.transport_compatibility_admissions.every((admission) =>
      isTransportCompatibilityAdmissionBoundToLogicalChannel(admission, binding),
    )
  ) {
    throw new ApiRequestError(
      "Workflow transport compatibility admission response was unsafe",
      response.status,
    );
  }
  const admissionIds = new Set(
    data.transport_compatibility_admissions.map((admission) =>
      isObject(admission) ? admission.compatibility_admission_id : undefined,
    ),
  );
  const sourcePairs = new Set(
    data.transport_compatibility_admissions.map((admission) =>
      isObject(admission)
        ? `${String(admission.transport_profile_snapshot_id)}:${String(admission.policy_digest)}`
        : "",
    ),
  );
  if (
    admissionIds.size !== data.transport_compatibility_admissions.length ||
    sourcePairs.size !== data.transport_compatibility_admissions.length
  ) {
    throw new ApiRequestError(
      "Workflow transport compatibility admission response was unsafe",
      response.status,
    );
  }
  return data as WorkflowTransportCompatibilityAdmissionInventory;
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
