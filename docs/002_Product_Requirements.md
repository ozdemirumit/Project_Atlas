# Project Atlas

## Product Requirements Document

| Field | Value |
| --- | --- |
| Document ID | ATLAS-002 |
| Version | 1.0.0 |
| Status | Approved |
| Document Owner | Product Owner |
| Reviewers | Architecture Owner, Security Architecture, Infrastructure Domain Architects, Operations, AI Architecture, Quality Engineering, IT Service Management Owner |
| Approver | Umit Ozdemir (Product Owner) |
| Approval Date | 2026-08-03 |
| Last Updated | 2026-08-03 |
| Related Documents | [ATLAS-001](001_Product_Vision.md), [ATLAS-003](003_Project_Principles.md), [ATLAS-004](004_Glossary.md), [ATLAS-010](010_System_Architecture.md), [ATLAS-020](020_MCP_Framework.md), [ATLAS-026](026_Graph_Engine.md), [ATLAS-027](027_Knowledge_Engine.md), [ATLAS-030](030_Authentication.md), [ATLAS-032](032_Audit.md), [ATLAS-037](037_Approval_Workflow.md), [ATLAS-040](040_AI_Agents.md), [ATLAS-047](047_Guardrails.md), [ATLAS-056](056_Testing.md) |
| Supersedes | ATLAS-002 version 0.1.0 |

## 1. Purpose

This Product Requirements Document defines what Project Atlas must deliver, for whom, within which safety and enterprise boundaries, and how product readiness is evaluated.

Architecture documents define how these requirements are satisfied. A requirement in this Draft PRD is not implementation authorization until the document and relevant downstream contracts are approved.

## 2. Product Summary

Atlas is an enterprise AI infrastructure operations decision-support platform. It connects to infrastructure through modular MCP connectors, builds time-aware inventory and dependency context, retrieves governed vendor and organizational knowledge, and helps users investigate health, root cause, change impact, and remediation options.

The initial product posture is decision support. AI does not independently execute infrastructure-changing actions. Eligible live access passes through deterministic identity, RBAC, policy, approval, audit, guardrail, workflow, and connector controls.

## 3. Objectives

- Reduce time required to gather and correlate operational evidence
- Improve the quality and explainability of infrastructure investigation
- Identify affected infrastructure and business services before change
- Produce safer recommendations with explicit uncertainty and recovery
- Preserve reusable vendor and organizational knowledge
- Provide enterprise identity, audit, integration, deployment, and support foundations
- Prove one bounded end-to-end vertical slice before expanding vendor coverage

## 4. Requirement Language and Priority

- `Must`: required for the stated scope or release gate
- `Should`: expected unless a documented product decision defers it
- `Could`: valuable future capability outside the committed MVP
- `Will not`: explicitly excluded from the defined scope

The terms `must`, `must not`, and `required` are normative.

## 5. Target Users and Jobs

| User | Primary jobs |
| --- | --- |
| Infrastructure Engineer | Query systems, inspect evidence, troubleshoot, and prepare safe plans |
| Infrastructure Architect | Analyze topology, resilience, capacity, and change impact |
| Operations or NOC Analyst | Triage findings, schedule checks, coordinate incidents, and report status |
| Domain Specialist | Validate connector behavior, RCA, runbooks, and recommendations |
| Service Owner or Approver | Review service impact, interruption, risk, readiness, and recovery |
| Security or Auditor | Review identity, authority, data access, policy, approval, and audit evidence |
| IT Manager | Review risk, service, capacity, reliability, and operational trends |
| Platform Administrator | Configure identity, connectors, integrations, models, policies, and platform health |

## 6. Core User Journeys

### UJ-001: Investigate Infrastructure Health

A user selects scope, asks about a target or service, reviews current observations and citations, sees uncertainty, and opens a durable investigation.

### UJ-002: Analyze an Incident

A user correlates alerts, changes, topology, knowledge, and historical outcomes; Atlas ranks hypotheses and recommends bounded diagnostic checks.

### UJ-003: Assess a Proposed Change

A user provides a target and plan; Atlas shows affected infrastructure and services, scenarios, interruption, duration, prerequisites, and recovery.

### UJ-004: Review a Recommendation

A user compares options, including defer or no action, and inspects evidence, applicability, tradeoffs, policy, and approval requirements.

### UJ-005: Govern Knowledge and Connectors

Authorized administrators register, validate, review, activate, upgrade, suspend, and audit modular sources and connector packages.

### UJ-006: Produce a Report or ITSM Handoff

