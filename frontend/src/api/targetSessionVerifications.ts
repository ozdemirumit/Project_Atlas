import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorRuntimeActivationInventoryItem } from "./runtimeActivations";

export type TargetConnectivityCheckEvidence = {
  check_id: string;
  outcome: "connectivity.passed";
};

export type ConnectorTargetSessionVerificationInventoryItem = {
  verification_id: string;
  schema_version: "atlas.connector-target-session-verification.v1";
  version: 1;
  source_runtime_activation_id: string;
  target_identity_digest: string;
  protocol_classification: string;
  tls_classification: string;
  session_profile_digest: string;
  session_policy_digest: string;
  connectivity_check_results: TargetConnectivityCheckEvidence[];
  instance_state: "enabled_target_session_verified";
  verified_at: string;
  canonical_digest: string;
  runtime_health_verified: true;
  secret_brokerage_governed: true;
  target_connection_authorized: true;
  target_connectivity_verified: true;
  target_identity_verified: true;
  read_only_session_verified: true;
  target_session_established: true;
  target_session_closed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_capability_invocation_governance: true;
  target_connected: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  scheduled: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorTargetSessionVerificationOption = {
  source_runtime_activation_id: string;
  source_runtime_activation_digest: string;
  package_digest: string;
  session_profile_id: string;
  session_profile_digest: string;
  session_profile_expires_at: string;
  session_policy_id: string;
  session_policy_digest: string;
  session_policy_version: string;
  session_policy_expires_at: string;
  expected_target_product: string;
  protocol_classification: string;
  connectivity_check_ids: string[];
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  resulting_instance_state: "enabled_target_session_verified";
  target_connection_authorized: true;
  target_connectivity_verified: true;
  target_identity_verified: true;
  read_only_session_verified: true;
  target_session_closed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_capability_invocation_governance: true;
  target_connected: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

// Later invocation-governance code still consumes the original internal response contract.
export type ConnectorTargetSessionVerification = {
  verification_id: string;
  schema_version: "atlas.connector-target-session-verification.v1";
  version: 1;
  source_runtime_activation_id: string;
  source_runtime_activation_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  target_profile_digest: string;
  target_identity_digest: string;
  expected_target_product: string;
  protocol_classification: string;
  tls_classification: string;
  session_profile_id: string;
  session_profile_digest: string;
  session_policy_id: string;
  session_policy_digest: string;
  session_policy_version: string;
  session_adapter_id: string;
  connectivity_check_results: TargetConnectivityCheckEvidence[];
  instance_state: "enabled_target_session_verified";
  verified_by: string;
  purpose: string;
  verified_at: string;
  canonical_digest: string;
  runtime_health_verified: true;
  secret_brokerage_governed: true;
  target_connection_authorized: true;
  target_connectivity_verified: true;
  target_identity_verified: true;
  read_only_session_verified: true;
  target_session_established: true;
  target_session_closed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  eligible_for_capability_invocation_governance: true;
  target_connected: false;
  capability_invocation_authorized: false;
  capability_invoked: false;
  scheduled: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const inventoryFields = new Set([
  "verification_id", "schema_version", "version", "source_runtime_activation_id",
  "target_identity_digest", "protocol_classification", "tls_classification",
  "session_profile_digest", "session_policy_digest", "connectivity_check_results",
  "instance_state", "verified_at",
  "canonical_digest", "runtime_health_verified", "secret_brokerage_governed",
  "target_connection_authorized", "target_connectivity_verified", "target_identity_verified",
  "read_only_session_verified", "target_session_established", "target_session_closed",
  "delivery_channel_closed", "lease_revocation_confirmed",
  "eligible_for_capability_invocation_governance", "target_connected",
  "capability_invocation_authorized", "capability_invoked", "scheduled", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed",
]);
const optionFields = new Set([
  "source_runtime_activation_id", "source_runtime_activation_digest", "package_digest",
  "session_profile_id", "session_profile_digest", "session_profile_expires_at",
  "session_policy_id", "session_policy_digest", "session_policy_version",
  "session_policy_expires_at", "expected_target_product", "protocol_classification",
  "connectivity_check_ids", "required_assurance_level", "resulting_instance_state",
  "target_connection_authorized", "target_connectivity_verified", "target_identity_verified",
  "read_only_session_verified", "target_session_closed",
  "delivery_channel_closed", "lease_revocation_confirmed",
  "eligible_for_capability_invocation_governance", "target_connected",
  "capability_invocation_authorized", "capability_invoked", "execution_authorized",
  "deployment_approved", "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function isSafeInventoryBoundary(record: Record<string, unknown>): boolean {
  return record.runtime_health_verified === true && record.secret_brokerage_governed === true &&
    record.target_connection_authorized === true &&
    record.target_connectivity_verified === true && record.target_identity_verified === true &&
    record.read_only_session_verified === true && record.target_session_established === true &&
    record.target_session_closed === true && record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.eligible_for_capability_invocation_governance === true &&
    record.target_connected === false && record.capability_invocation_authorized === false &&
    record.capability_invoked === false && record.scheduled === false &&
    record.execution_authorized === false && record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false;
}

function isSafeOptionBoundary(record: Record<string, unknown>): boolean {
  return record.target_connection_authorized === true &&
    record.target_connectivity_verified === true && record.target_identity_verified === true &&
    record.read_only_session_verified === true && record.target_session_closed === true &&
    record.delivery_channel_closed === true && record.lease_revocation_confirmed === true &&
    record.eligible_for_capability_invocation_governance === true &&
    record.target_connected === false && record.capability_invocation_authorized === false &&
    record.capability_invoked === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isConnectivityCheck(value: unknown): value is TargetConnectivityCheckEvidence {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, new Set(["check_id", "outcome"])) &&
    typeof record.check_id === "string" && stableId.test(record.check_id) &&
    record.outcome === "connectivity.passed";
}

function isInventoryItem(value: unknown): value is ConnectorTargetSessionVerificationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "verification_id", "source_runtime_activation_id", "protocol_classification",
    "tls_classification",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.connector-target-session-verification.v1" &&
    record.version === 1 &&
    typeof record.target_identity_digest === "string" && digest.test(record.target_identity_digest) &&
    typeof record.session_profile_digest === "string" && digest.test(record.session_profile_digest) &&
    typeof record.session_policy_digest === "string" && digest.test(record.session_policy_digest) &&
    typeof record.canonical_digest === "string" && digest.test(record.canonical_digest) &&
    Array.isArray(record.connectivity_check_results) &&
    record.connectivity_check_results.length > 0 && record.connectivity_check_results.length <= 32 &&
    record.connectivity_check_results.every(isConnectivityCheck) &&
    record.instance_state === "enabled_target_session_verified" &&
    isTimestamp(record.verified_at) && isSafeInventoryBoundary(record);
}

function isOption(value: unknown): value is ConnectorTargetSessionVerificationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_runtime_activation_id", "session_profile_id", "session_policy_id",
    "session_policy_version", "protocol_classification",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_runtime_activation_digest", "package_digest", "session_profile_digest",
    "session_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    isTimestamp(record.session_profile_expires_at) && isTimestamp(record.session_policy_expires_at) &&
    typeof record.expected_target_product === "string" &&
    record.expected_target_product.trim().length > 0 && record.expected_target_product.length <= 160 &&
    Array.isArray(record.connectivity_check_ids) && record.connectivity_check_ids.length > 0 &&
    record.connectivity_check_ids.length <= 32 &&
    record.connectivity_check_ids.every((check) => typeof check === "string" && stableId.test(check)) &&
    typeof record.required_assurance_level === "string" &&
    ["single_factor", "multi_factor", "hardware_backed"].includes(
      record.required_assurance_level,
    ) && record.resulting_instance_state === "enabled_target_session_verified" &&
    isSafeOptionBoundary(record);
}

export async function getConnectorTargetSessionVerifications(input?: {
  sourceRuntimeActivationId?: string;
}): Promise<ConnectorTargetSessionVerificationInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceRuntimeActivationId) {
    parameters.set("source_runtime_activation_id", input.sourceRuntimeActivationId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/target-session-verifications${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Target session verification inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Target session verification inventory returned unsafe records");
  }
  const verifications: ConnectorTargetSessionVerificationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Target session verification inventory returned unsafe records");
    }
    if (input?.sourceRuntimeActivationId &&
      candidate.source_runtime_activation_id !== input.sourceRuntimeActivationId) {
      throw new Error("Target session verification inventory crossed the requested runtime scope");
    }
    verifications.push(candidate);
  }
  return verifications;
}

