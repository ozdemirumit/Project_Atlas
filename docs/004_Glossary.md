# Project Atlas

## Glossary

| Field | Value |
| --- | --- |
| Document ID | ATLAS-004 |
| Version | 1.0.0 |
| Status | Approved |
| Document Owner | Architecture Owner |
| Reviewers | Product Owner, Security Architecture, Infrastructure Domain Architects |
| Approver | Umit Ozdemir (Product Owner) |
| Approval Date | 2026-08-03 |
| Last Updated | 2026-08-03 |
| Related Documents | [ATLAS-001](001_Product_Vision.md), [ATLAS-002](002_Product_Requirements.md), [ATLAS-003](003_Project_Principles.md), [ATLAS-010](010_System_Architecture.md), [ATLAS-020](020_MCP_Framework.md) |
| Supersedes | ATLAS-004 version 0.1.0 |

## 1. Purpose

This glossary defines the canonical product, infrastructure, AI, security, and governance terminology used by Project Atlas.

Consistent language is necessary because Atlas spans multiple infrastructure domains and vendor ecosystems. The same word can otherwise imply different permissions, risk levels, or technical behavior. Governed documents, APIs, user interfaces, events, policies, and reports should use these definitions.

## 2. Scope

### In Scope

- Cross-platform Atlas product and architecture terms
- AI decision-support terminology
- MCP integration and capability terminology
- Infrastructure graph, knowledge, workflow, security, and governance terms
- Operational risk and approval terminology

### Out of Scope

- Complete definitions for individual vendor products
- Customer-specific organizational language
- General IT terms that have no Atlas-specific meaning
- API field-level schemas, which belong in interface specifications

Vendor-specific terms should be maintained in versioned vendor knowledge packs unless they become part of a shared Atlas contract.

## 3. Terminology Rules

- A canonical term should be used consistently instead of introducing synonyms in separate documents.
- Acronyms must be expanded on first use in each governed document.
- The words `must`, `must not`, `should`, and `may` retain the normative meanings defined in ATLAS-003.
- `AI`, `LLM`, `agent`, `workflow`, `connector`, and `capability` are not interchangeable.
- `Approval` and `authorization` are separate controls; one does not replace the other.
- `Audit log` and `operational log` are separate record types, even when exported to the same platform.
- A proposed term that changes a platform contract must be reviewed as a glossary and architecture change.

## 4. Canonical Terms

### A

**Action**

A requested unit of operational behavior against a defined target. An action is implemented through a declared capability and is subject to identity, authorization, policy, risk classification, approval, and audit controls.

**Agent**

A bounded AI-assisted logical worker responsible for a defined task such as investigation, retrieval, correlation, root cause analysis, or recommendation preparation. An agent does not receive inherent authority to execute infrastructure changes.

**Agentic Workflow**

A controlled workflow in which one or more agents select or sequence permitted analysis steps to achieve a defined objective. Agentic behavior remains bounded by tool allowlists, budgets, policy, authorization, and audit controls.

**Approval**

An explicit, recorded decision by an authorized human to permit a specific proposed action, target, parameter set, and time window. Approval does not replace runtime authorization or policy evaluation.

**Approval Workflow**

The governed process that routes a proposal to the required approvers, captures decisions and conditions, handles expiry or rejection, and produces audit evidence before eligible execution.

**Architecture Decision Record (ADR)**

A versioned record of a significant architecture decision, its context, alternatives, consequences, and approval status. ADRs use stable `ADR-NNN` identifiers.

**Assumption**

A statement treated as true for analysis despite lacking sufficient direct evidence. Assumptions must be visible and must not be presented as observations.

**Audit Event**

A structured, immutable-intent record of one security-relevant or operationally relevant occurrence, including actor, action, target, time, decision context, and outcome.

**Audit Log**

The tamper-resistant collection and retention mechanism for audit events. It supports accountability, investigation, compliance, and external export.

**Authentication**

The process of verifying the identity of a human, service, or system.

**Authorization**

The runtime decision that an authenticated identity is permitted to perform a specific operation on a specific target within a specific context.

**Autonomous Remediation**

Infrastructure-changing execution initiated and authorized without a human decision for the specific action. Autonomous remediation is outside the Atlas MVP and is prohibited for service-impacting and destructive capability classes.

### B

**Blast Radius**

The estimated set of technical components, business services, users, locations, and dependent processes that could be affected by a fault or proposed change.

**Business Service**

A business-facing outcome delivered by one or more applications and infrastructure dependencies. Business services are modeled separately from individual technical components.