A user creates a technical or management report and links labeled Atlas evidence to an incident or change record.

## 7. Functional Requirements

### FR-001: Chat-Centered Operations Workspace - Must

Atlas must provide an authenticated web workspace where users can ask infrastructure questions, track durable work, and move between chat, evidence, inventory, topology, investigation, recommendation, approval, and reports without losing context.

Verification: UI, API, accessibility, streaming, state, and end-to-end tests under ATLAS-050, ATLAS-052, and ATLAS-056.

### FR-002: Modular MCP Connector Framework - Must

Atlas must install, configure, validate, enable, disable, upgrade, roll back, and remove independently versioned MCP packages with declared publisher, compatibility, targets, capabilities, schemas, permissions, network access, and C0-C5 classification.

Unknown capabilities must be denied. New connectors must be read-only by default.

Verification: manifest, SDK, simulator, isolation, security, and lifecycle tests under ATLAS-020 and ATLAS-021.

### FR-003: Governed MCP Builder - Should for MVP design; Could for production generation

Atlas should draft connector artifacts from approved API, CLI, schema, and documentation inputs. Generated artifacts must remain quarantined until schema, static, dependency, simulator, lab, security, domain, signing, and human approval gates pass.

Verification: generated-artifact lifecycle and adversarial suites under ATLAS-022 and ATLAS-047.

### FR-004: Infrastructure Inventory - Must

Atlas must normalize discovered and registered entities across selected infrastructure domains while preserving source identifiers, vendor evidence, product version, environment, site, ownership, observation time, conflict, and freshness.

Verification: domain schema, source mapping, stale state, conflict, and access tests.

### FR-005: Infrastructure and Service Graph - Must

Atlas must maintain time-aware typed relationships among infrastructure components and technical or business services. Graph queries must expose source, direction, time, confidence, and missing context and must be bounded and authorization-filtered.

Verification: entity, edge, temporal, traversal, isolation, and rebuild tests under ATLAS-026.

### FR-006: Knowledge and RAG - Must

Atlas must ingest, classify, version, retrieve, cite, suspend, supersede, expire, and delete vendor and organizational knowledge with source authority, product applicability, ownership, ACL, and lineage.

Verification: ingestion, retrieval, citation, access, prompt-injection, lifecycle, and deletion tests under ATLAS-015, ATLAS-027, and ATLAS-054.

### FR-007: Health Checks - Must

Atlas must define versioned connector-based health checks that are scoped, schedulable, enableable, bounded, auditable, and reportable. Results must retain target, capability, observation time, thresholds, evidence, and freshness.

Verification: workflow, schedule, connector, timeout, partial, and reporting tests.

### FR-008: Investigation and Reasoning - Must

Atlas must distinguish observations, retrieved facts, calculations, correlations, inferences, hypotheses, assumptions, unknowns, and recommendations. Material claims must link to authorized evidence and current scope.

Verification: structured-output, citation, epistemic-type, temporal, conflict, and insufficiency evaluation under ATLAS-041.

### FR-009: Root Cause Analysis - Must for selected MVP domain

Atlas must create a versioned RCA case with incident scope, timeline, affected and unaffected entities, hypothesis ledger, supporting and contradicting evidence, safe diagnostic plan, confidence or confirmation state, and human correction.

Correlation, recent change, or historical similarity must not be labeled root cause alone.

Verification: domain case set, false-positive, top-k, diagnostic, and human-review evaluation under ATLAS-042.

### FR-010: Recommendation Engine - Must

Atlas must present versioned options with evidence, applicability, confidence, assumptions, unknowns, risk, impact, interruption, duration, prerequisites, validation, stop conditions, rollback or recovery, alternatives, and required controls.

The engine must support no-action, defer, and escalation outcomes and may state that no option is supportable.

Verification: option completeness, ranking, policy, unsafe option, and human-review evaluation under ATLAS-043.

### FR-011: Change Impact Analysis - Must

Atlas must assess direct and transitive infrastructure and service impact, redundancy, capacity, performance, data protection, security, interruption mode, duration phases, expected and failure scenarios, and graph or evidence gaps.

MVP must describe this as dependency and scenario analysis, not a validated digital twin.

Verification: affected/unaffected precision, service mapping, scenario, duration, and false-safe evaluation under ATLAS-044.

### FR-012: Runbook Engine - Should

Atlas should ingest and author governed runbooks with owner, product/version applicability, preconditions, roles, steps, branches, checkpoints, risk, impact, duration, approval, stop, rollback, recovery, test, review, and expiry.

