import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BootstrapDataPlan } from "../../api/bootstrapData";
import type { BootstrapIdentityPlan } from "../../api/bootstrapIdentity";
import type { BootstrapServicePlan } from "../../api/bootstrapServices";
import type {
  BootstrapIdentityExecution,
  BootstrapServiceExecution,
  BootstrapState,
} from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";
import BootstrapIdentityHandoffWorkspace from "./BootstrapIdentityHandoffWorkspace";

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
  generated_at: "2026-08-11T15:00:00Z",
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
  generated_at: "2026-08-11T15:00:00Z",
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
  migrations: [],
  backup_applicability: "not_applicable_clean_install",
  generated_at: "2026-08-11T15:01:00Z",
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
  generated_at: "2026-08-11T15:02:00Z",
  real_process_mutation_authorized: false,
  container_runtime_mutation_authorized: false,
  operating_system_service_mutation_authorized: false,
  network_mutation_authorized: false,
  secret_mutation_authorized: false,
  external_data_mutation_authorized: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const identityPlan: BootstrapIdentityPlan = {
  schema_version: "atlas.bootstrap-identity-plan.v1",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  data_plan_digest: dataPlan.data_plan_digest,
  service_plan_digest: servicePlan.service_plan_digest,
  identity_plan_digest: "i".repeat(64),
  target_id: "identity-state.test",
  target_kind: "atlas_synthetic_identity_state",
  target_state: "empty",
  bootstrap_administrator_subject_id: "subject.bootstrap-admin",
  credential_verifier_reference_id: "secret-reference.bootstrap-admin.verifier",
  credential_replacement_required: true,
  recovery_identity_id: "identity.recovery-admin",
  recovery_seal_required: true,
  provider_id: "provider.ldap.enterprise",
  provider_protocol: "ldaps",
  pilot_subject_id: "subject.pilot-admin",
  group_mappings: [
    {
      mapping_id: "mapping.platform-admins",
      directory_group_reference: "directory-group.platform-admins",
      role_ids: ["role.platform-admin"],
    },
    {
      mapping_id: "mapping.security-admins",
      directory_group_reference: "directory-group.security-admins",
      role_ids: ["role.security-admin"],
    },
  ],
  state: "passed",
  result_code: "bootstrap.identity-plan.passed",
  generated_at: "2026-08-11T15:03:00Z",
  credential_material_present: false,
  directory_mutation_authorized: false,
  provider_activation_authorized: false,
  account_mutation_authorized: false,
  session_or_token_mutation_authorized: false,
  infrastructure_mutation_authorized: false,
  ai_operation_authorized: false,
};

const serviceExecution: BootstrapServiceExecution = {
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
  started_at: "2026-08-11T15:04:00Z",
  completed_at: "2026-08-11T15:04:02Z",
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
  evidence: [],
};