export async function getConnectorTargetSessionVerificationOptions(
  sourceRuntimeActivationId: string,
): Promise<ConnectorTargetSessionVerificationOption[]> {
  const parameters = new URLSearchParams({ source_runtime_activation_id: sourceRuntimeActivationId });
  const response = await apiFetch(
    `/api/v1/connectors/target-session-verifications/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Target session verification options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Target session verification options returned unsafe evidence");
  }
  const options: ConnectorTargetSessionVerificationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) ||
      candidate.source_runtime_activation_id !== sourceRuntimeActivationId) {
      throw new Error("Target session verification options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorTargetSessionVerification(input: {
  activation: ConnectorRuntimeActivationInventoryItem;
  option: ConnectorTargetSessionVerificationOption;
  purpose: string;
}) {
  const { activation, option, purpose } = input;
  if (!activation.runtime_health_verified ||
    !activation.eligible_for_target_session_authorization || activation.target_connected ||
    activation.target_connection_authorized ||
    activation.instance_state !== "enabled_runtime_healthy" ||
    option.source_runtime_activation_id !== activation.activation_id) {
    throw new Error("A current healthy runtime activation is required");
  }
  if (!digest.test(option.source_runtime_activation_digest) ||
    !digest.test(option.package_digest) || !stableId.test(option.session_profile_id) ||
    !digest.test(option.session_profile_digest) || !stableId.test(option.session_policy_id) ||
    !digest.test(option.session_policy_digest) || purpose.trim().length < 20 ||
    purpose.length > 1000) {
    throw new Error("Exact signed target-session profile and policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/target-session-verifications", {
    method: "POST",
    headers: {
      Accept: "application/json", "Content-Type": "application/json",
      "Idempotency-Key": `connector-target-session.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-target-session-input.v1",
      source_runtime_activation_id: activation.activation_id,
      source_runtime_activation_digest: option.source_runtime_activation_digest,
      package_digest: option.package_digest,
      session_profile_id: option.session_profile_id,
      session_profile_digest: option.session_profile_digest,
      session_policy_id: option.session_policy_id,
      session_policy_digest: option.session_policy_digest,
      purpose: purpose.trim(),
      acknowledged_bounded_session_grants_no_invocation_execution_or_deployment: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Target session verification failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!isInventoryItem(data)) throw new Error("Target session returned unsafe evidence");
  if (data.source_runtime_activation_id !== activation.activation_id ||
    data.session_profile_digest !== option.session_profile_digest ||
    data.session_policy_digest !== option.session_policy_digest ||
    data.protocol_classification !== option.protocol_classification ||
    data.connectivity_check_results.some(
      (check) => !option.connectivity_check_ids.includes(check.check_id),
    )) {
    throw new Error("Target session does not match the exact governed evidence");
  }
  return { data };
}
