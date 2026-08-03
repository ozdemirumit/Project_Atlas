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

const storageResponse = {
  data: {
    snapshot_id: "snapshot.storage.lab.001",
    organization_id: "organization.development",
    environment_id: "environment.test",
    site_id: "site.local",
    target_id: "target.hitachi.opscenter.lab",
    data_profile: "synthetic_lab",
    generated_at: "2026-08-03T10:00:00Z",
    assets: [
      {
        asset_id: "asset.storage.lab.g400",
        storage_device_id: "836000123456",
        vendor: "Hitachi Vantara",
        model: "VSP G400",
        serial_number: 123456,
        health: "healthy",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.inventory", "evidence.healthy"],
      },
      {
        asset_id: "asset.storage.lab.b28",
        storage_device_id: "A34000800556",
        vendor: "Hitachi Vantara",
        model: "VSP One B28",
        serial_number: 800556,
        health: "warning",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.inventory", "evidence.warning"],
      },
    ],
    findings: [
      {
        finding_id: "finding.storage.lab.controller-warning",
        asset_id: "asset.storage.lab.b28",
        severity: "warning",
        component: "CTL01",
        summary: "Controller CTL01 reports a vendor warning while its peer reports Normal.",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.warning"],
        status: "open",
      },
    ],
    evidence: [
      {
        reference: "evidence.inventory",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic inventory fixture",
      },
      {
        reference: "evidence.healthy",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic hardware fixture",
      },
      {
        reference: "evidence.warning",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic warning fixture",
      },
    ],
    investigation: {
      investigation_id: "investigation.storage.lab.001",
      title: "VSP One B28 controller warning",
      state: "provisional",
      summary: "A localized controller warning is present. No root cause is confirmed.",
      hypotheses: [
        {
          hypothesis_id: "hypothesis.storage.lab.thermal",
          title: "Localized controller condition",
          state: "possible",
          rationale: "Only CTL01 reports a warning.",
          confidence_basis: "Single documentation-derived health observation",
          evidence_references: ["evidence.warning"],
          contradicting_evidence: [],
        },
      ],
      unknowns: ["The warning duration is unknown."],
      next_checks: ["Repeat the approved C1 hardware-health read."],
      evidence_references: ["evidence.warning"],
      updated_at: "2026-08-03T10:00:00Z",
    },
    report: {
      report_id: "report.storage.lab.001",
      title: "Synthetic storage health assessment",
      generated_at: "2026-08-03T10:00:00Z",
      executive_summary: "One of two synthetic arrays has a controller warning.",
      confirmed_facts: ["Two storage systems are represented."],
      provisional_findings: ["The condition appears localized."],
      unknowns: ["The warning duration is unknown."],
      evidence_references: ["evidence.inventory", "evidence.warning"],
      safety_notice: "Decision support only. No infrastructure change is authorized.",
    },
  },
  meta: {
    correlation_id: "test-storage-correlation",
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
      const payload = url.includes("/identity/me")
        ? identityResponse
        : url.includes("/storage/overview")
          ? storageResponse
          : platformResponse;
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

    expect(screen.getByRole("heading", { name: "Storage estate assessment" })).toBeVisible();
    expect(screen.getByText("Human decision required")).toBeVisible();
    expect(await screen.findByText("test")).toBeVisible();
    expect(await screen.findByText("Local Operator")).toBeVisible();
    expect(await screen.findAllByText("VSP One B28")).not.toHaveLength(0);
    expect(screen.getByText("VSP G400")).toBeVisible();
    expect(screen.getByText("CTL01")).toBeVisible();
    expect(screen.getByText("provisional", { selector: ".state-badge" })).toBeVisible();
    expect(screen.getAllByText("Synthetic lab").length).toBeGreaterThan(0);
    expect(screen.getByText(/No infrastructure change is authorized/)).toBeVisible();
  });
});
