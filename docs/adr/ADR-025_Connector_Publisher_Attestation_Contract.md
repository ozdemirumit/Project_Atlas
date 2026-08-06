# ADR-025: Connector Publisher Attestation Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-06 |
| Owners | MCP Platform Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-047, ADR-009, ADR-023, ADR-024 |

## Context

ADR-024 records an accountable human decision for one exact validated connector package. Approval
sets only `connector_approved=true` and `eligible_for_publisher_governance=true`; it neither proves
who published the package nor authorizes signing, publication, installation, or execution.

Atlas must independently bind a publisher's stable organizational identity, ownership and support
responsibility, release provenance, and supplied evidence to the exact approved package. A manifest
string, package uploader, human approval, domain name, email address, or successful signature check
alone is not publisher attestation.

## Decision

Atlas will implement publisher attestation as two immutable records:

1. a publisher claim snapshot issued through a governed source and bound to one package digest; and
2. one independent verification report that binds the exact still-valid ADR-024 approval, claim,
   package, signed attestation-policy snapshot, verifier, and deterministic evidence digest.

The first profile records one terminal `verified` or `rejected` verification. Missing evidence,
policy incompatibility, stale approval or claim, identity mismatch, actor overlap, tampering, or
infrastructure failure fails closed. Historical records are never edited.

## Publisher Claim Snapshot

The claim source supplies an immutable, signed, verified, unexpired snapshot containing only:

- stable claim, publisher, organization, and environment identity;
- exact package, connector, release, and source-provenance digests;
- publisher legal/display name, ownership statement, support contact reference, and support expiry;
- issuer identity, issue and expiry time, schema/version, signature verification state, and digest;
- explicit declarations that the publisher owns or is authorized to distribute the connector,
  accepts support responsibility, and grants no Atlas runtime or infrastructure authority.

Raw credentials, private keys, package bytes, target coordinates, filesystem paths, secrets,
commands, payloads, model context, and unrestricted contact data are excluded. The API caller
references an existing claim and cannot author, edit, sign, or override it.

## Attestation Policy

Platform policy selects one immutable, signed, verified, unexpired, tenant-scoped snapshot that
fixes accepted approval and claim schemas, maximum evidence age, minimum identity assurance,
required publisher assertions, allowed issuer trust domains, support-validity minimum, actor
separation, canonicalization, and report schema.

Customer policy may strengthen but cannot weaken exact binding, independent verification,
separation, no-authority, audit-before-persist, or fail-closed behavior.

## Independent Verification

Only an exact-tenant, multi-factor human with dedicated verification permission may create or read
a report. The verifier must be distinct from:

- the package-approval requester and approver;
- every acquisition, review, validation, analysis, runner, lab, plan-approval, and credential-
  custody actor in the exact package lineage;
- the approval-policy signer, claim issuer, attestation-policy signer, and publisher identity.

AI, workload, service, shared, anonymous, wrong-scope, disabled, insufficient-assurance, or
ineligible identities fail closed without record discovery.

Verification independently reloads and checks the complete approval lineage, exact package and
digest binding, current approval validity, claim signature and freshness, publisher and release
identity, provenance digest, ownership and support assertions, issuer trust, policy signature and
scope, actor separation, and deterministic evidence digest. The caller cannot choose checks,
waive evidence, lower risk, select an outcome, or provide a lifecycle state.

## Request And Result Contract

The create request accepts only exact approval request ID/digest, package digest, publisher claim
ID/digest, attestation-policy ID/digest, a bounded verification purpose, no-authority
acknowledgement, idempotency key, and correlation ID.

The report exposes safe identity and digest references, stable check results, timestamps, outcome,
reason codes, and lifecycle flags. It excludes raw evidence and sensitive source material.
Requests and reports are immutable, one-to-one with the exact approval and claim in the first
profile, deterministic, idempotent, concurrency-safe, audit-before-persist, and behaviorally
equivalent in memory and PostgreSQL.

## Lifecycle Effect

A `verified` report sets only:

- `publisher_attested=true`; and
- `eligible_for_package_signing_governance=true`.

A `rejected` report sets neither flag and remains promotion-blocked. Every outcome keeps
`package_signed`, `connector_registered`, `connector_installed`, `connector_enabled`,
`target_configured`, `credentials_resolved`, `runtime_trust_granted`, `execution_authorized`,
`deployment_approved`, and `infrastructure_mutation_performed` false.

Verification produces no signing key, signature, registry entry, installation package, runtime
token, target reference, credential handle, command, payload, deployment approval, or mutation
authority. Package signing and registry publication require later independent ADRs and controls.

## API And Web Contract

Strict create/read APIs require dedicated default-deny RBAC, browser sessions, CSRF on mutation,
exact tenant scope, MFA human identity, correlation, acknowledgement, bounded schemas, safe errors,
non-disclosing lookup, and `no-store` responses.

The web view presents exact approval, package, publisher claim, policy, verifier, checks, outcome,
expiry, and no-authority scope. It has no signing, registry, install, enable, target, secret,
execution, or deployment control and uses no persuasive or urgency language.

## Consequences

- Publisher identity and provenance become independently verifiable evidence rather than trusted
  manifest text.
- Human package approval cannot self-attest a publisher or skip separation of duties.
- Exact digest binding prevents publisher or package substitution after approval.
- Signing, publication, installation, enablement, and runtime trust remain separate stages.

## Rejected Alternatives

- Trust the manifest publisher field: rejected because it is self-asserted package content.
- Treat package approval as publisher attestation: rejected because risk acceptance is not identity
  or provenance verification.
- Let the publisher or claim issuer verify the claim: rejected because assertion and verification
  must remain independent.
- Sign or publish immediately after verification: rejected because attestation is evidence for a
  later signing-governance boundary, not signing or registry authority.

## Validation

- Exact approval, decision, package, claim, policy, tenant, environment, publisher, release, and
  provenance binding tests
- Approval/claim/policy freshness, signature, assertion, issuer-trust, support-validity, tamper,
  replay, conflict, and fail-closed tests
- Verifier separation from every upstream, approval, claim, publisher, and policy actor
- Immutable, idempotent, concurrent, audit-before-persist, memory/PostgreSQL, and Alembic-head tests
- Proof that no result signs, publishes, registers, installs, configures, enables, accesses targets
  or secrets, executes, deploys, or mutates infrastructure
- Strict API, CSRF, `no-store`, minimized-response, web, desktop, 390-pixel mobile, browser-log,
  live HTTP, and GitHub CI validation
