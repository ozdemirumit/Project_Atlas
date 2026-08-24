import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorSecretBrokerageAuthorizationInventoryItem } from "./secretBrokerageAuthorizations";

export type RuntimeHealthProbeEvidence = { probe_id: string; outcome: "health.passed" };

export type ConnectorRuntimeActivationInventoryItem = {
  activation_id: string;
  source_brokerage_authorization_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
  activation_profile_id: string;
  activation_policy_id: string;
  activation_policy_version: string;
  activation_adapter_id: string;
  health_probe_results: RuntimeHealthProbeEvidence[];
  instance_state: "enabled_runtime_healthy";
  activated_by: string;
  purpose: string;
  activated_at: string;
  healthy_at: string;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  secret_brokerage_governed: true;
  credential_resolution_authorized: true;
  secret_lease_issued: true;
  credentials_resolved: true;
  runner_started: true;
  package_loaded: true;
  runtime_health_verified: true;
  lease_delivery_completed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_target_session_authorization: true;
  target_connected: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorRuntimeActivationOption = {
  source_brokerage_authorization_id: string;
  source_brokerage_authorization_digest: string;
  package_digest: string;
  activation_profile_id: string;
  activation_profile_digest: string;
  activation_profile_expires_at: string;
  health_probe_ids: string[];
  activation_policy_id: string;
  activation_policy_digest: string;
  activation_policy_version: string;
  activation_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  resulting_instance_state: "enabled_runtime_healthy";
  secret_lease_issued: true;
  credentials_resolved: true;
  runner_started: true;
  package_loaded: true;
  runtime_health_verified: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_target_session_authorization: true;
  target_connected: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

// Later target-session code still consumes the original internal response contract.
export type ConnectorRuntimeActivation = {
  activation_id: string;
  schema_version: "atlas.connector-runtime-activation.v1";
  version: 1;
  source_brokerage_authorization_id: string;
  source_brokerage_authorization_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  runtime_profile_digest: string;
  runner_identity_digest: string;
  image_digest: string;
  workload_identity_digest: string;
  activation_profile_id: string;
  activation_profile_digest: string;
  activation_policy_id: string;
  activation_policy_digest: string;
  activation_policy_version: string;
  activation_adapter_id: string;
  health_probe_results: RuntimeHealthProbeEvidence[];
  instance_state: "enabled_runtime_healthy";
  activated_by: string;
  purpose: string;
  activated_at: string;
  healthy_at: string;
  canonical_digest: string;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  secret_brokerage_governed: true;
  credential_resolution_authorized: true;
  secret_lease_issued: true;
  credentials_resolved: true;
  runner_started: true;
  package_loaded: true;
  runtime_health_verified: true;
  lease_delivery_completed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_target_session_authorization: true;
  target_connected: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const inventoryFields = new Set([
  "activation_id", "source_brokerage_authorization_id", "connector_id", "release_version",
  "instance_id", "display_name", "activation_profile_id", "activation_policy_id",
  "activation_policy_version", "activation_adapter_id", "health_probe_results",
  "instance_state", "activated_by", "purpose", "activated_at", "healthy_at",
  "runtime_boundary_bound", "runtime_trust_granted", "secret_brokerage_governed",
  "credential_resolution_authorized", "secret_lease_issued", "credentials_resolved",
  "runner_started", "package_loaded", "runtime_health_verified", "lease_delivery_completed",
  "delivery_channel_closed", "lease_revocation_confirmed",
  "eligible_for_target_session_authorization", "target_connected",
  "target_connection_authorized", "capability_invocation_authorized", "capability_invoked",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);
const optionFields = new Set([
  "source_brokerage_authorization_id", "source_brokerage_authorization_digest", "package_digest",
  "activation_profile_id", "activation_profile_digest", "activation_profile_expires_at",
  "health_probe_ids",
  "activation_policy_id", "activation_policy_digest", "activation_policy_version",
  "activation_policy_expires_at", "required_assurance_level",
  "resulting_instance_state", "secret_lease_issued", "credentials_resolved", "runner_started",
  "package_loaded", "runtime_health_verified", "delivery_channel_closed",
  "lease_revocation_confirmed", "eligible_for_target_session_authorization", "target_connected",
  "target_connection_authorized", "capability_invocation_authorized", "capability_invoked",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function hasSafeResult(record: Record<string, unknown>): boolean {
  return record.secret_lease_issued === true && record.credentials_resolved === true &&
    record.runner_started === true && record.package_loaded === true &&
    record.runtime_health_verified === true && record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.eligible_for_target_session_authorization === true && record.target_connected === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false && record.capability_invoked === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function hasSafeOptionResult(record: Record<string, unknown>): boolean {
  return record.secret_lease_issued === true && record.credentials_resolved === true &&
    record.runner_started === true && record.package_loaded === true &&
    record.runtime_health_verified === true && record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.eligible_for_target_session_authorization === true &&
    record.target_connected === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false && record.capability_invoked === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isProbe(value: unknown): value is RuntimeHealthProbeEvidence {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, new Set(["probe_id", "outcome"])) &&
    typeof record.probe_id === "string" && stableId.test(record.probe_id) &&
    record.outcome === "health.passed";
}

function isInventoryItem(value: unknown): value is ConnectorRuntimeActivationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "activation_id", "source_brokerage_authorization_id", "connector_id", "release_version",
    "instance_id", "activation_profile_id", "activation_policy_id", "activation_policy_version",
    "activation_adapter_id", "activated_by",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    typeof record.display_name === "string" && record.display_name.length <= 120 &&
    Array.isArray(record.health_probe_results) && record.health_probe_results.length > 0 &&
    record.health_probe_results.length <= 32 && record.health_probe_results.every(isProbe) &&
    record.instance_state === "enabled_runtime_healthy" &&
    typeof record.purpose === "string" && record.purpose.trim().length >= 20 &&
    record.purpose.length <= 1000 && isTimestamp(record.activated_at) &&
    isTimestamp(record.healthy_at) && record.runtime_boundary_bound === true &&
    record.runtime_trust_granted === true && record.secret_brokerage_governed === true &&
    record.credential_resolution_authorized === true && record.lease_delivery_completed === true &&
    hasSafeResult(record);
}

function isOption(value: unknown): value is ConnectorRuntimeActivationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_brokerage_authorization_id", "activation_profile_id", "activation_policy_id",
    "activation_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_brokerage_authorization_digest", "package_digest", "activation_profile_digest",
    "activation_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    isTimestamp(record.activation_profile_expires_at) && isTimestamp(record.activation_policy_expires_at) &&
    typeof record.required_assurance_level === "string" &&
    ["single_factor", "multi_factor", "hardware_backed"].includes(record.required_assurance_level) &&
    Array.isArray(record.health_probe_ids) && record.health_probe_ids.length > 0 &&
    record.health_probe_ids.length <= 32 &&
    record.health_probe_ids.every((probe) => typeof probe === "string" && stableId.test(probe)) &&
    record.resulting_instance_state === "enabled_runtime_healthy" && hasSafeOptionResult(record);
}

export async function getConnectorRuntimeActivations(input?: {
  sourceBrokerageAuthorizationId?: string;
}): Promise<ConnectorRuntimeActivationInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceBrokerageAuthorizationId) {
    parameters.set("source_brokerage_authorization_id", input.sourceBrokerageAuthorizationId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/runtime-activations${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Runtime activation inventory failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Runtime activation inventory returned unsafe records");
  const activations: ConnectorRuntimeActivationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) throw new Error("Runtime activation inventory returned unsafe records");
    if (input?.sourceBrokerageAuthorizationId &&
      candidate.source_brokerage_authorization_id !== input.sourceBrokerageAuthorizationId) {
      throw new Error("Runtime activation inventory crossed the requested brokerage scope");
    }
    activations.push(candidate);
  }
  return activations;
}

export async function getConnectorRuntimeActivationOptions(
  sourceBrokerageAuthorizationId: string,
): Promise<ConnectorRuntimeActivationOption[]> {
  const parameters = new URLSearchParams({ source_brokerage_authorization_id: sourceBrokerageAuthorizationId });
  const response = await apiFetch(`/api/v1/connectors/runtime-activations/options?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Runtime activation options failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Runtime activation options returned unsafe evidence");
  const options: ConnectorRuntimeActivationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_brokerage_authorization_id !== sourceBrokerageAuthorizationId) {
      throw new Error("Runtime activation options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorRuntimeActivation(input: {
  brokerage: ConnectorSecretBrokerageAuthorizationInventoryItem;
  option: ConnectorRuntimeActivationOption;
  purpose: string;
}) {
  const { brokerage, option, purpose } = input;
  if (!brokerage.secret_brokerage_governed || !brokerage.eligible_for_runtime_activation ||
    brokerage.secret_lease_issued || brokerage.instance_state !== "enabled_secret_brokerage_governed" ||
    option.source_brokerage_authorization_id !== brokerage.authorization_id) {
    throw new Error("A current secret-brokerage authorization is required");
  }
  if (!digest.test(option.source_brokerage_authorization_digest) || !digest.test(option.package_digest) ||
    !stableId.test(option.activation_profile_id) || !digest.test(option.activation_profile_digest) ||
    !stableId.test(option.activation_policy_id) || !digest.test(option.activation_policy_digest) ||
    purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact signed activation profile and policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/runtime-activations", {
    method: "POST",
    headers: {
      Accept: "application/json", "Content-Type": "application/json",
      "Idempotency-Key": `connector-runtime-activation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-runtime-activation-input.v1",
      source_brokerage_authorization_id: brokerage.authorization_id,
      source_brokerage_authorization_digest: option.source_brokerage_authorization_digest,
      package_digest: option.package_digest,
      activation_profile_id: option.activation_profile_id,
      activation_profile_digest: option.activation_profile_digest,
      activation_policy_id: option.activation_policy_id,
      activation_policy_digest: option.activation_policy_digest,
      purpose: purpose.trim(),
      acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Runtime activation failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!isInventoryItem(data)) throw new Error("Runtime activation returned unsafe evidence");
  if (data.source_brokerage_authorization_id !== brokerage.authorization_id ||
    data.connector_id !== brokerage.connector_id || data.release_version !== brokerage.release_version ||
    data.instance_id !== brokerage.instance_id || data.activation_profile_id !== option.activation_profile_id ||
    data.activation_policy_id !== option.activation_policy_id ||
    data.activation_policy_version !== option.activation_policy_version ||
    data.health_probe_results.some((probe) => !option.health_probe_ids.includes(probe.probe_id))) {
    throw new Error("Runtime activation does not match the exact governed evidence");
  }
  return { data };
}
