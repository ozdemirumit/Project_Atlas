# ADR-098: Bootstrap Identity Handoff Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093,
  ADR-094, ADR-095, ADR-096, ADR-097

## Context

IMP-141 assigned Service Deployment to a dedicated lazy Health workflow and reduced the
transitional operational chunk to 768.43 KB. Identity Handoff is the next state-changing Bootstrap
phase. Its eligibility, human review, mutation, recovery and result presentation remain in
`App.tsx`.

This phase publishes a secret-free Atlas identity-state document. It does not create or modify a
credential, account, directory object, provider, session or token; activate enterprise
authentication; change infrastructure; or invoke AI operations.

## Decision

Atlas will assign the complete Identity Handoff interaction lifecycle to one static lazy Health
feature named `BootstrapIdentityHandoffWorkspace`.

The parent supplies current Bootstrap state, configuration preview, public trust plan, data plan,
service plan, identity plan and authenticated organization scope. The feature owns exact-input
fingerprinting, fail-closed eligibility, review, justification, cancel and confirmation state,
version-bound mutation, stale-review rejection, cache recovery and bounded replay/result
presentation.

The parent retains query, navigation, authentication and authorization ownership. The feature does
not own lease acquisition, plan generation, directory access, credential resolution, account or
provider mutation, Integration Validation, later phases, server validation, idempotency
construction or audit policy.

## Exact Review Binding

One review intent is valid only for the exact fingerprint containing:

- run identity, version, state, current phase, release, profile, plan digest, resume key,
  configuration digest, scope, lease expiry and completed phases;
- completed Service Deployment and prior Identity Handoff identities, states, results, counts,
  digests, target and all service readiness/probe booleans;
- configuration, trust, data and service-plan identities, schemas, states, scopes and digests;
- every service identity, order, dependency, workload identity, endpoint class and bounded runtime
  flag needed to bind the completed service state;
- identity-plan schema, state, result, release, profile, scope, configuration, trust, data,
  service-plan and identity-plan digests;
- target identity, kind and expected state, administrator subject, credential-verifier reference,
  recovery identity and seal requirement, LDAPS provider and pilot subject;
- every mapping identity, directory-group reference and role set; and
- all false credential, directory, provider, account, session/token, infrastructure and AI
  authority flags.

Any change invalidates review. Confirmation compares the recorded fingerprint with current
evidence immediately before calling the existing API client.

## Availability

The workflow is available only when:

- a non-completed run exists, the current actor holds its lease and `phase.identity` is current;
- no identity handoff is running and Service Deployment completed successfully;
- configuration, trust, data, service and identity plans passed and agree with run and scope;
- Service Deployment binds the exact release, profile, configuration, trust, data, service-plan
  and target evidence, with one ready status and three passed probes per planned service;
- the identity plan requires credential replacement and recovery sealing, uses LDAPS and contains
  unique mappings, directory groups and role assignments; and
- the identity plan contains no credential material or mutation authority.

Absent, stale, failed, malformed, mismatched, duplicate, unleased, non-identity or incompletely
probed evidence exposes no action. Existing execution evidence may remain visible without
later-phase authority.

## Mutation And Recovery

Confirmation calls the existing `handoffBootstrapIdentity` client unchanged. The request remains
version-bound and idempotent and sends only validated configuration, trust, data, migration,
service-plan, identity-plan and target bindings plus an empty overlay and reviewed justification.

Success stores bounded returned evidence and refreshes Bootstrap state, invalidation evidence and
the identity plan. Failure clears review intent, refreshes all three sources and requires a new
review. No automatic mutation retry is permitted.

## Presentation

The feature may present secret-free subject, recovery, provider, pilot, mapping and role
references; execution state and result; validation and mapping counts; recovery-seal state; and
sanitized evidence identifiers, dispositions and digest prefixes.

Credential material, verifier values, passwords, directory bind controls, account/provider
mutations, session/token issuance, integration controls, infrastructure controls and AI authority
are forbidden.

## Consequences

- Identity Handoff can evolve and fail independently of the application coordinator.
- Service-readiness binding, exact review and no-real-identity-mutation behavior become directly
  testable.
- The Deployments view loads the workflow only when it owns the current task surface.
- The transitional operational chunk shrinks while server contracts remain unchanged.

## Verification

- Component tests cover exact request, replay/result evidence, cancel, stale review, lease and
  service-probe gates, failure refresh, sensitive exclusion and absence of later authority.
- Existing integration coverage preserves services-before-identity and identity-before-integrations
  order.
- ESLint, both TypeScript projects, full frontend tests and production build pass with a separate
  lazy feature chunk.
- Live desktop/mobile checks cover review/cancel, disabled confirmation, responsive fit and clean
  behavior without executing handoff.

## Follow-Up

Measure the resulting chunks, then define the Integration Validation workflow owner while
preserving exact-input, audit, idempotency, recovery and no-autonomous-execution rules.
