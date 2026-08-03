import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const platformResponse = {
  data: {
    service: "atlas-api",
    version: "0.1.0",
    environment: "test",
    status: "healthy",
    components: [],
    warnings: [],
  },
  meta: {
    correlation_id: "test-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const identityResponse = {
  data: {
    subject_id: "subject.development.operator",
    display_name: "Local Operator",
    subject_kind: "human",
    organization_id: "organization.development",
    role_ids: ["role.development.operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.development.local",
      method: "development",
      assurance_level: "development",
      authenticated_at: "2026-08-03T10:00:00Z",
    },
    scope: {
      organization_id: "organization.development",
      environment_id: "environment.test",
      site_id: "site.local",
      domain_id: "domain.identity",
      resource_id: "resource.identity.self",
      capability_class: "C0",
    },
    authorization_decision_id: "dec_test",
    effective_role_versions: ["role.development.operator:v1"],
    effective_assignment_versions: ["assignment.development.operator:v1"],
  },
  meta: {
    correlation_id: "test-identity-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const storageResponse = {
  data: {
    snapshot_id: "snapshot.storage.lab.001",
    organization_id: "organization.development",
    environment_id: "environment.test",
    site_id: "site.local",
    target_id: "target.hitachi.opscenter.lab",
    data_profile: "synthetic_lab",
    generated_at: "2026-08-03T10:00:00Z",
    assets: [
      {
        asset_id: "asset.storage.lab.g400",
        storage_device_id: "836000123456",
        vendor: "Hitachi Vantara",
        model: "VSP G400",
        serial_number: 123456,
        health: "healthy",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.inventory", "evidence.healthy"],
      },
      {
        asset_id: "asset.storage.lab.b28",
        storage_device_id: "A34000800556",
        vendor: "Hitachi Vantara",
        model: "VSP One B28",
        serial_number: 800556,
        health: "warning",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.inventory", "evidence.warning"],
      },
    ],
    findings: [
      {
        finding_id: "finding.storage.lab.controller-warning",
        asset_id: "asset.storage.lab.b28",
        severity: "warning",
        component: "CTL01",
        summary: "Controller CTL01 reports a vendor warning while its peer reports Normal.",
        observed_at: "2026-08-03T10:00:00Z",
        evidence_references: ["evidence.warning"],
        status: "open",
      },
    ],
    evidence: [
      {
        reference: "evidence.inventory",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic inventory fixture",
      },
      {
        reference: "evidence.healthy",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic hardware fixture",
      },
      {
        reference: "evidence.warning",
        source: "Hitachi Ops Center synthetic fixture",
        source_version: "11.0.x-contract.1",
        observed_at: "2026-08-03T10:00:00Z",
        freshness: "current",
        trust_basis: "Documentation-derived synthetic warning fixture",
      },
    ],
    investigation: {
      investigation_id: "investigation.storage.lab.001",
      title: "VSP One B28 controller warning",
      state: "provisional",
      summary: "A localized controller warning is present. No root cause is confirmed.",
      hypotheses: [
        {
          hypothesis_id: "hypothesis.storage.lab.thermal",
          title: "Localized controller condition",
          state: "possible",
          rationale: "Only CTL01 reports a warning.",
          confidence_basis: "Single documentation-derived health observation",
          evidence_references: ["evidence.warning"],
          contradicting_evidence: [],
        },
      ],
      unknowns: ["The warning duration is unknown."],
      next_checks: ["Repeat the approved C1 hardware-health read."],
      evidence_references: ["evidence.warning"],
      updated_at: "2026-08-03T10:00:00Z",
    },
    report: {
      report_id: "report.storage.lab.001",
      title: "Synthetic storage health assessment",
      generated_at: "2026-08-03T10:00:00Z",
      executive_summary: "One of two synthetic arrays has a controller warning.",
      confirmed_facts: ["Two storage systems are represented."],
      provisional_findings: ["The condition appears localized."],
      unknowns: ["The warning duration is unknown."],
      evidence_references: ["evidence.inventory", "evidence.warning"],
      safety_notice: "Decision support only. No infrastructure change is authorized.",
    },
  },
  meta: {
    correlation_id: "test-storage-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const graphResponse = {
  data: {
    snapshot_id: "snapshot.graph.lab.001",
    snapshot_generated_at: "2026-08-03T10:00:00Z",
    start_entity_id: "asset.storage.lab.b28",
    max_depth: 5,
    freshness: "fresh",
    completeness: "partial",
    entities: [
      ["asset.storage.lab.b28", "storage_system", "VSP One B28"],
      ["entity.volume.erp.prod", "volume", "ERP-PROD-VOL-01"],
      ["entity.datastore.erp.prod", "datastore", "ERP-PROD-DS-01"],
      ["entity.vm.erp.app.01", "virtual_machine", "erp-app-01"],
      ["entity.service.erp.application", "technical_service", "ERP Application Service"],
      ["entity.business-service.erp", "business_service", "Enterprise Resource Planning"],
    ].map(([entity_id, entity_type, display_name], index) => ({
      entity_id,
      entity_type,
      display_name,
      domain_id: `domain.${entity_type}`,
      observed_at: "2026-08-03T10:00:00Z",
      freshness: "fresh",
      confidence_basis: "Synthetic topology observation",
      evidence_references: [`evidence.entity.${index}`],
      classification: "internal",
      vendor: index === 0 ? "Hitachi" : null,
      product: null,
      model: index === 0 ? "VSP One B28" : null,
      lifecycle_state: "active",
    })),
    relationships: [
      ["rel.1", "backed_by", "entity.volume.erp.prod", "asset.storage.lab.b28"],
      ["rel.2", "backed_by", "entity.datastore.erp.prod", "entity.volume.erp.prod"],
      ["rel.3", "uses", "entity.vm.erp.app.01", "entity.datastore.erp.prod"],
      ["rel.4", "runs_on", "entity.service.erp.application", "entity.vm.erp.app.01"],
      [
        "rel.5",
        "depends_on",
        "entity.business-service.erp",
        "entity.service.erp.application",
      ],
    ].map(([relationship_id, relationship_type, source_entity_id, target_entity_id], index) => ({
      relationship_id,
      relationship_type,
      source_entity_id,
      target_entity_id,
      assertion_method: "observed",
      observed_at: "2026-08-03T10:00:00Z",
      freshness: "fresh",
      confidence_basis: "Synthetic topology observation",
      evidence_references: [`evidence.relationship.${index}`],
      classification: "internal",
    })),
    paths: [
      {
        scope: "possible",
        entity_ids: [
          "asset.storage.lab.b28",
          "entity.volume.erp.prod",
          "entity.datastore.erp.prod",
          "entity.vm.erp.app.01",
          "entity.service.erp.application",
          "entity.business-service.erp",
        ],
        relationship_ids: ["rel.1", "rel.2", "rel.3", "rel.4", "rel.5"],
        evidence_references: ["evidence.relationship.0", "evidence.relationship.4"],
      },
    ],
    evidence: [],
    direct_entity_ids: ["entity.volume.erp.prod"],
    possible_entity_ids: [
      "entity.datastore.erp.prod",
      "entity.vm.erp.app.01",
      "entity.service.erp.application",
      "entity.business-service.erp",
    ],
    technical_service_ids: ["entity.service.erp.application"],
    business_service_ids: ["entity.business-service.erp"],
    unknowns: ["Reachability does not establish service unavailability."],
    known_gaps: ["Storage multipathing is not represented."],
    outage_confirmed: false,
    digital_twin_maturity: "D0-D1 dependency analysis",
    data_profile: "synthetic_lab",
    safety_notice: "Dependencies indicate possible impact, not an outage.",
  },
  meta: {
    correlation_id: "test-graph-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const healthCheckResponse = {
  data: {
    generated_at: "2026-08-03T10:00:00Z",
    data_profile: "synthetic_lab",
    definitions: [
      {
        definition_id: "health-check.storage.controller-status",
        version: 1,
        title: "Storage controller status",
        owner: "Storage Operations",
        enabled: true,
        target_id: "target.hitachi.opscenter.lab",
        connector_id: "connector.hitachi.opscenter.synthetic",
        connector_version: "1.0.0",
        capability_id: "hitachi.opscenter.storage.hardware.read",
        capability_class: "C1",
        schedule: { interval_minutes: 15, anchor_at: "2026-08-03T00:00:00Z" },
        thresholds: [
          {
            metric: "controller.status",
            warning_condition: "vendor status equals Warning",
            critical_condition: "vendor status equals Critical or Failed",
            unit: null,
          },
        ],
        limits: {
          timeout_seconds: 5,
          max_steps: 3,
          max_evidence_records: 8,
          max_targets: 1,
        },
        evidence_requirements: ["Current hardware status"],
      },
    ],
    schedules: [
      {
        definition_id: "health-check.storage.controller-status",
        enabled: true,
        interval_minutes: 15,
        last_due_at: "2026-08-03T10:00:00Z",
        next_due_at: "2026-08-03T10:15:00Z",
      },
    ],
    latest_runs: [
      {
        run_id: "run.health.001",
        definition_id: "health-check.storage.controller-status",
        definition_version: 1,
        connector_id: "connector.hitachi.opscenter.synthetic",
        connector_version: "1.0.0",
        capability_id: "hitachi.opscenter.storage.hardware.read",
        target_id: "target.hitachi.opscenter.lab",
        trigger: "scheduled",
        requested_by: "service.health-check.scheduler",
        started_at: "2026-08-03T10:00:00Z",
        completed_at: "2026-08-03T10:00:00Z",
        state: "partial",
        step_count: 2,
        observations: [
          {
            observation_id: "observation.health.b28.ctl01",
            target_id: "asset.storage.lab.b28",
            component: "CTL01",
            metric: "controller.status",
            value: "Warning",
            unit: null,
            state: "warning",
            observed_at: "2026-08-03T10:00:00Z",
            freshness: "current",
            evidence_references: ["evidence.health.warning"],
          },
        ],
        findings: [
          {
            finding_id: "finding.health.b28.ctl01-warning",
            severity: "warning",
            title: "Controller warning requires correlation",
            summary: "CTL01 reports Warning while event-log evidence is unavailable.",
            observation_ids: ["observation.health.b28.ctl01"],
            evidence_references: ["evidence.health.warning"],
          },
        ],
        evidence: [
          {
            reference: "evidence.health.warning",
            source: "Hitachi Ops Center synthetic hardware fixture",
            source_version: "11.0.x-contract.1",
            observed_at: "2026-08-03T10:00:00Z",
            freshness: "current",
            trust_basis: "Documentation-derived allowlisted C1 response",
          },
        ],
        partial_reasons: ["Authorized storage event-log evidence is not configured."],
        unknowns: ["No root cause or service outage is established by this check."],
        safety_notice: "Read-only decision support.",
      },
    ],
    safety_notice:
      "Read-only decision support. Health-check results do not authorize an infrastructure change.",
  },
  meta: {
    correlation_id: "test-health-check-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

const investigationResponse = {
  data: {
    artifact_id: "investigation_test",
    version: 1,
    prior_version_id: null,
    target_id: "asset.storage.lab.b28",
    data_profile: "synthetic_lab",
    summary: {
      known: ["A current controller warning was observed."],
      inferred: ["Reduced redundancy is plausible, but impact is not established."],
      alternatives: ["Persistent path degradation", "Transient warning"],
      unknowns: ["Current end-to-end path state is unknown."],
      confidence: "low",
      confidence_rationale: "Current direct evidence conflicts and path telemetry is missing.",
      safest_next_check: "Run the bounded C1 path and event evidence read.",
      supported_decision: "Collect more read-only evidence.",
      unsupported_decision: "Do not declare root cause or outage.",
    },
    claims: [
      {
        claim_id: "claim.observation",
        epistemic_type: "observation",
        text: "A controller warning was observed.",
        confidence: "high",
        supporting_evidence: ["evidence.health"],
        contradicting_evidence: [],
      },
      {
        claim_id: "claim.unknown",
        epistemic_type: "unknown",
        text: "Current service impact is unknown.",
        confidence: "insufficient",
        supporting_evidence: [],
        contradicting_evidence: [],
      },
    ],
    hypotheses: [
      {
        hypothesis_id: "hypothesis.path",
        statement: "A path condition may be contributing to degradation.",
        state: "supported",
        confidence: "low",
        confidence_rationale: "A direct warning exists, but current path evidence is missing.",
        discriminating_checks: [
          {
            title: "Read current path and event evidence",
            capability_class: "C1",
          },
        ],
      },
      {
        hypothesis_id: "hypothesis.transient",
        statement: "The warning may be transient.",
        state: "unresolved",
        confidence: "low",
        confidence_rationale: "The peer remains available.",
        discriminating_checks: [
          {
            title: "Repeat the current state read",
            capability_class: "C1",
          },
        ],
      },
    ],
    timeline: [
      {
        event_id: "timeline.warning",
        occurred_at: "2026-08-03T10:00:00Z",
        summary: "A controller warning was observed.",
        evidence_references: ["evidence.health"],
      },
    ],
    stop_reason: "Evidence is insufficient to confirm root cause or current service impact.",
    safety_notice:
      "Decision support only. This artifact does not confirm root cause or outage and does not authorize an infrastructure change.",
  },
  meta: {
    correlation_id: "test-investigation-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Atlas application shell", () => {
  it("shows the governed operations workspace and platform status", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const payload = url.includes("/identity/me")
        ? identityResponse
        : url.includes("/storage/overview")
          ? storageResponse
          : url.includes("/health-checks/overview")
            ? healthCheckResponse
            : url.includes("/investigations/storage")
              ? investigationResponse
          : url.includes("/graph/storage-impact")
            ? graphResponse
          : platformResponse;
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Storage estate assessment" })).toBeVisible();
    expect(screen.getByText("Human decision required")).toBeVisible();
    expect(await screen.findByText("test")).toBeVisible();
    expect(await screen.findByText("Local Operator")).toBeVisible();
    expect(await screen.findAllByText("VSP One B28")).not.toHaveLength(0);
    expect(screen.getByText("VSP G400")).toBeVisible();
    expect(screen.getAllByText("CTL01").length).toBeGreaterThan(0);
    expect(screen.getByText("provisional", { selector: ".state-badge" })).toBeVisible();
    expect(screen.getAllByText("Synthetic lab").length).toBeGreaterThan(0);
    expect(screen.getByText(/No infrastructure change is authorized/)).toBeVisible();
    expect(await screen.findByText("Evidence-linked service path")).toBeVisible();
    expect(await screen.findByText("Enterprise Resource Planning")).toBeVisible();
    expect(screen.getByText("D0-D1 dependency analysis")).toBeVisible();
    expect(screen.getByText(/Dependencies indicate possible impact/)).toBeVisible();
    expect(await screen.findByText("Governed read-only checks")).toBeVisible();
    expect(screen.getAllByText("Storage controller status").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Run check" })).toBeEnabled();
    expect(screen.getByText("Every 15 min")).toBeVisible();
    expect(screen.getByText("Controller warning requires correlation")).toBeVisible();
    expect(screen.getByText(/event-log evidence is not configured/)).toBeVisible();
    expect(screen.getByText(/results do not authorize an infrastructure change/)).toBeVisible();
    expect(screen.getByText("Start a bounded investigation")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Start investigation" }));

    expect(await screen.findByText("Typed claim ledger")).toBeVisible();
    expect(screen.getByText("Alternative hypotheses")).toBeVisible();
    expect(screen.getByText("Normalized UTC timeline")).toBeVisible();
    expect(screen.getByText("Do not declare root cause or outage.")).toBeVisible();
    expect(screen.getByText(/does not confirm root cause or outage/)).toBeVisible();
  });
});
