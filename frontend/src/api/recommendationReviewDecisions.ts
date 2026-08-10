import { apiFetch } from "./client";
import type { RecommendationFindingPresentation } from "./recommendationFindingPresentations";
import type { RecommendationProtectedContent } from "./recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "./recommendationProtectedInspections";
import type {
  RecommendationFindingTrack,
  RecommendationHumanReviewFinding,
} from "./recommendationReviewFindings";

export type RecommendationReviewDisposition =
  | "review-disposition.passed"
  | "review-disposition.changes-required";

export type RecommendationTrackReviewDecision = {
  decision_id: string;
  schema_version: "atlas.recommendation-track-review-decision.v1";
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
  source_review_request_digest: string;
  recommendation_id: string;
  readiness_assessment_id: string;
  promotion_id: string;
  classification: string;
  source_outcome: "preferred" | "tie" | "no_support";
  option_count: number;
  preferred_count: number;
  track_code: RecommendationFindingTrack;
  disposition_code: RecommendationReviewDisposition;
  basis_codes: string[];
  decision_policy_id: string;
  decision_policy_digest: string;
  decision_policy_version: string;
  attestor_id: string;
  attestation_digest: string;
  decided_at: string;
  expires_at: string;
  state: "recommendation_track_review_decided";
  purpose: string;
  canonical_digest: string;
  technical_review_completed: boolean;
  service_impact_review_completed: boolean;
  technical_review_passed: boolean;
  service_impact_review_passed: boolean;
  correction_required: boolean;
  correction_created: false;
  all_tracks_decided: boolean;
  all_tracks_passed: boolean;
  any_correction_required: boolean;
  track_decisions: Array<{
    track_code: RecommendationFindingTrack;
    decision_id: string;
    canonical_digest: string;
    disposition_code: RecommendationReviewDisposition;
  }>;
  recommendation_approved: false;
  workflow_created: false;
  itsm_record_created: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const forbiddenResponseFields = new Set([
  "findings",
  "category_code",
  "severity_code",
  "summary",
  "detail",
  "finding_artifact_id",
  "recommendation_artifact_digest",
  "presented_content_digest",
  "decided_by_subject_digest",
  "browser_session_binding_digest",
  "source_finding_digest",
  "source_lease_digest",
  "basis_digest",
  "idempotency_key",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenResponseFields.has(key) || hasForbiddenField(child),
  );
}

function isSafeDecision(
  value: unknown,
): value is { data: RecommendationTrackReviewDecision } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const track = record.track_code;
  const technical = track === "review-track.technical";
  const passed = record.disposition_code === "review-disposition.passed";
  return (
    record.schema_version === "atlas.recommendation-track-review-decision.v1" &&
    record.version === 1 &&
    typeof record.decision_id === "string" &&
    (technical || track === "review-track.service-impact") &&
    (passed || record.disposition_code === "review-disposition.changes-required") &&
    Array.isArray(record.basis_codes) &&
    record.basis_codes.length >= 1 &&
    record.basis_codes.length <= 4 &&
    record.basis_codes.every((item) => typeof item === "string") &&
    /^[a-f0-9]{64}$/.test(String(record.source_review_request_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.attestation_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.state === "recommendation_track_review_decided" &&
    record.technical_review_completed === technical &&
    record.service_impact_review_completed === !technical &&
    record.technical_review_passed === (technical && passed) &&
    record.service_impact_review_passed === (!technical && passed) &&
    record.correction_required === !passed &&
    Array.isArray(record.track_decisions) &&
    record.track_decisions.length >= 1 &&
    record.track_decisions.length <= 2 &&
    record.track_decisions.every((item) => {
      if (!item || typeof item !== "object") return false;
      const binding = item as Record<string, unknown>;
      return (
        (binding.track_code === "review-track.technical" ||
          binding.track_code === "review-track.service-impact") &&
        typeof binding.decision_id === "string" &&
        /^[a-f0-9]{64}$/.test(String(binding.canonical_digest)) &&
        (binding.disposition_code === "review-disposition.passed" ||
          binding.disposition_code === "review-disposition.changes-required")
      );
    }) &&
    record.correction_created === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false
  );
}

export async function createRecommendationTrackReviewDecision(input: {
  lease: RecommendationProtectedInspection;
  contentPresentation: RecommendationProtectedContent;
  finding: RecommendationHumanReviewFinding;
  findingPresentation: RecommendationFindingPresentation;
  policyId: string;
  policyDigest: string;
  disposition: RecommendationReviewDisposition;
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
    findingPresentation.recommendation_id !== lease.recommendation_id ||
    findingPresentation.track_code !== lease.track_code ||
    basisCodes.length < 1 ||
    basisCodes.length > 4 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact current finding presentation and review decision are required");
  const endpoint =
    `/api/v1/recommendations/${encodeURIComponent(lease.recommendation_id)}` +
    `/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}` +
    `/presentations/${encodeURIComponent(contentPresentation.presentation_id)}` +
    `/findings/${encodeURIComponent(finding.finding_packet_id)}` +
    `/presentations/${encodeURIComponent(findingPresentation.finding_presentation_id)}/decisions`;
  const response = await apiFetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `recommendation-track-review-decision.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.recommendation-track-review-decision-input.v1",
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
    throw new Error(`Recommendation track review decision failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeDecision(payload))
    throw new Error("Track review decision returned unsafe or authority-bearing data");
  if (
    payload.data.recommendation_id !== lease.recommendation_id ||
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
