import { apiFetch } from "./client";

export type McpBuilderCapability = {
  candidate_id: string;
  operation_id: string | null;
  method: string;
  path: string;
  summary: string;
  citation: string;
  proposed_capability_class: "C0" | "C1" | "C5";
  clarification_codes: string[];
  generation_blocked: boolean;
};

export type McpBuilderProject = {
  project_id: string;
  schema_version: "atlas.mcp-builder-project.v1";
  version: 1;
  state: "analyzed" | "needs_clarification";
  vendor: string;
  product: string;
  intended_product_versions: string[];
  source_authority: string;
  source_owner: string;
  documentation_version: string;
  publication_date: string;
  license_id: string;
  redistribution_allowed: boolean;
  classification: "public" | "internal" | "confidential" | "restricted";
  openapi_version: string;
  api_title: string;
  api_version: string;
  source_digest: string;
  source_size_bytes: number;
  declared_servers: string[];
  capability_candidates: McpBuilderCapability[];
  findings: Array<{
    code: string;
    severity: "informational" | "warning" | "error";
    location: string;
    message: string;
    blocking: boolean;
  }>;
  canonical_digest: string;
  analyzed_at: string;
  reused: boolean;
  synthetic_or_lab_only: true;
  generated_artifact_created: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  network_request_performed: false;
  model_inference_performed: false;
  dynamic_code_execution_performed: false;
  runtime_trust_granted: false;
};

export type McpBuilderInput = {
  vendor: string;
  product: string;
  productVersion: string;
  sourceAuthority: string;
  sourceOwner: string;
  documentationVersion: string;
  publicationDate: string;
  licenseId: string;
  redistributionAllowed: boolean;
  classification: McpBuilderProject["classification"];
  sourceDocument: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSafeProject(value: unknown): value is { data: McpBuilderProject } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const project = value.data;
  const noAuthority = [
    project.generated_artifact_created,
    project.candidate_package_created,
    project.connector_registered,
    project.connector_installed,
    project.connector_enabled,
    project.network_request_performed,
    project.model_inference_performed,
    project.dynamic_code_execution_performed,
    project.runtime_trust_granted,
  ];
  return (
    project.schema_version === "atlas.mcp-builder-project.v1" &&
    project.version === 1 &&
    (project.state === "analyzed" || project.state === "needs_clarification") &&
    typeof project.project_id === "string" &&
    typeof project.source_digest === "string" &&
    typeof project.canonical_digest === "string" &&
    project.synthetic_or_lab_only === true &&
    noAuthority.every((flag) => flag === false) &&
    Array.isArray(project.capability_candidates) &&
    project.capability_candidates.every(
      (candidate) =>
        isRecord(candidate) &&
        typeof candidate.candidate_id === "string" &&
        ["C0", "C1", "C5"].includes(String(candidate.proposed_capability_class)) &&
        typeof candidate.generation_blocked === "boolean",
    ) &&
    Array.isArray(project.findings)
  );
}

function nonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
}

export async function createMcpBuilderProject(input: McpBuilderInput) {
  const response = await apiFetch("/api/v1/mcp-builder/projects", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `mcp-builder.${nonce()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.mcp-builder-project-request.v1",
      vendor: input.vendor,
      product: input.product,
      intended_product_versions: [input.productVersion],
      target_environment: "isolated synthetic lab",
      sdk_profile: "sdk.python.openapi",
      source_id: "source.openapi.uploaded",
      source_authority: input.sourceAuthority,
      source_owner: input.sourceOwner,
      documentation_version: input.documentationVersion,
      publication_date: input.publicationDate,
      license_id: input.licenseId,
      redistribution_allowed: input.redistributionAllowed,
      classification: input.classification,
      source_document: input.sourceDocument,
      confirmed_synthetic_or_lab_only: true,
    }),
  });
  if (!response.ok) throw new Error(`MCP Builder analysis failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeProject(payload)) throw new Error("MCP Builder returned unsafe data");
  return payload;
}
