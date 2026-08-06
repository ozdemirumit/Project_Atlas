import { apiFetch } from "./client";
import type { ConnectorPackageSigningReceipt } from "./packageSigning";

export type ConnectorRegistryPublicationReceipt = {
  receipt_id: string;
  schema_version: "atlas.connector-registry-publication-receipt.v1";
  version: 1;
  source_signing_receipt_id: string;
  source_signing_receipt_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  package_size_bytes: number;
  publisher_id: string;
  connector_id: string;
  release_version: string;
  publication_policy_id: string;
  publication_policy_digest: string;
  verification: {
    verifier_profile_id: string;
    verifier_workload_id: string;
    key_id: string;
    algorithm: string;
    envelope_digest: string;
    signature_digest: string;
    verified_at: string;
    signature_valid: true;
  };
  publication: {
    registry_profile_id: string;
    publisher_workload_id: string;
    artifact_reference_schema: string;
    package_digest: string;
    package_size_bytes: number;
    source_signing_receipt_digest: string;
    publication_digest: string;
    published_at: string;
    integrity_verified: true;
    reused: boolean;
  };
  requested_by: string;
  purpose: string;
  published_at: string;
  canonical_digest: string;
  publisher_attested: true;
  package_signed: true;
  package_published: true;
  eligible_for_registration_governance: true;
  promotion_blocked: false;
  reused: boolean;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

function isPublicationResponse(
  value: unknown,
): value is { data: ConnectorRegistryPublicationReceipt } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const verification = record.verification;
  const publication = record.publication;
  return (
    record.schema_version === "atlas.connector-registry-publication-receipt.v1" &&
    record.version === 1 &&
    typeof record.receipt_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.publisher_attested === true &&
    record.package_signed === true &&
    record.package_published === true &&
    record.eligible_for_registration_governance === true &&
    record.promotion_blocked === false &&
    record.connector_registered === false &&
    record.connector_installed === false &&
    record.connector_enabled === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !!verification &&
    typeof verification === "object" &&
    (verification as Record<string, unknown>).signature_valid === true &&
    !("signature_value" in verification) &&
    !!publication &&
    typeof publication === "object" &&
    (publication as Record<string, unknown>).integrity_verified === true
    && !("artifact_reference" in publication)
  );
}

export async function createConnectorRegistryPublication(input: {
  signing: ConnectorPackageSigningReceipt;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { signing, policyId, policyDigest, purpose } = input;
  if (
    !signing.package_signed ||
    !signing.eligible_for_registry_governance ||
    signing.promotion_blocked
  ) {
    throw new Error("A current governed package signature is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("An exact publication policy and bounded purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/registry-publication-receipts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-registry-publication.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-registry-publication-input.v1",
      source_signing_receipt_id: signing.receipt_id,
      source_signing_receipt_digest: signing.canonical_digest,
      package_digest: signing.envelope.package_digest,
      publication_policy_id: policyId,
      publication_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_publication_grants_no_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector registry publication failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isPublicationResponse(payload)) {
    throw new Error("Connector registry returned an unsafe publication receipt");
  }
  if (
    payload.data.source_signing_receipt_id !== signing.receipt_id ||
    payload.data.source_signing_receipt_digest !== signing.canonical_digest ||
    payload.data.package_digest !== signing.envelope.package_digest ||
    payload.data.publication_policy_id !== policyId ||
    payload.data.publication_policy_digest !== policyDigest
  ) {
    throw new Error("Publication receipt does not match the exact signed package");
  }
  return payload;
}
