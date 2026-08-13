# ADR-133: Optional Policy-Based Step-Up Authentication

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Owner, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ADR-132 |

## Context

Earlier Atlas designs treated multi-factor or hardware-backed authentication as a fixed prerequisite
for many protected workflows. The product owner has decided that Atlas does not require an
Atlas-owned MFA feature and that the absence of an MFA claim must not prevent normal product use.
Enterprise identity providers may still perform MFA or expose authentication-assurance claims, but
Atlas must not assume that every deployment enables them.

## Decision

Atlas will not implement, enroll, issue or verify its own OTP, authenticator application, hardware
token or other MFA factor. Authentication remains the responsibility of the configured enterprise
identity provider or the governed local-development/recovery mechanism.

MFA and hardware-backed assurance are optional policy inputs. A deployment may configure step-up
authentication for selected operations when its identity provider supports it, but the default Atlas
policy must not require MFA and the product must remain functional without an MFA claim.

Authorization decisions will rely on the authenticated subject, tenant and scope boundaries, RBAC,
explicit acknowledgement, optimistic concurrency, idempotency, immutable audit and, for sensitive
decisions, separation of duties or two-person approval. Optional step-up may strengthen these
controls but cannot replace them.

## Required Behavior

- Login works with an approved single-factor enterprise identity when the deployment permits it.
- Missing MFA or hardware-backed assurance does not by itself hide or disable inventory, connector,
  MCP Builder, knowledge, investigation, reporting or chat functions.
- Policies express step-up as optional deployment configuration, never as a hard-coded product
  prerequisite.
- A policy that requests step-up must identify the affected operation, acceptable assurance values,
  freshness window and user-facing recovery path.
- When a configured identity provider cannot satisfy an enabled step-up policy, Atlas denies only
  that policy-governed operation and explains the reason without claiming that Atlas provides MFA.
- Existing RBAC, target scope, acknowledgement, approval, audit, CSRF and replay protections remain
  mandatory regardless of authentication assurance.

## Prohibited Behavior

- Atlas-hosted OTP seeds, recovery codes, factor enrollment or authenticator management
- A global `multi_factor` or `hardware_backed` check embedded directly in product services or UI
- Describing MFA as mandatory for Atlas installation, login or ordinary operation
- Treating a high assurance claim as authorization, approval or permission
- Creating an Active Directory management capability to configure or inspect MFA

## Consequences

- Existing fixed MFA gates must migrate to named, configurable step-up policies or be removed when
  RBAC and workflow governance already provide the intended control.
- Identity assurance remains available in normalized subject context and audit records for customers
  that use it.
- Development and test identities can exercise the complete authorized product surface without
  fabricating an MFA claim.
- Security-sensitive workflows continue to fail closed on authorization, scope, acknowledgement,
  approval and audit failures.

## Validation

- Static checks reject new hard-coded MFA or hardware-assurance gates outside the authentication and
  policy adapters.
- API and UI tests prove authorized single-factor users are not blocked solely by assurance level.
- Optional step-up policy tests cover satisfied, unsatisfied, unavailable-provider and stale-claim
  outcomes.
- Regression tests preserve RBAC, separation-of-duty, acknowledgement, audit and target-scope
  controls after each migration.
