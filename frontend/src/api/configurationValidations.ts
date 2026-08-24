import { apiFetch, ApiRequestError } from "./client";
import type {
  ConnectorCredentialAssignment,
  ConnectorCredentialAssignmentInventoryItem,
} from "./credentialAssignments";

export type ConnectorConfigurationValidation = {
  validation_id: string;
  schema_version: "atlas.connector-configuration-validation.v1";
  version: 1;
  source_assignment_id: string;
  source_assignment_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  owner_id: string;
  target_profile_id: string;
  target_profile_digest: string;
  site_id: string;
  target_type: string;
  target_product: string;
  credential_profile_id: string;
  credential_profile_digest: string;
  credential_class: string;
  authentication_method: string;
  privilege_class: string;
  evidence_id: string;
  evidence_digest: string;
  probe_runner_id: string;
  probe_runner_version: string;
  network_zone_id: string;
  configuration_result: string;
  connectivity_result: string;
  tls_result: string;
  endpoint_identity_result: string;
  authentication_result: string;
  authorization_result: string;
  product_identity_result: string;
  latency_band: string;
  completed_checks: string[];
  evidence_observed_at: string;
  validation_policy_id: string;
  validation_policy_digest: string;
  validation_policy_version: string;
  validation_version: 1;
  instance_state: "disabled_configuration_validated";
  validated_by: string;
  purpose: string;
  validated_at: string;
  canonical_digest: string;
  package_installed: true;
  instance_created: true;
  target_configured: true;
  credential_references_assigned: true;
  eligible_for_configuration_validation: true;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  promotion_blocked: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorConfigurationValidationInventoryItem = {
  validation_id: string;
  source_assignment_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
  evidence_id: string;
  evidence_observed_at: string;
  configuration_result: string;
  connectivity_result: string;
  tls_result: string;
  endpoint_identity_result: string;
  authentication_result: string;
  authorization_result: string;
  product_identity_result: string;
  latency_band: string;
  completed_checks: string[];
  validation_policy_id: string;
  validation_policy_version: string;
  instance_state: "disabled_configuration_validated";
  validated_by: string;
  purpose: string;
  validated_at: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorConfigurationValidationOption = {
  source_assignment_id: string;
  source_assignment_digest: string;
  package_digest: string;
  evidence_id: string;
  evidence_digest: string;
  evidence_observed_at: string;
  evidence_expires_at: string;
  configuration_result: string;
  connectivity_result: string;
  tls_result: string;
  endpoint_identity_result: string;
  authentication_result: string;
  authorization_result: string;
  product_identity_result: string;
  latency_band: string;
  completed_checks: string[];
  validation_policy_id: string;
  validation_policy_digest: string;
  validation_policy_version: string;
  validation_policy_expires_at: string;
  required_assurance_level: string;
  resulting_instance_state: "disabled_configuration_validated";
  resulting_configuration_validated: true;
  resulting_connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const validationFields = new Set([
  "validation_id", "schema_version", "version", "source_assignment_id",
  "source_assignment_digest", "organization_id", "environment_id", "package_digest",
  "connector_id", "release_version", "manifest_digest", "instance_id", "instance_key",
  "display_name", "owner_id", "target_profile_id", "target_profile_digest", "site_id",
  "target_type", "target_product", "credential_profile_id", "credential_profile_digest",
  "credential_class", "authentication_method", "privilege_class", "evidence_id",
  "evidence_digest", "probe_runner_id", "probe_runner_version", "network_zone_id",
  "configuration_result", "connectivity_result", "tls_result", "endpoint_identity_result",
  "authentication_result", "authorization_result", "product_identity_result", "latency_band",
  "completed_checks", "evidence_observed_at", "validation_policy_id",
  "validation_policy_digest", "validation_policy_version", "validation_version",
  "instance_state", "validated_by", "purpose", "validated_at", "canonical_digest",
  "package_installed", "instance_created", "target_configured", "credential_references_assigned",
  "eligible_for_configuration_validation", "configuration_validated",
  "connectivity_evidence_verified", "eligible_for_capability_governance", "promotion_blocked",
  "credentials_resolved", "connector_enabled", "runtime_trust_granted", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed", "reused",
]);

const inventoryFields = new Set([
  "validation_id", "source_assignment_id", "connector_id", "release_version", "instance_id",
  "display_name", "evidence_id", "evidence_observed_at", "configuration_result",
  "connectivity_result", "tls_result", "endpoint_identity_result", "authentication_result",
  "authorization_result", "product_identity_result", "latency_band", "completed_checks",
  "validation_policy_id", "validation_policy_version", "instance_state", "validated_by",
  "purpose", "validated_at", "configuration_validated", "connectivity_evidence_verified",
  "eligible_for_capability_governance", "credentials_resolved", "connector_enabled",
  "runtime_trust_granted", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

const optionFields = new Set([
  "source_assignment_id", "source_assignment_digest", "package_digest", "evidence_id",
  "evidence_digest", "evidence_observed_at", "evidence_expires_at", "configuration_result",
  "connectivity_result", "tls_result", "endpoint_identity_result", "authentication_result",
  "authorization_result", "product_identity_result", "latency_band", "completed_checks",
  "validation_policy_id", "validation_policy_digest", "validation_policy_version",
  "validation_policy_expires_at", "required_assurance_level", "resulting_instance_state",
  "resulting_configuration_validated", "resulting_connectivity_evidence_verified",
  "eligible_for_capability_governance", "credentials_resolved", "connector_enabled",
  "runtime_trust_granted", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, allowed: ReadonlySet<string>): boolean {
  const fields = Object.keys(value);
  return fields.length === allowed.size && fields.every((field) => allowed.has(field));
}

function isBoundedClassification(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 128 &&
    /^[a-z][a-z0-9-]{0,63}\.[a-z][a-z0-9-]{0,63}$/.test(value)
  );
}

function hasSafeResultBoundary(record: Record<string, unknown>): boolean {
  return (
    record.instance_state === "disabled_configuration_validated" &&
    record.configuration_validated === true &&
    record.connectivity_evidence_verified === true &&
    record.eligible_for_capability_governance === true &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false
  );
}

function hasSafeClassifications(record: Record<string, unknown>): boolean {
  return (
    isBoundedClassification(record.configuration_result) &&
    isBoundedClassification(record.connectivity_result) &&
    isBoundedClassification(record.tls_result) &&
    isBoundedClassification(record.endpoint_identity_result) &&
    isBoundedClassification(record.authentication_result) &&
    isBoundedClassification(record.authorization_result) &&
    isBoundedClassification(record.product_identity_result) &&
    isBoundedClassification(record.latency_band) &&
    Array.isArray(record.completed_checks) &&
    record.completed_checks.length <= 64 &&
    record.completed_checks.every(isBoundedClassification)
  );
}

function isValidation(value: unknown): value is ConnectorConfigurationValidation {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-configuration-validation.v1" &&
    record.version === 1 &&
    typeof record.validation_id === "string" &&
    typeof record.source_assignment_id === "string" &&
    typeof record.source_assignment_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.source_assignment_digest) &&
    typeof record.package_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.package_digest) &&
    typeof record.instance_id === "string" &&
    typeof record.credential_profile_id === "string" &&
    typeof record.evidence_id === "string" &&
    typeof record.evidence_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.evidence_digest) &&
    typeof record.validation_policy_id === "string" &&
    typeof record.validation_policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.validation_policy_digest) &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    [
      "organization_id", "environment_id", "connector_id", "release_version", "manifest_digest",
      "instance_key", "display_name", "owner_id", "target_profile_id", "target_profile_digest",
      "site_id", "target_type", "target_product", "credential_profile_digest", "credential_class",
      "authentication_method", "privilege_class", "probe_runner_id", "probe_runner_version",
      "network_zone_id", "evidence_observed_at", "validation_policy_version", "validated_by",
      "purpose", "validated_at",
    ].every((field) => typeof record[field] === "string") &&
    record.validation_version === 1 &&
    record.package_installed === true &&
    record.instance_created === true &&
    record.target_configured === true &&
    record.credential_references_assigned === true &&
    record.eligible_for_configuration_validation === true &&
    record.promotion_blocked === false &&
    typeof record.reused === "boolean" &&
    record.deployment_approved === false &&
    hasSafeClassifications(record) &&
    hasSafeResultBoundary(record) &&
    hasExactFields(record, validationFields)
  );
}

