import { apiFetch } from "./client";
import type { ConnectorSecretBrokerageAuthorization } from "./secretBrokerageAuthorizations";

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
  health_probe_results: Array<{ probe_id: string; outcome: "health.passed" }>;
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

function isSafeActivation(value: unknown): value is { data: ConnectorRuntimeActivation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-runtime-activation.v1" &&
    record.version === 1 &&
    typeof record.activation_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_runtime_healthy" &&
    record.secret_lease_issued === true &&
    record.credentials_resolved === true &&
    record.runner_started === true &&
    record.package_loaded === true &&
    record.runtime_health_verified === true &&
    record.delivery_channel_closed === true &&
    record.lease_revocation_confirmed === true &&
    record.eligible_for_target_session_authorization === true &&
    record.target_connected === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false &&
    record.capability_invoked === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("credential_profile_id" in record) &&
    !("secret_reference_id" in record) &&
    !("secret_store_profile_id" in record) &&
    !("broker_id" in record) &&
    !("lease_handle" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record) &&
    !("raw_health_output" in record) &&
    !("process_output" in record)
  );
}

export async function createConnectorRuntimeActivation(input: {
  brokerage: ConnectorSecretBrokerageAuthorization;
  profileId: string;
  profileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { brokerage, profileId, profileDigest, policyId, policyDigest, purpose } = input;
  if (
    !brokerage.secret_brokerage_governed ||
    !brokerage.eligible_for_runtime_activation ||
    brokerage.secret_lease_issued ||
    brokerage.instance_state !== "enabled_secret_brokerage_governed"
  ) throw new Error("A current secret-brokerage authorization is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) ||
    !/^[a-f0-9]{64}$/.test(profileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed activation profile and policy are required");
  const response = await apiFetch("/api/v1/connectors/runtime-activations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-runtime-activation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-runtime-activation-input.v1",
      source_brokerage_authorization_id: brokerage.authorization_id,
      source_brokerage_authorization_digest: brokerage.canonical_digest,
      package_digest: brokerage.package_digest,
      activation_profile_id: profileId,
      activation_profile_digest: profileDigest,
      activation_policy_id: policyId,
      activation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment: true,
    }),
  });
  if (!response.ok) throw new Error(`Runtime activation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeActivation(payload)) throw new Error("Runtime activation returned unsafe evidence");
  if (
    payload.data.source_brokerage_authorization_id !== brokerage.authorization_id ||
    payload.data.source_brokerage_authorization_digest !== brokerage.canonical_digest ||
    payload.data.package_digest !== brokerage.package_digest ||
    payload.data.instance_id !== brokerage.instance_id ||
    payload.data.runtime_profile_digest !== brokerage.runtime_profile_digest ||
    payload.data.activation_profile_id !== profileId ||
    payload.data.activation_profile_digest !== profileDigest ||
    payload.data.activation_policy_id !== policyId ||
    payload.data.activation_policy_digest !== policyDigest
  ) throw new Error("Runtime activation does not match the exact governed evidence");
  return payload;
}
