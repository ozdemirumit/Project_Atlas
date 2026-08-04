import {
  isBootstrapRun,
  isHandoffExecution,
  type BootstrapState,
  type BootstrapHandoffExecution,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { BootstrapDataPlan } from "./bootstrapData";
import type { BootstrapIdentityPlan } from "./bootstrapIdentity";
import type { BootstrapIntegrationPlan } from "./bootstrapIntegrations";
import type { BootstrapServicePlan } from "./bootstrapServices";
import type { BootstrapTrustPlan } from "./bootstrapTrust";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapHandoffPlan = {
  schema_version: "atlas.bootstrap-handoff-plan.v1";
  suite_version: "atlas.bootstrap-handoff-suite.v1";
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  source_run_id: string;
  source_run_version: number;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  service_plan_digest: string;
  identity_plan_digest: string;
  integration_plan_digest: string;
  verification_plan_digest: string;
  verification_report_digest: string;
  source_evidence_digest: string;
  handoff_plan_digest: string;
  ingress_contract_id: string;
  target_id: string;
  target_kind: string;
  target_state: "empty" | "reusable";
  readiness_class: "developer_linux_lab_bootstrap_complete";
  readiness_claims: {
    production_ready: false;
    customer_integrations_validated: false;
    support_accepted: false;
    ha_certified: false;
    dr_certified: false;
    backup_restore_validated: false;
    release_approved: false;
  };
  known_limitation_ids: string[];
  pending_action_ids: string[];
  owner_role_ids: string[];
  missing_production_evidence_ids: string[];
  checks: Array<{
    check_id: string;
    category_id: string;
    subject_id: string;
    state: "passed" | "not_applicable";
    result_code: string;
    mandatory: boolean;
  }>;
  state: "passed";
  result_code: string;
  generated_at: string;
  external_operations_authorized: false;
};

export type BootstrapHandoffResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapHandoffExecution;
  replayed: boolean;
  synthetic_report_mutation_performed: boolean;
  model_request_performed: false;
  network_request_performed: false;
  secret_resolution_performed: false;
  connector_invocation_performed: false;
  knowledge_mutation_performed: false;
  workflow_execution_performed: false;
  approval_creation_performed: false;
  backup_restore_operation_performed: false;
  external_export_performed: false;
  support_bundle_export_performed: false;
  ticket_creation_performed: false;
  notification_performed: false;
  infrastructure_mutation_performed: false;
  deployment_action_performed: false;
  ai_advice_generated: false;
};

type HandoffPlanResponse = { data: BootstrapHandoffPlan };
type HandoffResponse = { data: BootstrapHandoffResult };

function isHandoffPlan(value: unknown): value is BootstrapHandoffPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-handoff-plan.v1" &&
    candidate.suite_version === "atlas.bootstrap-handoff-suite.v1" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.source_run_id === "string" &&
    typeof candidate.source_run_version === "number" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.service_plan_digest === "string" &&
    typeof candidate.identity_plan_digest === "string" &&
    typeof candidate.integration_plan_digest === "string" &&
    typeof candidate.verification_plan_digest === "string" &&
    typeof candidate.verification_report_digest === "string" &&
    typeof candidate.source_evidence_digest === "string" &&
    typeof candidate.handoff_plan_digest === "string" &&
    typeof candidate.ingress_contract_id === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
    candidate.readiness_class === "developer_linux_lab_bootstrap_complete" &&
    isFalseReadinessClaims(candidate.readiness_claims) &&
    isStringCatalog(candidate.known_limitation_ids, 7) &&
    isStringCatalog(candidate.pending_action_ids, 7) &&
    isStringCatalog(candidate.owner_role_ids, 5) &&
    isStringCatalog(candidate.missing_production_evidence_ids, 7) &&
    Array.isArray(candidate.checks) &&
    candidate.checks.length === 15 &&
    candidate.checks.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const check = item as Record<string, unknown>;
      return (
        typeof check.check_id === "string" &&
        typeof check.category_id === "string" &&
        typeof check.subject_id === "string" &&
        (check.state === "passed" || check.state === "not_applicable") &&
        typeof check.result_code === "string" &&
        typeof check.mandatory === "boolean"
      );
    }) &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    typeof candidate.generated_at === "string" &&
    candidate.external_operations_authorized === false
  );
}

