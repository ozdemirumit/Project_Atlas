import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";
import type { ReleasePreflight } from "./releasePreflight";
import { apiFetch } from "./client";

export type BootstrapPlan = {
  plan_id: string;
  schema_version: string;
  release_id: string;
  profile: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  state: "ready" | "blocked";
  plan_digest: string;
  resume_key: string;
  phases: Array<{
    phase_id: string;
    sequence: number;
    title: string;
    dependencies: string[];
    state: "ready" | "blocked";
    resumable: boolean;
    input_references: string[];
    stop_guidance: string;
  }>;
  generated_at: string;
  correlation_id: string;
  mutation_authorized: false;
  execution_authorized: false;
};

type BootstrapPlanResponse = { data: BootstrapPlan };

function isPlanResponse(value: unknown): value is BootstrapPlanResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  return typeof data === "object" && data !== null && "phases" in data && Array.isArray(data.phases) && "plan_digest" in data && typeof data.plan_digest === "string" && "state" in data && (data.state === "ready" || data.state === "blocked");
}

export async function getBootstrapPlan(
  preflight: ReleasePreflight,
  configuration: DeploymentConfigurationPreview,
  scope: CurrentIdentity["scope"],
): Promise<BootstrapPlanResponse | null> {
  const response = await apiFetch("/api/v1/platform/bootstrap-plan", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-plan-request.v1",
      release_id: preflight.release_id,
      profile: preflight.profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      preflight_report_id: preflight.report_id,
      manifest_digest: preflight.manifest_digest,
      preflight_state: preflight.state,
      configuration_preview_id: configuration.preview_id,
      configuration_digest: configuration.configuration_digest,
      configuration_state: configuration.state,
    }),
  });
  if (response.status === 403) return null;
  if (!response.ok) throw new Error(`Bootstrap plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  return isPlanResponse(payload) ? payload : null;
}
