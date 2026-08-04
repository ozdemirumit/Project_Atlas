import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

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
    authorization_decision_id: "decision.configuration.ui",
    effective_role_versions: ["role.platform-operator:v1"],
    effective_assignment_versions: ["assignment.platform-configuration:1"],
  },
};

function configurationPreview(profile = "linux_lab") {
  return {
    data: {
      preview_id: "configuration-preview.ui.001",
      schema_version: "atlas.deployment-configuration-preview.v1",
      release_id: "release.atlas.lab-0.1.0",
      profile,
      organization_id: "organization.enterprise",
      environment_id: "environment.test",
      site_id: "site.local",
      state: "passed",
      configuration_digest: "b".repeat(64),
      fields: [
        {
          path: "api.bind",
          display_value: "127.0.0.1",
          source: "release_default",
          sensitive: false,
        },
        {
          path: "secret_references",
          display_value: "2 opaque references",
          source: "release_default",
          sensitive: true,
        },
      ],
      validations: [
        {
          code: "configuration.secrets.references-only",
          state: "passed",
          summary: "Secrets use opaque references only.",
          evidence: "validated",
          remediation: null,
        },
      ],
      generated_at: "2026-08-04T16:00:00Z",
      correlation_id: "correlation.configuration.ui",
      mutation_authorized: false,
      execution_authorized: false,
    },
  };
}

const preflight = {
  data: {
    report_id: "preflight.ui.plan",
    release_id: "release.atlas.lab-0.1.0",
    release_version: "0.1.0",
    build_id: "build.synthetic.main",
    manifest_digest: "a".repeat(64),
    mode: "offline",
    profile: "linux_lab",
    state: "passed",
    checks: [],
    generated_at: "2026-08-04T16:00:00Z",
    correlation_id: "correlation.plan.preflight",
    mutation_authorized: false,
    execution_authorized: false,
  },
};

const bootstrapPlan = {
  data: {
    plan_id: "bootstrap-plan.ui.001",
    schema_version: "atlas.bootstrap-plan.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    state: "ready",
    plan_digest: "c".repeat(64),
    resume_key: "resume.cccccccccccccccccccccccccccccccc",
    phases: [
      { phase_id: "phase.acquire", sequence: 1, title: "Acquire and verify artifacts", dependencies: [], state: "ready", resumable: true, input_references: ["manifest:aaa"], stop_guidance: "Stop without mutation." },
      { phase_id: "phase.configure", sequence: 2, title: "Render validated configuration", dependencies: ["phase.acquire"], state: "ready", resumable: true, input_references: ["configuration:bbb"], stop_guidance: "Keep the prior valid plan." },
    ],
    generated_at: "2026-08-04T16:00:00Z",
    correlation_id: "correlation.plan.ui",
    mutation_authorized: false,
    execution_authorized: false,
  },
};

const bootstrapState = {
  data: {
    run: {
      run_id: "bootstrap-run.ui-001",
      version: 3,
      state: "active",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      organization_id: "organization.enterprise",
      environment_id: "environment.test",
      site_id: "site.local",
      plan_digest: "c".repeat(64),
      resume_key: "resume.cccccccccccccccccccccccccccccccc",
      configuration_digest: "b".repeat(64),
      phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
      checkpoints: [
        {
          phase_id: "phase.acquire",
          state: "completed",
          safe_output_references: ["artifact.release-manifest-001"],
          recorded_at: "2026-08-04T16:01:00Z",
        },
      ],
      completed_phase_ids: ["phase.acquire"],
      failed_phase_id: null,
      current_phase_id: "phase.configure",
      lease_expires_at: "2026-08-04T16:10:00Z",
      created_at: "2026-08-04T16:00:00Z",
      updated_at: "2026-08-04T16:01:00Z",
    },
    durable: true,
    lease_available: false,
    lease_held_by_current_actor: true,
    execution_authorized: false,
    infrastructure_mutation_authorized: false,
  },
};

