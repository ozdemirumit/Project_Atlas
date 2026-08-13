import { ApiRequestError, apiFetch } from "./client";

export type ConversationLifecycle = "open" | "closed";
export type ConversationTurnRole = "user" | "assistant";
export type ConversationTurnStatus = "completed" | "partial" | "failed";

export type ConversationScope = {
  organizationId: string;
  environmentId: string;
  siteId: string;
  ownerSubjectId: string;
};

export type AuthorizedStorageTarget = {
  targetId: string;
  displayName: string;
  description?: string;
};

export type ConversationEvidenceReference = {
  evidence_id: string;
  artifact_id: string;
  artifact_version: string;
  source_type: string;
  source_reference: string;
  observed_at: string;
  citation: string;
};

export type ConversationArtifactReference = {
  artifact_id: string;
  artifact_type: string;
  version: number;
};

export type OperationalConversationTurn = {
  schema_version: "atlas.operational-conversation-turn.v1";
  turn_id: string;
  ordinal: number;
  role: ConversationTurnRole;
  status: ConversationTurnStatus;
  text: string;
  observed_at: string;
  evidence_references: ConversationEvidenceReference[];
  artifact_references: ConversationArtifactReference[];
  assumptions: string[];
  unknowns: string[];
  confidence_basis: string;
  failure_code: string | null;
  safety_notice: string;
  canonical_digest: string;
};

export type OperationalConversationSummary = {
  schema_version: "atlas.operational-conversation.v1";
  conversation_id: string;
  version: number;
  organization_id: string;
  environment_id: string;
  site_id: string;
  owner_subject_id: string;
  target_id: string;
  target_type: "storage";
  title: string;
  lifecycle: ConversationLifecycle;
  turn_count: number;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  durable: boolean;
  canonical_digest: string;
};

export type OperationalConversation = OperationalConversationSummary & {
  turns: OperationalConversationTurn[];
};

export type OperationalConversationInventory = {
  conversations: OperationalConversationSummary[];
  authorizedTargets: AuthorizedStorageTarget[];
  durable: boolean;
  truncated: boolean;
};

export type ConversationAccessContext = ConversationScope & {
  authorizedTargetIds: readonly string[];
};

const canonicalDigest = /^[a-f0-9]{64}$/;
const summaryFields = new Set([
  "schema_version",
  "conversation_id",
  "version",
  "organization_id",
  "environment_id",
  "site_id",
  "owner_subject_id",
  "target_id",
  "target_type",
  "title",
  "lifecycle",
  "turn_count",
  "created_by",
  "created_at",
  "updated_by",
  "updated_at",
  "durable",
  "canonical_digest",
]);
const conversationFields = new Set([...summaryFields, "turns"]);
const turnFields = new Set([
  "schema_version",
  "turn_id",
  "ordinal",
  "role",
  "status",
  "text",
  "observed_at",
  "evidence_references",
  "artifact_references",
  "assumptions",
  "unknowns",
  "confidence_basis",
  "failure_code",
  "safety_notice",
  "canonical_digest",
]);
const evidenceFields = new Set([
  "evidence_id",
  "artifact_id",
  "artifact_version",
  "source_type",
  "source_reference",
  "observed_at",
  "citation",
]);
const artifactFields = new Set(["artifact_id", "artifact_type", "version"]);
const authorizedTargetFields = new Set(["target_id", "display_name", "description"]);

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactFields(record: Record<string, unknown>, fields: Set<string>): boolean {
  return Object.keys(record).length === fields.size && Object.keys(record).every((key) => fields.has(key));
}

function isBoundedText(value: unknown, maximum: number, allowEmpty = false): value is string {
  return (
    typeof value === "string" &&
    value.length <= maximum &&
    (allowEmpty || value.trim().length > 0)
  );
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 240 && !/\s/.test(value);
}

function isAuthorizedTarget(value: unknown): value is {
  target_id: string;
  display_name: string;
  description?: string;
} {
  if (!isObject(value) || !Object.keys(value).every((key) => authorizedTargetFields.has(key))) {
    return false;
  }
  if (!Object.hasOwn(value, "target_id") || !Object.hasOwn(value, "display_name")) return false;
  return (
    isIdentifier(value.target_id) &&
    isBoundedText(value.display_name, 200) &&
    (value.description === undefined || isBoundedText(value.description, 500))
  );
}

