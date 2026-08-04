import type { BootstrapPlan } from "./bootstrapPlan";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";
import { apiFetch } from "./client";

export type BootstrapInvalidationPreview = {
  preview_id: string;
  schema_version: string;
  state: "empty" | "unchanged" | "drifted";
  source_run_id: string | null;
  source_run_version: number | null;
  changes: Array<{
    field: string;
    reason_code: string;
    old_reference: string;
    new_reference: string;
    earliest_affected_phase_id: string;
  }>;
  earliest_affected_phase_id: string | null;
  reusable_checkpoint_phase_ids: string[];
  invalidated_checkpoint_phase_ids: string[];
  downstream_phase_ids: string[];
  remediation: string | null;
  generated_at: string;
  correlation_id: string;
  execution_authorized: false;
  lease_mutation_authorized: false;
  checkpoint_mutation_authorized: false;
  infrastructure_mutation_authorized: false;
};

type BootstrapInvalidationResponse = { data: BootstrapInvalidationPreview };

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isChange(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.field === "string" &&
    typeof item.reason_code === "string" &&
    typeof item.old_reference === "string" &&
    typeof item.new_reference === "string" &&
    typeof item.earliest_affected_phase_id === "string"
  );
}

function isPreviewResponse(value: unknown): value is BootstrapInvalidationResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const item = data as Record<string, unknown>;
  return (
    (item.state === "empty" || item.state === "unchanged" || item.state === "drifted") &&
    (item.source_run_id === null || typeof item.source_run_id === "string") &&
    (item.source_run_version === null || typeof item.source_run_version === "number") &&
    Array.isArray(item.changes) &&
    item.changes.every(isChange) &&
    (item.earliest_affected_phase_id === null ||
      typeof item.earliest_affected_phase_id === "string") &&
    isStringArray(item.reusable_checkpoint_phase_ids) &&
    isStringArray(item.invalidated_checkpoint_phase_ids) &&
    isStringArray(item.downstream_phase_ids) &&
    item.execution_authorized === false &&
    item.lease_mutation_authorized === false &&
    item.checkpoint_mutation_authorized === false &&
    item.infrastructure_mutation_authorized === false
  );
}

export async function previewBootstrapInvalidation(
  plan: BootstrapPlan,
  configuration: DeploymentConfigurationPreview,
  scope: CurrentIdentity["scope"],
): Promise<BootstrapInvalidationResponse | null> {
  const response = await apiFetch("/api/v1/platform/bootstrap-invalidation-preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-invalidation-request.v1",
      release_id: plan.release_id,
      profile: plan.profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      plan_digest: plan.plan_digest,
      resume_key: plan.resume_key,
      configuration_digest: configuration.configuration_digest,
      phase_ids: plan.phases.map((phase) => phase.phase_id),
    }),
  });
  if (response.status === 403 || response.status === 404) return null;
  if (!response.ok) throw new Error(`Bootstrap invalidation preview failed with ${response.status}`);
  const payload: unknown = await response.json();
  return isPreviewResponse(payload) ? payload : null;
}
