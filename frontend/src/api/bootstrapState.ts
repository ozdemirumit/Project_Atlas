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
    trust_provisioning: BootstrapTrustExecution | null;
    data_initialization: BootstrapDataExecution | null;
    service_deployment: BootstrapServiceExecution | null;
    identity_handoff: BootstrapIdentityExecution | null;
    integration_validation: BootstrapIntegrationExecution | null;
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

export type BootstrapTrustExecution = {
  execution_id: string;
  phase_id: "phase.trust";
  release_id: string;
  profile: string;
  configuration_digest: string;
  trust_schema_version: "atlas.bootstrap-trust-plan.v1";
  trust_plan_digest: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  anchor_count: number;
  workload_identity_count: number;
  evidence: Array<{
    file_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
  file_count: number;
  total_bytes: number;
};

export type BootstrapDataExecution = {
  execution_id: string;
  phase_id: "phase.data";
  release_id: string;
  profile: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_schema_version: "atlas.bootstrap-data-plan.v1";
  data_plan_digest: string;
  migration_artifact_digest: string;
  target_id: string;
  from_revision: string;
  to_revision: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  lock_acquired: boolean;
  migration_count: number;
  verified_object_count: number;
  backup_applicability: "not_applicable_clean_install";
  evidence: Array<{
    evidence_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
};

export type BootstrapServiceExecution = {
  execution_id: string;
  phase_id: "phase.services";
  release_id: string;
  profile: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  migration_artifact_digest: string;
  service_schema_version: "atlas.bootstrap-service-plan.v1";
  service_plan_digest: string;
  target_id: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  deployed_service_count: number;
  ready_service_count: number;
  passed_probe_count: number;
  service_statuses: Array<{
    service_id: string;
    state: "ready";
    startup_passed: boolean;
    readiness_passed: boolean;
    liveness_passed: boolean;
  }>;
  evidence: Array<{
    evidence_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
};

export type BootstrapIdentityExecution = {
  execution_id: string;
  phase_id: "phase.identity";
  release_id: string;
  profile: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  service_plan_digest: string;
  identity_schema_version: "atlas.bootstrap-identity-plan.v1";
  identity_plan_digest: string;
  target_id: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  group_mapping_count: number;
  validation_count: number;
  credential_replacement_required: boolean;
  recovery_identity_verified: boolean;
  bootstrap_material_sealed: boolean;
  pilot_identity_verified: boolean;
  enterprise_authentication_validated: boolean;
  evidence: Array<{
    evidence_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
};

export type BootstrapIntegrationExecution = {
  execution_id: string;
  phase_id: "phase.integrations";
  release_id: string;
  profile: string;
  configuration_digest: string;
  trust_plan_digest: string;
  data_plan_digest: string;
  service_plan_digest: string;
  identity_plan_digest: string;
  integration_schema_version: "atlas.bootstrap-integration-plan.v1";
  integration_plan_digest: string;
  target_id: string;
  state: "running" | "completed" | "failed";
  result_code: string;
  started_at: string;
  completed_at: string | null;
  model_check_count: number;
  integration_check_count: number;
  mandatory_pass_count: number;
  activation_count: number;
  network_request_count: number;
  secret_resolution_count: number;
  checks: Array<{
    check_id: string;
    subject_id: string;
    state: "passed" | "not_applicable";
    result_code: string;
    mandatory: boolean;
  }>;
  evidence: Array<{
    evidence_id: string;
    sha256: string;
    size_bytes: number;
    disposition: "published" | "reused";
  }>;
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

export function isTrustExecution(value: unknown): value is BootstrapTrustExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.trust" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.configuration_digest === "string" &&
    candidate.trust_schema_version === "atlas.bootstrap-trust-plan.v1" &&
    typeof candidate.trust_plan_digest === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    typeof candidate.anchor_count === "number" &&
    typeof candidate.workload_identity_count === "number" &&
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

export function isDataExecution(value: unknown): value is BootstrapDataExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.data" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    candidate.data_schema_version === "atlas.bootstrap-data-plan.v1" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.migration_artifact_digest === "string" &&
    typeof candidate.target_id === "string" &&
    typeof candidate.from_revision === "string" &&
    typeof candidate.to_revision === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    typeof candidate.lock_acquired === "boolean" &&
    typeof candidate.migration_count === "number" &&
    typeof candidate.verified_object_count === "number" &&
    candidate.backup_applicability === "not_applicable_clean_install" &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.evidence_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    })
  );
}

export function isServiceExecution(value: unknown): value is BootstrapServiceExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.services" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.migration_artifact_digest === "string" &&
    candidate.service_schema_version === "atlas.bootstrap-service-plan.v1" &&
    typeof candidate.service_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    typeof candidate.deployed_service_count === "number" &&
    typeof candidate.ready_service_count === "number" &&
    typeof candidate.passed_probe_count === "number" &&
    Array.isArray(candidate.service_statuses) &&
    candidate.service_statuses.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const status = item as Record<string, unknown>;
      return (
        typeof status.service_id === "string" &&
        status.state === "ready" &&
        typeof status.startup_passed === "boolean" &&
        typeof status.readiness_passed === "boolean" &&
        typeof status.liveness_passed === "boolean"
      );
    }) &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.evidence_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    })
  );
}

