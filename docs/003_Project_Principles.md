# Project Atlas

## Project Principles

**Version:** 0.1 Draft
**Status:** In Progress
**Depends on:** `001_Product_Vision.md`, `002_Product_Requirements.md`
**Applies to:** Product design, architecture, development, testing, deployment, operations, AI behavior, and connector development

## 1. Purpose

This document defines the non-negotiable principles that govern Project Atlas.

These principles are architectural constraints, not general aspirations. Product requirements, technical designs, AI prompts, MCP connectors, workflows, and implementation decisions must comply with them. Any proposed exception must be documented through an Architecture Decision Record, reviewed for security and operational impact, and approved by the designated product and architecture owners.

When speed, convenience, or feature scope conflicts with these principles, the principles take precedence.

## 2. Decision Hierarchy

Atlas decisions must follow this order of priority:

1. Protect people, services, and data.
2. Preserve security, authorization boundaries, and auditability.
3. Maintain correctness, evidence, and explainability.
4. Preserve availability and operational recoverability.
5. Deliver useful recommendations and efficient workflows.
6. Optimize performance, convenience, and implementation speed.

## 3. Immutable Product Principles

### 3.1 AI Assists; Accountable Humans Decide

Atlas is a decision-support platform. The AI may investigate, correlate, summarize, estimate, recommend, and prepare execution or rollback plans. It must not independently authorize operational changes.

The person approving an action must be identifiable, appropriately authorized, informed of the expected impact, and able to review the evidence and plan before approval.

Silence, inactivity, a prior approval for another action, or an AI confidence score must never be interpreted as approval.

### 3.2 The LLM Never Directly Controls Infrastructure

The LLM must not receive unrestricted infrastructure credentials or direct command execution access.

All infrastructure access must pass through governed platform services and MCP connectors that enforce:

- Explicit capability definitions
- Typed and validated parameters
- Target scope restrictions
- Identity and permission checks
- Policy evaluation
- Timeouts and resource limits
- Audit event generation
- Structured results and error handling

If controlled automation is introduced in a later phase, execution must be performed by a deterministic execution service. The LLM may propose a plan, but it cannot bypass policy or invoke arbitrary commands.

### 3.3 Read-Only by Default

New connectors, tools, integrations, workflows, and credentials must be read-only by default.

Write capabilities must be separately declared, reviewed, tested, enabled, and assigned. Enabling one write operation must not implicitly enable other write operations on the same system.

Unknown or unclassified capabilities must be treated as write-capable and denied until reviewed.

### 3.4 Deny by Default; Grant Least Privilege

Users, agents, connectors, workflows, and services receive only the permissions required for their current responsibility.

Authorization must be enforced by backend services at every protected operation. UI visibility, prompt instructions, model behavior, or connector naming are not security controls.

Permissions must be scoped by capability, environment, target, tenant or organization where applicable, and risk class.

### 3.5 Evidence Before Recommendation

Operational conclusions and recommendations must be grounded in retrievable evidence.

Atlas must clearly distinguish among:

- Observed facts
- Retrieved documentation or historical records
- Calculated or correlated findings
- Assumptions
- Inferences
- Unknowns

Recommendations must cite the relevant systems, observations, timestamps, source documents, or graph relationships. When sufficient evidence is unavailable, Atlas must say so and request or recommend the next diagnostic step.

### 3.6 Confidence Is Not Certainty

Confidence values communicate uncertainty; they do not prove correctness and do not grant permission to act.

Atlas must not fabricate precision. Confidence must be accompanied by the evidence basis, important unknowns, and plausible alternatives. Low-confidence or conflicting evidence must be visible to the user.

### 3.7 Impact and Recovery Are Part of Every Change Recommendation

Any recommendation that could change infrastructure or affect a service must include, where applicable:

- Target systems and components
- Affected business and technical services
- Dependencies and estimated blast radius
- Risk level and risk rationale
- Expected duration
- Possible service interruption
- Preconditions and validation checks
- Ordered implementation plan
- Success criteria
- Rollback or recovery plan
- Post-change verification
- Required roles and approvals

