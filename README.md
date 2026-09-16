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
fetch from anywhere else except PostgreSQL itself. Cloning the repository and running one script
is enough to bring Atlas up in a new environment. There is no Docker, no containers, and no YAML
anywhere in the deployment path -- `scripts/install` runs a single backend process, no Node.js or
package registry access required.

The frontend ships pre-built as static files at `frontend/dist/`, served directly by the backend
on the same port -- a deployment target needs no Node.js, npm, or pnpm of its own. See
[Contributing](#contributing) for how to rebuild `frontend/dist/` after a frontend source change.

### Deploy anywhere

`scripts/install` installs almost everything it needs itself -- there is nothing to set up by
hand beforehand on most platforms:

- **`uv`** is installed automatically if missing, using its official installer (user-local, no
  administrator/root privileges needed).
- **PostgreSQL 18 with [pgvector](https://github.com/pgvector/pgvector)**, if `psql` isn't already
  found:
  - **macOS**: installed automatically with Homebrew (`brew install postgresql@18 pgvector`),
    after a one-line confirmation.
  - **Debian/Ubuntu**: installed automatically via the official PGDG apt repository, after a
    one-line confirmation (needs `sudo`).
  - **Windows**: the script launches the PostgreSQL installer for you via `winget`. pgvector
    ships no binary distribution for Windows at all -- only a source build is possible -- so the
    script also installs Visual Studio C++ Build Tools automatically if needed (several GB,
    several minutes) and builds pgvector from source. This requires an elevated (Administrator)
    PowerShell session; re-run as Administrator if it stops with a permissions error. If your
    network blocks the download (some corporate proxies block `.exe`/binary downloads by policy),
    obtain `vs_buildtools.exe` and the pgvector source zip through an approved channel yourself
    and pass their paths: `./scripts/install.ps1 -VcBuildToolsInstaller <path> -PgVectorArchive
    <path>`.
  - **Other Linux distributions**: no safe auto-install path is wired up; install PostgreSQL and
    pgvector yourself via your distribution's package manager (see the
    [pgvector installation notes](https://github.com/pgvector/pgvector#installation)) and re-run.

```bash
git clone https://github.com/ozdemirumit/Project_Atlas.git
cd Project_Atlas
scripts/install.sh          # Linux, macOS, or WSL
```

```powershell
scripts\install.cmd         # Windows, no PowerShell execution-policy change required
# or: .\scripts\install.ps1
```

The installer first makes sure `uv` and PostgreSQL are present (installing whichever are missing,
as described above), creates `.env` from `.env.example` with a freshly generated database
password if `.env` does not already exist, then -- the first time it cannot already connect as the
`atlas` role -- sets up the `atlas` role, `atlas` database, and `vector` extension. When the
installer just installed PostgreSQL itself (macOS/Debian/Ubuntu), this happens automatically with
no prompt; otherwise it prompts once for your existing PostgreSQL server's superuser credentials.
It then installs backend dependencies, runs database migrations, and starts the backend as a
background process (which also serves the pre-built frontend), waiting for it to report healthy.
Re-running `scripts/install` is safe: it skips already-installed prerequisites and the superuser
step once the `atlas` role is reachable, and only reinstalls dependencies and restarts the process.

Open `http://localhost:8000` -- the backend serves both the web application and the API from the
same port, with interactive API documentation at `http://localhost:8000/docs`.

Verify it came up healthy:

```bash
curl http://localhost:8000/health/ready       # backend readiness check
tail -f .atlas/backend.log
```

Stop everything the installer started:

```bash
scripts/uninstall.sh              # Linux, macOS, or WSL
scripts/uninstall.sh --purge      # also drops the atlas database and role
```

```powershell
scripts\uninstall.cmd             # Windows
.\scripts\uninstall.ps1 -Purge    # also drops the atlas database and role
```

### Configuration

All runtime configuration lives in `.env`, which `scripts/install` creates from `.env.example` on
first run (see `.env.example` for the full, commented list). Every variable is prefixed `ATLAS_`.
`ATLAS_POSTGRES_HOST` and `ATLAS_POSTGRES_PORT` (defaulting to `localhost`/`5432`) and
`ATLAS_POSTGRES_PASSWORD` are read by `scripts/install` itself to reach PostgreSQL and to build
`ATLAS_DATABASE_URL` for the backend; every other variable is read directly by the backend. Four
of them (`ATLAS_ENVIRONMENT`, `ATLAS_DATABASE_REQUIRED`, `ATLAS_DATABASE_URL`,
`ATLAS_DEVELOPMENT_IDENTITY_ENABLED`) are always set explicitly by `scripts/install` when it
starts the backend process, overriding whatever `.env` itself says for them.

| Variable | Purpose | Default |
| --- | --- | --- |
| `ATLAS_POSTGRES_HOST` | Hostname of the PostgreSQL server. Read only by `scripts/install`. | `localhost` |
| `ATLAS_POSTGRES_PORT` | Port of the PostgreSQL server. Read only by `scripts/install`. | `5432` |
| `ATLAS_POSTGRES_PASSWORD` | Password for the `atlas` PostgreSQL role. Generated automatically on first install. | *(generated)* |
| `ATLAS_DEVELOPMENT_IDENTITY_ENABLED` | Enables the built-in `Local Operator` identity for local testing. Disabled by default outside the installer/dev scripts; never enable in production. | `false` |
| `ATLAS_DIRECTORY_IDENTITY_ENABLED` | Enables enterprise LDAP/Active Directory authentication. | `false` |
| `ATLAS_DIRECTORY_ENDPOINTS` | JSON array of LDAPS endpoint URLs. | `[]` |
| `ATLAS_DIRECTORY_CA_CERTIFICATE_FILE` | Filesystem path to the directory server's CA certificate, read directly by the backend process. | *(unset)* |
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

The backend process reads `.env` itself via its own settings loader, regardless of which script
starts it, and that loader strips matching quotes, so both quoted and unquoted values work.

### Local development, with hot reload

Prerequisites:

- Python 3.12
- uv 0.12.1
- Node.js 24
- pnpm 11.7.0

Unlike `scripts/install`, these scripts run the backend and frontend in the foreground with live
reload, for active development, and default to synthetic mode
(`ATLAS_DATABASE_REQUIRED=false`) unless `.env` points `ATLAS_DATABASE_URL` at a real database.

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

### Updating the pre-built frontend

`frontend/dist/` is committed so `scripts/install` never needs Node.js/npm/pnpm or npm registry
access on the deployment target -- it is the one intentional exception to this repository's
"no build output committed" rule (see `.gitignore`). After any change under `frontend/src/`,
rebuild and commit it:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build
git add dist
```
