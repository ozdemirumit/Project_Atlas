import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const identity = {
  data: {
    subject_id: "subject.development.operator",
    display_name: "MCP Builder Reviewer",
    subject_kind: "human",
    organization_id: "organization.development",
    role_ids: ["role.development.operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.ldap.test",
      method: "ldap",
      assurance_level: "multi_factor",
      authenticated_at: "2026-08-05T12:00:00Z",
    },
    scope: {
      organization_id: "organization.development",
      environment_id: "environment.test",
      site_id: "site.local",
      domain_id: "domain.identity",
      resource_id: "resource.identity.self",
      capability_class: "C0",
    },
    authorization_decision_id: "decision.mcp-builder.ui",
    effective_role_versions: ["role.development.operator:v1"],
    effective_assignment_versions: ["assignment.development.mcp-builder-create:1"],
  },
};

const project = {
  data: {
    project_id: "mcp-builder-project.aaaaaaaaaaaaaaaaaaaaaaaa",
    schema_version: "atlas.mcp-builder-project.v1",
    version: 1,
    state: "analyzed",
    vendor: "Atlas Synthetic",
    product: "Storage Lab",
    intended_product_versions: ["1.0"],
    source_authority: "Vendor documentation portal",
    source_owner: "Platform engineering",
    documentation_version: "1.0",
    publication_date: "2026-08-05",
    license_id: "license.internal-review",
    redistribution_allowed: false,
    classification: "internal",
    openapi_version: "3.1.0",
    api_title: "Synthetic Storage API",
    api_version: "1.0",
    source_digest: "b".repeat(64),
    source_size_bytes: 640,
    declared_servers: ["https://lab-api.example.invalid"],
    capability_candidates: [
      {
        candidate_id: "builder-capability.read-systems",
        operation_id: "getSystems",
        method: "get",
        path: "/systems",
        summary: "Read synthetic storage systems",
        citation: `openapi://${"b".repeat(64)}/paths/~1systems/get`,
        proposed_capability_class: "C1",
        clarification_codes: [],
        generation_blocked: false,
      },
    ],
    findings: [],
    canonical_digest: "c".repeat(64),
    analyzed_at: "2026-08-05T12:00:00Z",
    reused: false,
    synthetic_or_lab_only: true,
    generated_artifact_created: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MCP Builder workspace", () => {
  it("submits bounded OpenAPI evidence and shows only analysis results", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "mcp-builder-ui-001" });
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.endsWith("/api/v1/mcp-builder/projects")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(project), { status: 201 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ code: "authorization_denied" }), { status: 403 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Connectors" }));
    fireEvent.change(screen.getByLabelText("Vendor"), {
      target: { value: "Atlas Synthetic" },
    });
    fireEvent.change(screen.getByLabelText("Product"), {
      target: { value: "Storage Lab" },
    });
    fireEvent.change(screen.getByLabelText("Product version"), {
      target: { value: "1.0" },
    });
    fireEvent.change(screen.getByLabelText("Documentation version"), {
      target: { value: "1.0" },
    });
    fireEvent.change(screen.getByLabelText("Source authority"), {
      target: { value: "Vendor documentation portal" },
    });
    fireEvent.change(screen.getByLabelText("Source owner"), {
      target: { value: "Platform engineering" },
    });
    fireEvent.change(screen.getByLabelText("License identifier"), {
      target: { value: "license.internal-review" },
    });
    const source = JSON.stringify({ openapi: "3.1.0", info: {}, paths: {} });
    const file = new File([source], "storage-openapi.json", {
      type: "application/json",
    });
    Object.defineProperty(file, "text", { value: () => Promise.resolve(source) });
    fireEvent.change(screen.getByLabelText(/Select OpenAPI JSON/), {
      target: { files: [file] },
    });

    const analyze = screen.getByRole("button", { name: "Analyze source" });
    await waitFor(() => expect(analyze).toBeEnabled());
    fireEvent.click(analyze);

    expect(await screen.findByText("Synthetic Storage API")).toBeVisible();
    expect(screen.getByText("getSystems")).toBeVisible();
    expect(screen.getByText("Read-only candidate")).toBeVisible();
    expect(screen.queryByRole("button", { name: /generate|install|execute/i })).not.toBeInTheDocument();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("mcp-builder.mcp-builder-ui-001");
    const body = JSON.parse(requests[0]?.body ?? "{}") as Record<string, unknown>;
    expect(body.source_document).toBe(source);
    expect(body.confirmed_synthetic_or_lab_only).toBe(true);
    expect(body).not.toHaveProperty("connector_enabled");
  });
});
