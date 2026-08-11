import { apiFetch } from "./client";

export type ConnectorCapabilityChange = {
  capability_id: string;
  change_type: "added" | "removed" | "changed";
  current_class: "C0" | "C1" | null;
  candidate_class: "C0" | "C1" | null;
  current_permission: string | null;
  candidate_permission: string | null;
};

export type ConnectorUpgradeCandidate = {
  receipt_id: string;
  receipt_digest: string;
  package_digest: string;
  manifest_digest: string;
  release_version: string;
  publisher_id: string;
  sdk_profile: string;
  installed_at: string;
  upgrade_class: "patch" | "minor" | "major";
  risk_level: "low" | "medium" | "high" | "critical";
  capability_changes: ConnectorCapabilityChange[];
  target_products_added: string[];
  target_products_removed: string[];
  network_destinations_added: string[];
  network_destinations_removed: string[];
  configuration_key_delta: number;
  secret_reference_delta: number;
  policy_review_required: boolean;
  configuration_migration_required: boolean;
  rollback_receipt_id: string;
  rollback_receipt_digest: string;
  review_eligible: boolean;
  blockers: string[];
  canonical_digest: string;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorUpgradeReadiness = {
  schema_version: "atlas.connector-upgrade-readiness.v1";
  source_record_id: string;
  source_record_version: number;
  instance_id: string;
  instance_key: string;
  connector_id: string;
  current_release_version: string;
  current_package_digest: string;
  current_manifest_digest: string;
  current_receipt_id: string;
  current_receipt_digest: string;
  target_configured: boolean;
  candidates: ConnectorUpgradeCandidate[];
  generated_at: string;
  canonical_digest: string;
  decision_support_only: true;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorUpgradePlanStep = {
  step_id: string;
  sequence: number;
  phase: "approval" | "precheck" | "quiescence" | "package_binding" | "configuration" | "verification" | "rollback_gate";
  expected_minutes: number;
  requires_service_interruption: boolean;
  rollback_boundary: boolean;
};

export type ConnectorUpgradePlan = {
  plan_id: string;
  schema_version: "atlas.connector-upgrade-plan.v1";
  source_record_id: string;
  source_record_version: number;
  instance_id: string;
  connector_id: string;
  current_release_version: string;
  current_receipt_id: string;
  current_receipt_digest: string;
  candidate_release_version: string;
  candidate_receipt_id: string;
  candidate_receipt_digest: string;
  readiness_digest: string;
  candidate_digest: string;
  risk_level: "low" | "medium" | "high" | "critical";
  target_configured: boolean;
  target_id: string | null;
  site_id: string | null;
  target_product: string | null;
  plan_state: "ready_for_human_review" | "blocked";
  plan_eligible: boolean;
  prerequisite_ids: string[];
  steps: ConnectorUpgradePlanStep[];
  validation_check_ids: string[];
  stop_condition_ids: string[];
  rollback_step_ids: string[];
  blockers: string[];
  unknowns: string[];
  estimated_interruption_min_minutes: number | null;
  estimated_interruption_max_minutes: number | null;
  rollback_window_minutes: number;
  generated_at: string;
  expires_at: string;
  canonical_digest: string;
  approval_required: true;
  decision_support_only: true;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

const DIGEST = /^[a-f0-9]{64}$/;

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function capabilityChange(value: unknown): value is ConnectorCapabilityChange {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.capability_id === "string" &&
    (item.change_type === "added" || item.change_type === "removed" || item.change_type === "changed") &&
    (item.current_class === null || item.current_class === "C0" || item.current_class === "C1") &&
    (item.candidate_class === null || item.candidate_class === "C0" || item.candidate_class === "C1") &&
    (item.current_permission === null || typeof item.current_permission === "string") &&
    (item.candidate_permission === null || typeof item.candidate_permission === "string")
  );
}

function candidate(value: unknown): value is ConnectorUpgradeCandidate {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.receipt_id === "string" &&
    typeof item.release_version === "string" &&
    typeof item.publisher_id === "string" &&
    typeof item.sdk_profile === "string" &&
    typeof item.installed_at === "string" &&
    (item.upgrade_class === "patch" || item.upgrade_class === "minor" || item.upgrade_class === "major") &&
    (item.risk_level === "low" || item.risk_level === "medium" || item.risk_level === "high" || item.risk_level === "critical") &&
    Array.isArray(item.capability_changes) &&
    item.capability_changes.every(capabilityChange) &&
    strings(item.target_products_added) &&
    strings(item.target_products_removed) &&
    strings(item.network_destinations_added) &&
    strings(item.network_destinations_removed) &&
    typeof item.configuration_key_delta === "number" &&
    typeof item.secret_reference_delta === "number" &&
    typeof item.policy_review_required === "boolean" &&
    typeof item.configuration_migration_required === "boolean" &&
    typeof item.rollback_receipt_id === "string" &&
    typeof item.review_eligible === "boolean" &&
    strings(item.blockers) &&
    typeof item.receipt_digest === "string" && DIGEST.test(item.receipt_digest) &&
    typeof item.package_digest === "string" && DIGEST.test(item.package_digest) &&
    typeof item.manifest_digest === "string" && DIGEST.test(item.manifest_digest) &&
    typeof item.rollback_receipt_digest === "string" && DIGEST.test(item.rollback_receipt_digest) &&
    typeof item.canonical_digest === "string" && DIGEST.test(item.canonical_digest) &&
    item.execution_authorized === false &&
    item.infrastructure_mutation_performed === false
  );
}

function readiness(value: unknown): value is ConnectorUpgradeReadiness {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.schema_version === "atlas.connector-upgrade-readiness.v1" &&
    typeof item.source_record_id === "string" &&
    typeof item.source_record_version === "number" &&
    typeof item.instance_id === "string" &&
    typeof item.instance_key === "string" &&
    typeof item.connector_id === "string" &&
    typeof item.current_release_version === "string" &&
    typeof item.current_package_digest === "string" && DIGEST.test(item.current_package_digest) &&
    typeof item.current_manifest_digest === "string" && DIGEST.test(item.current_manifest_digest) &&
    typeof item.current_receipt_id === "string" &&
    typeof item.current_receipt_digest === "string" && DIGEST.test(item.current_receipt_digest) &&
    typeof item.target_configured === "boolean" &&
    Array.isArray(item.candidates) && item.candidates.every(candidate) &&
    typeof item.generated_at === "string" &&
    typeof item.canonical_digest === "string" && DIGEST.test(item.canonical_digest) &&
    item.decision_support_only === true &&
    item.execution_authorized === false &&
    item.infrastructure_mutation_performed === false &&
    !("target_endpoint" in item || "secret_reference" in item || "credential" in item)
  );
}