### C

**Capability**

A versioned, machine-readable operation exposed by a connector or platform service. A capability declares its input and output schemas, risk class, permissions, side effects, target constraints, and operational characteristics.

**Capability Class**

The Atlas operational risk category assigned to a capability or workflow action: C0 Informational, C1 Read-only, C2 Diagnostic, C3 Controlled change, C4 Service-impacting, or C5 Destructive.

**Capability Manifest**

The signed or integrity-verifiable metadata describing an extension's identity, version, compatibility, capabilities, permissions, schemas, dependencies, and risk declarations.

**Change**

An intentional modification to infrastructure configuration, software, data, topology, protection, or operational state.

**Change Impact Analysis**

The evidence-based assessment of a proposed change's dependencies, blast radius, risk, duration, service interruption, prerequisites, alternatives, and recovery options.

**CMDB**

Configuration Management Database. A managed source of configuration items and relationships that Atlas may ingest as evidence. CMDB data is not assumed to be complete or current without validation.

**Confidence**

A bounded indication of how strongly available evidence supports a conclusion. Confidence is not certainty, authorization, approval, or a guarantee of correctness.

**Connector**

A modular Atlas integration component that maps a target system's APIs, CLI, SDK, events, or data model into governed Atlas capabilities and normalized results.

**Connector Instance**

A configured deployment of a connector for a particular environment, credential reference, endpoint set, and target scope.

**Controlled Automation**

Execution performed by deterministic platform services under explicit identity, policy, authorization, approval, scope, and audit controls. Controlled automation is distinct from AI directly executing a command.

**Correlation ID**

A unique identifier propagated across requests, workflows, connector calls, logs, traces, audit events, and AI outputs to support end-to-end investigation.

### D

**Data Freshness**

The age and observation time of data relative to the decision being made. Freshness must be disclosed when stale data could change an analysis or recommendation.

**Decision Engine**

The component that combines evidence, graph context, analysis results, policy outcomes, and risk information into structured decision-support outputs. It does not grant authorization.

**Deterministic Execution Service**

A non-LLM service that performs only predefined, validated, authorized, and policy-approved capabilities with bounded behavior and complete audit reporting.

**Digital Twin**

A time-aware modeled representation of infrastructure entities, state, behavior, and relationships used to evaluate scenarios without changing the real environment. A digital twin is an approximation and must expose its data age and modeling limits.

### E

**Environment**

A governed operational boundary such as development, test, staging, or production. Environments may have distinct identities, credentials, policies, data, and connector instances.

**Evidence**

Observable data supporting a conclusion, including connector results, logs, events, metrics, configuration, topology relationships, documents, and historical records.

**Evidence Package**

The structured collection of evidence references, timestamps, provenance, data-freshness information, assumptions, and analysis outputs supporting a recommendation or finding.

**Explainability**

The ability to show what was observed, which sources were used, how evidence relates to a conclusion, what assumptions remain, and why an option was recommended. Explainability does not require exposing private model reasoning.

**Extension**

A separately versioned component that expands Atlas, such as a connector, agent definition, workflow, policy package, health check, report, UI module, or knowledge pack.

### G

**Generated Artifact**

Code, configuration, connector definitions, queries, workflows, policies, runbooks, or documentation produced with AI assistance. Generated artifacts are untrusted until reviewed and validated.

**Guardrail**

A non-optional technical or procedural control that constrains AI, workflow, connector, data, or execution behavior. Prompt instructions alone are not sufficient guardrails.

### H

**Health Check**

A versioned, scheduled or on-demand assessment of infrastructure condition using declared evidence queries, evaluation rules, thresholds, and reporting behavior.

**Human-in-the-Loop (HITL)**

A workflow design requiring meaningful human review or decision at a defined point. A passive notification is not human approval.

### I

**Identity**

The authenticated representation of a human, service, connector, or external system used for authorization and audit.

**Impact**

The expected or observed consequence of an event or action on infrastructure, data, technical services, business services, users, compliance, or operations.

**Inference**

A conclusion derived from observations and other evidence rather than directly observed. Inferences must be distinguished from facts.

**Infrastructure Entity**

A normalized object representing a physical, virtual, logical, cloud, application, or service component managed or observed by Atlas.

**Infrastructure Graph**

The time-aware graph of infrastructure entities and typed relationships used for dependency, root cause, and impact analysis.

**Infrastructure Inventory**

The catalog of discovered or imported infrastructure entities, their identifiers, attributes, source systems, ownership, and observation times.

