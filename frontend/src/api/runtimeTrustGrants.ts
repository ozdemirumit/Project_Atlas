import type { ConnectorCapabilityEnablementInventoryItem } from "./capabilityEnablements";
import { apiFetch, ApiRequestError } from "./client";

export type ConnectorRuntimeTrustGrantInventoryItem = {
  grant_id: string;
  source_enablement_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
  capability_profile_id: string;
  capability_count: number;
  runtime_profile_id: string;
  sdk_profile: string;
  runner_runtime_id: string;
  runner_image_digest: string;
  runner_workload_identity_id: string;
  isolation_profile_id: string;
  filesystem_policy_id: string;
  egress_policy_id: string;
  telemetry_policy_id: string;
  resource_limit_profile_id: string;
  trust_policy_id: string;
  trust_policy_version: string;
  trust_version: 1;
  instance_state: "enabled_runtime_trusted";
  granted_by: string;
  purpose: string;
  granted_at: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  runner_started: false;
  package_loaded: false;
  credential_resolution_authorized: false;
  credentials_resolved: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorRuntimeTrustGrant = {
  grant_id: string;
  schema_version: "atlas.connector-runtime-trust-grant.v1";
  version: 1;
  source_enablement_id: string;
  source_enablement_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  capability_profile_id: string;
  capability_profile_digest: string;
  capability_count: number;
  runtime_profile_id: string;
  runtime_profile_digest: string;
  sdk_profile: string;
  runner_runtime_id: string;
  runner_pool_id: string;
  runner_image_digest: string;
  runner_workload_identity_id: string;
  isolation_profile_id: string;
  filesystem_policy_id: string;
  egress_policy_id: string;
  secret_delivery_policy_id: string;
  telemetry_policy_id: string;
  resource_limit_profile_id: string;
  trust_policy_id: string;
  trust_policy_digest: string;
  trust_policy_version: string;
  trust_version: 1;
  instance_state: "enabled_runtime_trusted";
  granted_by: string;
  purpose: string;
  granted_at: string;
  canonical_digest: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  promotion_blocked: false;
  runner_started: false;
  package_loaded: false;
  credential_resolution_authorized: false;
  credentials_resolved: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorRuntimeTrustGrantOption = {
  source_enablement_id: string;
  source_enablement_digest: string;
  package_digest: string;
  runtime_profile_id: string;
  runtime_profile_digest: string;
  runtime_profile_expires_at: string;
  sdk_profile: string;
  runner_runtime_id: string;
  runner_image_digest: string;
  runner_workload_identity_id: string;
  isolation_profile_id: string;
  filesystem_policy_id: string;
  egress_policy_id: string;
  telemetry_policy_id: string;
  resource_limit_profile_id: string;
  trust_policy_id: string;
  trust_policy_digest: string;
  trust_policy_version: string;
  trust_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  resulting_instance_state: "enabled_runtime_trusted";
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  runner_started: false;
  package_loaded: false;
  credential_resolution_authorized: false;
  credentials_resolved: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;

const inventoryFields = new Set([
  "grant_id", "source_enablement_id", "connector_id", "release_version", "instance_id",
  "display_name", "capability_profile_id", "capability_count", "runtime_profile_id",
  "sdk_profile", "runner_runtime_id",
  "runner_image_digest", "runner_workload_identity_id", "isolation_profile_id",
  "filesystem_policy_id", "egress_policy_id",
  "telemetry_policy_id", "resource_limit_profile_id", "trust_policy_id",
  "trust_policy_version", "trust_version", "instance_state", "granted_by", "purpose", "granted_at",
  "configuration_validated", "connectivity_evidence_verified", "capability_governance_applied",
  "connector_enabled", "eligible_for_runtime_trust",
  "runtime_boundary_bound", "runtime_trust_granted", "eligible_for_secret_brokerage",
  "runner_started", "package_loaded", "credential_resolution_authorized",
  "credentials_resolved", "target_connection_authorized", "capability_invocation_authorized",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);

const optionFields = new Set([
  "source_enablement_id", "source_enablement_digest", "package_digest", "runtime_profile_id",
  "runtime_profile_digest", "runtime_profile_expires_at", "sdk_profile", "runner_runtime_id",
  "runner_image_digest", "runner_workload_identity_id", "isolation_profile_id",
  "filesystem_policy_id", "egress_policy_id",
  "telemetry_policy_id", "resource_limit_profile_id", "trust_policy_id",
  "trust_policy_digest", "trust_policy_version", "trust_policy_expires_at",
  "required_assurance_level", "resulting_instance_state", "runtime_boundary_bound",
  "runtime_trust_granted", "eligible_for_secret_brokerage", "runner_started", "package_loaded",
  "credential_resolution_authorized", "credentials_resolved", "target_connection_authorized",
  "capability_invocation_authorized", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, allowed: ReadonlySet<string>): boolean {
  const fields = Object.keys(value);
  return fields.length === allowed.size && fields.every((field) => allowed.has(field));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function hasSafeBoundary(record: Record<string, unknown>): boolean {
  return (
    record.runtime_boundary_bound === true &&
    record.runtime_trust_granted === true &&
    record.eligible_for_secret_brokerage === true &&
    record.runner_started === false &&
    record.package_loaded === false &&
    record.credential_resolution_authorized === false &&
    record.credentials_resolved === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false
  );
}

function isInventoryItem(value: unknown): value is ConnectorRuntimeTrustGrantInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    hasExactFields(record, inventoryFields) &&
    [
      "grant_id", "source_enablement_id", "connector_id", "release_version", "instance_id",
      "runtime_profile_id", "sdk_profile", "runner_runtime_id",
      "runner_workload_identity_id", "isolation_profile_id", "filesystem_policy_id",
      "egress_policy_id", "telemetry_policy_id",
      "resource_limit_profile_id", "trust_policy_id", "trust_policy_version", "granted_by",
    ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    typeof record.display_name === "string" && record.display_name.length <= 120 &&
    typeof record.capability_profile_id === "string" && stableId.test(record.capability_profile_id) &&
    Number.isInteger(record.capability_count) && Number(record.capability_count) > 0 &&
    typeof record.runner_image_digest === "string" && digest.test(record.runner_image_digest) &&
    typeof record.purpose === "string" && record.purpose.trim().length >= 20 &&
    record.purpose.length <= 1000 &&
    isTimestamp(record.granted_at) &&
    record.trust_version === 1 &&
    record.instance_state === "enabled_runtime_trusted" &&
    record.configuration_validated === true &&
    record.connectivity_evidence_verified === true &&
    record.capability_governance_applied === true &&
    record.connector_enabled === true &&
    record.eligible_for_runtime_trust === true &&
    hasSafeBoundary(record)
  );
}

function isOption(value: unknown): value is ConnectorRuntimeTrustGrantOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    hasExactFields(record, optionFields) &&
    [
      "source_enablement_id", "runtime_profile_id", "sdk_profile", "runner_runtime_id",
      "runner_workload_identity_id", "isolation_profile_id",
      "filesystem_policy_id", "egress_policy_id",
      "telemetry_policy_id", "resource_limit_profile_id", "trust_policy_id",
      "trust_policy_version",
    ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    [
      "source_enablement_digest", "package_digest", "runtime_profile_digest",
      "runner_image_digest", "trust_policy_digest",
    ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    isTimestamp(record.runtime_profile_expires_at) &&
    isTimestamp(record.trust_policy_expires_at) &&
    typeof record.required_assurance_level === "string" &&
    ["single_factor", "multi_factor", "hardware_backed"].includes(
      record.required_assurance_level,
    ) &&
    record.resulting_instance_state === "enabled_runtime_trusted" &&
    hasSafeBoundary(record)
  );
}

export async function getConnectorRuntimeTrustGrants(input?: {
  sourceEnablementId?: string;
}): Promise<ConnectorRuntimeTrustGrantInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceEnablementId) parameters.set("source_enablement_id", input.sourceEnablementId);
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/runtime-trust-grants${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Runtime trust inventory failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data)) throw new Error("Runtime trust inventory returned unsafe records");
  const records: ConnectorRuntimeTrustGrantInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Runtime trust inventory returned unsafe records");
    }
    if (input?.sourceEnablementId && candidate.source_enablement_id !== input.sourceEnablementId) {
      throw new Error("Runtime trust inventory crossed the requested enablement scope");
    }
    records.push(candidate);
  }
  return records;
}

