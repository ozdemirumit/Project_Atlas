import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorTargetSessionVerificationInventoryItem } from "./targetSessionVerifications";

export type ConnectorInvocationAuthorizationInventoryItem = {
  authorization_id: string;
  schema_version: "atlas.connector-invocation-authorization.v1";
  version: 1;
  source_target_session_verification_id: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  invocation_profile_digest: string;
  input_envelope_digest: string;
  authorization_policy_digest: string;
  instance_state: "enabled_capability_invocation_governed";
  authorized_at: string;
  expires_at: string;
  canonical_digest: string;
  target_session_verified: true;
  capability_enabled: true;
  capability_permission_verified: true;
  capability_invocation_authorized: true;
  eligible_for_bounded_capability_invocation: true;
  single_use: true;
  renewable: false;
  consumed: false;
  target_connected: false;
  capability_invoked: false;
  scheduled: false;
  result_received: false;
  result_validated: false;
  evidence_ingested: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorInvocationAuthorizationOption = {
  source_target_session_verification_id: string;
  source_target_session_digest: string;
  package_digest: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  invocation_profile_id: string;
  invocation_profile_digest: string;
  invocation_profile_expires_at: string;
  input_envelope_id: string;
  input_envelope_digest: string;
  input_envelope_expires_at: string;
  input_envelope_field_count: number;
  authorization_policy_id: string;
  authorization_policy_digest: string;
  authorization_policy_version: string;
  authorization_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  maximum_timeout_seconds: number;
  maximum_output_bytes: number;
  resulting_instance_state: "enabled_capability_invocation_governed";
  capability_invocation_authorized: true;
  eligible_for_bounded_capability_invocation: true;
  single_use: true;
  renewable: false;
  consumed: false;
  target_connected: false;
  capability_invoked: false;
  scheduled: false;
  result_received: false;
  result_validated: false;
  evidence_ingested: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

// Kept for the later bounded-invocation slice, which still consumes the internal contract.
export type ConnectorInvocationAuthorization = ConnectorInvocationAuthorizationInventoryItem & {
  source_target_session_digest: string;
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
  required_permission: string;
  invocation_profile_id: string;
  input_envelope_id: string;
  input_envelope_schema: string;
  normalized_input_digest: string;
  input_schema_digest: string;
  output_schema_digest: string;
  result_policy_digest: string;
  maximum_timeout_seconds: number;
  maximum_output_bytes: number;
  authorization_policy_id: string;
  authorization_policy_version: string;
  authorized_by: string;
  purpose: string;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const inventoryFields = new Set([
  "authorization_id", "schema_version", "version",
  "source_target_session_verification_id", "capability_id", "capability_class",
  "invocation_profile_digest", "input_envelope_digest", "authorization_policy_digest",
  "instance_state", "authorized_at", "expires_at", "canonical_digest",
  "target_session_verified", "capability_enabled", "capability_permission_verified",
  "capability_invocation_authorized", "eligible_for_bounded_capability_invocation",
  "single_use", "renewable", "consumed", "target_connected", "capability_invoked",
  "scheduled", "result_received", "result_validated", "evidence_ingested",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);
const optionFields = new Set([
  "source_target_session_verification_id", "source_target_session_digest", "package_digest",
  "capability_id", "capability_class", "required_permission", "invocation_profile_id",
  "invocation_profile_digest", "invocation_profile_expires_at", "input_envelope_id",
  "input_envelope_digest", "input_envelope_expires_at", "input_envelope_field_count",
  "authorization_policy_id", "authorization_policy_digest", "authorization_policy_version",
  "authorization_policy_expires_at", "required_assurance_level", "maximum_timeout_seconds",
  "maximum_output_bytes", "resulting_instance_state", "capability_invocation_authorized",
  "eligible_for_bounded_capability_invocation", "single_use", "renewable", "consumed",
  "target_connected", "capability_invoked", "scheduled", "result_received", "result_validated",
  "evidence_ingested", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function hasSafeInventoryBoundary(record: Record<string, unknown>): boolean {
  return record.target_session_verified === true && record.capability_enabled === true &&
    record.capability_permission_verified === true &&
    record.capability_invocation_authorized === true &&
    record.eligible_for_bounded_capability_invocation === true && record.single_use === true &&
    record.renewable === false && record.consumed === false && record.target_connected === false &&
    record.capability_invoked === false && record.scheduled === false &&
    record.result_received === false && record.result_validated === false &&
    record.evidence_ingested === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function hasSafeOptionBoundary(record: Record<string, unknown>): boolean {
  return record.capability_invocation_authorized === true &&
    record.eligible_for_bounded_capability_invocation === true && record.single_use === true &&
    record.renewable === false && record.consumed === false && record.target_connected === false &&
    record.capability_invoked === false && record.scheduled === false &&
    record.result_received === false && record.result_validated === false &&
    record.evidence_ingested === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is ConnectorInvocationAuthorizationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "authorization_id", "source_target_session_verification_id", "capability_id",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.connector-invocation-authorization.v1" &&
    record.version === 1 && (record.capability_class === "C0" || record.capability_class === "C1") &&
    ["invocation_profile_digest", "input_envelope_digest", "authorization_policy_digest",
      "canonical_digest"].every(
      (field) => typeof record[field] === "string" && digest.test(record[field]),
    ) && record.instance_state === "enabled_capability_invocation_governed" &&
    isTimestamp(record.authorized_at) && isTimestamp(record.expires_at) &&
    hasSafeInventoryBoundary(record);
}

function isOption(value: unknown): value is ConnectorInvocationAuthorizationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_target_session_verification_id", "capability_id", "required_permission",
    "invocation_profile_id", "input_envelope_id", "authorization_policy_id",
    "authorization_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_target_session_digest", "package_digest", "invocation_profile_digest",
    "input_envelope_digest", "authorization_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    (record.capability_class === "C0" || record.capability_class === "C1") &&
    isTimestamp(record.invocation_profile_expires_at) &&
    isTimestamp(record.input_envelope_expires_at) &&
    isTimestamp(record.authorization_policy_expires_at) &&
    Number.isInteger(record.input_envelope_field_count) &&
    (record.input_envelope_field_count as number) >= 0 &&
    (record.input_envelope_field_count as number) <= 64 &&
    Number.isInteger(record.maximum_timeout_seconds) &&
    (record.maximum_timeout_seconds as number) > 0 &&
    (record.maximum_timeout_seconds as number) <= 120 &&
    Number.isInteger(record.maximum_output_bytes) &&
    (record.maximum_output_bytes as number) > 0 &&
    (record.maximum_output_bytes as number) <= 1_048_576 &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    record.resulting_instance_state === "enabled_capability_invocation_governed" &&
    hasSafeOptionBoundary(record);
}

export async function getConnectorInvocationAuthorizations(input: {
  sourceTargetSessionVerificationId: string;
}): Promise<ConnectorInvocationAuthorizationInventoryItem[]> {
  const sourceId = input.sourceTargetSessionVerificationId;
  if (!stableId.test(sourceId)) throw new Error("Exact target-session scope is required");
  const parameters = new URLSearchParams({ source_target_session_verification_id: sourceId });
  const response = await apiFetch(
    `/api/v1/connectors/invocation-authorizations?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Invocation authorization inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Invocation authorization inventory returned unsafe records");
  }
  const authorizations: ConnectorInvocationAuthorizationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Invocation authorization inventory returned unsafe records");
    }
    if (candidate.source_target_session_verification_id !== sourceId) {
      throw new Error("Invocation authorization inventory crossed the requested target-session scope");
    }
    authorizations.push(candidate);
  }
  return authorizations;
}

export async function getConnectorInvocationAuthorizationOptions(
  sourceTargetSessionVerificationId: string,
): Promise<ConnectorInvocationAuthorizationOption[]> {
  if (!stableId.test(sourceTargetSessionVerificationId)) {
    throw new Error("Exact target-session scope is required");
  }
  const parameters = new URLSearchParams({
    source_target_session_verification_id: sourceTargetSessionVerificationId,
  });
  const response = await apiFetch(
    `/api/v1/connectors/invocation-authorizations/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Invocation authorization options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Invocation authorization options returned unsafe evidence");
  }
  const options: ConnectorInvocationAuthorizationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) ||
      candidate.source_target_session_verification_id !== sourceTargetSessionVerificationId) {
      throw new Error("Invocation authorization options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorInvocationAuthorization(input: {
  targetSession: ConnectorTargetSessionVerificationInventoryItem;
  option: ConnectorInvocationAuthorizationOption;
  purpose: string;
}) {
  const { targetSession, option, purpose } = input;
  if (!targetSession.eligible_for_capability_invocation_governance ||
    targetSession.target_connected || targetSession.capability_invocation_authorized ||
    targetSession.instance_state !== "enabled_target_session_verified" ||
    option.source_target_session_verification_id !== targetSession.verification_id ||
    option.source_target_session_digest !== targetSession.canonical_digest ||
    purpose.trim().length < 20 || purpose.length > 1000) {
    throw new Error("Exact current target-session authorization evidence is required");
  }
  const response = await apiFetch("/api/v1/connectors/invocation-authorizations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-invocation-authorization.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-invocation-authorization-input.v1",
      source_target_session_verification_id: targetSession.verification_id,
      source_target_session_digest: option.source_target_session_digest,
      package_digest: option.package_digest,
      capability_id: option.capability_id,
      invocation_profile_id: option.invocation_profile_id,
      invocation_profile_digest: option.invocation_profile_digest,
      input_envelope_id: option.input_envelope_id,
      input_envelope_digest: option.input_envelope_digest,
      authorization_policy_id: option.authorization_policy_id,
      authorization_policy_digest: option.authorization_policy_digest,
      purpose: purpose.trim(),
      acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment:
        true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Invocation authorization failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!isInventoryItem(data)) {
    throw new Error("Invocation authorization returned unsafe evidence");
  }
  if (data.source_target_session_verification_id !== targetSession.verification_id ||
    data.capability_id !== option.capability_id || data.capability_class !== option.capability_class ||
    data.invocation_profile_digest !== option.invocation_profile_digest ||
    data.input_envelope_digest !== option.input_envelope_digest ||
    data.authorization_policy_digest !== option.authorization_policy_digest) {
    throw new Error("Invocation authorization does not match the exact governed evidence");
  }
  return { data };
}
