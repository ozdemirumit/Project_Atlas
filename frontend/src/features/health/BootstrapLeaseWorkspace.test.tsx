import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BootstrapPlan } from "../../api/bootstrapPlan";
import type { BootstrapState } from "../../api/bootstrapState";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapLeaseWorkspace from "./BootstrapLeaseWorkspace";

const scope: CurrentIdentity["scope"] = {
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  domain_id: "domain.test",
  resource_id: "resource.test",
  capability_class: "platform.bootstrap.coordinate",
};

const plan: BootstrapPlan = {
  plan_id: "bootstrap-plan.test",
  schema_version: "atlas.bootstrap-plan.v1",
  release_id: "release.test",
  profile: "linux_lab",
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  state: "ready",
  plan_digest: "plan-digest.test",
  resume_key: "resume.test",
  phases: [
    {
      phase_id: "phase.acquire",
      sequence: 1,
      title: "Acquire artifacts",
      dependencies: [],
      state: "ready",
      resumable: true,
      input_references: ["release.test"],
      stop_guidance: "Stop without mutation.",
    },
  ],
  generated_at: "2026-08-11T07:00:00Z",
  correlation_id: "correlation.plan.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const configuration: DeploymentConfigurationPreview = {
  preview_id: "configuration-preview.test",
  schema_version: "atlas.deployment-configuration-preview.v1",
  release_id: plan.release_id,
  profile: "linux_lab",
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  state: "passed",
  configuration_digest: "configuration-digest.test",
  fields: [],
  validations: [],
  generated_at: "2026-08-11T07:00:00Z",
  correlation_id: "correlation.configuration.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const emptyState: BootstrapState = {
  run: null,
  durable: true,
  lease_available: true,
  lease_held_by_current_actor: false,
  execution_authorized: false,
  infrastructure_mutation_authorized: false,
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 7,
  state: "active",
  release_id: plan.release_id,
  profile: plan.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: plan.plan_digest,
  resume_key: plan.resume_key,
  configuration_digest: configuration.configuration_digest,
  phase_ids: plan.phases.map((phase) => phase.phase_id),
  checkpoints: [],
  completed_phase_ids: [],
  failed_phase_id: null,
  current_phase_id: "phase.acquire",
  lease_expires_at: "2026-08-11T07:10:00Z",
  created_at: "2026-08-11T07:00:00Z",
  updated_at: "2026-08-11T07:00:00Z",
  artifact_acquisition: null,
  configuration_rendering: null,
  trust_provisioning: null,
  data_initialization: null,
  service_deployment: null,
  identity_handoff: null,
  integration_validation: null,
  end_to_end_verification: null,
  operational_handoff: null,
};

function response(options?: { reclaimed?: boolean; replayed?: boolean; version?: number }) {
  return {
    data: {
      run: { ...run, version: options?.version ?? run.version },
      replayed: options?.replayed ?? false,
      reclaimed_expired_lease: options?.reclaimed ?? false,
      execution_authorized: false,
      infrastructure_mutation_authorized: false,
    },
  };
}

function renderWorkspace(
  client: QueryClient,
  props: Partial<React.ComponentProps<typeof BootstrapLeaseWorkspace>> = {},
) {
  return render(
    <QueryClientProvider client={client}>
      <BootstrapLeaseWorkspace
        configuration={configuration}
        plan={plan}
        scope={scope}
        state={emptyState}
        {...props}
      />
    </QueryClientProvider>,
  );
}

function reviewAndConfirm(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review lease" }));
  const confirm = screen.getByRole("button", { name: "Confirm lease" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Lease justification"), {
    target: { value: justification },
  });
  fireEvent.click(confirm);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapLeaseWorkspace", () => {
  it("submits an exact reviewed initial-run claim and shows bounded server evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "initial-claim-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(
        new Response(JSON.stringify(response({ version: 1 })), { status: 201 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    renderWorkspace(client);

    reviewAndConfirm("Coordinate the reviewed immutable bootstrap plan.");

    expect(await screen.findByText("Coordination lease established")).toBeVisible();
    expect(screen.getByText(/server revision 1/i)).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-claim.0.initial-claim-001");
    expect(requests[0]?.body).toMatchObject({
      release_id: plan.release_id,
      plan_digest: plan.plan_digest,
      resume_key: plan.resume_key,
      configuration_digest: configuration.configuration_digest,
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      phase_ids: ["phase.acquire"],
      lease_minutes: 10,
      justification: "Coordinate the reviewed immutable bootstrap plan.",
    });
    expect(screen.getByText(/No phase execution is authorized/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /acquire|deploy|rollback/i })).not.toBeInTheDocument();
  });

  it("binds an expired-lease reclaim to the current run revision", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "reclaim-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(
        new Response(JSON.stringify(response({ reclaimed: true, version: 8 })), { status: 200 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    renderWorkspace(client, { state: { ...emptyState, run } });

    reviewAndConfirm("Reclaim the expired lease after evidence review.");

    expect(await screen.findByText("Expired coordination lease reclaimed")).toBeVisible();
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-claim.7.reclaim-001");
    expect(requests[0]?.body).toMatchObject({
      release_id: run.release_id,
      plan_digest: run.plan_digest,
      configuration_digest: run.configuration_digest,
      phase_ids: run.phase_ids,
    });
  });

  it("invalidates a reviewed intent when exact inputs change", () => {
    const client = new QueryClient();
    const rendered = renderWorkspace(client);

    fireEvent.click(screen.getByRole("button", { name: "Review lease" }));
    expect(screen.getByRole("dialog")).toBeVisible();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapLeaseWorkspace
          configuration={configuration}
          plan={{ ...plan, plan_digest: "plan-digest.changed" }}
          scope={scope}
          state={emptyState}
        />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review lease" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review lease" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByRole("button", { name: "Confirm lease" })).toBeDisabled();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapLeaseWorkspace
          configuration={configuration}
          plan={{ ...plan, plan_digest: "plan-digest.changed" }}
          scope={scope}
          state={{ ...emptyState, lease_available: false }}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapLeaseWorkspace
          configuration={configuration}
          plan={{ ...plan, plan_digest: "plan-digest.changed" }}
          scope={scope}
          state={emptyState}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review lease" })).toBeVisible();
  });

  it("refreshes authoritative evidence and requires a new review after conflict", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "conflict-001" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "lease_conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    renderWorkspace(client);

    reviewAndConfirm("Retry only after authoritative lease evidence refresh.");

    expect(await screen.findByRole("alert")).toHaveTextContent(/record a new review intent/i);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review lease" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
  });

  it("offers no workflow outside eligibility gates and cancel records no claim", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const rendered = renderWorkspace(client, { plan: { ...plan, state: "blocked" } });

    expect(screen.queryByRole("button", { name: "Review lease" })).not.toBeInTheDocument();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapLeaseWorkspace
          configuration={configuration}
          plan={plan}
          scope={scope}
          state={emptyState}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review lease" }));
    fireEvent.change(screen.getByLabelText("Lease justification"), {
      target: { value: "Review without submitting a lease claim." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review lease" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
