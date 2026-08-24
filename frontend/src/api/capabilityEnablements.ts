import { apiFetch, ApiRequestError } from "./client";
import type {
  ConnectorConfigurationValidation,
  ConnectorConfigurationValidationInventoryItem,
} from "./configurationValidations";

export type ConnectorGovernedCapability = {
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
};

export type ConnectorCapabilityEnablement = {
  enablement_id: string;
  schema_version: "atlas.connector-capability-enablement.v1";
  version: 1;
  source_validation_id: string;
  source_validation_digest: string;
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
  capability_profile_id: string;
  capability_profile_digest: string;
  capabilities: ConnectorGovernedCapability[];
  enablement_policy_id: string;
  enablement_policy_digest: string;
  enablement_policy_version: string;
  enablement_version: 1;
  instance_state: "enabled_capabilities_governed";
  enabled_by: string;
  purpose: string;
  enabled_at: string;
  canonical_digest: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  promotion_blocked: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorCapabilityEnablementInventoryItem = {
  enablement_id: string;
  source_validation_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
  capability_profile_id: string;
  capabilities: ConnectorGovernedCapability[];
  enablement_policy_id: string;
  enablement_policy_version: string;
  instance_state: "enabled_capabilities_governed";
  enabled_by: string;
  purpose: string;
  enabled_at: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorCapabilityEnablementOption = {
  source_validation_id: string;
  source_validation_digest: string;
  package_digest: string;
  capability_profile_id: string;
  capability_profile_digest: string;
  capability_profile_expires_at: string;
  capabilities: ConnectorGovernedCapability[];
  enablement_policy_id: string;
  enablement_policy_digest: string;
  enablement_policy_version: string;
  enablement_policy_expires_at: string;
  required_assurance_level: "development" | "single_factor" | "multi_factor" | "hardware_backed";
  resulting_instance_state: "enabled_capabilities_governed";
  resulting_capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;

const capabilityFields = new Set([
  "capability_id",
  "capability_class",
  "required_permission",
]);

const inventoryFields = new Set([
  "enablement_id", "source_validation_id", "connector_id", "release_version", "instance_id",
  "display_name", "capability_profile_id", "capabilities", "enablement_policy_id",
  "enablement_policy_version", "instance_state", "enabled_by", "purpose", "enabled_at",
  "configuration_validated", "connectivity_evidence_verified",
  "eligible_for_capability_governance", "capability_governance_applied", "connector_enabled",
  "eligible_for_runtime_trust", "credentials_resolved", "runtime_trust_granted",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);

const optionFields = new Set([
  "source_validation_id", "source_validation_digest", "package_digest",
  "capability_profile_id", "capability_profile_digest", "capability_profile_expires_at",
  "capabilities", "enablement_policy_id", "enablement_policy_digest",
  "enablement_policy_version", "enablement_policy_expires_at", "required_assurance_level",
  "resulting_instance_state", "resulting_capability_governance_applied",
  "connector_enabled", "eligible_for_runtime_trust", "credentials_resolved",
  "runtime_trust_granted", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, allowed: ReadonlySet<string>): boolean {
  const fields = Object.keys(value);
  return fields.length === allowed.size && fields.every((field) => allowed.has(field));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function isCapability(value: unknown): value is ConnectorGovernedCapability {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    hasExactFields(record, capabilityFields) &&
    typeof record.capability_id === "string" &&
    stableId.test(record.capability_id) &&
    (record.capability_class === "C0" || record.capability_class === "C1") &&
    typeof record.required_permission === "string" &&
    stableId.test(record.required_permission)
  );
}

function hasCapabilities(record: Record<string, unknown>): boolean {
  return (
    Array.isArray(record.capabilities) &&
    record.capabilities.length > 0 &&
    record.capabilities.length <= 100 &&
    record.capabilities.every(isCapability) &&
    new Set(record.capabilities.map((item) => item.capability_id))
      .size === record.capabilities.length
  );
}

function capabilitiesMatch(
  actual: ConnectorGovernedCapability[],
  expected: ConnectorGovernedCapability[],
): boolean {
  return (
    actual.length === expected.length &&
    actual.every((capability, index) => {
      const candidate = expected[index];
      return (
        candidate !== undefined &&
        capability.capability_id === candidate.capability_id &&
        capability.capability_class === candidate.capability_class &&
        capability.required_permission === candidate.required_permission
      );
    })
  );
}

function hasSafeAuthorityBoundary(record: Record<string, unknown>): boolean {
  return (
    record.instance_state === "enabled_capabilities_governed" &&
    record.configuration_validated === true &&
    record.connectivity_evidence_verified === true &&
    record.eligible_for_capability_governance === true &&
    record.capability_governance_applied === true &&
    record.connector_enabled === true &&
    record.eligible_for_runtime_trust === true &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false
  );
}

function isInventoryItem(value: unknown): value is ConnectorCapabilityEnablementInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    hasExactFields(record, inventoryFields) &&
    [
      "enablement_id", "source_validation_id", "connector_id", "release_version", "instance_id",
      "capability_profile_id", "enablement_policy_id", "enablement_policy_version", "enabled_by",
    ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    typeof record.display_name === "string" && record.display_name.length <= 120 &&
    typeof record.purpose === "string" && record.purpose.trim().length >= 20 &&
    record.purpose.length <= 1000 &&
    isTimestamp(record.enabled_at) &&
    hasCapabilities(record) &&
    hasSafeAuthorityBoundary(record)
  );
}

function isOption(value: unknown): value is ConnectorCapabilityEnablementOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    hasExactFields(record, optionFields) &&
    ["source_validation_id", "capability_profile_id", "enablement_policy_id", "enablement_policy_version"]
      .every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    [
      "source_validation_digest", "package_digest", "capability_profile_digest",
      "enablement_policy_digest",
    ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    isTimestamp(record.capability_profile_expires_at) &&
    isTimestamp(record.enablement_policy_expires_at) &&
    typeof record.required_assurance_level === "string" &&
    ["development", "single_factor", "multi_factor", "hardware_backed"].includes(
      record.required_assurance_level,
    ) &&
    hasCapabilities(record) &&
    record.resulting_instance_state === "enabled_capabilities_governed" &&
    record.resulting_capability_governance_applied === true &&
    record.connector_enabled === true &&
    record.eligible_for_runtime_trust === true &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false
  );
}

export function toConnectorCapabilityEnablementInventoryItem(
  enablement: ConnectorCapabilityEnablement,
): ConnectorCapabilityEnablementInventoryItem {
  return {
    enablement_id: enablement.enablement_id,
    source_validation_id: enablement.source_validation_id,
    connector_id: enablement.connector_id,
    release_version: enablement.release_version,
    instance_id: enablement.instance_id,
    display_name: enablement.display_name,
    capability_profile_id: enablement.capability_profile_id,
    capabilities: enablement.capabilities.map((item) => ({ ...item })),
    enablement_policy_id: enablement.enablement_policy_id,
    enablement_policy_version: enablement.enablement_policy_version,
    instance_state: "enabled_capabilities_governed",
    enabled_by: enablement.enabled_by,
    purpose: enablement.purpose,
    enabled_at: enablement.enabled_at,
    configuration_validated: true,
    connectivity_evidence_verified: true,
    eligible_for_capability_governance: true,
    capability_governance_applied: true,
    connector_enabled: true,
    eligible_for_runtime_trust: true,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  };
}

export async function getConnectorCapabilityEnablements(input?: {
  sourceValidationId?: string;
}): Promise<ConnectorCapabilityEnablementInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceValidationId) {
    parameters.set("source_validation_id", input.sourceValidationId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/capability-enablements${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Capability enablement inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Capability enablement inventory returned unsafe records");
  }
  const records: ConnectorCapabilityEnablementInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Capability enablement inventory returned unsafe records");
    }
    if (input?.sourceValidationId && candidate.source_validation_id !== input.sourceValidationId) {
      throw new Error("Capability enablement inventory crossed the requested validation scope");
    }
    records.push(candidate);
  }
  return records;
}

export async function getConnectorCapabilityEnablementOptions(
  sourceValidationId: string,
): Promise<ConnectorCapabilityEnablementOption[]> {
  const parameters = new URLSearchParams({ source_validation_id: sourceValidationId });
  const response = await apiFetch(
    `/api/v1/connectors/capability-enablements/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Capability enablement options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Capability enablement options returned unsafe evidence");
  }
  const options: ConnectorCapabilityEnablementOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_validation_id !== sourceValidationId) {
      throw new Error("Capability enablement options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorCapabilityEnablement(input: {
  validation: ConnectorConfigurationValidation | ConnectorConfigurationValidationInventoryItem;
  option: ConnectorCapabilityEnablementOption;
  purpose: string;
}) {
  const { validation, option, purpose } = input;
  if (
    !validation.configuration_validated ||
    !validation.eligible_for_capability_governance ||
    validation.connector_enabled ||
    validation.instance_state !== "disabled_configuration_validated" ||
    option.source_validation_id !== validation.validation_id
  ) {
    throw new Error("A current disabled configuration-validated connector is required");
  }
  if (
    !digest.test(option.source_validation_digest) ||
    !digest.test(option.package_digest) ||
    !stableId.test(option.capability_profile_id) ||
    !digest.test(option.capability_profile_digest) ||
    !stableId.test(option.enablement_policy_id) ||
    !digest.test(option.enablement_policy_digest) ||
    purpose.trim().length < 20 ||
    purpose.length > 1000
  ) {
    throw new Error("Exact signed capability profile and policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/capability-enablements", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-capability-enablement.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-capability-enablement-input.v1",
      source_validation_id: validation.validation_id,
      source_validation_digest: option.source_validation_digest,
      package_digest: option.package_digest,
      capability_profile_id: option.capability_profile_id,
      capability_profile_digest: option.capability_profile_digest,
      enablement_policy_id: option.enablement_policy_id,
      enablement_policy_digest: option.enablement_policy_digest,
      purpose: purpose.trim(),
      acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Capability enablement failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!isInventoryItem(data)) {
    throw new Error("Enablement service returned unsafe evidence");
  }
  if (
    data.source_validation_id !== validation.validation_id ||
    data.instance_id !== validation.instance_id ||
    data.connector_id !== validation.connector_id ||
    data.release_version !== validation.release_version ||
    data.capability_profile_id !== option.capability_profile_id ||
    data.enablement_policy_id !== option.enablement_policy_id ||
    data.enablement_policy_version !== option.enablement_policy_version ||
    !capabilitiesMatch(data.capabilities, option.capabilities)
  ) {
    throw new Error("Capability enablement does not match the exact governed evidence");
  }
  return { data };
}
