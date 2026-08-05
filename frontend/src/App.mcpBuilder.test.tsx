import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  downloadMcpBuilderCandidateArchive,
  type McpBuilderCandidateHandoff,
} from "./api/mcpBuilder";

const candidateArchiveBytes = new TextEncoder().encode("candidate archive");
const candidateArchiveDigest =
  "2bec12b4b590104ae734d2d91e6d9f1bdbb938b65d031606bdb15ee7b1e9bd41";

const identity = {
  data: {
    subject_id: "subject.development.operator",
    display_name: "MCP Builder Reviewer",
    subject_kind: "human",
    organization_id: "organization.development",
    role_ids: ["role.development.operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.ldap.test",
      method: "ldap",
      assurance_level: "multi_factor",
      authenticated_at: "2026-08-05T12:00:00Z",
    },
    scope: {
      organization_id: "organization.development",
      environment_id: "environment.test",
      site_id: "site.local",
      domain_id: "domain.identity",
      resource_id: "resource.identity.self",
      capability_class: "C0",
    },
    authorization_decision_id: "decision.mcp-builder.ui",
    effective_role_versions: ["role.development.operator:v1"],
    effective_assignment_versions: ["assignment.development.mcp-builder-create:1"],
  },
};

const project = {
  data: {
    project_id: "mcp-builder-project.aaaaaaaaaaaaaaaaaaaaaaaa",
    schema_version: "atlas.mcp-builder-project.v1",
    version: 1,
    state: "analyzed",
    vendor: "Atlas Synthetic",
    product: "Storage Lab",
    intended_product_versions: ["1.0"],
    source_authority: "Vendor documentation portal",
    source_owner: "Platform engineering",
    documentation_version: "1.0",
    publication_date: "2026-08-05",
    license_id: "license.internal-review",
    redistribution_allowed: false,
    classification: "internal",
    openapi_version: "3.1.0",
    api_title: "Synthetic Storage API",
    api_version: "1.0",
    source_digest: "b".repeat(64),
    source_size_bytes: 640,
    declared_servers: ["https://lab-api.example.invalid"],
    capability_candidates: [
      {
        candidate_id: "builder-capability.read-systems",
        operation_id: "getSystems",
        method: "get",
        path: "/systems",
        summary: "Read synthetic storage systems",
        citation: `openapi://${"b".repeat(64)}/paths/~1systems/get`,
        proposed_capability_class: "C1",
        clarification_codes: [],
        generation_blocked: false,
      },
    ],
    findings: [],
    canonical_digest: "c".repeat(64),
    analyzed_at: "2026-08-05T12:00:00Z",
    reused: false,
    synthetic_or_lab_only: true,
    generated_artifact_created: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
  },
};