function isInventoryItem(value: unknown): value is ConnectorConfigurationValidationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.validation_id === "string" &&
    typeof record.source_assignment_id === "string" &&
    typeof record.connector_id === "string" &&
    typeof record.release_version === "string" &&
    typeof record.instance_id === "string" &&
    typeof record.display_name === "string" &&
    typeof record.evidence_id === "string" &&
    typeof record.evidence_observed_at === "string" &&
    typeof record.validation_policy_id === "string" &&
    typeof record.validation_policy_version === "string" &&
    typeof record.validated_by === "string" &&
    typeof record.purpose === "string" &&
    typeof record.validated_at === "string" &&
    hasSafeClassifications(record) &&
    hasSafeResultBoundary(record) &&
    hasExactFields(record, inventoryFields)
  );
}

function isOption(value: unknown): value is ConnectorConfigurationValidationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.source_assignment_id === "string" &&
    typeof record.source_assignment_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.source_assignment_digest) &&
    typeof record.package_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.package_digest) &&
    typeof record.evidence_id === "string" &&
    typeof record.evidence_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.evidence_digest) &&
    typeof record.evidence_observed_at === "string" &&
    typeof record.evidence_expires_at === "string" &&
    typeof record.validation_policy_id === "string" &&
    typeof record.validation_policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.validation_policy_digest) &&
    typeof record.validation_policy_version === "string" &&
    typeof record.validation_policy_expires_at === "string" &&
    typeof record.required_assurance_level === "string" &&
    /^[A-Z][A-Z0-9_]{2,63}$/.test(record.required_assurance_level) &&
    record.resulting_instance_state === "disabled_configuration_validated" &&
    record.resulting_configuration_validated === true &&
    record.resulting_connectivity_evidence_verified === true &&
    record.eligible_for_capability_governance === true &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    hasSafeClassifications(record) &&
    hasExactFields(record, optionFields)
  );
}

