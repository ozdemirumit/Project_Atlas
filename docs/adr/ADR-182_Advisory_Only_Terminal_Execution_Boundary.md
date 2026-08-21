# ADR-182: Advisory-Only Terminal Execution Boundary

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-21 |
| Owners | Product Owner, Security Architecture, Workflow Architecture |
| Related | ATLAS-003, ATLAS-014, ATLAS-023, ATLAS-025, ATLAS-032, ATLAS-037, ATLAS-047, ADR-160 through ADR-181 |

## Context

ADR-160 through ADR-181 established narrowly separated, fail-closed evidence and authorization
boundaries while repeatedly withholding runtime resume, dispatch, execution and infrastructure
mutation authority. ADR-181 intentionally deferred consumption of its non-bearer process-resume
request lease to another decision.

The Product Owner has now selected Atlas's terminal product posture: Atlas remains an advisory-only
decision-support platform. It will analyze, explain, report and recommend, but it will not resume
processes or execute infrastructure-changing operations. Leaving the final boundary merely
unimplemented would make the safety property accidental and vulnerable to later composition or
configuration drift.

## Decision

Atlas adopts the immutable code-owned platform mode `advisory_only`. Under this mode:

- operational execution is disabled;
- protected runtime process-resume consumption is disabled;
- operational dispatch is disabled;
- infrastructure mutation is disabled; and
- AI execution authority is always false.

No identity, role, approval, policy outcome, lease, workflow state, connector capability, MCP tool,
AI output, environment variable or deployment configuration can enable those authorities. Human
approval records a decision and may support an external manually governed change process, but it
does not become Atlas execution authority.

The API composition root validates this boundary before application startup. Registration of any
operational execution component fails closed. Attempts to enable execution, process-resume
consumption, operational dispatch or infrastructure mutation through reserved environment flags
also fail startup. The absence of an executor is therefore an enforced contract rather than an
unfinished feature.

### Prior Runtime Lineage

ADR-160 through ADR-181 remain immutable historical and security-boundary records. Their data and
minimized read-only projections may remain available for audit, compatibility and verification.
No artifact in that lineage is bearer authority, and ADR-181's lease has no Atlas consumer. This
decision closes the deferred resume-consumption path and prohibits any successor implementation
that would resume, dispatch or execute the protected process.

### API And User Interface

The existing platform-status response publishes a minimized, code-owned advisory-only posture with
all authority fields false and a deterministic contract digest. The response is `no-store`.

The frontend validates the complete posture and rejects the response if any operational authority
is true, the mode changes, or the contract identity/digest shape is invalid. The authenticated
workspace displays a read-only `Advisory only` execution-boundary indicator. It exposes no toggle,
approval, resume, dispatch, execute or mutation control and requires no MFA, step-up or second
browser session after normal username/password authentication.

### Identity And Extension Boundaries

Active Directory and LDAP remain authentication-only. Atlas introduces no Active Directory
management capability or MCP. AI agents, MCP connectors, workflows and plugins cannot register or
invoke an operational execution service.

## Consequences

- Atlas can continue diagnostics, health checks, analysis, evidence collection, impact assessment,
  reporting, recommendations and rollback-plan preparation within approved read-only boundaries.
- Approved recommendations may be exported or handed to existing enterprise processes, but any
  real change occurs outside Atlas under the organization's own controls.
- The runtime authorization lineage no longer expands toward a process-resume consumer.
- A future product change would require an explicit Product Owner decision, a superseding governed
  architecture baseline and removal or replacement of the code-owned startup sentinel. It cannot
  be activated by configuration alone.

## Verification

- Domain tests prove every operational authority is false and the contract digest is stable.
- Composition tests prove operational component registration and reserved enablement flags fail
  closed before application startup.
- API tests prove the read-only posture and `no-store` response headers.
- Frontend tests prove strict rejection of every true authority field and read-only rendering with
  no operational controls.
