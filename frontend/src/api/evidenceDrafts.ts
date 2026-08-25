import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorInvocationEvidenceInventoryItem } from "./invocationEvidence";

// Retained for the separate review-request UI, which consumes the internal detail endpoint.
export type OperationalEvidenceKnowledgeDraft = {
  draft_id: string;
  schema_version: "atlas.operational-evidence-knowledge-draft.v1";
  version: 1;
  claim_id: string;
  source_ingestion_id: string;
  source_ingestion_digest: string;
  organization_id: string;
  environment_id: string;
  source_invocation_id: string;
  evidence_package_id: string;
  evidence_content_digest: string;
  evidence_metadata_digest: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  draft_artifact_id: string;
  draft_schema_version: string;
  title: string;
  draft_domain: "domain.operational";
  content_type: string;
  source_authority: "source-authority.system-generated";
  language: string;
  knowledge_lifecycle: "draft";
  classification: string;
  access_policy_id: string;
  access_policy_digest: string;
  retention_policy_id: string;
  retention_policy_digest: string;
  encryption_profile_id: string;
  encryption_profile_digest: string;
  draft_content_digest: string;
  draft_metadata_digest: string;
  provenance_digest: string;
  draft_access_digest: string;
  draft_retention_digest: string;
  curation_policy_id: string;
  curation_policy_digest: string;
  curation_policy_version: string;
  curation_adapter_id: string;
  draft_item_count: number;
  draft_bytes: number;
  observed_from: string;
  observed_to: string;
  created_at: string;
  instance_state: "draft_operational_knowledge_created";
  curated_by: string;
  purpose: string;
  canonical_digest: string;
  evidence_ingested: boolean;
  knowledge_item_created: boolean;
  immutable_draft_confirmed: boolean;
  encrypted_at_rest: boolean;
  transient_buffers_erased: boolean;
  artifact_channel_closed: boolean;
  domain_review_completed: boolean;
  security_review_completed: boolean;
  knowledge_approved: boolean;
  knowledge_published: boolean;
  chunks_created: boolean;
  embeddings_created: boolean;
  retrieval_published: boolean;
  model_context_available: boolean;
  graph_updated: boolean;
  scheduled: boolean;
  workflow_continued: boolean;
  execution_authorized: boolean;
  deployment_approved: boolean;
  infrastructure_mutation_performed: boolean;
  reused: boolean;
};

