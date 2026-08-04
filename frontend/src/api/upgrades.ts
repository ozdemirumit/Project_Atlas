import { apiFetch } from "./client";

export const UPGRADE_TARGET_RELEASE_ID = "release.atlas.lab-0.2.0" as const;

export type UpgradeMigrationStep = {
  step_id: string;
  sequence: number;
  migration_kind: string;
  reversible: boolean;
  requires_quiescence: boolean;
  estimated_minutes: number;
};

export type UpgradeReadinessPlan = {
  plan_id: string;
  schema_version: "atlas.upgrade-readiness-plan.v1";
  catalog_version: "atlas.synthetic-upgrade-catalog.v1";
  source_run_id: string;
  source_run_version: number;
  source_release_id: string;
  source_release_version: string;
  target_release_id: typeof UPGRADE_TARGET_RELEASE_ID;
  target_release_version: string;
  profile: string;
  source_schema_version: string;
  target_schema_version: string;
  source_evidence_digest: string;
  backup_id: string;
  restore_validation_id: string;
  migration_steps: UpgradeMigrationStep[];
  service_dependency_ids: string[];
  abort_criterion_ids: string[];
  rollback_step_ids: string[];
  post_verification_check_ids: string[];
  readiness_checks: Array<{
    check_id: string;
    category_id: string;
    result_code: string;
    mandatory: boolean;
    passed: boolean;
  }>;
  estimated_downtime_min_minutes: number;
  estimated_downtime_max_minutes: number;
  rollback_window_minutes: number;
  rollback_supported: true;
  state: "ready";
  plan_digest: string;
  generated_at: string;
  expires_at: string;
  production_authorized: false;
  execution_authorized: false;
  active_state_mutation_performed: false;
};

export type UpgradeSimulation = {
  simulation_id: string;
  schema_version: "atlas.upgrade-rollback-simulation.v1";
  state: "passed";
  source_run_id: string;
  source_run_version: number;
  plan_id: string;
  plan_digest: string;
  backup_id: string;
  restore_validation_id: string;
  steps: Array<{
    step_id: string;
    sequence: number;
    state: "simulated";
    result_code: string;
    rollback_applicable: boolean;
    simulated_minutes: number;
  }>;
  impacted_service_ids: string[];
  post_verification_check_ids: string[];
  abort_injected_at_step_id: string;
  rollback_decision: string;
  estimated_downtime_minutes: number;
  simulation_digest: string;
  created_at: string;
  isolated_target: true;
  reused: boolean;
  production_authorized: false;
  artifact_acquisition_performed: false;
  database_migration_performed: false;
  service_restart_performed: false;
  traffic_switch_performed: false;
  active_restore_performed: false;
  secret_resolution_performed: false;
  network_request_performed: false;
  model_inference_performed: false;
  infrastructure_mutation_performed: false;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isReadiness(value: unknown): value is { data: UpgradeReadinessPlan } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return (
    item.schema_version === "atlas.upgrade-readiness-plan.v1" &&
    item.catalog_version === "atlas.synthetic-upgrade-catalog.v1" &&
    item.target_release_id === UPGRADE_TARGET_RELEASE_ID &&
    item.state === "ready" &&
    typeof item.plan_id === "string" &&
    typeof item.plan_digest === "string" &&
    typeof item.source_evidence_digest === "string" &&
    Array.isArray(item.migration_steps) &&
    item.migration_steps.length === 3 &&
    item.migration_steps.every(
      (step) =>
        isRecord(step) &&
        typeof step.step_id === "string" &&
        typeof step.sequence === "number" &&
        step.reversible === true,
    ) &&
    Array.isArray(item.readiness_checks) &&
    item.readiness_checks.length === 12 &&
    item.readiness_checks.every(
      (check) => isRecord(check) && check.mandatory === true && check.passed === true,
    ) &&
    Array.isArray(item.service_dependency_ids) &&
    item.service_dependency_ids.length === 2 &&
    Array.isArray(item.abort_criterion_ids) &&
    item.abort_criterion_ids.length === 4 &&
    Array.isArray(item.rollback_step_ids) &&
    item.rollback_step_ids.length === 4 &&
    Array.isArray(item.post_verification_check_ids) &&
    item.post_verification_check_ids.length === 6 &&
    item.rollback_supported === true &&
    item.production_authorized === false &&
    item.execution_authorized === false &&
    item.active_state_mutation_performed === false
  );
}

function isSimulation(value: unknown): value is { data: UpgradeSimulation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  const forbiddenOperations = [
    item.production_authorized,
    item.artifact_acquisition_performed,
    item.database_migration_performed,
    item.service_restart_performed,
    item.traffic_switch_performed,
    item.active_restore_performed,
    item.secret_resolution_performed,
    item.network_request_performed,
    item.model_inference_performed,
    item.infrastructure_mutation_performed,
  ];
  return (
    item.schema_version === "atlas.upgrade-rollback-simulation.v1" &&
    item.state === "passed" &&
    typeof item.simulation_id === "string" &&
    typeof item.simulation_digest === "string" &&
    item.isolated_target === true &&
    forbiddenOperations.every((operation) => operation === false) &&
    Array.isArray(item.steps) &&
    item.steps.length === 8 &&
    item.steps.every(
      (step) =>
        isRecord(step) &&
        typeof step.step_id === "string" &&
        typeof step.sequence === "number" &&
        step.state === "simulated",
    ) &&
    Array.isArray(item.impacted_service_ids) &&
    item.impacted_service_ids.length === 2 &&
    Array.isArray(item.post_verification_check_ids) &&
    item.post_verification_check_ids.length === 6
  );
}

function nonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
}

export async function previewUpgradeReadiness(input: {
  sourceRunId: string;
  backupId: string;
  restoreValidationId: string;
}) {
  const response = await apiFetch("/api/v1/platform/upgrades/readiness-preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.upgrade-readiness-request.v1",
      source_run_id: input.sourceRunId,
      backup_id: input.backupId,
      restore_validation_id: input.restoreValidationId,
      target_release_id: UPGRADE_TARGET_RELEASE_ID,
    }),
  });
  if (!response.ok) throw new Error(`Upgrade readiness failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isReadiness(payload)) throw new Error("Upgrade readiness returned unsafe data");
  return payload;
}

export async function simulateUpgradeRollback(
  plan: UpgradeReadinessPlan,
  justification: string,
) {
  const response = await apiFetch(
    `/api/v1/platform/upgrades/${plan.source_run_id}/simulations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `upgrade-simulation.${plan.source_run_version}.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.upgrade-simulation-request.v1",
        source_run_version: plan.source_run_version,
        backup_id: plan.backup_id,
        restore_validation_id: plan.restore_validation_id,
        target_release_id: plan.target_release_id,
        plan_id: plan.plan_id,
        plan_digest: plan.plan_digest,
        source_evidence_digest: plan.source_evidence_digest,
        justification,
        confirmed_isolated: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Upgrade simulation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSimulation(payload)) throw new Error("Upgrade simulation returned unsafe data");
  return payload;
}
