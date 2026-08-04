import { apiFetch } from "./client";

export const SUPPORT_BUNDLE_COMPONENTS = [
  "support.release-manifest",
  "support.bootstrap-summary",
  "support.service-health",
  "support.configuration-schema",
  "support.sanitized-diagnostics",
] as const;

export type SupportBundlePreview = {
  preview_id: string;
  schema_version: "atlas.support-bundle-preview.v1";
  catalog_version: "atlas.synthetic-support-catalog.v1";
  source_run_id: string;
  source_run_version: number;
  release_id: string;
  handoff_report_digest: string;
  source_evidence_digest: string;
  component_ids: string[];
  lookback_hours: number;
  window_start: string;
  window_end: string;
  entries: Array<{
    entry_id: string;
    file_name: string;
    classification: string;
    mandatory: boolean;
    disposition: "included" | "excluded";
    reason_code: string;
    size_bytes: number;
    sha256: string | null;
  }>;
  included_count: number;
  excluded_count: number;
  content_bytes: number;
  max_content_bytes: number;
  redaction_check_count: number;
  preview_digest: string;
  target_id: string;
  target_state: "empty" | "reusable";
  archive_sha256: string;
  archive_size_bytes: number;
  generated_at: string;
  expires_at: string;
  exportable: true;
  external_transfer_performed: false;
  arbitrary_file_collection_performed: false;
  network_request_performed: false;
  model_inference_performed: false;
  infrastructure_mutation_performed: false;
};

export type SupportBundleExport = {
  export_id: string;
  state: "completed";
  source_run_id: string;
  source_run_version: number;
  preview_digest: string;
  archive_sha256: string;
  archive_size_bytes: number;
  archive_name: string;
  included_count: number;
  excluded_count: number;
  created_at: string;
  expires_at: string;
  reused: boolean;
  external_transfer_performed: false;
};

type PreviewResponse = { data: SupportBundlePreview };
type ExportResponse = { data: SupportBundleExport };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isPreviewResponse(value: unknown): value is PreviewResponse {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return (
    item.schema_version === "atlas.support-bundle-preview.v1" &&
    item.catalog_version === "atlas.synthetic-support-catalog.v1" &&
    typeof item.preview_id === "string" &&
    typeof item.source_run_id === "string" &&
    typeof item.source_run_version === "number" &&
    Array.isArray(item.component_ids) &&
    Array.isArray(item.entries) &&
    item.entries.every(
      (entry) =>
        isRecord(entry) &&
        typeof entry.entry_id === "string" &&
        (entry.disposition === "included" || entry.disposition === "excluded") &&
        typeof entry.size_bytes === "number",
    ) &&
    typeof item.preview_digest === "string" &&
    typeof item.archive_sha256 === "string" &&
    typeof item.archive_size_bytes === "number" &&
    (item.target_state === "empty" || item.target_state === "reusable") &&
    item.exportable === true &&
    item.external_transfer_performed === false &&
    item.arbitrary_file_collection_performed === false &&
    item.network_request_performed === false &&
    item.model_inference_performed === false &&
    item.infrastructure_mutation_performed === false
  );
}

function isExportResponse(value: unknown): value is ExportResponse {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return (
    typeof item.export_id === "string" &&
    item.state === "completed" &&
    typeof item.source_run_id === "string" &&
    typeof item.source_run_version === "number" &&
    typeof item.preview_digest === "string" &&
    typeof item.archive_sha256 === "string" &&
    typeof item.archive_size_bytes === "number" &&
    typeof item.archive_name === "string" &&
    typeof item.included_count === "number" &&
    typeof item.excluded_count === "number" &&
    typeof item.created_at === "string" &&
    typeof item.expires_at === "string" &&
    typeof item.reused === "boolean" &&
    item.external_transfer_performed === false
  );
}

export async function previewSupportBundle(input: {
  sourceRunId: string;
  componentIds: string[];
  lookbackHours: number;
}): Promise<PreviewResponse> {
  const response = await apiFetch("/api/v1/platform/support-bundles/preview", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: "atlas.support-bundle-preview-request.v1",
      source_run_id: input.sourceRunId,
      component_ids: input.componentIds,
      lookback_hours: input.lookbackHours,
    }),
  });
  if (!response.ok) throw new Error(`Support bundle preview failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isPreviewResponse(payload)) throw new Error("Support bundle preview returned unsafe data");
  return payload;
}

export async function exportSupportBundle(input: {
  preview: SupportBundlePreview;
  justification: string;
}): Promise<ExportResponse> {
  const nonce = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch(
    `/api/v1/platform/support-bundles/${input.preview.source_run_id}/exports`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `support-bundle.${input.preview.source_run_version}.${nonce}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.support-bundle-export-request.v1",
        source_run_version: input.preview.source_run_version,
        component_ids: input.preview.component_ids,
        lookback_hours: input.preview.lookback_hours,
        preview_digest: input.preview.preview_digest,
        archive_sha256: input.preview.archive_sha256,
        target_id: input.preview.target_id,
        expected_target_state: input.preview.target_state,
        justification: input.justification,
        confirmed: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Support bundle export failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isExportResponse(payload)) throw new Error("Support bundle export returned unsafe data");
  return payload;
}
