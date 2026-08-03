# Project Atlas

Project Atlas is an enterprise-grade AI Infrastructure Operations Platform.

Its purpose is to help infrastructure teams understand complex environments, analyze operational problems, assess risk, and generate explainable recommendations without allowing AI to perform unauthorized infrastructure changes.

Atlas is not a traditional monitoring tool and it is not an autonomous operator. It is designed as an intelligent decision-support platform that can correlate infrastructure data, vendor knowledge, operational history, topology, health checks, and human-approved workflows.

The project now has an approved documentation baseline. All 47 planned governed documents are at version `1.0.0` with `Approved` status. Implementation has not started and requires an explicit implementation task governed by these contracts.

## Executive Summary

Modern enterprise infrastructure spans storage systems, SAN switches, virtualization platforms, operating systems, backup platforms, directory services, network services, and vendor-specific tools. These domains are often managed through separate consoles, APIs, scripts, runbooks, and operational knowledge.

Project Atlas aims to create a unified AI-assisted operations platform for this environment. It uses modular MCP connectors, an infrastructure knowledge graph, retrieval-augmented generation, AI agents, policy controls, and enterprise governance to help engineers investigate incidents, understand impact, and prepare safe remediation plans.

Atlas must be suitable for enterprise environments from the beginning. Security, RBAC, LDAP and Active Directory integration, audit logging, Syslog, SIEM integration, explainability, approval workflows, and reproducible deployment are core requirements, not optional later additions.

## Core Principle

AI assists. Humans decide.

Atlas may analyze, correlate, explain, recommend, prepare plans, estimate impact, and propose rollback steps. It must not execute operationally risky actions without explicit human approval and policy control.

## Product Vision

Atlas should become the AI-powered operating platform that understands enterprise infrastructure, reasons about operational problems, and assists engineers in making safe, explainable, and informed decisions.

The long-term vision includes:

- Infrastructure discovery and relationship mapping
- Infrastructure knowledge graph
- Vendor and operational knowledge management
- Health checks and scheduled assessments
- Root cause analysis
- Change impact analysis
- Risk scoring and service interruption estimation
- Recommendation and rollback planning
- Human-controlled approval workflows
- Enterprise audit and compliance evidence
- AI-assisted MCP connector generation

## Design Principles

The following principles are architectural constraints for the entire project.

### AI Assists, Humans Decide

Atlas may analyze, explain, recommend, and prepare plans. It must not perform operationally risky or infrastructure-changing actions without explicit human approval and policy control.

### Explainability First

Every recommendation must include evidence, reasoning, confidence, risk, expected impact, assumptions, and alternatives where applicable.

### Enterprise First

Atlas must be designed for enterprise usage from day one, including identity integration, RBAC, auditability, logging, approval workflows, high availability, and operational governance.

### Vendor Agnostic

Atlas must not depend on a single vendor ecosystem. Infrastructure capabilities should be integrated through modular MCP connectors.

### Modular by Design

MCP connectors, AI agents, health checks, workflows, policies, reports, knowledge sources, and UI modules should be independently replaceable and versioned.

### Security by Default

Secure defaults, least privilege, protected secrets, auditable actions, and safe failure behavior are mandatory.

### Reproducible From the Repository

Everything required to build, test, validate, and deploy Atlas should be documented and automated from the repository. Enterprise and restricted-network environments must be considered in setup and bootstrap design.

## Initial Scope

- Modular MCP-based infrastructure integrations
- Infrastructure knowledge graph
- RAG-based vendor and operational knowledge
- AI-assisted troubleshooting and root cause analysis
- Health checks, reporting, and recommendations
- Enterprise authentication, RBAC, audit logging, Syslog, SIEM, and ITSM integration
- Human-controlled change impact analysis and approval workflows

## Roadmap

### Phase 1 - Product Definition

Define product vision, requirements, principles, and shared terminology.

### Phase 2 - Architecture

Define system, component, service, deployment, AI, RAG, and event architecture.

### Phase 3 - Core Platform

Define the MCP framework and SDK, MCP Builder, workflow, decision, policy, graph, and knowledge engines.

### Phase 4 - Enterprise

Define authentication, RBAC, audit, logging, Syslog, SIEM, ITSM, approval, deployment, and bootstrap controls.

### Phase 5 - AI

Define agents, reasoning, root cause analysis, recommendations, change impact, runbook intelligence, explainability, and guardrails.

### Phase 6 - Development

Define API, backend, frontend, databases, coding standards, testing, deployment, CI/CD, and release practices.

### Phase 7 - AI Development Control

Define the master operating prompt and control protocol for AI-assisted development.

## Development Status

Current status: Approved Documentation Baseline.

Implementation has not started. The repository currently contains the approved documentation foundation and repository structure only. Backend, frontend, MCP connector, AI agent, and deployment implementation may begin only through an explicit task that follows the approved contracts.

All 47 governed documents are at version `1.0.0` with `Approved` status and form the first binding implementation baseline.

## Repository Structure

```text
AGENTS.md          AI development rules for Codex, Claude Code, and similar agents
docs/              Product, architecture, platform, security, AI, and development documents
backend/           Backend services and APIs
frontend/          Web interface
mcp/               MCP framework and connector implementations
agents/            AI agent definitions and orchestration
knowledge/         RAG, document ingestion, and knowledge sources
workflows/         Health checks, runbooks, and operational workflows
infrastructure/    Deployment and platform infrastructure
tests/             Test suites and validation assets
scripts/           Project automation, bootstrap, and environment checks
```

Each top-level directory contains a short README that defines its ownership and current status.

## Getting Started

Getting started instructions will be added after the architecture and development workflow documents are accepted.

Planned setup modes:

- Online development setup
- Restricted-network enterprise setup
- Offline or mirrored dependency setup
- Environment validation through project scripts

Until then, contributors should read:

- `AGENTS.md`
- `docs/README.md`
- `docs/001_Product_Vision.md`
- `docs/002_Product_Requirements.md`
- `docs/003_Project_Principles.md`
- `docs/060_Master_Prompt.md`

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the documentation lifecycle, review and approval workflow, versioning policy, and pull request expectations.

- Do not start implementation until foundational documents are accepted.
- Do not commit secrets, credentials, IP addresses, customer names, or real infrastructure details.
- Keep changes scoped to the assigned task.
- Preserve the principle that AI assists and humans decide.
- Update documentation when decisions change.