export async function getConnectorRuntimeTrustGrantOptions(
  sourceEnablementId: string,
): Promise<ConnectorRuntimeTrustGrantOption[]> {
  const parameters = new URLSearchParams({ source_enablement_id: sourceEnablementId });
  const response = await apiFetch(
    `/api/v1/connectors/runtime-trust-grants/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Runtime trust options failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data)) throw new Error("Runtime trust options returned unsafe evidence");
  const options: ConnectorRuntimeTrustGrantOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_enablement_id !== sourceEnablementId) {
      throw new Error("Runtime trust options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorRuntimeTrustGrant(input: {
  enablement: ConnectorCapabilityEnablementInventoryItem;
  option: ConnectorRuntimeTrustGrantOption;
  purpose: string;
}) {
  const { enablement, option, purpose } = input;
  if (
    !enablement.connector_enabled ||
    !enablement.eligible_for_runtime_trust ||
    enablement.runtime_trust_granted ||
    enablement.instance_state !== "enabled_capabilities_governed" ||
    option.source_enablement_id !== enablement.enablement_id
  ) throw new Error("A current capability-governed connector is required");
  if (
    !digest.test(option.source_enablement_digest) ||
    !digest.test(option.package_digest) ||
    !stableId.test(option.runtime_profile_id) ||
    !digest.test(option.runtime_profile_digest) ||
    !stableId.test(option.trust_policy_id) ||
    !digest.test(option.trust_policy_digest) ||
    purpose.trim().length < 20 ||
    purpose.length > 1000
  ) throw new Error("Exact signed runtime profile and trust policy are required");
  const response = await apiFetch("/api/v1/connectors/runtime-trust-grants", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-runtime-trust.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-runtime-trust-input.v1",
      source_enablement_id: enablement.enablement_id,
      source_enablement_digest: option.source_enablement_digest,
      package_digest: option.package_digest,
      runtime_profile_id: option.runtime_profile_id,
      runtime_profile_digest: option.runtime_profile_digest,
      trust_policy_id: option.trust_policy_id,
      trust_policy_digest: option.trust_policy_digest,
      purpose: purpose.trim(),
      acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Runtime trust grant failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!isInventoryItem(data)) throw new Error("Runtime trust service returned unsafe evidence");
  if (
    data.source_enablement_id !== enablement.enablement_id ||
    data.connector_id !== enablement.connector_id ||
    data.release_version !== enablement.release_version ||
    data.instance_id !== enablement.instance_id ||
    data.runtime_profile_id !== option.runtime_profile_id ||
    data.sdk_profile !== option.sdk_profile ||
    data.runner_runtime_id !== option.runner_runtime_id ||
    data.runner_image_digest !== option.runner_image_digest ||
    data.runner_workload_identity_id !== option.runner_workload_identity_id ||
    data.isolation_profile_id !== option.isolation_profile_id ||
    data.filesystem_policy_id !== option.filesystem_policy_id ||
    data.egress_policy_id !== option.egress_policy_id ||
    data.telemetry_policy_id !== option.telemetry_policy_id ||
    data.resource_limit_profile_id !== option.resource_limit_profile_id ||
    data.trust_policy_id !== option.trust_policy_id ||
    data.trust_policy_version !== option.trust_policy_version
  ) throw new Error("Runtime trust grant does not match the exact governed evidence");
  return { data };
}
