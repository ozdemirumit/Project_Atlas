import {
  isBootstrapRun,
  isIntegrationExecution,
  type BootstrapIntegrationExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { BootstrapDataPlan } from "./bootstrapData";
import type { BootstrapIdentityPlan } from "./bootstrapIdentity";
import type { BootstrapServicePlan } from "./bootstrapServices";
import type { BootstrapTrustPlan } from "./bootstrapTrust";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapIntegrationPlan = {
  schema_version: "atlas.bootstrap-integration-plan.v1";
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  service_plan_digest: string;
  identity_plan_digest: string;
  integration_plan_digest: string;
  target_id: string;
  target_kind: string;
  target_state: "empty" | "reusable";
  model_endpoint: {
    endpoint_id: string;
    owner_id: string;
    provider_type: "provider-type.openai-compatible";
    service_reference_id: string;
    credential_reference_id: string;
    model_id: string;
    context_limit: number;
    output_limit: number;
    data_classification_ceiling: string;
    residency_boundary_id: string;
    timeout_seconds: number;
    max_retries: number;
    rate_limit_per_minute: number;
    concurrency_limit: number;
    telemetry_classification: string;
    approved_task_class_ids: string[];
  };
  integrations: Array<{
    integration_id: string;
    integration_type: string;
    owner_id: string;
    purpose_id: string;
    classification: string;
    endpoint_reference_id: string;
    trust_reference_id: string;
    credential_reference_id: string | null;
    scope_id: string;
    rate_limit_per_minute: number;
    validation_operation_id: string;
    mapping_preview_id: string;
    data_flow_id: string;
    activation_state: "inactive";
  }>;
  checks: Array<{
    check_id: string;
    subject_id: string;
    state: "passed" | "not_applicable";
    result_code: string;
    mandatory: boolean;
  }>;
  state: "passed";
  result_code: string;
  generated_at: string;
  actual_model_request_authorized: false;
  network_request_authorized: false;
  secret_resolution_authorized: false;
  integration_activation_authorized: false;
  connector_invocation_authorized: false;
  infrastructure_mutation_authorized: false;
};

export type BootstrapIntegrationValidationResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapIntegrationExecution;
  replayed: boolean;
  synthetic_state_mutation_performed: boolean;
  actual_model_request_performed: false;
  network_request_performed: false;
  secret_resolution_performed: false;
  integration_activation_performed: false;
  connector_invocation_performed: false;
  knowledge_ingestion_performed: false;
  infrastructure_mutation_performed: false;
  ai_advice_generated: false;
};

type IntegrationPlanResponse = { data: BootstrapIntegrationPlan };
type IntegrationValidationResponse = { data: BootstrapIntegrationValidationResult };

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isIntegrationPlan(value: unknown): value is BootstrapIntegrationPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  const model = candidate.model_endpoint;
  return (
    candidate.schema_version === "atlas.bootstrap-integration-plan.v1" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.service_plan_digest === "string" &&
    typeof candidate.identity_plan_digest === "string" &&
    typeof candidate.integration_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
    typeof model === "object" &&
    model !== null &&
    typeof (model as Record<string, unknown>).endpoint_id === "string" &&
    (model as Record<string, unknown>).provider_type === "provider-type.openai-compatible" &&
    typeof (model as Record<string, unknown>).model_id === "string" &&
    typeof (model as Record<string, unknown>).context_limit === "number" &&
    typeof (model as Record<string, unknown>).output_limit === "number" &&
    isStringList((model as Record<string, unknown>).approved_task_class_ids) &&
    Array.isArray(candidate.integrations) &&
    candidate.integrations.length === 4 &&
    candidate.integrations.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const integration = item as Record<string, unknown>;
      return (
        typeof integration.integration_id === "string" &&
        typeof integration.integration_type === "string" &&
        typeof integration.validation_operation_id === "string" &&
        integration.activation_state === "inactive"
      );
    }) &&
    Array.isArray(candidate.checks) &&
    candidate.checks.length === 12 &&
    candidate.checks.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const check = item as Record<string, unknown>;
      return (
        typeof check.check_id === "string" &&
        typeof check.subject_id === "string" &&
        check.state === "passed" &&
        check.mandatory === true
      );
    }) &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    typeof candidate.generated_at === "string" &&
    candidate.actual_model_request_authorized === false &&
    candidate.network_request_authorized === false &&
    candidate.secret_resolution_authorized === false &&
    candidate.integration_activation_authorized === false &&
    candidate.connector_invocation_authorized === false &&
    candidate.infrastructure_mutation_authorized === false
  );
}

