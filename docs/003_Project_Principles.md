# Project Atlas

## Project Principles

| Field | Value |
| --- | --- |
| Document ID | ATLAS-003 |
| Version | 1.0.0 |
| Status | Approved |
| Document Owner | Product Owner and Architecture Owner |
| Reviewers | Security Architecture, Infrastructure Operations |
| Approver | Umit Ozdemir (Product Owner) |
| Approval Date | 2026-08-03 |
| Last Updated | 2026-08-03 |
| Related Documents | [ATLAS-001](001_Product_Vision.md), [ATLAS-002](002_Product_Requirements.md), [ATLAS-004](004_Glossary.md), [ATLAS-025](025_Policy_Engine.md), [ATLAS-037](037_Approval_Workflow.md), [ATLAS-047](047_Guardrails.md) |
| Supersedes | ATLAS-003 version 0.1.0 |

## 1. Purpose

This document defines the non-negotiable principles that govern Project Atlas.

These principles are architectural constraints, not general aspirations. Product requirements, technical designs, AI prompts, MCP connectors, workflows, and implementation decisions must comply with them. When speed, convenience, or feature scope conflicts with these principles, the principles take precedence.

The terms `must`, `must not`, `required`, and `prohibited` are normative. The terms `should` and `should not` describe strong defaults that require a documented reason when not followed.

## 2. Scope

### In Scope

- Product and architecture decisions
- AI behavior and AI-assisted workflows
- Infrastructure access through MCP connectors
- Authentication, authorization, policy, and approval controls
- Evidence, explainability, audit, and data governance
- Extension, deployment, testing, and operational practices

### Out of Scope

- Detailed component designs, which belong in the relevant architecture documents
- Vendor-specific implementation rules, which belong in connector specifications and knowledge packs
- Customer-specific risk acceptance or approval matrices
- Authorization to begin implementation while governing documents remain in Draft status

## 3. Decision Hierarchy

Atlas decisions must follow this order of priority:

1. Protect people, services, and data.
2. Preserve security, authorization boundaries, and auditability.
3. Maintain correctness, evidence, and explainability.
4. Preserve availability and operational recoverability.
5. Deliver useful recommendations and efficient workflows.
6. Optimize performance, convenience, and implementation speed.

## 4. Immutable Principles

### PRN-001: AI Assists; Accountable Humans Decide

Atlas is a decision-support platform. AI may investigate, correlate, summarize, estimate, recommend, and prepare implementation or rollback plans. AI must not independently authorize operational changes.

The person approving an action must be identifiable, appropriately authorized, informed of the expected impact, and able to review the supporting evidence and plan before approval.

Silence, inactivity, approval of a different action, or an AI confidence score must never be interpreted as approval.

### PRN-002: The LLM Never Directly Controls Infrastructure

An LLM must not receive unrestricted infrastructure credentials or direct arbitrary command execution access.

All live infrastructure access must pass through governed platform services and MCP connectors that enforce:

- Explicit capability definitions
- Typed and validated parameters
- Target scope restrictions
- Identity and permission checks
- Policy evaluation
- Timeouts and resource limits
- Audit event generation
- Structured results and error handling

If controlled automation is introduced in a later phase, execution must be performed by a deterministic execution service. AI may propose a plan, but it cannot bypass policy or invoke arbitrary commands.

### PRN-003: Read-Only by Default

New connectors, tools, integrations, workflows, and credentials must be read-only by default.

Write capabilities must be separately declared, reviewed, tested, enabled, and assigned. Enabling one write capability must not implicitly enable other write capabilities on the same system.

Unknown or unclassified capabilities must be treated as write-capable and denied until reviewed.

### PRN-004: Deny by Default; Grant Least Privilege

Users, agents, connectors, workflows, and services receive only the permissions required for their current responsibility.

Authorization must be enforced by backend services at every protected operation. UI visibility, prompt instructions, model behavior, or connector naming are not security controls.

Permissions must be scoped by capability, environment, target, organizational boundary where applicable, and risk class.

