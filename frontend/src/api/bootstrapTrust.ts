import {
  isBootstrapRun,
  isTrustExecution,
  type BootstrapState,
  type BootstrapTrustExecution,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapTrustPlan = {
  schema_version: "atlas.bootstrap-trust-plan.v1";
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  configuration_digest: string;
  trust_plan_digest: string;
  state: "passed";
  result_code: string;
  anchors: Array<{
    anchor_id: string;
    source_id: string;
    purpose: string;
    subject_summary: string;
    sha256: string;
    not_before: string;
    not_after: string;
    non_production_only: boolean;
  }>;
  workload_identities: Array<{
    identity_id: string;
    service_id: string;
    instance_id: string;
    owner_subject_id: string;
    purpose: string;
    environment_id: string;
    audiences: string[];
    secret_reference_ids: string[];
  }>;
  generated_at: string;
  private_key_material_present: false;
  credential_material_present: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

export type BootstrapTrustProvisioningResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapTrustExecution;
  replayed: boolean;
  trust_storage_mutation_performed: boolean;
  private_key_mutation_performed: false;
  secret_value_mutation_performed: false;
  data_mutation_authorized: false;
  service_deployment_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

type TrustPlanResponse = { data: BootstrapTrustPlan };
type TrustProvisioningResponse = { data: BootstrapTrustProvisioningResult };

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isTrustPlan(value: unknown): value is BootstrapTrustPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-trust-plan.v1" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    Array.isArray(candidate.anchors) &&
    candidate.anchors.length > 0 &&
    candidate.anchors.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const anchor = item as Record<string, unknown>;
      return (
        typeof anchor.anchor_id === "string" &&
        typeof anchor.source_id === "string" &&
        typeof anchor.purpose === "string" &&
        typeof anchor.subject_summary === "string" &&
        typeof anchor.sha256 === "string" &&
        typeof anchor.not_before === "string" &&
        typeof anchor.not_after === "string" &&
        typeof anchor.non_production_only === "boolean"
      );
    }) &&
    Array.isArray(candidate.workload_identities) &&
    candidate.workload_identities.length > 0 &&
    candidate.workload_identities.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const identity = item as Record<string, unknown>;
      return (
        typeof identity.identity_id === "string" &&
        typeof identity.service_id === "string" &&
        typeof identity.instance_id === "string" &&
        typeof identity.owner_subject_id === "string" &&
        typeof identity.purpose === "string" &&
        typeof identity.environment_id === "string" &&
        isStringArray(identity.audiences) &&
        isStringArray(identity.secret_reference_ids)
      );
    }) &&
    typeof candidate.generated_at === "string" &&
    candidate.private_key_material_present === false &&
    candidate.credential_material_present === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

function isTrustPlanResponse(value: unknown): value is TrustPlanResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "data" in value &&
    isTrustPlan(value.data)
  );
}

function isProvisioningResponse(value: unknown): value is TrustProvisioningResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isTrustExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.trust_storage_mutation_performed === "boolean" &&
    candidate.private_key_mutation_performed === false &&
    candidate.secret_value_mutation_performed === false &&
    candidate.data_mutation_authorized === false &&
    candidate.service_deployment_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

export async function previewBootstrapTrustPlan(
  configuration: DeploymentConfigurationPreview,
  scope: CurrentIdentity["scope"],
): Promise<TrustPlanResponse> {
  const response = await apiFetch("/api/v1/platform/bootstrap-trust-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-trust-plan-request.v1",
      release_id: configuration.release_id,
      profile: configuration.profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap trust plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isTrustPlanResponse(payload)) {
    throw new Error("Bootstrap trust plan returned malformed evidence");
  }
  return payload;
}

export async function provisionBootstrapTrust(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<TrustProvisioningResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.trust") {
    throw new Error("Trust provisioning requires the current trust phase");
  }
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/phases/trust`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-trust.${run.version}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-trust-provisioning.v1",
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.trust",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: input.configuration.configuration_digest,
      overlay: {},
      trust_schema_version: input.trustPlan.schema_version,
      trust_plan_digest: input.trustPlan.trust_plan_digest,
      justification: input.justification,
    }),
  });
  if (!response.ok) {
    throw new Error(`Bootstrap trust provisioning failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isProvisioningResponse(payload)) {
    throw new Error("Bootstrap trust provisioning returned malformed evidence");
  }
  return payload;
}
