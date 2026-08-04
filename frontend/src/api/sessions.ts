import { apiFetch, ApiRequestError } from "./client";

type SessionResponse = {
  data: {
    session_id: string;
    subject_id: string;
    state: string;
    absolute_expires_at: string;
    idle_expires_at: string;
  };
};

export type BrowserSession = {
  session_id: string;
  version: number;
  state: "active" | "revoked" | "expired";
  credential_kind: "browser_session";
  created_at: string;
  last_seen_at: string;
  absolute_expires_at: string;
  idle_expires_at: string;
  current: boolean;
};

type SessionInventoryResponse = {
  data: { sessions: BrowserSession[]; truncated: boolean };
};

export async function createBrowserSession(
  username: string,
  password: string,
): Promise<SessionResponse> {
  const response = await apiFetch("/api/v1/authentication/sessions", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new ApiRequestError("Sign-in failed", response.status);
  return (await response.json()) as SessionResponse;
}

export async function logoutBrowserSession(): Promise<void> {
  const response = await apiFetch("/api/v1/authentication/sessions/current", {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Sign-out failed", response.status);
}

export async function getBrowserSessions(): Promise<SessionInventoryResponse> {
  const response = await apiFetch("/api/v1/authentication/sessions", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Session inventory failed", response.status);
  return (await response.json()) as SessionInventoryResponse;
}

export async function revokeBrowserSession(sessionId: string): Promise<void> {
  const response = await apiFetch(
    `/api/v1/authentication/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Session revocation failed", response.status);
}
