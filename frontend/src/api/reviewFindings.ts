import { apiFetch } from "./client";
import type { OperationalKnowledgeProtectedContent } from "./protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "./protectedInspections";

export type ReviewFindingTrack = "review-track.domain" | "review-track.security";

export type OperationalKnowledgeReviewFindingItem = {
  category_code: string;
  severity_code: string;
  summary: string;
  detail: string;
};

export type OperationalKnowledgeReviewFinding = {
  finding_packet_id: string;
  schema_version: "atlas.operational-knowledge-review-finding.v1";
  version: 1;
  source_lease_id: string;
  source_presentation_id: string;
  source_presentation_digest: string;
  source_assignment_set_id: string;
  organization_id: string;
  environment_id: string;
  review_request_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  classification: string;
  track_code: ReviewFindingTrack;
  finding_count: number;
  finding_bytes: number;
  finding_content_digest: string;
  finding_metadata_digest: string;
  lineage_digest: string;
  category_catalog_digest: string;
  severity_catalog_digest: string;
  finding_policy_id: string;
  finding_policy_digest: string;
  finding_policy_version: string;
  recorder_id: string;
  created_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_review_finding_recorded";
  purpose: string;
  canonical_digest: string;
  finding_recorded: true;
  domain_finding_recorded: boolean;
  security_finding_recorded: boolean;
  exact_assignee_verified: true;
  browser_session_bound: true;
  source_integrity_verified: true;
  immutable_finding_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  domain_review_completed: false;
  security_review_completed: false;
  correction_created: false;
  knowledge_approved: false;
  knowledge_published: false;
  retrieval_published: false;
  model_context_available: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const forbiddenResponseFields = [
  "summary",
  "detail",
  "findings",
  "finding_artifact_id",
  "lease_holder_subject_digest",
  "browser_session_binding_digest",
  "raw_subject_id",
  "reviewer_name",
  "reviewer_email",
  "storage_location",
  "idempotency_key",
];

function isSafeReviewFinding(
  value: unknown,
): value is { data: OperationalKnowledgeReviewFinding } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-review-finding.v1" &&
    record.version === 1 &&
    typeof record.finding_packet_id === "string" &&
    typeof record.finding_count === "number" &&
    record.finding_count >= 1 &&
    typeof record.finding_bytes === "number" &&
    record.finding_bytes >= 1 &&
    /^[a-f0-9]{64}$/.test(String(record.finding_content_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state === "operational_knowledge_review_finding_recorded" &&
    record.finding_recorded === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.immutable_finding_confirmed === true &&
    record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.domain_review_completed === false &&
    record.security_review_completed === false &&
    record.correction_created === false &&
    record.knowledge_approved === false &&
    record.knowledge_published === false &&
    record.retrieval_published === false &&
    record.model_context_available === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbiddenResponseFields.every((field) => !(field in record))
  );
}

export async function createOperationalKnowledgeReviewFinding(input: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  presentation: OperationalKnowledgeProtectedContent;
  policyId: string;
  policyDigest: string;
  findings: readonly OperationalKnowledgeReviewFindingItem[];
  purpose: string;
}) {
  const { lease, presentation, policyId, policyDigest, findings, purpose } = input;
  if (
    presentation.source_lease_id !== lease.lease_id ||
    presentation.track_code !== lease.track_code ||
    findings.length < 1 ||
    findings.length > 20 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact active presentation and bounded finding packet are required");
  const response = await apiFetch(
    `/api/v1/knowledge/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations/${encodeURIComponent(presentation.presentation_id)}/findings`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-review-finding.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-review-finding-input.v1",
        source_presentation_digest: presentation.canonical_digest,
        finding_policy_id: policyId,
        finding_policy_digest: policyDigest,
        findings: findings.map((finding) => ({
          category_code: finding.category_code,
          severity_code: finding.severity_code,
          summary: finding.summary.trim(),
          detail: finding.detail.trim(),
        })),
        purpose: purpose.trim(),
        acknowledged_evidence_was_reviewed: true,
        acknowledged_finding_is_not_a_review_decision: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge review finding failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewFinding(payload))
    throw new Error("Review finding returned an unsafe or authority-bearing record");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_presentation_id !== presentation.presentation_id ||
    payload.data.source_presentation_digest !== presentation.canonical_digest ||
    payload.data.track_code !== presentation.track_code ||
    payload.data.finding_policy_id !== policyId ||
    payload.data.finding_policy_digest !== policyDigest ||
    payload.data.finding_count !== findings.length
  )
    throw new Error("Review finding does not match the exact protected presentation");
  return payload;
}