AI may draft structure but cannot approve or execute ambiguous procedures.

Verification: source fidelity, applicability, safety, dry-run, and human-handoff tests under ATLAS-045.

### FR-013: Human Approval - Must as governance foundation

Atlas must support eligible authenticated human approval bound to one immutable action, target set, parameter set, plan, impact, policy, connector version, ITSM record, and time window.

Approval must not grant missing permission or override policy and guardrails. Chat acknowledgement is not approval.

Verification: substitution, replay, separation, quorum, expiry, revocation, and revalidation tests under ATLAS-037.

### FR-014: Workflow Engine - Must

Atlas must manage durable versioned workflows, timers, schedules, retries, human tasks, approvals, cancellation, partial results, unknown outcomes, and compensation without relying on an LLM for state authority.

Verification: state-machine, failure, concurrency, restart, upgrade, and audit tests under ATLAS-023.

### FR-015: Policy and Decision Controls - Must

Atlas must evaluate deterministic policy for permission, capability class, target, environment, evidence, risk, approval, exception, and non-overridable platform minimums. Decisions must be versioned, explainable, and auditable.

Verification: rule, precedence, conflict, simulation, fail-closed, and policy-bypass tests under ATLAS-024 and ATLAS-025.

### FR-016: Enterprise Authentication and RBAC - Must

Atlas must provide secure local bootstrap and recovery, one enterprise directory or federation path, stable subject identities, sessions, service identities, group mapping, least-privileged roles, resource scopes, separation of duties, revocation, and access review.

Verification: identity-provider, session, scope, group, revocation, break-glass, service identity, and direct-API tests under ATLAS-030 and ATLAS-031.

### FR-017: Audit, Logging, Syslog, and SIEM - Must

Atlas must maintain an append-only tamper-evident audit trail and structured operational logs with end-to-end correlation. It must export selected security and audit events over secure Syslog and through a normalized SIEM integration with delivery health.

Verification: event coverage, integrity, redaction, outage, retention, export, TLS, mapping, and detection tests under ATLAS-032 through ATLAS-035.

### FR-018: ITSM Integration - Should for MVP vertical slice

Atlas should read current incident or change context and create or append labeled analysis, recommendation, impact, and evidence references through a versioned adapter. ITSM remains authoritative for ticket state.

Verification: field mapping, idempotency, conflict, approval mapping, permission, and outage tests under ATLAS-036.

### FR-019: Reports - Must

Atlas must generate versioned technical and management reports from governed source artifacts, showing scope, freshness, confidence, redaction, reviewer status, and partial or failed sections.

Initial report types include health, incident analysis, change impact, capacity, risk, audit, and connector status.

Verification: source-version, access, rendering, export, and scheduled-delivery tests.

### FR-020: Platform and Extension Administration - Must

Authorized users must administer identity, connectors, knowledge, models, policies, workflows, integrations, certificates, deployment health, backup, and support through consistent draft, validate, preview, activate, observe, roll back, suspend, and retire lifecycles.

Verification: authorization, lifecycle, secret, concurrency, rollback, and audit tests.

## 8. AI and Safety Requirements

### AIR-001: Human Control - Must

AI must not independently authorize or execute infrastructure-changing activity.

### AIR-002: Governed Tools - Must

The LLM must not receive unrestricted credentials, arbitrary shell, dynamic code execution, or unrestricted network tools. Live access uses governed typed capabilities.

### AIR-003: Evidence and Explanation - Must

Material output must provide concise verifiable rationale and authorized citations without exposing private chain-of-thought.

### AIR-004: Uncertainty - Must

Confidence must include supporting and limiting factors. Missing, stale, conflicting, or inaccessible evidence must remain visible.

### AIR-005: Guardrails - Must

ATLAS-047 GRD-001 through GRD-016 must be enforced and cannot be disabled through customer settings.

### AIR-006: Generated Artifacts - Must

Generated connectors, code, runbooks, workflows, policies, and mappings must be quarantined until reviewed, tested, signed, and approved.

### AIR-007: Local and Private Models - Must

Atlas must support an OpenAI-compatible model endpoint within the configured enterprise data boundary and must not silently fall back to a less trusted endpoint.

### AIR-008: Evaluation - Must

Model, prompt, agent, retrieval, tool, and guardrail changes must pass versioned quality and safety evaluations before promotion.

## 9. Non-Functional Requirements

### NFR-001: Security

Atlas must use secure defaults, least privilege, explicit trust, protected secrets, input validation, extension isolation, supply-chain verification, and threat-model-driven testing.

