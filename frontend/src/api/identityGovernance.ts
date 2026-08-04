import { apiFetch, ApiRequestError } from "./client";

export type GovernedSession = {
  session_id: string;
  version: number;
  subject_id: string;
  subject_display_name: string;
  provider_id: string;
  state: "active";
  credential_kind: "browser_session";
  created_at: string;
  last_seen_at: string;
  absolute_expires_at: string;
  idle_expires_at: string;
};

export type GovernedApiCredential = {
  credential_id: string;
  version: number;
  subject_id: string;
  subject_display_name: string;
  provider_id: string;
  display_name: string;
  purpose: string;
  state: "active";
  grants: { permission_id: string; scope_reference: string }[];
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
};

export type IdentityGovernanceResponse = {
  data: {
    sessions: GovernedSession[];
    api_credentials: GovernedApiCredential[];
    truncated: boolean;
  };
};

export async function getIdentityGovernance(
  query: string,
): Promise<IdentityGovernanceResponse | null> {
  const parameters = new URLSearchParams({ limit: "50" });
  if (query.trim()) parameters.set("query", query.trim());
  const response = await apiFetch(`/api/v1/identity-governance?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 403) return null;
  if (!response.ok) throw new ApiRequestError("Identity governance inventory failed", response.status);
  return (await response.json()) as IdentityGovernanceResponse;
}

export async function revokeGovernedSession(input: {
  sessionId: string;
  expectedVersion: number;
  reason: string;
  idempotencyKey: string;
}): Promise<void> {
  const response = await apiFetch(
    `/api/v1/identity-governance/sessions/${encodeURIComponent(input.sessionId)}/revocations`,
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
  if (!response.ok) throw new ApiRequestError("Session governance revocation failed", response.status);
}

export async function revokeGovernedApiCredential(input: {
  credentialId: string;
  expectedVersion: number;
  reason: string;
  idempotencyKey: string;
}): Promise<void> {
  const response = await apiFetch(
    `/api/v1/identity-governance/api-credentials/${encodeURIComponent(input.credentialId)}/revocations`,
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
  if (!response.ok) {
    throw new ApiRequestError("API credential governance revocation failed", response.status);
  }
}
