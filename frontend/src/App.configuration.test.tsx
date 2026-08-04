import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const bootstrapTrustPlan = {
  data: {
    schema_version: "atlas.bootstrap-trust-plan.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    state: "passed",
    result_code: "bootstrap.trust-plan.passed",
    anchors: [
      {
        anchor_id: "trust-anchor.atlas-synthetic-lab-root",
        source_id: "trust-source.synthetic-lab",
        purpose: "internal_service",
        subject_summary: "CN=Atlas Synthetic Lab Root",
        sha256: "e".repeat(64),
        not_before: "2026-08-04T16:31:32Z",
        not_after: "2036-08-01T16:31:32Z",
        non_production_only: true,
      },
    ],
    workload_identities: [
      {
        identity_id: "workload.atlas-api.primary",
        service_id: "service.atlas-api",
        instance_id: "instance.primary",
        owner_subject_id: "subject.platform.security",
        purpose: "Authenticate the primary Atlas API workload to internal services.",
        environment_id: "environment.test",
        audiences: ["audience.atlas-internal"],
        secret_reference_ids: ["secret.workload.atlas-api"],
      },
    ],
    generated_at: "2026-08-04T16:02:00Z",
    private_key_material_present: false,
    credential_material_present: false,
    infrastructure_mutation_authorized: false,
    ai_operation_authorized: false,
  },
};

const bootstrapDataPlan = {
  data: {
    schema_version: "atlas.bootstrap-data-plan.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    migration_artifact_digest: "4".repeat(64),
    data_plan_digest: "5".repeat(64),
    target_id: "target.atlas-synthetic-database.primary",
    target_kind: "target-kind.synthetic-file-database",
    current_revision: "base",
    target_revision: "bootstrap",
    target_state: "empty",
    state: "passed",
    result_code: "bootstrap.data-plan.passed",
    migrations: [
      {
        migration_id: "migration.atlas.metadata",
        sequence: 1,
        sha256: "6".repeat(64),
        from_revision: "base",
        to_revision: "metadata",
        compatibility: "expand",
        reversible: true,
        destructive: false,
        recovery_code: "recovery.synthetic-state-remove",
        expected_object_count: 4,
      },
      {
        migration_id: "migration.atlas.core",
        sequence: 2,
        sha256: "7".repeat(64),
        from_revision: "metadata",
        to_revision: "core",
        compatibility: "expand",
        reversible: true,
        destructive: false,
        recovery_code: "recovery.synthetic-state-remove",
        expected_object_count: 6,
      },
      {
        migration_id: "migration.atlas.bootstrap",
        sequence: 3,
        sha256: "8".repeat(64),
        from_revision: "core",
        to_revision: "bootstrap",
        compatibility: "expand",
        reversible: true,
        destructive: false,
        recovery_code: "recovery.synthetic-state-remove",
        expected_object_count: 4,
      },
    ],
    backup_applicability: "not_applicable_clean_install",
    generated_at: "2026-08-04T16:04:00Z",
    database_url_present: false,
    credential_material_present: false,
    sql_text_present: false,
    destructive_migration_authorized: false,
    backup_operation_authorized: false,
    service_deployment_authorized: false,
    infrastructure_mutation_authorized: false,
    ai_operation_authorized: false,
  },
};