### NFR-002: Data Isolation and Privacy

Atlas must enforce organization, environment, purpose, and classification boundaries across APIs, queries, graphs, vectors, caches, logs, reports, errors, and model context.

### NFR-003: Availability and Safe Degradation

Critical control failure must fail safely. Optional model, vector, connector, or integration outage must produce explicit scoped degradation rather than uncontrolled behavior.

### NFR-004: Scalability

Atlas must scale across sites, infrastructure domains, connectors, knowledge, workflows, and concurrent investigations using measured capacity and bounded work.

### NFR-005: Performance

Interactive views and common read queries must meet product-defined latency objectives. Long analysis, ingestion, report, and export work must be asynchronous and trackable.

### NFR-006: Observability

Atlas must expose structured logs, metrics, traces, health, queue, model, connector, retrieval, workflow, audit, and integration state without leaking secrets.

### NFR-007: Reliability and Recovery

Retries, idempotency, cancellation, partial state, unknown outcomes, backup, restore, upgrade, rollback, and failover must be explicit and tested.

### NFR-008: Auditability

Accountable activity must be reconstructable from user request through evidence, AI artifact, policy, approval, connector, result, and external record.

### NFR-009: Explainability and Accessibility

Technical, operational, approver, management, and audit users must receive consistent underlying facts at appropriate detail. Core workflows target WCAG 2.2 AA.

### NFR-010: Compatibility and Versioning

APIs, events, schemas, connectors, workflows, policies, prompts, models, runbooks, migrations, and documents must be versioned with compatibility and deprecation rules.

### NFR-011: Restricted-Network Operation

Build, install, update, model, dependency, documentation, and support paths must work through signed internal mirrors or offline bundles without hidden public access.

### NFR-012: Maintainability

Implementation must use clear module ownership, typed contracts, focused changes, automated checks, and governed documentation and ADRs.

### NFR-013: Testability

Atlas must support synthetic data, simulators, isolated services, reproducible AI evaluations, vendor labs, and end-to-end deployment and recovery tests.

### NFR-014: Supportability

Releases must include compatibility, known issues, health, diagnostics, support bundles, upgrade, rollback, backup, restore, and operational handoff.

### NFR-015: Enterprise Deployment

Atlas must define developer, lab, enterprise test, production-ready target, mirrored, and offline profiles with secrets, certificates, network, HA, and recovery expectations.

## 10. MVP Vertical Slice

The MVP must prove one end-to-end scenario in one selected infrastructure domain.

### MVP-001: Foundation

- Authenticated web workspace and scoped RBAC
- Backend API, durable operations, audit, logs, and platform health
- Local or private OpenAI-compatible model
- Reproducible developer and lab deployment

### MVP-002: Data and Integration

- Connector registry and simulator
- One real read-only connector
- Inventory, observations, and bounded graph relationships
- One governed vendor or internal knowledge source and local embeddings
- One scheduled health check

### MVP-003: Decision Support

- Investigation and timeline
- RCA hypotheses in selected fault families
- Change-impact analysis at D0-D1 maturity
- Recommendation options with evidence and recovery
- Technical report and optional ITSM handoff

### MVP-004: Governance

- Policy and approval data models
- Exact human approval flow demonstrated without AI execution
- Syslog or SIEM security-event export
- Guardrail, prompt-injection, DLP, isolation, and AI evaluation suite

### MVP-005: Operations

- Clean install, mirrored or offline lab install
- Upgrade and rollback foundation
- Database and artifact backup plus restore test
- Signed release artifacts, SBOM, provenance, and validation evidence

## 11. Out of Scope for MVP

- Autonomous remediation or direct AI C3-C5 execution
- Destructive infrastructure operation
- Broad multi-vendor marketplace
- Production-grade automatic MCP Builder publication
- Validated cross-domain digital twin
- Universal root-cause analysis
- Complete CMDB, monitoring, SIEM, or ITSM replacement
- Public multi-tenant SaaS
- Every operating system, orchestrator, model, or vector store
- LTS support commitment before operational maturity

## 12. Product Metrics

- Time to first useful scoped assessment
- Evidence-gathering time and source coverage
- RCA top-k usefulness and false-positive rate
- Citation correctness and unsupported-claim rate
- Impact affected-scope precision and false-safe rate
- Recommendation reviewer acceptance and correction type
- Estimated versus actual duration and interruption
- Audit completeness and control-bypass defects
- Knowledge freshness and owner review performance
- Connector and workflow reliability
- User challenge, trust, and task-completion signals
- Deployment, upgrade, rollback, backup, and restore success

