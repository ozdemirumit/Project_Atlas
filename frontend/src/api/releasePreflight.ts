import { apiFetch } from "./client";

export type ReleasePreflightMode = "connected" | "mirrored" | "offline";
export type ReleasePreflightProfile = "developer" | "linux_lab";

export type ReleasePreflightCheck = {
  code: string;
  category: string;
  state: "passed" | "warning" | "failed" | "unchecked";
  mandatory: boolean;
  summary: string;
  evidence: string;
  remediation: string | null;
};

export type ReleasePreflight = {
  report_id: string;
  release_id: string;
  release_version: string;
  build_id: string;
  manifest_digest: string;
  mode: ReleasePreflightMode;
  profile: ReleasePreflightProfile;
  state: "passed" | "warning" | "failed" | "unchecked";
  checks: ReleasePreflightCheck[];
  generated_at: string;
  correlation_id: string;
  mutation_authorized: false;
  execution_authorized: false;
};

type ReleasePreflightResponse = { data: ReleasePreflight };

function isReleasePreflightResponse(value: unknown): value is ReleasePreflightResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  return (
    typeof data === "object" &&
    data !== null &&
    "checks" in data &&
    Array.isArray(data.checks) &&
    "manifest_digest" in data &&
    typeof data.manifest_digest === "string" &&
    "release_version" in data &&
    typeof data.release_version === "string" &&
    "build_id" in data &&
    typeof data.build_id === "string" &&
    "state" in data &&
    typeof data.state === "string"
  );
}

export async function getReleasePreflight(
  mode: ReleasePreflightMode,
  profile: ReleasePreflightProfile,
): Promise<ReleasePreflightResponse | null> {
  const params = new URLSearchParams({ mode, profile });
  const response = await apiFetch(`/api/v1/platform/release-preflight?${params}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 403) return null;
  if (!response.ok) throw new Error(`Release preflight failed with ${response.status}`);
  const payload: unknown = await response.json();
  return isReleasePreflightResponse(payload) ? payload : null;
}
