import { apiFetch } from "./client";
import type { ConnectorRuntimeTrustGrant } from "./runtimeTrustGrants";

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

function isSafeAuthorization(
  value: unknown,
): value is { data: ConnectorSecretBrokerageAuthorization } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-secret-brokerage-authorization.v1" &&
    record.version === 1 &&
    typeof record.authorization_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_secret_brokerage_governed" &&
    record.secret_brokerage_governed === true &&
    record.credential_resolution_authorized === true &&
    record.eligible_for_runtime_activation === true &&
    record.secret_lease_issued === false &&
    record.credentials_resolved === false &&
    record.runner_started === false &&
    record.package_loaded === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("credential_profile_id" in record) &&
    !("secret_reference_id" in record) &&
    !("secret_store_profile_id" in record) &&
    !("broker_id" in record) &&
    !("lease_handle" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record)
  );
}

export async function createConnectorSecretBrokerageAuthorization(input: {
  runtimeTrust: ConnectorRuntimeTrustGrant;
  profileId: string;
  profileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { runtimeTrust, profileId, profileDigest, policyId, policyDigest, purpose } = input;
  if (
    !runtimeTrust.runtime_trust_granted ||
    !runtimeTrust.eligible_for_secret_brokerage ||
    runtimeTrust.credential_resolution_authorized ||
    runtimeTrust.instance_state !== "enabled_runtime_trusted"
  ) throw new Error("A current runtime-trusted connector is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) ||
    !/^[a-f0-9]{64}$/.test(profileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed brokerage profile and policy are required");
  const response = await apiFetch("/api/v1/connectors/secret-brokerage-authorizations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-secret-brokerage.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-secret-brokerage-input.v1",
      source_runtime_trust_grant_id: runtimeTrust.grant_id,
      source_runtime_trust_digest: runtimeTrust.canonical_digest,
      package_digest: runtimeTrust.package_digest,
      brokerage_profile_id: profileId,
      brokerage_profile_digest: profileDigest,
      brokerage_policy_id: policyId,
      brokerage_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment: true,
    }),
  });
  if (!response.ok) throw new Error(`Secret brokerage authorization failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeAuthorization(payload)) throw new Error("Secret brokerage service returned unsafe evidence");
  if (
    payload.data.source_runtime_trust_grant_id !== runtimeTrust.grant_id ||
    payload.data.source_runtime_trust_digest !== runtimeTrust.canonical_digest ||
    payload.data.package_digest !== runtimeTrust.package_digest ||
    payload.data.instance_id !== runtimeTrust.instance_id ||
    payload.data.runtime_profile_digest !== runtimeTrust.runtime_profile_digest ||
    payload.data.brokerage_profile_id !== profileId ||
    payload.data.brokerage_profile_digest !== profileDigest ||
    payload.data.brokerage_policy_id !== policyId ||
    payload.data.brokerage_policy_digest !== policyDigest
  ) throw new Error("Secret brokerage authorization does not match the exact governed evidence");
  return payload;
}
