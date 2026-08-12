# ADR-122: Connector Upgrade Onboarding-Policy Provenance Remediation Guidance

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ADR-119, ADR-120, ADR-121 |

## Context

ADR-121 exposes five exact-scope provenance checks and stable failure reasons without weakening
readiness. The v1 diagnostic identifies what failed, but does not structure who owns the missing
evidence or which safe evidence-producing step is required. Operators would otherwise have to infer
ownership from internal reason codes.

Production trust-store, verifier, KMS/HSM and key-custody choices remain deployment decisions. Atlas
must not invent those inputs or turn remediation guidance into a mutation interface.

## Decision

The provenance diagnostic v2 will attach four server-owned fields to every blocked or unavailable
check: accountable owner-role ID, required-evidence ID, safe next-action ID and whether an external
deployment input is required. Verified checks carry no remediation metadata.

A closed, deterministic reason-code mapping produces the fields. Unknown mappings fail closed before
the diagnostic is returned. The fields are stable identifiers rather than caller-controlled prose,
are included in the canonical diagnostic digest and cannot be overridden by the request.

Prerequisite-unavailable checks point to a coordination role and the earlier provenance check; they
do not duplicate external provider requirements. The first directly failing check identifies the
external evidence owner when external input is required.

## Safety Boundary

Remediation guidance is read-only decision support. It does not authorize policy publication,
attestation issuance, trust-store or verifier configuration, key management, provider selection,
receipt signing, upgrade approval, execution or infrastructure mutation. The existing exact-scope
C1 permission, required audit and no-store response remain unchanged.

## Consequences

- Operators receive accountable ownership and evidence requirements without credentials, endpoints,
  signatures, key material or provider parameters.
- Frontend labels are derived from stable IDs and expose no execution control.
- Production remains unavailable until the named external owners supply reviewed deployment inputs.
- v1 clients must adopt the exact v2 schema because the API intentionally rejects partial contracts.

## Validation

- Complete mapping coverage and fail-closed unknown/inconsistent mapping tests
- Verified-empty and blocked-required remediation domain and API schema tests
- Frontend exact-contract and read-only ownership presentation tests
- Complete backend/frontend regression, one Alembic head, production build and responsive live UI
