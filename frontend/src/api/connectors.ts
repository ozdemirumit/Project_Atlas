import { apiFetch } from "./client";
import type { McpBuilderCandidateHandoff } from "./mcpBuilder";

export type ConnectorPackageAcquisition = {
  acquisition_id: string;
  schema_version: "atlas.connector-package-acquisition.v1";
  version: 1;
  state: "quarantined";
  source_type: "mcp_builder_handoff";
  source_handoff_id: string;
  source_handoff_digest: string;
  source_project_id: string;
  source_custodied_by: string;
  organization_id: string;
  environment_id: string;
  acquired_by: string;
  acquisition_profile: "atlas.connector-acquisition.builder-handoff.v1";
  archive_contract_version: "mcp-builder-candidate-zip.v1";
  package_filename: string;
  package_digest: string;
  package_size_bytes: number;
  publisher_identity: "unattested.generated";
  signature_state: "unsigned";
  attestation_state: "unattested";
  capabilities: Array<{
    capability_id: string;
    capability_class: "C0" | "C1";
    required_permission: string;
    supported_product_versions: string[];
  }>;
  limitations: string[];
  canonical_digest: string;
  acquired_at: string;
  package_acquired: true;
  integrity_verified: true;
  package_signed: false;
  publisher_attested: false;
  registry_validation_completed: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-validation.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_acquisition_id: string;
  source_acquisition_digest: string;
  source_handoff_id: string;
  source_handoff_digest: string;
  source_project_id: string;
  source_acquired_by: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  validation_profile: "atlas.connector-validation-intake.builder-v1";
  validator_version: "atlas.connector-manifest-schema-validator.v1";
  package_digest: string;
  package_size_bytes: number;
  manifest_path: "atlas-connector.yaml";
  manifest_digest: string | null;
  capability_ids: string[];
  schema_evidence: Array<{
    relative_path: string;
    digest: string;
    schema_id: string;
    purpose: "configuration" | "capability_input" | "capability_output";
    capability_id: string | null;
  }>;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    evidence_paths: string[];
    remediation: string;
  }>;
  limitations: string[];
  canonical_digest: string;
  validated_at: string;
  source_integrity_accepted: true;
  manifest_schema_validation_completed: true;
  dependency_scan_completed: false;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  secret_content_scan_completed: false;
  license_scan_completed: false;
  static_code_validation_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageSupplyChainInventory = {
  inventory_id: string;
  schema_version: "atlas.connector-package-supply-chain-inventory.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_validation_id: string;
  source_validation_digest: string;
  source_acquisition_id: string;
  source_acquisition_digest: string;
  source_handoff_id: string;
  source_project_id: string;
  source_acquired_by: string;
  source_validated_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  inventoried_by: string;
  inventory_profile: "atlas.connector-supply-chain-inventory.python312.v1";
  inspector_version: "atlas.connector-content-dependency-inspector.v1";
  package_digest: string;
  package_size_bytes: number;
  files: Array<{
    relative_path: string;
    digest: string;
    size_bytes: number;
    content_class: string;
  }>;
  dependencies: Array<{
    name: string;
    version_constraint: string;
    kind: "build" | "runtime";
    source_path: "pyproject.toml";
  }>;
  inventory_digest: string;
  dependency_set_digest: string;
  runtime_dependency_count: number;
  build_dependency_count: number;
  dependency_lock_present: false;
  checks: ConnectorPackageValidation["checks"];
  limitations: string[];
  canonical_digest: string;
  inventoried_at: string;
  content_inventory_completed: true;
  dependency_inventory_completed: true;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  secret_content_scan_completed: false;
  prohibited_content_scan_completed: false;
  license_scan_completed: false;
  static_code_validation_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_rejected: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageContentPolicyScan = {
  scan_id: string;
  schema_version: "atlas.connector-package-content-policy-scan.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_inventory_id: string;
  source_inventory_digest: string;
  source_validation_id: string;
  source_validation_digest: string;
  source_acquisition_id: string;
  source_acquisition_digest: string;
  source_handoff_id: string;
  source_project_id: string;
  source_acquired_by: string;
  source_validated_by: string;
  source_inventoried_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  scanned_by: string;
  scan_profile: "atlas.connector-content-policy-scan.python312.v1";
  scanner_version: "atlas.connector-secret-prohibited-content-scanner.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  dependency_set_digest: string;
  scanned_file_count: number;
  findings: Array<{
    rule_code: string;
    kind: "embedded_secret" | "prohibited_content";
    severity: "error";
    relative_path: string;
    line_number: number | null;
    evidence_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  content_scan_digest: string;
  checks: ConnectorPackageValidation["checks"];
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  scanned_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  license_scan_completed: false;
  static_code_validation_completed: false;
  schema_semantic_validation_completed: false;
  permission_behavior_validation_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_rejected: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageSchemaSemanticsValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-schema-semantics-validation.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_content_policy_scan_id: string;
  source_content_policy_scan_digest: string;
  source_inventory_id: string;
  source_inventory_digest: string;
  source_validation_id: string;
  source_validation_digest: string;
  source_acquisition_id: string;
  source_acquisition_digest: string;
  source_handoff_id: string;
  source_project_id: string;
  source_acquired_by: string;
  source_manifest_validated_by: string;
  source_inventoried_by: string;
  source_content_scanned_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  validation_profile: "atlas.connector-schema-semantics.python312.v1";
  validator_version: "atlas.connector-configuration-capability-schema-validator.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  content_scan_digest: string;
  schemas: Array<{
    relative_path: string;
    digest: string;
    purpose: "configuration" | "capability_input" | "capability_output";
    capability_id: string | null;
    property_count: number;
    required_count: number;
    closed_object: boolean;
    semantically_complete: boolean;
  }>;
  schema_set_digest: string;
  findings: Array<{
    rule_code: string;
    kind: "configuration" | "capability_input" | "capability_output";
    severity: "error";
    relative_path: string;
    json_pointer: string;
    evidence_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  semantic_validation_digest: string;
  checks: ConnectorPackageValidation["checks"];
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  license_scan_completed: false;
  static_code_validation_completed: false;
  permission_behavior_validation_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_rejected: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageAuthorityBehaviorValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-authority-behavior-validation.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_schema_semantics_validation_id: string;
  source_schema_semantics_validation_digest: string;
  source_content_policy_scan_id: string;
  source_inventory_id: string;
  source_validation_id: string;
  source_acquisition_id: string;
  source_handoff_id: string;
  source_project_id: string;
  source_acquired_by: string;
  source_manifest_validated_by: string;
  source_inventoried_by: string;
  source_content_scanned_by: string;
  source_schema_validated_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  validation_profile: "atlas.connector-authority-behavior.python312.v1";
  analyzer_version: "atlas.connector-declared-authority-ast-analyzer.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  semantic_validation_digest: string;
  capabilities: Array<{
    capability_id: string;
    declared_class: string;
    required_permission: string;
    module_path: string;
    source_digest: string;
    observed_categories: Array<
      | "declaration"
      | "read"
      | "mutation"
      | "network"
      | "process"
      | "filesystem"
      | "dynamic_execution"
      | "ambiguous"
    >;
    network_call_count: number;
    mutation_call_count: number;
    declaration_matches: boolean;
    permission_matches: boolean;
    behavior_compatible: boolean;
    statically_resolved: boolean;
  }>;
  capability_set_digest: string;
  findings: Array<{
    rule_code: string;
    category: string;
    severity: "error";
    relative_path: string;
    line_number: number;
    evidence_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  behavior_validation_digest: string;
  checks: ConnectorPackageValidation["checks"];
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  license_scan_completed: false;
  static_code_validation_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_rejected: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorPackageStaticDependencyAnalysis = {
  analysis_id: string;
  schema_version: "atlas.connector-package-static-dependency-analysis.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_authority_behavior_validation_id: string;
  source_authority_behavior_validation_digest: string;
  source_schema_semantics_validation_id: string;
  source_content_policy_scan_id: string;
  source_inventory_id: string;
  source_validation_id: string;
  source_acquisition_id: string;
  source_handoff_id: string;
  source_project_id: string;
  source_acquired_by: string;
  source_manifest_validated_by: string;
  source_inventoried_by: string;
  source_content_scanned_by: string;
  source_schema_validated_by: string;
  source_authority_validated_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  analyzed_by: string;
  analysis_profile: "atlas.connector-static-dependency.python312.v1";
  analyzer_version: "atlas.connector-static-dependency-analyzer.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  source_summary: {
    source_file_count: number;
    module_count: number;
    function_count: number;
    import_count: number;
    external_import_count: number;
    unresolved_import_count: number;
    source_set_digest: string;
  };
  dependency_summary: {
    runtime_dependency_count: number;
    build_dependency_count: number;
    imported_dependency_count: number;
    dependency_lock_present: boolean;
    dependency_lock_required: boolean;
    dependency_set_digest: string;
    metadata_consistent: boolean;
    imports_reconciled: boolean;
    deterministic_constraints: boolean;
  };
  findings: Array<{
    rule_code: string;
    category: string;
    severity: "error";
    relative_path: string;
    line_number: number;
    evidence_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  analysis_digest: string;
  checks: ConnectorPackageValidation["checks"];
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  analyzed_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: false;
  malware_scan_completed: false;
  license_scan_completed: false;
  contract_validation_completed: false;
  runner_validation_completed: false;
  lab_validation_completed: false;
  package_signed: false;
  publisher_attested: false;
  connector_rejected: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isValidationCheck(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    (value.state === "passed" || value.state === "failed") &&
    (value.severity === "informational" || value.severity === "error") &&
    typeof value.summary === "string" &&
    isStringArray(value.evidence_paths) &&
    typeof value.remediation === "string"
  );
}

function isSchemaEvidence(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.relative_path === "string" &&
    typeof value.digest === "string" &&
    value.digest.length === 64 &&
    typeof value.schema_id === "string" &&
    ["configuration", "capability_input", "capability_output"].includes(
      String(value.purpose),
    ) &&
    (value.capability_id === null || typeof value.capability_id === "string")
  );
}

function isSafeValidation(value: unknown): value is { data: ConnectorPackageValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const validation = value.data;
  const checks: unknown[] = Array.isArray(validation.checks) ? validation.checks : [];
  const schemas: unknown[] = Array.isArray(validation.schema_evidence)
    ? validation.schema_evidence
    : [];
  const noAuthority = [
    validation.dependency_scan_completed,
    validation.vulnerability_scan_completed,
    validation.malware_scan_completed,
    validation.secret_content_scan_completed,
    validation.license_scan_completed,
    validation.static_code_validation_completed,
    validation.contract_validation_completed,
    validation.runner_validation_completed,
    validation.lab_validation_completed,
    validation.package_signed,
    validation.publisher_attested,
    validation.connector_registered,
    validation.connector_approved,
    validation.connector_installed,
    validation.connector_enabled,
    validation.target_configured,
    validation.credentials_resolved,
    validation.runtime_trust_granted,
    validation.execution_authorized,
    validation.deployment_approved,
    validation.infrastructure_mutation_performed,
  ];
  return (
    validation.schema_version === "atlas.connector-package-validation.v1" &&
    validation.version === 1 &&
    validation.lifecycle === "validating" &&
    (validation.outcome === "passed" || validation.outcome === "failed") &&
    validation.validation_profile === "atlas.connector-validation-intake.builder-v1" &&
    validation.validator_version === "atlas.connector-manifest-schema-validator.v1" &&
    validation.manifest_path === "atlas-connector.yaml" &&
    validation.source_integrity_accepted === true &&
    validation.manifest_schema_validation_completed === true &&
    typeof validation.validated_by === "string" &&
    typeof validation.source_acquired_by === "string" &&
    validation.validated_by !== validation.source_acquired_by &&
    typeof validation.package_digest === "string" &&
    validation.package_digest.length === 64 &&
    typeof validation.canonical_digest === "string" &&
    validation.canonical_digest.length === 64 &&
    (validation.manifest_digest === null ||
      (typeof validation.manifest_digest === "string" && validation.manifest_digest.length === 64)) &&
    isStringArray(validation.capability_ids) &&
    validation.capability_ids.length > 0 &&
    isStringArray(validation.limitations) &&
    validation.limitations.length > 0 &&
    checks.length === 4 &&
    checks.every(isValidationCheck) &&
    schemas.every(isSchemaEvidence) &&
    noAuthority.every((flag) => flag === false)
  );
}

function isInventoryFile(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.relative_path === "string" &&
    typeof value.digest === "string" &&
    value.digest.length === 64 &&
    typeof value.size_bytes === "number" &&
    value.size_bytes > 0 &&
    typeof value.content_class === "string"
  );
}

function isInventoryDependency(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.version_constraint === "string" &&
    (value.kind === "build" || value.kind === "runtime") &&
    value.source_path === "pyproject.toml"
  );
}

function isSafeInventory(
  value: unknown,
): value is { data: ConnectorPackageSupplyChainInventory } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const inventory = value.data;
  const files: unknown[] = Array.isArray(inventory.files) ? inventory.files : [];
  const dependencies: unknown[] = Array.isArray(inventory.dependencies)
    ? inventory.dependencies
    : [];
  const checks: unknown[] = Array.isArray(inventory.checks) ? inventory.checks : [];
  const sourceActors = [
    inventory.source_acquired_by,
    inventory.source_validated_by,
    inventory.source_custodied_by,
    inventory.source_domain_reviewed_by,
    inventory.source_security_reviewed_by,
    inventory.source_lab_operated_by,
  ];
  const noAuthority = [
    inventory.vulnerability_scan_completed,
    inventory.malware_scan_completed,
    inventory.secret_content_scan_completed,
    inventory.prohibited_content_scan_completed,
    inventory.license_scan_completed,
    inventory.static_code_validation_completed,
    inventory.contract_validation_completed,
    inventory.runner_validation_completed,
    inventory.lab_validation_completed,
    inventory.package_signed,
    inventory.publisher_attested,
    inventory.connector_rejected,
    inventory.connector_registered,
    inventory.connector_approved,
    inventory.connector_installed,
    inventory.connector_enabled,
    inventory.target_configured,
    inventory.credentials_resolved,
    inventory.runtime_trust_granted,
    inventory.execution_authorized,
    inventory.deployment_approved,
    inventory.infrastructure_mutation_performed,
  ];
  return (
    inventory.schema_version === "atlas.connector-package-supply-chain-inventory.v1" &&
    inventory.version === 1 &&
    inventory.lifecycle === "validating" &&
    (inventory.outcome === "passed" || inventory.outcome === "failed") &&
    inventory.inventory_profile === "atlas.connector-supply-chain-inventory.python312.v1" &&
    inventory.inspector_version === "atlas.connector-content-dependency-inspector.v1" &&
    inventory.content_inventory_completed === true &&
    inventory.dependency_inventory_completed === true &&
    inventory.dependency_lock_present === false &&
    typeof inventory.inventoried_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(inventory.inventoried_by) &&
    typeof inventory.package_digest === "string" &&
    inventory.package_digest.length === 64 &&
    typeof inventory.inventory_digest === "string" &&
    inventory.inventory_digest.length === 64 &&
    typeof inventory.dependency_set_digest === "string" &&
    inventory.dependency_set_digest.length === 64 &&
    typeof inventory.canonical_digest === "string" &&
    inventory.canonical_digest.length === 64 &&
    typeof inventory.package_size_bytes === "number" &&
    inventory.package_size_bytes > 0 &&
    files.length > 0 &&
    files.every(isInventoryFile) &&
    dependencies.every(isInventoryDependency) &&
    typeof inventory.runtime_dependency_count === "number" &&
    typeof inventory.build_dependency_count === "number" &&
    isStringArray(inventory.limitations) &&
    inventory.limitations.length > 0 &&
    checks.length === 5 &&
    checks.every(isValidationCheck) &&
    noAuthority.every((flag) => flag === false)
  );
}

function isContentPolicyFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_code === "string" &&
    (value.kind === "embedded_secret" || value.kind === "prohibited_content") &&
    value.severity === "error" &&
    typeof value.relative_path === "string" &&
    (value.line_number === null ||
      (typeof value.line_number === "number" && value.line_number > 0)) &&
    typeof value.evidence_fingerprint === "string" &&
    value.evidence_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeContentPolicyScan(
  value: unknown,
): value is { data: ConnectorPackageContentPolicyScan } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const scan = value.data;
  const findings: unknown[] = Array.isArray(scan.findings) ? scan.findings : [];
  const checks: unknown[] = Array.isArray(scan.checks) ? scan.checks : [];
  const sourceActors = [
    scan.source_acquired_by,
    scan.source_validated_by,
    scan.source_inventoried_by,
    scan.source_custodied_by,
    scan.source_domain_reviewed_by,
    scan.source_security_reviewed_by,
    scan.source_lab_operated_by,
  ];
  const noAuthority = [
    scan.vulnerability_scan_completed,
    scan.malware_scan_completed,
    scan.license_scan_completed,
    scan.static_code_validation_completed,
    scan.schema_semantic_validation_completed,
    scan.permission_behavior_validation_completed,
    scan.contract_validation_completed,
    scan.runner_validation_completed,
    scan.lab_validation_completed,
    scan.package_signed,
    scan.publisher_attested,
    scan.connector_rejected,
    scan.connector_registered,
    scan.connector_approved,
    scan.connector_installed,
    scan.connector_enabled,
    scan.target_configured,
    scan.credentials_resolved,
    scan.runtime_trust_granted,
    scan.execution_authorized,
    scan.deployment_approved,
    scan.infrastructure_mutation_performed,
  ];
  return (
    scan.schema_version === "atlas.connector-package-content-policy-scan.v1" &&
    scan.version === 1 &&
    scan.lifecycle === "validating" &&
    (scan.outcome === "passed" || scan.outcome === "failed") &&
    scan.promotion_blocked === (scan.outcome === "failed") &&
    scan.scan_profile === "atlas.connector-content-policy-scan.python312.v1" &&
    scan.scanner_version === "atlas.connector-secret-prohibited-content-scanner.v1" &&
    scan.secret_content_scan_completed === true &&
    scan.prohibited_content_scan_completed === true &&
    typeof scan.scanned_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(scan.scanned_by) &&
    typeof scan.package_digest === "string" &&
    scan.package_digest.length === 64 &&
    typeof scan.inventory_digest === "string" &&
    scan.inventory_digest.length === 64 &&
    typeof scan.dependency_set_digest === "string" &&
    scan.dependency_set_digest.length === 64 &&
    typeof scan.finding_set_digest === "string" &&
    scan.finding_set_digest.length === 64 &&
    typeof scan.content_scan_digest === "string" &&
    scan.content_scan_digest.length === 64 &&
    typeof scan.canonical_digest === "string" &&
    scan.canonical_digest.length === 64 &&
    typeof scan.package_size_bytes === "number" &&
    scan.package_size_bytes > 0 &&
    typeof scan.scanned_file_count === "number" &&
    scan.scanned_file_count > 0 &&
    findings.length <= 500 &&
    findings.every(isContentPolicyFinding) &&
    checks.length === 5 &&
    checks.every(isValidationCheck) &&
    isStringArray(scan.limitations) &&
    scan.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSchemaSemanticsSummary(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.relative_path === "string" &&
    typeof value.digest === "string" &&
    value.digest.length === 64 &&
    ["configuration", "capability_input", "capability_output"].includes(
      String(value.purpose),
    ) &&
    (value.capability_id === null || typeof value.capability_id === "string") &&
    typeof value.property_count === "number" &&
    typeof value.required_count === "number" &&
    typeof value.closed_object === "boolean" &&
    typeof value.semantically_complete === "boolean"
  );
}

function isSchemaSemanticsFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_code === "string" &&
    ["configuration", "capability_input", "capability_output"].includes(
      String(value.kind),
    ) &&
    value.severity === "error" &&
    typeof value.relative_path === "string" &&
    typeof value.json_pointer === "string" &&
    typeof value.evidence_fingerprint === "string" &&
    value.evidence_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isCapabilityBehaviorSummary(value: unknown): boolean {
  const categories = [
    "declaration",
    "read",
    "mutation",
    "network",
    "process",
    "filesystem",
    "dynamic_execution",
    "ambiguous",
  ];
  return (
    isRecord(value) &&
    typeof value.capability_id === "string" &&
    typeof value.declared_class === "string" &&
    typeof value.required_permission === "string" &&
    typeof value.module_path === "string" &&
    typeof value.source_digest === "string" &&
    value.source_digest.length === 64 &&
    isStringArray(value.observed_categories) &&
    value.observed_categories.length > 0 &&
    value.observed_categories.every((category) => categories.includes(category)) &&
    typeof value.network_call_count === "number" &&
    typeof value.mutation_call_count === "number" &&
    typeof value.declaration_matches === "boolean" &&
    typeof value.permission_matches === "boolean" &&
    typeof value.behavior_compatible === "boolean" &&
    typeof value.statically_resolved === "boolean"
  );
}

function isAuthorityBehaviorFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_code === "string" &&
    typeof value.category === "string" &&
    value.severity === "error" &&
    typeof value.relative_path === "string" &&
    typeof value.line_number === "number" &&
    typeof value.evidence_fingerprint === "string" &&
    value.evidence_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeAuthorityBehaviorValidation(
  value: unknown,
): value is { data: ConnectorPackageAuthorityBehaviorValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  const capabilities: unknown[] = Array.isArray(report.capabilities)
    ? report.capabilities
    : [];
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const noAuthority = [
    report.vulnerability_scan_completed,
    report.malware_scan_completed,
    report.license_scan_completed,
    report.static_code_validation_completed,
    report.contract_validation_completed,
    report.runner_validation_completed,
    report.lab_validation_completed,
    report.package_signed,
    report.publisher_attested,
    report.connector_rejected,
    report.connector_registered,
    report.connector_approved,
    report.connector_installed,
    report.connector_enabled,
    report.target_configured,
    report.credentials_resolved,
    report.runtime_trust_granted,
    report.execution_authorized,
    report.deployment_approved,
    report.infrastructure_mutation_performed,
  ];
  return (
    report.schema_version === "atlas.connector-package-authority-behavior-validation.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.validation_profile === "atlas.connector-authority-behavior.python312.v1" &&
    report.analyzer_version === "atlas.connector-declared-authority-ast-analyzer.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    typeof report.validated_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.validated_by) &&
    typeof report.package_digest === "string" &&
    report.package_digest.length === 64 &&
    typeof report.inventory_digest === "string" &&
    report.inventory_digest.length === 64 &&
    typeof report.semantic_validation_digest === "string" &&
    report.semantic_validation_digest.length === 64 &&
    typeof report.capability_set_digest === "string" &&
    report.capability_set_digest.length === 64 &&
    typeof report.finding_set_digest === "string" &&
    report.finding_set_digest.length === 64 &&
    typeof report.behavior_validation_digest === "string" &&
    report.behavior_validation_digest.length === 64 &&
    typeof report.canonical_digest === "string" &&
    report.canonical_digest.length === 64 &&
    capabilities.length > 0 &&
    capabilities.every(isCapabilityBehaviorSummary) &&
    findings.length <= 500 &&
    findings.every(isAuthorityBehaviorFinding) &&
    checks.length === 5 &&
    checks.every(isValidationCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeStaticDependencyAnalysis(
  value: unknown,
): value is { data: ConnectorPackageStaticDependencyAnalysis } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  if (!isRecord(report.source_summary) || !isRecord(report.dependency_summary)) return false;
  const source = report.source_summary;
  const dependency = report.dependency_summary;
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_authority_validated_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const counts = [
    source.source_file_count,
    source.module_count,
    source.function_count,
    source.import_count,
    source.external_import_count,
    source.unresolved_import_count,
    dependency.runtime_dependency_count,
    dependency.build_dependency_count,
    dependency.imported_dependency_count,
  ];
  const noAuthority = [
    report.vulnerability_scan_completed,
    report.malware_scan_completed,
    report.license_scan_completed,
    report.contract_validation_completed,
    report.runner_validation_completed,
    report.lab_validation_completed,
    report.package_signed,
    report.publisher_attested,
    report.connector_rejected,
    report.connector_registered,
    report.connector_approved,
    report.connector_installed,
    report.connector_enabled,
    report.target_configured,
    report.credentials_resolved,
    report.runtime_trust_granted,
    report.execution_authorized,
    report.deployment_approved,
    report.infrastructure_mutation_performed,
  ];
  return (
    report.schema_version === "atlas.connector-package-static-dependency-analysis.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.analysis_profile === "atlas.connector-static-dependency.python312.v1" &&
    report.analyzer_version === "atlas.connector-static-dependency-analyzer.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    typeof report.analyzed_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.analyzed_by) &&
    counts.every((count) => typeof count === "number" && count >= 0) &&
    typeof source.source_file_count === "number" &&
    source.source_file_count > 0 &&
    typeof source.source_set_digest === "string" &&
    source.source_set_digest.length === 64 &&
    typeof dependency.dependency_set_digest === "string" &&
    dependency.dependency_set_digest.length === 64 &&
    typeof dependency.dependency_lock_present === "boolean" &&
    typeof dependency.runtime_dependency_count === "number" &&
    dependency.dependency_lock_required === (dependency.runtime_dependency_count > 0) &&
    typeof dependency.metadata_consistent === "boolean" &&
    typeof dependency.imports_reconciled === "boolean" &&
    typeof dependency.deterministic_constraints === "boolean" &&
    typeof report.package_digest === "string" &&
    report.package_digest.length === 64 &&
    typeof report.inventory_digest === "string" &&
    report.inventory_digest.length === 64 &&
    typeof report.finding_set_digest === "string" &&
    report.finding_set_digest.length === 64 &&
    typeof report.analysis_digest === "string" &&
    report.analysis_digest.length === 64 &&
    typeof report.canonical_digest === "string" &&
    report.canonical_digest.length === 64 &&
    findings.length <= 500 &&
    findings.every(isAuthorityBehaviorFinding) &&
    checks.length === 5 &&
    checks.every(isValidationCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeSchemaSemanticsValidation(
  value: unknown,
): value is { data: ConnectorPackageSchemaSemanticsValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  const schemas: unknown[] = Array.isArray(report.schemas) ? report.schemas : [];
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const noAuthority = [
    report.vulnerability_scan_completed,
    report.malware_scan_completed,
    report.license_scan_completed,
    report.static_code_validation_completed,
    report.permission_behavior_validation_completed,
    report.contract_validation_completed,
    report.runner_validation_completed,
    report.lab_validation_completed,
    report.package_signed,
    report.publisher_attested,
    report.connector_rejected,
    report.connector_registered,
    report.connector_approved,
    report.connector_installed,
    report.connector_enabled,
    report.target_configured,
    report.credentials_resolved,
    report.runtime_trust_granted,
    report.execution_authorized,
    report.deployment_approved,
    report.infrastructure_mutation_performed,
  ];
  return (
    report.schema_version === "atlas.connector-package-schema-semantics-validation.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.validation_profile === "atlas.connector-schema-semantics.python312.v1" &&
    report.validator_version ===
      "atlas.connector-configuration-capability-schema-validator.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    typeof report.validated_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.validated_by) &&
    typeof report.package_digest === "string" &&
    report.package_digest.length === 64 &&
    typeof report.inventory_digest === "string" &&
    report.inventory_digest.length === 64 &&
    typeof report.content_scan_digest === "string" &&
    report.content_scan_digest.length === 64 &&
    typeof report.schema_set_digest === "string" &&
    report.schema_set_digest.length === 64 &&
    typeof report.finding_set_digest === "string" &&
    report.finding_set_digest.length === 64 &&
    typeof report.semantic_validation_digest === "string" &&
    report.semantic_validation_digest.length === 64 &&
    typeof report.canonical_digest === "string" &&
    report.canonical_digest.length === 64 &&
    schemas.length > 0 &&
    schemas.every(isSchemaSemanticsSummary) &&
    findings.length <= 500 &&
    findings.every(isSchemaSemanticsFinding) &&
    checks.length === 5 &&
    checks.every(isValidationCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeAcquisition(
  value: unknown,
): value is { data: ConnectorPackageAcquisition } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const acquisition = value.data;
  const capabilities: unknown[] = Array.isArray(acquisition.capabilities)
    ? acquisition.capabilities
    : [];
  const noAuthority = [
    acquisition.package_signed,
    acquisition.publisher_attested,
    acquisition.registry_validation_completed,
    acquisition.connector_registered,
    acquisition.connector_approved,
    acquisition.connector_installed,
    acquisition.connector_enabled,
    acquisition.target_configured,
    acquisition.credentials_resolved,
    acquisition.runtime_trust_granted,
    acquisition.execution_authorized,
    acquisition.deployment_approved,
    acquisition.infrastructure_mutation_performed,
  ];
  return (
    acquisition.schema_version === "atlas.connector-package-acquisition.v1" &&
    acquisition.version === 1 &&
    acquisition.state === "quarantined" &&
    acquisition.source_type === "mcp_builder_handoff" &&
    acquisition.acquisition_profile === "atlas.connector-acquisition.builder-handoff.v1" &&
    acquisition.archive_contract_version === "mcp-builder-candidate-zip.v1" &&
    acquisition.publisher_identity === "unattested.generated" &&
    acquisition.signature_state === "unsigned" &&
    acquisition.attestation_state === "unattested" &&
    acquisition.package_acquired === true &&
    acquisition.integrity_verified === true &&
    acquisition.acquired_by !== acquisition.source_custodied_by &&
    typeof acquisition.package_digest === "string" &&
    acquisition.package_digest.length === 64 &&
    typeof acquisition.canonical_digest === "string" &&
    acquisition.canonical_digest.length === 64 &&
    typeof acquisition.package_size_bytes === "number" &&
    acquisition.package_size_bytes > 0 &&
    acquisition.package_size_bytes <= 25_000_000 &&
    Array.isArray(acquisition.limitations) &&
    acquisition.limitations.length > 0 &&
    capabilities.length > 0 &&
    capabilities.every(
      (item) =>
        isRecord(item) &&
        typeof item.capability_id === "string" &&
        (item.capability_class === "C0" || item.capability_class === "C1") &&
        typeof item.required_permission === "string" &&
        Array.isArray(item.supported_product_versions),
    ) &&
    noAuthority.every((flag) => flag === false)
  );
}

export async function acquireConnectorPackage(handoff: McpBuilderCandidateHandoff) {
  const response = await apiFetch("/api/v1/connectors/package-acquisitions", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-acquisition.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-acquisition-request.v1",
      source_handoff_id: handoff.handoff_id,
      source_handoff_digest: handoff.canonical_digest,
      package_digest: handoff.package_digest,
      acquisition_profile: "atlas.connector-acquisition.builder-handoff.v1",
      acknowledged_unsigned_unattested_quarantine: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package acquisition failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeAcquisition(payload)) {
    throw new Error("Connector registry returned unsafe package acquisition evidence");
  }
  const acquisition = payload.data;
  if (
    acquisition.source_handoff_id !== handoff.handoff_id ||
    acquisition.source_handoff_digest !== handoff.canonical_digest ||
    acquisition.source_project_id !== handoff.project_id ||
    acquisition.source_custodied_by !== handoff.custodied_by ||
    acquisition.organization_id !== handoff.organization_id ||
    acquisition.environment_id !== handoff.environment_id ||
    acquisition.package_filename !== handoff.package_filename ||
    acquisition.package_digest !== handoff.package_digest ||
    acquisition.package_size_bytes !== handoff.package_size_bytes ||
    acquisition.capabilities.length !== handoff.capabilities.length ||
    acquisition.capabilities.some(
      (item, index) => item.capability_id !== handoff.capabilities[index]?.candidate_id,
    )
  ) {
    throw new Error("Connector acquisition does not match the exact Builder handoff");
  }
  return payload;
}

export async function validateConnectorPackage(acquisition: ConnectorPackageAcquisition) {
  const response = await apiFetch("/api/v1/connectors/package-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-validation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-validation-request.v1",
      source_acquisition_id: acquisition.acquisition_id,
      source_acquisition_digest: acquisition.canonical_digest,
      package_digest: acquisition.package_digest,
      validation_profile: "atlas.connector-validation-intake.builder-v1",
      acknowledged_untrusted_quarantined_package: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeValidation(payload)) {
    throw new Error("Connector registry returned unsafe package validation evidence");
  }
  const validation = payload.data;
  if (
    validation.source_acquisition_id !== acquisition.acquisition_id ||
    validation.source_acquisition_digest !== acquisition.canonical_digest ||
    validation.source_handoff_id !== acquisition.source_handoff_id ||
    validation.source_handoff_digest !== acquisition.source_handoff_digest ||
    validation.source_project_id !== acquisition.source_project_id ||
    validation.organization_id !== acquisition.organization_id ||
    validation.environment_id !== acquisition.environment_id ||
    validation.source_acquired_by !== acquisition.acquired_by ||
    validation.package_digest !== acquisition.package_digest ||
    validation.package_size_bytes !== acquisition.package_size_bytes ||
    validation.capability_ids.length !== acquisition.capabilities.length ||
    validation.capability_ids.some(
      (item, index) => item !== acquisition.capabilities[index]?.capability_id,
    )
  ) {
    throw new Error("Connector validation does not match the exact acquisition receipt");
  }
  return payload;
}

export async function inventoryConnectorPackage(validation: ConnectorPackageValidation) {
  if (validation.outcome !== "passed") {
    throw new Error("Only a passed package validation can be inventoried");
  }
  const response = await apiFetch(
    "/api/v1/connectors/package-supply-chain-inventories",
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-package-inventory.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-package-supply-chain-inventory-request.v1",
        source_validation_id: validation.validation_id,
        source_validation_digest: validation.canonical_digest,
        package_digest: validation.package_digest,
        inventory_profile: "atlas.connector-supply-chain-inventory.python312.v1",
        acknowledged_untrusted_package_content: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Connector package inventory failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeInventory(payload)) {
    throw new Error("Connector registry returned unsafe package inventory evidence");
  }
  const inventory = payload.data;
  if (
    inventory.source_validation_id !== validation.validation_id ||
    inventory.source_validation_digest !== validation.canonical_digest ||
    inventory.source_acquisition_id !== validation.source_acquisition_id ||
    inventory.source_acquisition_digest !== validation.source_acquisition_digest ||
    inventory.source_handoff_id !== validation.source_handoff_id ||
    inventory.source_project_id !== validation.source_project_id ||
    inventory.source_acquired_by !== validation.source_acquired_by ||
    inventory.source_validated_by !== validation.validated_by ||
    inventory.organization_id !== validation.organization_id ||
    inventory.environment_id !== validation.environment_id ||
    inventory.package_digest !== validation.package_digest ||
    inventory.package_size_bytes !== validation.package_size_bytes
  ) {
    throw new Error("Connector inventory does not match the exact validation report");
  }
  return payload;
}

export async function scanConnectorPackageContent(
  inventory: ConnectorPackageSupplyChainInventory,
) {
  if (inventory.outcome !== "passed") {
    throw new Error("Only a passed package inventory can be content-policy scanned");
  }
  const response = await apiFetch("/api/v1/connectors/package-content-policy-scans", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-content-policy-scan.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-content-policy-scan-request.v1",
      source_inventory_id: inventory.inventory_id,
      source_inventory_digest: inventory.canonical_digest,
      package_digest: inventory.package_digest,
      scan_profile: "atlas.connector-content-policy-scan.python312.v1",
      acknowledged_untrusted_package_content: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package content-policy scan failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeContentPolicyScan(payload)) {
    throw new Error("Connector registry returned unsafe content-policy evidence");
  }
  const scan = payload.data;
  if (
    scan.source_inventory_id !== inventory.inventory_id ||
    scan.source_inventory_digest !== inventory.canonical_digest ||
    scan.source_validation_id !== inventory.source_validation_id ||
    scan.source_validation_digest !== inventory.source_validation_digest ||
    scan.source_acquisition_id !== inventory.source_acquisition_id ||
    scan.source_acquisition_digest !== inventory.source_acquisition_digest ||
    scan.source_handoff_id !== inventory.source_handoff_id ||
    scan.source_project_id !== inventory.source_project_id ||
    scan.source_acquired_by !== inventory.source_acquired_by ||
    scan.source_validated_by !== inventory.source_validated_by ||
    scan.source_inventoried_by !== inventory.inventoried_by ||
    scan.organization_id !== inventory.organization_id ||
    scan.environment_id !== inventory.environment_id ||
    scan.package_digest !== inventory.package_digest ||
    scan.package_size_bytes !== inventory.package_size_bytes ||
    scan.inventory_digest !== inventory.inventory_digest ||
    scan.dependency_set_digest !== inventory.dependency_set_digest ||
    scan.scanned_file_count !== inventory.files.length
  ) {
    throw new Error("Content-policy scan does not match the exact package inventory");
  }
  return payload;
}

export async function validateConnectorPackageSchemaSemantics(
  scan: ConnectorPackageContentPolicyScan,
) {
  if (scan.outcome !== "passed" || scan.promotion_blocked) {
    throw new Error("Only a passed content-policy report can receive schema validation");
  }
  const response = await apiFetch(
    "/api/v1/connectors/package-schema-semantics-validations",
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-schema-semantics.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-package-schema-semantics-validation-request.v1",
        source_content_policy_scan_id: scan.scan_id,
        source_content_policy_scan_digest: scan.canonical_digest,
        package_digest: scan.package_digest,
        validation_profile: "atlas.connector-schema-semantics.python312.v1",
        acknowledged_untrusted_schema_content: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Connector package schema validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeSchemaSemanticsValidation(payload)) {
    throw new Error("Connector registry returned unsafe schema semantics evidence");
  }
  const report = payload.data;
  if (
    report.source_content_policy_scan_id !== scan.scan_id ||
    report.source_content_policy_scan_digest !== scan.canonical_digest ||
    report.source_inventory_id !== scan.source_inventory_id ||
    report.source_inventory_digest !== scan.source_inventory_digest ||
    report.source_validation_id !== scan.source_validation_id ||
    report.source_validation_digest !== scan.source_validation_digest ||
    report.source_acquisition_id !== scan.source_acquisition_id ||
    report.source_acquisition_digest !== scan.source_acquisition_digest ||
    report.source_content_scanned_by !== scan.scanned_by ||
    report.organization_id !== scan.organization_id ||
    report.environment_id !== scan.environment_id ||
    report.package_digest !== scan.package_digest ||
    report.package_size_bytes !== scan.package_size_bytes ||
    report.inventory_digest !== scan.inventory_digest ||
    report.content_scan_digest !== scan.content_scan_digest
  ) {
    throw new Error("Schema semantics report does not match the exact content-policy scan");
  }
  return payload;
}

export async function validateConnectorPackageAuthorityBehavior(
  source: ConnectorPackageSchemaSemanticsValidation,
) {
  if (source.outcome !== "passed" || source.promotion_blocked) {
    throw new Error("Only a passed schema semantics report can receive behavior validation");
  }
  const response = await apiFetch(
    "/api/v1/connectors/package-authority-behavior-validations",
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-authority-behavior.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-package-authority-behavior-validation-request.v1",
        source_schema_semantics_validation_id: source.validation_id,
        source_schema_semantics_validation_digest: source.canonical_digest,
        package_digest: source.package_digest,
        validation_profile: "atlas.connector-authority-behavior.python312.v1",
        acknowledged_static_analysis_limitations: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Connector package authority behavior validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeAuthorityBehaviorValidation(payload)) {
    throw new Error("Connector registry returned unsafe authority behavior evidence");
  }
  const report = payload.data;
  if (
    report.source_schema_semantics_validation_id !== source.validation_id ||
    report.source_schema_semantics_validation_digest !== source.canonical_digest ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_schema_validated_by !== source.validated_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest ||
    report.semantic_validation_digest !== source.semantic_validation_digest
  ) {
    throw new Error("Authority behavior report does not match the exact schema validation");
  }
  return payload;
}

export async function analyzeConnectorPackageStaticDependencies(
  source: ConnectorPackageAuthorityBehaviorValidation,
) {
  if (source.outcome !== "passed" || source.promotion_blocked) {
    throw new Error("Only a passed authority behavior report can receive static analysis");
  }
  const response = await apiFetch("/api/v1/connectors/package-static-dependency-analyses", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-static-dependency.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-static-dependency-analysis-request.v1",
      source_authority_behavior_validation_id: source.validation_id,
      source_authority_behavior_validation_digest: source.canonical_digest,
      package_digest: source.package_digest,
      analysis_profile: "atlas.connector-static-dependency.python312.v1",
      acknowledged_offline_static_dependency_limitations: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package static dependency analysis failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeStaticDependencyAnalysis(payload)) {
    throw new Error("Connector registry returned unsafe static dependency evidence");
  }
  const report = payload.data;
  if (
    report.source_authority_behavior_validation_id !== source.validation_id ||
    report.source_authority_behavior_validation_digest !== source.canonical_digest ||
    report.source_schema_semantics_validation_id !==
      source.source_schema_semantics_validation_id ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_authority_validated_by !== source.validated_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest
  ) {
    throw new Error("Static dependency report does not match the exact authority validation");
  }
  return payload;
}