function isIntegrationPlanResponse(value: unknown): value is IntegrationPlanResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "data" in value &&
    isIntegrationPlan(value.data)
  );
}

function isIntegrationValidationResponse(
  value: unknown,
): value is IntegrationValidationResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isIntegrationExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.synthetic_state_mutation_performed === "boolean" &&
    candidate.actual_model_request_performed === false &&
    candidate.network_request_performed === false &&
    candidate.secret_resolution_performed === false &&
    candidate.integration_activation_performed === false &&
    candidate.connector_invocation_performed === false &&
    candidate.knowledge_ingestion_performed === false &&
    candidate.infrastructure_mutation_performed === false &&
    candidate.ai_advice_generated === false
  );
}

export async function previewBootstrapIntegrationPlan(
  configuration: DeploymentConfigurationPreview,
  trustPlan: BootstrapTrustPlan,
  dataPlan: BootstrapDataPlan,
  servicePlan: BootstrapServicePlan,
  identityPlan: BootstrapIdentityPlan,
  scope: CurrentIdentity["scope"],
): Promise<IntegrationPlanResponse> {
  const response = await apiFetch("/api/v1/platform/bootstrap-integration-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-integration-plan-request.v1",
      release_id: configuration.release_id,
      profile: configuration.profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: trustPlan.trust_plan_digest,
      data_plan_digest: dataPlan.data_plan_digest,
      migration_artifact_digest: dataPlan.migration_artifact_digest,
      service_plan_digest: servicePlan.service_plan_digest,
      identity_plan_digest: identityPlan.identity_plan_digest,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap integration plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isIntegrationPlanResponse(payload)) {
    throw new Error("Bootstrap integration plan returned malformed evidence");
  }
  return payload;
}

export async function validateBootstrapIntegrations(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  servicePlan: BootstrapServicePlan;
  identityPlan: BootstrapIdentityPlan;
  integrationPlan: BootstrapIntegrationPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<IntegrationValidationResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.integrations") {
    throw new Error("Integration validation requires the current integrations phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(
    `/api/v1/platform/bootstrap-state/${run.run_id}/phases/integrations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `bootstrap-integrations.${run.version}.${nonce}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.bootstrap-integration-validation.v1",
        organization_id: input.scope.organization_id,
        environment_id: input.scope.environment_id,
        site_id: input.scope.site_id,
        expected_version: run.version,
        plan_digest: run.plan_digest,
        resume_key: run.resume_key,
        phase_id: "phase.integrations",
        release_id: run.release_id,
        profile: run.profile,
        configuration_digest: input.configuration.configuration_digest,
        overlay: {},
        trust_plan_digest: input.trustPlan.trust_plan_digest,
        data_plan_digest: input.dataPlan.data_plan_digest,
        migration_artifact_digest: input.dataPlan.migration_artifact_digest,
        service_plan_digest: input.servicePlan.service_plan_digest,
        identity_plan_digest: input.identityPlan.identity_plan_digest,
        integration_schema_version: input.integrationPlan.schema_version,
        integration_plan_digest: input.integrationPlan.integration_plan_digest,
        target_id: input.integrationPlan.target_id,
        expected_target_state: input.integrationPlan.target_state,
        justification: input.justification,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Bootstrap integration validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isIntegrationValidationResponse(payload)) {
    throw new Error("Bootstrap integration validation returned malformed evidence");
  }
  return payload;
}
