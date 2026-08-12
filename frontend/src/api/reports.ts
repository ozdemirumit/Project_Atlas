import { ApiRequestError, apiFetch } from "./client";

export type ReportSection = {
  section_id: string;
  title: string;
  state: "complete" | "partial" | "failed";
  statements: string[];
  evidence_references: string[];
  limitations: string[];
};

export type ItsmHandoffDraft = {
  draft_id: string;
  idempotency_key: string;
  state: "review_required";
  external_system: string;
  operation: string;
  incident_reference: string;
  report_id: string;
  report_version: number;
  generated_content_label: string;
  field_mappings: Array<{
    field: string;
    value: string;
    source_reference: string;
  }>;
  artifact_references: string[];
  classification: string;
  redaction_state: string;
  human_review_required: boolean;
  dispatch_authorized: boolean;
  external_record_mutated: boolean;
};

export type TechnicalReport = {
  report_id: string;
  version: number;
  prior_version_id: string | null;
  owner: string;
  state: string;
  requested_by: string;
  created_at: string;
  expires_at: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  target_id: string;
  report_type: string;
  audience: string;
  classification: string;
  redaction_state: string;
  source: {
    recommendation_id: string;
    recommendation_version: number;
    recommendation_state: string;
    recommendation_created_at: string;
    recommendation_expires_at: string;
    rca_case_id: string;
    rca_case_version: number;
    target_id: string;
    evidence_ids: string[];
    component_versions: string[];
  };
  sections: ReportSection[];
  review: {
    status: string;
    reviewer_id: string | null;
    reviewed_at: string | null;
    rationale: string | null;
  };
  itsm_handoff: ItsmHandoffDraft | null;
  rendered_markdown: string;
  content_digest: string;
  component_versions: string[];
  data_profile: string;
  execution_authorized: boolean;
  external_mutation_authorized: boolean;
  safety_notice: string;
};

type TechnicalReportResponse = {
  data: TechnicalReport;
  meta: { correlation_id: string; generated_at: string };
};

export type ItsmHandoffReviewOutcome = "accept" | "needs_evidence" | "reject";

export type ItsmHandoffHumanReview = {
  review_id: string;
  schema_version: string;
  version: number;
  outcome: ItsmHandoffReviewOutcome;
  report_id: string;
  report_version: number;
  report_digest: string;
  handoff_draft_id: string;
  handoff_digest: string;
  handoff_idempotency_key: string;
  incident_reference: string;
  operation: string;
  requester_id: string;
  reviewer_id: string;
  reviewer_role_id: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  rationale: string;
  acknowledged_review_only: boolean;
  request_fingerprint: string;
  idempotency_key: string;
  canonical_digest: string;
  decided_at: string;
  expires_at: string;
  review_complete: boolean;
  dispatch_authorized: boolean;
  external_record_mutated: boolean;
  itsm_approval_satisfied: boolean;
  workflow_approved: boolean;
  execution_authorized: boolean;
  infrastructure_mutation_performed: boolean;
  reused: boolean;
};

type ItsmHandoffReviewResponse = {
  data: ItsmHandoffHumanReview;
  meta: { correlation_id: string; generated_at: string };
};

type ItsmHandoffReviewLookupResponse = {
  data: ItsmHandoffHumanReview | null;
  meta: { correlation_id: string; generated_at: string };
};

export async function createStorageTechnicalReport(
  targetId: string,
  recommendationId: string,
  recommendationVersion: number,
  incidentReference: string,
): Promise<TechnicalReportResponse> {
  const response = await apiFetch(`/api/v1/reports/storage/${encodeURIComponent(targetId)}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      source_recommendation_id: recommendationId,
      source_recommendation_version: recommendationVersion,
      report_type: "technical_decision",
      audience: "technical_operations",
      classification: "internal",
      include_itsm_handoff: true,
      incident_reference: incidentReference,
    }),
  });
  if (!response.ok) {
    throw new Error(`Report request failed with ${response.status}`);
  }
  return (await response.json()) as TechnicalReportResponse;
}

export async function getItsmHandoffReview(
  reportId: string,
  handoffDraftId: string,
): Promise<ItsmHandoffReviewLookupResponse> {
  const query = new URLSearchParams({ handoff_draft_id: handoffDraftId });
  const response = await apiFetch(
    `/api/v1/reports/${encodeURIComponent(reportId)}/itsm-handoff/review?${query}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("ITSM handoff review unavailable", response.status);
  }
  return (await response.json()) as ItsmHandoffReviewLookupResponse;
}

export async function decideItsmHandoffReview(
  report: TechnicalReport,
  outcome: ItsmHandoffReviewOutcome,
  rationale: string,
): Promise<ItsmHandoffReviewResponse> {
  if (!report.itsm_handoff) {
    throw new ApiRequestError("ITSM handoff draft unavailable", 409);
  }
  const response = await apiFetch(
    `/api/v1/reports/${encodeURIComponent(report.report_id)}/itsm-handoff/reviews`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `itsm-handoff-review.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        report_version: report.version,
        report_digest: report.content_digest,
        handoff_draft_id: report.itsm_handoff.draft_id,
        outcome,
        rationale,
        acknowledged_review_only: true,
      }),
    },
  );
  if (!response.ok) {
    throw new ApiRequestError("ITSM handoff review decision failed", response.status);
  }
  return (await response.json()) as ItsmHandoffReviewResponse;
}
