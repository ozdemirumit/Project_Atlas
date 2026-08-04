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