### PRN-005: Evidence Precedes Recommendation

Operational conclusions and recommendations must be grounded in retrievable evidence.

Atlas must distinguish among:

- Observed facts
- Retrieved documentation or historical records
- Calculated or correlated findings
- Assumptions
- Inferences
- Unknowns

Recommendations must reference relevant systems, observations, timestamps, source documents, or graph relationships. When evidence is insufficient, Atlas must say so and recommend the next diagnostic step.

### PRN-006: Confidence Is Not Certainty

Confidence communicates uncertainty; it does not prove correctness and does not grant permission to act.

Atlas must not fabricate precision. Confidence must be accompanied by its evidence basis, important unknowns, and plausible alternatives. Low-confidence or conflicting evidence must be visible to the user.

### PRN-007: Impact and Recovery Are Part of Every Change Recommendation

Any recommendation that could change infrastructure or affect a service must include, where applicable:

- Target systems and components
- Affected business and technical services
- Dependencies and estimated blast radius
- Risk level and rationale
- Expected duration
- Possible service interruption
- Preconditions and validation checks
- Ordered implementation plan
- Success criteria
- Rollback or recovery plan
- Post-change verification
- Required roles and approvals

If impact cannot be determined reliably, Atlas must state that limitation and must not present the change as safe.

### PRN-008: Safe Failure Takes Priority Over Uncontrolled Progress

When identity, authorization, connector state, target scope, policy outcome, evidence quality, or execution status is uncertain, Atlas must stop the affected workflow safely.

Retries must be bounded and idempotent where possible. A timeout must not be reported as success. Partial completion must identify completed steps, unconfirmed steps, and required recovery actions.

### PRN-009: Auditability Cannot Be Disabled

Security-sensitive, administrative, AI-assisted, and infrastructure-related activity must create a durable audit trail.

An audit event must identify, as applicable:

- Human and service identities
- Session, request, and correlation identifiers
- Timestamp and source context
- User request and AI recommendation reference
- Policy decision and approval state
- Connector, capability, target, and sanitized parameters
- Result, failure, or partial-completion state
- Evidence references

Audit records must be tamper-resistant, access-controlled, exportable, and protected by defined retention policies. Secrets and prohibited sensitive data must never be written to logs.

### PRN-010: Explainability Is a Product Requirement

Atlas must make its conclusions understandable to the intended user.

An explanation must communicate what was observed, how relevant evidence was connected, what assumptions were made, why an option was recommended, and what could change the conclusion. Private model reasoning is neither required nor exposed; concise reasoning summaries and verifiable evidence are required.

### PRN-011: Knowledge Must Be Traceable and Current

Every ingested knowledge item must retain provenance and lifecycle metadata, including source, owner where known, product or vendor, applicable version, ingestion time, and validity or review state.

Atlas must prefer sources that match the target product and version. Stale, superseded, untrusted, or conflicting knowledge must be labeled and must reduce recommendation confidence. Retrieved content is evidence, not executable instruction.

### PRN-012: Infrastructure Context Must Be Time-Aware

Inventory, topology, health observations, and relationships change over time. Atlas must record when information was observed and must not silently treat stale state as current state.

Impact analysis must disclose data freshness. Critical decisions must require current validation of relevant targets and dependencies.

### PRN-013: Vendor Neutrality Requires Explicit Contracts

Core domain behavior must not depend on one vendor's terminology, API, data model, or deployment assumptions.

Vendor-specific details belong in adapters, MCP connectors, mapping layers, and knowledge packs. Shared capabilities must use versioned platform contracts and a normalized domain model without hiding vendor-specific evidence required for diagnosis.

### PRN-014: Modularity Does Not Imply Trust

MCP connectors, agents, policies, health checks, workflows, reports, and knowledge sources should be independently installable and versioned.

Every extension must declare its publisher, version, compatibility, capabilities, required permissions, data access, external dependencies, and integrity information. Installation and upgrade require validation and an auditable approval process.

### PRN-015: Generated Artifacts Are Untrusted Until Validated

