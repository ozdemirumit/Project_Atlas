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

export type McpBuilderDesignDecision = {
  candidateId: string;
  decision: "include" | "exclude";
  analyzedClass: "C0" | "C1" | "C5";
  requiredPermission: string;
  rationale: string;
};

export type McpBuilderDesignCheckpoint = {
  checkpoint_id: string;
  schema_version: "atlas.mcp-builder-design-checkpoint.v1";
  version: 1;
  project_id: string;
  project_version: number;
  project_digest: string;
  source_digest: string;
  reviewer_id: string;
  connector_boundary: string;
  target_products: string[];
  network_destinations: string[];
  configuration_keys: string[];
  secret_reference_ids: string[];
  entity_mappings: Array<{ source_entity: string; atlas_entity: string }>;
  capability_decisions: Array<{
    candidate_id: string;
    decision: "include" | "exclude";
    analyzed_class: "C0" | "C1" | "C5";
    confirmed_class: "C0" | "C1" | "C5";
    required_permission: string;
    rationale: string;
    generation_eligible: boolean;
  }>;
  canonical_digest: string;
  created_at: string;
  ready_for_generation_design: true;
  generated_artifact_created: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  network_request_performed: false;
  model_inference_performed: false;
  dynamic_code_execution_performed: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type McpBuilderDesignInput = {
  project: McpBuilderProject;
  connectorBoundary: string;
  configurationKeys: string[];
  secretReferenceIds: string[];
  sourceEntity: string;
  atlasEntity: string;
  decisions: McpBuilderDesignDecision[];
};

export type McpBuilderGeneratedFile = {
  relative_path: string;
  media_type:
    | "application/json"
    | "application/toml"
    | "application/yaml"
    | "text/markdown"
    | "text/x-python";
  sha256: string;
  size_bytes: number;
  source_candidate_ids: string[];
};

export type McpBuilderGeneration = {
  generation_id: string;
  schema_version: "atlas.mcp-builder-generation.v1";
  version: 1;
  state: "quarantined";
  project_id: string;
  project_version: 1;
  project_digest: string;
  source_digest: string;
  checkpoint_id: string;
  checkpoint_digest: string;
  requested_by: string;
  language_profile: "atlas.python312.v1";
  template_version: string;
  artifact_digest: string;
  artifact_size_bytes: number;
  files: McpBuilderGeneratedFile[];
  canonical_digest: string;
  created_at: string;
  artifact_published: true;
  generated_artifact_created: true;
  validation_completed: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  network_request_performed: false;
  model_inference_performed: false;
  subprocess_invoked: false;
  dynamic_code_execution_performed: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type McpBuilderGeneratedFileView = {
  generation_id: string;
  state: "quarantined";
  artifact_digest: string;
  file: McpBuilderGeneratedFile;
  content: string;
  content_verified: true;
  quarantined: true;
  runtime_trust_granted: false;
  execution_authorized: false;
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

function isSafeDesignCheckpoint(
  value: unknown,
): value is { data: McpBuilderDesignCheckpoint } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const checkpoint = value.data;
  const noAuthority = [
    checkpoint.generated_artifact_created,
    checkpoint.candidate_package_created,
    checkpoint.connector_registered,
    checkpoint.connector_installed,
    checkpoint.connector_enabled,
    checkpoint.network_request_performed,
    checkpoint.model_inference_performed,
    checkpoint.dynamic_code_execution_performed,
    checkpoint.runtime_trust_granted,
    checkpoint.execution_authorized,
    checkpoint.infrastructure_mutation_performed,
  ];
  return (
    checkpoint.schema_version === "atlas.mcp-builder-design-checkpoint.v1" &&
    checkpoint.version === 1 &&
    checkpoint.ready_for_generation_design === true &&
    typeof checkpoint.checkpoint_id === "string" &&
    typeof checkpoint.project_id === "string" &&
    typeof checkpoint.canonical_digest === "string" &&
    noAuthority.every((flag) => flag === false) &&
    Array.isArray(checkpoint.capability_decisions) &&
    checkpoint.capability_decisions.length > 0
  );
}

function isSafeGeneratedFile(value: unknown): value is McpBuilderGeneratedFile {
  return (
    isRecord(value) &&
    typeof value.relative_path === "string" &&
    [
      "application/json",
      "application/toml",
      "application/yaml",
      "text/markdown",
      "text/x-python",
    ].includes(String(value.media_type)) &&
    typeof value.sha256 === "string" &&
    value.sha256.length === 64 &&
    typeof value.size_bytes === "number" &&
    value.size_bytes > 0 &&
    Array.isArray(value.source_candidate_ids) &&
    value.source_candidate_ids.every((item) => typeof item === "string")
  );
}

function isSafeGeneration(value: unknown): value is { data: McpBuilderGeneration } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const generation = value.data;
  const noAuthority = [
    generation.validation_completed,
    generation.candidate_package_created,
    generation.connector_registered,
    generation.connector_installed,
    generation.connector_enabled,
    generation.network_request_performed,
    generation.model_inference_performed,
    generation.subprocess_invoked,
    generation.dynamic_code_execution_performed,
    generation.runtime_trust_granted,
    generation.execution_authorized,
    generation.infrastructure_mutation_performed,
  ];
  return (
    generation.schema_version === "atlas.mcp-builder-generation.v1" &&
    generation.version === 1 &&
    generation.state === "quarantined" &&
    generation.language_profile === "atlas.python312.v1" &&
    generation.artifact_published === true &&
    generation.generated_artifact_created === true &&
    typeof generation.generation_id === "string" &&
    typeof generation.artifact_digest === "string" &&
    noAuthority.every((flag) => flag === false) &&
    Array.isArray(generation.files) &&
    generation.files.length > 0 &&
    generation.files.every(isSafeGeneratedFile)
  );
}

function isSafeGeneratedFileView(
  value: unknown,
): value is { data: McpBuilderGeneratedFileView } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const view = value.data;
  return (
    view.state === "quarantined" &&
    view.quarantined === true &&
    view.content_verified === true &&
    view.runtime_trust_granted === false &&
    view.execution_authorized === false &&
    typeof view.content === "string" &&
    isSafeGeneratedFile(view.file)
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

export async function createMcpBuilderDesignCheckpoint(input: McpBuilderDesignInput) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/design-checkpoints`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-design.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-design-checkpoint-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        connector_boundary: input.connectorBoundary,
        target_products: [input.project.product],
        network_destinations: input.project.declared_servers,
        configuration_keys: input.configurationKeys,
        secret_reference_ids: input.secretReferenceIds,
        entity_mappings: [
          { source_entity: input.sourceEntity, atlas_entity: input.atlasEntity },
        ],
        capability_decisions: input.decisions.map((decision) => ({
          candidate_id: decision.candidateId,
          decision: decision.decision,
          analyzed_class: decision.analyzedClass,
          confirmed_class: decision.analyzedClass,
          required_permission: decision.requiredPermission,
          rationale: decision.rationale,
        })),
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder design checkpoint failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeDesignCheckpoint(payload)) {
    throw new Error("MCP Builder returned an unsafe design checkpoint");
  }
  return payload;
}

export async function createMcpBuilderGeneration(input: {
  project: McpBuilderProject;
  checkpoint: McpBuilderDesignCheckpoint;
}) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/generations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-generation.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-generation-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        checkpoint_id: input.checkpoint.checkpoint_id,
        checkpoint_digest: input.checkpoint.canonical_digest,
        language_profile: "atlas.python312.v1",
        acknowledged_quarantine: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder generation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeGeneration(payload)) throw new Error("MCP Builder returned unsafe generation data");
  return payload;
}

export async function getMcpBuilderGeneratedFile(input: {
  projectId: string;
  relativePath: string;
}) {
  const path = input.relativePath.split("/").map(encodeURIComponent).join("/");
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.projectId}/generation/files/${path}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error(`MCP Builder file preview failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeGeneratedFileView(payload)) {
    throw new Error("MCP Builder returned an unsafe generated file preview");
  }
  return payload;
}
