import { apiFetch } from "./client";

export type BootstrapState = {
  run: null | {
    run_id: string;
    version: number;
    state: "active" | "failed" | "completed";
    release_id: string;
    profile: string;
    organization_id: string;
    environment_id: string;
    site_id: string;
    plan_digest: string;
    resume_key: string;
    configuration_digest: string;
    phase_ids: string[];
    checkpoints: Array<{
      phase_id: string;
      state: "completed" | "failed";
      safe_output_references: string[];
      recorded_at: string;
    }>;
    completed_phase_ids: string[];
    failed_phase_id: string | null;
    current_phase_id: string | null;
    lease_expires_at: string | null;
    created_at: string;
    updated_at: string;
    artifact_acquisition: BootstrapArtifactExecution | null;
    configuration_rendering: BootstrapConfigurationExecution | null;
  };
  durable: boolean;
  lease_available: boolean;
  lease_held_by_current_actor: boolean;
  execution_authorized: false;
  infrastructure_mutation_authorized: false;
};

export type BootstrapArtifactExecution = {
  execution_id: string;
  phase_id: "phase.acquire";
  release_id: string;
  manifest_digest: string;
  mode: "connected" | "mirrored" | "offline";
  preflight_report_id: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  evidence: Array<{
    artifact_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
  artifact_count: number;
  total_bytes: number;
};

export type BootstrapConfigurationExecution = {
  execution_id: string;
  phase_id: "phase.configure";
  release_id: string;
  profile: string;
  configuration_schema_version: "atlas.deployment-configuration.v1";
  configuration_digest: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  evidence: Array<{
    file_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
  file_count: number;
  total_bytes: number;
};

type BootstrapStateResponse = { data: BootstrapState };

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isCheckpoint(value: unknown): value is NonNullable<BootstrapState["run"]>["checkpoints"][number] {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.phase_id === "string" &&
    (candidate.state === "completed" || candidate.state === "failed") &&
    isStringArray(candidate.safe_output_references) &&
    typeof candidate.recorded_at === "string"
  );
}

export function isArtifactExecution(value: unknown): value is BootstrapArtifactExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.acquire" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.manifest_digest === "string" &&
    (candidate.mode === "connected" || candidate.mode === "mirrored" || candidate.mode === "offline") &&
    typeof candidate.preflight_report_id === "string" &&
    (candidate.state === "running" || candidate.state === "completed" || candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.artifact_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    }) &&
    typeof candidate.artifact_count === "number" &&
    typeof candidate.total_bytes === "number"
  );
}

export function isConfigurationExecution(
  value: unknown,
): value is BootstrapConfigurationExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.configure" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    candidate.configuration_schema_version === "atlas.deployment-configuration.v1" &&
    typeof candidate.configuration_digest === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.file_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    }) &&
    typeof candidate.file_count === "number" &&
    typeof candidate.total_bytes === "number"
  );
}

export function isBootstrapRun(value: unknown): value is NonNullable<BootstrapState["run"]> {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.run_id === "string" &&
    typeof candidate.version === "number" &&
    (candidate.state === "active" ||
      candidate.state === "failed" ||
      candidate.state === "completed") &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.environment_id === "string" &&
    typeof candidate.site_id === "string" &&
    typeof candidate.plan_digest === "string" &&
    typeof candidate.resume_key === "string" &&
    typeof candidate.configuration_digest === "string" &&
    isStringArray(candidate.phase_ids) &&
    isStringArray(candidate.completed_phase_ids) &&
    Array.isArray(candidate.checkpoints) &&
    candidate.checkpoints.every(isCheckpoint) &&
    (candidate.current_phase_id === null || typeof candidate.current_phase_id === "string") &&
    (candidate.failed_phase_id === null || typeof candidate.failed_phase_id === "string") &&
    (candidate.lease_expires_at === null || typeof candidate.lease_expires_at === "string") &&
    typeof candidate.created_at === "string" &&
    typeof candidate.updated_at === "string" &&
    (candidate.artifact_acquisition === null ||
      isArtifactExecution(candidate.artifact_acquisition)) &&
    (candidate.configuration_rendering === null ||
      isConfigurationExecution(candidate.configuration_rendering))
  );
}

function isBootstrapStateResponse(value: unknown): value is BootstrapStateResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    (candidate.run === null || isBootstrapRun(candidate.run)) &&
    typeof candidate.durable === "boolean" &&
    typeof candidate.lease_available === "boolean" &&
    typeof candidate.lease_held_by_current_actor === "boolean" &&
    candidate.execution_authorized === false &&
    candidate.infrastructure_mutation_authorized === false
  );
}

export async function getBootstrapState(): Promise<BootstrapStateResponse | null> {
  const response = await apiFetch("/api/v1/platform/bootstrap-state/current", {
    headers: { Accept: "application/json" },
  });
  if (response.status === 403 || response.status === 404) return null;
  if (!response.ok) throw new Error(`Bootstrap state failed with ${response.status}`);
  const payload: unknown = await response.json();
  return isBootstrapStateResponse(payload) ? payload : null;
}
