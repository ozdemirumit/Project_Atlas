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

const checkpoint = {
  data: {
    checkpoint_id: "mcp-builder-design.dddddddddddddddddddddddd",
    schema_version: "atlas.mcp-builder-design-checkpoint.v1",
    version: 1,
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    reviewer_id: identity.data.subject_id,
    connector_boundary: "Read-only inventory and health evidence.",
    target_products: [project.data.product],
    network_destinations: project.data.declared_servers,
    configuration_keys: ["config.vendor-endpoint"],
    secret_reference_ids: ["secret.vendor-api-key"],
    entity_mappings: [
      { source_entity: "vendor.storage-system", atlas_entity: "atlas.storage-system" },
    ],
    capability_decisions: [
      {
        candidate_id: project.data.capability_candidates[0]?.candidate_id,
        decision: "include",
        analyzed_class: "C1",
        confirmed_class: "C1",
        required_permission: "storage.system.read",
        rationale: "Confirmed as an authenticated bounded read.",
        generation_eligible: true,
      },
    ],
    canonical_digest: "d".repeat(64),
    created_at: "2026-08-05T12:10:00Z",
    ready_for_generation_design: true,
    generated_artifact_created: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const generation = {
  data: {
    generation_id: "mcp-builder-generation.eeeeeeeeeeeeeeeeeeeeeeee",
    schema_version: "atlas.mcp-builder-generation.v1",
    version: 1,
    state: "quarantined",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    requested_by: identity.data.subject_id,
    language_profile: "atlas.python312.v1",
    template_version: "mcp-builder-python.v1",
    artifact_digest: "e".repeat(64),
    artifact_size_bytes: 214,
    files: [
      {
        relative_path: "README.md",
        media_type: "text/markdown",
        sha256: "f".repeat(64),
        size_bytes: 214,
        source_candidate_ids: [],
      },
    ],
    canonical_digest: "a".repeat(64),
    created_at: "2026-08-05T12:20:00Z",
    artifact_published: true,
    generated_artifact_created: true,
    validation_completed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    subprocess_invoked: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const generatedFile = {
  data: {
    generation_id: generation.data.generation_id,
    state: "quarantined",
    artifact_digest: generation.data.artifact_digest,
    file: generation.data.files[0],
    content: "# Quarantined Atlas Connector Draft\n\nNo runtime trust.\n",
    content_verified: true,
    quarantined: true,
    runtime_trust_granted: false,
    execution_authorized: false,
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MCP Builder workspace", () => {
  it("records design evidence and creates a quarantined scaffold with verified preview", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "mcp-builder-ui-001" });
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const designRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const generationRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
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
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/design-checkpoints`)) {
        const headers = new Headers(init?.headers);
        designRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(checkpoint), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/generations`)) {
        const headers = new Headers(init?.headers);
        generationRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(generation), { status: 201 }));
      }
      if (
        url.endsWith(
          `/mcp-builder/projects/${project.data.project_id}/generation/files/README.md`,
        )
      ) {
        return Promise.resolve(new Response(JSON.stringify(generatedFile), { status: 200 }));
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
    expect(screen.getAllByText("getSystems")).toHaveLength(2);
    expect(screen.getByText("Read-only candidate")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Decision" })).toHaveValue("include");
    fireEvent.click(
      screen.getByLabelText(/I confirm this checkpoint records design evidence only/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm design checkpoint" }));

    expect(await screen.findByText("Design checkpoint recorded")).toBeVisible();
    expect(screen.getByText(checkpoint.data.checkpoint_id)).toBeVisible();
    expect(screen.getByText("Create a Python review scaffold")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I authorize deterministic file creation inside quarantine/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create quarantined scaffold" }));

    expect(await screen.findByText(generation.data.generation_id)).toBeVisible();
    expect(screen.getByText("No runtime trust.", { exact: false })).toBeVisible();
    expect(screen.getByText("Not run")).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|execute|register|enable/i })).not.toBeInTheDocument();
    expect(requests).toHaveLength(1);
    expect(designRequests).toHaveLength(1);
    expect(generationRequests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("mcp-builder.mcp-builder-ui-001");
    const body = JSON.parse(requests[0]?.body ?? "{}") as Record<string, unknown>;
    expect(body.source_document).toBe(source);
    expect(body.confirmed_synthetic_or_lab_only).toBe(true);
    expect(body).not.toHaveProperty("connector_enabled");
    expect(designRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-design.mcp-builder-ui-001",
    );
    const designBody = JSON.parse(designRequests[0]?.body ?? "{}") as Record<string, unknown>;
    expect(designBody.project_digest).toBe(project.data.canonical_digest);
    expect(designBody.network_destinations).toEqual(project.data.declared_servers);
    expect(designBody).not.toHaveProperty("runtime_trust_granted");
    expect(designBody).not.toHaveProperty("generated_artifact_created");
    expect(generationRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-generation.mcp-builder-ui-001",
    );
    const generationBody = JSON.parse(
      generationRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(generationBody.project_digest).toBe(project.data.canonical_digest);
    expect(generationBody.checkpoint_digest).toBe(checkpoint.data.canonical_digest);
    expect(generationBody.language_profile).toBe("atlas.python312.v1");
    expect(generationBody.acknowledged_quarantine).toBe(true);
    expect(generationBody).not.toHaveProperty("runtime_trust_granted");
    expect(generationBody).not.toHaveProperty("execute");
  });
});
