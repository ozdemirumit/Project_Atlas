import { apiFetch } from "./client";
import type { ConnectorInvocationAuthorization } from "./invocationAuthorizations";

export type ConnectorBoundedInvocation = {
  invocation_id: string;
  schema_version: "atlas.connector-bounded-invocation.v1";
  version: 1;
  consumption_claim_id: string;
  source_authorization_id: string;
  source_authorization_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  invocation_profile_id: string;
  invocation_profile_digest: string;
  input_envelope_id: string;
  input_envelope_digest: string;
  input_schema_digest: string;
  output_schema_digest: string;
  result_policy_digest: string;
  invocation_policy_id: string;
  invocation_policy_digest: string;
  invocation_policy_version: string;
  invocation_adapter_id: string;
  normalized_redacted_result_digest: string;
  observation_count: number;
  output_bytes: number;
  instance_state: "enabled_bounded_capability_invocation_completed";
  invoked_by: string;
  purpose: string;
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

function isSafeBoundedInvocation(
  value: unknown,
): value is { data: ConnectorBoundedInvocation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "raw_input",
    "input_values",
    "raw_output",
    "raw_parameters",
    "target_address",
    "target_endpoint",
    "target_port",
    "credential_profile_id",
    "secret_reference_id",
    "secret_store_profile_id",
    "broker_id",
    "lease_handle",
    "session_handle",
    "request_binding_digest",
    "idempotency_digest",
    "idempotency_key",
    "command",
  ];
  return (
    record.schema_version === "atlas.connector-bounded-invocation.v1" &&
    record.version === 1 &&
    typeof record.invocation_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_bounded_capability_invocation_completed" &&
    record.authorization_consumed === true &&
    record.target_connection_opened === true &&
    record.capability_invoked === true &&
    record.result_received === true &&
    record.result_validated === true &&
    record.result_redacted === true &&
    record.target_session_closed === true &&
    record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.target_connected === false &&
    record.reusable_session_available === false &&
    record.scheduled === false &&
    record.evidence_ingested === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbidden.every((field) => !(field in record))
  );
}

export async function createConnectorBoundedInvocation(input: {
  authorization: ConnectorInvocationAuthorization;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { authorization, policyId, policyDigest, purpose } = input;
  if (
    !authorization.capability_invocation_authorized ||
    !authorization.eligible_for_bounded_capability_invocation ||
    !authorization.single_use ||
    authorization.renewable ||
    authorization.consumed ||
    authorization.capability_invoked ||
    authorization.instance_state !== "enabled_capability_invocation_governed"
  )
    throw new Error("A current unconsumed invocation authorization is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed bounded-invocation policy is required");
  const response = await apiFetch("/api/v1/connectors/bounded-invocations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-bounded-invocation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-bounded-invocation-input.v1",
      source_authorization_id: authorization.authorization_id,
      source_authorization_digest: authorization.canonical_digest,
      package_digest: authorization.package_digest,
      invocation_policy_id: policyId,
      invocation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Bounded connector invocation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeBoundedInvocation(payload))
    throw new Error("Bounded invocation returned unsafe evidence");
  if (
    payload.data.source_authorization_id !== authorization.authorization_id ||
    payload.data.source_authorization_digest !== authorization.canonical_digest ||
    payload.data.package_digest !== authorization.package_digest ||
    payload.data.instance_id !== authorization.instance_id ||
    payload.data.capability_id !== authorization.capability_id ||
    payload.data.invocation_profile_digest !== authorization.invocation_profile_digest ||
    payload.data.input_envelope_digest !== authorization.input_envelope_digest ||
    payload.data.invocation_policy_id !== policyId ||
    payload.data.invocation_policy_digest !== policyDigest
  )
    throw new Error("Bounded invocation does not match the exact governed authorization");
  return payload;
}
