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

const bootstrapIntegrationPlan = {
  data: {
    schema_version: "atlas.bootstrap-integration-plan.v1",
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
    integration_plan_digest: "7".repeat(64),
    target_id: "target.atlas-synthetic-integrations.primary",
    target_kind: "target-kind.synthetic-file-integrations",
    target_state: "empty",
    model_endpoint: {
      endpoint_id: "endpoint.model-gateway.local",
      owner_id: "owner.project-atlas",
      provider_type: "provider-type.openai-compatible",
      service_reference_id: "service-reference.model-gateway.local",
      credential_reference_id: "secret.model.local-reader",
      model_id: "model.atlas-local.synthetic",
      context_limit: 32768,
      output_limit: 4096,
      data_classification_ceiling: "classification.internal",
      residency_boundary_id: "residency.local",
      timeout_seconds: 30,
      max_retries: 1,
      rate_limit_per_minute: 60,
      concurrency_limit: 4,
      telemetry_classification: "classification.internal",
      approved_task_class_ids: ["task-class.infrastructure-analysis"],
    },
    integrations: [
      ["integration.model-gateway.local", "integration-type.model-gateway"],
      ["integration.enterprise-identity.metadata", "integration-type.enterprise-identity"],
      ["integration.security-export.metadata", "integration-type.security-export"],
      ["integration.storage-connector.readonly", "integration-type.storage-connector"],
    ].map(([integrationId, integrationType]) => ({
      integration_id: integrationId,
      integration_type: integrationType,
      owner_id: "owner.project-atlas",
      purpose_id: "purpose.bootstrap-validation",
      classification: "classification.internal",
      endpoint_reference_id: `endpoint-reference.${integrationId}`,
      trust_reference_id: "trust-reference.atlas-ca",
      credential_reference_id: null,
      scope_id: "scope.readonly",
      rate_limit_per_minute: 60,
      validation_operation_id: `operation.${integrationId}.read`,
      mapping_preview_id: `mapping-preview.${integrationId}`,
      data_flow_id: `data-flow.${integrationId}`,
      activation_state: "inactive",
    })),
    checks: Array.from({ length: 12 }, (_, index) => ({
      check_id: `check.integration.${index + 1}`,
      subject_id: index < 8 ? "endpoint.model-gateway.local" : `integration.subject.${index}`,
      state: "passed",
      result_code: `bootstrap.integration-check.${index + 1}.passed`,
      mandatory: true,
    })),
    state: "passed",
    result_code: "bootstrap.integration-plan.passed",
    generated_at: "2026-08-04T16:07:00Z",
    actual_model_request_authorized: false,
    network_request_authorized: false,
    secret_resolution_authorized: false,
    integration_activation_authorized: false,
    connector_invocation_authorized: false,
    infrastructure_mutation_authorized: false,
  },
};

const bootstrapVerificationPlan = {
  data: {
    schema_version: "atlas.bootstrap-verification-plan.v1",
    suite_version: "atlas.bootstrap-verification-suite.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    source_run_id: "bootstrap-run.ui-001",
    source_run_version: 15,
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    data_plan_digest: "5".repeat(64),
    service_plan_digest: "d".repeat(64),
    identity_plan_digest: "9".repeat(64),
    integration_plan_digest: "7".repeat(64),
    verification_plan_digest: "4".repeat(64),
    ingress_contract_id: "ingress.local-api-ui",
    target_id: "target.bootstrap-verification-report",
    target_kind: "target-kind.local-verification-report",
    target_state: "empty",
    checks: Array.from({ length: 15 }, (_, index) => ({
      check_id: `verify.ui-${index + 1}`,
      category_id: `category.${index < 12 ? "mandatory" : "optional"}`,
      subject_id: `subject.verification-${index + 1}`,
      state: index < 12 ? "passed" : "not_applicable",
      result_code: `verification.ui-${index + 1}.${index < 12 ? "passed" : "not-selected"}`,
      mandatory: index < 12,
    })),
    state: "passed",
    result_code: "bootstrap.verification-plan.passed",
    generated_at: "2026-08-04T16:08:00Z",
    external_operations_authorized: false,
  },
};

