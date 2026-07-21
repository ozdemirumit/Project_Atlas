# Project Atlas

Project Atlas is an enterprise-grade AI Infrastructure Operations Platform.

Its purpose is to help infrastructure teams understand complex environments, analyze operational problems, assess risk, and generate explainable recommendations without allowing AI to perform unauthorized infrastructure changes.

## Core Principle

AI assists. Humans decide.

Atlas may analyze, correlate, explain, recommend, prepare plans, estimate impact, and propose rollback steps. It must not execute operationally risky actions without explicit human approval and policy control.

## Initial Scope

- Modular MCP-based infrastructure integrations
- Infrastructure knowledge graph
- RAG-based vendor and operational knowledge
- AI-assisted troubleshooting and root cause analysis
- Health checks, reporting, and recommendations
- Enterprise authentication, RBAC, audit logging, Syslog, SIEM, and ITSM integration
- Human-controlled change impact analysis and approval workflows

## Repository Structure

```text
docs/             Product, architecture, platform, security, AI, and development documents
backend/          Backend services
frontend/         Web interface
mcp/              MCP framework and connector implementations
agents/           AI agent definitions and orchestration
knowledge/        RAG, document ingestion, and knowledge sources
workflows/        Health checks, runbooks, and operational workflows
infrastructure/   Deployment and platform infrastructure
tests/            Test suites
scripts/          Project automation scripts
```

## Current Status

This repository is in the product-definition phase. Implementation should not begin until the foundational documents under `docs/` are reviewed and accepted.
