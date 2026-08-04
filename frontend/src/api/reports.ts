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
import { apiFetch } from "./client";
