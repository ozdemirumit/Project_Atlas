import { apiFetch } from "./client";

export const LOGICAL_BACKUP_COMPONENTS = [
  "backup.release-state",
  "backup.configuration-state",
  "backup.checkpoint-state",
  "backup.verification-state",
  "backup.identity-handoff",
  "backup.integration-validation",
  "backup.operational-handoff",
] as const;

export type BackupPreview = {
  preview_id: string;
  schema_version: "atlas.logical-backup-preview.v1";
  catalog_version: "atlas.synthetic-logical-backup-catalog.v1";
  source_run_id: string;
  source_run_version: number;
  release_id: string;
  source_evidence_digest: string;
  component_ids: string[];
  entries: Array<{ entry_id: string; file_name: string; classification: string;
    mandatory: boolean; size_bytes: number; sha256: string }>;
  content_bytes: number;
  max_content_bytes: number;
  preview_digest: string;
  target_id: string;
  target_state: "empty" | "reusable";
  archive_sha256: string;
  archive_size_bytes: number;
  generated_at: string;
  expires_at: string;
  creatable: true;
  external_transfer_performed: false;
  active_restore_performed: false;
  secret_export_performed: false;
  network_request_performed: false;
  infrastructure_mutation_performed: false;
};

export type LogicalBackup = {
  backup_id: string;
  state: "completed";
  source_run_id: string;
  source_run_version: number;
  preview_digest: string;
  target_id: string;
  archive_sha256: string;
  archive_size_bytes: number;
  archive_name: string;
  entry_count: number;
  created_at: string;
  expires_at: string;
  reused: boolean;
  external_transfer_performed: false;
  active_restore_performed: false;
};

export type RestoreValidation = {
  validation_id: string;
  state: "passed";
  backup_id: string;
  archive_sha256: string;
  validation_digest: string;
  check_ids: string[];
  entry_count: number;
  validated_at: string;
  isolated_target: true;
  active_repository_write_performed: false;
  operational_recovery_performed: false;
  secret_restore_performed: false;
  network_request_performed: false;
  reused: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isPreview(value: unknown): value is { data: BackupPreview } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return item.schema_version === "atlas.logical-backup-preview.v1" &&
    item.catalog_version === "atlas.synthetic-logical-backup-catalog.v1" &&
    typeof item.preview_id === "string" && typeof item.source_run_id === "string" &&
    typeof item.source_run_version === "number" && Array.isArray(item.component_ids) &&
    Array.isArray(item.entries) && item.entries.every((entry) => isRecord(entry) &&
      typeof entry.entry_id === "string" && typeof entry.sha256 === "string") &&
    typeof item.preview_digest === "string" && typeof item.archive_sha256 === "string" &&
    typeof item.archive_size_bytes === "number" &&
    (item.target_state === "empty" || item.target_state === "reusable") &&
    item.creatable === true && item.external_transfer_performed === false &&
    item.active_restore_performed === false && item.secret_export_performed === false &&
    item.network_request_performed === false && item.infrastructure_mutation_performed === false;
}

function isBackup(value: unknown): value is { data: LogicalBackup } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return typeof item.backup_id === "string" && item.state === "completed" &&
    typeof item.archive_sha256 === "string" && typeof item.archive_name === "string" &&
    typeof item.archive_size_bytes === "number" && typeof item.entry_count === "number" &&
    item.external_transfer_performed === false && item.active_restore_performed === false;
}

function isValidation(value: unknown): value is { data: RestoreValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const item = value.data;
  return typeof item.validation_id === "string" && item.state === "passed" &&
    typeof item.validation_digest === "string" && Array.isArray(item.check_ids) &&
    item.check_ids.length === 6 && item.isolated_target === true &&
    item.active_repository_write_performed === false &&
    item.operational_recovery_performed === false && item.secret_restore_performed === false &&
    item.network_request_performed === false;
}

function nonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
}

export async function previewLogicalBackup(sourceRunId: string, componentIds: string[]) {
  const response = await apiFetch("/api/v1/platform/backups/preview", {
    method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ schema_version: "atlas.logical-backup-preview-request.v1",
      source_run_id: sourceRunId, component_ids: componentIds }),
  });
  if (!response.ok) throw new Error(`Backup preview failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isPreview(payload)) throw new Error("Backup preview returned unsafe data");
  return payload;
}

export async function createLogicalBackup(preview: BackupPreview, justification: string) {
  const response = await apiFetch(`/api/v1/platform/backups/${preview.source_run_id}`, {
    method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json",
      "Idempotency-Key": `logical-backup.${preview.source_run_version}.${nonce()}` },
    body: JSON.stringify({ schema_version: "atlas.logical-backup-create-request.v1",
      source_run_version: preview.source_run_version, component_ids: preview.component_ids,
      preview_digest: preview.preview_digest, archive_sha256: preview.archive_sha256,
      target_id: preview.target_id, expected_target_state: preview.target_state,
      justification, confirmed: true }),
  });
  if (!response.ok) throw new Error(`Backup creation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isBackup(payload)) throw new Error("Backup creation returned unsafe data");
  return payload;
}

export async function validateLogicalRestore(backup: LogicalBackup) {
  const response = await apiFetch(
    `/api/v1/platform/backups/${backup.backup_id}/restore-validations`, {
      method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json",
        "Idempotency-Key": `restore-validation.${backup.source_run_version}.${nonce()}` },
      body: JSON.stringify({ schema_version: "atlas.isolated-restore-validation-request.v1",
        archive_sha256: backup.archive_sha256, confirmed_isolated: true }),
    });
  if (!response.ok) throw new Error(`Restore validation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isValidation(payload)) throw new Error("Restore validation returned unsafe data");
  return payload;
}
