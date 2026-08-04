import {
  isArtifactExecution,
  isBootstrapRun,
  type BootstrapArtifactExecution,
  type BootstrapState,
} from "./bootstrapState";
import { apiFetch } from "./client";
import type { CurrentIdentity } from "./identity";
import type { ReleasePreflight } from "./releasePreflight";

export type BootstrapArtifactAcquisitionResult = {
  run: NonNullable<BootstrapState["run"]>;
  execution: BootstrapArtifactExecution;
  replayed: boolean;
  artifact_storage_mutation_performed: boolean;
  configuration_mutation_authorized: false;
  service_deployment_authorized: false;
  infrastructure_mutation_authorized: false;
  ai_operation_authorized: false;
};

type BootstrapArtifactAcquisitionResponse = {
  data: BootstrapArtifactAcquisitionResult;
};

function isResponse(value: unknown): value is BootstrapArtifactAcquisitionResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  const run = candidate.run;
  const execution = candidate.execution;
  if (typeof run !== "object" || run === null || typeof execution !== "object" || execution === null) {
    return false;
  }
  return (
    isBootstrapRun(run) &&
    isArtifactExecution(execution) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.artifact_storage_mutation_performed === "boolean" &&
    candidate.configuration_mutation_authorized === false &&
    candidate.service_deployment_authorized === false &&
    candidate.infrastructure_mutation_authorized === false &&
    candidate.ai_operation_authorized === false
  );
}

export async function acquireBootstrapArtifacts(input: {
  state: BootstrapState;
  preflight: ReleasePreflight;
  scope: CurrentIdentity["scope"];
  justification: string;
  warningAccepted: boolean;
}): Promise<BootstrapArtifactAcquisitionResponse> {
  const run = input.state.run;
  if (!run || run.current_phase_id !== "phase.acquire") {
    throw new Error("Artifact acquisition requires the current acquire phase");
  }
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const idempotencyKey = `bootstrap-acquire.${run.version}.${nonce}`;
  const response = await apiFetch(
    `/api/v1/platform/bootstrap-state/${run.run_id}/phases/acquire`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({
        schema_version: "atlas.bootstrap-artifact-acquisition.v1",
        organization_id: input.scope.organization_id,
        environment_id: input.scope.environment_id,
        site_id: input.scope.site_id,
        expected_version: run.version,
        plan_digest: run.plan_digest,
        resume_key: run.resume_key,
        phase_id: "phase.acquire",
        release_id: run.release_id,
        manifest_digest: input.preflight.manifest_digest,
        mode: input.preflight.mode,
        profile: input.preflight.profile,
        preflight_report_id: input.preflight.report_id,
        preflight_state: input.preflight.state,
        warning_accepted: input.warningAccepted,
        justification: input.justification,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Bootstrap artifact acquisition failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isResponse(payload)) {
    throw new Error("Bootstrap artifact acquisition returned malformed evidence");
  }
  return payload;
}
