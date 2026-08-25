import { ApiRequestError, apiFetch } from "./client";
import type { OperationalEvidenceKnowledgeDraftInventoryItem } from "./evidenceDrafts";

export type OperationalKnowledgeReviewRequest = {
  review_request_id: string;
  schema_version: "atlas.operational-knowledge-review-request.v1";
  version: 1;
  source_draft_id: string;
  source_draft_digest: string;
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  source_ingestion_id: string;
  source_invocation_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  draft_domain: "domain.operational";
  content_type: string;
  language: string;
  knowledge_lifecycle: "review_requested";
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  manifest_id: string;
  orchestration_policy_id: string;
  orchestration_policy_digest: string;
  domain_track_code: "review-track.domain";
  security_track_code: "review-track.security";
  domain_queue_id: string;
  security_queue_id: string;
  assignment_strategy: "assignment-strategy.policy-controlled";
  sla_class: string;
  domain_status: "awaiting_reviewer";
  security_status: "awaiting_reviewer";
  created_at: string;
  instance_state: "operational_knowledge_review_requested";
  canonical_digest: string;
  review_requested: true;
  immutable_manifest_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  reviewer_assigned: false;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
  correction_created: false;
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

export type ReviewableOperationalEvidenceKnowledgeDraft = Pick<
  OperationalEvidenceKnowledgeDraftInventoryItem,
  | "draft_id"
  | "canonical_digest"
  | "connector_id"
  | "instance_id"
  | "capability_id"
  | "title"
  | "classification"
  | "retention_policy_id"
  | "retention_policy_digest"
  | "knowledge_lifecycle"
  | "instance_state"
  | "knowledge_item_created"
  | "immutable_draft_confirmed"
  | "domain_review_completed"
  | "security_review_completed"
  | "review_requested"
  | "knowledge_approved"
  | "knowledge_published"
  | "retrieval_published"
  | "model_context_available"
  | "scheduled"
  | "workflow_continued"
  | "execution_authorized"
  | "deployment_approved"
  | "infrastructure_mutation_performed"
>;

export type OperationalKnowledgeReviewRequestInventoryItem = {
  review_request_id: string;
  schema_version: "atlas.operational-knowledge-review-request.v1";
  version: 1;
  source_draft_id: string;
  source_draft_digest: string;
  knowledge_item_id: string;
  draft_version_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  knowledge_lifecycle: "review_requested";
  classification: string;
  retention_policy_id: string;
  retention_policy_digest: string;
  orchestration_policy_id: string;
  orchestration_policy_digest: string;
  orchestration_policy_version: string;
  domain_track_code: string;
  security_track_code: string;
  assignment_strategy: string;
  sla_class: string;
  domain_status: "awaiting_reviewer";
  security_status: "awaiting_reviewer";
  manifest_bytes: number;
  created_at: string;
  instance_state: "operational_knowledge_review_requested";
  canonical_digest: string;
  review_requested: true;
  immutable_manifest_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  reviewer_assigned: false;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
  correction_created: false;
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

export type OperationalKnowledgeReviewRequestOption = {
  review_request_option_id: string;
  source_draft_id: string;
  source_draft_digest: string;
  knowledge_item_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  orchestration_policy_id: string;
  orchestration_policy_digest: string;
  orchestration_policy_version: string;
  orchestration_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  classification: string;
  retention_policy_id: string;
  domain_track_code: string;
  security_track_code: string;
  assignment_strategy: string;
  sla_class: string;
  resulting_instance_state: "operational_knowledge_review_requested";
  resulting_domain_status: "awaiting_reviewer";
  resulting_security_status: "awaiting_reviewer";
  irreversible_claim_required: true;
  automatic_retry_allowed: false;
  review_requested: true;
  reviewer_assigned: false;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
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
  "review_request_id", "schema_version", "version", "source_draft_id",
  "source_draft_digest", "knowledge_item_id", "draft_version_id", "connector_id",
  "instance_id", "capability_id", "title",
  "knowledge_lifecycle", "classification", "retention_policy_id", "retention_policy_digest",
  "orchestration_policy_id", "orchestration_policy_digest", "orchestration_policy_version",
  "domain_track_code", "security_track_code", "assignment_strategy", "sla_class",
  "domain_status", "security_status", "manifest_bytes", "created_at", "instance_state",
  "canonical_digest",
  "review_requested", "immutable_manifest_confirmed", "encrypted_at_rest",
  "transient_buffers_erased", "artifact_channel_closed", "reviewer_assigned",
  "content_inspection_opened", "domain_review_completed", "security_review_completed",
  "correction_created", "knowledge_approved", "knowledge_published", "chunks_created",
  "embeddings_created", "retrieval_published", "model_context_available", "graph_updated",
  "scheduled", "workflow_continued", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed", "reused",
]);
const optionFields = new Set([
  "review_request_option_id", "source_draft_id", "source_draft_digest", "knowledge_item_id",
  "connector_id", "instance_id", "capability_id", "orchestration_policy_id",
  "orchestration_policy_digest",
  "orchestration_policy_version", "orchestration_policy_expires_at",
  "required_assurance_level", "classification", "retention_policy_id", "domain_track_code",
  "security_track_code", "assignment_strategy", "sla_class", "resulting_instance_state",
  "resulting_domain_status", "resulting_security_status", "irreversible_claim_required",
  "automatic_retry_allowed",
  "review_requested", "reviewer_assigned", "content_inspection_opened",
  "domain_review_completed", "security_review_completed",
  "knowledge_approved", "knowledge_published", "retrieval_published",
  "model_context_available", "scheduled", "workflow_continued", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed",
]);

export function operationalKnowledgeReviewRequestQueryKey(
  sessionScopeKey: string,
  draftId: string,
) {
  return ["operational-knowledge-review-requests", sessionScopeKey, draftId] as const;
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
    throw new Error("Knowledge review request response envelope is unsafe");
  }
  const envelope = payload as Record<string, unknown>;
  if (!hasExactFields(envelope, envelopeFields)) {
    throw new Error("Knowledge review request response envelope is unsafe");
  }
  const meta = envelope.meta;
  if (!meta || typeof meta !== "object" || Array.isArray(meta) ||
    !hasExactFields(meta as Record<string, unknown>, metaFields)) {
    throw new Error("Knowledge review request response envelope is unsafe");
  }
  const responseMeta = meta as Record<string, unknown>;
  if (typeof responseMeta.correlation_id !== "string" ||
    responseMeta.correlation_id.length < 1 || responseMeta.correlation_id.length > 128 ||
    !isTimestamp(responseMeta.generated_at)) {
    throw new Error("Knowledge review request response envelope is unsafe");
  }
  return envelope.data;
}