**ITSM**

Information Technology Service Management. In Atlas, ITSM integrations may exchange incidents, problems, changes, approvals, tasks, and evidence with governed external systems.

### K

**Knowledge Item**

A versioned unit of retrievable knowledge with content, provenance, ownership, product applicability, validity, classification, and ingestion metadata.

**Knowledge Pack**

A versioned collection of related knowledge items, terminology, mappings, prompts, checks, and retrieval metadata for a vendor, product, domain, or organizational practice.

**Knowledge Source**

The origin system or document collection from which knowledge items are ingested, such as vendor documentation, an internal wiki, runbooks, tickets, or architecture records.

### L

**Large Language Model (LLM)**

A model used for language understanding and generation. In Atlas, an LLM is an analytical component and does not possess identity, approval authority, credentials, or unrestricted infrastructure access.

**Least Privilege**

The principle that an identity or component receives only the minimum permissions, targets, data access, and duration required for its assigned responsibility.

**Local LLM**

An LLM endpoint operated within an organization's controlled environment. Local deployment does not remove the need for authorization, data classification, model security, or audit controls.

### M

**MCP**

Model Context Protocol. A protocol for exposing tools, resources, and contextual capabilities to AI-enabled clients through defined interfaces.

**MCP Builder**

An Atlas capability that assists in generating connector artifacts from API specifications, CLI references, schemas, examples, and vendor documentation. Its output is a generated artifact and is not production-trusted automatically.

**MCP Connector**

An Atlas connector implemented through MCP. It combines protocol-level exposure with Atlas-specific lifecycle, capability, policy, authorization, audit, and normalization requirements.

**MCP Server**

A protocol endpoint that exposes MCP tools or resources. An MCP server is not automatically an approved Atlas connector; it becomes eligible only after registration, validation, risk classification, and policy assignment.

**Model Context**

The bounded information supplied to an LLM for a request, including instructions, conversation state, retrieved evidence, and tool results. Context must follow data-classification and minimization rules.

### O

**Observation**

A time-stamped fact obtained directly from a source, connector, log, metric, event, or user-confirmed input.

**Operational Log**

A record used to understand platform behavior, performance, failures, and service health. Operational logs do not replace audit logs.

### P

**Plugin**

A packaged extension distributed for installation into Atlas. A plugin may contain one or more connectors, policies, workflows, checks, knowledge packs, or UI modules and must declare its trust and compatibility metadata.

**Policy**

A versioned rule that evaluates context and determines whether an operation is allowed, denied, or requires additional conditions or approval.

**Policy Engine**

The deterministic component that evaluates policies using identity, role, capability class, target, environment, approval, time, and other governed context.

**Prompt Injection**

Untrusted content designed to alter AI behavior, override instructions, disclose data, or induce unsafe tool use. Retrieved documents and tool results must be treated as potentially hostile input.

**Provenance**

Metadata identifying where evidence or knowledge originated, how it was collected or transformed, who owns it, and which version applies.

### R

**RAG**

Retrieval-Augmented Generation. A pattern in which relevant knowledge and evidence are retrieved and supplied to an LLM before an answer is generated.

**RBAC**

Role-Based Access Control. An authorization model in which permissions are assigned to roles and roles are assigned to identities, usually with additional target and environment scope.

**Reasoning Summary**

A concise, user-facing explanation of the evidence connections, assumptions, alternatives, and decision basis behind an AI output. It is not private model chain-of-thought.

**Recommendation**

A proposed diagnostic or remediation approach containing evidence, confidence, risk, impact, duration, preconditions, approvals, alternatives, and recovery guidance as applicable.

**Recovery Plan**

A prepared method for restoring an acceptable service state after a failed, partial, or harmful action. It may include rollback, failover, restore, or manual recovery procedures.

**Relationship**

A typed, directional, time-aware connection between infrastructure entities, such as `hosts`, `depends_on`, `connected_to`, `protects`, or `runs_on`.

**Risk**

The combination of likelihood and consequence associated with an event, recommendation, action, or uncertainty.

**Rollback Plan**

An ordered procedure for reversing a change to a known prior state. When reversal is impossible, the correct term is recovery plan rather than rollback plan.

**Root Cause Analysis (RCA)**

An evidence-based analysis that identifies and ranks probable causes of a problem, shows affected components and relationships, states confidence and unknowns, and recommends validation steps.

**Runbook**

A versioned operational procedure for diagnosis, maintenance, incident handling, change, validation, rollback, or recovery.

