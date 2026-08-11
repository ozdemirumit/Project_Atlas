import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BootstrapPlan } from "../../api/bootstrapPlan";
import type { BootstrapArtifactExecution, BootstrapState } from "../../api/bootstrapState";
import type { CurrentIdentity } from "../../api/identity";
import type { ReleasePreflight } from "../../api/releasePreflight";
import BootstrapArtifactAcquisitionWorkspace from "./BootstrapArtifactAcquisitionWorkspace";

const scope: CurrentIdentity["scope"] = {
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  domain_id: "domain.test",
  resource_id: "resource.test",
  capability_class: "platform.bootstrap.coordinate",
};

const preflight: ReleasePreflight = {
  report_id: "preflight.test",
  release_id: "release.test",
  release_version: "0.1.0",
  build_id: "build.test",
  manifest_digest: "a".repeat(64),
  mode: "offline",
  profile: "linux_lab",
  state: "passed",
  checks: [],
  generated_at: "2026-08-11T08:00:00Z",
  correlation_id: "correlation.preflight.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const plan: BootstrapPlan = {
  plan_id: "bootstrap-plan.test",
  schema_version: "atlas.bootstrap-plan.v1",
  release_id: preflight.release_id,
  profile: preflight.profile,
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
      input_references: [preflight.release_id],
      stop_guidance: "Stop without further mutation.",
    },
  ],
  generated_at: "2026-08-11T08:00:00Z",
  correlation_id: "correlation.plan.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 11,
  state: "active",
  release_id: plan.release_id,
  profile: plan.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: plan.plan_digest,
  resume_key: plan.resume_key,
  configuration_digest: "configuration-digest.test",
  phase_ids: plan.phases.map((phase) => phase.phase_id),
  checkpoints: [],
  completed_phase_ids: [],
  failed_phase_id: null,
  current_phase_id: "phase.acquire",
  lease_expires_at: "2026-08-11T08:10:00Z",
  created_at: "2026-08-11T08:00:00Z",
  updated_at: "2026-08-11T08:00:00Z",
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

const state: BootstrapState = {
  run,
  durable: true,
  lease_available: false,
  lease_held_by_current_actor: true,
  execution_authorized: false,
  infrastructure_mutation_authorized: false,
};

const execution: BootstrapArtifactExecution = {
  execution_id: "phase-execution.acquire.test",
  phase_id: "phase.acquire",
  release_id: run.release_id,
  manifest_digest: preflight.manifest_digest,
  mode: preflight.mode,
  preflight_report_id: preflight.report_id,
  state: "completed",
  result_code: "bootstrap.artifact.completed",
  started_at: "2026-08-11T08:01:00Z",
  completed_at: "2026-08-11T08:01:01Z",
  evidence: [
    {
      artifact_id: "artifact.backend.image",
      sha256: "d".repeat(64),
      size_bytes: 13,
      disposition: "published",
    },
    {
      artifact_id: "artifact.frontend.image",
      sha256: "e".repeat(64),
      size_bytes: 21,
      disposition: "reused",
    },
  ],
  artifact_count: 2,
  total_bytes: 34,
};

function acquisitionResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 12,
        checkpoints: [
          {
            phase_id: "phase.acquire",
            state: "completed" as const,
            safe_output_references: ["artifact.receipt.test"],
            recorded_at: execution.completed_at!,
          },
        ],
        completed_phase_ids: ["phase.acquire"],
        current_phase_id: "phase.configure",
        updated_at: execution.completed_at!,
        artifact_acquisition: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
      artifact_storage_mutation_performed: true,
      configuration_mutation_authorized: false,
      service_deployment_authorized: false,
      infrastructure_mutation_authorized: false,
      ai_operation_authorized: false,
    },
  };
}