function hasReviewRequestBoundary(record: Record<string, unknown>): boolean {
  return record.review_requested === true && record.immutable_manifest_confirmed === true &&
    record.encrypted_at_rest === true && record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true && record.reviewer_assigned === false &&
    record.content_inspection_opened === false && record.domain_review_completed === false &&
    record.security_review_completed === false && record.correction_created === false &&
    record.knowledge_approved === false && record.knowledge_published === false &&
    record.chunks_created === false && record.embeddings_created === false &&
    record.retrieval_published === false && record.model_context_available === false &&
    record.graph_updated === false && record.scheduled === false &&
    record.workflow_continued === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is OperationalKnowledgeReviewRequestInventoryItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) &&
    ["review_request_id", "source_draft_id", "knowledge_item_id", "draft_version_id",
      "connector_id", "instance_id", "capability_id", "classification", "retention_policy_id",
      "orchestration_policy_id", "domain_track_code", "security_track_code",
      "assignment_strategy", "sla_class"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.operational-knowledge-review-request.v1" &&
    record.version === 1 && typeof record.title === "string" && record.title.length > 0 &&
    record.title.length <= 512 && typeof record.orchestration_policy_version === "string" &&
    record.orchestration_policy_version.length > 0 &&
    ["source_draft_digest", "retention_policy_digest", "orchestration_policy_digest",
      "canonical_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    record.knowledge_lifecycle === "review_requested" &&
    record.domain_status === "awaiting_reviewer" && record.security_status === "awaiting_reviewer" &&
    Number.isInteger(record.manifest_bytes) && (record.manifest_bytes as number) >= 0 &&
    record.instance_state === "operational_knowledge_review_requested" &&
    isTimestamp(record.created_at) && typeof record.reused === "boolean" &&
    hasReviewRequestBoundary(record);
}

function hasReviewOptionBoundary(record: Record<string, unknown>): boolean {
  return record.irreversible_claim_required === true && record.automatic_retry_allowed === false &&
    record.review_requested === true && record.reviewer_assigned === false &&
    record.content_inspection_opened === false && record.domain_review_completed === false &&
    record.security_review_completed === false &&
    record.knowledge_approved === false && record.knowledge_published === false &&
    record.retrieval_published === false && record.model_context_available === false &&
    record.scheduled === false && record.workflow_continued === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function isOption(value: unknown): value is OperationalKnowledgeReviewRequestOption {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) &&
    ["review_request_option_id", "source_draft_id", "knowledge_item_id", "connector_id",
      "instance_id", "capability_id", "orchestration_policy_id", "classification",
      "retention_policy_id", "domain_track_code", "security_track_code", "assignment_strategy",
      "sla_class"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    ["source_draft_digest", "orchestration_policy_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    typeof record.orchestration_policy_version === "string" &&
    record.orchestration_policy_version.length > 0 &&
    isTimestamp(record.orchestration_policy_expires_at) &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    record.resulting_instance_state === "operational_knowledge_review_requested" &&
    record.resulting_domain_status === "awaiting_reviewer" &&
    record.resulting_security_status === "awaiting_reviewer" &&
    hasReviewOptionBoundary(record);
}

function assertReviewableDraft(draft: ReviewableOperationalEvidenceKnowledgeDraft): void {
  if (!draft.knowledge_item_created || !draft.immutable_draft_confirmed ||
    draft.knowledge_lifecycle !== "draft" ||
    draft.instance_state !== "draft_operational_knowledge_created" ||
    draft.domain_review_completed || draft.security_review_completed || draft.review_requested ||
    draft.knowledge_approved || draft.knowledge_published || draft.retrieval_published ||
    draft.model_context_available || draft.scheduled || draft.workflow_continued ||
    draft.execution_authorized || draft.deployment_approved ||
    draft.infrastructure_mutation_performed) {
    throw new Error("An exact unreviewed immutable knowledge draft is required");
  }
}

function matchesDraft(
  candidate: OperationalKnowledgeReviewRequestInventoryItem,
  draft: ReviewableOperationalEvidenceKnowledgeDraft,
): boolean {
  return candidate.source_draft_id === draft.draft_id &&
    candidate.source_draft_digest === draft.canonical_digest &&
    candidate.connector_id === draft.connector_id && candidate.instance_id === draft.instance_id &&
    candidate.capability_id === draft.capability_id &&
    candidate.classification === draft.classification &&
    candidate.retention_policy_id === draft.retention_policy_id &&
    candidate.retention_policy_digest === draft.retention_policy_digest;
}

function optionMatchesDraft(
  option: OperationalKnowledgeReviewRequestOption,
  draft: ReviewableOperationalEvidenceKnowledgeDraft,
): boolean {
  return option.source_draft_id === draft.draft_id &&
    option.source_draft_digest === draft.canonical_digest &&
    option.connector_id === draft.connector_id && option.instance_id === draft.instance_id &&
    option.capability_id === draft.capability_id &&
    option.classification === draft.classification &&
    option.retention_policy_id === draft.retention_policy_id;
}

export async function getOperationalKnowledgeReviewRequests(input: {
  draft: ReviewableOperationalEvidenceKnowledgeDraft;
}): Promise<OperationalKnowledgeReviewRequestInventoryItem[]> {
  assertReviewableDraft(input.draft);
  const parameters = new URLSearchParams({ source_draft_id: input.draft.draft_id });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-review-requests?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Knowledge review request inventory failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) {
    throw new Error("Knowledge review request inventory returned unsafe records");
  }
  const records: OperationalKnowledgeReviewRequestInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate) || !matchesDraft(candidate, input.draft)) {
      throw new Error("Knowledge review request inventory returned unsafe records");
    }
    records.push(candidate);
  }
  if (records.length > 1) {
    throw new Error("Knowledge review request inventory returned duplicate records");
  }
  return records;
}

