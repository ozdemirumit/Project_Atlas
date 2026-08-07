import { apiFetch } from "./client";
import type { OperationalKnowledgeProtectedContent } from "./protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "./protectedInspections";
import type {
  OperationalKnowledgeReviewFinding,
  OperationalKnowledgeReviewFindingItem,
  ReviewFindingTrack,
} from "./reviewFindings";

export type OperationalKnowledgeFindingPresentation = {
  finding_presentation_id: string;
  schema_version: "atlas.operational-knowledge-finding-presentation.v1";
  version: 1;
  source_finding_packet_id: string;
  source_finding_digest: string;
  source_lease_id: string;
  source_content_presentation_id: string;
  source_assignment_set_id: string;
  organization_id: string;
  environment_id: string;
  review_request_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  title: string;
  classification: string;
  track_code: ReviewFindingTrack;
  findings: OperationalKnowledgeReviewFindingItem[];
  finding_count: number;
  finding_bytes: number;
  finding_content_digest: string;
  finding_metadata_digest: string;
  lineage_digest: string;
  category_catalog_digest: string;
  severity_catalog_digest: string;
  presentation_policy_id: string;
  presentation_policy_digest: string;
  presentation_policy_version: string;
  presenter_id: string;
  presented_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_review_finding_presented";
  purpose: string;
  canonical_digest: string;
  finding_recorded: true;
  finding_presented: true;
  domain_finding_recorded: boolean;
  security_finding_recorded: boolean;
  exact_assignee_verified: true;
  browser_session_bound: true;
  source_integrity_verified: true;
  encrypted_source_verified: true;
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
  "finding_artifact_id",
  "source_finding_artifact_id",
  "lease_holder_subject_digest",
  "browser_session_binding_digest",
  "source_cleanup_digest",
  "presentation_cleanup_digest",
  "storage_location",
  "decryption_key",
  "idempotency_key",
];

function isFindingItem(value: unknown): value is OperationalKnowledgeReviewFindingItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.category_code === "string" &&
    typeof item.severity_code === "string" &&
    typeof item.summary === "string" &&
    item.summary.length >= 10 &&
    item.summary.length <= 200 &&
    typeof item.detail === "string" &&
    item.detail.length >= 20 &&
    item.detail.length <= 4000
  );
}

function isSafeFindingPresentation(
  value: unknown,
): value is { data: OperationalKnowledgeFindingPresentation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-finding-presentation.v1" &&
    record.version === 1 &&
    typeof record.finding_presentation_id === "string" &&
    Array.isArray(record.findings) &&
    record.findings.length >= 1 &&
    record.findings.length <= 20 &&
    record.findings.every(isFindingItem) &&
    record.finding_count === record.findings.length &&
    typeof record.finding_bytes === "number" &&
    record.finding_bytes >= 1 &&
    /^[a-f0-9]{64}$/.test(String(record.finding_content_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state === "operational_knowledge_review_finding_presented" &&
    record.finding_recorded === true &&
    record.finding_presented === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.encrypted_source_verified === true &&
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

export async function createOperationalKnowledgeFindingPresentation(input: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  contentPresentation: OperationalKnowledgeProtectedContent;
  finding: OperationalKnowledgeReviewFinding;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { lease, contentPresentation, finding, policyId, policyDigest, purpose } = input;
  if (
    contentPresentation.source_lease_id !== lease.lease_id ||
    finding.source_lease_id !== lease.lease_id ||
    finding.source_presentation_id !== contentPresentation.presentation_id ||
    finding.track_code !== lease.track_code ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact sealed finding packet and active inspection lease are required");
  const response = await apiFetch(
    `/api/v1/knowledge/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations/${encodeURIComponent(contentPresentation.presentation_id)}/findings/${encodeURIComponent(finding.finding_packet_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-finding-presentation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-finding-presentation-input.v1",
        source_finding_digest: finding.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_findings_are_sensitive: true,
        acknowledged_finding_presentation_is_not_a_review_decision: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge finding presentation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeFindingPresentation(payload))
    throw new Error("Finding presentation returned unsafe or authority-bearing data");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_content_presentation_id !== contentPresentation.presentation_id ||
    payload.data.source_finding_packet_id !== finding.finding_packet_id ||
    payload.data.source_finding_digest !== finding.canonical_digest ||
    payload.data.track_code !== finding.track_code ||
    payload.data.finding_count !== finding.finding_count ||
    payload.data.finding_content_digest !== finding.finding_content_digest ||
    payload.data.presentation_policy_id !== policyId ||
    payload.data.presentation_policy_digest !== policyDigest
  )
    throw new Error("Finding presentation does not match the exact sealed packet");
  return payload;
}
