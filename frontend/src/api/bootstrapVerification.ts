import {
  isBootstrapRun,
  isVerificationExecution,
  type BootstrapState,
  type BootstrapVerificationExecution,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { BootstrapDataPlan } from "./bootstrapData";
import type { BootstrapIdentityPlan } from "./bootstrapIdentity";
import type { BootstrapIntegrationPlan } from "./bootstrapIntegrations";
import type { BootstrapServicePlan } from "./bootstrapServices";
import type { BootstrapTrustPlan } from "./bootstrapTrust";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapVerificationPlan = {
  schema_version: "atlas.bootstrap-verification-plan.v1";
  suite_version: "atlas.bootstrap-verification-suite.v1";
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
  ingress_contract_id: string;
  target_id: string;
  target_kind: string;
  target_state: "empty" | "reusable";
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

export type BootstrapVerificationResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapVerificationExecution;
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
  infrastructure_mutation_performed: false;
  deployment_action_performed: false;
  ai_advice_generated: false;
};

type VerificationPlanResponse = { data: BootstrapVerificationPlan };
type VerificationResponse = { data: BootstrapVerificationResult };

function isVerificationPlan(value: unknown): value is BootstrapVerificationPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-verification-plan.v1" &&
    candidate.suite_version === "atlas.bootstrap-verification-suite.v1" &&
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
    typeof candidate.ingress_contract_id === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
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

function isVerificationPlanResponse(value: unknown): value is VerificationPlanResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "data" in value &&
    isVerificationPlan(value.data)
  );
}

function isVerificationResponse(value: unknown): value is VerificationResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isVerificationExecution(candidate.execution) &&
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
    candidate.infrastructure_mutation_performed === false &&
    candidate.deployment_action_performed === false &&
    candidate.ai_advice_generated === false
  );
}

export async function previewBootstrapVerificationPlan(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  servicePlan: BootstrapServicePlan;
  identityPlan: BootstrapIdentityPlan;
  integrationPlan: BootstrapIntegrationPlan;
  scope: CurrentIdentity["scope"];
}): Promise<VerificationPlanResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.verify") {
    throw new Error("Verification planning requires the current verify phase");
  }
  const response = await apiFetch("/api/v1/platform/bootstrap-verification-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-verification-plan-request.v1",
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
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap verification plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isVerificationPlanResponse(payload)) {
    throw new Error("Bootstrap verification plan returned malformed evidence");
  }
  return payload;
}

export async function verifyBootstrapEndToEnd(input: {
  state: BootstrapState;
  plan: BootstrapVerificationPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<VerificationResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.verify") {
    throw new Error("End-to-end verification requires the current verify phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/phases/verify`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-verification.${run.version}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-verification.v1",
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.verify",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: input.plan.configuration_digest,
      trust_plan_digest: input.plan.trust_plan_digest,
      data_plan_digest: input.plan.data_plan_digest,
      service_plan_digest: input.plan.service_plan_digest,
      identity_plan_digest: input.plan.identity_plan_digest,
      integration_plan_digest: input.plan.integration_plan_digest,
      verification_schema_version: input.plan.schema_version,
      suite_version: input.plan.suite_version,
      verification_plan_digest: input.plan.verification_plan_digest,
      target_id: input.plan.target_id,
      expected_target_state: input.plan.target_state,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap verification failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isVerificationResponse(payload)) {
    throw new Error("Bootstrap verification returned malformed evidence");
  }
  return payload;
}
