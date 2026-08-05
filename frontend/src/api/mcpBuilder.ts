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

export type McpBuilderValidationCheck = {
  code: string;
  state: "passed" | "failed" | "skipped";
  severity: "informational" | "warning" | "error";
  summary: string;
  evidence_paths: string[];
  remediation: string | null;
};

export type McpBuilderValidation = {
  validation_id: string;
  schema_version: "atlas.mcp-builder-validation.v1";
  version: 1;
  state: "passed" | "failed";
  project_id: string;
  project_version: 1;
  project_digest: string;
  source_digest: string;
  checkpoint_id: string;
  checkpoint_digest: string;
  generation_id: string;
  generation_digest: string;
  artifact_digest: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  language_profile: "atlas.python312.v1";
  template_version: string;
  validation_profile: "atlas.static-validation.python312.v1";
  validator_version: "mcp-builder-static-validator.v1";
  checks: McpBuilderValidationCheck[];
  passed_count: number;
  failed_count: number;
  skipped_count: number;
  limitations: string[];
  canonical_digest: string;
  completed_at: string;
  validation_completed: true;
  static_validation_passed: boolean;
  runtime_self_test_performed: false;
  dependency_resolution_performed: false;
  domain_review_completed: false;
  security_review_completed: false;
  lab_validation_completed: false;
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

export type McpBuilderDomainDecision = {
  candidateId: string;
  confirmedClass: "C0" | "C1" | "C5";
  decision: "accepted" | "needs_evidence" | "rejected";
  supportedProductVersions: string[];
  vendorPermission: string;
  authenticationAssessment: string;
  sideEffectAssessment: string;
  errorBehaviorAssessment: string;
  healthGuidanceAssessment: string;
  evidenceCitations: string[];
  missingCaseCodes: string[];
  rationale: string;
};

export type McpBuilderDomainReview = {
  review_id: string;
  schema_version: "atlas.mcp-builder-domain-review.v1";
  version: 1;
  state: "accepted" | "needs_evidence" | "rejected";
  project_id: string;
  project_version: 1;
  project_digest: string;
  source_digest: string;
  checkpoint_id: string;
  checkpoint_digest: string;
  generation_id: string;
  generation_digest: string;
  artifact_digest: string;
  validation_id: string;
  validation_digest: string;
  validation_profile: "atlas.static-validation.python312.v1";
  validator_version: "mcp-builder-static-validator.v1";
  organization_id: string;
  environment_id: string;
  reviewed_by: string;
  review_profile: "atlas.domain-review.connector.v1";
  reviewer_contract_version: "mcp-builder-domain-review.v1";
  capability_decisions: Array<{
    candidate_id: string;
    confirmed_class: "C0" | "C1" | "C5";
    decision: "accepted" | "needs_evidence" | "rejected";
    supported_product_versions: string[];
    vendor_permission: string;
    authentication_assessment: string;
    side_effect_assessment: string;
    error_behavior_assessment: string;
    health_guidance_assessment: string;
    evidence_citations: string[];
    missing_case_codes: string[];
    rationale: string;
  }>;
  accepted_count: number;
  needs_evidence_count: number;
  rejected_count: number;
  summary: string;
  limitations: string[];
  canonical_digest: string;
  completed_at: string;
  domain_review_completed: true;
  domain_review_accepted: boolean;
  security_review_completed: false;
  lab_validation_completed: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  network_request_performed: false;
  model_inference_performed: false;
  dependency_resolution_performed: false;
  runtime_self_test_performed: false;
  subprocess_invoked: false;
  dynamic_code_execution_performed: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type McpBuilderSecurityControl =
  | "provenance"
  | "supply_chain"
  | "credentials"
  | "network"
  | "input_output"
  | "injection_execution"
  | "logging_redaction"
  | "runner_privileges"
  | "capability_governance";

export type McpBuilderSecurityAssessment = {
  control: McpBuilderSecurityControl;
  decision: "accepted" | "needs_remediation" | "rejected";
  assessment: string;
  evidenceReferences: string[];
  findingCodes: string[];
  requiredControls: string[];
};

export type McpBuilderSecurityReview = {
  review_id: string;
  schema_version: "atlas.mcp-builder-security-review.v1";
  version: 1;
  state: "accepted" | "needs_remediation" | "rejected";
  project_id: string;
  project_version: 1;
  project_digest: string;
  source_digest: string;
  checkpoint_id: string;
  checkpoint_digest: string;
  generation_id: string;
  generation_digest: string;
  artifact_digest: string;
  validation_id: string;
  validation_digest: string;
  validation_profile: "atlas.static-validation.python312.v1";
  validator_version: "mcp-builder-static-validator.v1";
  domain_review_id: string;
  domain_review_digest: string;
  domain_review_profile: "atlas.domain-review.connector.v1";
  domain_reviewer_contract_version: "mcp-builder-domain-review.v1";
  domain_reviewed_by: string;
  organization_id: string;
  environment_id: string;
  reviewed_by: string;
  review_profile: "atlas.security-review.connector.v1";
  reviewer_contract_version: "mcp-builder-security-review.v1";
  control_assessments: Array<{
    control: McpBuilderSecurityControl;
    decision: "accepted" | "needs_remediation" | "rejected";
    assessment: string;
    evidence_references: string[];
    finding_codes: string[];
    required_controls: string[];
  }>;
  accepted_count: number;
  needs_remediation_count: number;
  rejected_count: number;
  summary: string;
  limitations: string[];
  canonical_digest: string;
  completed_at: string;
  security_review_completed: true;
  security_review_accepted: boolean;
  lab_validation_completed: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  network_request_performed: false;
  model_inference_performed: false;
  dependency_resolution_performed: false;
  malware_or_dynamic_scan_performed: false;
  runtime_self_test_performed: false;
  subprocess_invoked: false;
  dynamic_code_execution_performed: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type McpBuilderLabCheck = {
  code:
    | "lab.artifact_integrity"
    | "lab.runner_isolation"
    | "lab.secret_free_environment"
    | "lab.network_denial"
    | "lab.package_import"
    | "lab.quarantine_contract"
    | "lab.capability_fail_closed"
    | "lab.bounded_output";
  state: "passed" | "failed" | "skipped";
  severity: "info" | "error";
  summary: string;
  evidence_paths: string[];
  remediation: string | null;
};

export type McpBuilderLabValidation = {
  lab_validation_id: string;
  schema_version: "atlas.mcp-builder-lab-validation.v1";
  version: 1;
  state: "passed" | "failed";
  project_id: string;
  project_version: 1;
  project_digest: string;
  source_digest: string;
  checkpoint_id: string;
  checkpoint_digest: string;
  generation_id: string;
  generation_digest: string;
  artifact_digest: string;
  validation_id: string;
  validation_digest: string;
  domain_review_id: string;
  domain_review_digest: string;
  domain_reviewed_by: string;
  security_review_id: string;
  security_review_digest: string;
  security_reviewed_by: string;
  organization_id: string;
  environment_id: string;
  operated_by: string;
  lab_profile: "atlas.lab-validation.python312.v1";
  runner_contract_version: "mcp-builder-isolated-runner.v1";
  runtime_version: string;
  checks: McpBuilderLabCheck[];
  passed_count: number;
  failed_count: number;
  skipped_count: number;
  child_started: boolean;
  child_exit_code: number | null;
  duration_ms: number;
  output_digest: string;
  output_size_bytes: number;
  artifact_file_count: number;
  artifact_size_bytes: number;
  workspace_removed: true;
  limitations: string[];
  canonical_digest: string;
  completed_at: string;
  lab_validation_completed: true;
  lab_validation_passed: boolean;
  synthetic_fixture_used: true;
  secret_values_present: false;
  target_connected: false;
  network_request_performed: false;
  runtime_self_test_performed: boolean;
  subprocess_invoked: boolean;
  dynamic_code_execution_performed: boolean;
  dependency_resolution_performed: false;
  malware_or_dynamic_scan_performed: false;
  candidate_package_created: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
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

function isSafeValidationCheck(value: unknown): value is McpBuilderValidationCheck {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    ["passed", "failed", "skipped"].includes(String(value.state)) &&
    ["informational", "warning", "error"].includes(String(value.severity)) &&
    typeof value.summary === "string" &&
    Array.isArray(value.evidence_paths) &&
    value.evidence_paths.every((item) => typeof item === "string") &&
    (value.remediation === null || typeof value.remediation === "string")
  );
}

function isSafeValidation(value: unknown): value is { data: McpBuilderValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const validation = value.data;
  const noAuthority = [
    validation.runtime_self_test_performed,
    validation.dependency_resolution_performed,
    validation.domain_review_completed,
    validation.security_review_completed,
    validation.lab_validation_completed,
    validation.candidate_package_created,
    validation.connector_registered,
    validation.connector_installed,
    validation.connector_enabled,
    validation.network_request_performed,
    validation.model_inference_performed,
    validation.subprocess_invoked,
    validation.dynamic_code_execution_performed,
    validation.runtime_trust_granted,
    validation.execution_authorized,
    validation.infrastructure_mutation_performed,
  ];
  const checks = validation.checks;
  if (!Array.isArray(checks) || checks.length !== 15 || !checks.every(isSafeValidationCheck)) {
    return false;
  }
  const passed = checks.filter((item) => item.state === "passed").length;
  const failed = checks.filter((item) => item.state === "failed").length;
  const skipped = checks.filter((item) => item.state === "skipped").length;
  return (
    validation.schema_version === "atlas.mcp-builder-validation.v1" &&
    validation.version === 1 &&
    (validation.state === "passed" || validation.state === "failed") &&
    validation.language_profile === "atlas.python312.v1" &&
    validation.validation_profile === "atlas.static-validation.python312.v1" &&
    validation.validator_version === "mcp-builder-static-validator.v1" &&
    validation.validation_completed === true &&
    validation.static_validation_passed === (validation.state === "passed") &&
    validation.passed_count === passed &&
    validation.failed_count === failed &&
    validation.skipped_count === skipped &&
    typeof validation.validation_id === "string" &&
    typeof validation.canonical_digest === "string" &&
    Array.isArray(validation.limitations) &&
    validation.limitations.length > 0 &&
    validation.limitations.every((item) => typeof item === "string") &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeDomainDecision(
  value: unknown,
): value is McpBuilderDomainReview["capability_decisions"][number] {
  return (
    isRecord(value) &&
    typeof value.candidate_id === "string" &&
    ["C0", "C1", "C5"].includes(String(value.confirmed_class)) &&
    ["accepted", "needs_evidence", "rejected"].includes(String(value.decision)) &&
    Array.isArray(value.supported_product_versions) &&
    value.supported_product_versions.every((item) => typeof item === "string") &&
    typeof value.vendor_permission === "string" &&
    typeof value.authentication_assessment === "string" &&
    typeof value.side_effect_assessment === "string" &&
    typeof value.error_behavior_assessment === "string" &&
    typeof value.health_guidance_assessment === "string" &&
    Array.isArray(value.evidence_citations) &&
    value.evidence_citations.every((item) => typeof item === "string") &&
    Array.isArray(value.missing_case_codes) &&
    value.missing_case_codes.every((item) => typeof item === "string") &&
    typeof value.rationale === "string"
  );
}

function isSafeDomainReview(value: unknown): value is { data: McpBuilderDomainReview } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const review = value.data;
  const noAuthority = [
    review.security_review_completed,
    review.lab_validation_completed,
    review.candidate_package_created,
    review.connector_registered,
    review.connector_installed,
    review.connector_enabled,
    review.network_request_performed,
    review.model_inference_performed,
    review.dependency_resolution_performed,
    review.runtime_self_test_performed,
    review.subprocess_invoked,
    review.dynamic_code_execution_performed,
    review.runtime_trust_granted,
    review.execution_authorized,
    review.infrastructure_mutation_performed,
  ];
  if (
    !Array.isArray(review.capability_decisions) ||
    review.capability_decisions.length === 0 ||
    !review.capability_decisions.every(isSafeDomainDecision)
  ) {
    return false;
  }
  const accepted = review.capability_decisions.filter(
    (item) => item.decision === "accepted",
  ).length;
  const needsEvidence = review.capability_decisions.filter(
    (item) => item.decision === "needs_evidence",
  ).length;
  const rejected = review.capability_decisions.filter(
    (item) => item.decision === "rejected",
  ).length;
  const expectedState = rejected ? "rejected" : needsEvidence ? "needs_evidence" : "accepted";
  return (
    review.schema_version === "atlas.mcp-builder-domain-review.v1" &&
    review.version === 1 &&
    review.state === expectedState &&
    review.review_profile === "atlas.domain-review.connector.v1" &&
    review.reviewer_contract_version === "mcp-builder-domain-review.v1" &&
    review.validation_profile === "atlas.static-validation.python312.v1" &&
    review.validator_version === "mcp-builder-static-validator.v1" &&
    review.domain_review_completed === true &&
    review.domain_review_accepted === (review.state === "accepted") &&
    review.accepted_count === accepted &&
    review.needs_evidence_count === needsEvidence &&
    review.rejected_count === rejected &&
    typeof review.review_id === "string" &&
    typeof review.reviewed_by === "string" &&
    typeof review.canonical_digest === "string" &&
    Array.isArray(review.limitations) &&
    review.limitations.length > 0 &&
    review.limitations.every((item) => typeof item === "string") &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeSecurityAssessment(
  value: unknown,
): value is McpBuilderSecurityReview["control_assessments"][number] {
  return (
    isRecord(value) &&
    [
      "provenance",
      "supply_chain",
      "credentials",
      "network",
      "input_output",
      "injection_execution",
      "logging_redaction",
      "runner_privileges",
      "capability_governance",
    ].includes(String(value.control)) &&
    ["accepted", "needs_remediation", "rejected"].includes(String(value.decision)) &&
    typeof value.assessment === "string" &&
    Array.isArray(value.evidence_references) &&
    value.evidence_references.length > 0 &&
    value.evidence_references.every((item) => typeof item === "string") &&
    Array.isArray(value.finding_codes) &&
    value.finding_codes.every((item) => typeof item === "string") &&
    (value.decision === "accepted"
      ? value.finding_codes.length === 0
      : value.finding_codes.length > 0) &&
    Array.isArray(value.required_controls) &&
    value.required_controls.length > 0 &&
    value.required_controls.every((item) => typeof item === "string")
  );
}

function isSafeSecurityReview(value: unknown): value is { data: McpBuilderSecurityReview } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const review = value.data;
  const assessments = review.control_assessments;
  const noAuthority = [
    review.lab_validation_completed,
    review.candidate_package_created,
    review.connector_registered,
    review.connector_installed,
    review.connector_enabled,
    review.network_request_performed,
    review.model_inference_performed,
    review.dependency_resolution_performed,
    review.malware_or_dynamic_scan_performed,
    review.runtime_self_test_performed,
    review.subprocess_invoked,
    review.dynamic_code_execution_performed,
    review.runtime_trust_granted,
    review.execution_authorized,
    review.infrastructure_mutation_performed,
  ];
  if (!Array.isArray(assessments) || assessments.length !== 9) return false;
  if (!assessments.every(isSafeSecurityAssessment)) return false;
  if (new Set(assessments.map((item) => item.control)).size !== 9) return false;
  const accepted = assessments.filter((item) => item.decision === "accepted").length;
  const needsRemediation = assessments.filter(
    (item) => item.decision === "needs_remediation",
  ).length;
  const rejected = assessments.filter((item) => item.decision === "rejected").length;
  const expectedState = rejected
    ? "rejected"
    : needsRemediation
      ? "needs_remediation"
      : "accepted";
  return (
    review.schema_version === "atlas.mcp-builder-security-review.v1" &&
    review.version === 1 &&
    review.state === expectedState &&
    review.review_profile === "atlas.security-review.connector.v1" &&
    review.reviewer_contract_version === "mcp-builder-security-review.v1" &&
    review.domain_review_profile === "atlas.domain-review.connector.v1" &&
    review.domain_reviewer_contract_version === "mcp-builder-domain-review.v1" &&
    review.reviewed_by !== review.domain_reviewed_by &&
    review.security_review_completed === true &&
    review.security_review_accepted === (review.state === "accepted") &&
    review.accepted_count === accepted &&
    review.needs_remediation_count === needsRemediation &&
    review.rejected_count === rejected &&
    typeof review.review_id === "string" &&
    typeof review.domain_review_id === "string" &&
    typeof review.canonical_digest === "string" &&
    Array.isArray(review.limitations) &&
    review.limitations.length > 0 &&
    review.limitations.every((item) => typeof item === "string") &&
    noAuthority.every((flag) => flag === false)
  );
}

const LAB_CHECK_CODES = [
  "lab.artifact_integrity",
  "lab.runner_isolation",
  "lab.secret_free_environment",
  "lab.network_denial",
  "lab.package_import",
  "lab.quarantine_contract",
  "lab.capability_fail_closed",
  "lab.bounded_output",
] as const;

function isSafeLabCheck(value: unknown): value is McpBuilderLabCheck {
  return (
    isRecord(value) &&
    LAB_CHECK_CODES.includes(value.code as McpBuilderLabCheck["code"]) &&
    ["passed", "failed", "skipped"].includes(String(value.state)) &&
    ["info", "error"].includes(String(value.severity)) &&
    typeof value.summary === "string" &&
    Array.isArray(value.evidence_paths) &&
    value.evidence_paths.every((item) => typeof item === "string") &&
    (value.remediation === null || typeof value.remediation === "string") &&
    (value.state === "passed"
      ? value.severity === "info" && value.remediation === null
      : value.severity === "error" && typeof value.remediation === "string")
  );
}

function isSafeLabValidation(
  value: unknown,
): value is { data: McpBuilderLabValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const validation = value.data;
  const checks = validation.checks;
  if (!Array.isArray(checks) || checks.length !== 8 || !checks.every(isSafeLabCheck)) {
    return false;
  }
  if (new Set(checks.map((item) => item.code)).size !== 8) return false;
  const passed = checks.filter((item) => item.state === "passed").length;
  const failed = checks.filter((item) => item.state === "failed").length;
  const skipped = checks.filter((item) => item.state === "skipped").length;
  const noAuthority = [
    validation.secret_values_present,
    validation.target_connected,
    validation.network_request_performed,
    validation.dependency_resolution_performed,
    validation.malware_or_dynamic_scan_performed,
    validation.candidate_package_created,
    validation.connector_registered,
    validation.connector_installed,
    validation.connector_enabled,
    validation.runtime_trust_granted,
    validation.execution_authorized,
    validation.infrastructure_mutation_performed,
  ];
  const expectedState = passed === 8 ? "passed" : "failed";
  return (
    validation.schema_version === "atlas.mcp-builder-lab-validation.v1" &&
    validation.version === 1 &&
    validation.state === expectedState &&
    validation.lab_profile === "atlas.lab-validation.python312.v1" &&
    validation.runner_contract_version === "mcp-builder-isolated-runner.v1" &&
    validation.lab_validation_completed === true &&
    validation.lab_validation_passed === (validation.state === "passed") &&
    validation.synthetic_fixture_used === true &&
    validation.workspace_removed === true &&
    validation.passed_count === passed &&
    validation.failed_count === failed &&
    validation.skipped_count === skipped &&
    validation.operated_by !== validation.domain_reviewed_by &&
    validation.operated_by !== validation.security_reviewed_by &&
    validation.runtime_self_test_performed === validation.child_started &&
    validation.subprocess_invoked === validation.child_started &&
    validation.dynamic_code_execution_performed === validation.child_started &&
    typeof validation.lab_validation_id === "string" &&
    typeof validation.security_review_id === "string" &&
    typeof validation.runtime_version === "string" &&
    typeof validation.canonical_digest === "string" &&
    Array.isArray(validation.limitations) &&
    validation.limitations.length > 0 &&
    validation.limitations.every((item) => typeof item === "string") &&
    noAuthority.every((flag) => flag === false)
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

export async function createMcpBuilderValidation(input: {
  project: McpBuilderProject;
  checkpoint: McpBuilderDesignCheckpoint;
  generation: McpBuilderGeneration;
}) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/validations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-validation.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-validation-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        checkpoint_id: input.checkpoint.checkpoint_id,
        checkpoint_digest: input.checkpoint.canonical_digest,
        generation_id: input.generation.generation_id,
        generation_digest: input.generation.canonical_digest,
        artifact_digest: input.generation.artifact_digest,
        validation_profile: "atlas.static-validation.python312.v1",
        acknowledged_static_only: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder validation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeValidation(payload)) {
    throw new Error("MCP Builder returned unsafe validation data");
  }
  return payload;
}

export async function createMcpBuilderDomainReview(input: {
  project: McpBuilderProject;
  checkpoint: McpBuilderDesignCheckpoint;
  generation: McpBuilderGeneration;
  validation: McpBuilderValidation;
  decisions: McpBuilderDomainDecision[];
  summary: string;
}) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/domain-reviews`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-domain-review.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-domain-review-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        checkpoint_id: input.checkpoint.checkpoint_id,
        checkpoint_digest: input.checkpoint.canonical_digest,
        generation_id: input.generation.generation_id,
        generation_digest: input.generation.canonical_digest,
        artifact_digest: input.generation.artifact_digest,
        validation_id: input.validation.validation_id,
        validation_digest: input.validation.canonical_digest,
        validation_profile: input.validation.validation_profile,
        validator_version: input.validation.validator_version,
        review_profile: "atlas.domain-review.connector.v1",
        acknowledged_human_domain_decision: true,
        capability_decisions: input.decisions.map((decision) => ({
          candidate_id: decision.candidateId,
          confirmed_class: decision.confirmedClass,
          decision: decision.decision,
          supported_product_versions: decision.supportedProductVersions,
          vendor_permission: decision.vendorPermission,
          authentication_assessment: decision.authenticationAssessment,
          side_effect_assessment: decision.sideEffectAssessment,
          error_behavior_assessment: decision.errorBehaviorAssessment,
          health_guidance_assessment: decision.healthGuidanceAssessment,
          evidence_citations: decision.evidenceCitations,
          missing_case_codes: decision.missingCaseCodes,
          rationale: decision.rationale,
        })),
        summary: input.summary,
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder domain review failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeDomainReview(payload)) {
    throw new Error("MCP Builder returned an unsafe domain review");
  }
  return payload;
}

export async function createMcpBuilderSecurityReview(input: {
  project: McpBuilderProject;
  checkpoint: McpBuilderDesignCheckpoint;
  generation: McpBuilderGeneration;
  validation: McpBuilderValidation;
  domainReview: McpBuilderDomainReview;
  assessments: McpBuilderSecurityAssessment[];
  summary: string;
}) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/security-reviews`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-security-review.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-security-review-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        checkpoint_id: input.checkpoint.checkpoint_id,
        checkpoint_digest: input.checkpoint.canonical_digest,
        generation_id: input.generation.generation_id,
        generation_digest: input.generation.canonical_digest,
        artifact_digest: input.generation.artifact_digest,
        validation_id: input.validation.validation_id,
        validation_digest: input.validation.canonical_digest,
        validation_profile: input.validation.validation_profile,
        validator_version: input.validation.validator_version,
        domain_review_id: input.domainReview.review_id,
        domain_review_digest: input.domainReview.canonical_digest,
        domain_review_profile: input.domainReview.review_profile,
        domain_reviewer_contract_version: input.domainReview.reviewer_contract_version,
        review_profile: "atlas.security-review.connector.v1",
        acknowledged_independent_security_decision: true,
        control_assessments: input.assessments.map((assessment) => ({
          control: assessment.control,
          decision: assessment.decision,
          assessment: assessment.assessment,
          evidence_references: assessment.evidenceReferences,
          finding_codes: assessment.findingCodes,
          required_controls: assessment.requiredControls,
        })),
        summary: input.summary,
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder security review failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeSecurityReview(payload)) {
    throw new Error("MCP Builder returned an unsafe security review");
  }
  return payload;
}

export async function createMcpBuilderLabValidation(input: {
  project: McpBuilderProject;
  checkpoint: McpBuilderDesignCheckpoint;
  generation: McpBuilderGeneration;
  validation: McpBuilderValidation;
  domainReview: McpBuilderDomainReview;
  securityReview: McpBuilderSecurityReview;
}) {
  const response = await apiFetch(
    `/api/v1/mcp-builder/projects/${input.project.project_id}/lab-validations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `mcp-builder-lab-validation.${nonce()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.mcp-builder-lab-validation-request.v1",
        project_version: input.project.version,
        project_digest: input.project.canonical_digest,
        source_digest: input.project.source_digest,
        checkpoint_id: input.checkpoint.checkpoint_id,
        checkpoint_digest: input.checkpoint.canonical_digest,
        generation_id: input.generation.generation_id,
        generation_digest: input.generation.canonical_digest,
        artifact_digest: input.generation.artifact_digest,
        validation_id: input.validation.validation_id,
        validation_digest: input.validation.canonical_digest,
        domain_review_id: input.domainReview.review_id,
        domain_review_digest: input.domainReview.canonical_digest,
        security_review_id: input.securityReview.review_id,
        security_review_digest: input.securityReview.canonical_digest,
        lab_profile: "atlas.lab-validation.python312.v1",
        acknowledged_isolated_synthetic_execution: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`MCP Builder lab validation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeLabValidation(payload)) {
    throw new Error("MCP Builder returned unsafe lab validation evidence");
  }
  return payload;
}
