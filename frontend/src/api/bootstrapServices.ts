import {
  isBootstrapRun,
  isServiceExecution,
  type BootstrapServiceExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { BootstrapDataPlan } from "./bootstrapData";
import type { BootstrapTrustPlan } from "./bootstrapTrust";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapServicePlan = {
  schema_version: "atlas.bootstrap-service-plan.v1";
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  migration_artifact_digest: string;
  service_plan_digest: string;
  target_id: string;
  target_kind: string;
  target_state: "empty" | "reusable";
  state: "passed";
  result_code: string;
  services: Array<{
    service_id: string;
    sequence: number;
    artifact_id: string;
    artifact_sha256: string;
    dependencies: string[];
    workload_identity_id: string | null;
    endpoint_class: "private";
    cpu_limit_millicores: number;
    memory_limit_mb: number;
    startup_probe_id: string;
    readiness_probe_id: string;
    liveness_probe_id: string;
    run_as_root: false;
    privileged: false;
    arbitrary_public_egress: false;
  }>;
  generated_at: string;
  real_process_mutation_authorized: false;
  container_runtime_mutation_authorized: false;
  operating_system_service_mutation_authorized: false;
  network_mutation_authorized: false;
  secret_mutation_authorized: false;
  external_data_mutation_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

export type BootstrapServiceDeploymentResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapServiceExecution;
  replayed: boolean;
  synthetic_state_mutation_performed: boolean;
  real_process_mutation_performed: false;
  container_runtime_mutation_performed: false;
  operating_system_service_mutation_performed: false;
  port_or_network_mutation_performed: false;
  secret_mutation_performed: false;
  external_data_mutation_performed: false;
  infrastructure_mutation_performed: false;
  ai_operation_performed: false;
};

type ServicePlanResponse = { data: BootstrapServicePlan };
type ServiceDeploymentResponse = { data: BootstrapServiceDeploymentResult };

function isServicePlan(value: unknown): value is BootstrapServicePlan {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === "atlas.bootstrap-service-plan.v1" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.migration_artifact_digest === "string" &&
    typeof candidate.service_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.target_kind === "string" &&
    (candidate.target_state === "empty" || candidate.target_state === "reusable") &&
    candidate.state === "passed" &&
    typeof candidate.result_code === "string" &&
    Array.isArray(candidate.services) &&
    candidate.services.length > 0 &&
    candidate.services.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const service = item as Record<string, unknown>;
      return (
        typeof service.service_id === "string" &&
        typeof service.sequence === "number" &&
        typeof service.artifact_id === "string" &&
        typeof service.artifact_sha256 === "string" &&
        Array.isArray(service.dependencies) &&
        service.dependencies.every((dependency) => typeof dependency === "string") &&
        (service.workload_identity_id === null ||
          typeof service.workload_identity_id === "string") &&
        service.endpoint_class === "private" &&
        typeof service.cpu_limit_millicores === "number" &&
        typeof service.memory_limit_mb === "number" &&
        typeof service.startup_probe_id === "string" &&
        typeof service.readiness_probe_id === "string" &&
        typeof service.liveness_probe_id === "string" &&
        service.run_as_root === false &&
        service.privileged === false &&
        service.arbitrary_public_egress === false
      );
    }) &&
    typeof candidate.generated_at === "string" &&
    candidate.real_process_mutation_authorized === false &&
    candidate.container_runtime_mutation_authorized === false &&
    candidate.operating_system_service_mutation_authorized === false &&
    candidate.network_mutation_authorized === false &&
    candidate.secret_mutation_authorized === false &&
    candidate.external_data_mutation_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

function isServicePlanResponse(value: unknown): value is ServicePlanResponse {
  return typeof value === "object" && value !== null && "data" in value && isServicePlan(value.data);
}

function isServiceDeploymentResponse(value: unknown): value is ServiceDeploymentResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isServiceExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.synthetic_state_mutation_performed === "boolean" &&
    candidate.real_process_mutation_performed === false &&
    candidate.container_runtime_mutation_performed === false &&
    candidate.operating_system_service_mutation_performed === false &&
    candidate.port_or_network_mutation_performed === false &&
    candidate.secret_mutation_performed === false &&
    candidate.external_data_mutation_performed === false &&
    candidate.infrastructure_mutation_performed === false &&
    candidate.ai_operation_performed === false
  );
}

export async function previewBootstrapServicePlan(
  configuration: DeploymentConfigurationPreview,
  trustPlan: BootstrapTrustPlan,
  dataPlan: BootstrapDataPlan,
  scope: CurrentIdentity["scope"],
): Promise<ServicePlanResponse> {
  const response = await apiFetch("/api/v1/platform/bootstrap-service-plan/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-service-plan-request.v1",
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
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap service plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isServicePlanResponse(payload)) {
    throw new Error("Bootstrap service plan returned malformed evidence");
  }
  return payload;
}

export async function deployBootstrapServices(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  trustPlan: BootstrapTrustPlan;
  dataPlan: BootstrapDataPlan;
  servicePlan: BootstrapServicePlan;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<ServiceDeploymentResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.services") {
    throw new Error("Service deployment requires the current services phase");
  }
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(
    `/api/v1/platform/bootstrap-state/${run.run_id}/phases/services`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `bootstrap-services.${run.version}.${nonce}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.bootstrap-service-deployment.v1",
        organization_id: input.scope.organization_id,
        environment_id: input.scope.environment_id,
        site_id: input.scope.site_id,
        expected_version: run.version,
        plan_digest: run.plan_digest,
        resume_key: run.resume_key,
        phase_id: "phase.services",
        release_id: run.release_id,
        profile: run.profile,
        configuration_digest: input.configuration.configuration_digest,
        overlay: {},
        trust_plan_digest: input.trustPlan.trust_plan_digest,
        data_plan_digest: input.dataPlan.data_plan_digest,
        migration_artifact_digest: input.dataPlan.migration_artifact_digest,
        service_schema_version: input.servicePlan.schema_version,
        service_plan_digest: input.servicePlan.service_plan_digest,
        target_id: input.servicePlan.target_id,
        expected_target_state: input.servicePlan.target_state,
        justification: input.justification,
      }),
    },
  );
  if (!response.ok) throw new Error(`Bootstrap service deployment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isServiceDeploymentResponse(payload)) {
    throw new Error("Bootstrap service deployment returned malformed evidence");
  }
  return payload;
}
