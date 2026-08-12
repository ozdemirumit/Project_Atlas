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

export type ConnectorUpgradeApprovalRequest = {
  request_id: string;
  schema_version: "atlas.connector-upgrade-approval-request.v1";
  version: 1;
  source_record_id: string;
  source_record_version: number;
  instance_id: string;
  connector_id: string;
  plan_id: string;
  plan_digest: string;
  readiness_digest: string;
  current_release_version: string;
  current_receipt_id: string;
  current_receipt_digest: string;
  candidate_release_version: string;
  candidate_receipt_id: string;
  candidate_receipt_digest: string;
  candidate_digest: string;
  risk_level: "low" | "medium" | "high" | "critical";
  organization_id: string;
  environment_id: string;
  requested_by: string;
  purpose: string;
  approval_policy_id: string;
  approval_policy_digest: string;
  approval_policy_version: string;
  created_at: string;
  expires_at: string;
  state: "pending";
  canonical_digest: string;
  separation_of_duties_required: true;
  approval_granted: false;
  decision_recorded: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorUpgradeApprovalOutcome = "approve" | "reject" | "needs_evidence" | "defer";

export type ConnectorUpgradeApprovalDecision = {
  decision_id: string;
  schema_version: "atlas.connector-upgrade-approval-decision.v1";
  version: 1;
  request_id: string;
  request_version: 1;
  request_digest: string;
  plan_id: string;
  plan_digest: string;
  outcome: ConnectorUpgradeApprovalOutcome;
  decided_by: string;
  rationale: string;
  organization_id: string;
  environment_id: string;
  approval_policy_id: string;
  approval_policy_digest: string;
  decided_at: string;
  canonical_digest: string;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorUpgradeApprovalRecord = {
  request: ConnectorUpgradeApprovalRequest;
  decision: ConnectorUpgradeApprovalDecision | null;
  state: "pending" | "approved" | "rejected" | "needs_evidence" | "deferred" | "expired";
  approval_valid: boolean;
  approval_granted: boolean;
  decision_recorded: boolean;
  separation_of_duties_enforced: true;
  package_rebound: false;
  configuration_changed: false;
  target_contacted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorUpgradeApprovalRevalidation = {
  revalidation_id: string;
  schema_version: "atlas.connector-upgrade-approval-revalidation.v1";
  version: 1;
  source_record_id: string;
  source_record_version: number;
  instance_id: string;
  connector_id: string;
  request_id: string;
  request_version: 1;
  request_digest: string;
  decision_id: string;
  decision_version: 1;
  decision_digest: string;
  plan_id: string;
  plan_digest: string;
  readiness_digest: string;
  current_receipt_id: string;
  current_receipt_digest: string;
  candidate_receipt_id: string;
  candidate_receipt_digest: string;
  approval_policy_id: string;
  approval_policy_version: string;
  approval_policy_digest: string;
  organization_id: string;
  environment_id: string;
  requester_id: string;
  approver_id: string;
  revalidated_by: string;
  purpose: string;
  check_ids: string[];
  revalidated_at: string;
  valid_until: string;
  canonical_digest: string;
  approval_current_at_revalidation: true;
  governance_ready: true;
  handoff_ready: false;
  target_configured: false;
  package_rebound: false;
  configuration_changed: false;
  target_contacted: false;
  handoff_artifact_issued: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorUpgradeHandoffReadiness = {
  assessment_id: string;
  schema_version: "atlas.connector-upgrade-handoff-readiness.v2";
  source_record_id: string;
  source_record_version: number;
  instance_id: string;
  connector_id: string;
  request_id: string;
  request_digest: string;
  decision_id: string;
  decision_digest: string;
  revalidation_id: string;
  revalidation_digest: string;
  plan_id: string;
  plan_digest: string;
  organization_id: string;
  environment_id: string;
  assessed_by: string;
  applicability_policy_id: string;
  applicability_policy_version: string;
  applicability_policy_digest: string;
  required_check_ids: string[];
  satisfied_check_ids: string[];
  not_applicable_check_ids: string[];
  blocker_ids: string[];
  assessed_at: string;
  evidence_valid_until: string;
  canonical_digest: string;
  assessment_state: "blocked";
  approval_current: true;
  revalidation_current: true;
  handoff_ready: false;
  handoff_artifact_issued: false;
  approval_consumed: false;
  target_contacted: false;
  package_rebound: false;
  configuration_changed: false;
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

function approvalRequest(value: unknown): value is ConnectorUpgradeApprovalRequest {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const digests = [
    item.plan_digest,
    item.readiness_digest,
    item.current_receipt_digest,
    item.candidate_receipt_digest,
    item.candidate_digest,
    item.approval_policy_digest,
    item.canonical_digest,
  ];
  return (
    item.schema_version === "atlas.connector-upgrade-approval-request.v1" &&
    item.version === 1 &&
    typeof item.request_id === "string" &&
    typeof item.source_record_id === "string" &&
    typeof item.source_record_version === "number" &&
    typeof item.instance_id === "string" &&
    typeof item.connector_id === "string" &&
    typeof item.plan_id === "string" &&
    typeof item.current_release_version === "string" &&
    typeof item.current_receipt_id === "string" &&
    typeof item.candidate_release_version === "string" &&
    typeof item.candidate_receipt_id === "string" &&
    (item.risk_level === "low" || item.risk_level === "medium" || item.risk_level === "high" || item.risk_level === "critical") &&
    typeof item.organization_id === "string" &&
    typeof item.environment_id === "string" &&
    typeof item.requested_by === "string" &&
    typeof item.purpose === "string" &&
    typeof item.approval_policy_id === "string" &&
    typeof item.approval_policy_version === "string" &&
    typeof item.created_at === "string" &&
    typeof item.expires_at === "string" &&
    item.state === "pending" &&
    digests.every((digest) => typeof digest === "string" && DIGEST.test(digest)) &&
    item.separation_of_duties_required === true &&
    item.approval_granted === false &&
    item.decision_recorded === false &&
    item.execution_authorized === false &&
    item.infrastructure_mutation_performed === false &&
    typeof item.reused === "boolean" &&
    !("request_fingerprint" in item || "idempotency_key" in item || "credential" in item)
  );
}

function approvalDecision(value: unknown): value is ConnectorUpgradeApprovalDecision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.schema_version === "atlas.connector-upgrade-approval-decision.v1" &&
    item.version === 1 &&
    item.request_version === 1 &&
    typeof item.decision_id === "string" &&
    typeof item.request_id === "string" &&
    typeof item.plan_id === "string" &&
    typeof item.decided_by === "string" &&
    typeof item.rationale === "string" &&
    typeof item.organization_id === "string" &&
    typeof item.environment_id === "string" &&
    typeof item.approval_policy_id === "string" &&
    typeof item.decided_at === "string" &&
    ["approve", "reject", "needs_evidence", "defer"].includes(String(item.outcome)) &&
    [
      item.request_digest,
      item.plan_digest,
      item.approval_policy_digest,
      item.canonical_digest,
    ].every((digest) => typeof digest === "string" && DIGEST.test(digest)) &&
    item.execution_authorized === false &&
    item.infrastructure_mutation_performed === false &&
    typeof item.reused === "boolean" &&
    !("decision_fingerprint" in item || "idempotency_key" in item || "credential" in item)
  );
}

function approvalRecord(value: unknown): value is ConnectorUpgradeApprovalRecord {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const states = ["pending", "approved", "rejected", "needs_evidence", "deferred", "expired"];
  return (
    approvalRequest(item.request) &&
    (item.decision === null || approvalDecision(item.decision)) &&
    states.includes(String(item.state)) &&
    typeof item.approval_valid === "boolean" &&
    typeof item.approval_granted === "boolean" &&
    typeof item.decision_recorded === "boolean" &&
    item.separation_of_duties_enforced === true &&
    item.package_rebound === false &&
    item.configuration_changed === false &&
    item.target_contacted === false &&
    item.execution_authorized === false &&
    item.infrastructure_mutation_performed === false &&
    !("request_fingerprint" in item || "decision_fingerprint" in item || "idempotency_key" in item)
  );
}

function approvalRevalidation(value: unknown): value is ConnectorUpgradeApprovalRevalidation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const digests = [
    item.request_digest,
    item.decision_digest,
    item.plan_digest,
    item.readiness_digest,
    item.current_receipt_digest,
    item.candidate_receipt_digest,
    item.approval_policy_digest,
    item.canonical_digest,
  ];
  return (
    item.schema_version === "atlas.connector-upgrade-approval-revalidation.v1" &&
    item.version === 1 && item.request_version === 1 && item.decision_version === 1 &&
    [
      item.revalidation_id, item.source_record_id, item.instance_id, item.connector_id,
      item.request_id, item.decision_id, item.plan_id, item.current_receipt_id,
      item.candidate_receipt_id, item.approval_policy_id, item.approval_policy_version,
      item.organization_id, item.environment_id, item.requester_id, item.approver_id,
      item.revalidated_by, item.purpose, item.revalidated_at, item.valid_until,
    ].every((field) => typeof field === "string") &&
    typeof item.source_record_version === "number" && strings(item.check_ids) &&
    digests.every((digest) => typeof digest === "string" && DIGEST.test(digest)) &&
    item.approval_current_at_revalidation === true && item.governance_ready === true &&
    item.handoff_ready === false && item.target_configured === false &&
    item.package_rebound === false && item.configuration_changed === false &&
    item.target_contacted === false && item.handoff_artifact_issued === false &&
    item.execution_authorized === false && item.infrastructure_mutation_performed === false &&
    typeof item.reused === "boolean" &&
    !("revalidation_fingerprint" in item || "idempotency_key" in item || "credential" in item)
  );
}

export function isConnectorUpgradeHandoffReadiness(
  value: unknown,
): value is ConnectorUpgradeHandoffReadiness {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const requiredItems = strings(item.required_check_ids) ? item.required_check_ids : null;
  const satisfiedItems = strings(item.satisfied_check_ids) ? item.satisfied_check_ids : null;
  const notApplicableItems = strings(item.not_applicable_check_ids)
    ? item.not_applicable_check_ids
    : null;
  const required = requiredItems ? new Set(requiredItems) : null;
  const satisfied = satisfiedItems ? new Set(satisfiedItems) : null;
  const notApplicable = notApplicableItems ? new Set(notApplicableItems) : null;
  const expectedBlockers = required && satisfied
    ? new Set([...required]
      .filter((checkId) => !satisfied.has(checkId))
      .map((checkId) => `connector.upgrade.handoff.blocked.${checkId
        .replace("connector.upgrade.handoff.", "")
        .replace(/-current$/, "")}-missing`))
    : null;
  return (
    item.schema_version === "atlas.connector-upgrade-handoff-readiness.v2" &&
    item.assessment_state === "blocked" &&
    [item.assessment_id, item.source_record_id, item.instance_id, item.connector_id, item.request_id,
      item.decision_id, item.revalidation_id, item.plan_id, item.organization_id, item.environment_id,
      item.assessed_by, item.applicability_policy_id, item.applicability_policy_version,
      item.assessed_at, item.evidence_valid_until].every((field) => typeof field === "string") &&
    [item.request_digest, item.decision_digest, item.revalidation_digest, item.plan_digest,
      item.applicability_policy_digest, item.canonical_digest]
      .every((digest) => typeof digest === "string" && DIGEST.test(digest)) &&
    requiredItems !== null && required !== null && required.size === requiredItems.length && required.size > 0 &&
    satisfiedItems !== null && satisfied !== null && satisfied.size === satisfiedItems.length && satisfied.size > 0 &&
    [...satisfied].every((checkId) => required.has(checkId)) &&
    notApplicableItems !== null && notApplicable !== null && notApplicable.size === notApplicableItems.length &&
    [...notApplicable].every((checkId) => !required.has(checkId)) &&
    strings(item.blocker_ids) && item.blocker_ids.length > 0 &&
    new Set(item.blocker_ids).size === item.blocker_ids.length &&
    expectedBlockers !== null && item.blocker_ids.length === expectedBlockers.size &&
    item.blocker_ids.every((blockerId) => expectedBlockers.has(blockerId)) &&
    item.approval_current === true && item.revalidation_current === true &&
    item.handoff_ready === false && item.handoff_artifact_issued === false &&
    item.approval_consumed === false && item.target_contacted === false &&
    item.package_rebound === false && item.configuration_changed === false &&
    item.execution_authorized === false && item.infrastructure_mutation_performed === false &&
    !("token" in item || "credential" in item || "target_endpoint" in item)
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

export async function createConnectorUpgradeApprovalRequest(input: {
  plan: ConnectorUpgradePlan;
  purpose: string;
}): Promise<ConnectorUpgradeApprovalRequest> {
  if (!input.plan.plan_eligible || input.plan.plan_state !== "ready_for_human_review") {
    throw new Error("Only an eligible exact upgrade plan can enter human approval");
  }
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(input.plan.source_record_id)}/upgrade-plans/${encodeURIComponent(input.plan.candidate_receipt_id)}/approval-requests`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-upgrade-approval.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-upgrade-approval-create-input.v1",
        source_plan_digest: input.plan.canonical_digest,
        purpose: input.purpose.trim(),
        acknowledged_request_is_not_approval_and_grants_no_execution_authority: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Connector upgrade approval request failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (
    !payload ||
    typeof payload !== "object" ||
    !("data" in payload) ||
    !approvalRequest(payload.data)
  ) {
    throw new Error("Connector upgrade approval returned an unsafe record");
  }
  if (
    payload.data.plan_id !== input.plan.plan_id ||
    payload.data.plan_digest !== input.plan.canonical_digest ||
    payload.data.source_record_id !== input.plan.source_record_id ||
    payload.data.candidate_receipt_id !== input.plan.candidate_receipt_id
  ) {
    throw new Error("Connector upgrade approval does not match the exact plan");
  }
  return payload.data;
}

export async function getConnectorUpgradeApprovalRequest(
  recordId: string,
  requestId: string,
): Promise<ConnectorUpgradeApprovalRequest> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(recordId)}/upgrade-approval-requests/${encodeURIComponent(requestId)}`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Connector upgrade approval read failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !approvalRequest(payload.data)) {
    throw new Error("Connector upgrade approval returned an unsafe record");
  }
  return payload.data;
}

export async function getConnectorUpgradeApprovalRecord(
  plan: ConnectorUpgradePlan,
): Promise<ConnectorUpgradeApprovalRecord | null> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(plan.source_record_id)}/upgrade-plans/${encodeURIComponent(plan.candidate_receipt_id)}/approval-record`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Connector upgrade approval record failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !approvalRecord(payload.data)) {
    throw new Error("Connector upgrade approval record returned an unsafe record");
  }
  if (
    payload.data.request.plan_id !== plan.plan_id ||
    payload.data.request.plan_digest !== plan.canonical_digest ||
    payload.data.request.source_record_id !== plan.source_record_id
  ) {
    throw new Error("Connector upgrade approval record does not match the exact plan");
  }
  return payload.data;
}

export async function decideConnectorUpgradeApproval(input: {
  record: ConnectorUpgradeApprovalRecord;
  outcome: ConnectorUpgradeApprovalOutcome;
  rationale: string;
}): Promise<ConnectorUpgradeApprovalRecord> {
  const { record, outcome, rationale } = input;
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(record.request.source_record_id)}/upgrade-approval-requests/${encodeURIComponent(record.request.request_id)}/decisions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-upgrade-approval-decision.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-upgrade-approval-decision-input.v1",
        expected_request_version: record.request.version,
        expected_request_digest: record.request.canonical_digest,
        outcome,
        rationale: rationale.trim(),
        acknowledged_decision_grants_no_execution_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Connector upgrade approval decision failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !approvalRecord(payload.data)) {
    throw new Error("Connector upgrade approval decision returned an unsafe record");
  }
  if (
    payload.data.request.request_id !== record.request.request_id ||
    payload.data.request.canonical_digest !== record.request.canonical_digest ||
    payload.data.decision?.outcome !== outcome
  ) {
    throw new Error("Connector upgrade approval decision does not match the exact request");
  }
  return payload.data;
}

export async function getLatestConnectorUpgradeApprovalRevalidation(
  record: ConnectorUpgradeApprovalRecord,
): Promise<ConnectorUpgradeApprovalRevalidation | null> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(record.request.source_record_id)}/upgrade-approval-requests/${encodeURIComponent(record.request.request_id)}/revalidations/latest`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Connector upgrade approval revalidation read failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !approvalRevalidation(payload.data)) {
    throw new Error("Connector upgrade approval revalidation returned an unsafe record");
  }
  if (
    payload.data.request_id !== record.request.request_id ||
    payload.data.request_digest !== record.request.canonical_digest ||
    payload.data.decision_digest !== record.decision?.canonical_digest
  ) {
    throw new Error("Connector upgrade approval revalidation does not match the exact decision");
  }
  return payload.data;
}

