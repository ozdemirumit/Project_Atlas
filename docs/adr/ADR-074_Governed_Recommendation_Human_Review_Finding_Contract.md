# ADR-074: Governed Recommendation Human Review Finding Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, Infrastructure Operations,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-073

## Context

ADR-073 lets the exact assigned technical or service-impact reviewer inspect one immutable,
redacted, bounded plain-text recommendation snapshot while a short-lived browser-bound lease is
active. Presentation records disclosure only. The next stage must preserve accountable human
observations without interpreting them as a decision, approval, priority, remediation order,
workflow request, ITSM record, or operational action.

Reviewer narratives may contain sensitive infrastructure and service-impact information. They
must not become plaintext application records, audit fields, logs, model context, retrieval
content, browser storage, or executable instructions. Atlas therefore needs a trusted finding
recorder boundary and a metadata-only application record.

## Decision

Atlas will implement one immutable track-specific finding packet per exact protected-content
presentation. The same current assignee, browser session and track lease cookie may submit one to
twenty bounded findings before lease expiry. A trusted recorder seals normalized findings into an
encrypted immutable artifact; Atlas persists only lineage, policy, counts and integrity metadata.

### Caller Contract

The caller may provide only:

- the exact presentation canonical digest and signed finding-policy ID and digest;
- one to twenty findings with a policy-allowed category, policy-allowed severity, bounded summary
  and bounded detail;
- a bounded purpose and acknowledgements that evidence was inspected and findings grant no later
  authority;
- idempotency and correlation identifiers.

Recommendation, lease and presentation IDs come from the path. Callers cannot provide identity,
tenant, assignment, track, holder, browser binding, source content, excerpt, option selection,
range, policy catalogs, recorder, artifact location, key, classification, decision, disposition,
correction, approval, workflow, ITSM, command, schedule, execution, deployment or mutation fields.

### Finding Semantics And Track Separation

A finding is an accountable human observation, not a verdict. Severity expresses perceived
importance only and grants no priority or action. Summary and detail are sensitive untrusted text
and never executable instructions.

Technical and service-impact tracks use independent signed category catalogs. Technical findings
may address technical accuracy, evidence conflict, operational safety, recovery feasibility,
implementation assumptions or unknowns. Service-impact findings may address affected services,
interruption estimates, business impact, communication gaps, recovery objectives or dependency
uncertainty. The immutable presentation derives the track; cross-track categories fail closed.

At least one finding is required. A reviewer with no finding creates no empty packet and proceeds
only through a later independent decision contract. Finding existence, absence, category and
severity cannot become an automatic decision.

### Authorization And Source Proof

Before claim creation Atlas revalidates the complete promotion, readiness, request, assignment,
inspection lease and protected-content presentation lineage; all canonical digests and signed
policies; current enterprise human identity with recent hardware MFA; exact tenant and C2
finding-create/C1 source-read scope; salted assignee digest; browser binding; selected track
cookie; lease expiry; and absence of later review, approval, workflow, ITSM or operational
authority. Any missing, changed, expired, transferred or cross-track proof fails before claim and
before finding text crosses the recorder boundary.

### Atomic Claim And Trusted Recorder

Required intent audit succeeds before one immutable source-presentation claim. Claim creation is
the point of no return. Exact replay is allowed only for matching subject, browser, source,
request and idempotency digests and a completed metadata record. Failure after claim remains
claimed and is not automatically retried.

The trusted recorder receives only exact immutable lineage, derived track, inherited governance,
signed limits, packet ID and bounded normalized findings. It validates catalogs and limits,
rejects active payloads and embedded objects, writes one encrypted immutable artifact, computes
content/metadata/lineage/access/retention/encryption/cleanup digests, erases plaintext buffers,
closes channels and returns a signed minimized receipt. Production fails closed without a trusted
recorder. Development may use a deterministic local synthetic recorder with no model, target,
connector, directory, workflow, ITSM or infrastructure access.

### Persistence, Response And Replay

The application record uses state `recommendation_human_review_finding_recorded` and stores exact
source IDs and digests, derived track, salted holder/browser bindings, opaque artifact ID, finding
and byte counts, safe catalog and content digests, recorder/policy identities, timestamps, purpose
and canonical digest. It stores no summary, detail, content, excerpt, identity, cookie, secret,
browser ID, artifact coordinate, key, request digest or idempotency material.

API responses further omit artifact ID and private bindings and use no-store, no-cache, nosniff,
no-referrer and restrictive CSP controls. Audited `GET` returns metadata only after full current
reauthorization. Finding plaintext never appears in responses, persistence, audit, logs, errors,
events, browser storage, model context, vector stores, retrieval indexes or graph records.

### A Finding Grants No Later Authority

Success sets only `human_findings_recorded=true` and the derived technical or service-impact
finding flag. Human review completion, disposition, correction, recommendation approval,
workflow, ITSM, scheduling, execution, deployment and infrastructure mutation remain false.
Later independent contracts may present sealed findings and record accountable decisions; they
cannot treat findings as approval or operational authorization.

### Failure And Audit

Intent audit precedes claim. Claim audit follows claim. Completion audit succeeds after a verified
recorder receipt and before metadata persistence. Every metadata read has a separate event. Audit
contains accountable identity and safe counts/track only, never narratives or secrets.
Authorization, audit, recorder, integrity, encryption, persistence, immutable-write or cleanup
uncertainty fails closed without a partial receipt.

## Consequences

### Positive

- Technical and service-impact observations become durable accountable evidence without becoming
  decisions.
- Sensitive narratives remain outside application persistence, telemetry and model context.
- Exact-assignee, browser, track and immutable recommendation lineage remain enforceable.

### Costs

- Production requires a trusted encrypted finding recorder and protected artifact store.
- Redisplay and decisions require later separately governed contracts.
- A claimed uncertain submission requires governed recovery rather than automatic retry.

## Rejected Alternatives

### Store Narratives In PostgreSQL

Rejected because this creates unmanaged plaintext copies of sensitive operational observations.

### Use An LLM To Rewrite Findings Before Recording

Rejected because human observations need accountable preservation, not model mediation.

### Treat Severity Or Category As Disposition

Rejected because neither grants acceptance, rejection, priority, remediation or approval.

### Accept Findings After Lease Expiry

Rejected because findings must remain bound to current evidence access and accountable identity.

## Follow-Up

Later contracts cover protected finding presentation, independent track decisions, correction,
final recommendation disposition, workflow/ITSM handoff and any separately approved operation.