Targets require baseline measurement and cannot be invented in this Draft.

## 13. Product Risks and Mitigations

| Risk | Primary mitigation |
| --- | --- |
| Hallucinated or inapplicable guidance | Evidence contracts, citations, version filters, evaluations, human review |
| Unsafe operational action | C0-C5 classes, no direct AI C3-C5, deterministic policy and approval |
| Over-permissioned credentials | Secret references, scoped connector identities, read-only default |
| Incomplete topology | Freshness and graph-gap disclosure, conservative impact behavior |
| Prompt injection or data exfiltration | Layered ATLAS-047 controls, tool isolation, DLP, adversarial tests |
| Stale knowledge | Ownership, review, expiry, suspension, and applicability |
| Generated artifact risk | Quarantine, analysis, simulator, lab, signing, approval |
| Incorrect success state | Explicit partial and unknown outcomes, reconciliation |
| Deployment complexity | Modular-monolith start, profiles, preflight, offline bundle, tested recovery |
| User over-reliance | Explainability, alternatives, uncertainty, non-coercive approval |

## 14. Dependencies and Traceability

- ATLAS-001 defines vision and product boundaries.
- ATLAS-003 provides stable principles and C0-C5 capability classes.
- ATLAS-010 through ATLAS-016 allocate system responsibilities.
- ATLAS-020 through ATLAS-027 define core platform capabilities.
- ATLAS-030 through ATLAS-038 define enterprise controls and integrations.
- ATLAS-040 through ATLAS-047 define AI behavior and guardrails.
- ATLAS-050 through ATLAS-059 define implementation, testing, deployment, and release contracts.
- Each implementation epic and acceptance test must reference applicable requirement IDs.

## 15. Assumptions

- The first domain has a supported read interface, documentation, lab target, and domain reviewer.
- Enterprise identity, certificates, secrets, storage, and a private model endpoint are available.
- The initial product is deployed inside customer-controlled boundaries.
- Product and architecture documents are formally reviewed before implementation begins.
- Some requirements will receive measurable targets through later ADRs or service-level objectives.

## 16. Open Questions and Product Decisions

- Which domain, vendor, connector, fault family, and user journey form the MVP slice?
- Which directory, ITSM, and SIEM products are first validated?
- Which local language and embedding models and hardware profile are first supported?
- Which exact MVP reports and export formats are required?
- Which latency, scale, availability, recovery, and retention targets apply?
- Which C2 diagnostics, if any, are included after policy and safety review?
- What review evidence moves this PRD from Draft to Review?

## 17. Product Acceptance Gates

The MVP is ready for product acceptance only when:

- The selected vertical slice works end to end with synthetic and approved lab data.
- Identity, RBAC, organization isolation, policy, approval, audit, and guardrail suites pass.
- AI output meets agreed grounding, citation, uncertainty, domain, and safety thresholds.
- The real connector remains read-only and passes simulator, lab, timeout, partial, and permission tests.
- RCA, impact, and recommendation outputs include evidence, alternatives, unknowns, service effect, duration, and recovery.
- No C3-C5 capability is directly available to AI.
- Clean install, restricted-network path, upgrade, rollback or recovery, backup, and restore are demonstrated.
- Documentation, compatibility, security, support, and release evidence are complete.
- Accountable product, architecture, security, quality, domain, AI, and operations reviewers approve the exact candidate.

## 18. Document Acceptance Criteria

This document is ready to enter Review when:

- Target users, journeys, functional, AI, non-functional, MVP, and out-of-scope requirements are agreed.
- Requirements have stable IDs and map to downstream documents and verification.
- Human control and direct AI execution boundaries are unambiguous.
- Enterprise identity, audit, integration, deployment, recovery, and restricted-network requirements are present.
- MVP is one bounded vertical slice with measurable product and safety gates.
- Product, architecture, security, domain, AI, operations, quality, and ITSM reviewers accept the requirement baseline.

## 19. Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | 2026-07-21 | Project Atlas Team | Initial product summary, capabilities, non-functional requirements, MVP, risks, and guardrails |
| 0.2.0 | 2026-08-03 | Product Owner | Added stable user journeys and requirements, verification traceability, AI and non-functional contracts, bounded MVP vertical slice, product metrics, risks, and release acceptance gates |
| 1.0.0 | 2026-08-03 | Umit Ozdemir | Approved as the first binding documentation baseline under the designated approver authority |
