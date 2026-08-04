import { apiFetch, ApiRequestError } from "./client";

export type ApiCredentialGrant = {
  permission_id: string;
  scope_reference: string;
};

export type ApiCredential = {
  credential_id: string;
  version: number;
  display_name: string;
  purpose: string;
  state: "active" | "revoked" | "expired";
  grants: ApiCredentialGrant[];
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
};

export type ApiCredentialInventoryResponse = {
  data: {
    credentials: ApiCredential[];
    available_grants: ApiCredentialGrant[];
    truncated: boolean;
  };
};

export type IssuedApiCredentialResponse = {
  data: ApiCredential & { token: string };
};

export async function getApiCredentials(): Promise<ApiCredentialInventoryResponse> {
  const response = await apiFetch("/api/v1/authentication/api-credentials", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("API credential inventory failed", response.status);
  return (await response.json()) as ApiCredentialInventoryResponse;
}

export async function createApiCredential(input: {
  displayName: string;
  purpose: string;
  expiresInMinutes: number;
  permissionIds: string[];
}): Promise<IssuedApiCredentialResponse> {
  const response = await apiFetch("/api/v1/authentication/api-credentials", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: input.displayName,
      purpose: input.purpose,
      expires_in_minutes: input.expiresInMinutes,
      permission_ids: input.permissionIds,
    }),
  });
  if (!response.ok) throw new ApiRequestError("API credential creation failed", response.status);
  return (await response.json()) as IssuedApiCredentialResponse;
}

export async function revokeApiCredential(credentialId: string): Promise<void> {
  const response = await apiFetch(
    `/api/v1/authentication/api-credentials/${encodeURIComponent(credentialId)}`,
    { method: "DELETE", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("API credential revocation failed", response.status);
}