const bootstrapInvalidation = {
  data: {
    preview_id: "bootstrap-invalidation.ui-001",
    schema_version: "atlas.bootstrap-invalidation-preview.v1",
    state: "drifted",
    source_run_id: "bootstrap-run.ui-001",
    source_run_version: 3,
    changes: [
      {
        field: "configuration_digest",
        reason_code: "bootstrap.configuration.changed",
        old_reference: `sha256:${"a".repeat(64)}`,
        new_reference: `sha256:${"b".repeat(64)}`,
        earliest_affected_phase_id: "phase.configure",
      },
    ],
    earliest_affected_phase_id: "phase.configure",
    reusable_checkpoint_phase_ids: ["phase.acquire"],
    invalidated_checkpoint_phase_ids: ["phase.configure"],
    downstream_phase_ids: ["phase.configure", "phase.trust"],
    remediation: "Create a new governed plan.",
    generated_at: "2026-08-04T16:05:00Z",
    correlation_id: "correlation.invalidation.ui",
    execution_authorized: false,
    lease_mutation_authorized: false,
    checkpoint_mutation_authorized: false,
    infrastructure_mutation_authorized: false,
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("deployment configuration preview", () => {
  it("shows an authorized redacted preview and follows the selected profile", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const requestBodies: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        const body = typeof init?.body === "string" ? init.body : "";
        requestBodies.push(body);
        const profile = body.includes('"profile":"developer"') ? "developer" : "linux_lab";
        return Promise.resolve(
          new Response(JSON.stringify(configurationPreview(profile)), { status: 200 }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Versioned deployment preview")).toBeVisible();
    expect(screen.getByText("Secrets use opaque references only.")).toBeVisible();
    expect(screen.getByText(/No file write, secret provisioning, port change/)).toBeVisible();
    expect(screen.queryByText(/top-secret-value/)).not.toBeInTheDocument();
    await waitFor(() =>
      expect(requestBodies.some((body) => body.includes('"profile":"linux_lab"'))).toBe(true),
    );
  });

  it("keeps forbidden or malformed discovery absent", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        return Promise.resolve(new Response(JSON.stringify({ data: { state: "passed" } }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
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
        screen.queryByRole("heading", { name: "Versioned deployment preview" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("shows the exact-input non-executing bootstrap plan", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(await screen.findByText("Ordered deployment phases")).toBeVisible();
    expect(screen.getByText("Acquire and verify artifacts")).toBeVisible();
    expect(screen.getByText(/No phase, command, rollback/)).toBeVisible();
  });

  it("shows durable checkpoint progress without exposing a lease owner or taking action", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapState), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(await screen.findByText("Resume and lease state")).toBeVisible();
    expect(screen.getByText("Held by this session")).toBeVisible();
    expect(screen.getByText("phase.configure")).toBeVisible();
    expect(screen.getByText(/loading this view never claims a lease/)).toBeVisible();
    expect(screen.queryByText(/subject\.lease-owner/)).not.toBeInTheDocument();
  });

  it("keeps malformed bootstrap state absent", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(
          new Response(JSON.stringify({ data: { run: { version: "unsafe" } } }), { status: 200 }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(await screen.findByText("Platform Operator")).toBeVisible();
    await waitFor(() => expect(screen.queryByText("Resume and lease state")).not.toBeInTheDocument());
  });

  it("shows deterministic checkpoint invalidation without mutation controls", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-invalidation-preview")) return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(await screen.findByText("Checkpoint invalidation preview")).toBeVisible();
    expect(screen.getByText("bootstrap.configuration.changed")).toBeVisible();
    expect(screen.getByText(/confirmed plan update changes checkpoint metadata only/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /invalidate/i })).not.toBeInTheDocument();
  });

  it("requires explicit confirmation and shows the applied checkpoint metadata boundary", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const rebaseRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-invalidation-preview")) return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      if (url.includes("/bootstrap-state/current")) return Promise.resolve(new Response(JSON.stringify(bootstrapState), { status: 200 }));
      if (url.includes("/bootstrap-state/bootstrap-run.ui-001/rebase")) {
        const headers = new Headers(init?.headers);
        rebaseRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  run_id: "bootstrap-run.ui-001",
                  version: 4,
                  state: "active",
                  completed_phase_ids: ["phase.acquire"],
                  current_phase_id: "phase.configure",
                },
                replayed: false,
                preserved_checkpoint_phase_ids: ["phase.acquire"],
                invalidated_checkpoint_phase_ids: ["phase.configure"],
                invalidation_reason_codes: ["bootstrap.configuration.changed"],
                earliest_affected_phase_id: "phase.configure",
                execution_authorized: false,
                lease_mutation_authorized: false,
                infrastructure_mutation_authorized: false,
              },
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "Review plan update" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm checkpoint update" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review justification"), {
      target: { value: "Reviewed configuration correction for the lab deployment." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Plan metadata updated to revision 4")).toBeVisible();
    expect(screen.getByText(/Preserved: phase.acquire. Invalidated: phase.configure/)).toBeVisible();
    expect(rebaseRequests).toHaveLength(1);
    const [rebaseRequest] = rebaseRequests;
    expect(rebaseRequest).toBeDefined();
    expect(rebaseRequest?.body).toContain("Reviewed configuration correction");
    expect(rebaseRequest?.idempotencyKey).toMatch(/^bootstrap-rebase\.3\.3\./);
    expect(screen.queryByRole("button", { name: /run phase|execute|rollback/i })).not.toBeInTheDocument();
  });

  it("keeps malformed invalidation evidence absent", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-invalidation-preview")) return Promise.resolve(new Response(JSON.stringify({ data: { state: "drifted", execution_authorized: true } }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(await screen.findByText("Ordered deployment phases")).toBeVisible();
    await waitFor(() => expect(screen.queryByText("Checkpoint invalidation preview")).not.toBeInTheDocument());
  });
});