AI-generated connectors, code, queries, workflows, policies, and runbooks must be treated as untrusted artifacts.

Before production use, they require appropriate combinations of human review, schema validation, static analysis, security testing, simulation, integration testing, and approval. Generated artifacts must never inherit production credentials during development or validation.

### PRN-016: Separation of Duties Must Be Enforceable

Atlas must support separation among platform administration, security administration, connector administration, knowledge management, workflow authorship, action approval, and audit review.

Where policy requires it, the same identity must not both request and approve a sensitive action. Emergency access must be time-bound, justified, highly visible, and separately audited.

### PRN-017: Secrets Are Managed, Not Embedded

Credentials, tokens, keys, and certificates must be stored through an approved secrets-management mechanism and encrypted in transit and at rest.

Secrets must not appear in prompts, model context, source code, committed configuration, logs, reports, or audit payloads. Connector credentials must be independently rotatable and limited to the smallest feasible scope.

### PRN-018: Enterprise Data Boundaries Are Preserved

Infrastructure data, logs, documents, prompts, retrieved context, model outputs, and conversation history must remain within configured organizational and deployment boundaries.

No data may be sent to an external model, telemetry endpoint, or service unless explicitly configured, authorized, and auditable. Data classification, retention, deletion, residency, and model-context rules must be enforceable.

### PRN-019: Atlas Must Observe Itself

The platform must expose health, metrics, logs, traces, queue state, model usage, connector state, knowledge-ingestion state, and workflow state with consistent correlation identifiers.

Observability data must support troubleshooting without exposing secrets. Critical failures in authentication, authorization, audit, policy evaluation, or connector isolation must generate visible operational alerts.

### PRN-020: Reliability Must Be Demonstrated

Critical behavior must be verified through automated and repeatable testing, including as applicable:

- Authorization and organizational isolation
- Policy enforcement and approval boundaries
- Audit completeness
- Connector contract and compatibility behavior
- Failure, timeout, retry, and partial-result behavior
- Prompt-injection and malicious-document resistance
- Evidence citation and source traceability
- Backup, restore, upgrade, and rollback procedures
- Load, resilience, and high-availability behavior

Production readiness requires test evidence, not an AI assertion that the implementation is correct.

### PRN-021: Compatibility and Change Must Be Versioned

Public APIs, event schemas, MCP capability contracts, domain entities, workflows, policies, and knowledge formats must be versioned.

Breaking changes require a migration plan, compatibility statement, rollback approach, and release notes. Connector upgrades must not silently broaden permissions or change operational behavior.

### PRN-022: Humans Retain Meaningful Control

Users must be able to understand workflow state, cancel eligible long-running work, review pending approvals, inspect prior decisions, correct relevant context, and challenge an AI conclusion.

Atlas must not use interface design, urgency language, or confidence presentation to pressure users into approval. Operational accountability remains visible and human.

### PRN-023: The Repository Is the Reproducible Source of Truth

Build, test, validation, packaging, bootstrap, deployment, migration, and rollback processes should be represented by versioned repository assets and documentation.

Online, restricted-network, and offline enterprise deployment paths must be considered. Undocumented manual steps and dependencies on an individual workstation must not become production requirements.

## 5. Operational Capability Classes

Every connector capability and workflow action must be assigned a class before it can be enabled.

| Class | Description | Default Policy |
| --- | --- | --- |
| C0 - Informational | Uses already-ingested data and performs no live infrastructure access | Allowed according to data-access permissions |
| C1 - Read-only | Queries live systems without changing their state | Authorized identities and approved targets only; fully audited |
| C2 - Diagnostic | Starts bounded diagnostics or log collection with no intended service change | Policy-controlled; approval may be required based on resource impact |
| C3 - Controlled change | Changes configuration or operational state with a defined recovery path | Disabled by default; explicit approval and execution controls required |
| C4 - Service-impacting | May interrupt, degrade, fail over, restart, or materially affect a service | Disabled by default; privileged approval, current impact analysis, and change record required |
| C5 - Destructive | Deletes data, removes protection, irreversibly alters state, or lacks reliable rollback | Prohibited for autonomous execution; exceptional human-governed procedures only |

