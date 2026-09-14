# Project Atlas

Project Atlas is an enterprise-grade AI Infrastructure Operations Platform.

Its purpose is to help infrastructure teams understand complex environments, analyze operational problems, assess risk, and generate explainable recommendations without allowing AI to perform unauthorized infrastructure changes.

Atlas is not a traditional monitoring tool and it is not an autonomous operator. It is designed as an intelligent decision-support platform that can correlate infrastructure data, vendor knowledge, operational history, topology, health checks, and human-approved workflows.

The project has an approved documentation baseline of 47 governed documents, all at version `1.0.0` with `Approved` status, and a working implementation built against it: 35 backend modules, 6 real vendor MCP connectors, an Enterprise React web application, and an automated deployment path, all tracked task-by-task in [`docs/implementation/IMPLEMENTATION_TRACKER.md`](docs/implementation/IMPLEMENTATION_TRACKER.md).

## Executive Summary

Modern enterprise infrastructure spans storage systems, SAN switches, virtualization platforms, operating systems, backup platforms, directory services, network services, and vendor-specific tools. These domains are often managed through separate consoles, APIs, scripts, runbooks, and operational knowledge.

Project Atlas aims to create a unified AI-assisted operations platform for this environment. It uses modular MCP connectors, an infrastructure knowledge graph, retrieval-augmented generation, AI agents, policy controls, and enterprise governance to help engineers investigate incidents, understand impact, and prepare safe remediation plans.

Atlas must be suitable for enterprise environments from the beginning. Security, RBAC, LDAP and Active Directory integration, audit logging, Syslog, SIEM integration, explainability, approval workflows, and reproducible deployment are core requirements, not optional later additions.

## Core Principle

AI assists. Humans decide.

Atlas may analyze, correlate, explain, recommend, prepare plans, estimate impact, and propose rollback
steps. It does not execute infrastructure-changing operations; approved plans are carried out through
external, human-governed organizational processes.

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

Atlas may analyze, explain, recommend, and prepare plans. It must not perform operationally risky or
infrastructure-changing actions. Approval cannot convert a recommendation into Atlas execution
authority.

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

All seven phases below define the governed documentation baseline; that baseline is complete (47/47
documents `Approved`). Implementation against it is ongoing and tracked task-by-task in
[`docs/implementation/IMPLEMENTATION_TRACKER.md`](docs/implementation/IMPLEMENTATION_TRACKER.md).

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

Current status: core platform implemented and passing continuous verification.

The backend is a runnable modular monolith of 35 domain modules (`backend/src/atlas/modules/`),
including identity and RBAC, LDAP/Active Directory integration, the infrastructure knowledge
graph, policy engine, guardrails, explainability, root cause analysis, recommendations, change
impact, runbook engine, approval workflows with ITSM binding, notifications, audit logging with a
hash-chained integrity ledger, and a retrieval-augmented knowledge base. Six vendor MCP connectors
are implemented against each vendor's real API (`mcp/connectors/`): Hitachi Ops Center, Huawei
Dorado, Huawei Pacific, Brocade SANnav, VMware vCenter, and Commvault. The web application
(`frontend/`) and the automated deployment path (see Getting Started, below) are both real and
runnable end to end. The backend carries an extensive automated test suite (850+ test files) run
with `ruff`, `mypy`, and `pytest` on every change.

Every implementation task is recorded in
[`docs/implementation/IMPLEMENTATION_TRACKER.md`](docs/implementation/IMPLEMENTATION_TRACKER.md),
which is the authoritative source for what is built, in progress, or deliberately deferred. Items
currently deferred by explicit, on-record decision rather than oversight include: the composition
of a single guardrails/pipeline architecture across several already-built modules (an open product
question, not a missing feature); the MCP Builder's manual-change tracking and regeneration
workflow; and the `infrastructure/` implementation track, which remains an intentional placeholder
pending a dedicated implementation request.

All 47 governed documents are at version `1.0.0` with `Approved` status and form the binding
implementation baseline that every task above is built against.

## Repository Structure

