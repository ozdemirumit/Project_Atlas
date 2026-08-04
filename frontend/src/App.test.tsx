import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const securityExportOverviewResponse = {
  data: {
    generated_at: "2026-08-04T10:00:00Z",
    mapping_version: "atlas-siem-mapping.v1",
    normalized_schema_version: "atlas-security-event.v1",
    destinations: [
      {
        destination_id: "destination.syslog.synthetic-siem",
        version: 1,
        name: "Enterprise SIEM synthetic TLS collector",
        state: "active",
        transport: "tls",
        host: "siem-collector.synthetic.local",
        port: 6514,
        tls_server_authentication: true,
        tls_hostname_validation: true,
        certificate_not_after: "2026-11-02T10:00:00Z",
        facility: 16,
        selected_categories: ["audit", "security", "platform"],
        classification_ceiling: "internal",
        max_queue_records: 100,
        max_attempts: 3,
      },
    ],
    health: [
      {
        destination_id: "destination.syslog.synthetic-siem",
        state: "active",
        queue_depth: 0,
        delivered_count: 4,
        retrying_count: 0,
        dead_letter_count: 0,
        certificate_days_remaining: 90,
        last_transport_handoff_at: "2026-08-04T09:58:00Z",
        collector_acknowledgement_available: true,
        siem_ingestion_confirmed: false,
        limitations: ["Transport handoff does not prove SIEM ingestion or parsing."],
      },
    ],
    recent_deliveries: [],
    preview_message: {
      priority: 134,
      message_id: "ATLAS_AUTHORIZATION_DECISION",
      payload:
        '<134>1 2026-08-04T10:00:00Z atlas-local atlas - ATLAS_AUTHORIZATION_DECISION [atlas@32473 eventId="evt_preview"] preview only',
      payload_bytes: 144,
      content_digest: "c".repeat(64),
    },
    safety_notice:
      "Transport delivery confirms only Syslog handoff. SIEM ingestion remains unconfirmed and no infrastructure action is authorized.",
  },
  meta: {
    correlation_id: "test-security-export-correlation",
    generated_at: "2026-08-04T10:00:00Z",
  },
};

