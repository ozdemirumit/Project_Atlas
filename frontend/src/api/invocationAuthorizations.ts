import { apiFetch } from "./client";
import type { ConnectorTargetSessionVerification } from "./targetSessionVerifications";

export type ConnectorInvocationAuthorization = {
  authorization_id: string;
  schema_version: "atlas.connector-invocation-authorization.v1";
  version: 1;
  source_target_session_verification_id: string;
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
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
  invocation_profile_id: string;
  invocation_profile_digest: string;
  input_envelope_id: string;
  input_envelope_digest: string;
  input_envelope_schema: string;
  normalized_input_digest: string;
  input_schema_digest: string;
  output_schema_digest: string;
  result_policy_digest: string;
  maximum_timeout_seconds: number;
  maximum_output_bytes: number;
  authorization_policy_id: string;
  authorization_policy_digest: string;
  authorization_policy_version: string;
  instance_state: "enabled_capability_invocation_governed";
  authorized_by: string;
  purpose: string;
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
  reused: boolean;
};

function isSafeAuthorization(
  value: unknown,
): value is { data: ConnectorInvocationAuthorization } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "raw_input",
    "input_values",
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
    "raw_vendor_output",
    "request_fingerprint",
    "idempotency_key",
    "command",
  ];
  return (
    record.schema_version === "atlas.connector-invocation-authorization.v1" &&
    record.version === 1 &&
    typeof record.authorization_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_capability_invocation_governed" &&
    (record.capability_class === "C0" || record.capability_class === "C1") &&
    record.target_session_verified === true &&
    record.capability_enabled === true &&
    record.capability_permission_verified === true &&
    record.capability_invocation_authorized === true &&
    record.eligible_for_bounded_capability_invocation === true &&
    record.single_use === true &&
    record.renewable === false &&
    record.consumed === false &&
    record.target_connected === false &&
    record.capability_invoked === false &&
    record.scheduled === false &&
    record.result_received === false &&
    record.result_validated === false &&
    record.evidence_ingested === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbidden.every((field) => !(field in record))
  );
}

export async function createConnectorInvocationAuthorization(input: {
  targetSession: ConnectorTargetSessionVerification;
  capabilityId: string;
  profileId: string;
  profileDigest: string;
  envelopeId: string;
  envelopeDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const {
    targetSession,
    capabilityId,
    profileId,
    profileDigest,
    envelopeId,
    envelopeDigest,
    policyId,
    policyDigest,
    purpose,
  } = input;
  if (
    !targetSession.eligible_for_capability_invocation_governance ||
    targetSession.target_connected ||
    targetSession.capability_invocation_authorized ||
    targetSession.instance_state !== "enabled_target_session_verified"
  )
    throw new Error("A current closed target-session verification is required");
  const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
  const digest = /^[a-f0-9]{64}$/;
  if (
    !stableId.test(capabilityId) ||
    !stableId.test(profileId) ||
    !digest.test(profileDigest) ||
    !stableId.test(envelopeId) ||
    !digest.test(envelopeDigest) ||
    !stableId.test(policyId) ||
    !digest.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("Exact signed invocation authorization evidence is required");
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
      source_target_session_digest: targetSession.canonical_digest,
      package_digest: targetSession.package_digest,
      capability_id: capabilityId,
      invocation_profile_id: profileId,
      invocation_profile_digest: profileDigest,
      input_envelope_id: envelopeId,
      input_envelope_digest: envelopeDigest,
      authorization_policy_id: policyId,
      authorization_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment:
        true,
    }),
  });
  if (!response.ok)
    throw new Error(`Invocation authorization failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeAuthorization(payload))
    throw new Error("Invocation authorization returned unsafe evidence");
  if (
    payload.data.source_target_session_verification_id !== targetSession.verification_id ||
    payload.data.source_target_session_digest !== targetSession.canonical_digest ||
    payload.data.package_digest !== targetSession.package_digest ||
    payload.data.instance_id !== targetSession.instance_id ||
    payload.data.capability_id !== capabilityId ||
    payload.data.invocation_profile_id !== profileId ||
    payload.data.invocation_profile_digest !== profileDigest ||
    payload.data.input_envelope_id !== envelopeId ||
    payload.data.input_envelope_digest !== envelopeDigest ||
    payload.data.authorization_policy_id !== policyId ||
    payload.data.authorization_policy_digest !== policyDigest
  )
    throw new Error("Invocation authorization does not match the exact governed evidence");
  return payload;
}
