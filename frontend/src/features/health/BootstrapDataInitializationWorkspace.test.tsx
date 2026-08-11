import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BootstrapDataPlan } from "../../api/bootstrapData";
import type {
  BootstrapDataExecution,
  BootstrapState,
  BootstrapTrustExecution,
} from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapDataInitializationWorkspace from "./BootstrapDataInitializationWorkspace";

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
  anchors: [],
  workload_identities: [],
  generated_at: "2026-08-11T12:00:00Z",
  private_key_material_present: false,
  credential_material_present: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const dataPlan: BootstrapDataPlan = {
  schema_version: "atlas.bootstrap-data-plan.v1",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  migration_artifact_digest: "a".repeat(64),
  data_plan_digest: "d".repeat(64),
  target_id: "data-target.test",
  target_kind: "embedded_postgresql",
  current_revision: "empty",
  target_revision: "atlas-0002",
  target_state: "empty",
  state: "passed",
  result_code: "bootstrap.data-plan.passed",
  migrations: [
    {
      migration_id: "migration.atlas-0001",
      sequence: 1,
      sha256: "1".repeat(64),
      from_revision: "empty",
      to_revision: "atlas-0001",
      compatibility: "expand",
      reversible: true,
      destructive: false,
      recovery_code: "bootstrap.data.recover.atlas-0001",
      expected_object_count: 12,
    },
    {
      migration_id: "migration.atlas-0002",
      sequence: 2,
      sha256: "2".repeat(64),
      from_revision: "atlas-0001",
      to_revision: "atlas-0002",
      compatibility: "expand",
      reversible: true,
      destructive: false,
      recovery_code: "bootstrap.data.recover.atlas-0002",
      expected_object_count: 18,
    },
  ],
  backup_applicability: "not_applicable_clean_install",
  generated_at: "2026-08-11T12:03:00Z",
  database_url_present: false,
  credential_material_present: false,
  sql_text_present: false,
  destructive_migration_authorized: false,
  backup_operation_authorized: false,
  service_deployment_authorized: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const trustExecution: BootstrapTrustExecution = {
  execution_id: "phase-execution.trust.test",
  phase_id: "phase.trust",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_digest: configuration.configuration_digest,
  trust_schema_version: trustPlan.schema_version,
  trust_plan_digest: trustPlan.trust_plan_digest,
  state: "completed",
  result_code: "bootstrap.trust.completed",
  started_at: "2026-08-11T12:02:00Z",
  completed_at: "2026-08-11T12:02:01Z",
  anchor_count: 1,
  workload_identity_count: 1,
  evidence: [],
  file_count: 2,
  total_bytes: 2000,
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 6,
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
  completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
  failed_phase_id: null,
  current_phase_id: "phase.data",
  lease_expires_at: "2026-08-11T12:20:00Z",
  created_at: "2026-08-11T12:00:00Z",
  updated_at: "2026-08-11T12:02:01Z",
  artifact_acquisition: null,
  configuration_rendering: null,
  trust_provisioning: trustExecution,
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

const execution: BootstrapDataExecution = {
  execution_id: "phase-execution.data.test",
  phase_id: "phase.data",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  data_schema_version: dataPlan.schema_version,
  data_plan_digest: dataPlan.data_plan_digest,
  migration_artifact_digest: dataPlan.migration_artifact_digest,
  target_id: dataPlan.target_id,
  from_revision: dataPlan.current_revision,
  to_revision: dataPlan.target_revision,
  state: "completed",
  result_code: "bootstrap.data.completed",
  started_at: "2026-08-11T12:04:00Z",
  completed_at: "2026-08-11T12:04:02Z",
  lock_acquired: true,
  migration_count: 2,
  verified_object_count: 18,
  backup_applicability: "not_applicable_clean_install",
  evidence: [
    {
      evidence_id: "data.schema.receipt",
      sha256: "3".repeat(64),
      size_bytes: 640,
      disposition: "published",
    },
  ],
};

function dataResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 7,
        completed_phase_ids: [...run.completed_phase_ids, "phase.data"],
        current_phase_id: "phase.services",
        updated_at: execution.completed_at!,
        data_initialization: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
      schema_state_mutation_performed: true,
      external_database_provisioning_performed: false,
      destructive_migration_performed: false,
      backup_operation_performed: false,
      service_deployment_authorized: false,
      infrastructure_mutation_authorized: false,
      ai_operation_authorized: false,
    },
  };
}

