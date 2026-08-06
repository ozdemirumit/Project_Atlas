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

export type ConnectorPackageVulnerabilityAnalysis = {
  analysis_id: string;
  schema_version: "atlas.connector-package-vulnerability-analysis.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_static_dependency_analysis_id: string;
  source_static_dependency_analysis_digest: string;
  source_authority_behavior_validation_id: string;
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
  source_static_analyzed_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  analyzed_by: string;
  analysis_profile: "atlas.connector-vulnerability.python312.v1";
  analyzer_version: "atlas.connector-vulnerability-analyzer.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  advisory_snapshot: {
    snapshot_id: string;
    snapshot_version: string;
    snapshot_digest: string;
    signing_key_id: string;
    issued_at: string;
    expires_at: string;
    ecosystem: "pypi";
    record_count: number;
    coverage_complete: boolean;
    fresh: boolean;
  };
  subject_summary: {
    runtime_dependency_count: number;
    transitive_dependency_count: number;
    build_dependency_count: number;
    scanned_subject_count: number;
    affected_subject_count: number;
    advisory_match_count: number;
    withdrawn_record_count: number;
    low_count: number;
    medium_count: number;
    high_count: number;
    critical_count: number;
    dependency_set_digest: string;
  };
  findings: Array<{
    advisory_id: string;
    severity: "low" | "medium" | "high" | "critical";
    dependency_scope: "runtime" | "transitive" | "build" | "dataset";
    subject_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  analysis_digest: string;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  analyzed_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
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

export type ConnectorPackageMalwareAnalysis = {
  analysis_id: string;
  schema_version: "atlas.connector-package-malware-analysis.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_vulnerability_analysis_id: string;
  source_vulnerability_analysis_digest: string;
  source_static_dependency_analysis_id: string;
  source_static_dependency_analysis_digest: string;
  source_authority_behavior_validation_id: string;
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
  source_static_analyzed_by: string;
  source_vulnerability_analyzed_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  analyzed_by: string;
  analysis_profile: "atlas.connector-malware.offline.v1";
  scanner_version: "atlas.connector-malware-scanner.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  definition_snapshot: {
    snapshot_id: string;
    snapshot_version: string;
    snapshot_digest: string;
    signing_key_id: string;
    issued_at: string;
    expires_at: string;
    scan_profile: "atlas.connector-malware.offline.v1";
    scanner_version: "atlas.connector-malware-scanner.v1";
    record_count: number;
    package_coverage_complete: boolean;
    file_coverage_complete: boolean;
    stream_coverage_complete: boolean;
    fresh: boolean;
  };
  subject_summary: {
    package_subject_count: number;
    file_subject_count: number;
    scanned_subject_count: number;
    scanned_bytes: number;
    matched_subject_count: number;
    definition_match_count: number;
    inactive_record_count: number;
    low_count: number;
    medium_count: number;
    high_count: number;
    critical_count: number;
    content_set_digest: string;
  };
  findings: Array<{
    rule_id: string;
    category: string;
    severity: "low" | "medium" | "high" | "critical";
    subject_scope: "package" | "file" | "dataset";
    subject_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  analysis_digest: string;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  analyzed_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
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

export type ConnectorPackageLicenseAnalysis = {
  analysis_id: string;
  schema_version: "atlas.connector-package-license-analysis.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_malware_analysis_id: string;
  source_malware_analysis_digest: string;
  source_vulnerability_analysis_id: string;
  source_vulnerability_analysis_digest: string;
  source_static_dependency_analysis_id: string;
  source_static_dependency_analysis_digest: string;
  source_authority_behavior_validation_id: string;
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
  source_static_analyzed_by: string;
  source_vulnerability_analyzed_by: string;
  source_malware_analyzed_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  analyzed_by: string;
  analysis_profile: "atlas.connector-license-policy.python312.v1";
  analyzer_version: "atlas.connector-license-policy-analyzer.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  dependency_set_digest: string;
  policy_snapshot: {
    snapshot_id: string;
    snapshot_version: string;
    snapshot_digest: string;
    signing_key_id: string;
    issued_at: string;
    expires_at: string;
    analysis_profile: "atlas.connector-license-policy.python312.v1";
    analyzer_version: "atlas.connector-license-policy-analyzer.v1";
    record_count: number;
    package_coverage_complete: boolean;
    source_coverage_complete: boolean;
    dependency_coverage_complete: boolean;
    obligation_coverage_complete: boolean;
    fresh: boolean;
  };
  subject_summary: {
    package_subject_count: number;
    source_subject_count: number;
    runtime_dependency_count: number;
    transitive_dependency_count: number;
    build_dependency_count: number;
    scanned_subject_count: number;
    permitted_count: number;
    review_required_count: number;
    prohibited_count: number;
    unknown_count: number;
    obligation_count: number;
    unsatisfied_obligation_count: number;
    subject_set_digest: string;
  };
  findings: Array<{
    rule_id: string;
    category: string;
    severity: "low" | "medium" | "high" | "critical";
    subject_scope: "package" | "source" | "runtime" | "transitive" | "build" | "dataset";
    subject_fingerprint: string;
    disposition: "permitted" | "review_required" | "prohibited";
    obligations: string[];
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  analysis_digest: string;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  analyzed_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
  license_scan_completed: true;
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

export type ConnectorPackageContractValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-contract-validation.v1";
  version: 1;
  lifecycle: "validating";
  outcome: "passed" | "failed";
  source_license_analysis_id: string;
  source_license_analysis_digest: string;
  source_malware_analysis_id: string;
  source_malware_analysis_digest: string;
  source_vulnerability_analysis_id: string;
  source_vulnerability_analysis_digest: string;
  source_static_dependency_analysis_id: string;
  source_static_dependency_analysis_digest: string;
  source_authority_behavior_validation_id: string;
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
  source_static_analyzed_by: string;
  source_vulnerability_analyzed_by: string;
  source_malware_analyzed_by: string;
  source_license_analyzed_by: string;
  source_custodied_by: string;
  source_domain_reviewed_by: string;
  source_security_reviewed_by: string;
  source_lab_operated_by: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  validation_profile: "atlas.connector-contract.python312.v1";
  validator_version: "atlas.connector-contract-validator.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  dependency_set_digest: string;
  coverage: {
    manifest_count: number;
    configuration_schema_count: number;
    capability_count: number;
    input_schema_count: number;
    output_schema_count: number;
    handler_count: number;
    covered_capability_count: number;
    contract_test_count: number;
    synthetic_fixture_count: number;
    orphan_artifact_count: number;
    contract_set_digest: string;
  };
  findings: Array<{
    rule_id: string;
    category: string;
    severity: "medium" | "high" | "critical";
    artifact_scope:
      | "manifest"
      | "configuration_schema"
      | "capability_schema"
      | "handler"
      | "contract_test"
      | "synthetic_fixture"
      | "coverage";
    subject_fingerprint: string;
    summary: string;
    remediation: string;
  }>;
  finding_set_digest: string;
  validation_digest: string;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
  license_scan_completed: true;
  contract_validation_completed: true;
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

export type ConnectorPackageRunnerValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-runner-validation.v1";
  version: 1;
  outcome: "passed" | "failed";
  source_contract_validation_id: string;
  source_contract_validation_digest: string;
  source_license_analysis_id: string;
  source_license_analysis_digest: string;
  source_inventory_id: string;
  source_acquisition_id: string;
  source_project_id: string;
  source_contract_validated_by: string;
  source_actor_set_digest: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  validation_profile: "atlas.connector-runner.python312.v1";
  adapter_contract: "atlas.connector-isolated-subprocess.v1";
  harness_version: "atlas.connector-runner-harness.v1";
  runtime_version: string;
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  capability_count: number;
  invoked_capability_count: number;
  fail_closed_count: number;
  bounded_literal_count: number;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  child_started: boolean;
  child_exit_code: number | null;
  duration_ms: number;
  output_digest: string;
  output_size_bytes: number;
  workspace_removed: boolean;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
  license_scan_completed: true;
  contract_validation_completed: true;
  runner_validation_completed: true;
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

export type ConnectorPackageLabSelfTest = {
  self_test_id: string;
  schema_version: "atlas.connector-package-lab-self-test.v1";
  version: 1;
  outcome: "passed" | "failed";
  source_runner_validation_id: string;
  source_runner_validation_digest: string;
  source_contract_validation_id: string;
  source_contract_validation_digest: string;
  source_inventory_id: string;
  source_acquisition_id: string;
  source_project_id: string;
  source_runner_validated_by: string;
  source_actor_set_digest: string;
  lab_plan_id: string;
  lab_plan_digest: string;
  lab_plan_approved_by: string;
  credential_custodied_by: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  target_alias: string;
  product_family: string;
  observed_product_version: string;
  validation_profile: "atlas.connector-lab-self-test.readonly.v1";
  adapter_contract: "atlas.connector-lab-mock-target.v1";
  runner_runtime: "mock-target.python312.v1";
  package_digest: string;
  package_size_bytes: number;
  inventory_digest: string;
  capability_count: number;
  tested_capability_count: number;
  request_count: number;
  request_bytes: number;
  response_bytes: number;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "error";
    summary: string;
    remediation: string;
  }>;
  duration_ms: number;
  evidence_digest: string;
  lease_issued: boolean;
  lease_released: boolean;
  credentials_revoked: boolean;
  session_closed: boolean;
  workspace_removed: boolean;
  limitations: string[];
  promotion_blocked: boolean;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
  license_scan_completed: true;
  contract_validation_completed: true;
  runner_validation_completed: true;
  lab_validation_completed: true;
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

export type ConnectorPackageFinalValidation = {
  validation_id: string;
  schema_version: "atlas.connector-package-final-validation.v1";
  version: 1;
  outcome: "eligible_for_human_approval" | "blocked";
  source_lab_self_test_id: string;
  source_lab_self_test_digest: string;
  source_handoff_id: string;
  source_handoff_digest: string;
  source_project_id: string;
  source_actor_set_digest: string;
  organization_id: string;
  environment_id: string;
  validated_by: string;
  policy_id: string;
  policy_digest: string;
  policy_version: string;
  package_digest: string;
  inventory_digest: string;
  product_family: string;
  observed_product_version: string;
  capability_count: number;
  tested_capability_count: number;
  stage_evidence: Array<{
    stage_code: string;
    evidence_id: string;
    evidence_digest: string;
    observed_at: string;
    outcome: string;
    promotion_blocked: boolean;
    finding_count: number;
    limitation_count: number;
  }>;
  stage_count: number;
  passed_stage_count: number;
  finding_count: number;
  limitation_count: number;
  blocking_risk_count: number;
  risks: Array<{
    code: string;
    source_stage: string;
    source_evidence_id: string;
    source_evidence_digest: string;
    classification: "disclosed_limitation" | "blocking_policy";
    severity: "informational" | "warning" | "error";
    blocking: boolean;
    occurrence_count: number;
    next_step: string;
  }>;
  checks: Array<{
    code: string;
    state: "passed" | "failed";
    severity: "informational" | "warning" | "error";
    summary: string;
    remediation: string;
  }>;
  limitations: string[];
  eligible_for_human_approval: boolean;
  promotion_blocked: boolean;
  evidence_digest: string;
  canonical_digest: string;
  validated_at: string;
  secret_content_scan_completed: true;
  prohibited_content_scan_completed: true;
  schema_semantic_validation_completed: true;
  permission_behavior_validation_completed: true;
  static_code_validation_completed: true;
  vulnerability_scan_completed: true;
  malware_scan_completed: true;
  license_scan_completed: true;
  contract_validation_completed: true;
  runner_validation_completed: true;
  lab_validation_completed: true;
  final_validation_completed: true;
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

export type ConnectorPackageApprovalOutcome =
  | "approve"
  | "reject"
  | "needs_evidence"
  | "defer";

export type ConnectorPackageApprovalRecord = {
  request: {
    request_id: string;
    schema_version: "atlas.connector-package-approval-request.v1";
    version: 1;
    source_final_validation_id: string;
    source_final_validation_digest: string;
    source_handoff_id: string;
    source_project_id: string;
    source_actor_set_digest: string;
    organization_id: string;
    environment_id: string;
    requested_by: string;
    purpose: string;
    approval_policy_id: string;
    approval_policy_digest: string;
    approval_policy_version: string;
    package_digest: string;
    inventory_digest: string;
    product_family: string;
    observed_product_version: string;
    evidence_digest: string;
    final_policy_id: string;
    final_policy_digest: string;
    final_policy_version: string;
    stage_count: number;
    passed_stage_count: number;
    finding_count: number;
    limitation_count: number;
    blocking_risk_count: number;
    created_at: string;
    expires_at: string;
    canonical_digest: string;
    final_validation_completed: true;
    connector_approved: false;
    connector_rejected: false;
    eligible_for_publisher_governance: false;
    promotion_blocked: true;
    reused: boolean;
  };
  decision: null | {
    decision_id: string;
    schema_version: "atlas.connector-package-approval-decision.v1";
    version: 1;
    request_id: string;
    request_version: 1;
    request_digest: string;
    outcome: ConnectorPackageApprovalOutcome;
    decided_by: string;
    rationale: string;
    organization_id: string;
    environment_id: string;
    source_final_validation_id: string;
    source_final_validation_digest: string;
    package_digest: string;
    approval_policy_id: string;
    approval_policy_digest: string;
    decided_at: string;
    canonical_digest: string;
    reused: boolean;
  };
  state: "pending" | "approved" | "rejected" | "needs_evidence" | "deferred" | "expired";
  approval_valid: boolean;
  connector_approved: boolean;
  connector_rejected: boolean;
  eligible_for_publisher_governance: boolean;
  promotion_blocked: boolean;
  package_signed: false;
  publisher_attested: false;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
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

function isVulnerabilityFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.advisory_id === "string" &&
    ["low", "medium", "high", "critical"].includes(String(value.severity)) &&
    ["runtime", "transitive", "build", "dataset"].includes(
      String(value.dependency_scope),
    ) &&
    typeof value.subject_fingerprint === "string" &&
    value.subject_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isVulnerabilityCheck(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    (value.state === "passed" || value.state === "failed") &&
    (value.severity === "informational" || value.severity === "error") &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeVulnerabilityAnalysis(
  value: unknown,
): value is { data: ConnectorPackageVulnerabilityAnalysis } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  if (!isRecord(report.advisory_snapshot) || !isRecord(report.subject_summary)) return false;
  const snapshot = report.advisory_snapshot;
  const subjects = report.subject_summary;
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_authority_validated_by,
    report.source_static_analyzed_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const counts = [
    snapshot.record_count,
    subjects.runtime_dependency_count,
    subjects.transitive_dependency_count,
    subjects.build_dependency_count,
    subjects.scanned_subject_count,
    subjects.affected_subject_count,
    subjects.advisory_match_count,
    subjects.withdrawn_record_count,
    subjects.low_count,
    subjects.medium_count,
    subjects.high_count,
    subjects.critical_count,
  ];
  const noAuthority = [
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
    report.schema_version === "atlas.connector-package-vulnerability-analysis.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.analysis_profile === "atlas.connector-vulnerability.python312.v1" &&
    report.analyzer_version === "atlas.connector-vulnerability-analyzer.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    report.vulnerability_scan_completed === true &&
    typeof report.analyzed_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.analyzed_by) &&
    typeof snapshot.snapshot_id === "string" &&
    typeof snapshot.snapshot_version === "string" &&
    typeof snapshot.snapshot_digest === "string" &&
    snapshot.snapshot_digest.length === 64 &&
    typeof snapshot.signing_key_id === "string" &&
    snapshot.ecosystem === "pypi" &&
    typeof snapshot.issued_at === "string" &&
    typeof snapshot.expires_at === "string" &&
    typeof snapshot.coverage_complete === "boolean" &&
    typeof snapshot.fresh === "boolean" &&
    counts.every((count) => typeof count === "number" && count >= 0) &&
    subjects.scanned_subject_count ===
      Number(subjects.runtime_dependency_count) +
        Number(subjects.transitive_dependency_count) +
        Number(subjects.build_dependency_count) &&
    subjects.advisory_match_count ===
      Number(subjects.low_count) +
        Number(subjects.medium_count) +
        Number(subjects.high_count) +
        Number(subjects.critical_count) &&
    typeof subjects.dependency_set_digest === "string" &&
    subjects.dependency_set_digest.length === 64 &&
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
    findings.every(isVulnerabilityFinding) &&
    checks.length === 6 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isMalwareFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_id === "string" &&
    typeof value.category === "string" &&
    ["low", "medium", "high", "critical"].includes(String(value.severity)) &&
    ["package", "file", "dataset"].includes(String(value.subject_scope)) &&
    typeof value.subject_fingerprint === "string" &&
    value.subject_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeMalwareAnalysis(
  value: unknown,
): value is { data: ConnectorPackageMalwareAnalysis } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  if (!isRecord(report.definition_snapshot) || !isRecord(report.subject_summary)) return false;
  const snapshot = report.definition_snapshot;
  const subjects = report.subject_summary;
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_authority_validated_by,
    report.source_static_analyzed_by,
    report.source_vulnerability_analyzed_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const sourceIdentifiers = [
    report.source_vulnerability_analysis_id,
    report.source_static_dependency_analysis_id,
    report.source_authority_behavior_validation_id,
    report.source_schema_semantics_validation_id,
    report.source_content_policy_scan_id,
    report.source_inventory_id,
    report.source_validation_id,
    report.source_acquisition_id,
    report.source_handoff_id,
    report.source_project_id,
  ];
  const sourceDigests = [
    report.source_vulnerability_analysis_digest,
    report.source_static_dependency_analysis_digest,
  ];
  const counts = [
    snapshot.record_count,
    subjects.package_subject_count,
    subjects.file_subject_count,
    subjects.scanned_subject_count,
    subjects.scanned_bytes,
    subjects.matched_subject_count,
    subjects.definition_match_count,
    subjects.inactive_record_count,
    subjects.low_count,
    subjects.medium_count,
    subjects.high_count,
    subjects.critical_count,
  ];
  const noAuthority = [
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
    report.schema_version === "atlas.connector-package-malware-analysis.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.analysis_profile === "atlas.connector-malware.offline.v1" &&
    report.scanner_version === "atlas.connector-malware-scanner.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    report.vulnerability_scan_completed === true &&
    report.malware_scan_completed === true &&
    typeof report.analyzed_by === "string" &&
    sourceIdentifiers.every((identifier) => typeof identifier === "string") &&
    sourceDigests.every((digest) => typeof digest === "string" && digest.length === 64) &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.analyzed_by) &&
    typeof snapshot.snapshot_id === "string" &&
    typeof snapshot.snapshot_version === "string" &&
    typeof snapshot.snapshot_digest === "string" &&
    snapshot.snapshot_digest.length === 64 &&
    typeof snapshot.signing_key_id === "string" &&
    typeof snapshot.issued_at === "string" &&
    typeof snapshot.expires_at === "string" &&
    snapshot.scan_profile === "atlas.connector-malware.offline.v1" &&
    snapshot.scanner_version === "atlas.connector-malware-scanner.v1" &&
    typeof snapshot.package_coverage_complete === "boolean" &&
    typeof snapshot.file_coverage_complete === "boolean" &&
    typeof snapshot.stream_coverage_complete === "boolean" &&
    typeof snapshot.fresh === "boolean" &&
    counts.every((count) => typeof count === "number" && count >= 0) &&
    subjects.package_subject_count === 1 &&
    subjects.scanned_subject_count ===
      Number(subjects.package_subject_count) + Number(subjects.file_subject_count) &&
    Number(subjects.matched_subject_count) <= Number(subjects.scanned_subject_count) &&
    subjects.definition_match_count ===
      Number(subjects.low_count) +
        Number(subjects.medium_count) +
        Number(subjects.high_count) +
        Number(subjects.critical_count) &&
    typeof subjects.content_set_digest === "string" &&
    subjects.content_set_digest.length === 64 &&
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
    findings.every(isMalwareFinding) &&
    checks.length === 6 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isLicenseFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_id === "string" &&
    typeof value.category === "string" &&
    ["low", "medium", "high", "critical"].includes(String(value.severity)) &&
    ["package", "source", "runtime", "transitive", "build", "dataset"].includes(
      String(value.subject_scope),
    ) &&
    typeof value.subject_fingerprint === "string" &&
    value.subject_fingerprint.length === 64 &&
    ["permitted", "review_required", "prohibited"].includes(String(value.disposition)) &&
    isStringArray(value.obligations) &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeLicenseAnalysis(
  value: unknown,
): value is { data: ConnectorPackageLicenseAnalysis } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  if (!isRecord(report.policy_snapshot) || !isRecord(report.subject_summary)) return false;
  const snapshot = report.policy_snapshot;
  const subjects = report.subject_summary;
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_authority_validated_by,
    report.source_static_analyzed_by,
    report.source_vulnerability_analyzed_by,
    report.source_malware_analyzed_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const identifiers = [
    report.source_malware_analysis_id,
    report.source_vulnerability_analysis_id,
    report.source_static_dependency_analysis_id,
    report.source_authority_behavior_validation_id,
    report.source_schema_semantics_validation_id,
    report.source_content_policy_scan_id,
    report.source_inventory_id,
    report.source_validation_id,
    report.source_acquisition_id,
    report.source_handoff_id,
    report.source_project_id,
  ];
  const digests = [
    report.source_malware_analysis_digest,
    report.source_vulnerability_analysis_digest,
    report.source_static_dependency_analysis_digest,
    report.package_digest,
    report.inventory_digest,
    report.dependency_set_digest,
    report.finding_set_digest,
    report.analysis_digest,
    report.canonical_digest,
    snapshot.snapshot_digest,
    subjects.subject_set_digest,
  ];
  const counts = [
    snapshot.record_count,
    subjects.package_subject_count,
    subjects.source_subject_count,
    subjects.runtime_dependency_count,
    subjects.transitive_dependency_count,
    subjects.build_dependency_count,
    subjects.scanned_subject_count,
    subjects.permitted_count,
    subjects.review_required_count,
    subjects.prohibited_count,
    subjects.unknown_count,
    subjects.obligation_count,
    subjects.unsatisfied_obligation_count,
  ];
  const noAuthority = [
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
    report.schema_version === "atlas.connector-package-license-analysis.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.analysis_profile === "atlas.connector-license-policy.python312.v1" &&
    report.analyzer_version === "atlas.connector-license-policy-analyzer.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    report.vulnerability_scan_completed === true &&
    report.malware_scan_completed === true &&
    report.license_scan_completed === true &&
    typeof report.analyzed_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.analyzed_by) &&
    identifiers.every((identifier) => typeof identifier === "string") &&
    digests.every((digest) => typeof digest === "string" && digest.length === 64) &&
    snapshot.analysis_profile === "atlas.connector-license-policy.python312.v1" &&
    snapshot.analyzer_version === "atlas.connector-license-policy-analyzer.v1" &&
    typeof snapshot.snapshot_id === "string" &&
    typeof snapshot.snapshot_version === "string" &&
    typeof snapshot.signing_key_id === "string" &&
    typeof snapshot.issued_at === "string" &&
    typeof snapshot.expires_at === "string" &&
    typeof snapshot.package_coverage_complete === "boolean" &&
    typeof snapshot.source_coverage_complete === "boolean" &&
    typeof snapshot.dependency_coverage_complete === "boolean" &&
    typeof snapshot.obligation_coverage_complete === "boolean" &&
    typeof snapshot.fresh === "boolean" &&
    counts.every((count) => typeof count === "number" && count >= 0) &&
    subjects.package_subject_count === 1 &&
    subjects.source_subject_count === 1 &&
    subjects.scanned_subject_count ===
      Number(subjects.package_subject_count) +
        Number(subjects.source_subject_count) +
        Number(subjects.runtime_dependency_count) +
        Number(subjects.transitive_dependency_count) +
        Number(subjects.build_dependency_count) &&
    subjects.scanned_subject_count ===
      Number(subjects.permitted_count) +
        Number(subjects.review_required_count) +
        Number(subjects.prohibited_count) +
        Number(subjects.unknown_count) &&
    Number(subjects.unsatisfied_obligation_count) <= Number(subjects.obligation_count) &&
    findings.length <= 500 &&
    findings.every(isLicenseFinding) &&
    checks.length === 6 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isContractFinding(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.rule_id === "string" &&
    typeof value.category === "string" &&
    ["medium", "high", "critical"].includes(String(value.severity)) &&
    [
      "manifest",
      "configuration_schema",
      "capability_schema",
      "handler",
      "contract_test",
      "synthetic_fixture",
      "coverage",
    ].includes(String(value.artifact_scope)) &&
    typeof value.subject_fingerprint === "string" &&
    value.subject_fingerprint.length === 64 &&
    typeof value.summary === "string" &&
    typeof value.remediation === "string"
  );
}

function isSafeContractValidation(
  value: unknown,
): value is { data: ConnectorPackageContractValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  if (!isRecord(report.coverage)) return false;
  const coverage = report.coverage;
  const findings: unknown[] = Array.isArray(report.findings) ? report.findings : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const sourceActors = [
    report.source_acquired_by,
    report.source_manifest_validated_by,
    report.source_inventoried_by,
    report.source_content_scanned_by,
    report.source_schema_validated_by,
    report.source_authority_validated_by,
    report.source_static_analyzed_by,
    report.source_vulnerability_analyzed_by,
    report.source_malware_analyzed_by,
    report.source_license_analyzed_by,
    report.source_custodied_by,
    report.source_domain_reviewed_by,
    report.source_security_reviewed_by,
    report.source_lab_operated_by,
  ];
  const identifiers = [
    report.source_license_analysis_id,
    report.source_malware_analysis_id,
    report.source_vulnerability_analysis_id,
    report.source_static_dependency_analysis_id,
    report.source_authority_behavior_validation_id,
    report.source_schema_semantics_validation_id,
    report.source_content_policy_scan_id,
    report.source_inventory_id,
    report.source_validation_id,
    report.source_acquisition_id,
    report.source_handoff_id,
    report.source_project_id,
  ];
  const digests = [
    report.source_license_analysis_digest,
    report.source_malware_analysis_digest,
    report.source_vulnerability_analysis_digest,
    report.source_static_dependency_analysis_digest,
    report.package_digest,
    report.inventory_digest,
    report.dependency_set_digest,
    report.finding_set_digest,
    report.validation_digest,
    report.canonical_digest,
    coverage.contract_set_digest,
  ];
  const counts = [
    coverage.manifest_count,
    coverage.configuration_schema_count,
    coverage.capability_count,
    coverage.input_schema_count,
    coverage.output_schema_count,
    coverage.handler_count,
    coverage.covered_capability_count,
    coverage.contract_test_count,
    coverage.synthetic_fixture_count,
    coverage.orphan_artifact_count,
  ];
  const noAuthority = [
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
    report.schema_version === "atlas.connector-package-contract-validation.v1" &&
    report.version === 1 &&
    report.lifecycle === "validating" &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.validation_profile === "atlas.connector-contract.python312.v1" &&
    report.validator_version === "atlas.connector-contract-validator.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    report.vulnerability_scan_completed === true &&
    report.malware_scan_completed === true &&
    report.license_scan_completed === true &&
    report.contract_validation_completed === true &&
    typeof report.validated_by === "string" &&
    sourceActors.every((actor) => typeof actor === "string") &&
    !sourceActors.includes(report.validated_by) &&
    identifiers.every((identifier) => typeof identifier === "string") &&
    digests.every((digest) => typeof digest === "string" && digest.length === 64) &&
    counts.every((count) => typeof count === "number" && count >= 0) &&
    Number(coverage.covered_capability_count) <= Number(coverage.capability_count) &&
    findings.length <= 500 &&
    findings.every(isContractFinding) &&
    checks.length === 7 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((flag) => flag === false)
  );
}

function isSafeRunnerValidation(
  value: unknown,
): value is { data: ConnectorPackageRunnerValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const identifiers = [
    report.source_contract_validation_id,
    report.source_license_analysis_id,
    report.source_inventory_id,
    report.source_acquisition_id,
    report.source_project_id,
    report.source_contract_validated_by,
    report.organization_id,
    report.environment_id,
    report.validated_by,
    report.runtime_version,
  ];
  const digests = [
    report.source_contract_validation_digest,
    report.source_license_analysis_digest,
    report.source_actor_set_digest,
    report.package_digest,
    report.inventory_digest,
    report.output_digest,
    report.canonical_digest,
  ];
  const counts = [
    report.package_size_bytes,
    report.capability_count,
    report.invoked_capability_count,
    report.fail_closed_count,
    report.bounded_literal_count,
    report.duration_ms,
    report.output_size_bytes,
  ];
  const noAuthority = [
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
    report.schema_version === "atlas.connector-package-runner-validation.v1" &&
    report.version === 1 &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.validation_profile === "atlas.connector-runner.python312.v1" &&
    report.adapter_contract === "atlas.connector-isolated-subprocess.v1" &&
    report.harness_version === "atlas.connector-runner-harness.v1" &&
    report.secret_content_scan_completed === true &&
    report.prohibited_content_scan_completed === true &&
    report.schema_semantic_validation_completed === true &&
    report.permission_behavior_validation_completed === true &&
    report.static_code_validation_completed === true &&
    report.vulnerability_scan_completed === true &&
    report.malware_scan_completed === true &&
    report.license_scan_completed === true &&
    report.contract_validation_completed === true &&
    report.runner_validation_completed === true &&
    report.workspace_removed === true &&
    identifiers.every((item) => typeof item === "string") &&
    report.validated_by !== report.source_contract_validated_by &&
    digests.every((item) => typeof item === "string" && item.length === 64) &&
    counts.every((item) => typeof item === "number" && item >= 0) &&
    Number(report.invoked_capability_count) <= Number(report.capability_count) &&
    Number(report.fail_closed_count) + Number(report.bounded_literal_count) ===
      Number(report.invoked_capability_count) &&
    (report.child_exit_code === null || typeof report.child_exit_code === "number") &&
    typeof report.child_started === "boolean" &&
    checks.length === 10 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    noAuthority.every((item) => item === false)
  );
}

function isSafeLabSelfTest(value: unknown): value is { data: ConnectorPackageLabSelfTest } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const identifiers = [
    report.source_runner_validation_id,
    report.source_contract_validation_id,
    report.source_inventory_id,
    report.source_acquisition_id,
    report.source_project_id,
    report.source_runner_validated_by,
    report.lab_plan_id,
    report.lab_plan_approved_by,
    report.credential_custodied_by,
    report.organization_id,
    report.environment_id,
    report.validated_by,
    report.target_alias,
    report.product_family,
    report.observed_product_version,
  ];
  const digests = [
    report.source_runner_validation_digest,
    report.source_contract_validation_digest,
    report.source_actor_set_digest,
    report.lab_plan_digest,
    report.package_digest,
    report.inventory_digest,
    report.evidence_digest,
    report.canonical_digest,
  ];
  const counts = [
    report.package_size_bytes,
    report.capability_count,
    report.tested_capability_count,
    report.request_count,
    report.request_bytes,
    report.response_bytes,
    report.duration_ms,
  ];
  const completion = [
    report.secret_content_scan_completed,
    report.prohibited_content_scan_completed,
    report.schema_semantic_validation_completed,
    report.permission_behavior_validation_completed,
    report.static_code_validation_completed,
    report.vulnerability_scan_completed,
    report.malware_scan_completed,
    report.license_scan_completed,
    report.contract_validation_completed,
    report.runner_validation_completed,
    report.lab_validation_completed,
  ];
  const noAuthority = [
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
  const forbidden = [
    "destination_references",
    "tls_trust_reference",
    "secret_reference_ids",
    "credential_handle",
    "endpoint",
    "request_payload",
    "response_payload",
    "stdout",
    "stderr",
    "exception",
  ];
  return (
    report.schema_version === "atlas.connector-package-lab-self-test.v1" &&
    report.version === 1 &&
    (report.outcome === "passed" || report.outcome === "failed") &&
    report.promotion_blocked === (report.outcome === "failed") &&
    report.validation_profile === "atlas.connector-lab-self-test.readonly.v1" &&
    report.adapter_contract === "atlas.connector-lab-mock-target.v1" &&
    report.runner_runtime === "mock-target.python312.v1" &&
    identifiers.every((item) => typeof item === "string") &&
    report.validated_by !== report.source_runner_validated_by &&
    report.validated_by !== report.lab_plan_approved_by &&
    report.validated_by !== report.credential_custodied_by &&
    report.lab_plan_approved_by !== report.credential_custodied_by &&
    digests.every((item) => typeof item === "string" && item.length === 64) &&
    counts.every((item) => typeof item === "number" && item >= 0) &&
    Number(report.tested_capability_count) <= Number(report.capability_count) &&
    checks.length === 14 &&
    checks.every(isVulnerabilityCheck) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    completion.every((item) => item === true) &&
    noAuthority.every((item) => item === false) &&
    typeof report.lease_issued === "boolean" &&
    typeof report.lease_released === "boolean" &&
    typeof report.credentials_revoked === "boolean" &&
    typeof report.session_closed === "boolean" &&
    typeof report.workspace_removed === "boolean" &&
    forbidden.every((field) => !(field in report))
  );
}

function isSafeFinalValidation(
  value: unknown,
): value is { data: ConnectorPackageFinalValidation } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const report = value.data;
  const stages: unknown[] = Array.isArray(report.stage_evidence) ? report.stage_evidence : [];
  const risks: unknown[] = Array.isArray(report.risks) ? report.risks : [];
  const checks: unknown[] = Array.isArray(report.checks) ? report.checks : [];
  const expectedStages = [
    "acquisition",
    "validation-intake",
    "supply-chain-inventory",
    "content-policy",
    "schema-semantics",
    "authority-behavior",
    "static-dependency",
    "vulnerability",
    "malware",
    "license",
    "contract",
    "runner",
    "lab",
  ];
  const digests = [
    report.source_lab_self_test_digest,
    report.source_handoff_digest,
    report.source_actor_set_digest,
    report.policy_digest,
    report.package_digest,
    report.inventory_digest,
    report.evidence_digest,
    report.canonical_digest,
  ];
  const identifiers = [
    report.validation_id,
    report.source_lab_self_test_id,
    report.source_handoff_id,
    report.source_project_id,
    report.organization_id,
    report.environment_id,
    report.validated_by,
    report.policy_id,
    report.policy_version,
    report.product_family,
    report.observed_product_version,
  ];
  const completion = [
    report.secret_content_scan_completed,
    report.prohibited_content_scan_completed,
    report.schema_semantic_validation_completed,
    report.permission_behavior_validation_completed,
    report.static_code_validation_completed,
    report.vulnerability_scan_completed,
    report.malware_scan_completed,
    report.license_scan_completed,
    report.contract_validation_completed,
    report.runner_validation_completed,
    report.lab_validation_completed,
    report.final_validation_completed,
  ];
  const noAuthority = [
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
  const forbidden = [
    "destination_references",
    "tls_trust_reference",
    "secret_reference_ids",
    "credential_handle",
    "endpoint",
    "request_payload",
    "response_payload",
    "stdout",
    "stderr",
    "exception",
    "target_alias",
  ];
  return (
    report.schema_version === "atlas.connector-package-final-validation.v1" &&
    report.version === 1 &&
    (report.outcome === "eligible_for_human_approval" || report.outcome === "blocked") &&
    report.eligible_for_human_approval ===
      (report.outcome === "eligible_for_human_approval") &&
    report.promotion_blocked === (report.outcome === "blocked") &&
    stages.length === 13 &&
    stages.every(
      (stage, index) =>
        isRecord(stage) &&
        stage.stage_code === expectedStages[index] &&
        typeof stage.evidence_id === "string" &&
        typeof stage.evidence_digest === "string" &&
        stage.evidence_digest.length === 64 &&
        typeof stage.observed_at === "string" &&
        typeof stage.outcome === "string" &&
        typeof stage.promotion_blocked === "boolean" &&
        typeof stage.finding_count === "number" &&
        typeof stage.limitation_count === "number",
    ) &&
    risks.every(
      (risk) =>
        isRecord(risk) &&
        typeof risk.code === "string" &&
        expectedStages.includes(String(risk.source_stage)) &&
        typeof risk.source_evidence_id === "string" &&
        typeof risk.source_evidence_digest === "string" &&
        risk.source_evidence_digest.length === 64 &&
        ["disclosed_limitation", "blocking_policy"].includes(String(risk.classification)) &&
        ["informational", "warning", "error"].includes(String(risk.severity)) &&
        typeof risk.blocking === "boolean" &&
        typeof risk.occurrence_count === "number" &&
        typeof risk.next_step === "string",
    ) &&
    checks.every(
      (check) =>
        isRecord(check) &&
        typeof check.code === "string" &&
        (check.state === "passed" || check.state === "failed") &&
        ["informational", "warning", "error"].includes(String(check.severity)) &&
        typeof check.summary === "string" &&
        typeof check.remediation === "string",
    ) &&
    Number(report.stage_count) === 13 &&
    Number(report.passed_stage_count) <= 13 &&
    Number(report.tested_capability_count) <= Number(report.capability_count) &&
    Number(report.blocking_risk_count) ===
      risks.filter((risk) => isRecord(risk) && risk.blocking === true).length &&
    identifiers.every((item) => typeof item === "string" && item.length > 0) &&
    digests.every((item) => typeof item === "string" && item.length === 64) &&
    isStringArray(report.limitations) &&
    report.limitations.length > 0 &&
    completion.every((item) => item === true) &&
    noAuthority.every((item) => item === false) &&
    forbidden.every((field) => !(field in report))
  );
}

function isSafePackageApproval(
  value: unknown,
): value is { data: ConnectorPackageApprovalRecord } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const record = value.data;
  if (!isRecord(record.request)) return false;
  const request = record.request;
  const decision = record.decision;
  const state = String(record.state);
  const approved = state === "approved" && record.approval_valid === true;
  const rejected = state === "rejected";
  const noAuthority = [
    record.package_signed,
    record.publisher_attested,
    record.connector_registered,
    record.connector_installed,
    record.connector_enabled,
    record.target_configured,
    record.credentials_resolved,
    record.runtime_trust_granted,
    record.execution_authorized,
    record.deployment_approved,
    record.infrastructure_mutation_performed,
  ];
  const forbidden = [
    "request_fingerprint",
    "idempotency_key",
    "forbidden_actor_ids",
    "credential_handle",
    "endpoint",
    "request_payload",
    "response_payload",
  ];
  return (
    ["pending", "approved", "rejected", "needs_evidence", "deferred", "expired"].includes(
      state,
    ) &&
    request.schema_version === "atlas.connector-package-approval-request.v1" &&
    request.version === 1 &&
    typeof request.request_id === "string" &&
    typeof request.source_final_validation_id === "string" &&
    typeof request.source_final_validation_digest === "string" &&
    request.source_final_validation_digest.length === 64 &&
    typeof request.package_digest === "string" &&
    request.package_digest.length === 64 &&
    typeof request.approval_policy_id === "string" &&
    typeof request.approval_policy_digest === "string" &&
    request.approval_policy_digest.length === 64 &&
    typeof request.requested_by === "string" &&
    typeof request.purpose === "string" &&
    typeof request.canonical_digest === "string" &&
    request.canonical_digest.length === 64 &&
    request.final_validation_completed === true &&
    request.connector_approved === false &&
    request.connector_rejected === false &&
    request.eligible_for_publisher_governance === false &&
    request.promotion_blocked === true &&
    (decision === null ||
      (isRecord(decision) &&
        decision.schema_version === "atlas.connector-package-approval-decision.v1" &&
        decision.version === 1 &&
        decision.request_id === request.request_id &&
        decision.request_version === request.version &&
        decision.request_digest === request.canonical_digest &&
        ["approve", "reject", "needs_evidence", "defer"].includes(
          String(decision.outcome),
        ) &&
        typeof decision.decided_by === "string" &&
        typeof decision.rationale === "string" &&
        typeof decision.canonical_digest === "string" &&
        decision.canonical_digest.length === 64)) &&
    record.connector_approved === approved &&
    record.eligible_for_publisher_governance === approved &&
    record.connector_rejected === rejected &&
    record.promotion_blocked === !approved &&
    noAuthority.every((item) => item === false) &&
    forbidden.every((field) => !(field in record) && !(field in request))
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

export async function analyzeConnectorPackageVulnerabilities(
  source: ConnectorPackageStaticDependencyAnalysis,
) {
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.static_code_validation_completed
  ) {
    throw new Error("Only a passed static dependency report can receive vulnerability analysis");
  }
  const response = await apiFetch("/api/v1/connectors/package-vulnerability-analyses", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-vulnerability.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-vulnerability-analysis-request.v1",
      source_static_dependency_analysis_id: source.analysis_id,
      source_static_dependency_analysis_digest: source.canonical_digest,
      package_digest: source.package_digest,
      analysis_profile: "atlas.connector-vulnerability.python312.v1",
      acknowledged_offline_advisory_limitations: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package vulnerability analysis failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeVulnerabilityAnalysis(payload)) {
    throw new Error("Connector registry returned unsafe vulnerability evidence");
  }
  const report = payload.data;
  if (
    report.source_static_dependency_analysis_id !== source.analysis_id ||
    report.source_static_dependency_analysis_digest !== source.canonical_digest ||
    report.source_authority_behavior_validation_id !==
      source.source_authority_behavior_validation_id ||
    report.source_schema_semantics_validation_id !==
      source.source_schema_semantics_validation_id ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_static_analyzed_by !== source.analyzed_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest ||
    report.subject_summary.dependency_set_digest !==
      source.dependency_summary.dependency_set_digest
  ) {
    throw new Error("Vulnerability report does not match the exact static dependency analysis");
  }
  return payload;
}

export async function analyzeConnectorPackageMalware(
  source: ConnectorPackageVulnerabilityAnalysis,
) {
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.vulnerability_scan_completed ||
    source.malware_scan_completed
  ) {
    throw new Error("Only a passed vulnerability report can receive malware analysis");
  }
  const response = await apiFetch("/api/v1/connectors/package-malware-analyses", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-malware.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-malware-analysis-request.v1",
      source_vulnerability_analysis_id: source.analysis_id,
      source_vulnerability_analysis_digest: source.canonical_digest,
      package_digest: source.package_digest,
      analysis_profile: "atlas.connector-malware.offline.v1",
      acknowledged_offline_definition_limitations: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package malware analysis failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeMalwareAnalysis(payload)) {
    throw new Error("Connector registry returned unsafe malware evidence");
  }
  const report = payload.data;
  if (
    report.source_vulnerability_analysis_id !== source.analysis_id ||
    report.source_vulnerability_analysis_digest !== source.canonical_digest ||
    report.source_static_dependency_analysis_id !==
      source.source_static_dependency_analysis_id ||
    report.source_static_dependency_analysis_digest !==
      source.source_static_dependency_analysis_digest ||
    report.source_authority_behavior_validation_id !==
      source.source_authority_behavior_validation_id ||
    report.source_schema_semantics_validation_id !==
      source.source_schema_semantics_validation_id ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_handoff_id !== source.source_handoff_id ||
    report.source_project_id !== source.source_project_id ||
    report.source_acquired_by !== source.source_acquired_by ||
    report.source_manifest_validated_by !== source.source_manifest_validated_by ||
    report.source_inventoried_by !== source.source_inventoried_by ||
    report.source_content_scanned_by !== source.source_content_scanned_by ||
    report.source_schema_validated_by !== source.source_schema_validated_by ||
    report.source_authority_validated_by !== source.source_authority_validated_by ||
    report.source_static_analyzed_by !== source.source_static_analyzed_by ||
    report.source_vulnerability_analyzed_by !== source.analyzed_by ||
    report.source_custodied_by !== source.source_custodied_by ||
    report.source_domain_reviewed_by !== source.source_domain_reviewed_by ||
    report.source_security_reviewed_by !== source.source_security_reviewed_by ||
    report.source_lab_operated_by !== source.source_lab_operated_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest
  ) {
    throw new Error("Malware report does not match the exact vulnerability analysis");
  }
  return payload;
}

export async function analyzeConnectorPackageLicenses(source: ConnectorPackageMalwareAnalysis) {
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.malware_scan_completed ||
    source.license_scan_completed
  ) {
    throw new Error("Only a passed malware report can receive license policy analysis");
  }
  const response = await apiFetch("/api/v1/connectors/package-license-analyses", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-license.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-license-analysis-request.v1",
      source_malware_analysis_id: source.analysis_id,
      source_malware_analysis_digest: source.canonical_digest,
      package_digest: source.package_digest,
      analysis_profile: "atlas.connector-license-policy.python312.v1",
      acknowledged_policy_not_legal_advice: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package license analysis failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeLicenseAnalysis(payload)) {
    throw new Error("Connector registry returned unsafe license policy evidence");
  }
  const report = payload.data;
  if (
    report.source_malware_analysis_id !== source.analysis_id ||
    report.source_malware_analysis_digest !== source.canonical_digest ||
    report.source_vulnerability_analysis_id !== source.source_vulnerability_analysis_id ||
    report.source_vulnerability_analysis_digest !== source.source_vulnerability_analysis_digest ||
    report.source_static_dependency_analysis_id !==
      source.source_static_dependency_analysis_id ||
    report.source_static_dependency_analysis_digest !==
      source.source_static_dependency_analysis_digest ||
    report.source_authority_behavior_validation_id !==
      source.source_authority_behavior_validation_id ||
    report.source_schema_semantics_validation_id !== source.source_schema_semantics_validation_id ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_handoff_id !== source.source_handoff_id ||
    report.source_project_id !== source.source_project_id ||
    report.source_malware_analyzed_by !== source.analyzed_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest
  ) {
    throw new Error("License report does not match the exact malware analysis");
  }
  return payload;
}

export async function validateConnectorPackageContracts(
  source: ConnectorPackageLicenseAnalysis,
) {
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.license_scan_completed ||
    source.contract_validation_completed
  ) {
    throw new Error("Only a passed license report can receive contract validation");
  }
  const response = await apiFetch("/api/v1/connectors/package-contract-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-contract.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-contract-validation-request.v1",
      source_license_analysis_id: source.analysis_id,
      source_license_analysis_digest: source.canonical_digest,
      package_digest: source.package_digest,
      validation_profile: "atlas.connector-contract.python312.v1",
      acknowledged_static_contract_only: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package contract validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeContractValidation(payload)) {
    throw new Error("Connector registry returned unsafe contract validation evidence");
  }
  const report = payload.data;
  if (
    report.source_license_analysis_id !== source.analysis_id ||
    report.source_license_analysis_digest !== source.canonical_digest ||
    report.source_malware_analysis_id !== source.source_malware_analysis_id ||
    report.source_malware_analysis_digest !== source.source_malware_analysis_digest ||
    report.source_vulnerability_analysis_id !== source.source_vulnerability_analysis_id ||
    report.source_vulnerability_analysis_digest !== source.source_vulnerability_analysis_digest ||
    report.source_static_dependency_analysis_id !== source.source_static_dependency_analysis_id ||
    report.source_static_dependency_analysis_digest !==
      source.source_static_dependency_analysis_digest ||
    report.source_authority_behavior_validation_id !==
      source.source_authority_behavior_validation_id ||
    report.source_schema_semantics_validation_id !== source.source_schema_semantics_validation_id ||
    report.source_content_policy_scan_id !== source.source_content_policy_scan_id ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_validation_id !== source.source_validation_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_handoff_id !== source.source_handoff_id ||
    report.source_project_id !== source.source_project_id ||
    report.source_license_analyzed_by !== source.analyzed_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest ||
    report.dependency_set_digest !== source.dependency_set_digest
  ) {
    throw new Error("Contract report does not match the exact license analysis");
  }
  return payload;
}

export async function validateConnectorPackageRunner(
  source: ConnectorPackageContractValidation,
) {
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.contract_validation_completed ||
    source.runner_validation_completed
  ) {
    throw new Error("Only a passed contract report can receive runner validation");
  }
  const response = await apiFetch("/api/v1/connectors/package-runner-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-runner.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-runner-validation-request.v1",
      source_contract_validation_id: source.validation_id,
      source_contract_validation_digest: source.canonical_digest,
      package_digest: source.package_digest,
      validation_profile: "atlas.connector-runner.python312.v1",
      acknowledged_disconnected_synthetic_execution: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package runner validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeRunnerValidation(payload)) {
    throw new Error("Connector registry returned unsafe runner validation evidence");
  }
  const report = payload.data;
  if (
    report.source_contract_validation_id !== source.validation_id ||
    report.source_contract_validation_digest !== source.canonical_digest ||
    report.source_license_analysis_id !== source.source_license_analysis_id ||
    report.source_license_analysis_digest !== source.source_license_analysis_digest ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_project_id !== source.source_project_id ||
    report.source_contract_validated_by !== source.validated_by ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest ||
    report.capability_count !== source.coverage.capability_count
  ) {
    throw new Error("Runner report does not match the exact contract validation");
  }
  return payload;
}

export async function validateConnectorPackageLabSelfTest(input: {
  source: ConnectorPackageRunnerValidation;
  labPlanId: string;
  labPlanDigest: string;
}) {
  const { source, labPlanId, labPlanDigest } = input;
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.runner_validation_completed ||
    source.lab_validation_completed
  ) {
    throw new Error("Only a passed runner report can receive lab self-test validation");
  }
  if (!/^[a-z][a-z0-9_.:-]{2,127}$/.test(labPlanId) || !/^[a-f0-9]{64}$/.test(labPlanDigest)) {
    throw new Error("An approved lab plan ID and digest are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-lab-self-tests", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-lab.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-lab-self-test-request.v1",
      source_runner_validation_id: source.validation_id,
      source_runner_validation_digest: source.canonical_digest,
      package_digest: source.package_digest,
      lab_plan_id: labPlanId,
      lab_plan_digest: labPlanDigest,
      validation_profile: "atlas.connector-lab-self-test.readonly.v1",
      acknowledged_non_production_read_only_lab_access: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package lab self-test failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeLabSelfTest(payload)) {
    throw new Error("Connector registry returned unsafe lab self-test evidence");
  }
  const report = payload.data;
  if (
    report.source_runner_validation_id !== source.validation_id ||
    report.source_runner_validation_digest !== source.canonical_digest ||
    report.source_contract_validation_id !== source.source_contract_validation_id ||
    report.source_contract_validation_digest !== source.source_contract_validation_digest ||
    report.source_inventory_id !== source.source_inventory_id ||
    report.source_acquisition_id !== source.source_acquisition_id ||
    report.source_project_id !== source.source_project_id ||
    report.source_runner_validated_by !== source.validated_by ||
    report.source_actor_set_digest !== source.source_actor_set_digest ||
    report.lab_plan_id !== labPlanId ||
    report.lab_plan_digest !== labPlanDigest ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.package_size_bytes !== source.package_size_bytes ||
    report.inventory_digest !== source.inventory_digest ||
    report.capability_count !== source.capability_count
  ) {
    throw new Error("Lab self-test report does not match the exact runner report and plan");
  }
  return payload;
}

export async function validateConnectorPackageFinal(input: {
  source: ConnectorPackageLabSelfTest;
  policyId: string;
  policyDigest: string;
}) {
  const { source, policyId, policyDigest } = input;
  if (
    source.outcome !== "passed" ||
    source.promotion_blocked ||
    !source.lab_validation_completed
  ) {
    throw new Error("Only a passed lab self-test can receive final validation");
  }
  if (!/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) || !/^[a-f0-9]{64}$/.test(policyDigest)) {
    throw new Error("A signed final-validation policy ID and digest are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-final-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-final.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-final-validation-request.v1",
      source_lab_self_test_id: source.self_test_id,
      source_lab_self_test_digest: source.canonical_digest,
      package_digest: source.package_digest,
      policy_id: policyId,
      policy_digest: policyDigest,
      acknowledged_evidence_only_no_approval: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package final validation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeFinalValidation(payload)) {
    throw new Error("Connector registry returned unsafe final-validation evidence");
  }
  const report = payload.data;
  if (
    report.source_lab_self_test_id !== source.self_test_id ||
    report.source_lab_self_test_digest !== source.canonical_digest ||
    report.source_project_id !== source.source_project_id ||
    report.source_actor_set_digest !== source.source_actor_set_digest ||
    report.organization_id !== source.organization_id ||
    report.environment_id !== source.environment_id ||
    report.package_digest !== source.package_digest ||
    report.inventory_digest !== source.inventory_digest ||
    report.product_family !== source.product_family ||
    report.observed_product_version !== source.observed_product_version ||
    report.capability_count !== source.capability_count ||
    report.tested_capability_count !== source.tested_capability_count ||
    report.policy_id !== policyId ||
    report.policy_digest !== policyDigest
  ) {
    throw new Error("Final-validation report does not match the exact lab evidence and policy");
  }
  return payload;
}

export async function createConnectorPackageApprovalRequest(input: {
  source: ConnectorPackageFinalValidation;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { source, policyId, policyDigest, purpose } = input;
  if (!source.eligible_for_human_approval || source.promotion_blocked) {
    throw new Error("Only an eligible final-validation report can enter human approval");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("A signed approval policy and a bounded purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-approval-requests", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-approval.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-approval-request-input.v1",
      source_final_validation_id: source.validation_id,
      source_final_validation_digest: source.canonical_digest,
      package_digest: source.package_digest,
      approval_policy_id: policyId,
      approval_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_request_is_not_approval: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package approval request failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafePackageApproval(payload)) {
    throw new Error("Connector registry returned an unsafe approval record");
  }
  if (
    payload.data.request.source_final_validation_id !== source.validation_id ||
    payload.data.request.source_final_validation_digest !== source.canonical_digest ||
    payload.data.request.package_digest !== source.package_digest ||
    payload.data.request.approval_policy_id !== policyId ||
    payload.data.request.approval_policy_digest !== policyDigest
  ) {
    throw new Error("Approval request does not match the exact final-validation packet");
  }
  return payload;
}

export async function decideConnectorPackageApproval(input: {
  record: ConnectorPackageApprovalRecord;
  outcome: ConnectorPackageApprovalOutcome;
  rationale: string;
}) {
  const { record, outcome, rationale } = input;
  if (record.state !== "pending" || record.decision !== null || rationale.trim().length < 20) {
    throw new Error("A pending exact approval packet and a substantive rationale are required");
  }
  const response = await apiFetch(
    `/api/v1/connectors/package-approval-requests/${encodeURIComponent(record.request.request_id)}/decisions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-package-decision.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-package-approval-decision-input.v1",
        expected_request_version: record.request.version,
        request_digest: record.request.canonical_digest,
        outcome,
        rationale: rationale.trim(),
        acknowledged_decision_grants_no_runtime_authority: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Connector package approval decision failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafePackageApproval(payload)) {
    throw new Error("Connector registry returned an unsafe approval decision");
  }
  if (
    payload.data.request.request_id !== record.request.request_id ||
    payload.data.request.canonical_digest !== record.request.canonical_digest ||
    payload.data.decision?.outcome !== outcome
  ) {
    throw new Error("Approval decision does not match the exact pending packet");
  }
  return payload;
}