export function isIdentityExecution(value: unknown): value is BootstrapIdentityExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.identity" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.service_plan_digest === "string" &&
    candidate.identity_schema_version === "atlas.bootstrap-identity-plan.v1" &&
    typeof candidate.identity_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    typeof candidate.group_mapping_count === "number" &&
    typeof candidate.validation_count === "number" &&
    typeof candidate.credential_replacement_required === "boolean" &&
    typeof candidate.recovery_identity_verified === "boolean" &&
    typeof candidate.bootstrap_material_sealed === "boolean" &&
    typeof candidate.pilot_identity_verified === "boolean" &&
    typeof candidate.enterprise_authentication_validated === "boolean" &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.evidence_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    })
  );
}

export function isIntegrationExecution(value: unknown): value is BootstrapIntegrationExecution {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.execution_id === "string" &&
    candidate.phase_id === "phase.integrations" &&
    typeof candidate.release_id === "string" &&
    typeof candidate.profile === "string" &&
    typeof candidate.configuration_digest === "string" &&
    typeof candidate.trust_plan_digest === "string" &&
    typeof candidate.data_plan_digest === "string" &&
    typeof candidate.service_plan_digest === "string" &&
    typeof candidate.identity_plan_digest === "string" &&
    candidate.integration_schema_version === "atlas.bootstrap-integration-plan.v1" &&
    typeof candidate.integration_plan_digest === "string" &&
    typeof candidate.target_id === "string" &&
    (candidate.state === "running" ||
      candidate.state === "completed" ||
      candidate.state === "failed") &&
    typeof candidate.result_code === "string" &&
    typeof candidate.started_at === "string" &&
    (candidate.completed_at === null || typeof candidate.completed_at === "string") &&
    typeof candidate.model_check_count === "number" &&
    typeof candidate.integration_check_count === "number" &&
    typeof candidate.mandatory_pass_count === "number" &&
    candidate.activation_count === 0 &&
    candidate.network_request_count === 0 &&
    candidate.secret_resolution_count === 0 &&
    Array.isArray(candidate.checks) &&
    candidate.checks.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const check = item as Record<string, unknown>;
      return (
        typeof check.check_id === "string" &&
        typeof check.subject_id === "string" &&
        (check.state === "passed" || check.state === "not_applicable") &&
        typeof check.result_code === "string" &&
        typeof check.mandatory === "boolean"
      );
    }) &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const evidence = item as Record<string, unknown>;
      return (
        typeof evidence.evidence_id === "string" &&
        typeof evidence.sha256 === "string" &&
        typeof evidence.size_bytes === "number" &&
        (evidence.disposition === "published" || evidence.disposition === "reused")
      );
    })
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
      isConfigurationExecution(candidate.configuration_rendering)) &&
    (candidate.trust_provisioning === null ||
      isTrustExecution(candidate.trust_provisioning)) &&
    (candidate.data_initialization === null ||
      isDataExecution(candidate.data_initialization)) &&
    (candidate.service_deployment === null ||
      isServiceExecution(candidate.service_deployment)) &&
    (candidate.identity_handoff === null ||
      isIdentityExecution(candidate.identity_handoff)) &&
    (candidate.integration_validation === null ||
      isIntegrationExecution(candidate.integration_validation))
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