```text
AGENTS.md          AI development rules for Codex, Claude Code, and similar agents
docs/              Product, architecture, platform, security, AI, and development documents
backend/           Backend API and all domain modules (identity, graph, policy, RCA, ...)
frontend/          Enterprise React web application
mcp/connectors/    Real vendor MCP connector packages (Hitachi, Huawei, Brocade, vCenter, Commvault)
scripts/           Deployment (Docker) and local development automation
tests/             Cross-cutting test suites and validation assets
agents/            Placeholder for standalone AI agent orchestration (not yet implemented)
knowledge/         Placeholder for repository-level knowledge assets (not yet implemented)
workflows/         Placeholder for repository-level workflow assets (not yet implemented)
infrastructure/    Placeholder for deployment/platform infrastructure (not yet implemented)
```

Each top-level directory contains a short README that defines its ownership and current status.
`agents/`, `knowledge/`, `workflows/`, and `infrastructure/` are intentional placeholders reserved
by their governing documents -- the working equivalents of AI orchestration, RAG, and health-check
logic already exist today inside `backend/src/atlas/modules/`.

## Getting Started

Everything needed to build, run, and deploy Atlas ships in this repository -- there is nothing to
fetch from anywhere else. Cloning the repository and running one script is enough to bring the
whole stack (PostgreSQL, backend, frontend) up in a new environment.

### Deploy anywhere with Docker

Prerequisites: Docker.

```bash
git clone https://github.com/ozdemirumit/Project_Atlas.git
cd Project_Atlas
scripts/install.sh          # Linux, macOS, or WSL
```

```powershell
scripts\install.cmd         # Windows, no PowerShell execution-policy change required
# or: .\scripts\install.ps1
```

The installer builds the backend and frontend images, starts PostgreSQL, the backend, and the
frontend as plain Docker containers on a private network, runs database migrations, and waits for
every service to report healthy. There is no Docker Compose file and no YAML involved -- the
script itself is the whole deployment description. If `.env` does not already exist, the installer
creates one from `.env.example` with a freshly generated database password; review `.env.example`
first if you need to enable enterprise directory authentication or other production settings
before the first run.

Open `http://localhost:5173`. The API is available at `http://localhost:8000`, with interactive
API documentation at `http://localhost:8000/docs`.

Verify everything came up healthy:

```bash
docker ps --filter "name=atlas-"                       # all three containers should show "healthy"
curl http://localhost:8000/health/ready                 # backend readiness check
docker logs -f atlas-backend                             # follow backend logs
```

Stop and remove everything the installer created:

```bash
scripts/uninstall.sh              # Linux, macOS, or WSL
scripts/uninstall.sh --purge      # also deletes the database volume
```

```powershell
scripts\uninstall.cmd             # Windows
.\scripts\uninstall.ps1 -Purge    # also deletes the database volume
```

### Configuration

All runtime configuration lives in `.env`, which `scripts/install` creates from `.env.example` on
first run (see `.env.example` for the full, commented list). Every variable is prefixed `ATLAS_`.
For the Docker deployment path, the installer forwards the whole file into the backend container
with `docker run --env-file`; four keys (`ATLAS_ENVIRONMENT`, `ATLAS_DATABASE_REQUIRED`,
`ATLAS_DATABASE_URL`, `ATLAS_DEVELOPMENT_IDENTITY_ENABLED`) are always set explicitly by the
installer and override whatever `.env` itself says for them, because they describe the container
network rather than a user choice.

Unlike a shell or the backend's own settings loader, `docker run --env-file` does not strip
surrounding quotes from values. Keep JSON-array and other structured values in `.env` unquoted, or
a quoted value will reach the application as literal text -- including the quote characters --
instead of being parsed.

