import { apiFetch } from "./client";
import type { ConnectorRegistryPublicationReceipt } from "./registryPublications";

export type ConnectorPackageRegistrationRecord = {
  record_id: string;
  schema_version: "atlas.connector-package-registration-record.v1";
  version: 1;
  source_publication_receipt_id: string;
  source_publication_receipt_digest: string;
  source_signing_receipt_id: string;
  source_signing_receipt_digest: string;
  source_approval_request_id: string;
  source_approval_request_digest: string;
  source_final_validation_id: string;
  source_final_validation_digest: string;
  source_acquisition_id: string;
  source_acquisition_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  package_size_bytes: number;
  publisher_id: string;
  connector_id: string;
  release_version: string;
  provenance_digest: string;
  registry_profile_id: string;
  registration_policy_id: string;
  registration_policy_digest: string;
  registration_policy_version: string;
  manifest: {
    schema_version: string;
    connector_id: string;
    manifest_version: string;
    release_version: string;
    source_status: string;
    sdk_profile: string;
    target_products: string[];
    network_destination_count: number;
    configuration_key_count: number;
    secret_reference_count: number;
    capabilities: Array<{
      capability_id: string;
      capability_class: "C0" | "C1";
      required_permission: string;
    }>;
    manifest_digest: string;
  };
  registered_by: string;
  purpose: string;
  registered_at: string;
  canonical_digest: string;
  package_published: true;
  connector_registered: true;
  eligible_for_installation_governance: true;
  promotion_blocked: false;
  reused: boolean;
  connector_installed: false;
  connector_enabled: false;
  instance_created: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

function isRegistrationResponse(
  value: unknown,
): value is { data: ConnectorPackageRegistrationRecord } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const manifest = record.manifest;
  return (
    record.schema_version === "atlas.connector-package-registration-record.v1" &&
    record.version === 1 &&
    typeof record.record_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.package_published === true &&
    record.connector_registered === true &&
    record.eligible_for_installation_governance === true &&
    record.promotion_blocked === false &&
    record.connector_installed === false &&
    record.connector_enabled === false &&
    record.instance_created === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !!manifest &&
    typeof manifest === "object" &&
    Array.isArray((manifest as Record<string, unknown>).capabilities) &&
    !("artifact_reference" in record) &&
    !("reader_workload_id" in record) &&
    !("network_destinations" in manifest) &&
    !("configuration_keys" in manifest) &&
    !("secret_reference_ids" in manifest)
  );
}

export async function createConnectorPackageRegistration(input: {
  publication: ConnectorRegistryPublicationReceipt;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { publication, policyId, policyDigest, purpose } = input;
  if (
    !publication.package_published ||
    !publication.eligible_for_registration_governance ||
    publication.promotion_blocked ||
    publication.connector_registered
  ) {
    throw new Error("A current governed registry publication is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("An exact registration policy and bounded purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-registration-records", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-registration.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-registration-input.v1",
      source_publication_receipt_id: publication.receipt_id,
      source_publication_receipt_digest: publication.canonical_digest,
      package_digest: publication.package_digest,
      registration_policy_id: policyId,
      registration_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_registration_grants_no_installation_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package registration failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isRegistrationResponse(payload)) {
    throw new Error("Connector registry returned an unsafe registration record");
  }
  if (
    payload.data.source_publication_receipt_id !== publication.receipt_id ||
    payload.data.source_publication_receipt_digest !== publication.canonical_digest ||
    payload.data.package_digest !== publication.package_digest ||
    payload.data.connector_id !== publication.connector_id ||
    payload.data.release_version !== publication.release_version ||
    payload.data.registration_policy_id !== policyId ||
    payload.data.registration_policy_digest !== policyDigest
  ) {
    throw new Error("Registration record does not match the exact published package");
  }
  return payload;
}
