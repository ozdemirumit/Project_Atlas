import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  BootstrapArtifactExecution,
  BootstrapConfigurationExecution,
  BootstrapState,
} from "../../api/bootstrapState";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapConfigurationRenderingWorkspace from "./BootstrapConfigurationRenderingWorkspace";

const scope: CurrentIdentity["scope"] = {
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  domain_id: "domain.test",
  resource_id: "resource.test",
  capability_class: "platform.bootstrap.coordinate",
};

const configuration: DeploymentConfigurationPreview = {
  preview_id: "configuration-preview.test",
  schema_version: "atlas.deployment-configuration.v1",
  release_id: "release.test",
  profile: "linux_lab",
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  state: "passed",
  configuration_digest: "b".repeat(64),
  fields: [],
  validations: [],
  generated_at: "2026-08-11T10:00:00Z",
  correlation_id: "correlation.configuration.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const artifactExecution: BootstrapArtifactExecution = {
  execution_id: "phase-execution.acquire.test",
  phase_id: "phase.acquire",
  release_id: configuration.release_id,
  manifest_digest: "a".repeat(64),
  mode: "offline",
  preflight_report_id: "preflight.test",
  state: "completed",
  result_code: "bootstrap.artifact.completed",
  started_at: "2026-08-11T10:00:00Z",
  completed_at: "2026-08-11T10:00:01Z",
  evidence: [],
  artifact_count: 1,
  total_bytes: 13,
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 3,
  state: "active",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: "plan-digest.test",
  resume_key: "resume.test",
  configuration_digest: configuration.configuration_digest,
  phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
  checkpoints: [
    {
      phase_id: "phase.acquire",
      state: "completed",
      safe_output_references: ["artifact.receipt.test"],
      recorded_at: artifactExecution.completed_at!,
    },
  ],
  completed_phase_ids: ["phase.acquire"],
  failed_phase_id: null,
  current_phase_id: "phase.configure",
  lease_expires_at: "2026-08-11T10:10:00Z",
  created_at: "2026-08-11T10:00:00Z",
  updated_at: "2026-08-11T10:00:01Z",
  artifact_acquisition: artifactExecution,
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

const execution: BootstrapConfigurationExecution = {
  execution_id: "phase-execution.configure.test",
  phase_id: "phase.configure",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_schema_version: "atlas.deployment-configuration.v1",
  configuration_digest: configuration.configuration_digest,
  state: "completed",
  result_code: "bootstrap.configuration.completed",
  started_at: "2026-08-11T10:01:00Z",
  completed_at: "2026-08-11T10:01:01Z",
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

function configurationResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 4,
        checkpoints: [
          ...run.checkpoints,
          {
            phase_id: "phase.configure",
            state: "completed" as const,
            safe_output_references: ["configuration.receipt.test"],
            recorded_at: execution.completed_at!,
          },
        ],
        completed_phase_ids: ["phase.acquire", "phase.configure"],
        current_phase_id: "phase.trust",
        updated_at: execution.completed_at!,
        configuration_rendering: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
      configuration_storage_mutation_performed: true,
      trust_mutation_authorized: false,
      secret_mutation_authorized: false,
      data_mutation_authorized: false,
      service_deployment_authorized: false,
      infrastructure_mutation_authorized: false,
      ai_operation_authorized: false,
    },
  };
}

function workspace(
  client: QueryClient,
  options?: { configuration?: DeploymentConfigurationPreview; state?: BootstrapState },
) {
  return (
    <QueryClientProvider client={client}>
      <BootstrapConfigurationRenderingWorkspace
        configuration={options?.configuration ?? configuration}
        formatTimestamp={(value) => value ?? "Not completed"}
        scope={scope}
        state={options?.state ?? state}
      />
    </QueryClientProvider>
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review configuration" }));
  const confirm = screen.getByRole("button", { name: "Confirm configuration" });
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

describe("BootstrapConfigurationRenderingWorkspace", () => {
  it("submits the exact reviewed configuration and presents bounded file evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "configuration-001" });
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
        new Response(JSON.stringify(configurationResponse()), { status: 200 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Render the approved effective configuration for this run."));

    expect(await screen.findByText("Configuration rendering completed")).toBeVisible();
    const file = screen.getByText("configuration.effective");
    expect(within(file.parentElement!).getByText("published")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-configure.3.configuration-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-configuration-rendering.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.configure",
      release_id: run.release_id,
      profile: run.profile,
      configuration_schema_version: "atlas.deployment-configuration.v1",
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      justification: "Render the approved effective configuration for this run.",
    });
    expect(
      screen.queryByRole("button", { name: /trust|secret|data|service|infrastructure|AI/i }),
    ).not.toBeInTheDocument();
  });

  it("marks replayed evidence without adding later authority", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "configuration-replay" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(configurationResponse({ replayed: true })), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Replay the exact approved effective configuration result."));

    expect(await screen.findByText("Configuration rendering completed (replayed)")).toBeVisible();
    expect(screen.queryByRole("button", { name: /trust|deploy|rollback/i })).not.toBeInTheDocument();
  });

  it("cancels review without sending a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    render(workspace(client));

    review("Render the reviewed configuration but cancel before submission.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review configuration" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalidates an open review when exact run evidence changes", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const view = render(workspace(client));

    review("Render only the currently reviewed run configuration evidence.");
    view.rerender(
      workspace(client, { state: { ...state, run: { ...run, version: run.version + 1 } } }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review configuration" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fails closed for unavailable or mismatched evidence", () => {
    const client = new QueryClient();
    const view = render(
      workspace(client, { state: { ...state, lease_held_by_current_actor: false } }),
    );
    expect(screen.queryByRole("button", { name: "Review configuration" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        configuration: { ...configuration, configuration_digest: "c".repeat(64) },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review configuration" })).not.toBeInTheDocument();
  });

  it("refreshes authoritative evidence and requires a new review after failure", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "configuration-failure" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(workspace(client));

    fireEvent.click(review("Render the approved configuration after exact review."));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence was refreshed");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review configuration" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
  });
});
