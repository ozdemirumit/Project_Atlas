import { apiFetch } from "./client";
import type { ConnectorCapabilityEnablement } from "./capabilityEnablements";

export type ConnectorRuntimeTrustGrant = {
  grant_id: string;
  schema_version: "atlas.connector-runtime-trust-grant.v1";
  version: 1;
  source_enablement_id: string;
  source_enablement_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  capability_profile_id: string;
  capability_profile_digest: string;
  capability_count: number;
  runtime_profile_id: string;
  runtime_profile_digest: string;
  sdk_profile: string;
  runner_runtime_id: string;
  runner_pool_id: string;
  runner_image_digest: string;
  runner_workload_identity_id: string;
  isolation_profile_id: string;
  filesystem_policy_id: string;
  egress_policy_id: string;
  secret_delivery_policy_id: string;
  telemetry_policy_id: string;
  resource_limit_profile_id: string;
  trust_policy_id: string;
  trust_policy_digest: string;
  trust_policy_version: string;
  trust_version: 1;
  instance_state: "enabled_runtime_trusted";
  granted_by: string;
  purpose: string;
  granted_at: string;
  canonical_digest: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  runtime_boundary_bound: true;
  runtime_trust_granted: true;
  eligible_for_secret_brokerage: true;
  promotion_blocked: false;
  runner_started: false;
  package_loaded: false;
  credential_resolution_authorized: false;
  credentials_resolved: false;
  target_connection_authorized: false;
  capability_invocation_authorized: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeRuntimeTrust(value: unknown): value is { data: ConnectorRuntimeTrustGrant } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-runtime-trust-grant.v1" &&
    record.version === 1 &&
    typeof record.grant_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_runtime_trusted" &&
    record.runtime_boundary_bound === true &&
    record.runtime_trust_granted === true &&
    record.eligible_for_secret_brokerage === true &&
    record.runner_started === false &&
    record.package_loaded === false &&
    record.credential_resolution_authorized === false &&
    record.credentials_resolved === false &&
    record.target_connection_authorized === false &&
    record.capability_invocation_authorized === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("target_profile_id" in record) &&
    !("credential_profile_id" in record) &&
    !("endpoint_url" in record) &&
    !("secret_reference_id" in record) &&
    !("command" in record) &&
    !("parameters" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record)
  );
}

export async function createConnectorRuntimeTrustGrant(input: {
  enablement: ConnectorCapabilityEnablement;
  profileId: string;
  profileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { enablement, profileId, profileDigest, policyId, policyDigest, purpose } = input;
  if (
    !enablement.connector_enabled ||
    !enablement.eligible_for_runtime_trust ||
    enablement.runtime_trust_granted ||
    enablement.instance_state !== "enabled_capabilities_governed"
  ) throw new Error("A current capability-governed connector is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) ||
    !/^[a-f0-9]{64}$/.test(profileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed runtime profile and trust policy are required");
  const response = await apiFetch("/api/v1/connectors/runtime-trust-grants", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-runtime-trust.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-runtime-trust-input.v1",
      source_enablement_id: enablement.enablement_id,
      source_enablement_digest: enablement.canonical_digest,
      package_digest: enablement.package_digest,
      runtime_profile_id: profileId,
      runtime_profile_digest: profileDigest,
      trust_policy_id: policyId,
      trust_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: true,
    }),
  });
  if (!response.ok) throw new Error(`Runtime trust grant failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeRuntimeTrust(payload)) throw new Error("Runtime trust service returned unsafe evidence");
  if (
    payload.data.source_enablement_id !== enablement.enablement_id ||
    payload.data.source_enablement_digest !== enablement.canonical_digest ||
    payload.data.package_digest !== enablement.package_digest ||
    payload.data.instance_id !== enablement.instance_id ||
    payload.data.capability_profile_digest !== enablement.capability_profile_digest ||
    payload.data.runtime_profile_id !== profileId ||
    payload.data.runtime_profile_digest !== profileDigest ||
    payload.data.trust_policy_id !== policyId ||
    payload.data.trust_policy_digest !== policyDigest
  ) throw new Error("Runtime trust grant does not match the exact governed evidence");
  return payload;
}