const securityExportTestResponse = {
  data: {
    delivery_id: "delivery_test",
    destination_id: "destination.syslog.synthetic-siem",
    event_id: "evt_test",
    state: "transport_delivered",
    attempts: 1,
    queued_at: "2026-08-04T10:01:00Z",
    updated_at: "2026-08-04T10:01:00Z",
    next_attempt_at: null,
    last_error_code: null,
    receipt: {
      receipt_id: "receipt_test",
      destination_id: "destination.syslog.synthetic-siem",
      event_id: "evt_test",
      accepted_at: "2026-08-04T10:01:00Z",
      transport: "tls",
      collector_acknowledged: true,
      siem_ingestion_confirmed: false,
    },
  },
  meta: {
    correlation_id: "test-security-export-event-correlation",
    generated_at: "2026-08-04T10:01:00Z",
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

const sessionInventoryResponse = {
  data: {
    sessions: [
      {
        session_id: "session.test",
        version: 1,
        state: "active",
        credential_kind: "browser_session",
        created_at: "2026-08-04T09:00:00Z",
        last_seen_at: "2026-08-04T10:00:00Z",
        absolute_expires_at: "2026-08-04T17:00:00Z",
        idle_expires_at: "2026-08-04T10:15:00Z",
        current: true,
      },
      {
        session_id: "session.other",
        version: 2,
        state: "active",
        credential_kind: "browser_session",
        created_at: "2026-08-04T08:00:00Z",
        last_seen_at: "2026-08-04T09:55:00Z",
        absolute_expires_at: "2026-08-04T16:00:00Z",
        idle_expires_at: "2026-08-04T10:10:00Z",
        current: false,
      },
    ],
    truncated: false,
  },
  meta: {
    correlation_id: "test-session-inventory-correlation",
    generated_at: "2026-08-04T10:00:00Z",
  },
};

const apiCredentialInventoryResponse = {
  data: {
    credentials: [
      {
        credential_id: "credential.ui",
        version: 1,
        display_name: "Existing CLI",
        purpose: "Read the bounded storage overview.",
        state: "active",
        grants: [
          {
            permission_id: "storage.overview.read",
            scope_reference:
              "organization.development/environment.test/site.local/domain.storage/resource.storage.lab-overview/C1",
          },
        ],
        created_at: "2026-08-04T10:00:00Z",
        expires_at: "2026-08-04T10:30:00Z",
        last_used_at: null,
      },
    ],
    available_grants: [
      {
        permission_id: "storage.overview.read",
        scope_reference:
          "organization.development/environment.test/site.local/domain.storage/resource.storage.lab-overview/C1",
      },
      {
        permission_id: "graph.storage-impact.read",
        scope_reference:
          "organization.development/environment.test/site.local/domain.graph/resource.graph.storage-impact.synthetic/C1",
      },
    ],
    truncated: false,
  },
};

const issuedApiCredentialResponse = {
  data: {
    ...apiCredentialInventoryResponse.data.credentials[0],
    credential_id: "credential.created",
    display_name: "Operations CLI",
    purpose: "Read current storage evidence.",
    token: `atlas_pat_${"A".repeat(43)}`,
  },
};

const identityGovernanceResponse = {
  data: {
    sessions: [
      {
        session_id: "session.governed.operator",
        version: 3,
        subject_id: "subject.enterprise.operator",
        subject_display_name: "Storage Operator",
        provider_id: "provider.ldap.enterprise",
        state: "active",
        credential_kind: "browser_session",
        created_at: "2026-08-04T09:00:00Z",
        last_seen_at: "2026-08-04T10:00:00Z",
        absolute_expires_at: "2026-08-04T17:00:00Z",
        idle_expires_at: "2026-08-04T10:30:00Z",
      },
    ],
    api_credentials: [
      {
        credential_id: "credential.governed.operator",
        version: 4,
        subject_id: "subject.enterprise.operator",
        subject_display_name: "Storage Operator",
        provider_id: "provider.ldap.enterprise",
        display_name: "Operator dashboard reader",
        purpose: "Read bounded storage evidence from the operator dashboard.",
        state: "active",
        grants: [
          {
            permission_id: "storage.overview.read",
            scope_reference:
              "organization.enterprise/environment.test/site.local/domain.storage/resource.storage.lab-overview/C1",
          },
        ],
        created_at: "2026-08-04T09:10:00Z",
        expires_at: "2026-08-04T10:40:00Z",
        last_used_at: "2026-08-04T09:58:00Z",
      },
    ],
    truncated: false,
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

const rcaResponse = {
  data: {
    case_id: "rca_test",
    version: 1,
    prior_version_id: null,
    owner: "Storage Operations",
    requested_by: "subject.development.operator",
    state: "provisional",
    severity: "warning",
    created_at: "2026-08-04T10:00:00Z",
    updated_at: "2026-08-04T10:00:00Z",
    incident_references: [
      { reference_type: "incident", reference_id: "INC-LOCAL-B28", authority: "user" },
    ],
    target_id: "asset.storage.lab.b28",
    fault_families: ["storage_controller_or_path_degradation"],
    symptoms: [
      {
        symptom_id: "symptom.storage.warning",
        statement: "A current controller warning was observed.",
        first_observed_at: "2026-08-04T09:30:00Z",
        current_state: "observed warning; persistence and impact unknown",
        evidence_references: ["evidence.health"],
      },
    ],
    impact_scope: {
      affected_entities: ["asset.storage.lab.b28", "CTL01"],
      possibly_affected_services: ["Enterprise Resource Planning"],
      explicitly_unaffected_entities: ["CTL02"],
      current_impact: "A component warning is observed.",
      business_criticality: "Unknown",
      impact_confirmed: false,
      limitations: ["Graph reachability does not establish current service impact."],
    },
    source_investigation_artifact_id: "investigation_test",
    evidence: [],
    timeline: [],
    hypotheses: [
      {
        hypothesis_id: "rca-hypothesis.controller-path-degradation",
        rank: 1,
        fault_family: "storage_controller_or_path_degradation",
        cause_type: "contributing_cause",
        statement: "A controller or path condition may be contributing to the warning.",
        mechanism: "A degraded component could reduce redundancy.",
        expected_affected_entities: ["CTL01"],
        expected_unaffected_entities: ["CTL02"],
        expected_sequence: ["Condition begins", "Warning is observed"],
        supporting_evidence: ["evidence.health"],
        contradicting_evidence: ["evidence.peer"],
        missing_expected_observations: ["Current path state"],
        confounders: ["Transient warning"],
        assumptions: ["Target mapping is current"],
        confirmation_level: "supported",
        confidence_rationale: "Direct warning exists, but independent evidence is missing.",
        diagnostic_steps: [
          {
            step_id: "diagnostic.path-events",
            question: "Is the warning reproduced by current path evidence?",
            capability_id: "hitachi.opscenter.storage.path-events.read",
            capability_class: "C1",
            timeout_seconds: 30,
            max_output_records: 20,
          },
        ],
      },
    ],
    evidence_gaps: ["Current path and event-log evidence is missing."],
    blocker: "Evidence cannot distinguish persistent degradation from a transient warning.",
    safest_next_step: "Run the allowlisted C1 path and event read.",
    provisional_statement: {
      statement: "No root cause is confirmed. Path degradation is the leading candidate.",
      confirmation_level: "supported",
      supporting_evidence: ["evidence.health"],
      contradicting_evidence: ["evidence.peer"],
      residual_uncertainty: ["The warning has not been reproduced."],
      alternatives_not_ruled_out: ["Transient warning"],
      prevention_or_verification_implication: "Collect current path evidence before remediation.",
    },
    human_review: {
      status: "pending",
      reviewer_id: null,
      reviewed_at: null,
      decision_reason: null,
      domain_confirmation_criterion: null,
    },
    data_profile: "synthetic_lab",
    root_cause_confirmed: false,
    safety_notice:
      "Decision support only. This provisional RCA cannot authorize an infrastructure change.",
  },
  meta: {
    correlation_id: "test-rca-correlation",
    generated_at: "2026-08-04T10:00:00Z",
  },
};

const recommendationResponse = {
  data: {
    recommendation_id: "rec_test",
    version: 1,
    prior_version_id: null,
    owner: "Storage Operations",
    state: "ready_for_review",
    created_at: "2026-08-04T10:05:00Z",
    expires_at: "2026-08-04T14:05:00Z",
    target_id: "asset.storage.lab.b28",
    decision_question: "What is the safest next operational choice?",
    accountable_audience: "Storage Operations",
    horizon: "immediate_response",
    constraints: ["No infrastructure change", "C1 read-only maximum"],
    source_case_id: "rca_test",
    source_case_version: 1,
    source_case_state: "provisional",
    options: [
      {
        option_id: "recommendation.option.investigate",
        version: 1,
        category: "investigate",
        state: "viable",
        preference: "preferred",
        title: "Collect current path, event, and service evidence",
        intended_outcome: "Distinguish persistent degradation from a transient observation.",
        confidence: "supported",
        overall_risk: "low",
        duration: { minimum_minutes: 2, maximum_minutes: 5 },
        interruption: { expected_mode: "none expected from read-only evidence collection" },
        plan_steps: [
          {
            step_id: "step.investigate.path-events",
            order: 1,
            conceptual_action: "Collect one bounded current path and event snapshot.",
            capability_class: "C1",
            capability_id: "hitachi.opscenter.storage.path-events.read",
          },
        ],
        recovery: { rollback_feasible: true },
        policy_outcome: "permitted_for_human_initiation",
        exclusion_reasons: [],
      },
      {
        option_id: "recommendation.option.escalate",
        version: 1,
        category: "escalate",
        state: "viable",
        preference: "alternative",
        title: "Prepare an attributable vendor escalation package",
        intended_outcome: "Enable specialist review without exposing secrets or hidden targets.",
        confidence: "supported",
        overall_risk: "low",
        duration: { minimum_minutes: 10, maximum_minutes: 30 },
        interruption: { expected_mode: "none expected" },
        plan_steps: [
          {
            step_id: "step.escalate.package",
            order: 1,
            conceptual_action: "Prepare a redacted evidence and version summary.",
            capability_class: "C0",
            capability_id: "atlas.vendor.support.package.prepare",
          },
        ],
        recovery: { rollback_feasible: true },
        policy_outcome: "permitted_for_human_handoff",
        exclusion_reasons: [],
      },
      {
        option_id: "recommendation.option.defer",
        version: 1,
        category: "defer_no_action",
        state: "viable",
        preference: "alternative",
        title: "Defer change and monitor explicit triggers",
        intended_outcome: "Avoid premature change while keeping a bounded review trigger.",
        confidence: "suspected",
        overall_risk: "moderate",
        duration: { minimum_minutes: 0, maximum_minutes: 240 },
        interruption: { expected_mode: "none expected" },
        plan_steps: [
          {
            step_id: "step.defer.monitor",
            order: 1,
            conceptual_action: "Continue the approved bounded health observation until expiry.",
            capability_class: "C1",
            capability_id: "hitachi.opscenter.storage.hardware.read",
          },
        ],
        recovery: { rollback_feasible: true },
        policy_outcome: "permitted_with_expiry_and_trigger",
        exclusion_reasons: [],
      },
      {
        option_id: "recommendation.option.restoration-planning",
        version: 1,
        category: "restoration_planning",
        state: "blocked",
        preference: "ineligible",
        title: "Prepare controller failover restoration planning",
        intended_outcome: "Plan a human-governed restoration path if impact becomes active.",
        confidence: "insufficient",
        overall_risk: "critical",
        duration: { minimum_minutes: 0, maximum_minutes: 0 },
        interruption: { expected_mode: "not estimated because the option is blocked" },
        plan_steps: [
          {
            step_id: "step.restore.failover-plan",
            order: 1,
            conceptual_action: "Select an approved vendor failover procedure for planning.",
            capability_class: "C3",
            capability_id: "hitachi.opscenter.storage.controller-failover.plan",
          },
        ],
        recovery: { rollback_feasible: false },
        policy_outcome: "blocked_pending_readiness",
        exclusion_reasons: [
          "No current service impact is confirmed.",
          "Rollback and recovery are not established.",
        ],
      },
      {
        option_id: "recommendation.option.remediation-planning",
        version: 1,
        category: "remediation_planning",
        state: "blocked",
        preference: "ineligible",
        title: "Prepare permanent controller or path remediation planning",
        intended_outcome: "Plan correction only after the causal mechanism is supported.",
        confidence: "insufficient",
        overall_risk: "high",
        duration: { minimum_minutes: 0, maximum_minutes: 0 },
        interruption: { expected_mode: "not estimated because the option is blocked" },
        plan_steps: [
          {
            step_id: "step.remediate.plan",
            order: 1,
            conceptual_action: "Select an approved remediation procedure.",
            capability_class: "C3",
            capability_id: "hitachi.opscenter.storage.path-remediation.plan",
          },
        ],
        recovery: { rollback_feasible: false },
        policy_outcome: "blocked_pending_causal_and_change_readiness",
        exclusion_reasons: [
          "Root cause is not confirmed.",
          "Change impact and rollback are incomplete.",
        ],
      },
    ],
    comparisons: [
      {
        dimension: "evidence_strength",
        precedence: 1,
        option_values: [
          ["recommendation.option.investigate", "supported; 2 supporting"],
          ["recommendation.option.escalate", "supported; 2 supporting"],
          ["recommendation.option.defer", "suspected; 1 supporting"],
          ["recommendation.option.restoration-planning", "insufficient; 3 supporting"],
          ["recommendation.option.remediation-planning", "insufficient; 2 supporting"],
        ],
        rationale: "Applicability and evidence must be sufficient before preference.",
      },
      {
        dimension: "policy_and_readiness",
        precedence: 5,
        option_values: [
          ["recommendation.option.investigate", "permitted_for_human_initiation"],
          ["recommendation.option.escalate", "permitted_for_human_handoff"],
          ["recommendation.option.defer", "permitted_with_expiry_and_trigger"],
          ["recommendation.option.restoration-planning", "blocked_pending_readiness"],
          [
            "recommendation.option.remediation-planning",
            "blocked_pending_causal_and_change_readiness",
          ],
        ],
        rationale: "Policy exclusions override generated preference.",
      },
    ],
    preferred_option_id: "recommendation.option.investigate",
    preference_rationale:
      "The preferred option is bounded, read-only, reversible, and reduces the evidence gap.",
    policy_constraints: [
      "No Atlas execution authority is available.",
      "C3 planning remains blocked until readiness is current.",
    ],
    excluded_option_ids: [
      "recommendation.option.restoration-planning",
      "recommendation.option.remediation-planning",
    ],
    human_review: {
      status: "pending",
      reviewer_id: null,
      reviewed_at: null,
      rationale: null,
    },
    execution_authorized: false,
    safety_notice:
      "Decision support only. Recommendation review or approval does not authorize Atlas to execute an infrastructure change.",
  },
  meta: {
    correlation_id: "test-recommendation-correlation",
    generated_at: "2026-08-04T10:05:00Z",
  },
};

const approvalResponse = {
  data: {
    request_id: "approval_test",
    version: 1,
    state: "pending",
    packet: {
      canonicalization_version: "atlas-approval-packet.v1",
      canonical_digest: "d".repeat(64),
      requested_by: "subject.enterprise.requester",
      purpose: "Review the bounded evidence-supported operational recommendation.",
      created_at: "2026-08-04T10:06:00Z",
      expires_at: "2026-08-04T11:06:00Z",
      target_id: "asset.storage.lab.b28",
      recommendation_id: "rec_test",
      recommendation_version: 1,
      option_id: "recommendation.option.investigate",
      option_version: 1,
      option_title: "Collect current path, event, and service evidence",
      option_category: "investigate",
      option_confidence: "supported",
      confidence_rationale: "The current warning is direct, but path evidence is incomplete.",
      overall_risk: "low",
      risk_rationales: ["The bounded diagnostic is read-only and reversible."],
      evidence_references: ["evidence.health", "evidence.vendor"],
      evidence_summaries: [
        "A current controller warning was observed.",
        "Vendor guidance supports collecting path evidence before change.",
      ],
      alternatives: ["Prepare an attributable vendor escalation package"],
      assumptions: ["The approved read-only connector remains available."],
      unknowns: ["Current end-to-end path state is unknown."],
      affected_components: ["asset.storage.lab.b28"],
      possibly_affected_services: ["ERP Application Service"],
      blast_radius: "One storage system and possibly dependent ERP services.",
      impact_confirmed: false,
      graph_maturity: "D0-D1 dependency analysis",
      impact_gaps: ["Storage multipathing is not represented."],
      duration_minimum_minutes: 5,
      duration_maximum_minutes: 15,
      interruption_expected_mode: "none expected",
      interruption_worst_credible_mode: "diagnostic timeout only",
      interruption_expected_minutes: [0, 0],
      interruption_worst_credible_minutes: [0, 5],
      interruption_unknowns: ["Live service telemetry is unavailable."],
      plan_steps: [
        {
          order: 1,
          step_id: "step.investigate.path-events",
          conceptual_action: "Collect one bounded current path and event evidence package.",
          capability_id: "hitachi.opscenter.storage.path-events.read",
          capability_class: "C1",
          expected_output: "Current scoped path state and related events.",
          stop_condition: "Stop on timeout, stale data, scope mismatch, or output limit.",
        },
      ],
      preconditions: ["The target and connector scope remain current."],
      verification_criteria: ["Evidence is current and attributable."],
      stop_conditions: ["Stop when evidence freshness cannot be established."],
      recovery_strategy: "No infrastructure rollback is required for a read-only diagnostic.",
      rollback_feasible: true,
      recovery_duration_minimum_minutes: 0,
      recovery_duration_maximum_minutes: 1,
      recovery_gaps: ["No operational change is included."],
      policy_constraints: ["No Atlas execution authority is available."],
      execution_authorized: false,
    },
    decisions: [],
    execution_authorized: false,
  },
  meta: {
    correlation_id: "test-approval-correlation",
    generated_at: "2026-08-04T10:06:00Z",
  },
};

const approvedApprovalResponse = {
  ...approvalResponse,
  data: {
    ...approvalResponse.data,
    version: 2,
    state: "approved",
    decisions: [
      {
        decision_id: "approval_decision_test",
        request_version: 1,
        outcome: "approve",
        reviewer_id: "subject.enterprise.reviewer",
        decided_at: "2026-08-04T10:10:00Z",
        rationale: "The evidence supports this bounded read-only diagnostic plan.",
      },
    ],
  },
};

const reportResponse = {
  data: {
    report_id: "report_test",
    version: 1,
    prior_version_id: null,
    owner: "Storage Operations",
    state: "ready_for_review",
    requested_by: "subject.development.operator",
    created_at: "2026-08-04T10:10:00Z",
    expires_at: "2026-08-04T14:05:00Z",
    organization_id: "organization.development",
    environment_id: "environment.test",
    site_id: "site.local",
    target_id: "asset.storage.lab.b28",
    report_type: "technical_decision",
    audience: "technical_operations",
    classification: "internal",
    redaction_state: "complete",
    source: {
      recommendation_id: "rec_test",
      recommendation_version: 1,
      recommendation_state: "ready_for_review",
      recommendation_created_at: "2026-08-04T10:05:00Z",
      recommendation_expires_at: "2026-08-04T14:05:00Z",
      rca_case_id: "rca_test",
      rca_case_version: 1,
      target_id: "asset.storage.lab.b28",
      evidence_ids: ["evidence.health", "evidence.vendor"],
      component_versions: ["recommendation-artifact.v1"],
    },
    sections: [
      {
        section_id: "report.section.scope",
        title: "Scope and source lineage",
        state: "complete",
        statements: ["Target: asset.storage.lab.b28.", "Recommendation: rec_test version 1."],
        evidence_references: [],
        limitations: [],
      },
      {
        section_id: "report.section.preference",
        title: "Preferred option",
        state: "partial",
        statements: ["Collect current path, event, and service evidence"],
        evidence_references: ["evidence.health", "evidence.vendor"],
        limitations: ["Current service state is not independently observed."],
      },
      {
        section_id: "report.section.governance",
        title: "Governance and review boundary",
        state: "partial",
        statements: ["No Atlas execution authority is present."],
        evidence_references: [],
        limitations: ["An accountable human review remains pending."],
      },
    ],
    review: {
      status: "pending",
      reviewer_id: null,
      reviewed_at: null,
      rationale: null,
    },
    itsm_handoff: {
      draft_id: "itsm_draft_test",
      idempotency_key: "a".repeat(64),
      state: "review_required",
      external_system: "unconfigured_itsm",
      operation: "append_labeled_analysis",
      incident_reference: "INC-LOCAL-B28",
      report_id: "report_test",
      report_version: 1,
      generated_content_label: "Atlas generated decision-support draft",
      field_mappings: [
        {
          field: "work_notes",
          value: "Collect current path, event, and service evidence",
          source_reference: "report.section.preference",
        },
        {
          field: "u_atlas_report_reference",
          value: "report_test:v1",
          source_reference: "report_test",
        },
      ],
      artifact_references: ["recommendation:rec_test:v1", "report:report_test:v1"],
      classification: "internal",
      redaction_state: "complete",
      human_review_required: true,
      dispatch_authorized: false,
      external_record_mutated: false,
    },
    rendered_markdown: "# Atlas Technical Decision Report\n\nNo execution authority.",
    content_digest: "b".repeat(64),
    component_versions: ["technical-decision-report.v1"],
    data_profile: "synthetic_lab",
    execution_authorized: false,
    external_mutation_authorized: false,
    safety_notice:
      "Decision support only. Report generation and ITSM handoff preparation do not authorize Atlas to execute infrastructure changes or mutate an external ticket.",
  },
  meta: {
    correlation_id: "test-report-correlation",
    generated_at: "2026-08-04T10:10:00Z",
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "atlas_csrf=; Max-Age=0; path=/";
  window.history.replaceState({}, "", "/");
});

describe("Atlas application shell", () => {
  it("shows the governed operations workspace and platform status", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const payload = url.includes("/identity/me")
        ? identityResponse
        : url.includes("/security-export/test-event")
          ? securityExportTestResponse
          : url.includes("/security-export/overview")
            ? securityExportOverviewResponse
        : url.includes("/storage/overview")
          ? storageResponse
          : url.includes("/health-checks/overview")
            ? healthCheckResponse
            : url.includes("/approvals/")
              ? approvalResponse
            : url.includes("/reports/storage")
              ? reportResponse
              : url.includes("/recommendations/storage")
                ? recommendationResponse
                : url.includes("/rca/storage")
                  ? rcaResponse
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
    expect(await screen.findByText("Syslog and SIEM delivery")).toBeVisible();
    expect(screen.getByText("Enterprise SIEM synthetic TLS collector")).toBeVisible();
    expect(screen.getByText("Not confirmed")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Send test event" }));
    expect(
      await screen.findByText(/Transport handoff recorded. SIEM ingestion remains unconfirmed/),
    ).toBeVisible();
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

    fireEvent.click(screen.getByRole("button", { name: "Build RCA case" }));

    expect(await screen.findByText("Ranked hypotheses")).toBeVisible();
    expect(screen.getByText("Bounded diagnostics")).toBeVisible();
    expect(screen.getByText("Provisional cause statement")).toBeVisible();
    expect(screen.getByText("INC-LOCAL-B28")).toBeVisible();
    expect(screen.getAllByText(/No root cause is confirmed/).length).toBeGreaterThan(0);
    expect(screen.getByText(/cannot authorize an infrastructure change/)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Compare options" }));

    expect(await screen.findByText("Compared options")).toBeVisible();
    expect(screen.getByText("Visible comparison dimensions")).toBeVisible();
    expect(
      screen.getAllByText("Collect current path, event, and service evidence").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Blocked by policy and readiness")).toHaveLength(2);
    expect(screen.getByText("No execution authority")).toBeVisible();
    expect(screen.getByText(/does not authorize Atlas to execute/)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Submit for human review" }));

    expect(await screen.findByText("Canonical packet digest")).toBeVisible();
    expect(screen.getByText("Separated reviewer required")).toBeVisible();
    expect(screen.getAllByText("No execution authority").length).toBeGreaterThan(0);
    expect(screen.getByText(/Impact remains unconfirmed/)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Generate report" }));

    expect(await screen.findByText("Structured report sections")).toBeVisible();
    expect(screen.getByText("Immutable source lineage")).toBeVisible();
    expect(screen.getByText("ITSM HANDOFF DRAFT")).toBeVisible();
    expect(screen.getByText("Not authorized")).toBeVisible();
    expect(screen.getByText("No external mutation authority")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download technical report" })).toBeEnabled();
    expect(screen.getByText(/mutate an external ticket/)).toBeVisible();
  });

  it("signs in through the browser session and signs out with CSRF", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    let authenticated = false;
    let logoutRequest: RequestInit | undefined;
    let revokeRequest: RequestInit | undefined;
    let createApiCredentialRequest: RequestInit | undefined;
    let revokeApiCredentialRequest: RequestInit | undefined;
    const enterpriseIdentity = {
      ...identityResponse,
      data: {
        ...identityResponse.data,
        display_name: "Directory Operator",
        authentication: {
          ...identityResponse.data.authentication,
          provider_id: "provider.ldap.enterprise",
          method: "ldap",
          assurance_level: "single_factor",
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/authentication/sessions/current")) {
        logoutRequest = init;
        authenticated = false;
        document.cookie = "atlas_csrf=; Max-Age=0; path=/";
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/authentication/sessions/session.other")) {
        revokeRequest = init;
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/authentication/api-credentials/credential.ui")) {
        revokeApiCredentialRequest = init;
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/authentication/api-credentials") && init?.method === "POST") {
        createApiCredentialRequest = init;
        return Promise.resolve(
          new Response(JSON.stringify(issuedApiCredentialResponse), {
            status: 201,
            headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
          }),
        );
      }
      if (url.endsWith("/authentication/api-credentials")) {
        return Promise.resolve(
          new Response(JSON.stringify(apiCredentialInventoryResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.endsWith("/authentication/sessions") && init?.method === "POST") {
        authenticated = true;
        document.cookie = "atlas_csrf=csrf_browser_test; path=/; SameSite=Strict";
        return Promise.resolve(
          new Response(JSON.stringify({ data: { session_id: "session.test" } }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.endsWith("/authentication/sessions")) {
        return Promise.resolve(
          new Response(JSON.stringify(sessionInventoryResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/identity/me") && !authenticated) {
        return Promise.resolve(new Response(null, { status: 401 }));
      }
      if (url.includes("/identity-governance")) {
        return Promise.resolve(new Response(null, { status: 403 }));
      }
      const payload = url.includes("/identity/me")
        ? enterpriseIdentity
        : url.includes("/security-export/overview")
          ? securityExportOverviewResponse
          : url.includes("/storage/overview")
            ? storageResponse
            : url.includes("/health-checks/overview")
              ? healthCheckResponse
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

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "operator" } });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "temporary-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Directory Operator")).toBeVisible();
    expect(screen.queryByDisplayValue("temporary-secret")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Browser sessions" })).toBeVisible();
    expect(screen.getByText("Current session")).toBeVisible();
    expect(await screen.findByRole("heading", { name: "Personal read-only tokens" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Operations CLI" },
    });
    fireEvent.change(screen.getByLabelText("Purpose"), {
      target: { value: "Read current storage evidence." },
    });
    fireEvent.click(screen.getByLabelText("Storage overview"));
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    const rawToken = issuedApiCredentialResponse.data.token;
    expect(await screen.findByText(rawToken)).toBeVisible();
    await waitFor(() => expect(createApiCredentialRequest?.method).toBe("POST"));
    const createApiHeaders = new Headers(createApiCredentialRequest?.headers);
    expect(createApiHeaders.get("X-CSRF-Token")).toBe("csrf_browser_test");
    expect(createApiCredentialRequest?.body).toContain('"permission_ids":["storage.overview.read"]');
    fireEvent.click(screen.getByRole("button", { name: "Dismiss API token" }));
    expect(screen.queryByText(rawToken)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revoke Existing CLI" }));
    await waitFor(() => expect(revokeApiCredentialRequest?.method).toBe("DELETE"));
    const revokeApiHeaders = new Headers(revokeApiCredentialRequest?.headers);
    expect(revokeApiHeaders.get("X-CSRF-Token")).toBe("csrf_browser_test");
    fireEvent.click(screen.getByRole("button", { name: "Revoke browser session" }));

    await waitFor(() => expect(revokeRequest?.method).toBe("DELETE"));
    const revokeHeaders = new Headers(revokeRequest?.headers);
    expect(revokeHeaders.get("X-CSRF-Token")).toBe("csrf_browser_test");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
    const logoutHeaders = new Headers(logoutRequest?.headers);
    expect(logoutRequest?.method).toBe("DELETE");
    expect(logoutHeaders.get("X-CSRF-Token")).toBe("csrf_browser_test");
  });

  it("discovers authorized identity governance and revokes exact foreign access", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    document.cookie = "atlas_csrf=csrf_governance_test; path=/; SameSite=Strict";
    const governanceRequests: { url: string; init: RequestInit | undefined }[] = [];
    const adminIdentity = {
      ...identityResponse,
      data: {
        ...identityResponse.data,
        subject_id: "subject.enterprise.admin",
        display_name: "Security Administrator",
        role_ids: ["role.security-administrator"],
        authentication: {
          ...identityResponse.data.authentication,
          provider_id: "provider.ldap.enterprise",
          method: "ldap",
          assurance_level: "multi_factor",
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity-governance") && init?.method === "POST") {
        governanceRequests.push({ url, init });
        return Promise.resolve(
          new Response(JSON.stringify({ data: {} }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/identity-governance")) {
        return Promise.resolve(
          new Response(JSON.stringify(identityGovernanceResponse), {
            status: 200,
            headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
          }),
        );
      }
      const payload = url.includes("/identity/me")
        ? adminIdentity
        : url.endsWith("/authentication/sessions")
          ? sessionInventoryResponse
          : url.endsWith("/authentication/api-credentials")
            ? apiCredentialInventoryResponse
            : url.includes("/security-export/overview")
              ? securityExportOverviewResponse
              : url.includes("/storage/overview")
                ? storageResponse
                : url.includes("/health-checks/overview")
                  ? healthCheckResponse
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

    expect(await screen.findByText("Security Administrator")).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "Administrative access review" }),
    ).toBeVisible();
    expect(screen.getAllByText("Storage Operator").length).toBeGreaterThan(0);
    expect(screen.getByText("Operator dashboard reader")).toBeVisible();
    expect(screen.queryByText(/atlas_pat_/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search identity governance"), {
      target: { value: "operator" },
    });
    await waitFor(() =>
      expect(
        vi.mocked(globalThis.fetch).mock.calls.some(([input]) => {
          const url =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.href
                : input.url;
          return url.includes("query=operator");
        }),
      ).toBe(true),
    );
    fireEvent.change(await screen.findByLabelText("Identity governance revocation reason"), {
      target: { value: "Operator access is no longer required." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Revoke session" }));
    fireEvent.click(screen.getByRole("button", { name: "Revoke token" }));

    await waitFor(() => expect(governanceRequests).toHaveLength(2));
    for (const request of governanceRequests) {
      const headers = new Headers(request.init?.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf_governance_test");
      expect(headers.get("Idempotency-Key")).toMatch(/^governance-(session|token)-/);
      expect(request.init?.body).toContain(
        '"reason":"Operator access is no longer required."',
      );
    }
    const [sessionRequest, tokenRequest] = governanceRequests;
    if (!sessionRequest || !tokenRequest) throw new Error("governance requests were not captured");
    expect(sessionRequest.url).toContain("session.governed.operator/revocations");
    expect(sessionRequest.init?.body).toContain('"expected_version":3');
    expect(tokenRequest.url).toContain("credential.governed.operator/revocations");
    expect(tokenRequest.init?.body).toContain('"expected_version":4');
  });

  it("keeps identity governance absent when enterprise discovery is forbidden", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const ordinaryIdentity = {
      ...identityResponse,
      data: {
        ...identityResponse.data,
        display_name: "Directory Operator",
        authentication: {
          ...identityResponse.data.authentication,
          provider_id: "provider.ldap.enterprise",
          method: "ldap",
          assurance_level: "single_factor",
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity-governance")) {
        return Promise.resolve(new Response(null, { status: 403 }));
      }
      const payload = url.includes("/identity/me")
        ? ordinaryIdentity
        : url.endsWith("/authentication/sessions")
          ? sessionInventoryResponse
          : url.endsWith("/authentication/api-credentials")
            ? apiCredentialInventoryResponse
            : url.includes("/security-export/overview")
              ? securityExportOverviewResponse
              : url.includes("/storage/overview")
                ? storageResponse
                : url.includes("/health-checks/overview")
                  ? healthCheckResponse
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

    expect(await screen.findByText("Directory Operator")).toBeVisible();
    await waitFor(() =>
      expect(
        vi.mocked(globalThis.fetch).mock.calls.some(([input]) => {
          const url =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.href
                : input.url;
          return url.includes("/identity-governance");
        }),
      ).toBe(true),
    );
    expect(
      screen.queryByRole("heading", { name: "Administrative access review" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/governance inventory failed/i)).not.toBeInTheDocument();
  });

  it("opens a linked immutable packet for a separated human decision", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    window.history.replaceState({}, "", "/?approval_request_id=approval_test");
    document.cookie = "atlas_csrf=csrf_approval_test; path=/; SameSite=Strict";
    let decisionRequest: RequestInit | undefined;
    const reviewerIdentity = {
      ...identityResponse,
      data: {
        ...identityResponse.data,
        subject_id: "subject.enterprise.reviewer",
        display_name: "Separated Reviewer",
        authentication: {
          ...identityResponse.data.authentication,
          provider_id: "provider.ldap.enterprise",
          method: "ldap",
          assurance_level: "single_factor",
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/approvals/approval_test/decisions")) {
        decisionRequest = init;
        return Promise.resolve(
          new Response(JSON.stringify(approvedApprovalResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/identity-governance")) {
        return Promise.resolve(new Response(null, { status: 403 }));
      }
      const payload = url.includes("/identity/me")
        ? reviewerIdentity
        : url.includes("/authentication/api-credentials")
          ? apiCredentialInventoryResponse
        : url.includes("/approvals/approval_test")
          ? approvalResponse
          : url.includes("/security-export/overview")
            ? securityExportOverviewResponse
            : url.includes("/storage/overview")
              ? storageResponse
              : url.includes("/health-checks/overview")
                ? healthCheckResponse
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

    expect(await screen.findByText("Separated Reviewer")).toBeVisible();
    expect(await screen.findByText("Canonical packet digest")).toBeVisible();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Decision rationale"), {
      target: { value: "The evidence supports this bounded read-only diagnostic plan." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Decision history")).toBeVisible();
    expect(screen.getByText(/by subject.enterprise.reviewer/)).toBeVisible();
    await waitFor(() => expect(decisionRequest?.method).toBe("POST"));
    const headers = new Headers(decisionRequest?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("csrf_approval_test");
    expect(headers.get("Idempotency-Key")).toMatch(/^approval-ui-/);
    expect(decisionRequest?.body).toContain('"expected_version":1');
  });
});
