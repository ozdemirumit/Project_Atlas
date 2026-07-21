# Project Atlas

## Product Requirements Document

**Version:** 0.1 Draft  
**Status:** In Progress  
**Depends on:** `001_Product_Vision.md`

## 1. Product Summary

Project Atlas is an enterprise AI infrastructure operations platform that provides decision support for complex IT environments.

The platform connects to infrastructure systems through modular MCP connectors, collects operational context, builds infrastructure relationships, retrieves vendor and internal knowledge, and uses AI agents to analyze health, incidents, risks, and operational changes.

Atlas must be designed for enterprise environments where security, auditability, role-based access, human approval, and explainable recommendations are mandatory.

## 2. Primary Objective

The primary objective is to help infrastructure teams diagnose problems faster, understand operational impact, and make safer decisions without allowing AI to perform unauthorized changes.

## 3. Target Outcomes

Atlas should deliver the following outcomes:

- Faster incident investigation
- Better root cause analysis across infrastructure domains
- Clear explanation of evidence behind recommendations
- Safer change planning through impact and risk analysis
- Reduced dependency on undocumented human knowledge
- Centralized infrastructure knowledge and vendor documentation usage
- Enterprise-grade governance, authentication, authorization, and auditability

## 4. Target Users

### Infrastructure Engineer

Uses Atlas to investigate alerts, run health checks, query systems, and understand recommendations.

### Infrastructure Architect

Uses Atlas to analyze topology, dependencies, capacity, resilience, and change impact.

### Operations Team

Uses Atlas for periodic checks, incident summaries, reports, and operational workflows.

### IT Manager

Uses Atlas for risk summaries, service impact, executive reporting, compliance evidence, and trend analysis.

### Security and Compliance Team

Uses Atlas to review access, audit logs, command history, policy behavior, and evidence trails.

## 5. Core Product Capabilities

### 5.1 Chat-Based Operations Interface

Atlas must provide a chat-centered web interface where users can ask infrastructure-related questions.

Example questions:

- What is the current health of Hitachi storage system X?
- Which VMs are affected by datastore latency?
- Why did backup job Y fail last night?
- What is the impact of restarting this storage controller?
- Generate a weekly capacity report for VMware cluster Z.

The chat response must be structured, evidence-based, and explainable.

### 5.2 Modular MCP Connector Framework

Atlas must support modular MCP connectors for infrastructure systems.

Initial connector categories:

- Storage
- SAN switches
- Virtualization
- Linux
- Windows
- Backup platforms
- Directory services
- DNS and network services
- Cloud platforms

Connectors must be installable, removable, upgradeable, configurable, and independently testable.

### 5.3 MCP Builder

Atlas should include an MCP Builder capability that helps generate new MCP connectors from vendor documentation, REST API specifications, CLI references, and examples.

The generated MCP must not be trusted automatically. It must go through validation, review, testing, and approval before production use.

### 5.4 Infrastructure Inventory

Atlas must maintain an inventory of discovered infrastructure components.

Example entities:

- Site
- Datacenter
- Rack
- Storage system
- Storage pool
- Volume
- LUN
- SAN switch
- Fabric
- Host
- Cluster
- VM
- Datastore
- Operating system
- Backup job
- Application service

### 5.5 Infrastructure Knowledge Graph

Atlas must build and maintain relationships between infrastructure components.

Example relationship:

```text
Application
  -> VM
  -> Datastore
  -> Volume
  -> Storage Pool
  -> Storage System
  -> SAN Fabric
  -> SAN Switch
  -> Host HBA
```

This graph is required for root cause analysis, blast radius analysis, change impact analysis, and service dependency mapping.

### 5.6 RAG and Knowledge Management

Atlas must support retrieval-augmented generation using enterprise knowledge sources.

Supported knowledge source types should include:

- Vendor documentation
- REST API documentation
- CLI documentation
- Product manuals
- KB articles
- Internal runbooks
- Incident records
- Problem records
- Change records
- Architecture documents
- Operational notes
- CMDB exports

Knowledge ingestion must preserve source metadata, version, document owner, ingestion time, and retrieval evidence.

### 5.7 Health Checks

Atlas must support configurable health checks.

Health checks must be:

- Connector-based
- Schedulable
- Versioned
- Enableable and disableable
- Scoped by system, site, vendor, or domain
- Reportable
- Auditable

Health check results should feed AI analysis, reports, trends, and risk scoring.

### 5.8 Root Cause Analysis

Atlas must correlate signals from MCP connectors, logs, events, topology, historical incidents, and knowledge sources to identify probable root causes.

Every root cause analysis must include:

- Problem summary
- Evidence
- Affected components
- Possible root causes
- Confidence score
- Impact assessment
- Recommended next steps
- Unknowns and assumptions

### 5.9 Recommendation Engine

Atlas must provide recommendations in a controlled format.

Each recommendation must include:

- Recommended action
- Reasoning
- Evidence
- Risk level
- Expected impact
- Estimated duration
- Service interruption risk
- Preconditions
- Rollback plan
- Required approvals
- Alternative options