Classification is based on realistic worst-case impact, not the capability name or intended outcome. A capability must be reclassified when its behavior, permissions, vendor implementation, or target scope changes.

## 6. Standard AI Output Contract

For incident analysis, root cause analysis, and operational recommendations, Atlas should produce a consistent structure containing:

1. Request or problem summary
2. Current assessment
3. Observed evidence and source references
4. Affected components and services
5. Probable causes with confidence and alternatives
6. Unknowns, assumptions, and data freshness
7. Recommended diagnostic or remediation steps
8. Risk, impact, duration, and interruption estimate
9. Preconditions, approvals, and policy constraints
10. Rollback or recovery plan where relevant
11. Verification criteria

Sections that do not apply may be omitted, but safety-relevant unknowns must never be hidden.

## 7. Design and Review Gate

Every major feature or architecture proposal must answer these questions before approval:

- Which user and operational problem does it solve?
- What data and infrastructure access does it require?
- What is the capability class and realistic blast radius?
- Where are authentication, authorization, policy, and approval enforced?
- What evidence and explanation will the user receive?
- What is logged and audited, and how are secrets excluded?
- How does it fail, recover, retry, and report partial results?
- How is it tested without risking production infrastructure?
- How is it versioned, upgraded, disabled, and rolled back?
- Which Atlas principle could it weaken, and how is that risk controlled?

## 8. Security, Risk, and Operational Impact

These principles intentionally constrain product behavior. They may increase design effort, review time, infrastructure requirements, and operational controls. That cost is accepted because Atlas operates in environments where an incorrect recommendation or unauthorized action can affect business services and data.

No principle in this document grants permission to execute an infrastructure action. Authorization is determined at runtime by identity, RBAC, policy, capability class, target scope, approval state, and environment controls.

## 9. Dependencies and Traceability

- Product intent originates in [ATLAS-001](001_Product_Vision.md).
- Product requirements originate in [ATLAS-002](002_Product_Requirements.md).
- Terms used by these principles are defined in [ATLAS-004](004_Glossary.md).
- Policy behavior is specified by [ATLAS-025](025_Policy_Engine.md).
- Approval behavior is specified by [ATLAS-037](037_Approval_Workflow.md).
- AI safety controls are specified by [ATLAS-047](047_Guardrails.md).
- Future requirements, ADRs, implementations, and tests must reference applicable `PRN-NNN` identifiers.

## 10. Assumptions

- Atlas will operate in enterprise environments with heterogeneous infrastructure and identity systems.
- The configured LLM may be local, privately hosted, or externally hosted under organizational policy.
- Customer risk and approval matrices will differ, while the deny-by-default boundary remains consistent.
- Some target platforms cannot provide identical capabilities or audit detail; connectors must expose these limitations.

## 11. Open Questions

- Which `PRN-NNN` principles should be enforced by automated repository checks?
- Which capability classes will be implemented in the first MVP beyond C0 and C1?
- Which customer-configurable policies require a non-overridable platform minimum?
- Which roles will serve as formal reviewers and approvers before version 1.0.0?

## 12. Acceptance Criteria

This document is ready to enter Review when:

- Product, architecture, security, and development decisions can be evaluated against explicit principle IDs.
- The boundary between AI recommendation and operational execution is unambiguous.
- Capability risk classes and default policies are agreed.
- Enterprise security, evidence, audit, and data-governance expectations are complete enough to guide architecture.
- Generated MCP connectors and other AI-generated artifacts are explicitly untrusted until validated.
- Required reviewers and the approver are confirmed.

## 13. Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | 2026-07-21 | Project Atlas Team | Initial draft |
| 0.2.0 | 2026-08-03 | Architecture Owner | Added governed metadata, stable principle IDs, execution boundaries, capability classes, output contract, and review gates |
| 1.0.0 | 2026-08-03 | Umit Ozdemir | Approved as the first binding documentation baseline under the designated approver authority |
