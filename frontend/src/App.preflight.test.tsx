import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./ApplicationCoordinator";

const identity = {
  data: {
    subject_id: "subject.enterprise.platform-operator",
    display_name: "Platform Operator",
    subject_kind: "human",
    organization_id: "organization.enterprise",
    role_ids: ["role.platform-operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.ldap.enterprise",
      method: "ldap",
      assurance_level: "multi_factor",
      authenticated_at: "2026-08-04T16:00:00Z",
    },
    scope: {
      organization_id: "organization.enterprise",
      environment_id: "environment.test",
      site_id: "site.local",
      domain_id: "domain.identity",
      resource_id: "resource.identity.self",
      capability_class: "C0",
    },
    authorization_decision_id: "decision.preflight.ui",
    effective_role_versions: ["role.platform-operator:v1"],
    effective_assignment_versions: ["assignment.platform-preflight:1"],
  },
};

function preflight(mode = "offline", profile = "linux_lab") {
  return {
    data: {
      report_id: "preflight.ui.001",
      release_id: "release.atlas.lab-0.1.0",
      release_version: "0.1.0",
      build_id: "build.synthetic.main",
      manifest_digest: "a".repeat(64),
      mode,
      profile,
      state: "passed",
      checks: [
        {
          code: "release.signature.valid",
          category: "release",
          state: "passed",
          mandatory: true,
          summary: "Release manifest signature is valid.",
          evidence: "hmac-sha256-lab:secret.release-signing.lab",
          remediation: null,
        },
        {
          code: "host.ports.available",
          category: "network",
          state: "passed",
          mandatory: true,
          summary: "Required local ports are available.",
          evidence: "conflict_count=0",
          remediation: null,
        },
      ],
      generated_at: "2026-08-04T16:00:00Z",
      correlation_id: "correlation.preflight.ui",
      mutation_authorized: false,
      execution_authorized: false,
    },
  };
}

beforeEach(() => {
  window.history.replaceState({}, "", "/#/health/deployments");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("release preflight", () => {
  it("shows authorized read-only evidence and switches acquisition mode", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const requested: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      requested.push(url);
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/platform/release-preflight")) {
        const mode = url.includes("mode=mirrored") ? "mirrored" : "offline";
        return Promise.resolve(new Response(JSON.stringify(preflight(mode)), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Read-only deployment preflight")).toBeVisible();
    expect(screen.getByText("Release manifest signature is valid.")).toBeVisible();
    expect(screen.getByText(/No installation, mutation, deployment, or execution/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Release acquisition mode"), {
      target: { value: "mirrored" },
    });
    await waitFor(() => expect(requested.some((url) => url.includes("mode=mirrored"))).toBe(true));
    expect(screen.queryByText(/private-key-value/i)).not.toBeInTheDocument();
  });

  it("keeps the preflight surface absent when discovery is forbidden", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve(
        new Response(JSON.stringify(url.includes("/identity/me") ? identity : { code: "denied" }), {
          status: url.includes("/identity/me") ? 200 : 403,
        }),
      );
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Platform Operator")).toBeVisible();
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Read-only deployment preflight" }),
      ).not.toBeInTheDocument(),
    );
  });
});