const bootstrapHandoffPlan = {
  data: {
    schema_version: "atlas.bootstrap-handoff-plan.v1",
    suite_version: "atlas.bootstrap-handoff-suite.v1",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    source_run_id: "bootstrap-run.ui-001",
    source_run_version: 17,
    configuration_digest: "b".repeat(64),
    trust_plan_digest: "f".repeat(64),
    data_plan_digest: "5".repeat(64),
    service_plan_digest: "d".repeat(64),
    identity_plan_digest: "9".repeat(64),
    integration_plan_digest: "7".repeat(64),
    verification_plan_digest: "4".repeat(64),
    verification_report_digest: "3".repeat(64),
    source_evidence_digest: "8".repeat(64),
    handoff_plan_digest: "2".repeat(64),
    ingress_contract_id: "ingress.local-api-ui",
    target_id: "target.bootstrap-handoff-report",
    target_kind: "target-kind.local-handoff-report",
    target_state: "empty",
    readiness_class: "developer_linux_lab_bootstrap_complete",
    readiness_claims: {
      production_ready: false,
      customer_integrations_validated: false,
      support_accepted: false,
      ha_certified: false,
      dr_certified: false,
      backup_restore_validated: false,
      release_approved: false,
    },
    known_limitation_ids: Array.from(
      { length: 7 },
      (_, index) => `limitation.ui-${index + 1}`,
    ),
    pending_action_ids: Array.from({ length: 7 }, (_, index) => `action.ui-${index + 1}`),
    owner_role_ids: Array.from({ length: 5 }, (_, index) => `owner-role.ui-${index + 1}`),
    missing_production_evidence_ids: Array.from(
      { length: 7 },
      (_, index) => `evidence.production-ui-${index + 1}`,
    ),
    checks: Array.from({ length: 15 }, (_, index) => ({
      check_id: `handoff.ui-${index + 1}`,
      category_id: `category.${index < 12 ? "mandatory" : "production"}`,
      subject_id: `subject.handoff-${index + 1}`,
      state: index < 12 ? "passed" : "not_applicable",
      result_code: `handoff.ui-${index + 1}.${index < 12 ? "passed" : "not-available"}`,
      mandatory: index < 12,
    })),
    state: "passed",
    result_code: "bootstrap.handoff-plan.passed",
    generated_at: "2026-08-04T16:09:00Z",
    external_operations_authorized: false,
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
      integration_validation: null,
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
          integration_validation: null,
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
          integration_validation: null,
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
                  integration_validation: null,
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
          integration_validation: null,
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
                  integration_validation: null,
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
          integration_validation: null,
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
                  integration_validation: null,
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

  it("validates synthetic integrations without network, secret, or activation controls", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "integration-request-001" });
    const identityExecution = {
      execution_id: "phase-execution.ui-identity-complete",
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
    const integrationState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 13,
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ],
          checkpoints: [
            ...[
              "phase.acquire",
              "phase.configure",
              "phase.trust",
              "phase.data",
              "phase.services",
              "phase.identity",
            ].map((phaseId) => ({
              phase_id: phaseId,
              state: "completed",
              safe_output_references: [`result.${phaseId.slice(6)}.verified`],
              recorded_at: "2026-08-04T16:06:01Z",
            })),
          ],
          completed_phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
          ],
          current_phase_id: "phase.integrations",
          identity_handoff: identityExecution,
          integration_validation: null,
          updated_at: "2026-08-04T16:06:01Z",
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
      if (url.includes("/bootstrap-integration-plan/preview")) {
        return Promise.resolve(
          new Response(JSON.stringify(bootstrapIntegrationPlan), { status: 200 }),
        );
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(integrationState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/integrations")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-integrations-001",
          phase_id: "phase.integrations",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_plan_digest: "5".repeat(64),
          service_plan_digest: "d".repeat(64),
          identity_plan_digest: "9".repeat(64),
          integration_schema_version: "atlas.bootstrap-integration-plan.v1",
          integration_plan_digest: "7".repeat(64),
          target_id: "target.atlas-synthetic-integrations.primary",
          state: "completed",
          result_code: "bootstrap.integrations.completed",
          started_at: "2026-08-04T16:07:00Z",
          completed_at: "2026-08-04T16:07:01Z",
          model_check_count: 8,
          integration_check_count: 4,
          mandatory_pass_count: 12,
          activation_count: 0,
          network_request_count: 0,
          secret_resolution_count: 0,
          checks: bootstrapIntegrationPlan.data.checks,
          evidence: [
            {
              evidence_id: "integrations.validation-state",
              sha256: "6".repeat(64),
              size_bytes: 2400,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...integrationState.data.run,
                  version: 15,
                  checkpoints: [
                    ...integrationState.data.run.checkpoints,
                    {
                      phase_id: "phase.integrations",
                      state: "completed",
                      safe_output_references: [`result.integrations.${"7".repeat(32)}`],
                      recorded_at: "2026-08-04T16:07:01Z",
                    },
                  ],
                  completed_phase_ids: [
                    ...integrationState.data.run.completed_phase_ids,
                    "phase.integrations",
                  ],
                  current_phase_id: "phase.verify",
                  integration_validation: execution,
                  updated_at: "2026-08-04T16:07:01Z",
                },
                execution,
                replayed: false,
                synthetic_state_mutation_performed: true,
                actual_model_request_performed: false,
                network_request_performed: false,
                secret_resolution_performed: false,
                integration_activation_performed: false,
                connector_invocation_performed: false,
                knowledge_ingestion_performed: false,
                infrastructure_mutation_performed: false,
                ai_advice_generated: false,
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

    fireEvent.click(await screen.findByRole("button", { name: "Review integrations" }));
    expect(screen.getByText("Confirm synthetic integration validation")).toBeVisible();
    expect(screen.getAllByText("inactive")).toHaveLength(4);
    expect(screen.getByText("No network or secret access")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm integrations" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Integration-validation justification"), {
      target: { value: "Validate the reviewed offline integration contracts for this lab run." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Integration validation completed")).toBeVisible();
    expect(screen.getByText("integrations.validation-state")).toBeVisible();
    expect(screen.getByText("Mandatory passes")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"integration_plan_digest":"' + "7".repeat(64));
    expect(requests[0]?.body).toContain('"expected_target_state":"empty"');
    expect(requests[0]?.idempotencyKey).toBe(
      "bootstrap-integrations.13.integration-request-001",
    );
    expect(
      screen.queryByRole("button", {
        name: /activate integration|resolve secret|send model request/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("reconciles end-to-end evidence without external operations", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "verification-request-001" });
    const integrationExecution = {
      execution_id: "phase-execution.ui-integrations-complete",
      phase_id: "phase.integrations",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_plan_digest: "f".repeat(64),
      data_plan_digest: "5".repeat(64),
      service_plan_digest: "d".repeat(64),
      identity_plan_digest: "9".repeat(64),
      integration_schema_version: "atlas.bootstrap-integration-plan.v1",
      integration_plan_digest: "7".repeat(64),
      target_id: "target.atlas-synthetic-integrations.primary",
      state: "completed",
      result_code: "bootstrap.integrations.completed",
      started_at: "2026-08-04T16:07:00Z",
      completed_at: "2026-08-04T16:07:01Z",
      model_check_count: 8,
      integration_check_count: 4,
      mandatory_pass_count: 12,
      activation_count: 0,
      network_request_count: 0,
      secret_resolution_count: 0,
      checks: bootstrapIntegrationPlan.data.checks,
      evidence: [
        {
          evidence_id: "integrations.validation-state",
          sha256: "6".repeat(64),
          size_bytes: 2400,
          disposition: "published",
        },
      ],
    };
    const verificationState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 15,
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ],
          checkpoints: [
            ...[
              "phase.acquire",
              "phase.configure",
              "phase.trust",
              "phase.data",
              "phase.services",
              "phase.identity",
              "phase.integrations",
            ].map((phaseId) => ({
              phase_id: phaseId,
              state: "completed",
              safe_output_references: [`result.${phaseId.slice(6)}.verified`],
              recorded_at: "2026-08-04T16:07:01Z",
            })),
          ],
          completed_phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
          ],
          current_phase_id: "phase.verify",
          integration_validation: integrationExecution,
          end_to_end_verification: null,
          updated_at: "2026-08-04T16:07:01Z",
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
      if (url.includes("/bootstrap-integration-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapIntegrationPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-verification-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapVerificationPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(verificationState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/verify")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-verification-001",
          phase_id: "phase.verify",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_plan_digest: "5".repeat(64),
          service_plan_digest: "d".repeat(64),
          identity_plan_digest: "9".repeat(64),
          integration_plan_digest: "7".repeat(64),
          verification_schema_version: "atlas.bootstrap-verification-plan.v1",
          suite_version: "atlas.bootstrap-verification-suite.v1",
          verification_plan_digest: "4".repeat(64),
          target_id: "target.bootstrap-verification-report",
          state: "completed",
          result_code: "bootstrap.verification.completed",
          started_at: "2026-08-04T16:08:00Z",
          completed_at: "2026-08-04T16:08:01Z",
          passed_count: 12,
          failed_count: 0,
          skipped_count: 0,
          not_applicable_count: 3,
          mandatory_pass_count: 12,
          unresolved_mandatory_count: 0,
          external_operation_count: 0,
          checks: bootstrapVerificationPlan.data.checks,
          evidence: [
            {
              evidence_id: "verification.end-to-end-report",
              sha256: "3".repeat(64),
              size_bytes: 3200,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...verificationState.data.run,
                  version: 17,
                  checkpoints: [
                    ...verificationState.data.run.checkpoints,
                    {
                      phase_id: "phase.verify",
                      state: "completed",
                      safe_output_references: [`result.verification.${"4".repeat(32)}`],
                      recorded_at: "2026-08-04T16:08:01Z",
                    },
                  ],
                  completed_phase_ids: [
                    ...verificationState.data.run.completed_phase_ids,
                    "phase.verify",
                  ],
                  current_phase_id: "phase.handoff",
                  end_to_end_verification: execution,
                  updated_at: "2026-08-04T16:08:01Z",
                },
                execution,
                replayed: false,
                synthetic_report_mutation_performed: true,
                model_request_performed: false,
                network_request_performed: false,
                secret_resolution_performed: false,
                connector_invocation_performed: false,
                knowledge_mutation_performed: false,
                workflow_execution_performed: false,
                approval_creation_performed: false,
                backup_restore_operation_performed: false,
                external_export_performed: false,
                infrastructure_mutation_performed: false,
                deployment_action_performed: false,
                ai_advice_generated: false,
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

    fireEvent.click(await screen.findByRole("button", { name: "Review verification" }));
    expect(screen.getByText("Confirm end-to-end verification")).toBeVisible();
    expect(screen.getByText("No skipped mandatory check")).toBeVisible();
    expect(screen.getByText("Evidence reconciliation only")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm verification" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Verification justification"), {
      target: { value: "Reconcile the reviewed bootstrap evidence for operational handoff." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("End-to-end verification completed")).toBeVisible();
    expect(screen.getByText("verification.end-to-end-report")).toBeVisible();
    expect(screen.getByText("Failed / skipped")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"verification_plan_digest":"' + "4".repeat(64));
    expect(requests[0]?.body).toContain('"expected_target_state":"empty"');
    expect(requests[0]?.idempotencyKey).toBe(
      "bootstrap-verification.15.verification-request-001",
    );
    expect(
      screen.queryByRole("button", {
        name: /run backup|call model|activate connector|execute workflow/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("completes a bounded lab handoff without asserting production readiness", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "handoff-request-001" });
    const verificationExecution = {
      execution_id: "phase-execution.ui-verification-complete",
      phase_id: "phase.verify",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_plan_digest: "f".repeat(64),
      data_plan_digest: "5".repeat(64),
      service_plan_digest: "d".repeat(64),
      identity_plan_digest: "9".repeat(64),
      integration_plan_digest: "7".repeat(64),
      verification_schema_version: "atlas.bootstrap-verification-plan.v1",
      suite_version: "atlas.bootstrap-verification-suite.v1",
      verification_plan_digest: "4".repeat(64),
      target_id: "target.bootstrap-verification-report",
      state: "completed",
      result_code: "bootstrap.verification.completed",
      started_at: "2026-08-04T16:08:00Z",
      completed_at: "2026-08-04T16:08:01Z",
      passed_count: 12,
      failed_count: 0,
      skipped_count: 0,
      not_applicable_count: 3,
      mandatory_pass_count: 12,
      unresolved_mandatory_count: 0,
      external_operation_count: 0,
      checks: bootstrapVerificationPlan.data.checks,
      evidence: [
        {
          evidence_id: "verification.end-to-end-report",
          sha256: "3".repeat(64),
          size_bytes: 3200,
          disposition: "published",
        },
      ],
    };
    const handoffState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 17,
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ],
          checkpoints: [
            ...[
              "phase.acquire",
              "phase.configure",
              "phase.trust",
              "phase.data",
              "phase.services",
              "phase.identity",
              "phase.integrations",
              "phase.verify",
            ].map((phaseId) => ({
              phase_id: phaseId,
              state: "completed",
              safe_output_references: [`result.${phaseId.slice(6)}.verified`],
              recorded_at: "2026-08-04T16:08:01Z",
            })),
          ],
          completed_phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
          ],
          current_phase_id: "phase.handoff",
          end_to_end_verification: verificationExecution,
          operational_handoff: null,
          updated_at: "2026-08-04T16:08:01Z",
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
      if (url.includes("/bootstrap-integration-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapIntegrationPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-handoff-plan/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapHandoffPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(handoffState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.includes("/phases/handoff")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        const execution = {
          execution_id: "phase-execution.ui-handoff-001",
          phase_id: "phase.handoff",
          release_id: "release.atlas.lab-0.1.0",
          profile: "linux_lab",
          configuration_digest: "b".repeat(64),
          trust_plan_digest: "f".repeat(64),
          data_plan_digest: "5".repeat(64),
          service_plan_digest: "d".repeat(64),
          identity_plan_digest: "9".repeat(64),
          integration_plan_digest: "7".repeat(64),
          verification_plan_digest: "4".repeat(64),
          verification_report_digest: "3".repeat(64),
          source_evidence_digest: "8".repeat(64),
          handoff_schema_version: "atlas.bootstrap-handoff-plan.v1",
          suite_version: "atlas.bootstrap-handoff-suite.v1",
          handoff_plan_digest: "2".repeat(64),
          target_id: "target.bootstrap-handoff-report",
          readiness_class: "developer_linux_lab_bootstrap_complete",
          readiness_claims: bootstrapHandoffPlan.data.readiness_claims,
          state: "completed",
          result_code: "bootstrap.handoff.completed",
          started_at: "2026-08-04T16:09:00Z",
          completed_at: "2026-08-04T16:09:01Z",
          passed_count: 12,
          not_applicable_count: 3,
          mandatory_pass_count: 12,
          known_limitation_count: 7,
          pending_action_count: 7,
          owner_role_count: 5,
          missing_production_evidence_count: 7,
          external_operation_count: 0,
          checks: bootstrapHandoffPlan.data.checks,
          evidence: [
            {
              evidence_id: "handoff.operational-report",
              sha256: "1".repeat(64),
              size_bytes: 4100,
              disposition: "published",
            },
          ],
        };
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                run: {
                  ...handoffState.data.run,
                  version: 19,
                  state: "completed",
                  checkpoints: [
                    ...handoffState.data.run.checkpoints,
                    {
                      phase_id: "phase.handoff",
                      state: "completed",
                      safe_output_references: [`result.handoff.${"2".repeat(32)}`],
                      recorded_at: "2026-08-04T16:09:01Z",
                    },
                  ],
                  completed_phase_ids: [
                    ...handoffState.data.run.completed_phase_ids,
                    "phase.handoff",
                  ],
                  current_phase_id: null,
                  operational_handoff: execution,
                  updated_at: "2026-08-04T16:09:01Z",
                },
                execution,
                replayed: false,
                synthetic_report_mutation_performed: true,
                model_request_performed: false,
                network_request_performed: false,
                secret_resolution_performed: false,
                connector_invocation_performed: false,
                knowledge_mutation_performed: false,
                workflow_execution_performed: false,
                approval_creation_performed: false,
                backup_restore_operation_performed: false,
                external_export_performed: false,
                support_bundle_export_performed: false,
                ticket_creation_performed: false,
                notification_performed: false,
                infrastructure_mutation_performed: false,
                deployment_action_performed: false,
                ai_advice_generated: false,
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

    fireEvent.click(await screen.findByRole("button", { name: "Review handoff" }));
    expect(screen.getByText("Confirm operational handoff")).toBeVisible();
    expect(screen.getByText("All seven claims remain false")).toBeVisible();
    expect(screen.getAllByText("Bounded handoff limitation")).toHaveLength(7);
    const confirm = screen.getByRole("button", { name: "Confirm handoff" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Handoff justification"), {
      target: { value: "Publish the reviewed developer and lab operational handoff evidence." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Operational handoff completed")).toBeVisible();
    expect(screen.getByText("handoff.operational-report")).toBeVisible();
    expect(screen.getByText(/Production readiness remains false/)).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"phase_id":"phase.handoff"');
    expect(requests[0]?.body).toContain('"verification_report_digest":"' + "3".repeat(64));
    expect(requests[0]?.body).toContain('"handoff_plan_digest":"' + "2".repeat(64));
    expect(requests[0]?.idempotencyKey).toBe("bootstrap-handoff.17.handoff-request-001");
    expect(
      screen.queryByRole("button", {
        name: /export support|create ticket|notify owner|approve production/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("previews and creates a bounded local support bundle after handoff", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "support-request-001" });
    const handoffExecution = {
      execution_id: "phase-execution.ui-handoff-complete",
      phase_id: "phase.handoff",
      release_id: "release.atlas.lab-0.1.0",
      profile: "linux_lab",
      configuration_digest: "b".repeat(64),
      trust_plan_digest: "f".repeat(64),
      data_plan_digest: "5".repeat(64),
      service_plan_digest: "d".repeat(64),
      identity_plan_digest: "9".repeat(64),
      integration_plan_digest: "7".repeat(64),
      verification_plan_digest: "4".repeat(64),
      verification_report_digest: "3".repeat(64),
      source_evidence_digest: "8".repeat(64),
      handoff_schema_version: "atlas.bootstrap-handoff-plan.v1",
      suite_version: "atlas.bootstrap-handoff-suite.v1",
      handoff_plan_digest: "2".repeat(64),
      target_id: "target.bootstrap-handoff-report",
      readiness_class: "developer_linux_lab_bootstrap_complete",
      readiness_claims: bootstrapHandoffPlan.data.readiness_claims,
      state: "completed",
      result_code: "bootstrap.handoff.completed",
      started_at: "2026-08-04T16:09:00Z",
      completed_at: "2026-08-04T16:09:01Z",
      passed_count: 12,
      not_applicable_count: 3,
      mandatory_pass_count: 12,
      known_limitation_count: 7,
      pending_action_count: 7,
      owner_role_count: 5,
      missing_production_evidence_count: 7,
      external_operation_count: 0,
      checks: bootstrapHandoffPlan.data.checks,
      evidence: [
        {
          evidence_id: "handoff.operational-report",
          sha256: "1".repeat(64),
          size_bytes: 4100,
          disposition: "published",
        },
      ],
    };
    const completedState = {
      data: {
        ...bootstrapState.data,
        run: {
          ...bootstrapState.data.run,
          version: 19,
          state: "completed",
          phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ],
          checkpoints: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ].map((phaseId) => ({
            phase_id: phaseId,
            state: "completed",
            safe_output_references: [`result.${phaseId.slice(6)}.verified`],
            recorded_at: "2026-08-04T16:09:01Z",
          })),
          completed_phase_ids: [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
          ],
          current_phase_id: null,
          operational_handoff: handoffExecution,
          updated_at: "2026-08-04T16:09:01Z",
        },
      },
    };
    const entries = [
      ["support.release-manifest", "10-release-manifest.json", true],
      ["support.bootstrap-summary", "20-bootstrap-summary.json", true],
      ["support.service-health", "30-service-health.json", false],
      ["support.configuration-schema", "40-configuration-schema.json", false],
      ["support.sanitized-diagnostics", "50-sanitized-diagnostics.json", false],
    ];
    const supportPreview = {
      data: {
        preview_id: "support-preview.ui-001",
        schema_version: "atlas.support-bundle-preview.v1",
        catalog_version: "atlas.synthetic-support-catalog.v1",
        source_run_id: completedState.data.run.run_id,
        source_run_version: 19,
        release_id: completedState.data.run.release_id,
        handoff_report_digest: "1".repeat(64),
        source_evidence_digest: "6".repeat(64),
        component_ids: entries.map((item) => item[0]),
        lookback_hours: 24,
        window_start: "2026-08-03T16:09:01Z",
        window_end: "2026-08-04T16:09:01Z",
        entries: entries.map(([entryId, fileName, mandatory], index) => ({
          entry_id: entryId,
          file_name: fileName,
          classification: "internal",
          mandatory,
          disposition: "included",
          reason_code: "selected_and_sanitized",
          size_bytes: 200 + index,
          sha256: `${index + 1}`.repeat(64),
        })),
        included_count: 5,
        excluded_count: 0,
        content_bytes: 1010,
        max_content_bytes: 524288,
        redaction_check_count: 54,
        preview_digest: "a".repeat(64),
        target_id: "target.support-bundle.ui-001",
        target_state: "empty",
        archive_sha256: "c".repeat(64),
        archive_size_bytes: 2500,
        generated_at: "2026-08-04T16:10:00Z",
        expires_at: "2026-08-05T16:10:00Z",
        exportable: true,
        external_transfer_performed: false,
        arbitrary_file_collection_performed: false,
        network_request_performed: false,
        model_inference_performed: false,
        infrastructure_mutation_performed: false,
      },
    };
    const backupEntries = [
      ["backup.release-state", "10-release-state.json", true],
      ["backup.configuration-state", "20-configuration-state.json", true],
      ["backup.checkpoint-state", "30-checkpoint-state.json", true],
      ["backup.verification-state", "40-verification-state.json", true],
      ["backup.identity-handoff", "50-identity-handoff.json", false],
      ["backup.integration-validation", "60-integration-validation.json", false],
      ["backup.operational-handoff", "70-operational-handoff.json", true],
    ];
    const backupPreview = {
      data: {
        preview_id: "backup-preview.ui-001",
        schema_version: "atlas.logical-backup-preview.v1",
        catalog_version: "atlas.synthetic-logical-backup-catalog.v1",
        source_run_id: completedState.data.run.run_id,
        source_run_version: 19,
        release_id: completedState.data.run.release_id,
        source_evidence_digest: "d".repeat(64),
        component_ids: backupEntries.map((item) => item[0]),
        entries: backupEntries.map(([entryId, fileName, mandatory], index) => ({
          entry_id: entryId,
          file_name: fileName,
          classification: "internal",
          mandatory,
          size_bytes: 300 + index,
          sha256: `${index + 1}`.repeat(64),
        })),
        content_bytes: 2121,
        max_content_bytes: 524288,
        preview_digest: "e".repeat(64),
        target_id: "target.logical-backup.ui-001",
        target_state: "empty",
        archive_sha256: "f".repeat(64),
        archive_size_bytes: 4200,
        generated_at: "2026-08-04T16:11:00Z",
        expires_at: "2026-08-05T16:11:00Z",
        creatable: true,
        external_transfer_performed: false,
        active_restore_performed: false,
        secret_export_performed: false,
        network_request_performed: false,
        infrastructure_mutation_performed: false,
      },
    };
    const upgradeReadiness = {
      data: {
        plan_id: "upgrade-plan.ui-001",
        schema_version: "atlas.upgrade-readiness-plan.v1",
        catalog_version: "atlas.synthetic-upgrade-catalog.v1",
        source_run_id: completedState.data.run.run_id,
        source_run_version: 19,
        source_release_id: "release.atlas.lab-0.1.0",
        source_release_version: "0.1.0",
        target_release_id: "release.atlas.lab-0.2.0",
        target_release_version: "0.2.0",
        profile: "linux_lab",
        source_configuration_digest: "b".repeat(64),
        source_schema_version: "schema.platform.v1",
        target_schema_version: "schema.platform.v2",
        target_manifest_digest: "8".repeat(64),
        backup_id: "logical-backup.ui-001",
        backup_archive_sha256: "f".repeat(64),
        restore_validation_id: "restore-validation.ui-001",
        restore_validation_digest: "9".repeat(64),
        source_evidence_digest: "7".repeat(64),
        migration_steps: [
          ["migration.application.compatibility", "application", false, 2],
          ["migration.schema.expand-v2", "schema_expand", true, 4],
          ["migration.projection.rebuild-v2", "projection_rebuild", false, 3],
        ].map(([stepId, kind, quiescence, minutes], index) => ({
          step_id: stepId,
          sequence: index + 1,
          migration_kind: kind,
          reversible: true,
          requires_quiescence: quiescence,
          estimated_minutes: minutes,
        })),
        service_dependency_ids: ["service.atlas-api", "service.atlas-web"],
        abort_criterion_ids: [
          "abort.readiness-check-failed",
          "abort.schema-expand-failed",
          "abort.target-readiness-failed",
          "abort.verification-regressed",
        ],
        rollback_step_ids: [
          "rollback.stop-target-routing",
          "rollback.restore-source-application",
          "rollback.reconcile-expand-schema",
          "rollback.verify-source-release",
        ],
        post_verification_check_ids: Array.from(
          { length: 6 },
          (_, index) => `verify.ui-${index + 1}`,
        ),
        readiness_checks: Array.from({ length: 12 }, (_, index) => ({
          check_id: `upgrade.check.ui-${index + 1}`,
          category_id: "category.ui",
          result_code: `upgrade.ui-${index + 1}.passed`,
          mandatory: true,
          passed: true,
        })),
        estimated_downtime_min_minutes: 6,
        estimated_downtime_max_minutes: 12,
        rollback_window_minutes: 60,
        rollback_supported: true,
        forward_recovery_required_after_step_id: null,
        state: "ready",
        plan_digest: "6".repeat(64),
        generated_at: "2026-08-04T16:12:00Z",
        expires_at: "2026-08-04T17:12:00Z",
        production_authorized: false,
        execution_authorized: false,
        active_state_mutation_performed: false,
      },
    };
    const upgradeSimulation = {
      data: {
        simulation_id: "upgrade-simulation.ui-001",
        schema_version: "atlas.upgrade-rollback-simulation.v1",
        state: "passed",
        source_run_id: completedState.data.run.run_id,
        source_run_version: 19,
        plan_id: "upgrade-plan.ui-001",
        plan_digest: "6".repeat(64),
        backup_id: "logical-backup.ui-001",
        restore_validation_id: "restore-validation.ui-001",
        steps: [
          "preflight",
          "quiesce-services",
          "schema-expand",
          "deploy-target",
          "stop-target-routing",
          "restore-source-application",
          "reconcile-schema",
          "verify-source",
        ].map((step, index) => ({
          step_id: `simulation.${step}`,
          sequence: index + 1,
          state: "simulated",
          result_code: index === 3 ? "simulation.abort.injected" : `simulation.ui-${index + 1}.passed`,
          rollback_applicable: index < 7,
          simulated_minutes: [0, 2, 4, 1, 0, 2, 1, 1][index],
        })),
        impacted_service_ids: ["service.atlas-api", "service.atlas-web"],
        post_verification_check_ids: Array.from(
          { length: 6 },
          (_, index) => `verify.ui-${index + 1}`,
        ),
        abort_injected_at_step_id: "simulation.deploy-target",
        rollback_decision: "rollback.decision.applicable",
        estimated_downtime_minutes: 10,
        simulation_digest: "5".repeat(64),
        created_at: "2026-08-04T16:12:01Z",
        isolated_target: true,
        reused: false,
        production_authorized: false,
        artifact_acquisition_performed: false,
        database_migration_performed: false,
        service_restart_performed: false,
        traffic_switch_performed: false,
        active_restore_performed: false,
        secret_resolution_performed: false,
        network_request_performed: false,
        model_inference_performed: false,
        infrastructure_mutation_performed: false,
      },
    };
    const changeReviewPreview = {
      data: {
        preview_id: "change-review-preview.ui-001",
        schema_version: "atlas.upgrade-change-review-preview.v1",
        source_run_id: completedState.data.run.run_id,
        source_run_version: 19,
        plan_id: upgradeReadiness.data.plan_id,
        plan_digest: upgradeReadiness.data.plan_digest,
        simulation_id: upgradeSimulation.data.simulation_id,
        simulation_digest: upgradeSimulation.data.simulation_digest,
        source_release_id: upgradeReadiness.data.source_release_id,
        source_release_version: upgradeReadiness.data.source_release_version,
        target_release_id: upgradeReadiness.data.target_release_id,
        target_release_version: upgradeReadiness.data.target_release_version,
        backup_id: upgradeReadiness.data.backup_id,
        restore_validation_id: upgradeReadiness.data.restore_validation_id,
        risk_class: "risk.medium",
        change_class: "change.reviewed-standard",
        impacted_service_ids: upgradeReadiness.data.service_dependency_ids,
        migration_step_ids: upgradeReadiness.data.migration_steps.map((item) => item.step_id),
        abort_criterion_ids: upgradeReadiness.data.abort_criterion_ids,
        rollback_step_ids: upgradeReadiness.data.rollback_step_ids,
        post_verification_check_ids: upgradeReadiness.data.post_verification_check_ids,
        assumption_ids: Array.from({ length: 4 }, (_, index) => `assumption.ui-${index + 1}`),
        unknown_ids: Array.from({ length: 4 }, (_, index) => `unknown.ui-${index + 1}`),
        residual_risk_ids: Array.from({ length: 3 }, (_, index) => `risk.ui-${index + 1}`),
        owner_role_ids: Array.from({ length: 4 }, (_, index) => `role.ui-${index + 1}`),
        evidence_digests: ["6", "7", "8", "5"].map((item) => item.repeat(64)),
        estimated_downtime_min_minutes: 6,
        estimated_downtime_max_minutes: 12,
        rollback_window_minutes: 60,
        state: "ready",
        preview_digest: "4".repeat(64),
        generated_at: "2026-08-04T16:13:00Z",
        expires_at: "2026-08-04T16:43:00Z",
        approval_granted: false,
        execution_authorized: false,
        dispatch_authorized: false,
        infrastructure_mutation_performed: false,
      },
    };
    const changeReviewPacket = {
      data: {
        ...changeReviewPreview.data,
        packet_id: "change-review-packet.ui-001",
        schema_version: "atlas.upgrade-change-review-packet.v1",
        state: "created",
        proposed_window_start: "2026-08-05T10:00:00Z",
        proposed_window_end: "2026-08-05T11:00:00Z",
        itsm_draft_id: "itsm-draft.ui-001",
        itsm_draft_title: "Review Atlas upgrade 0.1.0 to 0.2.0",
        itsm_draft_digest: "3".repeat(64),
        packet_digest: "2".repeat(64),
        created_at: "2026-08-04T16:14:00Z",
        reused: false,
        itsm_dispatched: false,
        notification_sent: false,
        workflow_executed: false,
      },
    };
    const humanReview = {
      data: {
        review_id: "change-human-review.ui-001",
        schema_version: "atlas.upgrade-change-human-review.v1",
        version: 1,
        state: "pending",
        packet_id: changeReviewPacket.data.packet_id,
        packet_digest: changeReviewPacket.data.packet_digest,
        requester_id: "subject.development.operator",
        risk_class: "risk.medium",
        change_class: "change.reviewed-standard",
        impacted_service_ids: changeReviewPacket.data.impacted_service_ids,
        evidence_digests: changeReviewPacket.data.evidence_digests,
        proposed_window_start: changeReviewPacket.data.proposed_window_start,
        proposed_window_end: changeReviewPacket.data.proposed_window_end,
        justification: "Route the exact packet through separated accountable review",
        required_role_ids: changeReviewPacket.data.owner_role_ids,
        stages: changeReviewPacket.data.owner_role_ids.map((roleId, index) => ({
          stage_id: [
            "stage.platform-technical",
            "stage.service-owner",
            "stage.security-review",
            "stage.change-authority",
          ][index],
          sequence: index + 1,
          required_role_id: roleId,
          quorum: 1,
          state: index === 0 ? "pending" : "waiting",
          packet_digest: changeReviewPacket.data.packet_digest,
          reviewer_id: null,
          decision_id: null,
          decided_at: null,
          rationale: null,
        })),
        decisions: [],
        canonical_digest: "1".repeat(64),
        created_at: "2026-08-04T16:15:00Z",
        updated_at: "2026-08-04T16:15:00Z",
        expires_at: "2026-08-04T20:15:00Z",
        reused: false,
        human_review_completed: false,
        approval_granted: false,
        itsm_dispatched: false,
        handoff_issued: false,
        workflow_executed: false,
        execution_authorized: false,
        infrastructure_mutation_performed: false,
      },
    };
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const recoveryRequests: Array<{ path: string; body: string }> = [];
    const upgradeRequests: Array<{ path: string; body: string; idempotencyKey: string | null }> = [];
    const changeReviewRequests: Array<{
      path: string;
      body: string;
      idempotencyKey: string | null;
    }> = [];
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
      if (url.includes("/bootstrap-plan")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapPlan), { status: 200 }));
      }
      if (url.includes("/bootstrap-state/current")) {
        return Promise.resolve(new Response(JSON.stringify(completedState), { status: 200 }));
      }
      if (url.includes("/bootstrap-invalidation/preview")) {
        return Promise.resolve(new Response(JSON.stringify(bootstrapInvalidation), { status: 200 }));
      }
      if (url.endsWith("/platform/support-bundles/preview")) {
        return Promise.resolve(new Response(JSON.stringify(supportPreview), { status: 200 }));
      }
      if (url.endsWith("/platform/backups/preview")) {
        return Promise.resolve(new Response(JSON.stringify(backupPreview), { status: 200 }));
      }
      if (url.includes("/platform/support-bundles/") && url.endsWith("/exports")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                export_id: "support-export.ui-001",
                state: "completed",
                source_run_id: completedState.data.run.run_id,
                source_run_version: 19,
                preview_digest: "a".repeat(64),
                archive_sha256: "c".repeat(64),
                archive_size_bytes: 2500,
                archive_name: "target.support-bundle.ui-001.zip",
                included_count: 5,
                excluded_count: 0,
                created_at: "2026-08-04T16:10:01Z",
                expires_at: "2026-08-11T16:10:01Z",
                reused: false,
                external_transfer_performed: false,
              },
            }),
            { status: 200 },
          ),
        );
      }
      if (url.endsWith(`/platform/backups/${completedState.data.run.run_id}`)) {
        recoveryRequests.push({ path: url, body: typeof init?.body === "string" ? init.body : "" });
        return Promise.resolve(new Response(JSON.stringify({ data: {
          backup_id: "logical-backup.ui-001", state: "completed",
          source_run_id: completedState.data.run.run_id, source_run_version: 19,
          preview_digest: "e".repeat(64), target_id: "target.logical-backup.ui-001",
          archive_sha256: "f".repeat(64), archive_size_bytes: 4200,
          archive_name: "target.logical-backup.ui-001.zip", entry_count: 7,
          created_at: "2026-08-04T16:11:01Z", expires_at: "2026-08-11T16:11:01Z",
          reused: false, external_transfer_performed: false, active_restore_performed: false,
        } }), { status: 200 }));
      }
      if (url.endsWith("/platform/backups/logical-backup.ui-001/restore-validations")) {
        recoveryRequests.push({ path: url, body: typeof init?.body === "string" ? init.body : "" });
        return Promise.resolve(new Response(JSON.stringify({ data: {
          validation_id: "restore-validation.ui-001", state: "passed",
          backup_id: "logical-backup.ui-001", archive_sha256: "f".repeat(64),
          validation_digest: "9".repeat(64),
          check_ids: ["archive", "manifest", "entries", "schemas", "relationships", "isolation"],
          entry_count: 7, validated_at: "2026-08-04T16:11:02Z", isolated_target: true,
          active_repository_write_performed: false, operational_recovery_performed: false,
          secret_restore_performed: false, network_request_performed: false, reused: false,
        } }), { status: 200 }));
      }
      if (url.endsWith("/platform/upgrades/readiness-preview")) {
        upgradeRequests.push({
          path: url,
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(JSON.stringify(upgradeReadiness), { status: 200 }),
        );
      }
      if (url.endsWith(`/platform/upgrades/${completedState.data.run.run_id}/simulations`)) {
        upgradeRequests.push({
          path: url,
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(JSON.stringify(upgradeSimulation), { status: 200 }),
        );
      }
      if (url.endsWith("/platform/upgrade-change-reviews/preview")) {
        changeReviewRequests.push({
          path: url,
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(JSON.stringify(changeReviewPreview), { status: 200 }),
        );
      }
      if (
        url.endsWith(
          `/platform/upgrade-change-reviews/${completedState.data.run.run_id}/packets`,
        )
      ) {
        changeReviewRequests.push({
          path: url,
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Promise.resolve(
          new Response(JSON.stringify(changeReviewPacket), { status: 200 }),
        );
      }
      if (
        url.endsWith(
          `/platform/upgrade-change-reviews/${changeReviewPacket.data.packet_id}/human-reviews`,
        )
      ) {
        changeReviewRequests.push({
          path: url,
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(humanReview), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ code: "denied" }), { status: 403 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    const review = await screen.findByRole("button", { name: "Review export" });
    expect(screen.getByText(/54 redaction checks/)).toBeVisible();
    fireEvent.click(review);
    expect(screen.getByText("Confirm local support bundle")).toBeVisible();
    expect(screen.getAllByText("included")).toHaveLength(5);
    const confirm = screen.getByRole("button", { name: "Confirm local export" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Support-export justification"), {
      target: { value: "Create the reviewed local support package for diagnostic triage." },
    });
    fireEvent.click(confirm);

    expect(await screen.findByText("Support bundle completed")).toBeVisible();
    expect(screen.getByText("target.support-bundle.ui-001.zip")).toBeVisible();
    expect(screen.getByText("External transfer")).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0]?.body).toContain('"confirmed":true');
    expect(requests[0]?.body).not.toContain('"external_transfer_performed"');
    expect(requests[0]?.idempotencyKey).toBe("support-bundle.19.support-request-001");

    fireEvent.click(await screen.findByRole("button", { name: "Review backup" }));
    expect(screen.getByText("Confirm local logical backup")).toBeVisible();
    expect(screen.getByText(/not a production database backup/i)).toBeVisible();
    const backupConfirm = screen.getByRole("button", { name: "Confirm local backup" });
    expect(backupConfirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Backup justification"), {
      target: { value: "Create the reviewed local logical recovery evidence." },
    });
    fireEvent.click(backupConfirm);

    expect(await screen.findByText("Logical backup completed")).toBeVisible();
    expect(screen.getByText("target.logical-backup.ui-001.zip")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Validate restore" }));
    expect(await screen.findByText("Isolated restore validation passed")).toBeVisible();
    expect(screen.getByText(/no active repository write or operational recovery/i)).toBeVisible();
    expect(recoveryRequests).toHaveLength(2);
    expect(recoveryRequests[0]?.body).toContain('"confirmed":true');
    expect(recoveryRequests[1]?.body).toContain('"confirmed_isolated":true');

    expect(await screen.findByText("Upgrade readiness passed")).toBeVisible();
    expect(screen.getByText("12/12")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review simulation" }));
    expect(screen.getByText("Confirm isolated upgrade rollback simulation")).toBeVisible();
    expect(screen.getAllByText("reversible")).toHaveLength(3);
    const simulationConfirm = screen.getByRole("button", {
      name: "Confirm isolated simulation",
    });
    expect(simulationConfirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Upgrade simulation justification"), {
      target: { value: "Review the isolated abort and rollback path before any change." },
    });
    fireEvent.click(simulationConfirm);

    expect(await screen.findByText("Upgrade rollback simulation passed")).toBeVisible();
    expect(screen.getByText("Abort injected; rollback applicable")).toBeVisible();
    expect(screen.getByText("8 steps")).toBeVisible();
    expect(upgradeRequests).toHaveLength(2);
    expect(upgradeRequests[0]?.body).toContain('"target_release_id":"release.atlas.lab-0.2.0"');
    expect(upgradeRequests[1]?.body).toContain('"confirmed_isolated":true');
    expect(upgradeRequests[1]?.body).not.toContain("production_authorized");
    expect(upgradeRequests[1]?.idempotencyKey).toBe(
      "upgrade-simulation.19.support-request-001",
    );

    fireEvent.click(screen.getByRole("button", { name: "Review change packet" }));
    expect(await screen.findByText("Confirm upgrade change review packet")).toBeVisible();
    expect(screen.getByText("Medium risk")).toBeVisible();
    const packetConfirm = screen.getByRole("button", { name: "Create review packet" });
    expect(packetConfirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Change review justification"), {
      target: { value: "Prepare this evidence packet for the scheduled human CAB review." },
    });
    fireEvent.click(
      screen.getByLabelText(
        "I acknowledge this packet does not approve or execute the change.",
      ),
    );
    fireEvent.click(packetConfirm);

    expect(await screen.findByText("Upgrade change review packet created")).toBeVisible();
    expect(screen.getByText("Review Atlas upgrade 0.1.0 to 0.2.0")).toBeVisible();
    expect(screen.getAllByText("No").length).toBeGreaterThanOrEqual(3);
    expect(changeReviewRequests).toHaveLength(2);
    expect(changeReviewRequests[0]?.body).toContain('"simulation_id":"upgrade-simulation.ui-001"');
    expect(changeReviewRequests[1]?.body).toContain('"acknowledged_no_authority":true');
    expect(changeReviewRequests[1]?.body).not.toContain("execution_authorized");
    expect(changeReviewRequests[1]?.idempotencyKey).toBe(
      "change-review.19.support-request-001",
    );

    fireEvent.click(screen.getByRole("button", { name: "Review routing" }));
    expect(await screen.findByText("Confirm separated human review")).toBeVisible();
    expect(screen.getByText(/four distinct eligible humans/i)).toBeVisible();
    const reviewConfirm = screen.getByRole("button", { name: "Create review stages" });
    expect(reviewConfirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review routing justification"), {
      target: { value: "Route this exact packet through separated accountable review." },
    });
    fireEvent.click(
      screen.getByLabelText(
        "I acknowledge review completion will not authorize execution.",
      ),
    );
    fireEvent.click(reviewConfirm);

    expect(await screen.findByText("Separated human review created")).toBeVisible();
    expect(screen.getByText("Requester is ineligible to self-review")).toBeVisible();
    expect(screen.getAllByText("waiting")).toHaveLength(3);
    expect(changeReviewRequests).toHaveLength(3);
    expect(changeReviewRequests[2]?.body).toContain('"acknowledged_no_authority":true');
    expect(changeReviewRequests[2]?.body).not.toContain("execution_authorized");
    expect(changeReviewRequests[2]?.idempotencyKey).toBe(
      "human-review.19.support-request-001",
    );
  });

  it("shows only assigned human reviews and records an acknowledged non-approval outcome", async () => {
    const reviewerIdentity = {
      data: {
        ...identity.data,
        subject_id: "subject.enterprise.platform-reviewer",
        display_name: "Platform Reviewer",
        role_ids: ["role.platform-owner"],
        effective_role_versions: ["role.platform-owner:v1"],
      },
    };
    const packetDigest = "2".repeat(64);
    const roles = [
      "role.platform-owner",
      "role.service-owner",
      "role.security-reviewer",
      "role.change-approver",
    ];
    const stages = roles.map((roleId, index) => ({
      stage_id: [
        "stage.platform-technical",
        "stage.service-owner",
        "stage.security-review",
        "stage.change-authority",
      ][index],
      sequence: index + 1,
      required_role_id: roleId,
      quorum: 1,
      state: index === 0 ? "pending" : "waiting",
      packet_digest: packetDigest,
      reviewer_id: null,
      decision_id: null,
      decided_at: null,
      rationale: null,
    }));
    const assignedReview = {
      review_id: "change-human-review.inbox-ui-001",
      schema_version: "atlas.upgrade-change-human-review.v1",
      version: 1,
      state: "pending",
      packet_id: "change-review-packet.inbox-ui-001",
      packet_digest: packetDigest,
      requester_id: "subject.enterprise.upgrade-requester",
      risk_class: "risk.medium",
      change_class: "change.reviewed-standard",
      impacted_service_ids: ["service.atlas-api", "service.atlas-web"],
      evidence_digests: ["3", "4", "5", "6"].map((value) => value.repeat(64)),
      proposed_window_start: "2026-08-05T10:00:00Z",
      proposed_window_end: "2026-08-05T11:00:00Z",
      justification: "Review exact upgrade evidence before any external handoff",
      required_role_ids: roles,
      stages,
      decisions: [],
      canonical_digest: "1".repeat(64),
      created_at: "2026-08-05T06:00:00Z",
      updated_at: "2026-08-05T06:00:00Z",
      expires_at: "2026-08-05T09:00:00Z",
      reused: false,
      human_review_completed: false,
      approval_granted: false,
      itsm_dispatched: false,
      handoff_issued: false,
      workflow_executed: false,
      execution_authorized: false,
      infrastructure_mutation_performed: false,
    };
    let decisionRecorded = false;
    let decisionBody = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(reviewerIdentity), { status: 200 }));
      }
      if (
        url.endsWith("/platform/upgrade-change-reviews/human-reviews") &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                items: decisionRecorded ? [] : [assignedReview],
                next_cursor: null,
                limit: 20,
              },
            }),
            { status: 200 },
          ),
        );
      }
      if (url.endsWith(`/${assignedReview.review_id}/decisions`)) {
        decisionBody = typeof init?.body === "string" ? init.body : "";
        decisionRecorded = true;
        return Promise.resolve(
          new Response(
            JSON.stringify({
              data: {
                ...assignedReview,
                version: 2,
                state: "needs_evidence",
                stages: stages.map((stage, index) =>
                  index === 0
                    ? {
                        ...stage,
                        state: "needs_evidence",
                        reviewer_id: reviewerIdentity.data.subject_id,
                        decision_id: "human-review-decision.inbox-ui-001",
                        decided_at: "2026-08-05T06:05:00Z",
                        rationale: "Current dependency evidence is required before approval",
                      }
                    : stage,
                ),
                decisions: [
                  {
                    decision_id: "human-review-decision.inbox-ui-001",
                    stage_id: "stage.platform-technical",
                    request_version: 1,
                    outcome: "needs_evidence",
                    reviewer_id: reviewerIdentity.data.subject_id,
                    reviewer_role_id: "role.platform-owner",
                    rationale: "Current dependency evidence is required before approval",
                    acknowledged_no_authority: true,
                    decided_at: "2026-08-05T06:05:00Z",
                  },
                ],
                updated_at: "2026-08-05T06:05:00Z",
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

    expect(await screen.findByText("1 assigned")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review request" }));
    expect(screen.getByRole("button", { name: "Approve" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Reject" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Needs evidence" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Defer" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Needs evidence" }));
    fireEvent.change(screen.getByLabelText("Decision rationale"), {
      target: { value: "Current dependency evidence is required before approval" },
    });
    fireEvent.click(
      screen.getByLabelText(/This decision records human review only/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Record decision" }));

    expect(await screen.findByText("Decision recorded")).toBeVisible();
    expect(await screen.findByText("0 assigned")).toBeVisible();
    expect(decisionBody).toContain('"outcome":"needs_evidence"');
    expect(decisionBody).toContain('"acknowledged_no_authority":true');
    expect(decisionBody).not.toContain("execution_authorized");
  });
});
