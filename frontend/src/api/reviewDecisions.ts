import { apiFetch } from "./client";
import type { OperationalKnowledgeFindingPresentation } from "./findingPresentations";
import type { OperationalKnowledgeProtectedContent } from "./protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "./protectedInspections";
import type { OperationalKnowledgeReviewFinding, ReviewFindingTrack } from "./reviewFindings";

export type ReviewDisposition =
  | "review-disposition.passed"
  | "review-disposition.changes-required";

export type OperationalKnowledgeTrackReviewDecision = {
  decision_id: string;
  schema_version: "atlas.operational-knowledge-track-review-decision.v1";
  version: 1;
  source_finding_presentation_id: string;
  source_finding_presentation_digest: string;
  source_finding_packet_id: string;
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
  disposition_code: ReviewDisposition;
  basis_codes: string[];
  decision_policy_id: string;
  decision_policy_digest: string;
  decision_policy_version: string;
  attestor_id: string;
  attestation_digest: string;
  decided_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_track_review_decided";
  purpose: string;
  canonical_digest: string;
  domain_review_completed: boolean;
  security_review_completed: boolean;
  domain_review_passed: boolean;
  security_review_passed: boolean;
  correction_required: boolean;
  correction_created: false;
  all_tracks_decided: boolean;
  all_tracks_passed: boolean;
  any_correction_required: boolean;
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
  "findings",
  "category_code",
  "severity_code",
  "summary",
  "detail",
  "finding_artifact_id",
  "decided_by_subject_digest",
  "browser_session_binding_digest",
  "source_finding_digest",
  "source_lease_digest",
  "basis_digest",
  "idempotency_key",
];

function isSafeDecision(
  value: unknown,
): value is { data: OperationalKnowledgeTrackReviewDecision } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const disposition = record.disposition_code;
  const track = record.track_code;
  const domain = track === "review-track.domain";
  const passed = disposition === "review-disposition.passed";
  return (
    record.schema_version === "atlas.operational-knowledge-track-review-decision.v1" &&
    record.version === 1 &&
    typeof record.decision_id === "string" &&
    (domain || track === "review-track.security") &&
    (passed || disposition === "review-disposition.changes-required") &&
    Array.isArray(record.basis_codes) &&
    record.basis_codes.length >= 1 &&
    record.basis_codes.length <= 4 &&
    record.basis_codes.every((item) => typeof item === "string") &&
    /^[a-f0-9]{64}$/.test(String(record.attestation_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state === "operational_knowledge_track_review_decided" &&
    record.domain_review_completed === domain &&
    record.security_review_completed === !domain &&
    record.domain_review_passed === (domain && passed) &&
    record.security_review_passed === (!domain && passed) &&
    record.correction_required === !passed &&
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

export async function createOperationalKnowledgeTrackReviewDecision(input: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  contentPresentation: OperationalKnowledgeProtectedContent;
  finding: OperationalKnowledgeReviewFinding;
  findingPresentation: OperationalKnowledgeFindingPresentation;
  policyId: string;
  policyDigest: string;
  disposition: ReviewDisposition;
  basisCodes: string[];
  purpose: string;
}) {
  const {
    lease,
    contentPresentation,
    finding,
    findingPresentation,
    policyId,
    policyDigest,
    disposition,
    basisCodes,
    purpose,
  } = input;
  if (
    contentPresentation.source_lease_id !== lease.lease_id ||
    finding.source_presentation_id !== contentPresentation.presentation_id ||
    findingPresentation.source_finding_packet_id !== finding.finding_packet_id ||
    findingPresentation.track_code !== lease.track_code ||
    basisCodes.length < 1 ||
    basisCodes.length > 4 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact current finding presentation and review decision are required");
  const endpoint =
    `/api/v1/knowledge/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}` +
    `/presentations/${encodeURIComponent(contentPresentation.presentation_id)}` +
    `/findings/${encodeURIComponent(finding.finding_packet_id)}` +
    `/presentations/${encodeURIComponent(findingPresentation.finding_presentation_id)}/decisions`;
  const response = await apiFetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-track-review-decision.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-track-review-decision-input.v1",
      source_finding_presentation_digest: findingPresentation.canonical_digest,
      decision_policy_id: policyId,
      decision_policy_digest: policyDigest,
      disposition_code: disposition,
      basis_codes: [...new Set(basisCodes)].sort(),
      purpose: purpose.trim(),
      acknowledged_exact_findings_reviewed: true,
      acknowledged_human_track_decision: true,
      acknowledged_no_approval_or_operational_authority: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational knowledge track review decision failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeDecision(payload))
    throw new Error("Track review decision returned unsafe or authority-bearing data");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_content_presentation_id !== contentPresentation.presentation_id ||
    payload.data.source_finding_packet_id !== finding.finding_packet_id ||
    payload.data.source_finding_presentation_id !== findingPresentation.finding_presentation_id ||
    payload.data.source_finding_presentation_digest !== findingPresentation.canonical_digest ||
    payload.data.track_code !== findingPresentation.track_code ||
    payload.data.disposition_code !== disposition ||
    payload.data.decision_policy_id !== policyId ||
    payload.data.decision_policy_digest !== policyDigest
  )
    throw new Error("Track review decision does not match the exact presented finding packet");
  return payload;
}
