import { apiFetch } from "./client";
import type { ConnectorRuntimeActivation } from "./runtimeActivations";

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
  connectivity_check_results: Array<{ check_id: string; outcome: "connectivity.passed" }>;
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

function isSafeVerification(value: unknown): value is { data: ConnectorTargetSessionVerification } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-target-session-verification.v1" &&
    record.version === 1 &&
    typeof record.verification_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_target_session_verified" &&
    record.runtime_health_verified === true &&
    record.secret_brokerage_governed === true &&
    record.target_connection_authorized === true &&
    record.target_connectivity_verified === true &&
    record.target_identity_verified === true &&
    record.read_only_session_verified === true &&
    record.target_session_established === true &&
    record.target_session_closed === true &&
    record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.eligible_for_capability_invocation_governance === true &&
    record.target_connected === false &&
    record.capability_invocation_authorized === false &&
    record.capability_invoked === false &&
    record.scheduled === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !(
      "target_address" in record ||
      "target_endpoint" in record ||
      "target_port" in record ||
      "credential_profile_id" in record ||
      "secret_reference_id" in record ||
      "secret_store_profile_id" in record ||
      "broker_id" in record ||
      "lease_handle" in record ||
      "session_handle" in record ||
      "certificate_body" in record ||
      "raw_vendor_output" in record ||
      "transcript" in record ||
      "request_fingerprint" in record ||
      "idempotency_key" in record
    )
  );
}

export async function createConnectorTargetSessionVerification(input: {
  activation: ConnectorRuntimeActivation;
  profileId: string;
  profileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { activation, profileId, profileDigest, policyId, policyDigest, purpose } = input;
  if (
    !activation.runtime_health_verified ||
    !activation.eligible_for_target_session_authorization ||
    activation.target_connected ||
    activation.target_connection_authorized ||
    activation.instance_state !== "enabled_runtime_healthy"
  ) throw new Error("A current healthy runtime activation is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) ||
    !/^[a-f0-9]{64}$/.test(profileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed target-session profile and policy are required");
  const response = await apiFetch("/api/v1/connectors/target-session-verifications", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-target-session.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-target-session-input.v1",
      source_runtime_activation_id: activation.activation_id,
      source_runtime_activation_digest: activation.canonical_digest,
      package_digest: activation.package_digest,
      session_profile_id: profileId,
      session_profile_digest: profileDigest,
      session_policy_id: policyId,
      session_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_bounded_session_grants_no_invocation_execution_or_deployment: true,
    }),
  });
  if (!response.ok) throw new Error(`Target session verification failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeVerification(payload)) throw new Error("Target session returned unsafe evidence");
  if (
    payload.data.source_runtime_activation_id !== activation.activation_id ||
    payload.data.source_runtime_activation_digest !== activation.canonical_digest ||
    payload.data.package_digest !== activation.package_digest ||
    payload.data.instance_id !== activation.instance_id ||
    payload.data.session_profile_id !== profileId ||
    payload.data.session_profile_digest !== profileDigest ||
    payload.data.session_policy_id !== policyId ||
    payload.data.session_policy_digest !== policyDigest
  ) throw new Error("Target session does not match the exact governed evidence");
  return payload;
}
