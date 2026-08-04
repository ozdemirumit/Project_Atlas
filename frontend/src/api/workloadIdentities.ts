import { apiFetch, ApiRequestError } from "./client";

export type WorkloadIdentity = {
  identity_id: string;
  version: number;
  display_name: string;
  service_id: string;
  instance_id: string;
  owner_subject_id: string;
  purpose: string;
  organization_id: string;
  environment_id: string;
  audiences: string[];
  secret_reference_ids: string[];
  state: "active" | "disabled";
  created_at: string;
  updated_at: string;
};

export type WorkloadCredential = {
  credential_id: string;
  version: number;
  identity_id: string;
  key_version: number;
  audiences: string[];
  issued_at: string;
  expires_at: string;
  state: "active" | "retiring" | "revoked" | "expired";
  retire_at: string | null;
  revoked_at: string | null;
};

export type WorkloadIdentityInventoryResponse = {
  data: {
    identities: WorkloadIdentity[];
    credentials: WorkloadCredential[];
    truncated: boolean;
  };
};

export type IssuedWorkloadCredentialResponse = {
  data: {
    identity: WorkloadIdentity;
    credential: WorkloadCredential;
    token: string;
  };
};

export async function getWorkloadIdentities(
  query: string,
): Promise<WorkloadIdentityInventoryResponse | null> {
  const parameters = new URLSearchParams({ limit: "50" });
  if (query.trim()) parameters.set("query", query.trim());
  const response = await apiFetch(`/api/v1/workload-identities?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 403) return null;
  if (!response.ok) throw new ApiRequestError("Workload identity inventory failed", response.status);
  const payload = (await response.json()) as WorkloadIdentityInventoryResponse;
  if (!Array.isArray(payload.data?.identities) || !Array.isArray(payload.data?.credentials)) {
    throw new ApiRequestError("Workload identity inventory failed", response.status);
  }
  return payload;
}

export async function createWorkloadIdentity(input: {
  identityId: string;
  displayName: string;
  serviceId: string;
  instanceId: string;
  ownerSubjectId: string;
  purpose: string;
  audience: string;
  secretReferenceId: string;
  lifetimeMinutes: number;
  reason: string;
  idempotencyKey: string;
}): Promise<IssuedWorkloadCredentialResponse> {
  const response = await apiFetch("/api/v1/workload-identities", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": input.idempotencyKey,
    },
    body: JSON.stringify({
      identity_id: input.identityId,
      display_name: input.displayName,
      service_id: input.serviceId,
      instance_id: input.instanceId,
      owner_subject_id: input.ownerSubjectId,
      purpose: input.purpose,
      audiences: [input.audience],
      secret_reference_ids: [input.secretReferenceId],
      lifetime_minutes: input.lifetimeMinutes,
      reason: input.reason,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Workload identity creation failed", response.status);
  return (await response.json()) as IssuedWorkloadCredentialResponse;
}

export async function rotateWorkloadCredential(input: {
  identityId: string;
  expectedVersion: number;
  lifetimeMinutes: number;
  overlapMinutes: number;
  reason: string;
  idempotencyKey: string;
}): Promise<IssuedWorkloadCredentialResponse> {
  const response = await apiFetch(
    `/api/v1/workload-identities/${encodeURIComponent(input.identityId)}/rotations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": input.idempotencyKey,
      },
      body: JSON.stringify({
        expected_version: input.expectedVersion,
        lifetime_minutes: input.lifetimeMinutes,
        overlap_minutes: input.overlapMinutes,
        reason: input.reason,
      }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Workload credential rotation failed", response.status);
  return (await response.json()) as IssuedWorkloadCredentialResponse;
}

export async function revokeWorkloadCredential(input: {
  credentialId: string;
  expectedVersion: number;
  reason: string;
  idempotencyKey: string;
}): Promise<void> {
  const response = await apiFetch(
    `/api/v1/workload-identities/credentials/${encodeURIComponent(input.credentialId)}/revocations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": input.idempotencyKey,
      },
      body: JSON.stringify({
        expected_version: input.expectedVersion,
        reason: input.reason,
      }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Workload credential revocation failed", response.status);
}
