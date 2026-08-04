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
  };
  durable: boolean;
  lease_available: boolean;
  lease_held_by_current_actor: boolean;
  execution_authorized: false;
  infrastructure_mutation_authorized: false;
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

function isRun(value: unknown): value is NonNullable<BootstrapState["run"]> {
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
    typeof candidate.updated_at === "string"
  );
}

function isBootstrapStateResponse(value: unknown): value is BootstrapStateResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    (candidate.run === null || isRun(candidate.run)) &&
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
