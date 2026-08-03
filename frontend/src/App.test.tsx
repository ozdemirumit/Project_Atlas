import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const platformResponse = {
  data: {
    service: "atlas-api",
    version: "0.1.0",
    environment: "test",
    status: "healthy",
    components: [],
    warnings: [],
  },
  meta: {
    correlation_id: "test-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const identityResponse = {
  data: {
    subject_id: "subject.development.operator",
    display_name: "Local Operator",
    subject_kind: "human",
    organization_id: "organization.development",
    role_ids: ["role.development.operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.development.local",
      method: "development",
      assurance_level: "development",
      authenticated_at: "2026-08-03T10:00:00Z",
    },
    scope: {
      organization_id: "organization.development",
      environment_id: "environment.test",
      site_id: "site.local",
      domain_id: "domain.identity",
      resource_id: "resource.identity.self",
      capability_class: "C0",
    },
    authorization_decision_id: "dec_test",
    effective_role_versions: ["role.development.operator:v1"],
    effective_assignment_versions: ["assignment.development.operator:v1"],
  },
  meta: {
    correlation_id: "test-identity-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Atlas application shell", () => {
  it("shows the governed operations workspace and platform status", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const payload = url.includes("/identity/me") ? identityResponse : platformResponse;
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Infrastructure investigation" })).toBeVisible();
    expect(screen.getByText("Human decision required")).toBeVisible();
    expect(await screen.findByText("test")).toBeVisible();
    expect(await screen.findByText("Local Operator")).toBeVisible();
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
  });
});