const bootstrapServicePlan = {
  data: {
    schema_version: "atlas.bootstrap-service-plan.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    data_plan_digest: "5".repeat(64),
    migration_artifact_digest: "4".repeat(64),
    service_plan_digest: "d".repeat(64),
    target_id: "target.atlas-synthetic-runtime.primary",
    target_kind: "target-kind.synthetic-file-runtime",
    target_state: "empty",
    state: "passed",
    result_code: "bootstrap.service-plan.passed",
    services: [
      {
        service_id: "service.atlas-api",
        sequence: 1,
        artifact_id: "artifact.backend.image",
        artifact_sha256: "1".repeat(64),
        dependencies: [],
        workload_identity_id: "workload.atlas-api.primary",
        endpoint_class: "private",
        cpu_limit_millicores: 1000,
        memory_limit_mb: 1024,
        startup_probe_id: "probe.atlas-api.startup",
        readiness_probe_id: "probe.atlas-api.readiness",
        liveness_probe_id: "probe.atlas-api.liveness",
        run_as_root: false,
        privileged: false,
        arbitrary_public_egress: false,
      },
      {
        service_id: "service.atlas-web",
        sequence: 2,
        artifact_id: "artifact.frontend.image",
        artifact_sha256: "2".repeat(64),
        dependencies: ["service.atlas-api"],
        workload_identity_id: null,
        endpoint_class: "private",
        cpu_limit_millicores: 500,
        memory_limit_mb: 256,
        startup_probe_id: "probe.atlas-web.startup",
        readiness_probe_id: "probe.atlas-web.readiness",
        liveness_probe_id: "probe.atlas-web.liveness",
        run_as_root: false,
        privileged: false,
        arbitrary_public_egress: false,
      },
    ],
    generated_at: "2026-08-04T16:05:00Z",
    real_process_mutation_authorized: false,
    container_runtime_mutation_authorized: false,
    operating_system_service_mutation_authorized: false,
    network_mutation_authorized: false,
    secret_mutation_authorized: false,
    external_data_mutation_authorized: false,
    infrastructure_mutation_authorized: false,
    ai_operation_authorized: false,
  },
};