export async function revalidateConnectorUpgradeApproval(input: {
  record: ConnectorUpgradeApprovalRecord;
  purpose: string;
}): Promise<ConnectorUpgradeApprovalRevalidation> {
  const { record, purpose } = input;
  if (record.state !== "approved" || !record.approval_valid || record.decision?.outcome !== "approve") {
    throw new Error("Only a current approved decision can be revalidated");
  }
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(record.request.source_record_id)}/upgrade-approval-requests/${encodeURIComponent(record.request.request_id)}/revalidations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-upgrade-approval-revalidation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-upgrade-approval-revalidation-input.v1",
        expected_request_digest: record.request.canonical_digest,
        expected_decision_digest: record.decision.canonical_digest,
        purpose: purpose.trim(),
        acknowledged_revalidation_grants_no_handoff_or_execution_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Connector upgrade approval revalidation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !approvalRevalidation(payload.data)) {
    throw new Error("Connector upgrade approval revalidation returned an unsafe record");
  }
  if (
    payload.data.request_digest !== record.request.canonical_digest ||
    payload.data.decision_digest !== record.decision.canonical_digest
  ) {
    throw new Error("Connector upgrade approval revalidation does not match the exact decision");
  }
  return payload.data;
}

export async function getConnectorUpgradeHandoffReadiness(
  record: ConnectorUpgradeApprovalRecord,
): Promise<ConnectorUpgradeHandoffReadiness> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(record.request.source_record_id)}/upgrade-approval-requests/${encodeURIComponent(record.request.request_id)}/handoff-readiness`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Connector upgrade handoff readiness failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload) || !isConnectorUpgradeHandoffReadiness(payload.data)) {
    throw new Error("Connector upgrade handoff readiness returned an unsafe assessment");
  }
  if (
    payload.data.request_digest !== record.request.canonical_digest ||
    payload.data.decision_digest !== record.decision?.canonical_digest
  ) {
    throw new Error("Connector upgrade handoff readiness does not match the exact approval");
  }
  return payload.data;
}
