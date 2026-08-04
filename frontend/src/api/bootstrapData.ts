import {
  isBootstrapRun,
  isDataExecution,
  type BootstrapDataExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";
import type { BootstrapTrustPlan } from "./bootstrapTrust";

export type BootstrapDataPlan = {
  schema_version: "atlas.bootstrap-data-plan.v1";
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  configuration_digest: string;
  trust_plan_digest: string;
  migration_artifact_digest: string;
  data_plan_digest: string;
  target_id: string;
  target_kind: string;
  current_revision: string;
  target_revision: string;
  target_state: "empty" | "reusable";
  state: "passed";
  result_code: string;
  migrations: Array<{
    migration_id: string;
    sequence: number;
    sha256: string;
    from_revision: string;
    to_revision: string;
    compatibility: "expand";
    reversible: true;
    destructive: false;
    recovery_code: string;
    expected_object_count: number;
  }>;
  backup_applicability: "not_applicable_clean_install";
  generated_at: string;
  database_url_present: false;
  credential_material_present: false;
  sql_text_present: false;
  destructive_migration_authorized: false;
  backup_operation_authorized: false;
  service_deployment_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

export type BootstrapDataInitializationResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapDataExecution;
  replayed: boolean;
  schema_state_mutation_performed: boolean;
  external_database_provisioning_performed: false;
  destructive_migration_performed: false;
  backup_operation_performed: false;
  service_deployment_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

type DataPlanResponse = { data: BootstrapDataPlan };
type DataInitializationResponse = { data: BootstrapDataInitializationResult };

function isDataPlan(value: unknown): value is BootstrapDataPlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-data-plan.v1" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.migration_artifact_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    typeof candidate.current_revision === "string" &&
    typeof candidate.target_revision === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    Array.isArray(candidate.migrations) &&
    candidate.migrations.length > 0 &&
    candidate.migrations.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const migration = item as Record<string, unknown>;
      return (
        typeof migration.migration_id === "string" &&
        typeof migration.sequence === "number" &&
        typeof migration.sha256 === "string" &&
        typeof migration.from_revision === "string" &&
        typeof migration.to_revision === "string" &&
        migration.compatibility === "expand" &&
        migration.reversible === true &&
        migration.destructive === false &&
        typeof migration.recovery_code === "string" &&
        typeof migration.expected_object_count === "number"
      );
    }) &&
    candidate.backup_applicability === "not_applicable_clean_install" &&
    typeof candidate.generated_at === "string" &&
    candidate.database_url_present === false &&
    candidate.credential_material_present === false &&
    candidate.sql_text_present === false &&
    candidate.destructive_migration_authorized === false &&
    candidate.backup_operation_authorized === false &&
    candidate.service_deployment_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

function isDataPlanResponse(value: unknown): value is DataPlanResponse {
  return typeof value === "object" && value !== null && "data" in value && isDataPlan(value.data);
}

function isDataInitializationResponse(value: unknown): value is DataInitializationResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isDataExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.schema_state_mutation_performed === "boolean" &&
    candidate.external_database_provisioning_performed === false &&
    candidate.destructive_migration_performed === false &&
    candidate.backup_operation_performed === false &&
    candidate.service_deployment_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

export async function previewBootstrapDataPlan(
  configuration: DeploymentConfigurationPreview,
  trustPlan: BootstrapTrustPlan,
  scope: CurrentIdentity["scope"],
): Promise<DataPlanResponse> {
  const response = await apiFetch("/api/v1/platform/bootstrap-data-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-data-plan-request.v1",
      release_id: configuration.release_id,
      profile: configuration.profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: trustPlan.trust_plan_digest,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap data plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isDataPlanResponse(payload)) throw new Error("Bootstrap data plan returned malformed evidence");
  return payload;
}

export async function initializeBootstrapData(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<DataInitializationResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.data") {
    throw new Error("Data initialization requires the current data phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/phases/data`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-data.${run.version}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-data-initialization.v1",
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.data",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: input.configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: input.trustPlan.trust_plan_digest,
      data_schema_version: input.dataPlan.schema_version,
      data_plan_digest: input.dataPlan.data_plan_digest,
      migration_artifact_digest: input.dataPlan.migration_artifact_digest,
      target_id: input.dataPlan.target_id,
      expected_target_state: input.dataPlan.target_state,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap data initialization failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isDataInitializationResponse(payload)) {
    throw new Error("Bootstrap data initialization returned malformed evidence");
  }
  return payload;
}