const bootstrapIdentityPlan = {
  data: {
    schema_version: "atlas.bootstrap-identity-plan.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    data_plan_digest: "5".repeat(64),
    service_plan_digest: "d".repeat(64),
    identity_plan_digest: "9".repeat(64),
    target_id: "target.atlas-synthetic-identity.primary",
    target_kind: "target-kind.synthetic-file-identity",
    target_state: "empty",
    bootstrap_administrator_subject_id: "subject.bootstrap-administrator.primary",
    credential_verifier_reference_id: "secret-reference.bootstrap-administrator.verifier",
    credential_replacement_required: true,
    recovery_identity_id: "identity.recovery-administrator.primary",
    recovery_seal_required: true,
    provider_id: "provider.ldap.enterprise",
    provider_protocol: "ldaps",
    pilot_subject_id: "subject.pilot.platform-administrator",
    group_mappings: [
      {
        mapping_id: "mapping.platform-administrators",
        directory_group_reference: "directory-group.platform-administrators",
        role_ids: ["role.platform-administrator"],
      },
      {
        mapping_id: "mapping.security-administrators",
        directory_group_reference: "directory-group.security-administrators",
        role_ids: ["role.security-administrator"],
      },
    ],
    state: "passed",
    result_code: "bootstrap.identity-plan.passed",
    generated_at: "2026-08-04T16:06:00Z",
    credential_material_present: false,
    directory_mutation_authorized: false,
    provider_activation_authorized: false,
    account_mutation_authorized: false,
    session_or_token_mutation_authorized: false,
    infrastructure_mutation_authorized: false,
    ai_operation_authorized: false,
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
      artifact_acquisition: null,
      configuration_rendering: null,
      trust_provisioning: null,
      data_initialization: null,
      service_deployment: null,
      identity_handoff: null,
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
  vi.unstubAllGlobals();
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

  it("requires confirmation and reports bounded artifact acquisition evidence", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "acquisition-request-001" });
    const acquireState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 1,
          checkpoints: [],
          completed_phase_ids: [],
          current_phase_id: "phase.acquire",
          artifact_acquisition: null,
          configuration_rendering: null,
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-state/current")) return Promise.resolve(new Response(JSON.stringify(acquireState), { status: 200 }));
      if (url.includes("/phases/acquire")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-acquire-001",
          phase_id: "phase.acquire",
          release_id: "release.atlas.lab-0.1.0",
          manifest_digest: "a".repeat(64),
          mode: "offline",
          preflight_report_id: "preflight.ui.plan",
          state: "completed",
          result_code: "bootstrap.artifact.completed",
          started_at: "2026-08-04T16:02:00Z",
          completed_at: "2026-08-04T16:02:01Z",
          evidence: [
            {
              artifact_id: "artifact.backend.image",
              sha256: "d".repeat(64),
              size_bytes: 13,
              disposition: "published",
            },
          ],
          artifact_count: 1,
          total_bytes: 13,
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...acquireState.data.run,
                  version: 3,
                  checkpoints: [
                    {
                      phase_id: "phase.acquire",
                      state: "completed",
                      safe_output_references: ["artifact.receipt.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                      recorded_at: "2026-08-04T16:02:01Z",
                    },
                  ],
                  completed_phase_ids: ["phase.acquire"],
                  current_phase_id: "phase.configure",
                  updated_at: "2026-08-04T16:02:01Z",
                  artifact_acquisition: execution,
                  configuration_rendering: null,
                },
                execution,
                replayed: false,
                artifact_storage_mutation_performed: true,
                configuration_mutation_authorized: false,
                service_deployment_authorized: false,
                infrastructure_mutation_authorized: false,
                ai_operation_authorized: false,
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

    fireEvent.click(await screen.findByRole("button", { name: "Review acquisition" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm acquisition" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Change justification"), {
      target: { value: "Acquire approved immutable artifacts for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Artifact acquisition completed")).toBeVisible();
    expect(screen.getByText("artifact.backend.image")).toBeVisible();
    expect(screen.getByText("published")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain("Acquire approved immutable artifacts");
    expect(requests[0]?.idempotencyKey).toBe(
      "bootstrap-acquire.1.acquisition-request-001",
    );
    expect(screen.queryByRole("button", { name: /deploy|rollback|run service/i })).not.toBeInTheDocument();
  });

  it("initializes an exact bootstrap lease before offering phase execution", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "lease-request-001" });
    const emptyState = {
      data: {
        run: null,
        durable: true,
        lease_available: true,
        lease_held_by_current_actor: false,
        execution_authorized: false,
        infrastructure_mutation_authorized: false,
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-state/current")) return Promise.resolve(new Response(JSON.stringify(emptyState), { status: 200 }));
      if (url.endsWith("/bootstrap-state/claims")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...bootstrapState.data.run,
                  version: 1,
                  checkpoints: [],
                  completed_phase_ids: [],
                  current_phase_id: "phase.acquire",
                  artifact_acquisition: null,
                  configuration_rendering: null,
                },
                replayed: false,
                reclaimed_expired_lease: false,
                execution_authorized: false,
                infrastructure_mutation_authorized: false,
              },
            }),
            { status: 201 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);

    expect(screen.queryByRole("button", { name: "Review acquisition" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Review lease" }));
    const confirm = screen.getByRole("button", { name: "Confirm lease" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Lease justification"), {
      target: { value: "Coordinate the approved lab bootstrap artifact phase." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Coordination lease established")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain("Coordinate the approved lab bootstrap");
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-claim.0.lease-request-001");
  });

  it("requires confirmation and reports bounded configuration rendering evidence", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "configuration-request-001" });
    const artifactExecution = {
      execution_id: "phase-execution.ui-acquire-completed",
      phase_id: "phase.acquire",
      release_id: "release.atlas.lab-0.1.0",
      manifest_digest: "a".repeat(64),
      mode: "offline",
      preflight_report_id: "preflight.ui.plan",
      state: "completed",
      result_code: "bootstrap.artifact.completed",
      started_at: "2026-08-04T16:01:00Z",
      completed_at: "2026-08-04T16:01:01Z",
      evidence: [
        {
          artifact_id: "artifact.backend.image",
          sha256: "d".repeat(64),
          size_bytes: 13,
          disposition: "published",
        },
      ],
      artifact_count: 1,
      total_bytes: 13,
    };
    const configureState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          artifact_acquisition: artifactExecution,
          configuration_rendering: null,
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      if (url.includes("/release-preflight")) return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      if (url.includes("/deployment-configuration/preview")) return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      if (url.includes("/bootstrap-plan")) return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      if (url.includes("/bootstrap-state/current")) return Promise.resolve(new Response(JSON.stringify(configureState), { status: 200 }));
      if (url.includes("/bootstrap-invalidation/preview")) return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      if (url.includes("/phases/configure")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-configure-001",
          phase_id: "phase.configure",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_schema_version: "atlas.deployment-configuration.v1",
          configuration_digest: "b".repeat(64),
          state: "completed",
          result_code: "bootstrap.configuration.completed",
          started_at: "2026-08-04T16:02:00Z",
          completed_at: "2026-08-04T16:02:01Z",
          evidence: [
            {
              file_id: "configuration.effective",
              sha256: "e".repeat(64),
              size_bytes: 684,
              disposition: "published",
            },
          ],
          file_count: 1,
          total_bytes: 684,
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...configureState.data.run,
                  version: 5,
                  checkpoints: [
                    ...configureState.data.run.checkpoints,
                    {
                      phase_id: "phase.configure",
                      state: "completed",
                      safe_output_references: [`result.configuration.${"b".repeat(32)}`],
                      recorded_at: "2026-08-04T16:02:01Z",
                    },
                  ],
                  completed_phase_ids: ["phase.acquire", "phase.configure"],
                  current_phase_id: "phase.trust",
                  updated_at: "2026-08-04T16:02:01Z",
                  configuration_rendering: execution,
                },
                execution,
                replayed: false,
                configuration_storage_mutation_performed: true,
                trust_mutation_authorized: false,
                secret_mutation_authorized: false,
                data_mutation_authorized: false,
                service_deployment_authorized: false,
                infrastructure_mutation_authorized: false,
                ai_operation_authorized: false,
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

    fireEvent.click(await screen.findByRole("button", { name: "Review configuration" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm configuration" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Change justification"), {
      target: { value: "Render the approved effective configuration for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Configuration rendering completed")).toBeVisible();
    const fileEvidence = screen.getByText("configuration.effective");
    expect(fileEvidence).toBeVisible();
    expect(within(fileEvidence.parentElement!).getByText("published")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"overlay":{}');
    expect(requests[0]?.body).toContain("Render the approved effective configuration");
    expect(requests[0]?.idempotencyKey).toBe(
      "bootstrap-configure.3.configuration-request-001",
    );
    expect(screen.queryByRole("button", { name: /provision trust|deploy service|rollback/i })).not.toBeInTheDocument();
  });

  it("requires confirmation and reports bounded public trust evidence", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "trust-request-001" });
    const configurationExecution = {
      execution_id: "phase-execution.ui-configure-completed",
      phase_id: "phase.configure",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_schema_version: "atlas.deployment-configuration.v1",
      configuration_digest: "b".repeat(64),
      state: "completed",
      result_code: "bootstrap.configuration.completed",
      started_at: "2026-08-04T16:02:00Z",
      completed_at: "2026-08-04T16:02:01Z",
      evidence: [
        {
          file_id: "configuration.effective",
          sha256: "d".repeat(64),
          size_bytes: 684,
          disposition: "published",
        },
      ],
      file_count: 1,
      total_bytes: 684,
    };
    const trustState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 5,
          checkpoints: [
            ...bootstrapState.data.run.checkpoints,
            {
              phase_id: "phase.configure",
              state: "completed",
              safe_output_references: [`result.configuration.${"b".repeat(32)}`],
              recorded_at: "2026-08-04T16:02:01Z",
            },
          ],
          completed_phase_ids: ["phase.acquire", "phase.configure"],
          current_phase_id: "phase.trust",
          configuration_rendering: configurationExecution,
          trust_provisioning: null,
          data_initialization: null,
          service_deployment: null,
          identity_handoff: null,
          updated_at: "2026-08-04T16:02:01Z",
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/release-preflight")) {
        return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        return Promise.resolve(
          new Response(JSON.stringify(configurationPreview()), { status: 200 }),
        );
      }
      if (url.includes("/bootstrap-trust-plan/preview")) {
        return Promise.resolve(
          new Response(JSON.stringify(bootstrapTrustPlan), { status: 200 }),
        );
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(trustState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(
          new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }),
        );
      }
      if (url.includes("/phases/trust")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-trust-001",
          phase_id: "phase.trust",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_schema_version: "atlas.bootstrap-trust-plan.v1",
          trust_plan_digest: "f".repeat(64),
          state: "completed",
          result_code: "bootstrap.trust.completed",
          started_at: "2026-08-04T16:03:00Z",
          completed_at: "2026-08-04T16:03:01Z",
          anchor_count: 1,
          workload_identity_count: 1,
          evidence: [
            {
              file_id: "trust.bundle",
              sha256: "1".repeat(64),
              size_bytes: 1280,
              disposition: "published",
            },
            {
              file_id: "trust.workload-identities",
              sha256: "2".repeat(64),
              size_bytes: 720,
              disposition: "published",
            },
          ],
          file_count: 2,
          total_bytes: 2000,
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...trustState.data.run,
                  version: 7,
                  checkpoints: [
                    ...trustState.data.run.checkpoints,
                    {
                      phase_id: "phase.trust",
                      state: "completed",
                      safe_output_references: [`result.trust.${"f".repeat(32)}`],
                      recorded_at: "2026-08-04T16:03:01Z",
                    },
                  ],
                  completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
                  current_phase_id: null,
                  trust_provisioning: execution,
                  updated_at: "2026-08-04T16:03:01Z",
                },
                execution,
                replayed: false,
                trust_storage_mutation_performed: true,
                private_key_mutation_performed: false,
                secret_value_mutation_performed: false,
                data_mutation_authorized: false,
                service_deployment_authorized: false,
                infrastructure_mutation_authorized: false,
                ai_operation_authorized: false,
              },
            }),
            { status: 200 },
          ),
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

    fireEvent.click(await screen.findByRole("button", { name: "Review trust" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm trust" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Trust justification"), {
      target: { value: "Publish the approved public trust metadata for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Trust provisioning completed")).toBeVisible();
    const bundleEvidence = screen.getByText("trust.bundle");
    expect(bundleEvidence).toBeVisible();
    expect(within(bundleEvidence.parentElement!).getByText("published")).toBeVisible();
    expect(screen.getByText("trust.workload-identities")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"trust_plan_digest":"' + "f".repeat(64));
    expect(requests[0]?.body).toContain("Publish the approved public trust metadata");
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-trust.5.trust-request-001");
    expect(
      screen.queryByText(/BEGIN PRIVATE KEY|raw-token-value|top-secret/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /deploy service|initialize data|rollback/i }),
    ).not.toBeInTheDocument();
  });

  it("requires confirmation and reports bounded schema initialization evidence", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "data-request-001" });
    const configurationExecution = {
      execution_id: "phase-execution.ui-configure-completed",
      phase_id: "phase.configure",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_schema_version: "atlas.deployment-configuration.v1",
      configuration_digest: "b".repeat(64),
      state: "completed",
      result_code: "bootstrap.configuration.completed",
      started_at: "2026-08-04T16:02:00Z",
      completed_at: "2026-08-04T16:02:01Z",
      evidence: [],
      file_count: 1,
      total_bytes: 684,
    };
    const trustExecution = {
      execution_id: "phase-execution.ui-trust-completed",
      phase_id: "phase.trust",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_schema_version: "atlas.bootstrap-trust-plan.v1",
      trust_plan_digest: "f".repeat(64),
      state: "completed",
      result_code: "bootstrap.trust.completed",
      started_at: "2026-08-04T16:03:00Z",
      completed_at: "2026-08-04T16:03:01Z",
      anchor_count: 1,
      workload_identity_count: 1,
      evidence: [],
      file_count: 2,
      total_bytes: 2000,
    };
    const dataState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 7,
          phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services"],
          checkpoints: [
            ...bootstrapState.data.run.checkpoints,
            {
              phase_id: "phase.configure",
              state: "completed",
              safe_output_references: [`result.configuration.${"b".repeat(32)}`],
              recorded_at: "2026-08-04T16:02:01Z",
            },
            {
              phase_id: "phase.trust",
              state: "completed",
              safe_output_references: [`result.trust.${"f".repeat(32)}`],
              recorded_at: "2026-08-04T16:03:01Z",
            },
          ],
          completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
          current_phase_id: "phase.data",
          configuration_rendering: configurationExecution,
          trust_provisioning: trustExecution,
          data_initialization: null,
          service_deployment: null,
          identity_handoff: null,
          updated_at: "2026-08-04T16:03:01Z",
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/release-preflight")) {
        return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      }
      if (url.includes("/bootstrap-trust-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapTrustPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-data-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapDataPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(dataState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/data")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-data-001",
          phase_id: "phase.data",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_schema_version: "atlas.bootstrap-data-plan.v1",
          data_plan_digest: "5".repeat(64),
          migration_artifact_digest: "4".repeat(64),
          target_id: "target.atlas-synthetic-database.primary",
          from_revision: "base",
          to_revision: "bootstrap",
          state: "completed",
          result_code: "bootstrap.data.completed",
          started_at: "2026-08-04T16:04:00Z",
          completed_at: "2026-08-04T16:04:01Z",
          migration_count: 3,
          verified_object_count: 14,
          lock_acquired: true,
          backup_applicability: "not_applicable_clean_install",
          evidence: [
            {
              evidence_id: "data.schema-state",
              sha256: "9".repeat(64),
              size_bytes: 1240,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...dataState.data.run,
                  version: 9,
                  checkpoints: [
                    ...dataState.data.run.checkpoints,
                    {
                      phase_id: "phase.data",
                      state: "completed",
                      safe_output_references: [`result.data.${"5".repeat(32)}`],
                      recorded_at: "2026-08-04T16:04:01Z",
                    },
                  ],
                  completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data"],
                  current_phase_id: "phase.services",
                  data_initialization: execution,
                  service_deployment: null,
                  identity_handoff: null,
                  updated_at: "2026-08-04T16:04:01Z",
                },
                execution,
                replayed: false,
                schema_state_mutation_performed: true,
                external_database_provisioning_performed: false,
                destructive_migration_performed: false,
                backup_operation_performed: false,
                service_deployment_authorized: false,
                infrastructure_mutation_authorized: false,
                ai_operation_authorized: false,
              },
            }),
            { status: 200 },
          ),
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

    fireEvent.click(await screen.findByRole("button", { name: "Review data" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText("Confirm clean data-schema initialization")).toBeVisible();
    expect(screen.getByText("migration.atlas.metadata")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm data" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Data justification"), {
      target: { value: "Initialize the reviewed synthetic schema state for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Data initialization completed")).toBeVisible();
    const evidence = screen.getByText("data.schema-state");
    expect(evidence).toBeVisible();
    expect(within(evidence.parentElement!).getByText("published")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"data_plan_digest":"' + "5".repeat(64));
    expect(requests[0]?.body).toContain('"expected_target_state":"empty"');
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-data.7.data-request-001");
    expect(screen.queryByText(/database_url|credential material|sql text/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /deploy services|run backup|provision database|rollback data/i }),
    ).not.toBeInTheDocument();
  });

  it("reviews synthetic services and reports readiness without runtime controls", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "services-request-001" });
    const dataExecution = {
      execution_id: "phase-execution.ui-data-completed",
      phase_id: "phase.data",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_plan_digest: "f".repeat(64),
      data_schema_version: "atlas.bootstrap-data-plan.v1",
      data_plan_digest: "5".repeat(64),
      migration_artifact_digest: "4".repeat(64),
      target_id: "target.atlas-synthetic-database.primary",
      from_revision: "base",
      to_revision: "bootstrap",
      state: "completed",
      result_code: "bootstrap.data.completed",
      started_at: "2026-08-04T16:04:00Z",
      completed_at: "2026-08-04T16:04:01Z",
      migration_count: 3,
      verified_object_count: 14,
      lock_acquired: true,
      backup_applicability: "not_applicable_clean_install",
      evidence: [],
    };
    const servicesState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 9,
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
          ],
          checkpoints: [
            ...bootstrapState.data.run.checkpoints,
            ...["phase.configure", "phase.trust", "phase.data"].map((phaseId) => ({
              phase_id: phaseId,
              state: "completed",
              safe_output_references: [`result.${phaseId.slice(6)}.verified`],
              recorded_at: "2026-08-04T16:04:01Z",
            })),
          ],
          completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data"],
          current_phase_id: "phase.services",
          configuration_rendering: null,
          trust_provisioning: null,
          data_initialization: dataExecution,
          service_deployment: null,
          identity_handoff: null,
          updated_at: "2026-08-04T16:04:01Z",
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/release-preflight")) {
        return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      }
      if (url.includes("/bootstrap-trust-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapTrustPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-data-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapDataPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-service-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapServicePlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(servicesState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/services")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-services-001",
          phase_id: "phase.services",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_plan_digest: "5".repeat(64),
          migration_artifact_digest: "4".repeat(64),
          service_schema_version: "atlas.bootstrap-service-plan.v1",
          service_plan_digest: "d".repeat(64),
          target_id: "target.atlas-synthetic-runtime.primary",
          state: "completed",
          result_code: "bootstrap.services.completed",
          started_at: "2026-08-04T16:05:00Z",
          completed_at: "2026-08-04T16:05:01Z",
          deployed_service_count: 2,
          ready_service_count: 2,
          passed_probe_count: 6,
          service_statuses: ["service.atlas-api", "service.atlas-web"].map((serviceId) => ({
            service_id: serviceId,
            state: "ready",
            startup_passed: true,
            readiness_passed: true,
            liveness_passed: true,
          })),
          evidence: [
            {
              evidence_id: "services.runtime-state",
              sha256: "e".repeat(64),
              size_bytes: 1800,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...servicesState.data.run,
                  version: 11,
                  checkpoints: [
                    ...servicesState.data.run.checkpoints,
                    {
                      phase_id: "phase.services",
                      state: "completed",
                      safe_output_references: [`result.services.${"d".repeat(32)}`],
                      recorded_at: "2026-08-04T16:05:01Z",
                    },
                  ],
                  completed_phase_ids: [
                    "phase.acquire",
                    "phase.configure",
                    "phase.trust",
                    "phase.data",
                    "phase.services",
                  ],
                  current_phase_id: "phase.identity",
                  service_deployment: execution,
                  identity_handoff: null,
                  updated_at: "2026-08-04T16:05:01Z",
                },
                execution,
                replayed: false,
                synthetic_state_mutation_performed: true,
                real_process_mutation_performed: false,
                container_runtime_mutation_performed: false,
                operating_system_service_mutation_performed: false,
                port_or_network_mutation_performed: false,
                secret_mutation_performed: false,
                external_data_mutation_performed: false,
                infrastructure_mutation_performed: false,
                ai_operation_performed: false,
              },
            }),
            { status: 200 },
          ),
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

    fireEvent.click(await screen.findByRole("button", { name: "Review services" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText("Confirm synthetic service-state deployment")).toBeVisible();
    expect(screen.getAllByText("service.atlas-api").length).toBeGreaterThan(0);
    const confirm = screen.getByRole("button", { name: "Confirm services" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Service-state justification"), {
      target: { value: "Publish the reviewed synthetic service state for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Service-state deployment completed")).toBeVisible();
    expect(screen.getByText("services.runtime-state")).toBeVisible();
    expect(screen.getByText("Unchanged")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"service_plan_digest":"' + "d".repeat(64));
    expect(requests[0]?.body).toContain('"expected_target_state":"empty"');
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-services.9.services-request-001");
    expect(
      screen.queryByRole("button", { name: /start process|run container|open port|restart service/i }),
    ).not.toBeInTheDocument();
  });

  it("reviews synthetic identity handoff without credential or directory controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "identity-request-001" });
    const serviceExecution = {
      execution_id: "phase-execution.ui-services-complete",
      phase_id: "phase.services",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_plan_digest: "f".repeat(64),
      data_plan_digest: "5".repeat(64),
      migration_artifact_digest: "4".repeat(64),
      service_schema_version: "atlas.bootstrap-service-plan.v1",
      service_plan_digest: "d".repeat(64),
      target_id: "target.atlas-synthetic-runtime.primary",
      state: "completed",
      result_code: "bootstrap.services.completed",
      started_at: "2026-08-04T16:05:00Z",
      completed_at: "2026-08-04T16:05:01Z",
      deployed_service_count: 2,
      ready_service_count: 2,
      passed_probe_count: 6,
      service_statuses: ["service.atlas-api", "service.atlas-web"].map((serviceId) => ({
        service_id: serviceId,
        state: "ready",
        startup_passed: true,
        readiness_passed: true,
        liveness_passed: true,
      })),
      evidence: [
        {
          evidence_id: "services.runtime-state",
          sha256: "e".repeat(64),
          size_bytes: 1800,
          disposition: "published",
        },
      ],
    };
    const identityState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 11,
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
          ],
          checkpoints: [
            ...["phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services"].map(
              (phaseId) => ({
                phase_id: phaseId,
                state: "completed",
                safe_output_references: [`result.${phaseId.slice(6)}.verified`],
                recorded_at: "2026-08-04T16:05:01Z",
              }),
            ),
          ],
          completed_phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
          ],
          current_phase_id: "phase.identity",
          service_deployment: serviceExecution,
          identity_handoff: null,
          updated_at: "2026-08-04T16:05:01Z",
        },
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.includes("/release-preflight")) {
        return Promise.resolve(new Response(JSON.stringify(preflight), { status: 200 }));
      }
      if (url.includes("/deployment-configuration/preview")) {
        return Promise.resolve(new Response(JSON.stringify(configurationPreview()), { status: 200 }));
      }
      if (url.includes("/bootstrap-trust-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapTrustPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-data-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapDataPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-service-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapServicePlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-identity-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapIdentityPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(identityState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/identity")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-identity-001",
          phase_id: "phase.identity",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_plan_digest: "5".repeat(64),
          service_plan_digest: "d".repeat(64),
          identity_schema_version: "atlas.bootstrap-identity-plan.v1",
          identity_plan_digest: "9".repeat(64),
          target_id: "target.atlas-synthetic-identity.primary",
          state: "completed",
          result_code: "bootstrap.identity.completed",
          started_at: "2026-08-04T16:06:00Z",
          completed_at: "2026-08-04T16:06:01Z",
          group_mapping_count: 2,
          validation_count: 5,
          credential_replacement_required: true,
          recovery_identity_verified: true,
          bootstrap_material_sealed: true,
          pilot_identity_verified: true,
          enterprise_authentication_validated: true,
          evidence: [
            {
              evidence_id: "identity.handoff-state",
              sha256: "8".repeat(64),
              size_bytes: 1700,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...identityState.data.run,
                  version: 13,
                  checkpoints: [
                    ...identityState.data.run.checkpoints,
                    {
                      phase_id: "phase.identity",
                      state: "completed",
                      safe_output_references: [`result.identity.${"9".repeat(32)}`],
                      recorded_at: "2026-08-04T16:06:01Z",
                    },
                  ],
                  completed_phase_ids: [
                    ...identityState.data.run.completed_phase_ids,
                    "phase.identity",
                  ],
                  current_phase_id: "phase.integrations",
                  identity_handoff: execution,
                  updated_at: "2026-08-04T16:06:01Z",
                },
                execution,
                replayed: false,
                synthetic_state_mutation_performed: true,
                credential_material_mutation_performed: false,
                directory_mutation_performed: false,
                provider_activation_performed: false,
                account_mutation_performed: false,
                session_or_token_mutation_performed: false,
                infrastructure_mutation_performed: false,
                ai_operation_performed: false,
              },
            }),
            { status: 200 },
          ),
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

    fireEvent.click(await screen.findByRole("button", { name: "Review identity handoff" }));
    expect(screen.getByText("Confirm synthetic identity handoff")).toBeVisible();
    expect(screen.getByText("LDAPS metadata only")).toBeVisible();
    expect(screen.getByText("directory-group.platform-administrators")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm identity" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Identity-handoff justification"), {
      target: { value: "Publish the reviewed secret-free identity handoff for the lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Identity handoff completed")).toBeVisible();
    expect(screen.getByText("identity.handoff-state")).toBeVisible();
    expect(screen.getByText("Real identity systems")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"identity_plan_digest":"' + "9".repeat(64));
    expect(requests[0]?.body).toContain('"expected_target_state":"empty"');
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-identity.11.identity-request-001");
    expect(
      screen.queryByRole("button", { name: /set password|create account|activate provider|issue token/i }),
    ).not.toBeInTheDocument();
  });
});
