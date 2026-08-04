import { apiFetch, ApiRequestError } from "./client";
import type { SecurityExportDelivery } from "./securityExport";

export type AuditEvent = {
  sequence: number;
  event_id: string;
  event_type: string;
  schema_version: string;
  occurred_at: string;
  accepted_at: string;
  correlation_id: string;
  subject_id: string | null;
  actor_type: string | null;
  authentication_method: string | null;
  assurance_level: string | null;
  permission_id: string | null;
  resource_type: string | null;
  scope_reference: string;
  decision_id: string | null;
  outcome: string;
  result_code: string;
  target_subject_id: string | null;
};

export type AuditExportOverview = {
  generated_at: string;
  page: {
    events: AuditEvent[];
    limit: number;
    next_cursor: string | null;
    has_more: boolean;
  };
  health: Array<{
    destination_id: string;
    state: "active" | "degraded" | "disabled";
    queue_depth: number;
    delivered_count: number;
    retrying_count: number;
    dead_letter_count: number;
    certificate_days_remaining: number;
    last_transport_handoff_at: string | null;
    collector_acknowledgement_available: boolean;
    siem_ingestion_confirmed: boolean;
    limitations: string[];
  }>;
  recent_deliveries: SecurityExportDelivery[];
  safety_notice: string;
};

type AuditExportOverviewResponse = {
  data: AuditExportOverview;
  meta: { correlation_id: string; generated_at: string };
};

type AuditRetryResponse = {
  data: {
    attempted: number;
    delivered: number;
    retrying: number;
    dead_letter: number;
    generated_at: string;
  };
  meta: { correlation_id: string; generated_at: string };
};

export async function getAuditExportOverview(
  query: string,
  outcome: string,
): Promise<AuditExportOverviewResponse | null> {
  const parameters = new URLSearchParams({ limit: "25" });
  if (query.trim()) parameters.set("query", query.trim());
  if (outcome) parameters.set("outcome", outcome);
  const response = await apiFetch(`/api/v1/audit-export/overview?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 403) return null;
  if (!response.ok) throw new ApiRequestError("Audit export inventory failed", response.status);
  return (await response.json()) as AuditExportOverviewResponse;
}

export async function retryAuditExport(): Promise<AuditRetryResponse> {
  const response = await apiFetch("/api/v1/audit-export/retry", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Audit delivery retry failed", response.status);
  return (await response.json()) as AuditRetryResponse;
}
