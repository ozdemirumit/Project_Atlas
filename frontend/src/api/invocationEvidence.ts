import type { ConnectorBoundedInvocationInventoryItem } from "./boundedInvocations";
import { ApiRequestError, apiFetch } from "./client";

export type ConnectorInvocationEvidenceInventoryItem = {
  ingestion_id: string;
  schema_version: "atlas.connector-invocation-evidence-ingestion.v1";
  version: 1;
  source_invocation_id: string;
  source_invocation_digest: string;
  package_digest: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  normalized_redacted_result_digest: string;
  evidence_package_id: string;
  evidence_schema_version: string;
  evidence_content_digest: string;
  evidence_metadata_digest: string;
  classification: string;
  retention_policy_id: string;
  retention_policy_digest: string;
  ingestion_policy_id: string;
  ingestion_policy_digest: string;
  ingestion_policy_version: string;
  evidence_item_count: number;
  evidence_bytes: number;
  observed_from: string;
  observed_to: string;
  ingested_at: string;
  instance_state: "enabled_invocation_evidence_ingested";
  canonical_digest: string;
  source_invocation_completed: true;
  evidence_ingested: true;
  immutable_storage_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  knowledge_item_created: false;
  retrieval_published: false;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorInvocationEvidenceOption = {
  source_invocation_id: string;
  source_invocation_digest: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  ingestion_policy_id: string;
  ingestion_policy_digest: string;
  ingestion_policy_version: string;
  ingestion_policy_expires_at: string;
  classification: string;
  retention_policy_id: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  maximum_evidence_items: number;
  maximum_evidence_bytes: number;
  resulting_instance_state: "enabled_invocation_evidence_ingested";
  irreversible_claim_required: true;
  automatic_retry_allowed: false;
  knowledge_item_created: false;
  retrieval_published: false;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

// Retained for the later evidence-to-knowledge migration, which still consumes the internal record.
export type ConnectorInvocationEvidence = ConnectorInvocationEvidenceInventoryItem & {
  claim_id: string;
  organization_id: string;
  environment_id: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  output_schema_digest: string;
  result_policy_digest: string;
  access_policy_id: string;
  access_policy_digest: string;
  encryption_profile_id: string;
  encryption_profile_digest: string;
  ingestion_adapter_id: string;
  ingested_by: string;
  purpose: string;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const inventoryFields = new Set([
  "ingestion_id", "schema_version", "version", "source_invocation_id",
  "source_invocation_digest", "package_digest", "capability_id", "capability_class",
  "required_permission", "normalized_redacted_result_digest", "evidence_package_id",
  "evidence_schema_version", "evidence_content_digest", "evidence_metadata_digest",
  "classification", "retention_policy_id", "retention_policy_digest", "ingestion_policy_id",
  "ingestion_policy_digest", "ingestion_policy_version", "evidence_item_count",
  "evidence_bytes", "observed_from", "observed_to", "ingested_at", "instance_state",
  "canonical_digest", "source_invocation_completed", "evidence_ingested",
  "immutable_storage_confirmed", "encrypted_at_rest", "transient_buffers_erased",
  "artifact_channel_closed", "knowledge_item_created", "retrieval_published",
  "model_context_available", "graph_updated", "scheduled", "workflow_continued",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed", "reused",
]);
const optionFields = new Set([
  "source_invocation_id", "source_invocation_digest", "capability_id",
  "capability_class", "required_permission",
  "ingestion_policy_id", "ingestion_policy_digest", "ingestion_policy_version",
  "ingestion_policy_expires_at", "classification", "retention_policy_id",
  "required_assurance_level",
  "maximum_evidence_items", "maximum_evidence_bytes", "resulting_instance_state",
  "irreversible_claim_required", "automatic_retry_allowed", "knowledge_item_created",
  "retrieval_published", "model_context_available", "graph_updated", "scheduled",
  "workflow_continued", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function envelopeData(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    throw new Error("Invocation evidence response envelope is unsafe");
  }
  const envelope = payload as Record<string, unknown>;
  if (!hasExactFields(envelope, new Set(["data", "meta"]))) {
    throw new Error("Invocation evidence response envelope is unsafe");
  }
  const meta = envelope.meta;
  if (!meta || typeof meta !== "object" ||
    !hasExactFields(meta as Record<string, unknown>, new Set(["correlation_id", "generated_at"]))) {
    throw new Error("Invocation evidence response envelope is unsafe");
  }
  const responseMeta = meta as Record<string, unknown>;
  if (typeof responseMeta.correlation_id !== "string" ||
    responseMeta.correlation_id.length < 1 || responseMeta.correlation_id.length > 128 ||
    !isTimestamp(responseMeta.generated_at)) {
    throw new Error("Invocation evidence response envelope is unsafe");
  }
  return envelope.data;
}

function hasPreservedBoundary(record: Record<string, unknown>): boolean {
  return record.source_invocation_completed === true && record.evidence_ingested === true &&
    record.immutable_storage_confirmed === true && record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true && record.artifact_channel_closed === true &&
    record.knowledge_item_created === false && record.retrieval_published === false &&
    record.model_context_available === false && record.graph_updated === false &&
    record.scheduled === false && record.workflow_continued === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function hasSafeOptionBoundary(record: Record<string, unknown>): boolean {
  return record.irreversible_claim_required === true && record.automatic_retry_allowed === false &&
    record.knowledge_item_created === false && record.retrieval_published === false &&
    record.model_context_available === false && record.graph_updated === false &&
    record.scheduled === false && record.workflow_continued === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is ConnectorInvocationEvidenceInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "ingestion_id", "source_invocation_id", "capability_id", "required_permission",
    "evidence_package_id", "evidence_schema_version", "classification", "retention_policy_id",
    "ingestion_policy_id", "ingestion_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.connector-invocation-evidence-ingestion.v1" &&
    record.version === 1 && (record.capability_class === "C0" || record.capability_class === "C1") &&
    [
      "source_invocation_digest", "package_digest", "normalized_redacted_result_digest",
      "evidence_content_digest", "evidence_metadata_digest", "retention_policy_digest",
      "ingestion_policy_digest", "canonical_digest",
    ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    Number.isInteger(record.evidence_item_count) && (record.evidence_item_count as number) >= 1 &&
    (record.evidence_item_count as number) <= 1000 && Number.isInteger(record.evidence_bytes) &&
    (record.evidence_bytes as number) >= 0 && (record.evidence_bytes as number) <= 1_048_576 &&
    isTimestamp(record.observed_from) && isTimestamp(record.observed_to) &&
    isTimestamp(record.ingested_at) && Date.parse(record.observed_to) >=
      Date.parse(record.observed_from) && Date.parse(record.ingested_at) >=
      Date.parse(record.observed_to) &&
    record.instance_state === "enabled_invocation_evidence_ingested" &&
    typeof record.reused === "boolean" && hasPreservedBoundary(record);
}

function isOption(value: unknown): value is ConnectorInvocationEvidenceOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_invocation_id", "capability_id", "required_permission", "ingestion_policy_id",
    "ingestion_policy_version", "classification", "retention_policy_id",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_invocation_digest", "ingestion_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    (record.capability_class === "C0" || record.capability_class === "C1") &&
    isTimestamp(record.ingestion_policy_expires_at) &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    Number.isInteger(record.maximum_evidence_items) &&
    (record.maximum_evidence_items as number) >= 1 &&
    (record.maximum_evidence_items as number) <= 1000 &&
    Number.isInteger(record.maximum_evidence_bytes) &&
    (record.maximum_evidence_bytes as number) >= 1 &&
    (record.maximum_evidence_bytes as number) <= 1_048_576 &&
    record.resulting_instance_state === "enabled_invocation_evidence_ingested" &&
    hasSafeOptionBoundary(record);
}

export async function getConnectorInvocationEvidence(input: {
  sourceInvocationId: string;
}): Promise<ConnectorInvocationEvidenceInventoryItem[]> {
  const sourceId = input.sourceInvocationId;
  if (!stableId.test(sourceId)) throw new Error("Exact bounded-invocation scope is required");
  const parameters = new URLSearchParams({ source_invocation_id: sourceId });
  const response = await apiFetch(
    `/api/v1/connectors/invocation-evidence?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Invocation evidence inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = envelopeData(payload);
  if (!Array.isArray(data)) throw new Error("Invocation evidence inventory returned unsafe records");
  const records: ConnectorInvocationEvidenceInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Invocation evidence inventory returned unsafe records");
    }
    if (candidate.source_invocation_id !== sourceId) {
      throw new Error("Invocation evidence inventory crossed the requested invocation scope");
    }
    records.push(candidate);
  }
  return records;
}

export async function getConnectorInvocationEvidenceOptions(
  sourceInvocationId: string,
): Promise<ConnectorInvocationEvidenceOption[]> {
  if (!stableId.test(sourceInvocationId)) {
    throw new Error("Exact bounded-invocation scope is required");
  }
  const parameters = new URLSearchParams({ source_invocation_id: sourceInvocationId });
  const response = await apiFetch(
    `/api/v1/connectors/invocation-evidence/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Invocation evidence options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = envelopeData(payload);
  if (!Array.isArray(data)) throw new Error("Invocation evidence options returned unsafe evidence");
  const options: ConnectorInvocationEvidenceOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_invocation_id !== sourceInvocationId) {
      throw new Error("Invocation evidence options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorInvocationEvidence(input: {
  invocation: ConnectorBoundedInvocationInventoryItem;
  option: ConnectorInvocationEvidenceOption;
  purpose: string;
}) {
  const { invocation, option, purpose } = input;
  if (!invocation.authorization_consumed || !invocation.capability_invoked ||
    !invocation.result_validated || !invocation.result_redacted ||
    !invocation.target_session_closed || !invocation.lease_revocation_confirmed ||
    invocation.target_connected || invocation.evidence_ingested ||
    invocation.instance_state !== "enabled_bounded_capability_invocation_completed" ||
    option.source_invocation_id !== invocation.invocation_id ||
    option.source_invocation_digest !== invocation.canonical_digest ||
    option.capability_id !== invocation.capability_id ||
    option.capability_class !== invocation.capability_class ||
    option.required_permission !== invocation.required_permission ||
    purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact current invocation-evidence option is required");
  }
  const response = await apiFetch("/api/v1/connectors/invocation-evidence", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-invocation-evidence.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-invocation-evidence-input.v1",
      source_invocation_id: option.source_invocation_id,
      source_invocation_digest: option.source_invocation_digest,
      ingestion_policy_id: option.ingestion_policy_id,
      ingestion_policy_digest: option.ingestion_policy_digest,
      purpose: purpose.trim(),
      acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Connector invocation evidence ingestion failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = envelopeData(payload);
  if (!isInventoryItem(data)) throw new Error("Invocation evidence returned unsafe metadata");
  if (data.source_invocation_id !== invocation.invocation_id ||
    data.source_invocation_digest !== invocation.canonical_digest ||
    data.package_digest !== invocation.package_digest || data.capability_id !== invocation.capability_id ||
    data.capability_class !== invocation.capability_class ||
    data.required_permission !== invocation.required_permission ||
    data.normalized_redacted_result_digest !== invocation.normalized_redacted_result_digest ||
    data.ingestion_policy_id !== option.ingestion_policy_id ||
    data.ingestion_policy_digest !== option.ingestion_policy_digest ||
    data.classification !== option.classification ||
    data.retention_policy_id !== option.retention_policy_id) {
    throw new Error("Invocation evidence does not match the exact governed result");
  }
  return { data };
}
