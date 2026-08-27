import { ApiRequestError, apiFetch } from "./client";

export type DocumentKnowledgeReviewDecision = "passed" | "changes_required" | "rejected";
export type DocumentKnowledgeApprovalDecision = "approved" | "rejected";

export type DocumentKnowledgeDraft = {
  draft_id: string;
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  title: string;
  draft_domain: string;
  content_type: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  protected_material_digest: string;
  byte_count: number;
  created_at: string;
  instance_state: string;
  canonical_digest: string;
};

export type DocumentKnowledgeReview = {
  review_id: string;
  draft_id: string;
  organization_id: string;
  environment_id: string;
  decision: DocumentKnowledgeReviewDecision;
  findings: string[];
  decided_at: string;
  instance_state: string;
  canonical_digest: string;
};

export type DocumentKnowledgeApproval = {
  approval_id: string;
  review_id: string;
  draft_id: string;
  organization_id: string;
  environment_id: string;
  decision: DocumentKnowledgeApprovalDecision;
  rationale: string;
  decided_at: string;
  instance_state: string;
  canonical_digest: string;
};

export type DocumentKnowledgePublicationPreparation = {
  preparation_id: string;
  approval_id: string;
  draft_id: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  protected_material_digest: string;
  chunking_profile_digest: string;
  prepared_at: string;
  instance_state: string;
  canonical_digest: string;
};

export type DocumentKnowledgeIndexResult = {
  preparation_id: string;
  chunk_count: number;
};

export type DocumentKnowledgeSearchResult = {
  chunk_id: string;
  knowledge_item_id: string;
  content_digest: string;
  score: number;
  excerpt: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function problemMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.clone().json();
    if (isRecord(body) && typeof body.detail === "string" && body.detail.length > 0) {
      return typeof body.code === "string" ? `${body.detail} (${body.code})` : body.detail;
    }
  } catch {
    // The error body was not parseable JSON; fall back to the generic message.
  }
  return fallback;
}

async function extractData<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    throw new ApiRequestError(await problemMessage(response, fallbackMessage), response.status);
  }
  const envelope: unknown = await response.json();
  if (!isRecord(envelope) || !("data" in envelope)) {
    throw new ApiRequestError(`${fallbackMessage} response was unsafe`, response.status);
  }
  return envelope.data as T;
}

const JSON_HEADERS = { Accept: "application/json", "Content-Type": "application/json" };

export async function createDocumentKnowledgeDraft(input: {
  contentBase64: string;
  title: string;
  draftDomain: string;
  contentType: string;
  classification: string;
  accessPolicyId: string;
  retentionPolicyId: string;
  purpose: string;
}): Promise<DocumentKnowledgeDraft> {
  const response = await apiFetch("/api/v1/knowledge/documents/drafts", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      content_base64: input.contentBase64,
      title: input.title,
      draft_domain: input.draftDomain,
      content_type: input.contentType,
      classification: input.classification,
      access_policy_id: input.accessPolicyId,
      retention_policy_id: input.retentionPolicyId,
      purpose: input.purpose,
    }),
  });
  return extractData<DocumentKnowledgeDraft>(response, "Document draft curation failed");
}

export async function submitDocumentKnowledgeReview(input: {
  draftId: string;
  decision: DocumentKnowledgeReviewDecision;
  findings: string[];
}): Promise<DocumentKnowledgeReview> {
  const response = await apiFetch("/api/v1/knowledge/documents/reviews", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      draft_id: input.draftId,
      decision: input.decision,
      findings: input.findings,
    }),
  });
  return extractData<DocumentKnowledgeReview>(response, "Document review submission failed");
}

export async function recordDocumentKnowledgeApproval(input: {
  reviewId: string;
  decision: DocumentKnowledgeApprovalDecision;
  rationale: string;
}): Promise<DocumentKnowledgeApproval> {
  const response = await apiFetch("/api/v1/knowledge/documents/approvals", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      review_id: input.reviewId,
      decision: input.decision,
      rationale: input.rationale,
    }),
  });
  return extractData<DocumentKnowledgeApproval>(response, "Document approval recording failed");
}

export async function prepareDocumentKnowledgePublication(input: {
  approvalId: string;
  chunkingProfileDigest: string;
}): Promise<DocumentKnowledgePublicationPreparation> {
  const response = await apiFetch("/api/v1/knowledge/documents/publication-preparations", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      approval_id: input.approvalId,
      chunking_profile_digest: input.chunkingProfileDigest,
    }),
  });
  return extractData<DocumentKnowledgePublicationPreparation>(
    response,
    "Document publication preparation failed",
  );
}

export async function indexDocumentKnowledge(input: {
  preparationId: string;
}): Promise<DocumentKnowledgeIndexResult> {
  const response = await apiFetch("/api/v1/knowledge/documents/index", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ preparation_id: input.preparationId }),
  });
  return extractData<DocumentKnowledgeIndexResult>(response, "Document indexing failed");
}

export async function searchDocumentKnowledge(input: {
  query: string;
  topK?: number;
}): Promise<DocumentKnowledgeSearchResult[]> {
  const response = await apiFetch("/api/v1/knowledge/documents/search", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ query: input.query, top_k: input.topK ?? 5 }),
  });
  return extractData<DocumentKnowledgeSearchResult[]>(response, "Document search failed");
}

export async function chunkingProfileDigest(profileDescriptor: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(profileDescriptor));
  return Array.from(new Uint8Array(bytes))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}