function workspace(
  client: QueryClient,
  options?: {
    dataPlan?: BootstrapDataPlan;
    state?: BootstrapState;
    trustPlan?: BootstrapTrustPlan;
  },
) {
  return (
    <QueryClientProvider client={client}>
      <BootstrapDataInitializationWorkspace
        configuration={configuration}
        dataPlan={options?.dataPlan ?? dataPlan}
        scope={scope}
        state={options?.state ?? state}
        trustPlan={options?.trustPlan ?? trustPlan}
      />
    </QueryClientProvider>
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review data" }));
  const confirm = screen.getByRole("button", { name: "Confirm data" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Data justification"), {
    target: { value: justification },
  });
  return confirm;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapDataInitializationWorkspace", () => {
  it("submits the exact reviewed data plan and presents bounded schema evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "data-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(new Response(JSON.stringify(dataResponse()), { status: 200 }));
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Initialize the reviewed reversible Atlas schema records."));

    expect(await screen.findByText("Data initialization completed")).toBeVisible();
    const receipt = screen.getByText("data.schema.receipt");
    expect(within(receipt.parentElement!).getByText("published")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-data.6.data-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-data-initialization.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.data",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: trustPlan.trust_plan_digest,
      data_schema_version: dataPlan.schema_version,
      data_plan_digest: dataPlan.data_plan_digest,
      migration_artifact_digest: dataPlan.migration_artifact_digest,
      target_id: dataPlan.target_id,
      expected_target_state: dataPlan.target_state,
      justification: "Initialize the reviewed reversible Atlas schema records.",
    });
    expect(screen.queryByText(/database:\/\/|CREATE TABLE|raw-password|top-secret/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /backup|deploy service|infrastructure|AI/i }),
    ).not.toBeInTheDocument();
  });

  it("marks replayed evidence without exposing SQL, credentials, or later controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "data-replay" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(dataResponse({ replayed: true })), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Replay the exact reviewed schema initialization result."));

    expect(await screen.findByText("Data initialization completed (replayed)")).toBeVisible();
    expect(screen.queryByText(/secret|password|CREATE TABLE/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /service|rollback|backup/i })).not.toBeInTheDocument();
  });

  it("cancels review without sending a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    render(workspace(client));

    review("Initialize the reviewed data plan but cancel before submission.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review data" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalidates an open review when the ordered data plan changes", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const view = render(workspace(client));

    review("Initialize only the currently reviewed data plan evidence.");
    view.rerender(
      workspace(client, { dataPlan: { ...dataPlan, data_plan_digest: "9".repeat(64) } }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review data" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fails closed for unavailable or mismatched evidence", () => {
    const client = new QueryClient();
    const view = render(
      workspace(client, { state: { ...state, lease_held_by_current_actor: false } }),
    );
    expect(screen.queryByRole("button", { name: "Review data" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, { dataPlan: { ...dataPlan, environment_id: "environment.other" } }),
    );
    expect(screen.queryByRole("button", { name: "Review data" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        dataPlan: {
          ...dataPlan,
          migrations: [
            dataPlan.migrations[0]!,
            { ...dataPlan.migrations[1]!, from_revision: "unexpected-revision" },
          ],
        },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review data" })).not.toBeInTheDocument();
  });

  it("refreshes all authoritative evidence and requires a new review after failure", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "data-failure" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(workspace(client));

    fireEvent.click(review("Initialize the exact reviewed reversible schema records now."));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence was refreshed");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review data" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-data-plan"] });
  });
});

