import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorInvocationAuthorizationInventoryItem } from "./invocationAuthorizations";

export type ConnectorBoundedInvocationInventoryItem = {
  invocation_id: string;
  schema_version: "atlas.connector-bounded-invocation.v1";
  version: 1;
  source_authorization_id: string;
  source_authorization_digest: string;
  package_digest: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  output_schema_digest: string;
  result_policy_digest: string;
  invocation_policy_id: string;
  invocation_policy_digest: string;
  invocation_policy_version: string;
  normalized_redacted_result_digest: string;
  observation_count: number;
  output_bytes: number;
  instance_state: "enabled_bounded_capability_invocation_completed";
  started_at: string;
  completed_at: string;
  canonical_digest: string;
  authorization_consumed: true;
  target_connection_opened: true;
  capability_invoked: true;
  result_received: true;
  result_validated: true;
  result_redacted: true;
  target_session_closed: true;
  delivery_channel_closed: true;
  lease_revocation_confirmed: true;
  target_connected: false;
  reusable_session_available: false;
  scheduled: false;
  evidence_ingested: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

// Legacy evidence ingestion remains a separate later workflow and requires its internal record.
export type ConnectorBoundedInvocation = ConnectorBoundedInvocationInventoryItem & {
  instance_id: string;
  environment_id: string;
};

export type ConnectorBoundedInvocationOption = {
  source_authorization_id: string;
  source_authorization_digest: string;
  package_digest: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  invocation_policy_id: string;
  invocation_policy_digest: string;
  invocation_policy_version: string;
  invocation_policy_expires_at: string;
  required_assurance_level: "single_factor" | "multi_factor" | "hardware_backed";
  maximum_timeout_seconds: number;
  maximum_output_bytes: number;
  maximum_observations: number;
  resulting_instance_state: "enabled_bounded_capability_invocation_completed";
  irreversible_consumption_required: true;
  automatic_retry_allowed: false;
  target_connected: false;
  reusable_session_available: false;
  scheduled: false;
  evidence_ingested: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;
const inventoryFields = new Set([
  "invocation_id", "schema_version", "version", "source_authorization_id",
  "source_authorization_digest", "package_digest", "capability_id", "capability_class",
  "required_permission", "output_schema_digest", "result_policy_digest", "invocation_policy_id",
  "invocation_policy_digest", "invocation_policy_version",
  "normalized_redacted_result_digest", "observation_count", "output_bytes", "instance_state",
  "started_at", "completed_at", "canonical_digest", "authorization_consumed",
  "target_connection_opened", "capability_invoked", "result_received", "result_validated",
  "result_redacted", "target_session_closed", "delivery_channel_closed",
  "lease_revocation_confirmed", "target_connected", "reusable_session_available", "scheduled",
  "evidence_ingested", "execution_authorized", "deployment_approved",
  "infrastructure_mutation_performed", "reused",
]);
const optionFields = new Set([
  "source_authorization_id", "source_authorization_digest", "package_digest", "capability_id",
  "capability_class", "required_permission", "invocation_policy_id", "invocation_policy_digest",
  "invocation_policy_version", "invocation_policy_expires_at", "required_assurance_level",
  "maximum_timeout_seconds", "maximum_output_bytes", "maximum_observations",
  "resulting_instance_state", "irreversible_consumption_required", "automatic_retry_allowed",
  "target_connected", "reusable_session_available", "scheduled", "evidence_ingested",
  "execution_authorized", "deployment_approved", "infrastructure_mutation_performed",
]);

function hasExactFields(value: Record<string, unknown>, fields: ReadonlySet<string>): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}

function hasClosedBoundary(record: Record<string, unknown>): boolean {
  return record.authorization_consumed === true && record.target_connection_opened === true &&
    record.capability_invoked === true && record.result_received === true &&
    record.result_validated === true && record.result_redacted === true &&
    record.target_session_closed === true && record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true && record.target_connected === false &&
    record.reusable_session_available === false && record.scheduled === false &&
    record.evidence_ingested === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function hasSafeOptionBoundary(record: Record<string, unknown>): boolean {
  return record.irreversible_consumption_required === true &&
    record.automatic_retry_allowed === false && record.target_connected === false &&
    record.reusable_session_available === false && record.scheduled === false &&
    record.evidence_ingested === false && record.execution_authorized === false &&
    record.deployment_approved === false && record.infrastructure_mutation_performed === false;
}

function isInventoryItem(value: unknown): value is ConnectorBoundedInvocationInventoryItem {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, inventoryFields) && [
    "invocation_id", "source_authorization_id", "capability_id", "required_permission",
    "invocation_policy_id", "invocation_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) &&
    record.schema_version === "atlas.connector-bounded-invocation.v1" && record.version === 1 &&
    (record.capability_class === "C0" || record.capability_class === "C1") && [
      "source_authorization_digest", "package_digest", "output_schema_digest",
      "result_policy_digest", "invocation_policy_digest",
      "normalized_redacted_result_digest", "canonical_digest",
    ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    Number.isInteger(record.observation_count) && (record.observation_count as number) >= 0 &&
    (record.observation_count as number) <= 1000 && Number.isInteger(record.output_bytes) &&
    (record.output_bytes as number) >= 0 && (record.output_bytes as number) <= 1_048_576 &&
    record.instance_state === "enabled_bounded_capability_invocation_completed" &&
    isTimestamp(record.started_at) && isTimestamp(record.completed_at) &&
    Date.parse(record.completed_at) >= Date.parse(record.started_at) &&
    typeof record.reused === "boolean" && hasClosedBoundary(record);
}

function isOption(value: unknown): value is ConnectorBoundedInvocationOption {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return hasExactFields(record, optionFields) && [
    "source_authorization_id", "capability_id", "required_permission", "invocation_policy_id",
    "invocation_policy_version",
  ].every((field) => typeof record[field] === "string" && stableId.test(record[field])) && [
    "source_authorization_digest", "package_digest", "invocation_policy_digest",
  ].every((field) => typeof record[field] === "string" && digest.test(record[field])) &&
    (record.capability_class === "C0" || record.capability_class === "C1") &&
    isTimestamp(record.invocation_policy_expires_at) &&
    (record.required_assurance_level === "single_factor" ||
      record.required_assurance_level === "multi_factor" ||
      record.required_assurance_level === "hardware_backed") &&
    Number.isInteger(record.maximum_timeout_seconds) &&
    (record.maximum_timeout_seconds as number) > 0 &&
    (record.maximum_timeout_seconds as number) <= 120 &&
    Number.isInteger(record.maximum_output_bytes) && (record.maximum_output_bytes as number) > 0 &&
    (record.maximum_output_bytes as number) <= 1_048_576 &&
    Number.isInteger(record.maximum_observations) &&
    (record.maximum_observations as number) > 0 &&
    (record.maximum_observations as number) <= 1000 &&
    record.resulting_instance_state === "enabled_bounded_capability_invocation_completed" &&
    hasSafeOptionBoundary(record);
}

export async function getConnectorBoundedInvocations(input: {
  sourceAuthorizationId: string;
}): Promise<ConnectorBoundedInvocationInventoryItem[]> {
  const sourceId = input.sourceAuthorizationId;
  if (!stableId.test(sourceId)) throw new Error("Exact invocation-authorization scope is required");
  const parameters = new URLSearchParams({ source_authorization_id: sourceId });
  const response = await apiFetch(
    `/api/v1/connectors/bounded-invocations?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Bounded invocation inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Bounded invocation inventory returned unsafe records");
  const invocations: ConnectorBoundedInvocationInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Bounded invocation inventory returned unsafe records");
    }
    if (candidate.source_authorization_id !== sourceId) {
      throw new Error("Bounded invocation inventory crossed the requested authorization scope");
    }
    invocations.push(candidate);
  }
  return invocations;
}

export async function getConnectorBoundedInvocationOptions(
  sourceAuthorizationId: string,
): Promise<ConnectorBoundedInvocationOption[]> {
  if (!stableId.test(sourceAuthorizationId)) {
    throw new Error("Exact invocation-authorization scope is required");
  }
  const parameters = new URLSearchParams({ source_authorization_id: sourceAuthorizationId });
  const response = await apiFetch(
    `/api/v1/connectors/bounded-invocations/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Bounded invocation options failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!Array.isArray(data)) throw new Error("Bounded invocation options returned unsafe evidence");
  const options: ConnectorBoundedInvocationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_authorization_id !== sourceAuthorizationId) {
      throw new Error("Bounded invocation options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorBoundedInvocation(input: {
  authorization: ConnectorInvocationAuthorizationInventoryItem;
  option: ConnectorBoundedInvocationOption;
  purpose: string;
}) {
  const { authorization, option, purpose } = input;
  if (!authorization.capability_invocation_authorized ||
    !authorization.eligible_for_bounded_capability_invocation || !authorization.single_use ||
    authorization.renewable || authorization.consumed || authorization.capability_invoked ||
    authorization.instance_state !== "enabled_capability_invocation_governed" ||
    option.source_authorization_id !== authorization.authorization_id ||
    option.source_authorization_digest !== authorization.canonical_digest ||
    option.capability_id !== authorization.capability_id ||
    option.capability_class !== authorization.capability_class || purpose.trim().length < 20 ||
    purpose.length > 1000) {
    throw new Error("Exact current bounded-invocation evidence is required");
  }
  const response = await apiFetch("/api/v1/connectors/bounded-invocations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-bounded-invocation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-bounded-invocation-input.v1",
      source_authorization_id: option.source_authorization_id,
      source_authorization_digest: option.source_authorization_digest,
      package_digest: option.package_digest,
      invocation_policy_id: option.invocation_policy_id,
      invocation_policy_digest: option.invocation_policy_digest,
      purpose: purpose.trim(),
      acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Bounded connector invocation failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data : undefined;
  if (!isInventoryItem(data)) throw new Error("Bounded invocation returned unsafe evidence");
  if (data.source_authorization_id !== authorization.authorization_id ||
    data.capability_id !== option.capability_id || data.capability_class !== option.capability_class ||
    data.required_permission !== option.required_permission ||
    data.invocation_policy_digest !== option.invocation_policy_digest) {
    throw new Error("Bounded invocation does not match the exact governed authorization");
  }
  return { data };
}
