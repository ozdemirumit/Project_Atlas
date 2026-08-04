import type { BootstrapInvalidationPreview } from "./bootstrapInvalidation";
import type { BootstrapPlan } from "./bootstrapPlan";
import type { BootstrapState } from "./bootstrapState";
import { apiFetch } from "./client";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapRebaseResult = {
  run: {
    run_id: string;
    version: number;
    state: "active" | "failed" | "completed";
    completed_phase_ids: string[];
    current_phase_id: string | null;
  };
  replayed: boolean;
  preserved_checkpoint_phase_ids: string[];
  invalidated_checkpoint_phase_ids: string[];
  invalidation_reason_codes: string[];
  earliest_affected_phase_id: string;
  execution_authorized: false;
  lease_mutation_authorized: false;
  infrastructure_mutation_authorized: false;
};

type BootstrapRebaseResponse = { data: BootstrapRebaseResult };

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isRebaseResponse(value: unknown): value is BootstrapRebaseResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  const run = candidate.run;
  if (typeof run !== "object" || run === null) return false;
  const runData = run as Record<string, unknown>;
  return (
    typeof runData.run_id === "string" &&
    typeof runData.version === "number" &&
    (runData.state === "active" || runData.state === "failed" || runData.state === "completed") &&
    isStringArray(runData.completed_phase_ids) &&
    (runData.current_phase_id === null || typeof runData.current_phase_id === "string") &&
    typeof candidate.replayed === "boolean" &&
    isStringArray(candidate.preserved_checkpoint_phase_ids) &&
    isStringArray(candidate.invalidated_checkpoint_phase_ids) &&
    isStringArray(candidate.invalidation_reason_codes) &&
    typeof candidate.earliest_affected_phase_id === "string" &&
    candidate.execution_authorized === false &&
    candidate.lease_mutation_authorized === false &&
    candidate.infrastructure_mutation_authorized === false
  );
}

export async function rebaseBootstrapPlan(input: {
  state: BootstrapState;
  preview: BootstrapInvalidationPreview;
  plan: BootstrapPlan;
  configuration: DeploymentConfigurationPreview;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<BootstrapRebaseResponse> {
  const run = input.state.run;
  if (!run || input.preview.source_run_version === null) {
    throw new Error("Bootstrap rebase requires current reviewed state");
  }
  const idempotencyKey = [
    "bootstrap-rebase",
    run.version,
    input.preview.source_run_version,
    input.plan.plan_digest.slice(0, 24),
  ].join(".");
  const response = await apiFetch(`/api/v1/platform/bootstrap-state/${run.run_id}/rebase`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-rebase.v1",
      release_id: input.plan.release_id,
      profile: input.plan.profile,
      organization_id: input.scope.organization_id,
      environment_id: input.scope.environment_id,
      site_id: input.scope.site_id,
      plan_digest: input.plan.plan_digest,
      resume_key: input.plan.resume_key,
      configuration_digest: input.configuration.configuration_digest,
      phase_ids: input.plan.phases.map((phase) => phase.phase_id),
      expected_version: run.version,
      preview_source_version: input.preview.source_run_version,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap rebase failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isRebaseResponse(payload)) throw new Error("Bootstrap rebase returned malformed evidence");
  return payload;
}
