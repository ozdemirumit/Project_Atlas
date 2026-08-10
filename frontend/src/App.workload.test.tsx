import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./ApplicationCoordinator";

const identityResponse = {
  data: {
    subject_id: "subject.enterprise.admin",
    display_name: "Security Administrator",
    subject_kind: "human",
    organization_id: "organization.enterprise",
    role_ids: ["role.security-administrator"],
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
    authorization_decision_id: "decision.workload.ui",
    effective_role_versions: ["role.security-administrator:v3"],
    effective_assignment_versions: ["assignment.workload-admin:1"],
  },
};

const workloadIdentity = {
  identity_id: "workload.atlas.health.scheduler",
  version: 1,
  display_name: "Health scheduler",
  service_id: "service.health-scheduler",
  instance_id: "instance.health-scheduler.local-01",
  owner_subject_id: "subject.enterprise.platform-owner",
  purpose: "Run bounded Atlas health-check coordination.",
  organization_id: "organization.enterprise",
  environment_id: "environment.test",
  audiences: ["service.health-check"],
  secret_reference_ids: ["secret.connector.health-readonly"],
  state: "active",
  created_at: "2026-08-04T16:00:00Z",
  updated_at: "2026-08-04T16:00:00Z",
};

const workloadCredential = {
  credential_id: "credential.workload.ui-01",
  version: 1,
  identity_id: workloadIdentity.identity_id,
  key_version: 7,
  audiences: ["service.health-check"],
  issued_at: "2026-08-04T16:00:00Z",
  expires_at: "2026-08-04T16:10:00Z",
  state: "active",
  retire_at: null,
  revoked_at: null,
};

const workloadInventoryResponse = {
  data: {
    identities: [workloadIdentity],
    credentials: [workloadCredential],
    truncated: false,
  },
};

const issuedResponse = {
  data: {
    identity: workloadIdentity,
    credential: workloadCredential,
    token: `atlas_wlt_v1.${"A".repeat(50)}.${"B".repeat(43)}`,
  },
};

const storageResponse = {
  data: {
    snapshot_id: "snapshot.storage.workload-ui",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    target_id: "target.storage.synthetic",
    data_profile: "synthetic_lab",
    generated_at: "2026-08-04T16:00:00Z",
    assets: [],
    findings: [],
    evidence: [],
    investigation: {
      investigation_id: "investigation.empty",
      title: "No active investigation",
      state: "provisional",
      summary: "No storage evidence is required for workload governance validation.",
      hypotheses: [],
      unknowns: [],
      next_checks: [],
      evidence_references: [],
      updated_at: "2026-08-04T16:00:00Z",
    },
    report: {
      report_id: "report.empty",
      title: "No active report",
      generated_at: "2026-08-04T16:00:00Z",
      executive_summary: "No storage report is required.",
      confirmed_facts: [],
      provisional_findings: [],
      unknowns: [],
      evidence_references: [],
      safety_notice: "No infrastructure execution is authorized.",
    },
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "atlas_csrf=; Max-Age=0; path=/";
});

describe("workload identity governance", () => {
  it("creates, rotates, and revokes with confirmation and protected request headers", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    document.cookie = "atlas_csrf=csrf_workload_ui; path=/; SameSite=Strict";
    const mutations: { url: string; init: RequestInit | undefined }[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(
          new Response(JSON.stringify(identityResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/workload-identities") && init?.method === "POST") {
        mutations.push({ url, init });
        const payload = url.includes("/revocations")
          ? { data: { ...workloadCredential, state: "revoked" } }
          : issuedResponse;
        return Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: url.endsWith("/workload-identities") ? 201 : 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/workload-identities")) {
        return Promise.resolve(
          new Response(JSON.stringify(workloadInventoryResponse), {
            status: 200,
            headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
          }),
        );
      }
      if (url.includes("/storage/overview")) {
        return Promise.resolve(
          new Response(JSON.stringify(storageResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ code: "authorization_denied" }), {
          status: 403,
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

    expect(await screen.findByText("Security Administrator")).toBeVisible();
    await waitFor(() =>
      expect(
        vi.mocked(globalThis.fetch).mock.calls.some(([input]) => {
          const url =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.href
                : input.url;
          return url.includes("/workload-identities");
        }),
      ).toBe(true),
    );
    expect(await screen.findByText("Platform workload identities")).toBeVisible();
    expect(screen.getAllByText("Health scheduler").length).toBeGreaterThan(0);
    expect(screen.queryByText(/private-key-value/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Workload identity governance reason"), {
      target: { value: "Complete the scheduled workload credential lifecycle." },
    });

    fireEvent.click(screen.getByRole("button", { name: "Review creation" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("no execution authority");
    fireEvent.click(screen.getByRole("button", { name: "Confirm creation" }));
    await waitFor(() => expect(mutations).toHaveLength(1));
    expect(await screen.findByText("Credential shown once")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Rotate credential" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("two-minute overlap");
    fireEvent.click(screen.getByRole("button", { name: "Confirm rotation" }));
    await waitFor(() => expect(mutations).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Credential shown once")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Revoke credential" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("stops authenticating immediately");
    fireEvent.click(screen.getByRole("button", { name: "Confirm revocation" }));
    await waitFor(() => expect(mutations).toHaveLength(3));

    for (const mutation of mutations) {
      const headers = new Headers(mutation.init?.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf_workload_ui");
      expect(headers.get("Idempotency-Key")).toMatch(
        /^governance-workload-(create|rotate|revoke)-/,
      );
      expect(mutation.init?.body).not.toContain("private-key-value");
    }
    expect(mutations[0]?.url).toMatch(/\/workload-identities$/);
    expect(mutations[1]?.url).toContain("/rotations");
    expect(mutations[2]?.url).toContain("/revocations");
  });

  it("keeps workload governance absent when discovery is forbidden", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve(
        new Response(
          JSON.stringify(url.includes("/identity/me") ? identityResponse : { code: "denied" }),
          {
            status: url.includes("/identity/me") ? 200 : 403,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Security Administrator")).toBeVisible();
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Platform workload identities" }),
      ).not.toBeInTheDocument(),
    );
  });
});