### 5.10 Change Impact Analysis

Atlas must analyze the potential impact of infrastructure changes before they are performed.

Example:

If a storage controller restart is proposed, Atlas should estimate affected volumes, hosts, clusters, VMs, applications, possible service interruption, expected duration, and rollback options.

### 5.11 Human Approval and Governance

Atlas must not execute operationally risky actions autonomously.

Operational actions must be classified by risk:

- Read-only
- Low-risk diagnostic
- Controlled operational
- Service-impacting
- Destructive

Only read-only and explicitly permitted low-risk diagnostic actions may be automated by policy. Service-impacting and destructive actions must require human approval and appropriate authorization.

### 5.12 Audit Logging

Atlas must audit all security-relevant and operationally relevant activity.

Audit events must include:

- User
- Role
- Source IP or session metadata
- Timestamp
- Requested action
- Target system
- Connector used
- Parameters
- Approval state
- Result
- Evidence returned
- AI recommendation ID when applicable

Audit logs must be tamper-resistant and exportable.

### 5.13 Enterprise Authentication and Authorization

Atlas must support enterprise identity systems.

Required capabilities:

- Local administrator bootstrap
- LDAP authentication
- Active Directory integration
- SSO-ready architecture
- Role-based access control
- Group mapping
- Least privilege enforcement
- Session management

### 5.14 Logging, Syslog, and SIEM

Atlas must support operational logs, security logs, audit logs, and integration with external log platforms.

Required capabilities:

- Structured application logging
- Syslog forwarding
- SIEM integration
- Log retention policy
- Log filtering
- Correlation IDs
- Request IDs

### 5.15 Reporting

Atlas must generate technical and management reports.

Initial report types:

- Infrastructure health report
- Capacity report
- Risk report
- Incident analysis report
- Change impact report
- Audit report
- Connector status report

Reports should be exportable in common formats in later phases.

## 6. Non-Functional Requirements

### 6.1 Security

Atlas must be secure by design.

Requirements:

- Encryption in transit
- Secure secret storage
- Least privilege connector credentials
- No plaintext credential exposure
- Auditability for all sensitive actions
- Tenant and environment isolation where required
- Secure defaults

### 6.2 Availability

Atlas should support high availability architecture for enterprise deployments.

### 6.3 Scalability

Atlas should scale across multiple sites, vendors, connector types, and infrastructure domains.

### 6.4 Performance

The platform should return interactive chat responses quickly for normal questions while allowing long-running workflows for deeper analysis and reports.

### 6.5 Explainability

AI outputs must show evidence and reasoning summaries. The user must be able to inspect why a recommendation was made.

### 6.6 Observability

Atlas itself must be observable through metrics, logs, traces, health endpoints, and connector status.

## 7. Initial MVP Scope

The first MVP should focus on proving the platform architecture, not covering every vendor.

Recommended MVP:

- Web chat interface
- Local OpenAI-compatible LLM configuration
- Basic backend API
- User authentication foundation
- Audit logging foundation
- MCP connector registry
- One mock MCP connector
- One real read-only connector candidate
- RAG document ingestion prototype
- Basic infrastructure entity model
- Health check workflow prototype
- Recommendation response format
- Human approval model design

## 8. Out of Scope for MVP

The following should not be part of the first MVP:

- Autonomous remediation
- Destructive operations
- Full MCP marketplace
- Full digital twin simulation
- Multi-tenant SaaS deployment
- Complete vendor coverage
- Production-grade MCP Builder automation

## 9. Product Risks

Key risks:

- AI hallucination in operational recommendations
- Unsafe action execution
- Over-permissioned connector credentials
- Incomplete topology leading to wrong impact analysis
- Stale vendor documentation
- Poor auditability
- Unclear ownership of generated MCP connectors
- Enterprise deployment complexity

## 10. Mandatory Guardrails

Atlas must enforce these guardrails:

- AI must not execute infrastructure-changing actions by default
- Every recommendation must include evidence
- Risky actions require explicit approval
- Connector credentials must be scoped and protected
- Audit logging cannot be disabled for sensitive actions
- Generated MCP connectors must be reviewed before production use
- AI confidence must not be presented as certainty

## 11. Open Questions

- Which infrastructure domain should be used for the first real connector?
- Which local OpenAI-compatible LLM endpoint will be used for development?
- Which vector database should be selected first?
- Should the first deployment target be Docker Compose, Kubernetes, or both?
- Which identity provider should be prioritized first: LDAP, Active Directory, or SSO?
- Which ITSM platform should be targeted first?

## 12. Acceptance Criteria

This PRD is accepted when:

- Product scope is clear enough to guide architecture documents
- MVP scope is explicitly separated from long-term vision
- AI safety principles are reflected in functional requirements
- Enterprise requirements are captured from the beginning
- Connector modularity is defined as a core requirement
- Human approval and auditability are non-negotiable requirements
