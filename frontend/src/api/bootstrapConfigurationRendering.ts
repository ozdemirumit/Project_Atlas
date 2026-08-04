import {
  isBootstrapRun,
  isConfigurationExecution,
  type BootstrapConfigurationExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapConfigurationRenderingResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapConfigurationExecution;
  replayed: boolean;
  configuration_storage_mutation_performed: boolean;
  trust_mutation_authorized: false;
  secret_mutation_authorized: false;
  data_mutation_authorized: false;
  service_deployment_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

type BootstrapConfigurationRenderingResponse = {
  data: BootstrapConfigurationRenderingResult;
};

function isResponse(value: unknown): value is BootstrapConfigurationRenderingResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    isConfigurationExecution(candidate.execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.configuration_storage_mutation_performed === "boolean" &&
    candidate.trust_mutation_authorized === false &&
    candidate.secret_mutation_authorized === false &&
    candidate.data_mutation_authorized === false &&
    candidate.service_deployment_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

export async function renderBootstrapConfiguration(input: {
  state: BootstrapState;
  configuration: DeploymentConfigurationPreview;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<BootstrapConfigurationRenderingResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.configure") {
    throw new Error("Configuration rendering requires the current configure phase");
  }
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(
    `/api/v1/platform/bootstrap-state/${run.run_id}/phases/configure`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `bootstrap-configure.${run.version}.${nonce}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.bootstrap-configuration-rendering.v1",
        organization_id: input.scope.organization_id,
        environment_id: input.scope.environment_id,
        site_id: input.scope.site_id,
        expected_version: run.version,
        plan_digest: run.plan_digest,
        resume_key: run.resume_key,
        phase_id: "phase.configure",
        release_id: run.release_id,
        profile: run.profile,
        configuration_schema_version: "atlas.deployment-configuration.v1",
        configuration_digest: input.configuration.configuration_digest,
        overlay: {},
        justification: input.justification,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Bootstrap configuration rendering failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isResponse(payload)) {
    throw new Error("Bootstrap configuration rendering returned malformed evidence");
  }
  return payload;
}
