import {
  isBootstrapRun,
  isIdentityExecution,
  type BootstrapIdentityExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { BootstrapDataPlan } from "./bootstrapData";
import type { BootstrapServicePlan } from "./bootstrapServices";
import type { BootstrapTrustPlan } from "./bootstrapTrust";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapIdentityPlan = {
  schema_version: "atlas.bootstrap-identity-plan.v1";
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
  target_id: string;
  target_kind: string;
  target_state: "empty" | "reusable";
  bootstrap_administrator_subject_id: string;
  credential_verifier_reference_id: string;
  credential_replacement_required: true;
  recovery_identity_id: string;
  recovery_seal_required: true;
  provider_id: string;
  provider_protocol: "ldaps";
  pilot_subject_id: string;
  group_mappings: Array<{
    mapping_id: string;
    directory_group_reference: string;
    role_ids: string[];
  }>;
  state: "passed";
  result_code: string;
  generated_at: string;
  credential_material_present: false;
  directory_mutation_authorized: false;
  provider_activation_authorized: false;
  account_mutation_authorized: false;
  session_or_token_mutation_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

export type BootstrapIdentityHandoffResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapIdentityExecution;
  replayed: boolean;
  synthetic_state_mutation_performed: boolean;
  credential_material_mutation_performed: false;
  directory_mutation_performed: false;
  provider_activation_performed: false;
  account_mutation_performed: false;
  session_or_token_mutation_performed: false;
  infrastructure_mutation_performed: false;
  ai_operation_performed: false;
};

type IdentityPlanResponse = { data: BootstrapIdentityPlan };
type IdentityHandoffResponse = { data: BootstrapIdentityHandoffResult };

function isIdentityPlan(value: unknown): value is BootstrapIdentityPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-identity-plan.v1" &&
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
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
    typeof candidate.bootstrap_administrator_subject_id === "string" &&
    typeof candidate.credential_verifier_reference_id === "string" &&
    candidate.credential_replacement_required === true &&
    typeof candidate.recovery_identity_id === "string" &&
    candidate.recovery_seal_required === true &&
    typeof candidate.provider_id === "string" &&
    candidate.provider_protocol === "ldaps" &&
    typeof candidate.pilot_subject_id === "string" &&
    Array.isArray(candidate.group_mappings) &&
    candidate.group_mappings.length > 0 &&
    candidate.group_mappings.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const mapping = item as Record<string, unknown>;
      return (
        typeof mapping.mapping_id === "string" &&
        typeof mapping.directory_group_reference === "string" &&
        Array.isArray(mapping.role_ids) &&
        mapping.role_ids.length > 0 &&
        mapping.role_ids.every((role) => typeof role === "string")
      );
    }) &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    typeof candidate.generated_at === "string" &&
    candidate.credential_material_present === false &&
    candidate.directory_mutation_authorized === false &&
    candidate.provider_activation_authorized === false &&
    candidate.account_mutation_authorized === false &&
    candidate.session_or_token_mutation_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

function isIdentityPlanResponse(value: unknown): value is IdentityPlanResponse {
  return typeof value === "object" && value !== null && "data" in value && isIdentityPlan(value.data);
}

function isIdentityHandoffResponse(value: unknown): value is IdentityHandoffResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isIdentityExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.synthetic_state_mutation_performed === "boolean" &&
    candidate.credential_material_mutation_performed === false &&
    candidate.directory_mutation_performed === false &&
    candidate.provider_activation_performed === false &&
    candidate.account_mutation_performed === false &&
    candidate.session_or_token_mutation_performed === false &&
    candidate.infrastructure_mutation_performed === false &&
    candidate.ai_operation_performed === false
  );
}

export async function previewBootstrapIdentityPlan(
  configuration: DeploymentConfigurationPreview,
  trustPlan: BootstrapTrustPlan,
  dataPlan: BootstrapDataPlan,
  servicePlan: BootstrapServicePlan,
  scope: CurrentIdentity["scope"],
): Promise<IdentityPlanResponse> {
  const response = await apiFetch("/api/v1/platform/bootstrap-identity-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-identity-plan-request.v1",
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
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap identity plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isIdentityPlanResponse(payload)) {
    throw new Error("Bootstrap identity plan returned malformed evidence");
  }
  return payload;
}

export async function handoffBootstrapIdentity(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  servicePlan: BootstrapServicePlan;
  identityPlan: BootstrapIdentityPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<IdentityHandoffResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.identity") {
    throw new Error("Identity handoff requires the current identity phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/phases/identity`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-identity.${run.version}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-identity-handoff.v1",
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.identity",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: input.configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: input.trustPlan.trust_plan_digest,
      data_plan_digest: input.dataPlan.data_plan_digest,
      migration_artifact_digest: input.dataPlan.migration_artifact_digest,
      service_plan_digest: input.servicePlan.service_plan_digest,
      identity_schema_version: input.identityPlan.schema_version,
      identity_plan_digest: input.identityPlan.identity_plan_digest,
      target_id: input.identityPlan.target_id,
      expected_target_state: input.identityPlan.target_state,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap identity handoff failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isIdentityHandoffResponse(payload)) {
    throw new Error("Bootstrap identity handoff returned malformed evidence");
  }
  return payload;
}