| Variable | Purpose | Default |
| --- | --- | --- |
| `ATLAS_POSTGRES_PASSWORD` | Database password for the `atlas` PostgreSQL role. Generated automatically on first install. | *(generated)* |
| `ATLAS_DEVELOPMENT_IDENTITY_ENABLED` | Enables the built-in `Local Operator` identity for local testing. Disabled by default outside the installer/dev scripts; never enable in production. | `false` |
| `ATLAS_DIRECTORY_IDENTITY_ENABLED` | Enables enterprise LDAP/Active Directory authentication. | `false` |
| `ATLAS_DIRECTORY_ENDPOINTS` | JSON array of LDAPS endpoint URLs. | `[]` |
| `ATLAS_DIRECTORY_CA_CERTIFICATE_FILE` | Path to the directory server's CA certificate, read inside the process that reads it. For the Docker deployment path this is a container-side path -- add a `docker run -v <host-path>:<container-path>:ro` for the backend container yourself and point this at the container-side path. When running the backend directly (not in a container), this is a normal host filesystem path. | *(unset)* |
| `ATLAS_DIRECTORY_USER_PRINCIPAL_TEMPLATE` | Template used to build a user's bind principal, with `{username}` substituted. | `{username}@example.internal` |
| `ATLAS_DIRECTORY_USER_SEARCH_BASE` | LDAP search base for user lookups. | `OU=People,DC=example,DC=internal` |
| `ATLAS_DIRECTORY_USER_SEARCH_FILTER` | LDAP search filter, with `{username}` substituted. | `(&(objectClass=user)(sAMAccountName={username}))` |
| `ATLAS_DIRECTORY_GROUP_MAPPINGS` | JSON array mapping directory groups to Atlas roles. No directory password or bind secret belongs in this file. | `[]` |
| `ATLAS_WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENTS` | JSON array of secret-free deployment credential-assignment metadata. Passwords, tokens, private keys, certificates, vault paths, and retrievable secret references are prohibited here. | `[]` |
| `ATLAS_SESSION_COOKIE_NAME` | Name of the browser session cookie. | `atlas_session` |
| `ATLAS_CSRF_COOKIE_NAME` | Name of the CSRF cookie. | `atlas_csrf` |
| `ATLAS_CSRF_HEADER_NAME` | Header clients must echo the CSRF token in. | `X-CSRF-Token` |
| `ATLAS_SESSION_ABSOLUTE_TIMEOUT_MINUTES` | Maximum session lifetime regardless of activity (5-1440). | `480` |
| `ATLAS_SESSION_IDLE_TIMEOUT_MINUTES` | Session expiry after inactivity (1-240). | `30` |
| `ATLAS_SESSION_MAX_PER_SUBJECT` | Maximum concurrent sessions per identity (1-20). | `5` |
| `ATLAS_API_CREDENTIAL_MAX_LIFETIME_MINUTES` | Maximum lifetime of an issued API credential (5-60). | `60` |
| `ATLAS_API_CREDENTIAL_MAX_ACTIVE_PER_SUBJECT` | Maximum concurrent active API credentials per identity (1-20). | `10` |

When running the backend directly without Docker (see below), it reads `.env` itself via its own
settings loader, which does strip matching quotes -- both quoted and unquoted values work in that
path.

### Local development without Docker

Prerequisites:

- Python 3.12
- uv 0.12.1
- Node.js 24
- pnpm 11.7.0

For direct local development on Windows without changing PowerShell execution policy:

```bat
scripts\bootstrap.cmd
scripts\dev.cmd
```

Open `http://localhost:5173`. The API is available at `http://localhost:8000`, with interactive development documentation at `http://localhost:8000/docs`.

```powershell
curl http://localhost:8000/health/ready    # backend readiness check
```

The supported development launcher explicitly enables a local, server-configured identity named
`Local Operator`. This identity is disabled by default, cannot run in production, and has only the
C0 permission required to read its own identity context. It is not an administrator account.

Run all repository quality checks with:

```bat
scripts\check.cmd
```

Equivalent PowerShell scripts remain available for environments where signed or local scripts
are permitted. Do not disable antivirus or lower organizational security controls for Atlas.

Contributors should read:

- `AGENTS.md`
- `docs/README.md`
- `docs/001_Product_Vision.md`
- `docs/002_Product_Requirements.md`
- `docs/003_Project_Principles.md`
- `docs/060_Master_Prompt.md`
- `docs/implementation/IMPLEMENTATION_TRACKER.md`
- `docs/adr/README.md`

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the documentation lifecycle, review and approval workflow, versioning policy, and pull request expectations.

- Start implementation only through a scoped task governed by the accepted documents.
- Do not commit secrets, credentials, IP addresses, customer names, or real infrastructure details.
- Keep changes scoped to the assigned task.
- Preserve the principle that AI assists and humans decide.
- Update documentation when decisions change.