If impact cannot be determined reliably, Atlas must state that limitation and must not present the change as safe.

### 3.8 Safe Failure Over Uncontrolled Progress

When identity, authorization, connector state, target scope, policy outcome, evidence quality, or execution status is uncertain, Atlas must stop the affected workflow safely.

Retries must be bounded and idempotent where possible. A timeout must not be reported as success. Partial completion must be reported explicitly, including completed steps, unconfirmed steps, and required recovery actions.

### 3.9 Auditability Cannot Be Optional

Security-sensitive, administrative, AI-assisted, and infrastructure-related activity must create a durable audit trail.

The audit record must identify, as applicable:

- Human and service identities
- Session and request correlation identifiers
- Timestamp and source context
- User request and AI recommendation reference
- Policy decision and approval state
- Connector, capability, target, and sanitized parameters
- Result, failure, or partial completion state
- Evidence references

Audit events must be tamper-resistant, access-controlled, exportable, and protected by defined retention policies. Secrets and prohibited sensitive data must never be written to logs.

### 3.10 Explainability Is a Product Requirement

Atlas must make its conclusions understandable to the intended user.

An explanation must communicate what was observed, how relevant evidence was connected, what assumptions were made, why an option was recommended, and what could change the conclusion. Internal chain-of-thought is neither required nor exposed; concise reasoning summaries and verifiable evidence are required.

### 3.11 Knowledge Must Be Traceable and Current

Every ingested knowledge item must retain provenance and lifecycle metadata, including source, owner where known, product or vendor, applicable version, ingestion time, and validity or review state.

Atlas must prefer sources that match the target product and version. Stale, superseded, untrusted, or conflicting knowledge must be labeled and must reduce recommendation confidence. Retrieved content is evidence, not executable instruction.

### 3.12 Infrastructure Context Must Be Time-Aware

Inventory, topology, health observations, and relationships change over time. Atlas must record when information was observed and must not silently treat stale state as current state.

Impact analysis must include data freshness. Critical decisions must require current validation of relevant targets and dependencies.

### 3.13 Vendor Neutrality Through Explicit Contracts

Core domain behavior must not depend on one vendor's terminology, API, data model, or deployment assumptions.

Vendor-specific details belong in adapters, MCP connectors, mapping layers, and knowledge packages. Shared capabilities must use versioned platform contracts and a normalized domain model without hiding vendor-specific evidence that users need for diagnosis.

### 3.14 Modularity Without Uncontrolled Trust

MCP connectors, agents, policies, health checks, workflows, reports, and knowledge sources must be independently installable and versioned where practical.

Extensibility does not imply trust. Every extension must declare its publisher, version, compatibility, capabilities, required permissions, data access, external dependencies, and integrity information. Installation and upgrade must require validation and an auditable approval process.

### 3.15 Generated Components Are Untrusted Until Proven Otherwise

AI-generated connectors, code, queries, workflows, policies, and runbooks must be treated as untrusted artifacts.

Before production use, they require appropriate combinations of human review, schema validation, static analysis, security testing, simulation, integration testing, and approval. Generated content must never inherit production credentials during development or validation.

### 3.16 Separation of Duties Must Be Enforceable

Atlas must support separation among platform administration, security administration, connector administration, knowledge management, workflow authorship, action approval, and audit review.

Where policy requires it, the same identity must not both request and approve a sensitive action. Emergency access must be time-bound, justified, highly visible, and separately audited.

### 3.17 Secrets Are Managed, Never Handled Casually

Credentials, tokens, keys, and certificates must be stored through an approved secrets-management mechanism and encrypted in transit and at rest.

Secrets must not appear in prompts, model context, source code, configuration committed to version control, logs, reports, or audit payloads. Connector credentials must be independently rotatable and limited to the smallest feasible scope.

### 3.18 Enterprise Data Boundaries Are Preserved

