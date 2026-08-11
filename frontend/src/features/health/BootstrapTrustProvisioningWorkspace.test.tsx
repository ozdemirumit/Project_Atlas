import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  BootstrapConfigurationExecution,
  BootstrapState,
  BootstrapTrustExecution,
} from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapTrustProvisioningWorkspace from "./BootstrapTrustProvisioningWorkspace";

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
  generated_at: "2026-08-11T12:00:00Z",
  correlation_id: "correlation.configuration.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const trustPlan: BootstrapTrustPlan = {
  schema_version: "atlas.bootstrap-trust-plan.v1",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: "f".repeat(64),
  state: "passed",
  result_code: "bootstrap.trust-plan.passed",
  anchors: [
    {
      anchor_id: "trust-anchor.test",
      source_id: "trust-source.test",
      purpose: "internal_service",
      subject_summary: "CN=Atlas Test Root",
      sha256: "e".repeat(64),
      not_before: "2026-08-11T12:00:00Z",
      not_after: "2036-08-09T12:00:00Z",
      non_production_only: true,
    },
  ],
  workload_identities: [
    {
      identity_id: "workload.atlas-api.test",
      service_id: "service.atlas-api",
      instance_id: "instance.test",
      owner_subject_id: "subject.platform.security",
      purpose: "Authenticate the Atlas API test workload.",
      environment_id: scope.environment_id,
      audiences: ["audience.atlas-internal"],
      secret_reference_ids: ["secret-reference.workload.atlas-api"],
    },
  ],
  generated_at: "2026-08-11T12:00:00Z",
  private_key_material_present: false,
  credential_material_present: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const configurationExecution: BootstrapConfigurationExecution = {
  execution_id: "phase-execution.configure.test",
  phase_id: "phase.configure",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_schema_version: "atlas.deployment-configuration.v1",
  configuration_digest: configuration.configuration_digest,
  state: "completed",
  result_code: "bootstrap.configuration.completed",
  started_at: "2026-08-11T12:01:00Z",
  completed_at: "2026-08-11T12:01:01Z",
  evidence: [],
  file_count: 1,
  total_bytes: 684,
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 5,
  state: "active",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: "plan-digest.test",
  resume_key: "resume.test",
  configuration_digest: configuration.configuration_digest,
  phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data"],
  checkpoints: [],
  completed_phase_ids: ["phase.acquire", "phase.configure"],
  failed_phase_id: null,
  current_phase_id: "phase.trust",
  lease_expires_at: "2026-08-11T12:10:00Z",
  created_at: "2026-08-11T12:00:00Z",
  updated_at: "2026-08-11T12:01:01Z",
  artifact_acquisition: null,
  configuration_rendering: configurationExecution,
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

const execution: BootstrapTrustExecution = {
  execution_id: "phase-execution.trust.test",
  phase_id: "phase.trust",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_digest: configuration.configuration_digest,
  trust_schema_version: "atlas.bootstrap-trust-plan.v1",
  trust_plan_digest: trustPlan.trust_plan_digest,
  state: "completed",
  result_code: "bootstrap.trust.completed",
  started_at: "2026-08-11T12:02:00Z",
  completed_at: "2026-08-11T12:02:01Z",
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

function trustResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 6,
        checkpoints: [
          {
            phase_id: "phase.trust",
            state: "completed" as const,
            safe_output_references: ["trust.receipt.test"],
            recorded_at: execution.completed_at!,
          },
        ],
        completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
        current_phase_id: "phase.data",
        updated_at: execution.completed_at!,
        trust_provisioning: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
      trust_storage_mutation_performed: true,
      private_key_mutation_performed: false,
      secret_value_mutation_performed: false,
      data_mutation_authorized: false,
      service_deployment_authorized: false,
      infrastructure_mutation_authorized: false,
      ai_operation_authorized: false,
    },
  };
}

function workspace(
  client: QueryClient,
  options?: {
    configuration?: DeploymentConfigurationPreview;
    state?: BootstrapState;
    trustPlan?: BootstrapTrustPlan;
  },
) {
  return (
    <QueryClientProvider client={client}>
      <BootstrapTrustProvisioningWorkspace
        configuration={options?.configuration ?? configuration}
        scope={scope}
        state={options?.state ?? state}
        trustPlan={options?.trustPlan ?? trustPlan}
      />
    </QueryClientProvider>
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review trust" }));
  const confirm = screen.getByRole("button", { name: "Confirm trust" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Trust justification"), {
    target: { value: justification },
  });
  return confirm;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapTrustProvisioningWorkspace", () => {
  it("submits the exact reviewed trust plan and presents bounded public evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "trust-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(new Response(JSON.stringify(trustResponse()), { status: 200 }));
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Publish the approved public trust metadata for this run."));

    expect(await screen.findByText("Trust provisioning completed")).toBeVisible();
    const bundle = screen.getByText("trust.bundle");
    expect(within(bundle.parentElement!).getByText("published")).toBeVisible();
    expect(screen.getByText("trust.workload-identities")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-trust.5.trust-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-trust-provisioning.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.trust",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_schema_version: trustPlan.schema_version,
      trust_plan_digest: trustPlan.trust_plan_digest,
      justification: "Publish the approved public trust metadata for this run.",
    });
    expect(screen.queryByText(/BEGIN PRIVATE KEY|raw-token-value|top-secret/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /initialize data|deploy service|infrastructure|AI/i }),
    ).not.toBeInTheDocument();
  });

  it("marks replayed evidence without revealing secret or later-phase controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "trust-replay" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(trustResponse({ replayed: true })), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Replay the exact approved public trust publication result."));

    expect(await screen.findByText("Trust provisioning completed (replayed)")).toBeVisible();
    expect(screen.queryByText("secret-reference.workload.atlas-api")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /data|service|rollback/i })).not.toBeInTheDocument();
  });

  it("cancels review without sending a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    render(workspace(client));

    review("Publish the reviewed trust plan but cancel before submission.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review trust" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalidates an open review when the public trust plan changes", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const view = render(workspace(client));

    review("Publish only the currently reviewed public trust plan evidence.");
    view.rerender(
      workspace(client, {
        trustPlan: { ...trustPlan, trust_plan_digest: "9".repeat(64) },
      }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review trust" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fails closed for unavailable or mismatched evidence", () => {
    const client = new QueryClient();
    const view = render(
      workspace(client, { state: { ...state, lease_held_by_current_actor: false } }),
    );
    expect(screen.queryByRole("button", { name: "Review trust" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        trustPlan: { ...trustPlan, environment_id: "environment.other" },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review trust" })).not.toBeInTheDocument();
  });

  it("refreshes authoritative evidence and requires a new review after failure", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "trust-failure" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(workspace(client));

    fireEvent.click(review("Publish the exact reviewed public trust metadata now."));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence was refreshed");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review trust" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
  });
});
