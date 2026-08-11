import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BootstrapDataPlan } from "../../api/bootstrapData";
import type { BootstrapServicePlan } from "../../api/bootstrapServices";
import type {
  BootstrapDataExecution,
  BootstrapServiceExecution,
  BootstrapState,
} from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapServiceDeploymentWorkspace from "./BootstrapServiceDeploymentWorkspace";

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
  generated_at: "2026-08-11T14:00:00Z",
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
  generated_at: "2026-08-11T14:00:00Z",
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
      to_revision: "atlas-0002",
      compatibility: "expand",
      reversible: true,
      destructive: false,
      recovery_code: "bootstrap.data.recover.atlas-0001",
      expected_object_count: 18,
    },
  ],
  backup_applicability: "not_applicable_clean_install",
  generated_at: "2026-08-11T14:01:00Z",
  database_url_present: false,
  credential_material_present: false,
  sql_text_present: false,
  destructive_migration_authorized: false,
  backup_operation_authorized: false,
  service_deployment_authorized: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const servicePlan: BootstrapServicePlan = {
  schema_version: "atlas.bootstrap-service-plan.v1",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  data_plan_digest: dataPlan.data_plan_digest,
  migration_artifact_digest: dataPlan.migration_artifact_digest,
  service_plan_digest: "s".repeat(64),
  target_id: "service-state.test",
  target_kind: "atlas_synthetic_service_state",
  target_state: "empty",
  state: "passed",
  result_code: "bootstrap.service-plan.passed",
  services: [
    {
      service_id: "service.atlas-api",
      sequence: 1,
      artifact_id: "artifact.atlas-api",
      artifact_sha256: "2".repeat(64),
      dependencies: [],
      workload_identity_id: "workload.atlas-api",
      endpoint_class: "private",
      cpu_limit_millicores: 500,
      memory_limit_mb: 512,
      startup_probe_id: "probe.atlas-api.startup",
      readiness_probe_id: "probe.atlas-api.readiness",
      liveness_probe_id: "probe.atlas-api.liveness",
      run_as_root: false,
      privileged: false,
      arbitrary_public_egress: false,
    },
    {
      service_id: "service.atlas-worker",
      sequence: 2,
      artifact_id: "artifact.atlas-worker",
      artifact_sha256: "3".repeat(64),
      dependencies: ["service.atlas-api"],
      workload_identity_id: "workload.atlas-worker",
      endpoint_class: "private",
      cpu_limit_millicores: 750,
      memory_limit_mb: 768,
      startup_probe_id: "probe.atlas-worker.startup",
      readiness_probe_id: "probe.atlas-worker.readiness",
      liveness_probe_id: "probe.atlas-worker.liveness",
      run_as_root: false,
      privileged: false,
      arbitrary_public_egress: false,
    },
  ],
  generated_at: "2026-08-11T14:02:00Z",
  real_process_mutation_authorized: false,
  container_runtime_mutation_authorized: false,
  operating_system_service_mutation_authorized: false,
  network_mutation_authorized: false,
  secret_mutation_authorized: false,
  external_data_mutation_authorized: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const dataExecution: BootstrapDataExecution = {
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
  started_at: "2026-08-11T14:03:00Z",
  completed_at: "2026-08-11T14:03:02Z",
  lock_acquired: true,
  migration_count: 1,
  verified_object_count: 18,
  backup_applicability: "not_applicable_clean_install",
  evidence: [],
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 7,
  state: "active",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: "plan-digest.test",
  resume_key: "resume.test",
  configuration_digest: configuration.configuration_digest,
  phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services"],
  checkpoints: [],
  completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data"],
  failed_phase_id: null,
  current_phase_id: "phase.services",
  lease_expires_at: "2026-08-11T14:20:00Z",
  created_at: "2026-08-11T14:00:00Z",
  updated_at: "2026-08-11T14:03:02Z",
  artifact_acquisition: null,
  configuration_rendering: null,
  trust_provisioning: null,
  data_initialization: dataExecution,
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

const execution: BootstrapServiceExecution = {
  execution_id: "phase-execution.services.test",
  phase_id: "phase.services",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  data_plan_digest: dataPlan.data_plan_digest,
  migration_artifact_digest: dataPlan.migration_artifact_digest,
  service_schema_version: servicePlan.schema_version,
  service_plan_digest: servicePlan.service_plan_digest,
  target_id: servicePlan.target_id,
  state: "completed",
  result_code: "bootstrap.services.completed",
  started_at: "2026-08-11T14:04:00Z",
  completed_at: "2026-08-11T14:04:02Z",
  deployed_service_count: 2,
  ready_service_count: 2,
  passed_probe_count: 6,
  service_statuses: servicePlan.services.map((service) => ({
    service_id: service.service_id,
    state: "ready" as const,
    startup_passed: true,
    readiness_passed: true,
    liveness_passed: true,
  })),
  evidence: [
    {
      evidence_id: "service-state.receipt",
      sha256: "4".repeat(64),
      size_bytes: 720,
      disposition: "published",
    },
  ],
};

function serviceResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 8,
        completed_phase_ids: [...run.completed_phase_ids, "phase.services"],
        current_phase_id: "phase.identity",
        updated_at: execution.completed_at!,
        service_deployment: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
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
  };
}