function planStep(value: unknown): value is ConnectorUpgradePlanStep {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.step_id === "string" &&
    typeof item.sequence === "number" &&
    typeof item.phase === "string" &&
    ["approval", "precheck", "quiescence", "package_binding", "configuration", "verification", "rollback_gate"].includes(item.phase) &&
    typeof item.expected_minutes === "number" &&
    typeof item.requires_service_interruption === "boolean" &&
    typeof item.rollback_boundary === "boolean"
  );
}

function plan(value: unknown): value is ConnectorUpgradePlan {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const nullableString = (candidate: unknown) => candidate === null || typeof candidate === "string";
  const nullableNumber = (candidate: unknown) => candidate === null || typeof candidate === "number";
  return (
    item.schema_version === "atlas.connector-upgrade-plan.v1" &&
    typeof item.plan_id === "string" &&
    typeof item.source_record_id === "string" &&
    typeof item.source_record_version === "number" &&
    typeof item.instance_id === "string" &&
    typeof item.connector_id === "string" &&
    typeof item.current_release_version === "string" &&
    typeof item.current_receipt_id === "string" &&
    typeof item.candidate_release_version === "string" &&
    typeof item.candidate_receipt_id === "string" &&
    (item.risk_level === "low" || item.risk_level === "medium" || item.risk_level === "high" || item.risk_level === "critical") &&
    typeof item.target_configured === "boolean" &&
    nullableString(item.target_id) && nullableString(item.site_id) && nullableString(item.target_product) &&
    (item.plan_state === "ready_for_human_review" || item.plan_state === "blocked") &&
    typeof item.plan_eligible === "boolean" &&
    strings(item.prerequisite_ids) &&
    Array.isArray(item.steps) && item.steps.length === 7 && item.steps.every(planStep) &&
    strings(item.validation_check_ids) && strings(item.stop_condition_ids) &&
    strings(item.rollback_step_ids) && strings(item.blockers) && strings(item.unknowns) &&
    nullableNumber(item.estimated_interruption_min_minutes) &&
    nullableNumber(item.estimated_interruption_max_minutes) &&
    typeof item.rollback_window_minutes === "number" &&
    typeof item.generated_at === "string" && typeof item.expires_at === "string" &&
    [item.current_receipt_digest, item.candidate_receipt_digest, item.readiness_digest, item.candidate_digest, item.canonical_digest].every((digest) => typeof digest === "string" && DIGEST.test(digest)) &&
    item.approval_required === true && item.decision_support_only === true &&
    item.execution_authorized === false && item.infrastructure_mutation_performed === false &&
    !("target_endpoint" in item || "secret_reference" in item || "credential" in item)
  );
}

export async function getConnectorUpgradeReadiness(
  recordId: string,
): Promise<ConnectorUpgradeReadiness> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(recordId)}/upgrade-readiness`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Connector upgrade readiness failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !readiness(payload.data)) {
    throw new Error("Connector upgrade readiness returned an unsafe record");
  }
  return payload.data;
}

export async function getConnectorUpgradePlan(
  recordId: string,
  candidateReceiptId: string,
): Promise<ConnectorUpgradePlan> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(recordId)}/upgrade-plans/${encodeURIComponent(candidateReceiptId)}`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Connector upgrade plan failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !plan(payload.data)) {
    throw new Error("Connector upgrade plan returned an unsafe record");
  }
  return payload.data;
}