function renderWorkspace(
  client: QueryClient,
  props: Partial<React.ComponentProps<typeof BootstrapArtifactAcquisitionWorkspace>> = {},
) {
  return render(
    <QueryClientProvider client={client}>
      <BootstrapArtifactAcquisitionWorkspace
        formatTimestamp={(value) => value ?? "Not completed"}
        plan={plan}
        preflight={preflight}
        scope={scope}
        state={state}
        {...props}
      />
    </QueryClientProvider>,
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review acquisition" }));
  const confirm = screen.getByRole("button", { name: "Confirm acquisition" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Change justification"), {
    target: { value: justification },
  });
  return confirm;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapArtifactAcquisitionWorkspace", () => {
  it("submits the exact reviewed acquisition and presents bounded artifact evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "acquisition-001" });
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
        new Response(JSON.stringify(acquisitionResponse()), { status: 200 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    renderWorkspace(client);

    fireEvent.click(review("Acquire the approved immutable release artifacts."));

    expect(await screen.findByText("Artifact acquisition completed")).toBeVisible();
    expect(screen.getByText("artifact.backend.image")).toBeVisible();
    expect(screen.getByText("published")).toBeVisible();
    expect(screen.getByText("artifact.frontend.image")).toBeVisible();
    expect(screen.getByText("reused")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-acquire.11.acquisition-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-artifact-acquisition.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.acquire",
      release_id: run.release_id,
      manifest_digest: preflight.manifest_digest,
      mode: preflight.mode,
      profile: preflight.profile,
      preflight_report_id: preflight.report_id,
      preflight_state: "passed",
      warning_accepted: false,
      justification: "Acquire the approved immutable release artifacts.",
    });
    expect(
      screen.queryByRole("button", { name: /configuration|service|deploy|infrastructure|AI/i }),
    ).not.toBeInTheDocument();
  });

  it("requires and submits acknowledgement for the exact warning preflight", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "warning-001" });
    const bodies: Array<Record<string, unknown>> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      bodies.push(
        JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>,
      );
      return Promise.resolve(
        new Response(JSON.stringify(acquisitionResponse({ replayed: true })), { status: 200 }),
      );
    });
    const warningPreflight = { ...preflight, state: "warning" as const };
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    renderWorkspace(client, { preflight: warningPreflight });

    const confirm = review("Acquire after reviewing the bounded preflight warning.");
    expect(confirm).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "I accept the reviewed preflight warning for this lab run.",
      }),
    );
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    expect(await screen.findByText("Artifact acquisition completed (replayed)")).toBeVisible();
    expect(bodies[0]).toMatchObject({
      preflight_state: "warning",
      warning_accepted: true,
    });
  });

  it("invalidates review intent when exact evidence or eligibility changes", () => {
    const client = new QueryClient();
    const rendered = renderWorkspace(client);

    review("Review the exact current artifact acquisition inputs.");
    expect(screen.getByRole("dialog")).toBeVisible();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapArtifactAcquisitionWorkspace
          formatTimestamp={(value) => value ?? "Not completed"}
          plan={plan}
          preflight={{ ...preflight, report_id: "preflight.changed" }}
          scope={scope}
          state={state}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review acquisition" })).toBeVisible();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapArtifactAcquisitionWorkspace
          formatTimestamp={(value) => value ?? "Not completed"}
          plan={plan}
          preflight={preflight}
          scope={scope}
          state={{ ...state, lease_held_by_current_actor: false }}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("button", { name: "Review acquisition" })).not.toBeInTheDocument();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapArtifactAcquisitionWorkspace
          formatTimestamp={(value) => value ?? "Not completed"}
          plan={plan}
          preflight={preflight}
          scope={scope}
          state={state}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review acquisition" }));
    expect(screen.getByRole("button", { name: "Confirm acquisition" })).toBeDisabled();
  });

  it("refreshes authoritative evidence and requires a new review after conflict", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "conflict-001" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "bootstrap_version_conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    renderWorkspace(client);

    fireEvent.click(review("Refresh authoritative evidence after a bounded conflict."));

    expect(await screen.findByRole("alert")).toHaveTextContent(/new review intent/i);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review acquisition" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
  });

  it("offers no workflow outside all gates and cancel performs no request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const rendered = renderWorkspace(client, {
      preflight: { ...preflight, state: "unchecked" },
    });

    expect(screen.queryByRole("button", { name: "Review acquisition" })).not.toBeInTheDocument();

    rendered.rerender(
      <QueryClientProvider client={client}>
        <BootstrapArtifactAcquisitionWorkspace
          formatTimestamp={(value) => value ?? "Not completed"}
          plan={plan}
          preflight={preflight}
          scope={scope}
          state={state}
        />
      </QueryClientProvider>,
    );
    review("Review and cancel without writing an artifact.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review acquisition" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