function isBoundedStringList(value: unknown, maximumItems = 50): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maximumItems &&
    value.every((item) => isBoundedText(item, 2_000))
  );
}

function isEvidenceReference(value: unknown): value is ConversationEvidenceReference {
  if (!isObject(value) || !hasExactFields(value, evidenceFields)) return false;
  return (
    isIdentifier(value.evidence_id) &&
    isIdentifier(value.artifact_id) &&
    isBoundedText(value.artifact_version, 128) &&
    isBoundedText(value.source_type, 120) &&
    isBoundedText(value.source_reference, 1_000) &&
    isTimestamp(value.observed_at) &&
    isBoundedText(value.citation, 2_000)
  );
}

function isArtifactReference(value: unknown): value is ConversationArtifactReference {
  if (!isObject(value) || !hasExactFields(value, artifactFields)) return false;
  return (
    isIdentifier(value.artifact_id) &&
    isBoundedText(value.artifact_type, 120) &&
    Number.isInteger(value.version) &&
    Number(value.version) >= 1
  );
}

function isTurn(value: unknown): value is OperationalConversationTurn {
  if (!isObject(value) || !hasExactFields(value, turnFields)) return false;
  const role = value.role;
  const status = value.status;
  const evidence = value.evidence_references;
  const artifacts = value.artifact_references;
  if (
    value.schema_version !== "atlas.operational-conversation-turn.v1" ||
    !isIdentifier(value.turn_id) ||
    !Number.isInteger(value.ordinal) ||
    Number(value.ordinal) < 1 ||
    (role !== "user" && role !== "assistant") ||
    (status !== "completed" && status !== "partial" && status !== "failed") ||
    !isBoundedText(value.text, 12_000) ||
    !isTimestamp(value.observed_at) ||
    !Array.isArray(evidence) ||
    evidence.length > 50 ||
    !evidence.every(isEvidenceReference) ||
    !Array.isArray(artifacts) ||
    artifacts.length > 50 ||
    !artifacts.every(isArtifactReference) ||
    !isBoundedStringList(value.assumptions) ||
    !isBoundedStringList(value.unknowns) ||
    !isBoundedText(value.confidence_basis, 10_019, role === "user") ||
    !isBoundedText(value.safety_notice, 2_000) ||
    typeof value.canonical_digest !== "string" ||
    !canonicalDigest.test(value.canonical_digest) ||
    !(value.failure_code === null || isIdentifier(value.failure_code))
  ) {
    return false;
  }
  if (role === "user") {
    return (
      status === "completed" &&
      evidence.length === 0 &&
      artifacts.length === 0 &&
      value.assumptions.length === 0 &&
      value.unknowns.length === 0 &&
      value.confidence_basis === "" &&
      value.failure_code === null
    );
  }
  return status === "failed" ? value.failure_code !== null : value.failure_code === null;
}

function hasSummaryValues(value: Record<string, unknown>): boolean {
  return (
    value.schema_version === "atlas.operational-conversation.v1" &&
    isIdentifier(value.conversation_id) &&
    Number.isInteger(value.version) &&
    Number(value.version) >= 1 &&
    isIdentifier(value.organization_id) &&
    isIdentifier(value.environment_id) &&
    isIdentifier(value.site_id) &&
    isIdentifier(value.owner_subject_id) &&
    isIdentifier(value.target_id) &&
    value.target_type === "storage" &&
    isBoundedText(value.title, 200) &&
    (value.lifecycle === "open" || value.lifecycle === "closed") &&
    Number.isInteger(value.turn_count) &&
    Number(value.turn_count) >= 0 &&
    isIdentifier(value.created_by) &&
    isTimestamp(value.created_at) &&
    isIdentifier(value.updated_by) &&
    isTimestamp(value.updated_at) &&
    typeof value.durable === "boolean" &&
    typeof value.canonical_digest === "string" &&
    canonicalDigest.test(value.canonical_digest)
  );
}

function isSummary(value: unknown): value is OperationalConversationSummary {
  return isObject(value) && hasExactFields(value, summaryFields) && hasSummaryValues(value);
}