### S

**Secret**

Sensitive authentication material such as a password, token, private key, or certificate key. Secrets are referenced through approved secret-management systems and are never embedded in prompts, source code, logs, or committed configuration.

**Separation of Duties**

A control that distributes sensitive responsibilities among distinct roles or identities so that one actor cannot request, approve, execute, and audit the same action when policy prohibits it.

**Service Account**

A non-human identity used by a service or connector. It must have an owner, purpose, scoped permissions, rotation policy, and auditable usage.

**Service Interruption**

A period of complete or partial unavailability, degradation, failover, or reduced protection affecting a technical or business service.

**SIEM**

Security Information and Event Management. A platform that receives and correlates security and audit events for detection, investigation, and compliance.

**Source Authority**

The assessed trust and relevance of a knowledge or evidence source for a specific product, version, environment, and question.

**Syslog**

A standard mechanism for transmitting structured system, security, and audit messages to external log platforms.

### T

**Target**

The explicit infrastructure entity, service, environment, or bounded collection against which a capability is requested.

**Technical Service**

A technology-facing service, such as storage, virtualization, identity, or backup, that supports applications or business services.

**Tenant**

A logically isolated organizational data and policy boundary within a shared Atlas deployment. Tenant isolation is distinct from environment separation.

**Tool**

An operation exposed to an AI client. In Atlas, a tool must map to one or more governed capabilities before it may access infrastructure.

**Traceability**

The ability to connect vision, requirements, principles, architecture decisions, implementations, tests, operations, and audit evidence through stable identifiers.

### U

**Uncertainty**

The known limitation in available evidence, model behavior, topology, source quality, or analysis. Uncertainty must be disclosed when it can affect a conclusion or action.

### W

**Workflow**

A versioned sequence or graph of steps with declared inputs, outputs, state transitions, policies, timeouts, failure handling, and audit behavior.

**Workflow Run**

A single execution instance of a workflow with a unique identity, initiator, input set, state, timestamps, evidence references, and result.

## 5. Security, Risk, and Operational Impact

Ambiguous terminology can produce unsafe implementations. In particular:

- Calling an MCP server a trusted connector can bypass required validation.
- Treating approval as authorization can permit an operation outside the approver's scope.
- Treating a diagnostic action as read-only can hide resource or service impact.
- Treating confidence as certainty can conceal uncertainty.
- Calling recovery rollback can imply reversibility that does not exist.

Architecture and implementation reviews must identify terminology that changes security or operational meaning.

## 6. Dependencies and Traceability

- Product terminology originates in [ATLAS-001](001_Product_Vision.md) and [ATLAS-002](002_Product_Requirements.md).
- Normative principles and capability classes are defined in [ATLAS-003](003_Project_Principles.md).
- System boundaries are defined in [ATLAS-010](010_System_Architecture.md).
- MCP-specific contracts are defined in [ATLAS-020](020_MCP_Framework.md) and [ATLAS-021](021_MCP_Plugin_SDK.md).
- New governed documents should link to ATLAS-004 when introducing or refining a canonical term.

## 7. Assumptions

- English is the canonical language for repository contracts during the initial product-definition phase.
- User-facing localization may use translated labels while preserving the same semantic meaning.
- Vendor terminology will remain available as source evidence even when Atlas maps it to a normalized term.

## 8. Open Questions

- Which customer-specific terms require configurable aliases in the user interface?
- Should vendor knowledge packs contain separate machine-readable term mappings?
- Which glossary terms should become schema enumerations or API resource names?
- Should future approved terms require a lightweight terminology ADR?

## 9. Acceptance Criteria

This document is ready to enter Review when:

- Product, architecture, security, and infrastructure reviewers agree on the canonical meanings.
- MCP server, MCP connector, connector, plugin, capability, and tool are clearly distinguished.
- Approval, authorization, policy, and execution are clearly distinguished.
- Observation, evidence, assumption, inference, confidence, and uncertainty are clearly distinguished.
- Capability classes and operational impact language align with ATLAS-003.
- Terms used in the Phase 1 documents do not conflict with these definitions.

## 10. Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | 2026-07-21 | Project Atlas Team | Initial glossary draft |
| 0.2.0 | 2026-08-03 | Architecture Owner | Added governed metadata, canonical terminology rules, expanded cross-domain definitions, and traceability |
| 1.0.0 | 2026-08-03 | Umit Ozdemir | Approved as the first binding documentation baseline under the designated approver authority |
