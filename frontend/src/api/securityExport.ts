export type SecurityExportDelivery = {
  delivery_id: string;
  destination_id: string;
  event_id: string;
  state: "queued" | "retrying" | "transport_delivered" | "dead_letter";
  attempts: number;
  queued_at: string;
  updated_at: string;
  next_attempt_at: string | null;
  last_error_code: string | null;
  receipt: {
    receipt_id: string;
    destination_id: string;
    event_id: string;
    accepted_at: string;
    transport: "tls";
    collector_acknowledged: boolean;
    siem_ingestion_confirmed: boolean;
  } | null;
};

export type SecurityExportOverview = {
  generated_at: string;
  mapping_version: string;
  normalized_schema_version: string;
  destinations: Array<{
    destination_id: string;
    version: number;
    name: string;
    state: "active" | "degraded" | "disabled";
    transport: "tls";
    host: string;
    port: number;
    tls_server_authentication: boolean;
    tls_hostname_validation: boolean;
    certificate_not_after: string;
    facility: number;
    selected_categories: string[];
    classification_ceiling: string;
    max_queue_records: number;
    max_attempts: number;
  }>;
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
  preview_message: {
    priority: number;
    message_id: string;
    payload: string;
    payload_bytes: number;
    content_digest: string;
  };
  safety_notice: string;
};

type SecurityExportOverviewResponse = {
  data: SecurityExportOverview;
  meta: { correlation_id: string; generated_at: string };
};

type SecurityExportTestResponse = {
  data: SecurityExportDelivery;
  meta: { correlation_id: string; generated_at: string };
};

export async function getSecurityExportOverview(): Promise<SecurityExportOverviewResponse> {
  const response = await apiFetch("/api/v1/security-export/overview", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Security export overview request failed with ${response.status}`);
  }
  return (await response.json()) as SecurityExportOverviewResponse;
}

export async function sendSecurityExportTestEvent(): Promise<SecurityExportTestResponse> {
  const response = await apiFetch("/api/v1/security-export/test-event", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Security export test request failed with ${response.status}`);
  }
  return (await response.json()) as SecurityExportTestResponse;
}
import { apiFetch } from "./client";