export function toConnectorConfigurationValidationInventoryItem(
  validation: ConnectorConfigurationValidation,
): ConnectorConfigurationValidationInventoryItem {
  return {
    validation_id: validation.validation_id,
    source_assignment_id: validation.source_assignment_id,
    connector_id: validation.connector_id,
    release_version: validation.release_version,
    instance_id: validation.instance_id,
    display_name: validation.display_name,
    evidence_id: validation.evidence_id,
    evidence_observed_at: validation.evidence_observed_at,
    configuration_result: validation.configuration_result,
    connectivity_result: validation.connectivity_result,
    tls_result: validation.tls_result,
    endpoint_identity_result: validation.endpoint_identity_result,
    authentication_result: validation.authentication_result,
    authorization_result: validation.authorization_result,
    product_identity_result: validation.product_identity_result,
    latency_band: validation.latency_band,
    completed_checks: [...validation.completed_checks],
    validation_policy_id: validation.validation_policy_id,
    validation_policy_version: validation.validation_policy_version,
    instance_state: validation.instance_state,
    validated_by: validation.validated_by,
    purpose: validation.purpose,
    validated_at: validation.validated_at,
    configuration_validated: true,
    connectivity_evidence_verified: true,
    eligible_for_capability_governance: true,
    credentials_resolved: false,
    connector_enabled: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  };
}

export async function getConnectorConfigurationValidations(input?: {
  sourceAssignmentId?: string;
}): Promise<ConnectorConfigurationValidationInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceAssignmentId) {
    parameters.set("source_assignment_id", input.sourceAssignmentId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/configuration-validations${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Configuration validation inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Configuration validation inventory returned unsafe records");
  }
  const validations: ConnectorConfigurationValidationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Configuration validation inventory returned unsafe records");
    }
    if (input?.sourceAssignmentId && candidate.source_assignment_id !== input.sourceAssignmentId) {
      throw new Error("Configuration validation inventory crossed the requested assignment scope");
    }
    validations.push(candidate);
  }
  return validations;
}

export async function getConnectorConfigurationValidationOptions(
  sourceAssignmentId: string,
): Promise<ConnectorConfigurationValidationOption[]> {
  const parameters = new URLSearchParams({ source_assignment_id: sourceAssignmentId });
  const response = await apiFetch(
    `/api/v1/connectors/configuration-validations/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Configuration validation options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Configuration validation options returned unsafe evidence");
  }
  const options: ConnectorConfigurationValidationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_assignment_id !== sourceAssignmentId) {
      throw new Error("Configuration validation options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorConfigurationValidation(input: {
  assignment: ConnectorCredentialAssignment | ConnectorCredentialAssignmentInventoryItem;
  option: ConnectorConfigurationValidationOption;
  purpose: string;
}) {
  const { assignment, option, purpose } = input;
  if (
    !assignment.credential_references_assigned ||
    !assignment.eligible_for_configuration_validation ||
    assignment.credentials_resolved ||
    assignment.instance_state !== "disabled_credentials_assigned" ||
    option.source_assignment_id !== assignment.assignment_id
  ) {
    throw new Error("A current disabled credential-assigned connector is required");
  }
  if (
    !/^[a-f0-9]{64}$/.test(option.source_assignment_digest) ||
    !/^[a-f0-9]{64}$/.test(option.package_digest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(option.evidence_id) ||
    !/^[a-f0-9]{64}$/.test(option.evidence_digest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(option.validation_policy_id) ||
    !/^[a-f0-9]{64}$/.test(option.validation_policy_digest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("Exact signed validation evidence and policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/configuration-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-configuration-validation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-configuration-validation-input.v1",
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: option.source_assignment_digest,
      package_digest: option.package_digest,
      evidence_id: option.evidence_id,
      evidence_digest: option.evidence_digest,
      validation_policy_id: option.validation_policy_id,
      validation_policy_digest: option.validation_policy_digest,
      purpose: purpose.trim(),
      acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Configuration validation failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!isValidation(data)) {
    throw new Error("Validation service returned unsafe evidence");
  }
  if (
    data.source_assignment_id !== assignment.assignment_id ||
    data.source_assignment_digest !== option.source_assignment_digest ||
    data.package_digest !== option.package_digest ||
    data.instance_id !== assignment.instance_id ||
    data.evidence_id !== option.evidence_id ||
    data.evidence_digest !== option.evidence_digest ||
    data.validation_policy_id !== option.validation_policy_id ||
    data.validation_policy_digest !== option.validation_policy_digest
  ) {
    throw new Error("Configuration validation does not match the exact governed evidence");
  }
  return { data };
}