function isConversation(value: unknown): value is OperationalConversation {
  if (!isObject(value) || !hasExactFields(value, conversationFields) || !hasSummaryValues(value)) {
    return false;
  }
  return (
    Array.isArray(value.turns) &&
    value.turns.length <= 200 &&
    value.turns.length === value.turn_count &&
    value.turns.every(isTurn) &&
    value.turns.every((turn, index) => turn.ordinal === index + 1)
  );
}

function isBoundToContext(
  conversation: OperationalConversationSummary,
  context: ConversationAccessContext,
): boolean {
  return (
    conversation.organization_id === context.organizationId &&
    conversation.environment_id === context.environmentId &&
    conversation.site_id === context.siteId &&
    conversation.owner_subject_id === context.ownerSubjectId &&
    context.authorizedTargetIds.includes(conversation.target_id)
  );
}

function isBoundToScope(
  conversation: OperationalConversationSummary,
  scope: ConversationScope,
): boolean {
  return (
    conversation.organization_id === scope.organizationId &&
    conversation.environment_id === scope.environmentId &&
    conversation.site_id === scope.siteId &&
    conversation.owner_subject_id === scope.ownerSubjectId
  );
}

function readEnvelopeData(payload: unknown, status: number): unknown {
  if (!isObject(payload) || !hasExactFields(payload, new Set(["data", "meta"]))) {
    throw new ApiRequestError("Conversation response was malformed", status);
  }
  const meta = payload.meta;
  if (
    !isObject(meta) ||
    !hasExactFields(meta, new Set(["correlation_id", "generated_at"])) ||
    !isBoundedText(meta.correlation_id, 160) ||
    !isTimestamp(meta.generated_at)
  ) {
    throw new ApiRequestError("Conversation response metadata was malformed", status);
  }
  return payload.data;
}

function readConversation(
  payload: unknown,
  status: number,
  context: ConversationAccessContext,
): OperationalConversation {
  const data = readEnvelopeData(payload, status);
  if (!isConversation(data) || !isBoundToContext(data, context)) {
    throw new ApiRequestError("Conversation response was unsafe", status);
  }
  return data;
}

async function readJson(response: Response, message: string): Promise<unknown> {
  if (!response.ok) throw new ApiRequestError(message, response.status);
  try {
    return await response.json();
  } catch {
    throw new ApiRequestError(`${message}: malformed JSON`, response.status);
  }
}

/*
 * ADR-131 defines the aggregate semantics but not wire-level schema identifiers or envelope fields.
 * This client assumes Atlas' existing `{ data, meta }` envelope, boolean `durable` indicators,
 * `atlas.operational-conversation.v1` / `atlas.operational-conversation-turn.v1` records, and the
 * create/append input schema names below. These assumptions are intentionally centralized here so
 * backend integration changes remain explicit and fail closed instead of silently reshaping data.
 */
export async function listOperationalConversations(
  scope: ConversationScope,
): Promise<OperationalConversationInventory> {
  const response = await apiFetch("/api/v1/conversations?limit=50", {
    headers: { Accept: "application/json" },
  });
  const data = readEnvelopeData(
    await readJson(response, "Conversation list failed"),
    response.status,
  );
  if (
    !isObject(data) ||
    !hasExactFields(
      data,
      new Set(["conversations", "authorized_targets", "durable", "truncated"]),
    )
  ) {
    throw new ApiRequestError("Conversation list was malformed", response.status);
  }
  const authorizedTargets = data.authorized_targets;
  if (
    !Array.isArray(authorizedTargets) ||
    authorizedTargets.length > 200 ||
    !authorizedTargets.every(isAuthorizedTarget)
  ) {
    throw new ApiRequestError("Conversation target authorization was malformed", response.status);
  }
  const authorizedTargetIds = authorizedTargets.map((target) => target.target_id);
  if (new Set(authorizedTargetIds).size !== authorizedTargetIds.length) {
    throw new ApiRequestError("Conversation target authorization was ambiguous", response.status);
  }
  if (
    !Array.isArray(data.conversations) ||
    data.conversations.length > 50 ||
    !data.conversations.every(isSummary) ||
    !data.conversations.every((conversation) => isBoundToScope(conversation, scope)) ||
    !data.conversations.every((conversation) => authorizedTargetIds.includes(conversation.target_id)) ||
    typeof data.durable !== "boolean" ||
    typeof data.truncated !== "boolean" ||
    data.conversations.some((conversation) => conversation.durable !== data.durable)
  ) {
    throw new ApiRequestError("Conversation list was unsafe", response.status);
  }
  return {
    conversations: data.conversations,
    authorizedTargets: authorizedTargets.map((target) => ({
      targetId: target.target_id,
      displayName: target.display_name,
      ...(target.description === undefined ? {} : { description: target.description }),
    })),
    durable: data.durable,
    truncated: data.truncated,
  };
}