export type OperationalEvidenceKnowledgeDraftInventoryItem = {
  draft_id: string;
  schema_version: "atlas.operational-evidence-knowledge-draft.v1";
  version: 1;
  source_ingestion_id: string;
  source_ingestion_digest: string;
  evidence_package_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  knowledge_lifecycle: "draft";
  classification: string;
  retention_policy_id: string;
  retention_policy_digest: string;
  curation_policy_id: string;
  curation_policy_digest: string;
  curation_policy_version: string;
  draft_item_count: number;
  draft_bytes: number;
  observed_from: string;
  observed_to: string;
  created_at: string;
  instance_state: "draft_operational_knowledge_created";
  canonical_digest: string;
  evidence_ingested: true;
  knowledge_item_created: true;
  immutable_draft_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  domain_review_completed: false;
  security_review_completed: false;
  knowledge_approved: false;
  knowledge_published: false;
  chunks_created: false;
  embeddings_created: false;
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

export type OperationalEvidenceKnowledgeDraftOption = {
  curation_option_id: string;
  source_ingestion_id: string;
  source_ingestion_digest: string;
  evidence_package_id: string;
  capability_id: string;
  curation_policy_id: string;
  curation_policy_digest: string;
  curation_policy_version: string;
  curation_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  maximum_draft_items: number;
  maximum_draft_bytes: number;
  resulting_instance_state: "draft_operational_knowledge_created";
  irreversible_claim_required: true;
  automatic_retry_allowed: false;
  review_requested: false;
  knowledge_approved: false;
  knowledge_published: false;
  retrieval_published: false;
  model_context_available: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const envelopeFields = new Set(["data", "meta"]);
const metaFields = new Set(["correlation_id", "generated_at"]);
const inventoryFields = new Set([
  "draft_id", "schema_version", "version", "source_ingestion_id",
  "source_ingestion_digest", "evidence_package_id", "connector_id", "instance_id",
  "capability_id", "title", "knowledge_lifecycle", "classification",
  "retention_policy_id", "retention_policy_digest", "curation_policy_id",
  "curation_policy_digest", "curation_policy_version", "draft_item_count", "draft_bytes",
  "observed_from", "observed_to", "created_at", "instance_state", "canonical_digest",
  "evidence_ingested", "knowledge_item_created", "immutable_draft_confirmed",
  "encrypted_at_rest", "transient_buffers_erased", "artifact_channel_closed",
  "domain_review_completed", "security_review_completed", "knowledge_approved",
  "knowledge_published", "chunks_created", "embeddings_created", "retrieval_published",
  "model_context_available", "graph_updated", "scheduled", "workflow_continued",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed", "reused",
]);
const optionFields = new Set([
  "curation_option_id", "source_ingestion_id", "source_ingestion_digest",
  "evidence_package_id", "capability_id", "curation_policy_id", "curation_policy_digest",
  "curation_policy_version", "curation_policy_expires_at", "required_assurance_level",
  "classification", "access_policy_id", "retention_policy_id", "maximum_draft_items",
  "maximum_draft_bytes", "resulting_instance_state", "irreversible_claim_required",
  "automatic_retry_allowed", "review_requested", "knowledge_approved", "knowledge_published",
  "retrieval_published", "model_context_available", "scheduled", "workflow_continued",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);

export function operationalEvidenceKnowledgeDraftQueryKey(
  sessionScopeKey: string,
  ingestionId: string,
) {
  return ["operational-evidence-knowledge-drafts", sessionScopeKey, ingestionId] as const;
}

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function envelopeData(payload: unknown): unknown {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Knowledge draft response envelope is unsafe");
  }
  const envelope = payload as Record<string, unknown>;
  if (!hasExactFields(envelope, envelopeFields)) {
    throw new Error("Knowledge draft response envelope is unsafe");
  }
  const meta = envelope.meta;
  if (!meta || typeof meta !== "object" || Array.isArray(meta) ||
    !hasExactFields(meta as Record<string, unknown>, metaFields)) {
    throw new Error("Knowledge draft response envelope is unsafe");
  }
  const responseMeta = meta as Record<string, unknown>;
  if (typeof responseMeta.correlation_id !== "string" ||
    responseMeta.correlation_id.length < 1 || responseMeta.correlation_id.length > 128 ||
    !isTimestamp(responseMeta.generated_at)) {
    throw new Error("Knowledge draft response envelope is unsafe");
  }
  return envelope.data;
}

function hasDraftBoundary(record: Record<string, unknown>): boolean {
  return record.evidence_ingested === true && record.knowledge_item_created === true &&
    record.immutable_draft_confirmed === true && record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true && record.artifact_channel_closed === true &&
    record.domain_review_completed === false && record.security_review_completed === false &&
    record.knowledge_approved === false && record.knowledge_published === false &&
    record.chunks_created === false && record.embeddings_created === false &&
    record.retrieval_published === false && record.model_context_available === false &&
    record.graph_updated === false && record.scheduled === false &&
    record.workflow_continued === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is OperationalEvidenceKnowledgeDraftInventoryItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) &&
    ["draft_id", "source_ingestion_id", "evidence_package_id", "connector_id", "instance_id",
      "capability_id", "classification", "retention_policy_id", "curation_policy_id"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.operational-evidence-knowledge-draft.v1" &&
    record.version === 1 && typeof record.title === "string" && record.title.length > 0 &&
    typeof record.curation_policy_version === "string" &&
    ["source_ingestion_digest", "retention_policy_digest", "curation_policy_digest",
      "canonical_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    Number.isInteger(record.draft_item_count) && (record.draft_item_count as number) >= 0 &&
    Number.isInteger(record.draft_bytes) && (record.draft_bytes as number) >= 0 &&
    isTimestamp(record.observed_from) && isTimestamp(record.observed_to) &&
    isTimestamp(record.created_at) && record.knowledge_lifecycle === "draft" &&
    record.instance_state === "draft_operational_knowledge_created" &&
    typeof record.reused === "boolean" && hasDraftBoundary(record);
}

function hasOptionBoundary(record: Record<string, unknown>): boolean {
  return record.irreversible_claim_required === true && record.automatic_retry_allowed === false &&
    record.review_requested === false && record.knowledge_approved === false &&
    record.knowledge_published === false && record.retrieval_published === false &&
    record.model_context_available === false && record.scheduled === false &&
    record.workflow_continued === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isOption(value: unknown): value is OperationalEvidenceKnowledgeDraftOption {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) &&
    ["curation_option_id", "source_ingestion_id", "evidence_package_id", "capability_id",
      "curation_policy_id", "classification", "access_policy_id", "retention_policy_id"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    ["source_ingestion_digest", "curation_policy_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    typeof record.curation_policy_version === "string" &&
    isTimestamp(record.curation_policy_expires_at) &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    Number.isInteger(record.maximum_draft_items) && (record.maximum_draft_items as number) >= 1 &&
    Number.isInteger(record.maximum_draft_bytes) && (record.maximum_draft_bytes as number) >= 1 &&
    record.resulting_instance_state === "draft_operational_knowledge_created" &&
    hasOptionBoundary(record);
}

function assertEvidenceReady(evidence: ConnectorInvocationEvidenceInventoryItem): void {
  if (!evidence.evidence_ingested || !evidence.immutable_storage_confirmed ||
    evidence.knowledge_item_created || evidence.retrieval_published ||
    evidence.instance_state !== "enabled_invocation_evidence_ingested") {
    throw new Error("Completed uncurated operational evidence is required");
  }
}

function matchesEvidence(
  candidate: OperationalEvidenceKnowledgeDraftInventoryItem,
  evidence: ConnectorInvocationEvidenceInventoryItem,
): boolean {
  return candidate.source_ingestion_id === evidence.ingestion_id &&
    candidate.source_ingestion_digest === evidence.canonical_digest &&
    candidate.evidence_package_id === evidence.evidence_package_id &&
    candidate.capability_id === evidence.capability_id &&
    candidate.classification === evidence.classification &&
    candidate.retention_policy_id === evidence.retention_policy_id &&
    candidate.retention_policy_digest === evidence.retention_policy_digest;
}

function matchesOption(
  option: OperationalEvidenceKnowledgeDraftOption,
  evidence: ConnectorInvocationEvidenceInventoryItem,
): boolean {
  return option.source_ingestion_id === evidence.ingestion_id &&
    option.source_ingestion_digest === evidence.canonical_digest &&
    option.evidence_package_id === evidence.evidence_package_id &&
    option.capability_id === evidence.capability_id &&
    option.classification === evidence.classification &&
    option.retention_policy_id === evidence.retention_policy_id;
}

export async function getOperationalEvidenceKnowledgeDrafts(input: {
  evidence: ConnectorInvocationEvidenceInventoryItem;
}): Promise<OperationalEvidenceKnowledgeDraftInventoryItem[]> {
  assertEvidenceReady(input.evidence);
  const parameters = new URLSearchParams({ source_ingestion_id: input.evidence.ingestion_id });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-evidence-drafts?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Knowledge draft inventory failed", response.status);
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) throw new Error("Knowledge draft inventory returned unsafe records");
  const records: OperationalEvidenceKnowledgeDraftInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate) || !matchesEvidence(candidate, input.evidence)) {
      throw new Error("Knowledge draft inventory returned unsafe records");
    }
    records.push(candidate);
  }
  if (records.length > 1) throw new Error("Knowledge draft inventory returned duplicate records");
  return records;
}

export async function getOperationalEvidenceKnowledgeDraftOptions(input: {
  evidence: ConnectorInvocationEvidenceInventoryItem;
}): Promise<OperationalEvidenceKnowledgeDraftOption[]> {
  assertEvidenceReady(input.evidence);
  const parameters = new URLSearchParams({ source_ingestion_id: input.evidence.ingestion_id });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-evidence-drafts/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Knowledge draft options failed", response.status);
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) throw new Error("Knowledge draft options returned unsafe records");
  const options: OperationalEvidenceKnowledgeDraftOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || !matchesOption(candidate, input.evidence)) {
      throw new Error("Knowledge draft options returned unsafe records");
    }
    options.push(candidate);
  }
  return options;
}

export async function createOperationalEvidenceKnowledgeDraft(input: {
  evidence: ConnectorInvocationEvidenceInventoryItem;
  option: OperationalEvidenceKnowledgeDraftOption;
  purpose: string;
}): Promise<{ data: OperationalEvidenceKnowledgeDraftInventoryItem }> {
  const { evidence, option, purpose } = input;
  assertEvidenceReady(evidence);
  if (!matchesOption(option, evidence) || purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact current knowledge-draft option is required");
  }
  const response = await apiFetch("/api/v1/knowledge/operational-evidence-drafts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-evidence-knowledge-draft.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-evidence-knowledge-draft-input.v1",
      source_ingestion_id: evidence.ingestion_id,
      curation_option_id: option.curation_option_id,
      purpose: purpose.trim(),
      acknowledged_result_is_an_unapproved_non_retrievable_draft: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Operational evidence knowledge draft failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!isInventoryItem(data) || !matchesEvidence(data, evidence) ||
    data.curation_policy_id !== option.curation_policy_id ||
    data.curation_policy_digest !== option.curation_policy_digest ||
    data.curation_policy_version !== option.curation_policy_version) {
    throw new Error("Knowledge draft returned unsafe metadata");
  }
  return { data };
}
