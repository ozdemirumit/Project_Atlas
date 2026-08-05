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

