import { apiFetch } from "./client";
import type { ConnectorPackageRegistrationRecord } from "./packageRegistrations";

export type ConnectorPackageInstallationReceipt = {
  receipt_id: string;
  schema_version: "atlas.connector-package-installation-receipt.v1";
  version: 1;
  source_registration_record_id: string;
  source_registration_record_digest: string;
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
  manifest_digest: string;
  sdk_profile: string;
  registry_profile_id: string;
  registration_policy_id: string;
  registration_policy_digest: string;
  installation_policy_id: string;
  installation_policy_digest: string;
  installation_policy_version: string;
  installation: {
    installer_profile_id: string;
    installation_store_profile_id: string;
    artifact_reference_schema: string;
    package_digest: string;
    package_size_bytes: number;
    stored_at: string;
  };
  installed_by: string;
  purpose: string;
  installed_at: string;
  canonical_digest: string;
  package_published: true;
  connector_registered: true;
  package_installed: true;
  eligible_for_instance_governance: true;
  promotion_blocked: false;
  reused: boolean;
  connector_enabled: false;
  instance_created: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

function isInstallationResponse(
  value: unknown,
): value is { data: ConnectorPackageInstallationReceipt } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const receipt = data as Record<string, unknown>;
  const installation = receipt.installation;
  return (
    receipt.schema_version === "atlas.connector-package-installation-receipt.v1" &&
    receipt.version === 1 &&
    typeof receipt.receipt_id === "string" &&
    typeof receipt.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(receipt.canonical_digest) &&
    receipt.package_published === true &&
    receipt.connector_registered === true &&
    receipt.package_installed === true &&
    receipt.eligible_for_instance_governance === true &&
    receipt.promotion_blocked === false &&
    receipt.connector_enabled === false &&
    receipt.instance_created === false &&
    receipt.target_configured === false &&
    receipt.credentials_resolved === false &&
    receipt.runtime_trust_granted === false &&
    receipt.execution_authorized === false &&
    receipt.deployment_approved === false &&
    receipt.infrastructure_mutation_performed === false &&
    !!installation &&
    typeof installation === "object" &&
    !("artifact_reference" in installation) &&
    !("installer_workload_id" in installation) &&
    !("installation_custodian_id" in installation) &&
    !("request_fingerprint" in receipt) &&
    !("idempotency_key" in receipt)
  );
}

export async function createConnectorPackageInstallation(input: {
  registration: ConnectorPackageRegistrationRecord;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { registration, policyId, policyDigest, purpose } = input;
  if (
    !registration.connector_registered ||
    !registration.eligible_for_installation_governance ||
    registration.promotion_blocked ||
    registration.connector_installed
  ) {
    throw new Error("A current governed package registration is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("An exact installation policy and bounded purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-installation-receipts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-installation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-installation-input.v1",
      source_registration_record_id: registration.record_id,
      source_registration_record_digest: registration.canonical_digest,
      package_digest: registration.package_digest,
      installation_policy_id: policyId,
      installation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_installation_grants_no_instance_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package installation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isInstallationResponse(payload)) {
    throw new Error("Connector installer returned an unsafe installation receipt");
  }
  if (
    payload.data.source_registration_record_id !== registration.record_id ||
    payload.data.source_registration_record_digest !== registration.canonical_digest ||
    payload.data.package_digest !== registration.package_digest ||
    payload.data.connector_id !== registration.connector_id ||
    payload.data.release_version !== registration.release_version ||
    payload.data.manifest_digest !== registration.manifest.manifest_digest ||
    payload.data.installation_policy_id !== policyId ||
    payload.data.installation_policy_digest !== policyDigest
  ) {
    throw new Error("Installation receipt does not match the exact registered package");
  }
  return payload;
}