Infrastructure data, logs, documents, prompts, retrieved context, model outputs, and conversation history must remain within configured organizational and deployment boundaries.

No data may be sent to an external model, telemetry endpoint, or service unless explicitly configured, authorized, and auditable. Data classification, retention, deletion, residency, and model-context rules must be enforceable.

### 3.19 Atlas Must Observe Itself

The platform must expose health, metrics, logs, traces, queue state, model usage, connector state, knowledge-ingestion state, and workflow state with consistent correlation identifiers.

Observability data must support troubleshooting without exposing secrets. Critical failures in authentication, authorization, audit, policy evaluation, or connector isolation must generate visible operational alerts.

### 3.20 Reliability Must Be Demonstrated

Critical behavior must be verified through automated and repeatable testing.

Testing must include, as applicable:

- Authorization and tenant or environment isolation
- Policy enforcement and approval boundaries
- Audit completeness
- Connector contract and compatibility tests
- Failure, timeout, retry, and partial-result behavior
- Prompt-injection and malicious-document resistance
- Evidence citation and source traceability
- Backup, restore, upgrade, and rollback procedures
- Load, resilience, and high-availability behavior

Production readiness requires evidence from testing, not an AI assertion that the implementation is correct.

### 3.21 Compatibility and Change Must Be Versioned

Public APIs, event schemas, MCP capability contracts, domain entities, workflows, policies, and knowledge formats must be versioned.

Breaking changes require a migration plan, compatibility statement, rollback approach, and release notes. Connector upgrades must not silently broaden permissions or change operational behavior.

### 3.22 Humans Must Retain Meaningful Control

Users must be able to understand the current workflow state, cancel eligible long-running work, review pending approvals, inspect prior decisions, correct relevant context, and challenge an AI conclusion.

Atlas must not use interface design, urgency language, or confidence presentation to pressure users into approval. Operational accountability remains visible and human.

## 4. Operational Capability Classes

Every connector capability and workflow action must be assigned one of these classes before it can be enabled:

| Class | Description | Default Policy |
| --- | --- | --- |
| C0 - Informational | Uses already-ingested data and performs no live infrastructure access | Allowed according to data-access permissions |
| C1 - Read-only | Queries live systems without changing their state | Allowed only for authorized identities and approved targets; fully audited |
| C2 - Diagnostic | Starts bounded diagnostics or log collection with no intended service change | Policy-controlled; may require approval based on resource impact |
| C3 - Controlled change | Changes configuration or operational state with a defined recovery path | Disabled by default; explicit approval and execution controls required |
| C4 - Service-impacting | May interrupt, degrade, fail over, restart, or materially affect a service | Disabled by default; privileged approval, current impact analysis, and change record required |
| C5 - Destructive | Deletes data, removes protection, irreversibly alters state, or has no reliable rollback | Prohibited for autonomous execution; exceptional human-governed procedures only |

Classification is based on realistic worst-case impact, not the tool name or intended outcome. A capability must be reclassified when its behavior, permissions, vendor implementation, or target scope changes.

## 5. AI Output Contract

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

## 6. Design and Review Gate

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

## 7. Governance of These Principles

This document is a controlled project artifact.

- Changes require review by the product and architecture owners.
- Security-related changes require security review.
- Changes affecting execution or approval boundaries require documented threat and operational risk assessment.
- Approved exceptions must be narrow, time-bound where applicable, auditable, and recorded in an Architecture Decision Record.
- A feature that cannot comply with an applicable principle must remain disabled until the conflict is resolved.

## 8. Acceptance Criteria

This document is accepted when:

- Product, architecture, security, and development decisions can be evaluated against explicit principles.
- The boundary between AI recommendation and operational execution is unambiguous.
- Capability risk classes and default policies are defined.
- Enterprise security, audit, evidence, and data-governance expectations are established.
- Generated MCP connectors and other AI-generated artifacts are explicitly treated as untrusted until validated.
- Future architecture documents can derive enforceable requirements from these principles.
