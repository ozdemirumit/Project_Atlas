import { ApiRequestError, apiFetch } from "./client";
import type { OperationalKnowledgeReviewRequestInventoryItem } from "./knowledgeReviewRequests";

export type OperationalKnowledgeReviewerAssignmentSource =
  OperationalKnowledgeReviewRequestInventoryItem;

export type OperationalKnowledgeReviewerAssignmentInventoryItem = {
  assignment_set_id: string;
  schema_version: "atlas.operational-knowledge-reviewer-assignment.v1";
  version: 1;
  source_review_request_id: string;
  source_review_request_digest: string;
  source_draft_id: string;
  source_draft_digest: string;
  knowledge_item_id: string;
  draft_version_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  knowledge_lifecycle: "reviewer_assigned";
  classification: string;
  retention_policy_id: string;
  domain_track_code: "review-track.domain";
  security_track_code: "review-track.security";
  domain_status: "assigned";
  security_status: "assigned";
  assignment_policy_id: string;
  assignment_policy_digest: string;
  assignment_policy_version: string;
  created_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_reviewers_assigned";
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: true;
  immutable_assignments_confirmed: true;
  encrypted_identity_references: true;
  transient_identity_buffers_erased: true;
  directory_channel_closed: true;
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

export type OperationalKnowledgeReviewerAssignmentClaimStatus = {
  assignment_set_id: string;
  schema_version: "atlas.operational-knowledge-reviewer-assignment-claim-status.v1";
  source_review_request_id: string;
  source_review_request_digest: string;
  claimed_at: string;
  claim_state: "claim_consumed_unresolved";
  claim_consumed: true;
  assignment_completed: false;
  automatic_retry_allowed: false;
  content_inspection_opened: false;
  knowledge_approved: false;
  knowledge_published: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type OperationalKnowledgeReviewerAssignmentInventoryEntry =
  OperationalKnowledgeReviewerAssignmentInventoryItem |
  OperationalKnowledgeReviewerAssignmentClaimStatus;

// Legacy protected-inspection code owns a separate, non-inventory contract until its governance
// slice replaces browser-provided policy data. It must not be returned by the APIs in this module.
export type OperationalKnowledgeReviewerAssignment =
  OperationalKnowledgeReviewerAssignmentInventoryItem & {
    organization_id: string;
    environment_id: string;
    draft_version_id: string;
    source_ingestion_id: string;
    source_invocation_id: string;
    classification: string;
    access_policy_id: string;
    retention_policy_id: string;
    encryption_profile_id: string;
    manifest_id: string;
    manifest_digest: string;
    domain_assignment_id: string;
    security_assignment_id: string;
    domain_reviewer_subject_digest: string;
    security_reviewer_subject_digest: string;
    domain_queue_id: string;
    security_queue_id: string;
  };

export type OperationalKnowledgeReviewerAssignmentOption = {
  assignment_option_id: string;
  source_review_request_id: string;
  source_review_request_digest: string;
  source_draft_id: string;
  knowledge_item_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  assignment_policy_id: string;
  assignment_policy_digest: string;
  assignment_policy_version: string;
  assignment_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  domain_track_code: "review-track.domain";
  security_track_code: "review-track.security";
  assignment_ttl_minutes: number;
  resulting_instance_state: "operational_knowledge_reviewers_assigned";
  resulting_domain_status: "assigned";
  resulting_security_status: "assigned";
  irreversible_claim_required: true;
  automatic_retry_allowed: false;
  review_requested: true;
  reviewer_assigned: true;
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
  "assignment_set_id", "schema_version", "version", "source_review_request_id",
  "source_review_request_digest", "source_draft_id", "source_draft_digest",
  "knowledge_item_id", "draft_version_id", "connector_id", "instance_id", "capability_id",
  "title", "knowledge_lifecycle", "classification", "retention_policy_id",
  "domain_track_code", "security_track_code", "domain_status",
  "security_status", "assignment_policy_id", "assignment_policy_digest",
  "assignment_policy_version", "created_at", "expires_at", "instance_state",
  "canonical_digest", "review_requested", "reviewer_assigned",
  "immutable_assignments_confirmed", "encrypted_identity_references",
  "transient_identity_buffers_erased", "directory_channel_closed",
  "content_inspection_opened", "domain_review_completed", "security_review_completed",
  "correction_created", "knowledge_approved", "knowledge_published", "chunks_created",
  "embeddings_created", "retrieval_published", "model_context_available", "graph_updated",
  "scheduled", "workflow_continued", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed", "reused",
]);
const claimStatusFields = new Set([
  "assignment_set_id", "schema_version", "source_review_request_id",
  "source_review_request_digest", "claimed_at", "claim_state", "claim_consumed",
  "assignment_completed", "automatic_retry_allowed", "content_inspection_opened",
  "knowledge_approved", "knowledge_published", "workflow_continued", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed",
]);
const optionFields = new Set([
  "assignment_option_id", "source_review_request_id", "source_review_request_digest",
  "source_draft_id", "knowledge_item_id", "connector_id",
  "instance_id", "capability_id", "assignment_policy_id", "assignment_policy_digest",
  "assignment_policy_version", "assignment_policy_expires_at", "required_assurance_level",
  "domain_track_code", "security_track_code", "assignment_ttl_minutes",
  "resulting_instance_state",
  "resulting_domain_status", "resulting_security_status", "irreversible_claim_required",
  "automatic_retry_allowed", "review_requested", "reviewer_assigned",
  "content_inspection_opened", "domain_review_completed", "security_review_completed",
  "knowledge_approved", "knowledge_published", "retrieval_published",
  "model_context_available", "scheduled", "workflow_continued", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed",
]);

export function operationalKnowledgeReviewerAssignmentQueryKey(
  sessionScopeKey: string,
  reviewRequestId: string,
) {
  return [
    "operational-knowledge-reviewer-assignments",
    sessionScopeKey,
    reviewRequestId,
  ] as const;
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
    throw new Error("Reviewer assignment response envelope is unsafe");
  }
  const envelope = payload as Record<string, unknown>;
  if (!hasExactFields(envelope, envelopeFields)) {
    throw new Error("Reviewer assignment response envelope is unsafe");
  }
  const meta = envelope.meta;
  if (!meta || typeof meta !== "object" || Array.isArray(meta) ||
    !hasExactFields(meta as Record<string, unknown>, metaFields)) {
    throw new Error("Reviewer assignment response envelope is unsafe");
  }
  const responseMeta = meta as Record<string, unknown>;
  if (typeof responseMeta.correlation_id !== "string" ||
    responseMeta.correlation_id.length < 1 || responseMeta.correlation_id.length > 128 ||
    !isTimestamp(responseMeta.generated_at)) {
    throw new Error("Reviewer assignment response envelope is unsafe");
  }
  return envelope.data;
}