export async function getOperationalKnowledgeReviewRequestOptions(input: {
  draft: ReviewableOperationalEvidenceKnowledgeDraft;
}): Promise<OperationalKnowledgeReviewRequestOption[]> {
  assertReviewableDraft(input.draft);
  const parameters = new URLSearchParams({ source_draft_id: input.draft.draft_id });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-review-requests/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Knowledge review request options failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) {
    throw new Error("Knowledge review request options returned unsafe records");
  }
  const options: OperationalKnowledgeReviewRequestOption[] = [];
  const ids = new Set<string>();
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || !optionMatchesDraft(candidate, input.draft) ||
      ids.has(candidate.review_request_option_id)) {
      throw new Error("Knowledge review request options returned unsafe records");
    }
    ids.add(candidate.review_request_option_id);
    options.push(candidate);
  }
  return options;
}

export async function createOperationalKnowledgeReviewRequest(input: {
  draft: ReviewableOperationalEvidenceKnowledgeDraft;
  option: OperationalKnowledgeReviewRequestOption;
  purpose: string;
}): Promise<{ data: OperationalKnowledgeReviewRequestInventoryItem }> {
  const { draft, option, purpose } = input;
  assertReviewableDraft(draft);
  if (!optionMatchesDraft(option, draft) || purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact current knowledge review request option is required");
  }
  const response = await apiFetch("/api/v1/knowledge/operational-review-requests", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-review-request.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-review-request-input.v1",
      source_draft_id: draft.draft_id,
      review_request_option_id: option.review_request_option_id,
      purpose: purpose.trim(),
      acknowledged_result_is_only_an_unassigned_review_request: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Operational knowledge review request failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!isInventoryItem(data) || !matchesDraft(data, draft) ||
    data.orchestration_policy_id !== option.orchestration_policy_id ||
    data.orchestration_policy_digest !== option.orchestration_policy_digest ||
    data.orchestration_policy_version !== option.orchestration_policy_version) {
    throw new Error("Knowledge review request returned unsafe metadata");
  }
  return { data };
}
