export type CurrentIdentity = {
  subject_id: string;
  display_name: string;
  subject_kind: string;
  organization_id: string;
  credential_kind: "identity_provider" | "browser_session" | "api_token";
  role_ids: string[];
  group_ids: string[];
  authentication: {
    provider_id: string;
    method: string;
    assurance_level: string;
    authenticated_at: string;
  };
  scope: {
    organization_id: string;
    environment_id: string;
    site_id: string;
    domain_id: string;
    resource_id: string;
    capability_class: string;
  };
  authorization_decision_id: string;
  effective_role_versions: string[];
  effective_assignment_versions: string[];
};

type CurrentIdentityResponse = {
  data: CurrentIdentity;
  meta: {
    correlation_id: string;
    generated_at: string;
  };
};

export async function getCurrentIdentity(): Promise<CurrentIdentityResponse | null> {
  const response = await apiFetch("/api/v1/identity/me", {
    headers: { Accept: "application/json" },
  });

  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Current identity request failed with ${response.status}`);
  }

  return (await response.json()) as CurrentIdentityResponse;
}
import { apiFetch } from "./client";
