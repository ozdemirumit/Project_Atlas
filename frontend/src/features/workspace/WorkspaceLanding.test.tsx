import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentIdentity } from "../../api/identity";
import { WorkspaceLanding } from "./WorkspaceLanding";

const identity: CurrentIdentity = {
  subject_id: "subject.operator",
  display_name: "Atlas Operator",
  subject_kind: "human",
  organization_id: "organization.test",
  role_ids: ["role.operator"],
  group_ids: [],
  authentication: {
    provider_id: "provider.oidc",
    method: "oidc",
    assurance_level: "aal2",
    authenticated_at: "2026-08-10T00:00:00Z",
  },
  scope: {
    organization_id: "organization.test",
    environment_id: "environment.test",
    site_id: "site.test",
    domain_id: "domain.test",
    resource_id: "resource.test",
    capability_class: "C0",
  },
  authorization_decision_id: "decision.test",
  effective_role_versions: ["role.operator:v1"],
  effective_assignment_versions: ["assignment.operator:v1"],
};

const platform = {
  data: {
    service: "atlas",
    version: "test",
    environment: "test",
    status: "healthy",
    components: [],
    warnings: [],
  },
  meta: { correlation_id: "correlation.test", generated_at: "2026-08-10T00:00:00Z" },
};

function renderLanding() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <WorkspaceLanding
        identity={identity}
        onNavigate={() => undefined}
        onNavigateCapability={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("WorkspaceLanding", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("uses the existing current-session endpoint for sign-out", async () => {
    const requests: Array<{ method: string; url: string }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      requests.push({ method: init?.method ?? "GET", url });
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 204 }));
    });
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() =>
      expect(requests).toContainEqual({
        method: "DELETE",
        url: "/api/v1/authentication/sessions/current",
      }),
    );
  });

  it("keeps the current session authoritative when sign-out fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 503 }));
    });
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your current session remains authoritative",
    );
  });
});