function workspace(
  client: QueryClient,
  options?: { servicePlan?: BootstrapServicePlan; state?: BootstrapState },
) {
  return (
    <QueryClientProvider client={client}>
      <BootstrapServiceDeploymentWorkspace
        configuration={configuration}
        dataPlan={dataPlan}
        scope={scope}
        servicePlan={options?.servicePlan ?? servicePlan}
        state={options?.state ?? state}
        trustPlan={trustPlan}
      />
    </QueryClientProvider>
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review services" }));
  const confirm = screen.getByRole("button", { name: "Confirm services" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Service-state justification"), {
    target: { value: justification },
  });
  return confirm;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapServiceDeploymentWorkspace", () => {
  it("submits the exact reviewed service plan and presents bounded synthetic evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "service-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(new Response(JSON.stringify(serviceResponse()), { status: 200 }));
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Publish the reviewed synthetic Atlas service state."));

    expect(await screen.findByText("Service-state deployment completed")).toBeVisible();
    const receipt = screen.getByText("service-state.receipt");
    expect(within(receipt.parentElement!).getByText("published")).toBeVisible();
    expect(screen.getAllByText("startup passed")).toHaveLength(2);
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-services.7.service-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-service-deployment.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.services",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: trustPlan.trust_plan_digest,
      data_plan_digest: dataPlan.data_plan_digest,
      migration_artifact_digest: dataPlan.migration_artifact_digest,
      service_schema_version: servicePlan.schema_version,
      service_plan_digest: servicePlan.service_plan_digest,
      target_id: servicePlan.target_id,
      expected_target_state: servicePlan.target_state,
      justification: "Publish the reviewed synthetic Atlas service state.",
    });
    expect(screen.queryByText(/docker run|systemctl|Bearer|raw-secret|0\.0\.0\.0/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /identity|network|infrastructure|AI/i })).not.toBeInTheDocument();
  });

  it("marks replayed evidence without exposing runtime or later controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "service-replay" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(serviceResponse({ replayed: true })), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Replay the exact reviewed synthetic service-state result."));

    expect(await screen.findByText("Service-state deployment completed (replayed)")).toBeVisible();
    expect(screen.queryByText(/container runtime|secret value|private endpoint/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /identity|rollback|network/i })).not.toBeInTheDocument();
  });

  it("cancels review without sending a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    render(workspace(client));

    review("Publish the service plan but cancel before submission.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review services" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalidates an open review when ordered service evidence changes", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const view = render(workspace(client));

    review("Publish only the exact currently reviewed service plan evidence.");
    view.rerender(
      workspace(client, {
        servicePlan: { ...servicePlan, service_plan_digest: "9".repeat(64) },
      }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review services" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fails closed for missing lease and forward dependency evidence", () => {
    const client = new QueryClient();
    const view = render(
      workspace(client, { state: { ...state, lease_held_by_current_actor: false } }),
    );
    expect(screen.queryByRole("button", { name: "Review services" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        servicePlan: {
          ...servicePlan,
          services: [
            { ...servicePlan.services[0]!, dependencies: ["service.atlas-worker"] },
            servicePlan.services[1]!,
          ],
        },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review services" })).not.toBeInTheDocument();
  });

  it("refreshes all authoritative evidence and requires a new review after failure", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "service-failure" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(workspace(client));

    fireEvent.click(review("Publish the exact reviewed synthetic service state now."));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence was refreshed");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review services" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-service-plan"] });
  });
});