const run: NonNullable<BootstrapState["run"]> = {
  run_id: "bootstrap-run.test",
  version: 8,
  state: "active",
  release_id: configuration.release_id,
  profile: configuration.profile,
  organization_id: scope.organization_id,
  environment_id: scope.environment_id,
  site_id: scope.site_id,
  plan_digest: "plan-digest.test",
  resume_key: "resume.test",
  configuration_digest: configuration.configuration_digest,
  phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services", "phase.identity"],
  checkpoints: [],
  completed_phase_ids: ["phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services"],
  failed_phase_id: null,
  current_phase_id: "phase.identity",
  lease_expires_at: "2026-08-11T15:20:00Z",
  created_at: "2026-08-11T15:00:00Z",
  updated_at: "2026-08-11T15:04:02Z",
  artifact_acquisition: null,
  configuration_rendering: null,
  trust_provisioning: null,
  data_initialization: null,
  service_deployment: serviceExecution,
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

const execution: BootstrapIdentityExecution = {
  execution_id: "phase-execution.identity.test",
  phase_id: "phase.identity",
  release_id: configuration.release_id,
  profile: configuration.profile,
  configuration_digest: configuration.configuration_digest,
  trust_plan_digest: trustPlan.trust_plan_digest,
  data_plan_digest: dataPlan.data_plan_digest,
  service_plan_digest: servicePlan.service_plan_digest,
  identity_schema_version: identityPlan.schema_version,
  identity_plan_digest: identityPlan.identity_plan_digest,
  target_id: identityPlan.target_id,
  state: "completed",
  result_code: "bootstrap.identity.completed",
  started_at: "2026-08-11T15:05:00Z",
  completed_at: "2026-08-11T15:05:01Z",
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

function identityResponse(options?: { replayed?: boolean }) {
  return {
    data: {
      run: {
        ...run,
        version: 9,
        completed_phase_ids: [...run.completed_phase_ids, "phase.identity"],
        current_phase_id: "phase.integrations",
        updated_at: execution.completed_at!,
        identity_handoff: execution,
      },
      execution,
      replayed: options?.replayed ?? false,
      synthetic_state_mutation_performed: true,
      credential_material_mutation_performed: false,
      directory_mutation_performed: false,
      provider_activation_performed: false,
      account_mutation_performed: false,
      session_or_token_mutation_performed: false,
      infrastructure_mutation_performed: false,
      ai_operation_performed: false,
    },
  };
}

function workspace(
  client: QueryClient,
  options?: { identityPlan?: BootstrapIdentityPlan; state?: BootstrapState },
) {
  return (
    <QueryClientProvider client={client}>
      <BootstrapIdentityHandoffWorkspace
        configuration={configuration}
        dataPlan={dataPlan}
        identityPlan={options?.identityPlan ?? identityPlan}
        scope={scope}
        servicePlan={servicePlan}
        state={options?.state ?? state}
        trustPlan={trustPlan}
      />
    </QueryClientProvider>
  );
}

function review(justification: string) {
  fireEvent.click(screen.getByRole("button", { name: "Review identity handoff" }));
  const confirm = screen.getByRole("button", { name: "Confirm identity" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Identity-handoff justification"), {
    target: { value: justification },
  });
  return confirm;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapIdentityHandoffWorkspace", () => {
  it("submits the exact reviewed identity plan and presents bounded synthetic evidence", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "identity-001" });
    const requests: Array<{ body: Record<string, unknown>; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      requests.push({
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>,
        idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return Promise.resolve(new Response(JSON.stringify(identityResponse()), { status: 200 }));
    });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Publish the reviewed secret-free Atlas identity state."));

    expect(await screen.findByText("Identity handoff completed")).toBeVisible();
    const receipt = screen.getByText("identity.handoff-state");
    expect(within(receipt.parentElement!).getByText("published")).toBeVisible();
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-identity.8.identity-001");
    expect(requests[0]?.body).toEqual({
      schema_version: "atlas.bootstrap-identity-handoff.v1",
      organization_id: scope.organization_id,
      environment_id: scope.environment_id,
      site_id: scope.site_id,
      expected_version: run.version,
      plan_digest: run.plan_digest,
      resume_key: run.resume_key,
      phase_id: "phase.identity",
      release_id: run.release_id,
      profile: run.profile,
      configuration_digest: configuration.configuration_digest,
      overlay: {},
      trust_plan_digest: trustPlan.trust_plan_digest,
      data_plan_digest: dataPlan.data_plan_digest,
      migration_artifact_digest: dataPlan.migration_artifact_digest,
      service_plan_digest: servicePlan.service_plan_digest,
      identity_schema_version: identityPlan.schema_version,
      identity_plan_digest: identityPlan.identity_plan_digest,
      target_id: identityPlan.target_id,
      expected_target_state: identityPlan.target_state,
      justification: "Publish the reviewed secret-free Atlas identity state.",
    });
    expect(screen.queryByText(/raw-secret|password=|Bearer|private key/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create account|activate provider|issue token/i })).not.toBeInTheDocument();
  });

  it("marks replayed evidence without exposing real identity or later controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "identity-replay" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(identityResponse({ replayed: true })), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(workspace(client));

    fireEvent.click(review("Replay the exact reviewed synthetic identity handoff result."));

    expect(await screen.findByText("Identity handoff completed (replayed)")).toBeVisible();
    expect(screen.queryByText(/credential verifier|directory bind password|session token/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /integration|rollback|network/i })).not.toBeInTheDocument();
  });

  it("cancels review without sending a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    render(workspace(client));

    review("Publish the identity plan but cancel before submission.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review identity handoff" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalidates an open review when identity-plan evidence changes", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const client = new QueryClient();
    const view = render(workspace(client));

    review("Publish only the exact currently reviewed identity-plan evidence.");
    view.rerender(
      workspace(client, {
        identityPlan: { ...identityPlan, identity_plan_digest: "9".repeat(64) },
      }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review identity handoff" })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fails closed for missing lease, incomplete probes, and duplicate identity mappings", () => {
    const client = new QueryClient();
    const view = render(
      workspace(client, { state: { ...state, lease_held_by_current_actor: false } }),
    );
    expect(screen.queryByRole("button", { name: "Review identity handoff" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        state: {
          ...state,
          run: {
            ...run,
            service_deployment: {
              ...serviceExecution,
              service_statuses: serviceExecution.service_statuses.map((service, index) =>
                index === 0 ? { ...service, readiness_passed: false } : service,
              ),
            },
          },
        },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review identity handoff" })).not.toBeInTheDocument();

    view.rerender(
      workspace(client, {
        identityPlan: {
          ...identityPlan,
          group_mappings: [
            identityPlan.group_mappings[0]!,
            {
              ...identityPlan.group_mappings[1]!,
              directory_group_reference:
                identityPlan.group_mappings[0]!.directory_group_reference,
            },
          ],
        },
      }),
    );
    expect(screen.queryByRole("button", { name: "Review identity handoff" })).not.toBeInTheDocument();
  });

  it("refreshes all authoritative evidence and requires a new review after failure", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "identity-failure" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "conflict" }), { status: 409 }),
    );
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(workspace(client));

    fireEvent.click(review("Publish the exact reviewed synthetic identity state now."));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence was refreshed");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review identity handoff" })).toBeVisible();
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-state"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-invalidation"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bootstrap-identity-plan"] });
  });
});
