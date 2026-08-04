import { apiFetch } from "./client";
import type { CurrentIdentity } from "./identity";
import type { ReleasePreflightProfile } from "./releasePreflight";

export type ConfigurationValidation = {
  code: string;
  state: "passed" | "failed";
  summary: string;
  evidence: string;
  remediation: string | null;
};

export type EffectiveConfigurationField = {
  path: string;
  display_value: string;
  source: "release_default" | "overlay";
  sensitive: boolean;
};

export type DeploymentConfigurationPreview = {
  preview_id: string;
  schema_version: string;
  release_id: string;
  profile: ReleasePreflightProfile;
  organization_id: string;
  environment_id: string;
  site_id: string;
  state: "passed" | "failed";
  configuration_digest: string;
  fields: EffectiveConfigurationField[];
  validations: ConfigurationValidation[];
  generated_at: string;
  correlation_id: string;
  mutation_authorized: false;
  execution_authorized: false;
};

type DeploymentConfigurationPreviewResponse = { data: DeploymentConfigurationPreview };

function isPreviewResponse(value: unknown): value is DeploymentConfigurationPreviewResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  return (
    typeof data === "object" &&
    data !== null &&
    "configuration_digest" in data &&
    typeof data.configuration_digest === "string" &&
    "fields" in data &&
    Array.isArray(data.fields) &&
    "validations" in data &&
    Array.isArray(data.validations) &&
    "state" in data &&
    (data.state === "passed" || data.state === "failed")
  );
}

export async function previewDeploymentConfiguration(
  profile: ReleasePreflightProfile,
  scope: CurrentIdentity["scope"],
): Promise<DeploymentConfigurationPreviewResponse | null> {
  const response = await apiFetch("/api/v1/platform/deployment-configuration/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.deployment-configuration-request.v1",
      release_id: "release.atlas.lab-0.1.0",
      profile,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      overlay: {},
    }),
  });
  if (response.status === 403) return null;
  if (!response.ok) {
    throw new Error(`Deployment configuration preview failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  return isPreviewResponse(payload) ? payload : null;
}
