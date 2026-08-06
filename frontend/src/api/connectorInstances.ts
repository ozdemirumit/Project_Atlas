import { apiFetch } from "./client";
import type { ConnectorPackageInstallationReceipt } from "./packageInstallations";

export type ConnectorInstanceRecord = {
  record_id: string;
  schema_version: "atlas.connector-instance-record.v1";
  version: 1;
  source_installation_receipt_id: string;
  source_installation_receipt_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  sdk_profile: string;
  instance_policy_id: string;
  instance_policy_digest: string;
  instance_policy_version: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  instance_state: "disabled_unconfigured";
  owner_id: string;
  support_group_id: string;
  created_by: string;
  purpose: string;
  created_at: string;
  canonical_digest: string;
  package_published: true;
  connector_registered: true;
  package_installed: true;
  instance_created: true;
  eligible_for_configuration_governance: true;
  promotion_blocked: false;
  target_configured: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isInstanceResponse(value: unknown): value is { data: ConnectorInstanceRecord } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-instance-record.v1" &&
    record.version === 1 &&
    typeof record.record_id === "string" &&
    typeof record.instance_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "disabled_unconfigured" &&
    record.package_published === true &&
    record.connector_registered === true &&
    record.package_installed === true &&
    record.instance_created === true &&
    record.eligible_for_configuration_governance === true &&
    record.promotion_blocked === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("artifact_reference" in record) &&
    !("installation_store_profile_id" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record) &&
    !("target_endpoint" in record) &&
    !("secret_reference" in record)
  );
}

export async function createConnectorInstance(input: {
  installation: ConnectorPackageInstallationReceipt;
  instanceKey: string;
  displayName: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { installation, instanceKey, displayName, policyId, policyDigest, purpose } = input;
  if (
    !installation.package_installed ||
    !installation.eligible_for_instance_governance ||
    installation.promotion_blocked ||
    installation.instance_created
  ) {
    throw new Error("A current governed package installation is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(instanceKey) ||
    displayName.trim().length < 3 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("A bounded instance identity and exact policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/instances", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-instance.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-instance-creation-input.v1",
      source_installation_receipt_id: installation.receipt_id,
      source_installation_receipt_digest: installation.canonical_digest,
      package_digest: installation.package_digest,
      instance_key: instanceKey,
      display_name: displayName.trim(),
      instance_policy_id: policyId,
      instance_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector instance creation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isInstanceResponse(payload)) {
    throw new Error("Connector instance service returned an unsafe record");
  }
  if (
    payload.data.source_installation_receipt_id !== installation.receipt_id ||
    payload.data.source_installation_receipt_digest !== installation.canonical_digest ||
    payload.data.package_digest !== installation.package_digest ||
    payload.data.connector_id !== installation.connector_id ||
    payload.data.release_version !== installation.release_version ||
    payload.data.manifest_digest !== installation.manifest_digest ||
    payload.data.instance_key !== instanceKey ||
    payload.data.instance_policy_id !== policyId ||
    payload.data.instance_policy_digest !== policyDigest
  ) {
    throw new Error("Instance record does not match the exact installation and request");
  }
  return payload;
}
