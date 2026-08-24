import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorRuntimeTrustGrantInventoryItem } from "./runtimeTrustGrants";

export type ConnectorSecretBrokerageAuthorizationInventoryItem = {
  authorization_id: string;
  source_runtime_trust_grant_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
  credential_class: string;
  authentication_method: string;
  privilege_class: string;
  rotation_state: string;
  revocation_state: string;
  next_rotation_at: string;
  runtime_profile_id: string;
  brokerage_profile_id: string;
  delivery_policy_id: string;
  lease_policy_id: string;
  maximum_lease_seconds: number;
  revocation_policy_id: string;
  brokerage_policy_id: string;
  brokerage_policy_version: string;
  authorization_version: 1;
  instance_state: "enabled_secret_brokerage_governed";
  authorized_by: string;
  purpose: string;
  authorized_at: string;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  secret_brokerage_governed: true;
  credential_resolution_authorized: true;
  eligible_for_runtime_activation: true;
  promotion_blocked: false;
  secret_lease_issued: false;
  credentials_resolved: false;
  runner_started: false;
  package_loaded: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorSecretBrokerageAuthorizationOption = {
  source_runtime_trust_grant_id: string;
  source_runtime_trust_digest: string;
  package_digest: string;
  brokerage_profile_id: string;
  brokerage_profile_digest: string;
  brokerage_profile_expires_at: string;
  delivery_policy_id: string;
  lease_policy_id: string;
  maximum_lease_seconds: number;
  revocation_policy_id: string;
  brokerage_policy_id: string;
  brokerage_policy_digest: string;
  brokerage_policy_version: string;
  brokerage_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  resulting_instance_state: "enabled_secret_brokerage_governed";
  secret_brokerage_governed: true;
  credential_resolution_authorized: true;
  eligible_for_runtime_activation: true;
  secret_lease_issued: false;
  credentials_resolved: false;
  runner_started: false;
  package_loaded: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

// The later runtime-activation contract still consumes this full internal evidence type.
export type ConnectorSecretBrokerageAuthorization = {
  authorization_id: string;
  schema_version: "atlas.connector-secret-brokerage-authorization.v1";
  version: 1;
  source_runtime_trust_grant_id: string;
  source_runtime_trust_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  credential_class: string;
  authentication_method: string;
  privilege_class: string;
  rotation_state: string;
  revocation_state: string;
  next_rotation_at: string;
  runtime_profile_id: string;
  runtime_profile_digest: string;
  runner_workload_identity_id: string;
  secret_delivery_policy_id: string;
  brokerage_profile_id: string;
  brokerage_profile_digest: string;
  delivery_policy_id: string;
  lease_policy_id: string;
  maximum_lease_seconds: number;
  revocation_policy_id: string;
  brokerage_policy_id: string;
  brokerage_policy_digest: string;
  brokerage_policy_version: string;
  authorization_version: 1;
  instance_state: "enabled_secret_brokerage_governed";
  authorized_by: string;
  purpose: string;
  authorized_at: string;
  canonical_digest: string;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  secret_brokerage_governed: true;
  credential_resolution_authorized: true;
  eligible_for_runtime_activation: true;
  promotion_blocked: false;
  secret_lease_issued: false;
  credentials_resolved: false;
  runner_started: false;
  package_loaded: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;

const inventoryFields = new Set([
  "authorization_id", "source_runtime_trust_grant_id", "connector_id", "release_version",
  "instance_id", "display_name", "credential_class", "authentication_method", "privilege_class",
  "rotation_state", "revocation_state", "next_rotation_at", "runtime_profile_id",
  "brokerage_profile_id", "delivery_policy_id", "lease_policy_id", "maximum_lease_seconds",
  "revocation_policy_id", "brokerage_policy_id", "brokerage_policy_version",
  "authorization_version", "instance_state", "authorized_by", "purpose", "authorized_at",
  "runtime_boundary_bound", "runtime_trust_granted", "eligible_for_secret_brokerage",
  "secret_brokerage_governed", "credential_resolution_authorized",
  "eligible_for_runtime_activation", "promotion_blocked", "secret_lease_issued",
  "credentials_resolved", "runner_started", "package_loaded", "target_connection_authorized",
  "capability_invocation_authorized", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

const optionFields = new Set([
  "source_runtime_trust_grant_id", "source_runtime_trust_digest", "package_digest",
  "brokerage_profile_id", "brokerage_profile_digest", "brokerage_profile_expires_at",
  "delivery_policy_id", "lease_policy_id", "maximum_lease_seconds", "revocation_policy_id",
  "brokerage_policy_id", "brokerage_policy_digest", "brokerage_policy_version",
  "brokerage_policy_expires_at", "required_assurance_level", "resulting_instance_state",
  "secret_brokerage_governed", "credential_resolution_authorized",
  "eligible_for_runtime_activation", "secret_lease_issued", "credentials_resolved",
  "runner_started", "package_loaded", "target_connection_authorized",
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
  return record.runtime_boundary_bound === true && record.runtime_trust_granted === true &&
    record.eligible_for_secret_brokerage === true && record.secret_brokerage_governed === true &&
    record.credential_resolution_authorized === true &&
    record.eligible_for_runtime_activation === true && record.secret_lease_issued === false &&
    record.credentials_resolved === false && record.runner_started === false &&
    record.package_loaded === false && record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function hasSafeOptionBoundary(record: Record<string, unknown>): boolean {
  return record.secret_brokerage_governed === true &&
    record.credential_resolution_authorized === true &&
    record.eligible_for_runtime_activation === true && record.secret_lease_issued === false &&
    record.credentials_resolved === false && record.runner_started === false &&
    record.package_loaded === false && record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is ConnectorSecretBrokerageAuthorizationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "authorization_id", "source_runtime_trust_grant_id", "connector_id", "release_version",
    "instance_id", "credential_class", "authentication_method", "privilege_class",
    "rotation_state", "revocation_state", "runtime_profile_id", "brokerage_profile_id",
    "delivery_policy_id", "lease_policy_id", "revocation_policy_id", "brokerage_policy_id",
    "brokerage_policy_version", "authorized_by",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    typeof record.display_name === "string" && record.display_name.length <= 120 &&
    isTimestamp(record.next_rotation_at) && Number.isInteger(record.maximum_lease_seconds) &&
    Number(record.maximum_lease_seconds) >= 1 && Number(record.maximum_lease_seconds) <= 900 &&
    record.authorization_version === 1 &&
    record.instance_state === "enabled_secret_brokerage_governed" &&
    typeof record.purpose === "string" && record.purpose.trim().length >= 20 &&
    record.purpose.length <= 1000 && isTimestamp(record.authorized_at) &&
    record.promotion_blocked === false && hasSafeBoundary(record);
}

function isOption(value: unknown): value is ConnectorSecretBrokerageAuthorizationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_runtime_trust_grant_id", "brokerage_profile_id", "delivery_policy_id",
    "lease_policy_id", "revocation_policy_id", "brokerage_policy_id",
    "brokerage_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_runtime_trust_digest", "package_digest", "brokerage_profile_digest",
    "brokerage_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    isTimestamp(record.brokerage_profile_expires_at) &&
    isTimestamp(record.brokerage_policy_expires_at) &&
    Number.isInteger(record.maximum_lease_seconds) && Number(record.maximum_lease_seconds) >= 1 &&
    Number(record.maximum_lease_seconds) <= 900 &&
    typeof record.required_assurance_level === "string" &&
    ["single_factor", "multi_factor", "hardware_backed"].includes(record.required_assurance_level) &&
    record.resulting_instance_state === "enabled_secret_brokerage_governed" &&
    hasSafeOptionBoundary(record);
}

export async function getConnectorSecretBrokerageAuthorizations(input?: {
  sourceRuntimeTrustGrantId?: string;
}): Promise<ConnectorSecretBrokerageAuthorizationInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceRuntimeTrustGrantId) {
    parameters.set("source_runtime_trust_grant_id", input.sourceRuntimeTrustGrantId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/secret-brokerage-authorizations${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Secret brokerage inventory failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Secret brokerage inventory returned unsafe records");
  const records: ConnectorSecretBrokerageAuthorizationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Secret brokerage inventory returned unsafe records");
    }
    if (input?.sourceRuntimeTrustGrantId &&
      candidate.source_runtime_trust_grant_id !== input.sourceRuntimeTrustGrantId) {
      throw new Error("Secret brokerage inventory crossed the requested runtime trust scope");
    }
    records.push(candidate);
  }
  return records;
}

export async function getConnectorSecretBrokerageAuthorizationOptions(
  sourceRuntimeTrustGrantId: string,
): Promise<ConnectorSecretBrokerageAuthorizationOption[]> {
  const parameters = new URLSearchParams({ source_runtime_trust_grant_id: sourceRuntimeTrustGrantId });
  const response = await apiFetch(
    `/api/v1/connectors/secret-brokerage-authorizations/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Secret brokerage options failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Secret brokerage options returned unsafe evidence");
  const options: ConnectorSecretBrokerageAuthorizationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_runtime_trust_grant_id !== sourceRuntimeTrustGrantId) {
      throw new Error("Secret brokerage options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorSecretBrokerageAuthorization(input: {
  runtimeTrust: ConnectorRuntimeTrustGrantInventoryItem;
  option: ConnectorSecretBrokerageAuthorizationOption;
  purpose: string;
}) {
  const { runtimeTrust, option, purpose } = input;
  if (!runtimeTrust.runtime_trust_granted || !runtimeTrust.eligible_for_secret_brokerage ||
    runtimeTrust.credential_resolution_authorized ||
    runtimeTrust.instance_state !== "enabled_runtime_trusted" ||
    option.source_runtime_trust_grant_id !== runtimeTrust.grant_id) {
    throw new Error("A current runtime-trusted connector is required");
  }
  if (!digest.test(option.source_runtime_trust_digest) || !digest.test(option.package_digest) ||
    !stableId.test(option.brokerage_profile_id) || !digest.test(option.brokerage_profile_digest) ||
    !stableId.test(option.brokerage_policy_id) || !digest.test(option.brokerage_policy_digest) ||
    purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact signed brokerage profile and policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/secret-brokerage-authorizations", {
    method: "POST",
    headers: {
      Accept: "application/json", "Content-Type": "application/json",
      "Idempotency-Key": `connector-secret-brokerage.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-secret-brokerage-input.v1",
      source_runtime_trust_grant_id: runtimeTrust.grant_id,
      source_runtime_trust_digest: option.source_runtime_trust_digest,
      package_digest: option.package_digest,
      brokerage_profile_id: option.brokerage_profile_id,
      brokerage_profile_digest: option.brokerage_profile_digest,
      brokerage_policy_id: option.brokerage_policy_id,
      brokerage_policy_digest: option.brokerage_policy_digest,
      purpose: purpose.trim(),
      acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Secret brokerage authorization failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!isInventoryItem(data)) throw new Error("Secret brokerage service returned unsafe evidence");
  if (data.source_runtime_trust_grant_id !== runtimeTrust.grant_id ||
    data.connector_id !== runtimeTrust.connector_id || data.release_version !== runtimeTrust.release_version ||
    data.instance_id !== runtimeTrust.instance_id ||
    data.brokerage_profile_id !== option.brokerage_profile_id ||
    data.delivery_policy_id !== option.delivery_policy_id || data.lease_policy_id !== option.lease_policy_id ||
    data.maximum_lease_seconds !== option.maximum_lease_seconds ||
    data.revocation_policy_id !== option.revocation_policy_id ||
    data.brokerage_policy_id !== option.brokerage_policy_id ||
    data.brokerage_policy_version !== option.brokerage_policy_version) {
    throw new Error("Secret brokerage authorization does not match the exact governed evidence");
  }
  return { data };
}