function isStringCatalog(value: unknown, length: number): value is string[] {
  return (
    Array.isArray(value) &&
    value.length === length &&
    value.every((item) => typeof item === "string")
  );
}

function isFalseReadinessClaims(value: unknown): value is BootstrapHandoffPlan["readiness_claims"] {
  if (typeof value !== "object" || value === null) return false;
  const claims = value as Record<string, unknown>;
  return (
    claims.production_ready === false &&
    claims.customer_integrations_validated === false &&
    claims.support_accepted === false &&
    claims.ha_certified === false &&
    claims.dr_certified === false &&
    claims.backup_restore_validated === false &&
    claims.release_approved === false
  );
}

function isHandoffPlanResponse(value: unknown): value is HandoffPlanResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "data" in value &&
    isHandoffPlan(value.data)
  );
}

function isHandoffResponse(value: unknown): value is HandoffResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isHandoffExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.synthetic_report_mutation_performed === "boolean" &&
    candidate.model_request_performed === false &&
    candidate.network_request_performed === false &&
    candidate.secret_resolution_performed === false &&
    candidate.connector_invocation_performed === false &&
    candidate.knowledge_mutation_performed === false &&
    candidate.workflow_execution_performed === false &&
    candidate.approval_creation_performed === false &&
    candidate.backup_restore_operation_performed === false &&
    candidate.external_export_performed === false &&
    candidate.support_bundle_export_performed === false &&
    candidate.ticket_creation_performed === false &&
    candidate.notification_performed === false &&
    candidate.infrastructure_mutation_performed === false &&
    candidate.deployment_action_performed === false &&
    candidate.ai_advice_generated === false
  );
}

export async function previewBootstrapHandoffPlan(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  servicePlan: BootstrapServicePlan;
  identityPlan: BootstrapIdentityPlan;
  integrationPlan: BootstrapIntegrationPlan;
  scope: CurrentIdentity["scope"];
}): Promise<HandoffPlanResponse> {
  const run = input.state.run;
  const verification = run?.end_to_end_verification;
  const verificationEvidence = verification?.evidence[0];
  if (
    !run ||
    run.current_phase_id !== "phase.handoff" ||
    verification?.state !== "completed" ||
    verification.evidence.length !== 1 ||
    !verificationEvidence
  ) {
    throw new Error("Handoff planning requires completed verification evidence");
  }
  const response = await apiFetch("/api/v1/platform/bootstrap-handoff-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-handoff-plan-request.v1",
      release_id: run.release_id,
      profile: run.profile,
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      source_run_id: run.run_id,
      source_run_version: run.version,
      configuration_digest: input.configuration.configuration_digest,
      trust_plan_digest: input.trustPlan.trust_plan_digest,
      data_plan_digest: input.dataPlan.data_plan_digest,
      service_plan_digest: input.servicePlan.service_plan_digest,
      identity_plan_digest: input.identityPlan.identity_plan_digest,
      integration_plan_digest: input.integrationPlan.integration_plan_digest,
      verification_plan_digest: verification.verification_plan_digest,
      verification_report_digest: verificationEvidence.sha256,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap handoff plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isHandoffPlanResponse(payload)) {
    throw new Error("Bootstrap handoff plan returned malformed evidence");
  }
  return payload;
}

export async function completeBootstrapHandoff(input: {
  state: BootstrapState;
  plan: BootstrapHandoffPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<HandoffResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.handoff") {
    throw new Error("Operational handoff requires the current handoff phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/phases/handoff`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-handoff.${run.version}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-handoff.v1",
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.handoff",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: input.plan.configuration_digest,
      trust_plan_digest: input.plan.trust_plan_digest,
      data_plan_digest: input.plan.data_plan_digest,
      service_plan_digest: input.plan.service_plan_digest,
      identity_plan_digest: input.plan.identity_plan_digest,
      integration_plan_digest: input.plan.integration_plan_digest,
      verification_plan_digest: input.plan.verification_plan_digest,
      verification_report_digest: input.plan.verification_report_digest,
      source_evidence_digest: input.plan.source_evidence_digest,
      handoff_schema_version: input.plan.schema_version,
      suite_version: input.plan.suite_version,
      handoff_plan_digest: input.plan.handoff_plan_digest,
      target_id: input.plan.target_id,
      expected_target_state: input.plan.target_state,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap handoff failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isHandoffResponse(payload)) {
    throw new Error("Bootstrap handoff returned malformed evidence");
  }
  return payload;
}
