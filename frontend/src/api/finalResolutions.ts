import { apiFetch } from "./client";
import type { OperationalKnowledgeTrackReviewDecision } from "./reviewDecisions";

export type OperationalKnowledgeFinalResolution = {
  resolution_id: string;
  schema_version: "atlas.operational-knowledge-final-resolution.v1";
  version: 1;
  review_request_id: string;
  review_request_digest: string;
  decision_ids: [string, string];
  decision_digests: [string, string];
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  disposition_code: "final-resolution.approved" | "final-resolution.rejected";
  resolution_policy_id: string;
  resolution_policy_digest: string;
  attestation_digest: string;
  instance_state:
    | "operational_knowledge_final_approved"
    | "operational_knowledge_final_rejected";
  canonical_digest: string;
  domain_review_passed: true;
  security_review_passed: true;
  correction_required: false;
  correction_created: false;
  knowledge_approved: boolean;
  publication_ready: boolean;
  knowledge_published: false;
  retrieval_published: false;
  model_context_available: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const forbiddenResponseFields = [
  "content",
  "finding",
  "free_form_rationale",
  "artifact_location",
  "approved_by_subject_digest",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeResolution(
  value: unknown,
): value is { data: OperationalKnowledgeFinalResolution } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const approved = record.disposition_code === "final-resolution.approved";
  return (
    record.schema_version === "atlas.operational-knowledge-final-resolution.v1" &&
    record.version === 1 &&
    typeof record.resolution_id === "string" &&
    Array.isArray(record.decision_ids) &&
    record.decision_ids.length === 2 &&
    Array.isArray(record.decision_digests) &&
    record.decision_digests.length === 2 &&
    /^[a-f0-9]{64}$/.test(String(record.attestation_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state ===
      (approved
        ? "operational_knowledge_final_approved"
        : "operational_knowledge_final_rejected") &&
    record.domain_review_passed === true &&
    record.security_review_passed === true &&
    record.correction_required === false &&
    record.correction_created === false &&
    record.knowledge_approved === approved &&
    record.publication_ready === approved &&
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

export async function createOperationalKnowledgeFinalResolution(input: {
  decision: OperationalKnowledgeTrackReviewDecision;
  dispositionCode: "final-resolution.approved" | "final-resolution.rejected";
  basisCodes: string[];
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { decision, dispositionCode, basisCodes, policyId, policyDigest, purpose } = input;
  const bindings = [...decision.track_decisions].sort((a, b) =>
    a.track_code.localeCompare(b.track_code),
  );
  if (
    !decision.all_tracks_decided ||
    !decision.all_tracks_passed ||
    decision.any_correction_required ||
    bindings.length !== 2 ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("A fully passed review generation is required");
  const response = await apiFetch(
    `/api/v1/knowledge/review-requests/${encodeURIComponent(decision.review_request_id)}/final-resolutions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-final-resolution.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-final-resolution-input.v1",
        review_request_digest: decision.source_review_request_digest,
        decision_ids: bindings.map((item) => item.decision_id),
        decision_digests: bindings.map((item) => item.canonical_digest),
        disposition_code: dispositionCode,
        basis_codes: basisCodes,
        resolution_policy_id: policyId,
        resolution_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_immutable_review_generation: true,
        acknowledged_publication_readiness_only: true,
        acknowledged_no_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge final resolution failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeResolution(payload))
    throw new Error("Final resolution returned unsafe content or authority-bearing data");
  return payload;
}