const checkpoint = {
  data: {
    checkpoint_id: "mcp-builder-design.dddddddddddddddddddddddd",
    schema_version: "atlas.mcp-builder-design-checkpoint.v1",
    version: 1,
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    reviewer_id: identity.data.subject_id,
    connector_boundary: "Read-only inventory and health evidence.",
    target_products: [project.data.product],
    network_destinations: project.data.declared_servers,
    configuration_keys: ["config.vendor-endpoint"],
    secret_reference_ids: ["secret.vendor-api-key"],
    entity_mappings: [
      { source_entity: "vendor.storage-system", atlas_entity: "atlas.storage-system" },
    ],
    capability_decisions: [
      {
        candidate_id: project.data.capability_candidates[0]?.candidate_id,
        decision: "include",
        analyzed_class: "C1",
        confirmed_class: "C1",
        required_permission: "storage.system.read",
        rationale: "Confirmed as an authenticated bounded read.",
        generation_eligible: true,
      },
    ],
    canonical_digest: "d".repeat(64),
    created_at: "2026-08-05T12:10:00Z",
    ready_for_generation_design: true,
    generated_artifact_created: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const generation = {
  data: {
    generation_id: "mcp-builder-generation.eeeeeeeeeeeeeeeeeeeeeeee",
    schema_version: "atlas.mcp-builder-generation.v1",
    version: 1,
    state: "quarantined",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    requested_by: identity.data.subject_id,
    language_profile: "atlas.python312.v1",
    template_version: "mcp-builder-python.v1",
    artifact_digest: "e".repeat(64),
    artifact_size_bytes: 214,
    files: [
      {
        relative_path: "README.md",
        media_type: "text/markdown",
        sha256: "f".repeat(64),
        size_bytes: 214,
        source_candidate_ids: [],
      },
    ],
    canonical_digest: "a".repeat(64),
    created_at: "2026-08-05T12:20:00Z",
    artifact_published: true,
    generated_artifact_created: true,
    validation_completed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    subprocess_invoked: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const generatedFile = {
  data: {
    generation_id: generation.data.generation_id,
    state: "quarantined",
    artifact_digest: generation.data.artifact_digest,
    file: generation.data.files[0],
    content: "# Quarantined Atlas Connector Draft\n\nNo runtime trust.\n",
    content_verified: true,
    quarantined: true,
    runtime_trust_granted: false,
    execution_authorized: false,
  },
};

const validationCodes = [
  "validation.artifact.integrity",
  "validation.artifact.reproducible",
  "validation.artifact.file-set",
  "validation.manifest.contract",
  "validation.python.project",
  "validation.python.ast-safety",
  "validation.schemas.contract",
  "validation.tests.fail-closed",
  "validation.permissions.complete",
  "validation.network.boundary",
  "validation.traceability.complete",
  "validation.entities.complete",
  "validation.security.secret-scan",
  "validation.documentation.complete",
  "validation.isolation.authority",
];

const validation = {
  data: {
    validation_id: "mcp-builder-validation.111111111111111111111111",
    schema_version: "atlas.mcp-builder-validation.v1",
    version: 1,
    state: "passed",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    generation_id: generation.data.generation_id,
    generation_digest: generation.data.canonical_digest,
    artifact_digest: generation.data.artifact_digest,
    organization_id: identity.data.organization_id,
    environment_id: "environment.development",
    validated_by: identity.data.subject_id,
    language_profile: "atlas.python312.v1",
    template_version: generation.data.template_version,
    validation_profile: "atlas.static-validation.python312.v1",
    validator_version: "mcp-builder-static-validator.v1",
    checks: validationCodes.map((code) => ({
      code,
      state: "passed",
      severity: "informational",
      summary: `${code} passed without executing generated code.`,
      evidence_paths: ["README.md"],
      remediation: null,
    })),
    passed_count: 15,
    failed_count: 0,
    skipped_count: 0,
    limitations: [
      "Generated code was parsed but was not imported, compiled, executed, or tested.",
      "A passing static report does not authorize packaging, registration, installation, or execution.",
    ],
    canonical_digest: "1".repeat(64),
    completed_at: "2026-08-05T12:30:00Z",
    validation_completed: true,
    static_validation_passed: true,
    runtime_self_test_performed: false,
    dependency_resolution_performed: false,
    domain_review_completed: false,
    security_review_completed: false,
    lab_validation_completed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    subprocess_invoked: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const domainReview = {
  data: {
    review_id: "mcp-builder-domain-review.222222222222222222222222",
    schema_version: "atlas.mcp-builder-domain-review.v1",
    version: 1,
    state: "accepted",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    generation_id: generation.data.generation_id,
    generation_digest: generation.data.canonical_digest,
    artifact_digest: generation.data.artifact_digest,
    validation_id: validation.data.validation_id,
    validation_digest: validation.data.canonical_digest,
    validation_profile: validation.data.validation_profile,
    validator_version: validation.data.validator_version,
    organization_id: identity.data.organization_id,
    environment_id: "environment.development",
    reviewed_by: "subject.domain.reviewer",
    review_profile: "atlas.domain-review.connector.v1",
    reviewer_contract_version: "mcp-builder-domain-review.v1",
    capability_decisions: [
      {
        candidate_id: project.data.capability_candidates[0]?.candidate_id,
        confirmed_class: "C1",
        decision: "accepted",
        supported_product_versions: project.data.intended_product_versions,
        vendor_permission: "storage.system.read",
        authentication_assessment:
          "Authentication uses an external governed secret reference.",
        side_effect_assessment:
          "The operation is read-only with no documented side effect.",
        error_behavior_assessment:
          "Errors, timeouts, pagination, and rate limits fail closed.",
        health_guidance_assessment:
          "A bounded response is informational health evidence.",
        evidence_citations: [project.data.capability_candidates[0]?.citation],
        missing_case_codes: [],
        rationale: "Authoritative source evidence supports the bounded behavior.",
      },
    ],
    accepted_count: 1,
    needs_evidence_count: 0,
    rejected_count: 0,
    summary: "Human domain review completed against the exact analyzed source lineage.",
    limitations: [
      "Human domain review does not prove vendor runtime behavior.",
      "Security review, lab validation, and candidate package approval remain required.",
    ],
    canonical_digest: "2".repeat(64),
    completed_at: "2026-08-05T12:40:00Z",
    domain_review_completed: true,
    domain_review_accepted: true,
    security_review_completed: false,
    lab_validation_completed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dependency_resolution_performed: false,
    runtime_self_test_performed: false,
    subprocess_invoked: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const securityControls = [
  "provenance",
  "supply_chain",
  "credentials",
  "network",
  "input_output",
  "injection_execution",
  "logging_redaction",
  "runner_privileges",
  "capability_governance",
];

const securityReview = {
  data: {
    review_id: "mcp-builder-security-review.333333333333333333333333",
    schema_version: "atlas.mcp-builder-security-review.v1",
    version: 1,
    state: "accepted",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    generation_id: generation.data.generation_id,
    generation_digest: generation.data.canonical_digest,
    artifact_digest: generation.data.artifact_digest,
    validation_id: validation.data.validation_id,
    validation_digest: validation.data.canonical_digest,
    validation_profile: validation.data.validation_profile,
    validator_version: validation.data.validator_version,
    domain_review_id: domainReview.data.review_id,
    domain_review_digest: domainReview.data.canonical_digest,
    domain_review_profile: domainReview.data.review_profile,
    domain_reviewer_contract_version: domainReview.data.reviewer_contract_version,
    domain_reviewed_by: domainReview.data.reviewed_by,
    organization_id: identity.data.organization_id,
    environment_id: "environment.development",
    reviewed_by: "subject.security.reviewer",
    review_profile: "atlas.security-review.connector.v1",
    reviewer_contract_version: "mcp-builder-security-review.v1",
    control_assessments: securityControls.map((control) => ({
      control,
      decision: "accepted",
      assessment: `Independent review confirms the bounded ${control} posture.`,
      evidence_references: [project.data.capability_candidates[0]?.citation],
      finding_codes: [],
      required_controls: [`Preserve the declared ${control} boundary.`],
    })),
    accepted_count: 9,
    needs_remediation_count: 0,
    rejected_count: 0,
    summary: "Independent security review completed against exact immutable evidence.",
    limitations: [
      "Security review covers the exact quarantined scaffold and declared evidence only.",
      "Dynamic scanning, lab validation, and candidate package approval remain required.",
    ],
    canonical_digest: "3".repeat(64),
    completed_at: "2026-08-05T12:50:00Z",
    security_review_completed: true,
    security_review_accepted: true,
    lab_validation_completed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    network_request_performed: false,
    model_inference_performed: false,
    dependency_resolution_performed: false,
    malware_or_dynamic_scan_performed: false,
    runtime_self_test_performed: false,
    subprocess_invoked: false,
    dynamic_code_execution_performed: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const labCheckCodes = [
  "lab.artifact_integrity",
  "lab.runner_isolation",
  "lab.secret_free_environment",
  "lab.network_denial",
  "lab.package_import",
  "lab.quarantine_contract",
  "lab.capability_fail_closed",
  "lab.bounded_output",
];

const labValidation = {
  data: {
    lab_validation_id: "mcp-builder-lab-validation.444444444444444444444444",
    schema_version: "atlas.mcp-builder-lab-validation.v1",
    version: 1,
    state: "passed",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    generation_id: generation.data.generation_id,
    generation_digest: generation.data.canonical_digest,
    artifact_digest: generation.data.artifact_digest,
    validation_id: validation.data.validation_id,
    validation_digest: validation.data.canonical_digest,
    domain_review_id: domainReview.data.review_id,
    domain_review_digest: domainReview.data.canonical_digest,
    domain_reviewed_by: domainReview.data.reviewed_by,
    security_review_id: securityReview.data.review_id,
    security_review_digest: securityReview.data.canonical_digest,
    security_reviewed_by: securityReview.data.reviewed_by,
    organization_id: identity.data.organization_id,
    environment_id: "environment.development",
    operated_by: "subject.lab.operator",
    lab_profile: "atlas.lab-validation.python312.v1",
    runner_contract_version: "mcp-builder-isolated-runner.v1",
    runtime_version: "python.3.12.10",
    checks: labCheckCodes.map((code) => ({
      code,
      state: "passed",
      severity: "info",
      summary: "The isolated synthetic check passed.",
      evidence_paths: ["artifact inventory"],
      remediation: null,
    })),
    passed_count: 8,
    failed_count: 0,
    skipped_count: 0,
    child_started: true,
    child_exit_code: 0,
    duration_ms: 87,
    output_digest: "4".repeat(64),
    output_size_bytes: 512,
    artifact_file_count: 14,
    artifact_size_bytes: 8192,
    workspace_removed: true,
    limitations: [
      "This result covers only the exact deterministic quarantined scaffold.",
      "No vendor target, credential, package, installation, or runtime trust was exercised.",
    ],
    canonical_digest: "5".repeat(64),
    completed_at: "2026-08-05T13:00:00Z",
    lab_validation_completed: true,
    lab_validation_passed: true,
    synthetic_fixture_used: true,
    secret_values_present: false,
    target_connected: false,
    network_request_performed: false,
    runtime_self_test_performed: true,
    subprocess_invoked: true,
    dynamic_code_execution_performed: true,
    dependency_resolution_performed: false,
    malware_or_dynamic_scan_performed: false,
    candidate_package_created: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const candidateHandoff = {
  data: {
    handoff_id: "mcp-builder-candidate-handoff.666666666666666666666666",
    schema_version: "atlas.mcp-builder-candidate-handoff.v1",
    version: 1,
    state: "candidate_quarantined",
    project_id: project.data.project_id,
    project_version: 1,
    project_digest: project.data.canonical_digest,
    source_digest: project.data.source_digest,
    checkpoint_id: checkpoint.data.checkpoint_id,
    checkpoint_digest: checkpoint.data.canonical_digest,
    generation_id: generation.data.generation_id,
    generation_digest: generation.data.canonical_digest,
    artifact_digest: generation.data.artifact_digest,
    validation_id: validation.data.validation_id,
    validation_digest: validation.data.canonical_digest,
    domain_review_id: domainReview.data.review_id,
    domain_review_digest: domainReview.data.canonical_digest,
    domain_reviewed_by: domainReview.data.reviewed_by,
    security_review_id: securityReview.data.review_id,
    security_review_digest: securityReview.data.canonical_digest,
    security_reviewed_by: securityReview.data.reviewed_by,
    lab_validation_id: labValidation.data.lab_validation_id,
    lab_validation_digest: labValidation.data.canonical_digest,
    lab_operated_by: labValidation.data.operated_by,
    organization_id: identity.data.organization_id,
    environment_id: "environment.development",
    custodied_by: "subject.package.custodian",
    handoff_profile: "atlas.candidate-handoff.python312.v1",
    archive_contract_version: "mcp-builder-candidate-zip.v1",
    package_filename: "atlas-synthetic-storage-lab-eeeeeeeeeeee.zip",
    package_digest: candidateArchiveDigest,
    package_size_bytes: candidateArchiveBytes.byteLength,
    package_entry_count: 15,
    generated_file_count: 14,
    generated_size_bytes: 8192,
    envelope_digest: "7".repeat(64),
    signature_state: "unsigned",
    capabilities: [
      {
        candidate_id: project.data.capability_candidates[0]?.candidate_id,
        capability_class: "C1",
        required_permission: "storage.system.read",
        supported_product_versions: project.data.intended_product_versions,
        source_citations: [project.data.capability_candidates[0]?.citation],
      },
    ],
    network_destinations: project.data.declared_servers,
    limitations: [
      "The archive remains quarantined until later independent lifecycle gates.",
      "Only the exact reviewed C0/C1 scaffold is included.",
    ],
    unsupported_behavior: [
      "Signing, registration, installation, enablement, and execution are unsupported.",
    ],
    manual_change_count: 0,
    canonical_digest: "8".repeat(64),
    created_at: "2026-08-05T13:10:00Z",
    candidate_package_created: true,
    package_signed: false,
    publisher_attested: false,
    registry_validation_completed: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    target_configured: false,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const packageAcquisition = {
  data: {
    acquisition_id: "connector-package-acquisition.999999999999999999999999",
    schema_version: "atlas.connector-package-acquisition.v1",
    version: 1,
    state: "quarantined",
    source_type: "mcp_builder_handoff",
    source_handoff_id: candidateHandoff.data.handoff_id,
    source_handoff_digest: candidateHandoff.data.canonical_digest,
    source_project_id: candidateHandoff.data.project_id,
    source_custodied_by: candidateHandoff.data.custodied_by,
    organization_id: candidateHandoff.data.organization_id,
    environment_id: candidateHandoff.data.environment_id,
    acquired_by: "subject.registry.intake",
    acquisition_profile: "atlas.connector-acquisition.builder-handoff.v1",
    archive_contract_version: "mcp-builder-candidate-zip.v1",
    package_filename: candidateHandoff.data.package_filename,
    package_digest: candidateHandoff.data.package_digest,
    package_size_bytes: candidateHandoff.data.package_size_bytes,
    publisher_identity: "unattested.generated",
    signature_state: "unsigned",
    attestation_state: "unattested",
    capabilities: candidateHandoff.data.capabilities.map((item) => ({
      capability_id: item.candidate_id,
      capability_class: item.capability_class,
      required_permission: item.required_permission,
      supported_product_versions: item.supported_product_versions,
    })),
    limitations: [
      "Acquisition preserves exact Builder package bytes in connector quarantine only.",
      "Signing, publisher attestation, registry validation, approval, installation, enablement, and runtime trust remain required.",
    ],
    canonical_digest: "9".repeat(64),
    acquired_at: "2026-08-05T14:00:00Z",
    package_acquired: true,
    integrity_verified: true,
    package_signed: false,
    publisher_attested: false,
    registry_validation_completed: false,
    connector_registered: false,
    connector_approved: false,
    connector_installed: false,
    connector_enabled: false,
    target_configured: false,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const packageValidation = {
  data: {
    validation_id: "connector-package-validation.aaaaaaaaaaaaaaaaaaaaaaaa",
    schema_version: "atlas.connector-package-validation.v1",
    version: 1,
    lifecycle: "validating",
    outcome: "passed",
    source_acquisition_id: packageAcquisition.data.acquisition_id,
    source_acquisition_digest: packageAcquisition.data.canonical_digest,
    source_handoff_id: candidateHandoff.data.handoff_id,
    source_handoff_digest: candidateHandoff.data.canonical_digest,
    source_project_id: candidateHandoff.data.project_id,
    source_acquired_by: packageAcquisition.data.acquired_by,
    organization_id: candidateHandoff.data.organization_id,
    environment_id: candidateHandoff.data.environment_id,
    validated_by: "subject.package.validator",
    validation_profile: "atlas.connector-validation-intake.builder-v1",
    validator_version: "atlas.connector-manifest-schema-validator.v1",
    package_digest: packageAcquisition.data.package_digest,
    package_size_bytes: packageAcquisition.data.package_size_bytes,
    manifest_path: "atlas-connector.yaml",
    manifest_digest: "b".repeat(64),
    capability_ids: packageAcquisition.data.capabilities.map((item) => item.capability_id),
    schema_evidence: [
      {
        relative_path: "schemas/config/config.schema.json",
        digest: "c".repeat(64),
        schema_id: "atlas://generated/config.schema.json",
        purpose: "configuration",
        capability_id: null,
      },
      {
        relative_path: "schemas/inputs/capability_read.schema.json",
        digest: "d".repeat(64),
        schema_id: "atlas://generated/capability.storage.health.read/input.schema.json",
        purpose: "capability_input",
        capability_id: "capability.storage.health.read",
      },
      {
        relative_path: "schemas/outputs/capability_read.schema.json",
        digest: "e".repeat(64),
        schema_id: "atlas://generated/capability.storage.health.read/output.schema.json",
        purpose: "capability_output",
        capability_id: "capability.storage.health.read",
      },
    ],
    checks: [
      ["validation.source.accepted", "ATLAS-CANDIDATE-HANDOFF.json"],
      ["validation.archive.contract", "ATLAS-CANDIDATE-HANDOFF.json"],
      ["validation.manifest.contract", "atlas-connector.yaml"],
      ["validation.schemas.contract", "schemas/config/config.schema.json"],
    ].map(([code, path]) => ({
      code,
      state: "passed",
      severity: "informational",
      summary: `Bounded ${code} evidence passed.`,
      evidence_paths: [path],
      remediation: "Preserve the exact bounded contract.",
    })),
    limitations: [
      "This report covers exact acquisition, archive, manifest, and JSON Schema intake only.",
      "Dependency, vulnerability, malware, secret-content, license, static-code, contract, runner, self-test, and lab validation remain incomplete.",
      "Signing, registration, installation, enablement, runtime trust, execution, and deployment remain prohibited.",
    ],
    canonical_digest: "f".repeat(64),
    validated_at: "2026-08-05T15:00:00Z",
    source_integrity_accepted: true,
    manifest_schema_validation_completed: true,
    dependency_scan_completed: false,
    vulnerability_scan_completed: false,
    malware_scan_completed: false,
    secret_content_scan_completed: false,
    license_scan_completed: false,
    static_code_validation_completed: false,
    contract_validation_completed: false,
    runner_validation_completed: false,
    lab_validation_completed: false,
    package_signed: false,
    publisher_attested: false,
    connector_registered: false,
    connector_approved: false,
    connector_installed: false,
    connector_enabled: false,
    target_configured: false,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

const packageInventory = {
  data: {
    inventory_id: "connector-package-inventory.bbbbbbbbbbbbbbbbbbbbbbbb",
    schema_version: "atlas.connector-package-supply-chain-inventory.v1",
    version: 1,
    lifecycle: "validating",
    outcome: "passed",
    source_validation_id: packageValidation.data.validation_id,
    source_validation_digest: packageValidation.data.canonical_digest,
    source_acquisition_id: packageValidation.data.source_acquisition_id,
    source_acquisition_digest: packageValidation.data.source_acquisition_digest,
    source_handoff_id: packageValidation.data.source_handoff_id,
    source_project_id: packageValidation.data.source_project_id,
    source_acquired_by: packageValidation.data.source_acquired_by,
    source_validated_by: packageValidation.data.validated_by,
    source_custodied_by: candidateHandoff.data.custodied_by,
    source_domain_reviewed_by: candidateHandoff.data.domain_reviewed_by,
    source_security_reviewed_by: candidateHandoff.data.security_reviewed_by,
    source_lab_operated_by: candidateHandoff.data.lab_operated_by,
    organization_id: packageValidation.data.organization_id,
    environment_id: packageValidation.data.environment_id,
    inventoried_by: identity.data.subject_id,
    inventory_profile: "atlas.connector-supply-chain-inventory.python312.v1",
    inspector_version: "atlas.connector-content-dependency-inspector.v1",
    package_digest: packageValidation.data.package_digest,
    package_size_bytes: packageValidation.data.package_size_bytes,
    files: [
      {
        relative_path: "pyproject.toml",
        digest: "1".repeat(64),
        size_bytes: 512,
        content_class: "build_metadata",
      },
    ],
    dependencies: [
      {
        name: "setuptools",
        version_constraint: ">=75,<76",
        kind: "build",
        source_path: "pyproject.toml",
      },
    ],
    inventory_digest: "2".repeat(64),
    dependency_set_digest: "3".repeat(64),
    runtime_dependency_count: 0,
    build_dependency_count: 1,
    dependency_lock_present: false,
    checks: [
      "inventory.source.accepted",
      "inventory.archive.contract",
      "inventory.content.classified",
      "inventory.project-metadata.contract",
      "inventory.dependencies.normalized",
    ].map((code) => ({
      code,
      state: "passed",
      severity: "informational",
      summary: `Bounded ${code} evidence passed.`,
      evidence_paths: ["pyproject.toml"],
      remediation: "Preserve the exact bounded contract.",
    })),
    limitations: [
      "This report proves exact package-content and dependency-declaration inventory only.",
      "Security and executable validation remain incomplete.",
    ],
    canonical_digest: "4".repeat(64),
    inventoried_at: "2026-08-05T16:00:00Z",
    content_inventory_completed: true,
    dependency_inventory_completed: true,
    vulnerability_scan_completed: false,
    malware_scan_completed: false,
    secret_content_scan_completed: false,
    prohibited_content_scan_completed: false,
    license_scan_completed: false,
    static_code_validation_completed: false,
    contract_validation_completed: false,
    runner_validation_completed: false,
    lab_validation_completed: false,
    package_signed: false,
    publisher_attested: false,
    connector_rejected: false,
    connector_registered: false,
    connector_approved: false,
    connector_installed: false,
    connector_enabled: false,
    target_configured: false,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MCP Builder workspace", () => {
  it("creates a quarantined scaffold and records static validation without authority", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.stubGlobal("crypto", { randomUUID: () => "mcp-builder-ui-001" });
    const requests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const designRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const generationRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const validationRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const domainReviewRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const securityReviewRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const labValidationRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const candidateHandoffRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const packageAcquisitionRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const packageValidationRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    const packageInventoryRequests: Array<{ body: string; idempotencyKey: string | null }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
      }
      if (url.endsWith("/api/v1/mcp-builder/projects")) {
        const headers = new Headers(init?.headers);
        requests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(project), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/design-checkpoints`)) {
        const headers = new Headers(init?.headers);
        designRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(checkpoint), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/generations`)) {
        const headers = new Headers(init?.headers);
        generationRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(generation), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/validations`)) {
        const headers = new Headers(init?.headers);
        validationRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(validation), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/domain-reviews`)) {
        const headers = new Headers(init?.headers);
        domainReviewRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(domainReview), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/security-reviews`)) {
        const headers = new Headers(init?.headers);
        securityReviewRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(securityReview), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/lab-validations`)) {
        const headers = new Headers(init?.headers);
        labValidationRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(labValidation), { status: 201 }));
      }
      if (url.endsWith(`/mcp-builder/projects/${project.data.project_id}/candidate-handoffs`)) {
        const headers = new Headers(init?.headers);
        candidateHandoffRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(candidateHandoff), { status: 201 }));
      }
      if (url.endsWith("/api/v1/connectors/package-acquisitions")) {
        const headers = new Headers(init?.headers);
        packageAcquisitionRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(packageAcquisition), { status: 201 }));
      }
      if (url.endsWith("/api/v1/connectors/package-validations")) {
        const headers = new Headers(init?.headers);
        packageValidationRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(packageValidation), { status: 201 }));
      }
      if (url.endsWith("/api/v1/connectors/package-supply-chain-inventories")) {
        const headers = new Headers(init?.headers);
        packageInventoryRequests.push({
          body: typeof init?.body === "string" ? init.body : "",
          idempotencyKey: headers.get("Idempotency-Key"),
        });
        return Promise.resolve(new Response(JSON.stringify(packageInventory), { status: 201 }));
      }
      if (
        url.endsWith(
          `/mcp-builder/projects/${project.data.project_id}/generation/files/README.md`,
        )
      ) {
        return Promise.resolve(new Response(JSON.stringify(generatedFile), { status: 200 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ code: "authorization_denied" }), { status: 403 }),
      );
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Connectors" }));
    fireEvent.change(screen.getByLabelText("Vendor"), {
      target: { value: "Atlas Synthetic" },
    });
    fireEvent.change(screen.getByLabelText("Product"), {
      target: { value: "Storage Lab" },
    });
    fireEvent.change(screen.getByLabelText("Product version"), {
      target: { value: "1.0" },
    });
    fireEvent.change(screen.getByLabelText("Documentation version"), {
      target: { value: "1.0" },
    });
    fireEvent.change(screen.getByLabelText("Source authority"), {
      target: { value: "Vendor documentation portal" },
    });
    fireEvent.change(screen.getByLabelText("Source owner"), {
      target: { value: "Platform engineering" },
    });
    fireEvent.change(screen.getByLabelText("License identifier"), {
      target: { value: "license.internal-review" },
    });
    const source = JSON.stringify({ openapi: "3.1.0", info: {}, paths: {} });
    fireEvent.change(screen.getByLabelText("OpenAPI JSON"), {
      target: { value: source },
    });

    const analyze = screen.getByRole("button", { name: "Analyze source" });
    await waitFor(() => expect(analyze).toBeEnabled());
    expect(screen.getByText("Pasted OpenAPI JSON")).toBeVisible();
    fireEvent.click(analyze);

    expect(await screen.findByText("Synthetic Storage API")).toBeVisible();
    expect(screen.getAllByText("getSystems")).toHaveLength(2);
    expect(screen.getByText("Read-only candidate")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Decision" })).toHaveValue("include");
    fireEvent.click(
      screen.getByLabelText(/I confirm this checkpoint records design evidence only/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm design checkpoint" }));

    expect(await screen.findByText("Design checkpoint recorded")).toBeVisible();
    expect(screen.getByText(checkpoint.data.checkpoint_id)).toBeVisible();
    expect(screen.getByText("Create a Python review scaffold")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I authorize deterministic file creation inside quarantine/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create quarantined scaffold" }));

    expect(await screen.findByText(generation.data.generation_id)).toBeVisible();
    expect(screen.getByText("No runtime trust.", { exact: false })).toBeVisible();
    expect(screen.getByText("Not run")).toBeVisible();
    expect(screen.getByText("Inspect the quarantined scaffold")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I understand this produces static evidence only/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run static validation" }));

    expect(await screen.findByText(validation.data.validation_id)).toBeVisible();
    expect(screen.getByText("Static validation passed")).toBeVisible();
    expect(screen.getByText("validation.python.ast-safety")).toBeVisible();
    expect(screen.getByText("Validation boundaries")).toBeVisible();
    expect(screen.getByText("Confirm vendor semantics by capability")).toBeVisible();
    expect(
      screen.getByRole("combobox", {
        name: `Domain decision ${project.data.capability_candidates[0]?.candidate_id}`,
      }),
    ).toHaveValue("accepted");
    fireEvent.click(
      screen.getByLabelText(/I am the accountable human domain reviewer/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Record domain review" }));

    expect(await screen.findByText(domainReview.data.review_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE DOMAIN REVIEW")).toBeVisible();
    expect(screen.getByText("No declared evidence gaps")).toBeVisible();
    expect(screen.getByText(domainReview.data.reviewed_by)).toBeVisible();
    expect(screen.getByText("Assess the quarantined scaffold")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Security decision provenance" })).toHaveValue(
      "accepted",
    );
    fireEvent.click(
      screen.getByLabelText(/I am the independent human security reviewer/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Record security review" }));

    expect(await screen.findByText(securityReview.data.review_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE SECURITY REVIEW")).toBeVisible();
    expect(screen.getAllByText("No declared security findings")).toHaveLength(9);
    expect(screen.getByText(securityReview.data.reviewed_by)).toBeVisible();
    expect(screen.getByText("Verify the fail-closed scaffold")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I am the independent lab operator/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run isolated validation" }));

    expect(await screen.findByText(labValidation.data.lab_validation_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE LAB EVIDENCE")).toBeVisible();
    expect(screen.getByText(labValidation.data.runtime_version)).toBeVisible();
    expect(screen.getByText("capability fail closed")).toBeVisible();
    expect(screen.getByText("Create the quarantined candidate")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I am the independent package custodian/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create candidate package" }));

    expect(await screen.findByText(candidateHandoff.data.handoff_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE PACKAGE EVIDENCE")).toBeVisible();
    expect(screen.getByText("candidate quarantined")).toBeVisible();
    expect(screen.getByText("Unsigned")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download verified archive" })).toBeVisible();
    expect(screen.getByText("Transfer package custody")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I am the independent registry intake operator/i),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Acquire into connector quarantine" }),
    );

    expect(await screen.findByText(packageAcquisition.data.acquisition_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE ACQUISITION RECEIPT")).toBeVisible();
    expect(screen.getByText("Verified")).toBeVisible();
    expect(screen.getByText("Unattested")).toBeVisible();
    expect(screen.getAllByText("Not run")).toHaveLength(2);
    expect(screen.getByText("Validate manifest and schemas")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I am the independent package validator/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run package intake validation" }));

    expect(await screen.findByText(packageValidation.data.validation_id)).toBeVisible();
    expect(screen.getAllByText("IMMUTABLE VALIDATION REPORT")).toHaveLength(2);
    expect(screen.getAllByText("validation.manifest.contract")).toHaveLength(2);
    expect(screen.getAllByText("Validation boundaries")).toHaveLength(2);
    expect(screen.getByText("Inventory content and dependencies")).toBeVisible();
    fireEvent.click(
      screen.getByLabelText(/I am the independent supply-chain inventory operator/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create supply-chain inventory" }));

    expect(await screen.findByText(packageInventory.data.inventory_id)).toBeVisible();
    expect(screen.getByText("IMMUTABLE SUPPLY-CHAIN INVENTORY")).toBeVisible();
    expect(screen.getByText("inventory.dependencies.normalized")).toBeVisible();
    expect(screen.getByText("Inventory boundaries")).toBeVisible();
    expect(screen.getByText("build_metadata")).toBeVisible();
    expect(screen.getByText("build: setuptools>=75,<76")).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|execute|register|enable/i })).not.toBeInTheDocument();
    expect(requests).toHaveLength(1);
    expect(designRequests).toHaveLength(1);
    expect(generationRequests).toHaveLength(1);
    expect(validationRequests).toHaveLength(1);
    expect(domainReviewRequests).toHaveLength(1);
    expect(securityReviewRequests).toHaveLength(1);
    expect(labValidationRequests).toHaveLength(1);
    expect(candidateHandoffRequests).toHaveLength(1);
    expect(packageAcquisitionRequests).toHaveLength(1);
    expect(packageValidationRequests).toHaveLength(1);
    expect(packageInventoryRequests).toHaveLength(1);
    expect(requests[0]?.idempotencyKey).toBe("mcp-builder.mcp-builder-ui-001");
    const body = JSON.parse(requests[0]?.body ?? "{}") as Record<string, unknown>;
    expect(body.source_document).toBe(source);
    expect(body.confirmed_synthetic_or_lab_only).toBe(true);
    expect(body).not.toHaveProperty("connector_enabled");
    expect(designRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-design.mcp-builder-ui-001",
    );
    const designBody = JSON.parse(designRequests[0]?.body ?? "{}") as Record<string, unknown>;
    expect(designBody.project_digest).toBe(project.data.canonical_digest);
    expect(designBody.network_destinations).toEqual(project.data.declared_servers);
    expect(designBody).not.toHaveProperty("runtime_trust_granted");
    expect(designBody).not.toHaveProperty("generated_artifact_created");
    expect(generationRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-generation.mcp-builder-ui-001",
    );
    const generationBody = JSON.parse(
      generationRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(generationBody.project_digest).toBe(project.data.canonical_digest);
    expect(generationBody.checkpoint_digest).toBe(checkpoint.data.canonical_digest);
    expect(generationBody.language_profile).toBe("atlas.python312.v1");
    expect(generationBody.acknowledged_quarantine).toBe(true);
    expect(generationBody).not.toHaveProperty("runtime_trust_granted");
    expect(generationBody).not.toHaveProperty("execute");
    expect(validationRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-validation.mcp-builder-ui-001",
    );
    const validationBody = JSON.parse(
      validationRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(validationBody.project_digest).toBe(project.data.canonical_digest);
    expect(validationBody.checkpoint_digest).toBe(checkpoint.data.canonical_digest);
    expect(validationBody.generation_digest).toBe(generation.data.canonical_digest);
    expect(validationBody.artifact_digest).toBe(generation.data.artifact_digest);
    expect(validationBody.validation_profile).toBe(
      "atlas.static-validation.python312.v1",
    );
    expect(validationBody.acknowledged_static_only).toBe(true);
    expect(validationBody).not.toHaveProperty("runtime_trust_granted");
    expect(validationBody).not.toHaveProperty("execute");
    expect(domainReviewRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-domain-review.mcp-builder-ui-001",
    );
    const domainReviewBody = JSON.parse(
      domainReviewRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(domainReviewBody.validation_digest).toBe(validation.data.canonical_digest);
    expect(domainReviewBody.review_profile).toBe("atlas.domain-review.connector.v1");
    expect(domainReviewBody.acknowledged_human_domain_decision).toBe(true);
    expect(domainReviewBody.capability_decisions).toEqual([
      expect.objectContaining({
        candidate_id: project.data.capability_candidates[0]?.candidate_id,
        decision: "accepted",
        vendor_permission: "storage.system.read",
        evidence_citations: [project.data.capability_candidates[0]?.citation],
        missing_case_codes: [],
      }),
    ]);
    expect(domainReviewBody).not.toHaveProperty("security_review_completed");
    expect(domainReviewBody).not.toHaveProperty("execute");
    expect(securityReviewRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-security-review.mcp-builder-ui-001",
    );
    const securityReviewBody = JSON.parse(
      securityReviewRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(securityReviewBody.domain_review_digest).toBe(
      domainReview.data.canonical_digest,
    );
    expect(securityReviewBody.review_profile).toBe(
      "atlas.security-review.connector.v1",
    );
    expect(securityReviewBody.acknowledged_independent_security_decision).toBe(true);
    expect(securityReviewBody.control_assessments).toHaveLength(9);
    expect(securityReviewBody.control_assessments).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          control: "provenance",
          decision: "accepted",
          evidence_references: [project.data.capability_candidates[0]?.citation],
          finding_codes: [],
        }),
      ]),
    );
    expect(securityReviewBody).not.toHaveProperty("lab_validation_completed");
    expect(securityReviewBody).not.toHaveProperty("execute");
    expect(labValidationRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-lab-validation.mcp-builder-ui-001",
    );
    const labValidationBody = JSON.parse(
      labValidationRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(labValidationBody.security_review_id).toBe(securityReview.data.review_id);
    expect(labValidationBody.security_review_digest).toBe(
      securityReview.data.canonical_digest,
    );
    expect(labValidationBody.lab_profile).toBe(
      "atlas.lab-validation.python312.v1",
    );
    expect(labValidationBody.acknowledged_isolated_synthetic_execution).toBe(true);
    expect(labValidationBody).not.toHaveProperty("target");
    expect(labValidationBody).not.toHaveProperty("secret");
    expect(labValidationBody).not.toHaveProperty("execute");
    expect(candidateHandoffRequests[0]?.idempotencyKey).toBe(
      "mcp-builder-candidate-handoff.mcp-builder-ui-001",
    );
    const candidateHandoffBody = JSON.parse(
      candidateHandoffRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(candidateHandoffBody.project_digest).toBe(project.data.canonical_digest);
    expect(candidateHandoffBody.artifact_digest).toBe(generation.data.artifact_digest);
    expect(candidateHandoffBody.security_review_digest).toBe(
      securityReview.data.canonical_digest,
    );
    expect(candidateHandoffBody.lab_validation_digest).toBe(
      labValidation.data.canonical_digest,
    );
    expect(candidateHandoffBody.handoff_profile).toBe(
      "atlas.candidate-handoff.python312.v1",
    );
    expect(candidateHandoffBody.acknowledged_unsigned_quarantined_package).toBe(true);
    expect(candidateHandoffBody).not.toHaveProperty("sign");
    expect(candidateHandoffBody).not.toHaveProperty("install");
    expect(candidateHandoffBody).not.toHaveProperty("execute");
    expect(packageAcquisitionRequests[0]?.idempotencyKey).toBe(
      "connector-package-acquisition.mcp-builder-ui-001",
    );
    const packageAcquisitionBody = JSON.parse(
      packageAcquisitionRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(packageAcquisitionBody.source_handoff_id).toBe(candidateHandoff.data.handoff_id);
    expect(packageAcquisitionBody.source_handoff_digest).toBe(
      candidateHandoff.data.canonical_digest,
    );
    expect(packageAcquisitionBody.package_digest).toBe(candidateHandoff.data.package_digest);
    expect(packageAcquisitionBody.acknowledged_unsigned_unattested_quarantine).toBe(true);
    expect(packageAcquisitionBody).not.toHaveProperty("sign");
    expect(packageAcquisitionBody).not.toHaveProperty("validate");
    expect(packageAcquisitionBody).not.toHaveProperty("register");
    expect(packageAcquisitionBody).not.toHaveProperty("install");
    expect(packageAcquisitionBody).not.toHaveProperty("execute");
    expect(packageValidationRequests[0]?.idempotencyKey).toBe(
      "connector-package-validation.mcp-builder-ui-001",
    );
    const packageValidationBody = JSON.parse(
      packageValidationRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(packageValidationBody.source_acquisition_id).toBe(
      packageAcquisition.data.acquisition_id,
    );
    expect(packageValidationBody.source_acquisition_digest).toBe(
      packageAcquisition.data.canonical_digest,
    );
    expect(packageValidationBody.package_digest).toBe(packageAcquisition.data.package_digest);
    expect(packageValidationBody.acknowledged_untrusted_quarantined_package).toBe(true);
    expect(packageValidationBody).not.toHaveProperty("register");
    expect(packageValidationBody).not.toHaveProperty("install");
    expect(packageValidationBody).not.toHaveProperty("execute");
    expect(packageInventoryRequests[0]?.idempotencyKey).toBe(
      "connector-package-inventory.mcp-builder-ui-001",
    );
    const packageInventoryBody = JSON.parse(
      packageInventoryRequests[0]?.body ?? "{}",
    ) as Record<string, unknown>;
    expect(packageInventoryBody.source_validation_id).toBe(
      packageValidation.data.validation_id,
    );
    expect(packageInventoryBody.source_validation_digest).toBe(
      packageValidation.data.canonical_digest,
    );
    expect(packageInventoryBody.package_digest).toBe(packageValidation.data.package_digest);
    expect(packageInventoryBody.acknowledged_untrusted_package_content).toBe(true);
    expect(packageInventoryBody).not.toHaveProperty("install");
    expect(packageInventoryBody).not.toHaveProperty("execute");
    expect(packageInventoryBody).not.toHaveProperty("trust");
  }, 15_000);

  it("verifies the downloaded candidate archive against immutable evidence", async () => {
    const digestBytes = Uint8Array.from(
      candidateArchiveDigest.match(/.{2}/g)?.map((value) => Number.parseInt(value, 16)) ?? [],
    );
    const subtleDigest = vi.fn().mockResolvedValue(digestBytes.buffer);
    vi.stubGlobal("crypto", { subtle: { digest: subtleDigest } });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(candidateArchiveBytes, {
        status: 200,
        headers: {
          "Content-Type": "application/zip",
          "X-Atlas-Package-Digest": candidateArchiveDigest,
        },
      }),
    );

    const result = await downloadMcpBuilderCandidateArchive(
      candidateHandoff.data as unknown as McpBuilderCandidateHandoff,
    );

    expect(result.digest).toBe(candidateArchiveDigest);
    expect(result.filename).toBe(candidateHandoff.data.package_filename);
    expect(result.blob.size).toBe(candidateArchiveBytes.byteLength);
    expect(subtleDigest).toHaveBeenCalledWith("SHA-256", expect.any(ArrayBuffer));
  });
});