function hasAssignmentBoundary(record: Record<string, unknown>): boolean {
  return record.review_requested === true && record.reviewer_assigned === true &&
    record.immutable_assignments_confirmed === true &&
    record.encrypted_identity_references === true &&
    record.transient_identity_buffers_erased === true &&
    record.directory_channel_closed === true && record.content_inspection_opened === false &&
    record.domain_review_completed === false && record.security_review_completed === false &&
    record.correction_created === false && record.knowledge_approved === false &&
    record.knowledge_published === false && record.chunks_created === false &&
    record.embeddings_created === false && record.retrieval_published === false &&
    record.model_context_available === false && record.graph_updated === false &&
    record.scheduled === false && record.workflow_continued === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function isInventoryItem(
  value: unknown,
): value is OperationalKnowledgeReviewerAssignmentInventoryItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) &&
    ["assignment_set_id", "source_review_request_id", "source_draft_id", "knowledge_item_id",
      "draft_version_id", "connector_id", "instance_id", "capability_id", "classification",
      "retention_policy_id", "assignment_policy_id", "domain_track_code", "security_track_code"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    ["source_review_request_digest", "source_draft_digest", "assignment_policy_digest",
      "canonical_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    record.schema_version === "atlas.operational-knowledge-reviewer-assignment.v1" &&
    record.version === 1 && typeof record.title === "string" && record.title.length > 0 &&
    record.title.length <= 512 && typeof record.assignment_policy_version === "string" &&
    record.assignment_policy_version.length > 0 && record.assignment_policy_version.length <= 64 &&
    record.knowledge_lifecycle === "reviewer_assigned" &&
    record.domain_track_code === "review-track.domain" &&
    record.security_track_code === "review-track.security" && record.domain_status === "assigned" &&
    record.security_status === "assigned" && isTimestamp(record.created_at) &&
    isTimestamp(record.expires_at) && Date.parse(record.expires_at) >
      Date.parse(record.created_at) &&
    record.instance_state === "operational_knowledge_reviewers_assigned" &&
    typeof record.reused === "boolean" && hasAssignmentBoundary(record);
}

function isClaimStatus(
  value: unknown,
): value is OperationalKnowledgeReviewerAssignmentClaimStatus {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, claimStatusFields) &&
    typeof record.assignment_set_id === "string" && stableId.test(record.assignment_set_id) &&
    record.schema_version ===
      "atlas.operational-knowledge-reviewer-assignment-claim-status.v1" &&
    typeof record.source_review_request_id === "string" &&
    stableId.test(record.source_review_request_id) &&
    typeof record.source_review_request_digest === "string" &&
    digest.test(record.source_review_request_digest) && isTimestamp(record.claimed_at) &&
    record.claim_state === "claim_consumed_unresolved" && record.claim_consumed === true &&
    record.assignment_completed === false && record.automatic_retry_allowed === false &&
    record.content_inspection_opened === false && record.knowledge_approved === false &&
    record.knowledge_published === false && record.workflow_continued === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function hasOptionBoundary(record: Record<string, unknown>): boolean {
  return record.irreversible_claim_required === true && record.automatic_retry_allowed === false &&
    record.review_requested === true && record.reviewer_assigned === true &&
    record.content_inspection_opened === false && record.domain_review_completed === false &&
    record.security_review_completed === false && record.knowledge_approved === false &&
    record.knowledge_published === false && record.retrieval_published === false &&
    record.model_context_available === false && record.scheduled === false &&
    record.workflow_continued === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isOption(value: unknown): value is OperationalKnowledgeReviewerAssignmentOption {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) &&
    ["assignment_option_id", "source_review_request_id", "source_draft_id", "knowledge_item_id",
      "connector_id", "instance_id", "capability_id", "assignment_policy_id",
      "domain_track_code", "security_track_code"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    ["source_review_request_digest", "assignment_policy_digest"]
      .every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    typeof record.assignment_policy_version === "string" &&
    record.assignment_policy_version.length > 0 &&
    isTimestamp(record.assignment_policy_expires_at) &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    record.domain_track_code === "review-track.domain" &&
    record.security_track_code === "review-track.security" &&
    Number.isInteger(record.assignment_ttl_minutes) &&
    (record.assignment_ttl_minutes as number) >= 5 &&
    (record.assignment_ttl_minutes as number) <= 10_080 &&
    record.resulting_instance_state === "operational_knowledge_reviewers_assigned" &&
    record.resulting_domain_status === "assigned" &&
    record.resulting_security_status === "assigned" && hasOptionBoundary(record);
}

function assertAssignableReviewRequest(
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource,
): void {
  if (!reviewRequest.review_requested || reviewRequest.reviewer_assigned ||
    reviewRequest.knowledge_lifecycle !== "review_requested" ||
    reviewRequest.instance_state !== "operational_knowledge_review_requested" ||
    reviewRequest.content_inspection_opened || reviewRequest.domain_review_completed ||
    reviewRequest.security_review_completed || reviewRequest.knowledge_approved ||
    reviewRequest.knowledge_published || reviewRequest.retrieval_published ||
    reviewRequest.model_context_available || reviewRequest.scheduled ||
    reviewRequest.workflow_continued || reviewRequest.execution_authorized ||
    reviewRequest.deployment_approved || reviewRequest.infrastructure_mutation_performed) {
    throw new Error("An exact unassigned operational knowledge review request is required");
  }
}

function matchesReviewRequest(
  candidate: OperationalKnowledgeReviewerAssignmentInventoryItem,
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource,
): boolean {
  return candidate.source_review_request_id === reviewRequest.review_request_id &&
    candidate.source_review_request_digest === reviewRequest.canonical_digest &&
    candidate.source_draft_id === reviewRequest.source_draft_id &&
    candidate.source_draft_digest === reviewRequest.source_draft_digest &&
    candidate.knowledge_item_id === reviewRequest.knowledge_item_id &&
    candidate.draft_version_id === reviewRequest.draft_version_id &&
    candidate.connector_id === reviewRequest.connector_id &&
    candidate.instance_id === reviewRequest.instance_id &&
    candidate.capability_id === reviewRequest.capability_id &&
    candidate.classification === reviewRequest.classification &&
    candidate.retention_policy_id === reviewRequest.retention_policy_id;
}

function optionMatchesReviewRequest(
  option: OperationalKnowledgeReviewerAssignmentOption,
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource,
): boolean {
  return option.source_review_request_id === reviewRequest.review_request_id &&
    option.source_review_request_digest === reviewRequest.canonical_digest &&
    option.source_draft_id === reviewRequest.source_draft_id &&
    option.knowledge_item_id === reviewRequest.knowledge_item_id &&
    option.connector_id === reviewRequest.connector_id &&
    option.instance_id === reviewRequest.instance_id &&
    option.capability_id === reviewRequest.capability_id;
}

export async function getOperationalKnowledgeReviewerAssignments(input: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
}): Promise<OperationalKnowledgeReviewerAssignmentInventoryEntry[]> {
  assertAssignableReviewRequest(input.reviewRequest);
  const parameters = new URLSearchParams({
    source_review_request_id: input.reviewRequest.review_request_id,
  });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-reviewer-assignments?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Reviewer assignment inventory failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) {
    throw new Error("Reviewer assignment inventory returned unsafe records");
  }
  const records: OperationalKnowledgeReviewerAssignmentInventoryEntry[] = [];
  for (const candidate of data as unknown[]) {
    const matchesSource = isInventoryItem(candidate)
      ? matchesReviewRequest(candidate, input.reviewRequest)
      : isClaimStatus(candidate) &&
        candidate.source_review_request_id === input.reviewRequest.review_request_id &&
        candidate.source_review_request_digest === input.reviewRequest.canonical_digest;
    if (!matchesSource) {
      throw new Error("Reviewer assignment inventory returned unsafe records");
    }
    records.push(candidate as OperationalKnowledgeReviewerAssignmentInventoryEntry);
  }
  if (records.length > 1) {
    throw new Error("Reviewer assignment inventory returned duplicate records");
  }
  return records;
}

