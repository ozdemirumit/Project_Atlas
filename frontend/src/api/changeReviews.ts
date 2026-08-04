import { apiFetch } from "./client";
import type { UpgradeReadinessPlan, UpgradeSimulation } from "./upgrades";

export type UpgradeChangeReviewPreview = {
  preview_id: string;
  schema_version: "atlas.upgrade-change-review-preview.v1";
  source_run_id: string;
  source_run_version: number;
  plan_id: string;
  plan_digest: string;
  simulation_id: string;
  simulation_digest: string;
  source_release_id: string;
  source_release_version: string;
  target_release_id: string;
  target_release_version: string;
  backup_id: string;
  restore_validation_id: string;
  risk_class: "risk.medium";
  change_class: "change.reviewed-standard";
  impacted_service_ids: string[];
  migration_step_ids: string[];
  abort_criterion_ids: string[];
  rollback_step_ids: string[];
  post_verification_check_ids: string[];
  assumption_ids: string[];
  unknown_ids: string[];
  residual_risk_ids: string[];
  owner_role_ids: string[];
  evidence_digests: string[];
  estimated_downtime_min_minutes: number;
  estimated_downtime_max_minutes: number;
  rollback_window_minutes: number;
  state: "ready";
  preview_digest: string;
  generated_at: string;
  expires_at: string;
  approval_granted: false;
  execution_authorized: false;
  dispatch_authorized: false;
  infrastructure_mutation_performed: false;
};

export type UpgradeChangeReviewPacket = {
  packet_id: string;
  schema_version: "atlas.upgrade-change-review-packet.v1";
  state: "created";
  source_run_id: string;
  source_run_version: number;
  preview_id: string;
  preview_digest: string;
  plan_id: string;
  plan_digest: string;
  simulation_id: string;
  simulation_digest: string;
  backup_id: string;
  restore_validation_id: string;
  risk_class: string;
  change_class: string;
  impacted_service_ids: string[];
  migration_step_ids: string[];
  abort_criterion_ids: string[];
  rollback_step_ids: string[];
  post_verification_check_ids: string[];
  assumption_ids: string[];
  unknown_ids: string[];
  residual_risk_ids: string[];
  owner_role_ids: string[];
  evidence_digests: string[];
  proposed_window_start: string;
  proposed_window_end: string;
  estimated_downtime_min_minutes: number;
  estimated_downtime_max_minutes: number;
  rollback_window_minutes: number;
  itsm_draft_id: string;
  itsm_draft_title: string;
  itsm_draft_digest: string;
  packet_digest: string;
  created_at: string;
  reused: boolean;
  approval_granted: false;
  execution_authorized: false;
  itsm_dispatched: false;
  notification_sent: false;
  workflow_executed: false;
  infrastructure_mutation_performed: false;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasExactEvidence(item: Record<string, unknown>): boolean {
  const lengths: Array<[unknown, number]> = [
    [item.impacted_service_ids, 2],
    [item.migration_step_ids, 3],
    [item.abort_criterion_ids, 4],
    [item.rollback_step_ids, 4],
    [item.post_verification_check_ids, 6],
    [item.assumption_ids, 4],
    [item.unknown_ids, 4],
    [item.residual_risk_ids, 3],
    [item.owner_role_ids, 4],
    [item.evidence_digests, 4],
  ];
  return lengths.every(([value, length]) => Array.isArray(value) && value.length === length);
}

function isPreview(value: unknown): value is { data: UpgradeChangeReviewPreview } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return (
    item.schema_version === "atlas.upgrade-change-review-preview.v1" &&
    item.state === "ready" &&
    item.risk_class === "risk.medium" &&
    item.change_class === "change.reviewed-standard" &&
    typeof item.preview_id === "string" &&
    typeof item.preview_digest === "string" &&
    hasExactEvidence(item) &&
    item.approval_granted === false &&
    item.execution_authorized === false &&
    item.dispatch_authorized === false &&
    item.infrastructure_mutation_performed === false
  );
}

function isPacket(value: unknown): value is { data: UpgradeChangeReviewPacket } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return (
    item.schema_version === "atlas.upgrade-change-review-packet.v1" &&
    item.state === "created" &&
    typeof item.packet_id === "string" &&
    typeof item.packet_digest === "string" &&
    typeof item.itsm_draft_id === "string" &&
    hasExactEvidence(item) &&
    item.approval_granted === false &&
    item.execution_authorized === false &&
    item.itsm_dispatched === false &&
    item.notification_sent === false &&
    item.workflow_executed === false &&
    item.infrastructure_mutation_performed === false
  );
}

function evidence(plan: UpgradeReadinessPlan, simulation: UpgradeSimulation) {
  return {
    source_run_id: plan.source_run_id,
    source_run_version: plan.source_run_version,
    backup_id: plan.backup_id,
    restore_validation_id: plan.restore_validation_id,
    target_release_id: plan.target_release_id,
    plan_id: plan.plan_id,
    plan_digest: plan.plan_digest,
    simulation_id: simulation.simulation_id,
    simulation_digest: simulation.simulation_digest,
  };
}

function nonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
}

export async function previewUpgradeChangeReview(
  plan: UpgradeReadinessPlan,
  simulation: UpgradeSimulation,
) {
  const response = await apiFetch("/api/v1/platform/upgrade-change-reviews/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.upgrade-change-review-preview-request.v1",
      ...evidence(plan, simulation),
    }),
  });
  if (!response.ok) throw new Error(`Change review preview failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isPreview(payload)) throw new Error("Change review preview returned unsafe data");
  return payload;
}

export async function createUpgradeChangeReviewPacket(input: {
  preview: UpgradeChangeReviewPreview;
  plan: UpgradeReadinessPlan;
  simulation: UpgradeSimulation;
  justification: string;
  proposedWindowStart: string;
  proposedWindowEnd: string;
}) {
  const response = await apiFetch(
    `/api/v1/platform/upgrade-change-reviews/${input.plan.source_run_id}/packets`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `change-review.${input.plan.source_run_version}.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.upgrade-change-review-create-request.v1",
        ...evidence(input.plan, input.simulation),
        preview_id: input.preview.preview_id,
        preview_digest: input.preview.preview_digest,
        preview_expires_at: input.preview.expires_at,
        proposed_window_start: new Date(input.proposedWindowStart).toISOString(),
        proposed_window_end: new Date(input.proposedWindowEnd).toISOString(),
        justification: input.justification,
        confirmed: true,
        acknowledged_no_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Change review creation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isPacket(payload)) throw new Error("Change review creation returned unsafe data");
  return payload;
}
