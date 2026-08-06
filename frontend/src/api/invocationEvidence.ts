import { apiFetch } from "./client";
import type { ConnectorBoundedInvocation } from "./boundedInvocations";

export type ConnectorInvocationEvidence = {
  ingestion_id: string;
  schema_version: "atlas.connector-invocation-evidence-ingestion.v1";
  version: 1;
  claim_id: string;
  source_invocation_id: string;
  source_invocation_digest: string;
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
  output_schema_digest: string;
  result_policy_digest: string;
  normalized_redacted_result_digest: string;
  evidence_package_id: string;
  evidence_schema_version: string;
  evidence_content_digest: string;
  evidence_metadata_digest: string;
  classification: string;
  access_policy_id: string;
  access_policy_digest: string;
  retention_policy_id: string;
  retention_policy_digest: string;
  encryption_profile_id: string;
  encryption_profile_digest: string;
  ingestion_policy_id: string;
  ingestion_policy_digest: string;
  ingestion_policy_version: string;
  ingestion_adapter_id: string;
  evidence_item_count: number;
  evidence_bytes: number;
  observed_from: string;
  observed_to: string;
  ingested_at: string;
  instance_state: "enabled_invocation_evidence_ingested";
  ingested_by: string;
  purpose: string;
  canonical_digest: string;
  source_invocation_completed: true;
  evidence_ingested: true;
  immutable_storage_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  knowledge_item_created: false;
  retrieval_published: false;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeInvocationEvidence(
  value: unknown,
): value is { data: ConnectorInvocationEvidence } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "evidence_content",
    "evidence_excerpt",
    "observation_values",
    "raw_output",
    "target_address",
    "storage_location",
    "storage_coordinates",
    "acl_principals",
    "encryption_key",
    "secret_reference_id",
    "lease_handle",
    "session_handle",
    "request_binding_digest",
    "idempotency_digest",
    "idempotency_key",
  ];
  return (
    record.schema_version === "atlas.connector-invocation-evidence-ingestion.v1" &&
    record.version === 1 &&
    typeof record.ingestion_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "enabled_invocation_evidence_ingested" &&
    record.source_invocation_completed === true &&
    record.evidence_ingested === true &&
    record.immutable_storage_confirmed === true &&
    record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.knowledge_item_created === false &&
    record.retrieval_published === false &&
    record.model_context_available === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbidden.every((field) => !(field in record))
  );
}

export async function createConnectorInvocationEvidence(input: {
  invocation: ConnectorBoundedInvocation;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { invocation, policyId, policyDigest, purpose } = input;
  if (
    !invocation.authorization_consumed ||
    !invocation.capability_invoked ||
    !invocation.result_validated ||
    !invocation.result_redacted ||
    !invocation.target_session_closed ||
    !invocation.lease_revocation_confirmed ||
    invocation.target_connected ||
    invocation.evidence_ingested ||
    invocation.instance_state !== "enabled_bounded_capability_invocation_completed"
  )
    throw new Error("A completed un-ingested bounded invocation is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed evidence-ingestion policy is required");
  const response = await apiFetch("/api/v1/connectors/invocation-evidence", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-invocation-evidence.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-invocation-evidence-input.v1",
      source_invocation_id: invocation.invocation_id,
      source_invocation_digest: invocation.canonical_digest,
      ingestion_policy_id: policyId,
      ingestion_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Connector invocation evidence ingestion failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeInvocationEvidence(payload))
    throw new Error("Invocation evidence returned unsafe metadata");
  if (
    payload.data.source_invocation_id !== invocation.invocation_id ||
    payload.data.source_invocation_digest !== invocation.canonical_digest ||
    payload.data.package_digest !== invocation.package_digest ||
    payload.data.instance_id !== invocation.instance_id ||
    payload.data.capability_id !== invocation.capability_id ||
    payload.data.normalized_redacted_result_digest !==
      invocation.normalized_redacted_result_digest ||
    payload.data.ingestion_policy_id !== policyId ||
    payload.data.ingestion_policy_digest !== policyDigest
  )
    throw new Error("Invocation evidence does not match the exact governed result");
  return payload;
}