export async function getOperationalKnowledgeReviewerAssignmentOptions(input: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
}): Promise<OperationalKnowledgeReviewerAssignmentOption[]> {
  assertAssignableReviewRequest(input.reviewRequest);
  const parameters = new URLSearchParams({
    source_review_request_id: input.reviewRequest.review_request_id,
  });
  const response = await apiFetch(
    `/api/v1/knowledge/operational-reviewer-assignments/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Reviewer assignment options failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!Array.isArray(data)) {
    throw new Error("Reviewer assignment options returned unsafe records");
  }
  const options: OperationalKnowledgeReviewerAssignmentOption[] = [];
  const ids = new Set<string>();
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || !optionMatchesReviewRequest(candidate, input.reviewRequest) ||
      ids.has(candidate.assignment_option_id)) {
      throw new Error("Reviewer assignment options returned unsafe records");
    }
    ids.add(candidate.assignment_option_id);
    options.push(candidate);
  }
  return options;
}

export async function createOperationalKnowledgeReviewerAssignment(input: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
  option: OperationalKnowledgeReviewerAssignmentOption;
  purpose: string;
}): Promise<{ data: OperationalKnowledgeReviewerAssignmentInventoryItem }> {
  const { reviewRequest, option, purpose } = input;
  assertAssignableReviewRequest(reviewRequest);
  if (!optionMatchesReviewRequest(option, reviewRequest) || purpose.trim().length < 20 ||
    purpose.length > 1000) {
    throw new Error("Exact current reviewer assignment option is required");
  }
  const response = await apiFetch("/api/v1/knowledge/operational-reviewer-assignments", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-reviewer-assignment.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-reviewer-assignment-input.v1",
      source_review_request_id: reviewRequest.review_request_id,
      assignment_option_id: option.assignment_option_id,
      purpose: purpose.trim(),
      acknowledged_assignment_opens_no_content_and_records_no_decision: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Operational knowledge reviewer assignment failed", response.status);
  }
  const data = envelopeData(await response.json());
  if (!isInventoryItem(data) || !matchesReviewRequest(data, reviewRequest) ||
    data.assignment_policy_id !== option.assignment_policy_id ||
    data.assignment_policy_digest !== option.assignment_policy_digest ||
    data.assignment_policy_version !== option.assignment_policy_version) {
    throw new Error("Reviewer assignment returned unsafe metadata");
  }
  return { data };
}