export async function getOperationalConversation(input: {
  conversationId: string;
  context: ConversationAccessContext;
}): Promise<OperationalConversation> {
  const response = await apiFetch(
    `/api/v1/conversations/${encodeURIComponent(input.conversationId)}`,
    { headers: { Accept: "application/json" } },
  );
  const conversation = readConversation(
    await readJson(response, "Conversation retrieval failed"),
    response.status,
    input.context,
  );
  if (conversation.conversation_id !== input.conversationId) {
    throw new ApiRequestError("Conversation response was not request-bound", response.status);
  }
  return conversation;
}

export async function createOperationalConversation(input: {
  context: ConversationAccessContext;
  targetId: string;
  title: string;
  idempotencyKey?: string;
}): Promise<OperationalConversation> {
  if (!input.context.authorizedTargetIds.includes(input.targetId)) {
    throw new ApiRequestError("Storage target is outside the authorized conversation scope", 403);
  }
  const title = input.title.trim();
  const response = await apiFetch("/api/v1/conversations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": input.idempotencyKey ?? `conversation-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-conversation-create.v1",
      target_id: input.targetId,
      target_type: "storage",
      title,
      acknowledged_decision_support_only: true,
    }),
  });
  const conversation = readConversation(
    await readJson(response, "Conversation creation failed"),
    response.status,
    input.context,
  );
  if (
    conversation.target_id !== input.targetId ||
    conversation.title !== title ||
    conversation.lifecycle !== "open" ||
    conversation.version !== 1 ||
    conversation.turn_count !== 0
  ) {
    throw new ApiRequestError("Conversation creation response was not request-bound", response.status);
  }
  return conversation;
}

export async function appendOperationalConversationTurn(input: {
  context: ConversationAccessContext;
  conversation: OperationalConversation;
  question: string;
  idempotencyKey?: string;
}): Promise<OperationalConversation> {
  if (!isBoundToContext(input.conversation, input.context) || input.conversation.lifecycle !== "open") {
    throw new ApiRequestError("Conversation is not appendable in this authorized scope", 409);
  }
  const question = input.question.trim();
  if (question.length < 3 || question.length > 700) {
    throw new ApiRequestError("Conversation question must contain 3 to 700 characters", 400);
  }
  const response = await apiFetch(
    `/api/v1/conversations/${encodeURIComponent(input.conversation.conversation_id)}/turns`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": input.idempotencyKey ?? `conversation-turn.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-conversation-turn-append.v1",
        expected_version: input.conversation.version,
        question,
        acknowledged_decision_support_only: true,
      }),
    },
  );
  const conversation = readConversation(
    await readJson(response, "Conversation turn failed"),
    response.status,
    input.context,
  );
  const priorTurnsUnchanged = input.conversation.turns.every(
    (turn, index) => conversation.turns[index]?.canonical_digest === turn.canonical_digest,
  );
  const userTurn = conversation.turns[input.conversation.turn_count];
  const assistantTurn = conversation.turns[input.conversation.turn_count + 1];
  if (
    conversation.conversation_id !== input.conversation.conversation_id ||
    conversation.target_id !== input.conversation.target_id ||
    conversation.version !== input.conversation.version + 1 ||
    conversation.turn_count !== input.conversation.turn_count + 2 ||
    !priorTurnsUnchanged ||
    userTurn?.role !== "user" ||
    userTurn.text !== question ||
    assistantTurn?.role !== "assistant"
  ) {
    throw new ApiRequestError("Conversation turn response was not version-bound", response.status);
  }
  return conversation;
}
