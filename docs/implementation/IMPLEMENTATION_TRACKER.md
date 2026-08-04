# Project Atlas Implementation Tracker

## Current Focus

| Field | Value |
| --- | --- |
| Task ID | ATLAS-IMP-020 |
| Title | Administrative identity access governance |
| Status | In Progress |
| Branch | `agent/administrative-identity-access-governance` |
| Pull Request | Pending |
| Governing Documents | ATLAS-003, ATLAS-016, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-056 |
| Last Updated | 2026-08-04 |
| Next Action | Implement exact-scope administrative identity inventory and revocation, complete local and live validation, and open the pull request |

### ATLAS-IMP-020 Acceptance Criteria

- Dedicated administrative identity permissions and a Security Administrator role apply only to
  authenticated human enterprise identities within exact organization, environment, and site scope;
  development and non-human identities cannot use the administrative surface.
- A bounded, filtered, deterministic inventory exposes secret-free lifecycle metadata for active
  browser sessions and personal API credentials belonging to other subjects in the authorized scope.
- Exact session and personal API credential revocation require current administrative RBAC, a
  browser session, CSRF, reason, correlation, idempotency, and optimistic concurrency. Bearer tokens
  cannot invoke administrative mutation endpoints.
- Missing, foreign, hidden, inactive, stale, and concurrently changed targets behave equivalently
  without leaking existence, counts, or unauthorized subject metadata and cannot resurrect state.
- The current administrator browser session cannot be revoked through the administrative endpoint;
  revoking another subject's session or credential leaves the administrator session active.
- Required inventory, allow, deny, and revoke audit events fail closed and include actor, target
  subject, safe lifecycle metadata, reason, correlation, and idempotency evidence without secrets.
- A searchable governance view is discovered only after the backend confirms administrative access.
  Ordinary operators treat a 403 discovery response as an unavailable capability rather than a
  disruptive application error.
- Tests cover role and identity-class boundaries, exact scope, filtering and bounds, secret
  redaction, hidden targets, current-session protection, CSRF, bearer denial, idempotency,
  concurrency, audit failure, revocation propagation, and responsive UI.
- Identity-disablement fan-out, OIDC/SAML setup, service or workload credentials, break-glass,
  secret recovery or rotation, and infrastructure-changing grants remain outside this slice.

### ATLAS-IMP-020 Validation Evidence

- Pending implementation and validation.

### ATLAS-IMP-019 Acceptance Criteria

- Only an authenticated human using a CSRF-protected browser session and an exact C2 self-service
  credential permission can create or revoke a personal API credential; bearer credentials cannot
  create, rotate, broaden, or revoke credentials.
- Creation requires a bounded display name, explicit purpose, five-to-sixty-minute lifetime, and one
  or more server-catalogued read-only grants. Every requested permission and exact scope is authorized
  against the human's current RBAC before issuance, so a credential cannot elevate its owner.
- The raw prefixed token is generated with cryptographic randomness, returned exactly once over a
  `Cache-Control: no-store` response, excluded from logs and representations, and never persisted;
  only a SHA-256 digest is retained and constant-time comparison protects validation.
- Bearer authentication accepts only the dedicated token format, rejects ambiguous cookie-plus-header
  authentication, expiry, revocation, malformed input, and unsafe HTTP methods, and never falls back
  to a weaker provider path for an invalid bearer token.
- Every token-backed authorization is conjunctive: both the credential's exact permission and scope
  grant and the subject's current role assignment must allow the request. Grant mismatch is audited
  as a denied authorization without revealing hidden resources.
- Self-service inventory is bounded and newest-first, exposes metadata, exact grants, last use, expiry,
  lifecycle state, and a stable credential ID only, and never returns token material or its digest.
- Revocation is subject-bound, idempotently fail-closed for missing, foreign, expired, or already
  revoked records, uses optimistic version checks, and prevents subsequent authentication without
  affecting browser sessions.
- Issuance, successful authentication, rejected authentication, inventory, expiry, revocation, RBAC
  denial, and credential-grant denial produce required secret-safe audit records; audit failure blocks
  protected disclosure or a successful lifecycle mutation.
- The web settings experience can create a bounded read-only token, shows its raw value once with a
  clear dismissal boundary, lists lifecycle metadata and grants, and provides explicit revoke controls
  without storing the raw token in browser storage.
- Tests cover one-time disclosure, digest-only persistence, randomness, lifetime and active-count
  bounds, exact grant/RBAC conjunction, bearer reads, unsafe-method denial, ambiguity, expiry,
  revocation, optimistic concurrency, CSRF, audit failure, redaction, and responsive UI. Service
  accounts, workload identities, refresh tokens, rotation, delegated tokens, administrator-wide
  management, and infrastructure-changing permissions remain outside this slice.

### ATLAS-IMP-019 Validation Evidence

- A dedicated digest-only credential repository and service enforce cryptographic token generation,
  five-to-sixty-minute lifetime, bounded active count, deterministic grants, subject isolation,
  optimistic updates, expiry, and revocation. Raw token material is returned once and excluded from
  persisted records, representations, audit events, and inventory responses.
- Bearer authentication recognizes only the dedicated `atlas_pat_` format, never falls through to an
  identity provider, denies unsafe methods, rejects cookie ambiguity, and attaches an exact grant
  restriction to the authenticated subject. Every authorization still re-evaluates current RBAC and
  denies either a missing token grant or inactive/missing role assignment.
- Credential creation, inventory, and revocation require a CSRF-protected browser session plus exact
  self-service C0/C2 permissions. Requested grants come from a server catalogue and are independently
  authorized before issuance; management is unavailable to bearer credentials.
- API credential lifecycle and bearer responses use `Cache-Control: no-store`. Required issuance,
  authentication, inventory, expiry, revocation, denial, and authorization audit failures block the
  protected response or successful mutation.
- Backend Ruff and strict type checks passed across 201 source and test files. The complete backend
  suite passed with 213 tests, including ten focused API credential scenarios for one-time disclosure,
  digest-only storage, exact grant and RBAC conjunction, unsafe methods, ambiguity, expiry, revocation,
  races, subject isolation, limits, CSRF, redaction, and audit failure.
- Frontend ESLint and TypeScript checks passed, five Vitest scenarios passed across two files, and the
  production Vite bundle built successfully. The integrated browser-session test verifies CSRF-backed
  creation and revocation, grant selection, one-time display, and dismissal from UI state.
- GitHub Actions passed on the review head: the backend job completed successfully in 27 seconds and
  the frontend job completed successfully in 40 seconds.
- A fresh live enterprise-style browser session created a real token, used it without a cookie to read
  the exact storage scope with HTTP 200, revoked it, and confirmed the same bearer then failed with
  HTTP 401. The raw token disappeared after explicit dismissal.
- Desktop 1440x900 and mobile 390x844 views were visually inspected. The API access form, grant
  checkboxes, lifecycle row, and revoke state remained readable with no page-level horizontal overflow
  or incoherent overlap.
- Service accounts, workload identities, refresh tokens, rotation, delegated credentials,
  administrator-wide management, and infrastructure-changing grants remain intentionally outside this
  slice.

### ATLAS-IMP-018 Acceptance Criteria

- An approval request can be created only from an authorized, persisted recommendation ID, exact
  version, target, and one viable option; blocked, missing, stale, expired, or substituted sources
  fail closed without disclosing hidden resources.
- The submitted packet is immutable and versioned. Deterministic canonical JSON and a SHA-256 digest
  bind requester, purpose, source versions, option, target and scope, evidence references, ordered
  plan, policy constraints, risk, impact, duration, interruption, recovery, and expiry.
- Packet output visibly preserves facts, assumptions, unknowns, evidence, blast-radius limits,
  service-impact uncertainty, preconditions, verification, stop conditions, and recovery gaps; no
  missing field is rewritten as a safe or confirmed claim.
- The first slice supports one human-review stage with pending, approved, rejected, needs-evidence,
  deferred, and expired outcomes. Historical decisions are append-only and an approved packet still
  has `execution_authorized=false` and produces no executable credential or connector invocation.
- Decision-time authorization requires a dedicated exact-scope permission, a human identity, current
  eligible role and scope, minimum assurance, and requester-reviewer separation. AI, service,
  connector, shared, unassigned, and self-review identities cannot decide.
- Decision mutations require CSRF for browser sessions, a bounded idempotency key, and the expected
  request version. Replays return the original decision, key substitution or stale concurrency fails
  closed, and the first valid terminal or review-required transition is never overwritten.
- Expiry is evaluated before every read and decision. Material source or digest mismatch invalidates
  decision eligibility; approval cannot supply missing authentication, RBAC, policy, evidence,
  freshness, or future execution authority.
- Request creation, read, eligibility denial, decision, replay, conflict, and expiry are audited with
  stable IDs and no credential material. Required authorization or audit failure blocks protected
  disclosure or a successful mutation response.
- The web workspace presents the exact packet, requester, target, evidence and uncertainty, risk,
  impact, interruption, duration, recovery, expiry, digest, decision history, and an equally visible
  set of approve, reject, needs-evidence, and defer controls only when the current human is eligible.
- Tests cover canonical digest stability and substitution, exact RBAC and scope, non-human and
  self-review denial, assurance, expiry, optimistic concurrency, idempotency, CSRF, audit failure,
  non-execution invariants, secret-safe responses, and responsive UI. Multi-stage quorum, external
  ITSM decisions, notifications, emergency approval, revocation, handoff tokens, and infrastructure
  execution remain outside this slice.

### ATLAS-IMP-018 Validation Evidence

- The approval service binds one exact viable recommendation option to a canonical, versioned packet
  and SHA-256 digest containing the visible evidence, assumptions, unknowns, plan, risk, impact,
  interruption, recovery, policy, scope, requester, source versions, and expiry.
- Create, read, and decision boundaries enforce exact-scope authorization, source and digest
  revalidation, expiry, optimistic versioning, bounded idempotency, human identity, assurance, and
  requester-reviewer separation. Required audit failure blocks disclosure or mutation.
- Approval, rejection, needs-evidence, defer, expiry, replay, conflict, tamper, substitution, CSRF,
  self-review, non-human review, weak assurance, and audit-failure paths are covered without producing
  an execution credential or connector call; every record retains `execution_authorized=false`.
- Backend Ruff and strict type checks passed; the complete backend suite passed with 203 tests,
  including 11 focused approval API scenarios.
- Frontend ESLint and TypeScript checks passed, five Vitest scenarios passed across two files, and the
  production Vite bundle built successfully.
- The live same-origin browser flow created a real recommendation-bound packet and visibly preserved
  the digest, requester, evidence, uncertainty, risk, impact, interruption, recovery, expiry, ordered
  plan, non-execution boundary, and separated-reviewer requirement.
- Desktop 1440x900 and mobile 390x844 views were visually inspected. The approval workspace remained
  readable without overlap; page-level horizontal scrolling was removed while bounded data tables
  retained their own controlled overflow.
- Multi-stage quorum, external ITSM decisions, notifications, emergency approval, revocation, handoff
  tokens, and infrastructure execution remain intentionally outside this slice.

### ATLAS-IMP-017 Acceptance Criteria

- A dedicated session-inventory permission and exact identity-session scope are evaluated by the
  existing authorization service before any inventory metadata is returned.
- Authenticated users can list only sessions whose normalized subject ID exactly matches their own;
  query input cannot select another subject and counts do not reveal hidden sessions.
- Inventory records expose stable session ID, lifecycle state, credential kind, creation, activity,
  expiry, and current-session marker only; token and CSRF values or digests never leave the service.
- Results are bounded, deterministically newest-first, and explicitly report truncation; inactive
  records remain distinguishable without extending or reactivating their lifetime.
- A separate self-revocation permission is required to revoke a selected own session. Unknown,
  foreign, already terminated, stale, and concurrently changed targets fail closed without
  disclosing another subject or resurrecting state.
- Cookie-authenticated revocation requires CSRF through the shared request boundary. Revoking the
  current session clears both browser cookies and removes protected client state; revoking another
  own session leaves the current session active.
- Inventory reads and successful or denied revocations are audited with stable IDs and no credential
  material; required authorization or audit failure blocks disclosure or successful response.
- The web workspace provides a compact session-management view with current-session status, expiry,
  last activity, and an explicit revoke control for eligible sessions, including empty, loading,
  error, and success states.
- Tests cover exact RBAC and subject isolation, bounded ordering, secret redaction, current versus
  other-session revocation, CSRF, cookie clearing, concurrency, audit failure, and responsive UI.
- Administrator-wide inventory/revocation, identity disablement fan-out, API-token issuance,
  approval, and infrastructure execution remain outside this slice.

### ATLAS-IMP-017 Validation Evidence

- Dedicated exact-scope `session.self.read` and `session.self.revoke` authorization precedes every
  inventory or selected-session operation; subject selection is not accepted from request input.
- The bounded newest-first inventory exposes only lifecycle metadata and an explicit current marker,
  reports truncation, normalizes expired records without reactivation, emits a required audit event,
  and returns `Cache-Control: no-store`.
- Selected self-revocation uses optimistic version checks, hides foreign, missing, and inactive
  targets behind the same response, requires the shared cookie CSRF boundary, and clears both cookies
  only when the selected session is current.
- Backend Ruff and strict type checks passed; the full backend suite passed with 192 tests, including
  29 browser-session scenarios covering exact RBAC, subject isolation, ordering, redaction, CSRF,
  current and other-session revocation, expiry, races, and required audit failure.
- Frontend ESLint and TypeScript checks passed, four Vitest scenarios passed across two files, and the
  production Vite bundle built successfully.
- The web workspace displays current, active, and revoked sessions with bounded metadata and explicit
  revoke controls. Integrated UI tests verify inventory loading and CSRF-backed other-session revoke
  while preserving the established login and logout lifecycle.
- A fresh live API returned the bounded inventory contract. Desktop and 390-pixel mobile views were
  visually inspected with no horizontal overflow, child overlap, or browser console warnings/errors.
- Administrator-wide revocation, real directory-session validation, API-token issuance, approval,
  and infrastructure execution remain intentionally outside this slice.

### ATLAS-IMP-016 Acceptance Criteria

- The web client presents a focused login form only after the identity boundary returns an
  authentication-required response; development identity and already-authenticated sessions enter
  the operations workspace without a second client-side identity path.
- Credentials are submitted only to the same-origin session endpoint over the existing provider
  boundary, are never retained after the request, and never enter query strings, logs, browser
  storage, response JSON, UI diagnostics, or model context.
- Successful login sets the existing opaque HTTP-only session cookie plus a separate non-HTTP-only,
  SameSite Strict, Secure-in-production CSRF cookie whose path permits the web client to read it;
  neither raw value is stored server-side.
- A single frontend API client sends same-origin credentials and copies the CSRF cookie into the
  configured header for every unsafe API request; safe requests do not add the header and no feature
  API can silently bypass the shared client.
- Page reload and a second same-origin browser tab retain mutation capability without exposing the
  session credential or weakening CSRF validation.
- Logout requires the cookie-authenticated CSRF check, revokes the server-side session, clears both
  browser cookies with matching attributes, removes protected client state, and returns to login.
- Invalid credentials, validation errors, unavailable identity providers, expired sessions, missing
  CSRF, and logout failures produce bounded user feedback without account discovery or secret echo.
- Authentication success does not grant roles or scopes; every post-login API call continues through
  existing exact RBAC, policy, audit, and capability controls.
- Tests cover login rendering, credential submission, cookie attributes, reload-safe CSRF forwarding,
  safe-request behavior, invalid login, logout and cookie clearing, protected-state removal, and the
  unchanged direct-development-identity path.
- Session inventory, administrator revocation, API-token issuance, approval, and infrastructure
  execution remain outside this slice.

### ATLAS-IMP-016 Validation Evidence

- Backend Ruff check and format verification passed across 185 source and test files.
- Strict backend type checking passed across all 185 source and test files.
- Full backend test suite passed: 185 tests; browser-session integration now verifies separate
  HTTP-only session and readable CSRF cookies, production Secure attributes, matching paths, and
  deterministic clearing of both cookies on logout.
- Frontend TypeScript and ESLint passed, four Vitest scenarios passed across two test files, and the
  production Vite bundle built successfully.
- The shared frontend API client is the only raw fetch boundary, always uses same-origin credentials,
  adds CSRF only to unsafe methods, and rejects cross-origin requests before credential material can
  be attached.
- Integrated web tests covered authentication-required rendering, credential submission, password
  state removal, LDAP-normalized identity entry, protected workspace loading, CSRF-backed logout,
  return to login, and the unchanged direct development-identity workspace.
- A fresh live API with no enabled provider failed closed and drove the live login screen. Desktop
  and 390-pixel mobile views were visually inspected with no horizontal overflow, overlap, or browser
  console warnings/errors.
- Real enterprise LDAPS login was not attempted because no customer directory endpoint, trust bundle,
  or test account is configured; successful provider behavior remains covered at the full FastAPI
  integration boundary with a deterministic injected provider.
- GitHub quality gates passed on the review-linked tracker commit: backend in 24 seconds and
  frontend in 39 seconds.

### ATLAS-IMP-015 Acceptance Criteria

- Browser login authenticates through the existing identity-provider port, then creates an opaque
  session without storing the raw session or CSRF credential server-side.
- Session records retain a stable session ID, credential digests, normalized subject snapshot,
  creation and activity times, absolute and idle expiry, lifecycle state, and revocation reason.
- Session cookies are HTTP-only, SameSite Strict, path-bounded, Secure in production, and cleared on
  logout; credential values never appear in response JSON, audit, logs, repr, URLs, or model context.
- Unsafe cookie-authenticated requests require a matching CSRF credential using constant-time digest
  comparison; safe requests, direct development identity, and non-cookie authentication do not gain
  or bypass session authority.
- Expired, idle, revoked, missing, malformed, ambiguous cookie-plus-Authorization, and unknown
  sessions fail closed with generic errors and cannot extend their own lifetime.
- Login rotates session identity, enforces absolute/idle timeout bounds and a per-subject concurrent
  session limit, while logout deterministically revokes the current session.
- Session creation, expiry, denial, and revocation are audited without raw credentials; required
  authentication and creation audit failures block session issuance.
- Existing RBAC evaluates the normalized session subject on every request; session creation never
  grants a role, assignment, scope, approval, policy outcome, or infrastructure authority.
- API-token domain and repository boundaries remain distinct from browser sessions; external token
  issuance stays disabled until permission-scope enforcement is implemented and tested.
- Configuration enforces secure production cookies and bounded timeout/session limits; browser
  security cannot be weakened by environment input below platform minimums.
- Tests cover creation, cookie flags, CSRF, safe reads, logout, expiry, idle timeout, concurrency,
  ambiguity, unknown credentials, audit failure, secret redaction, and authentication/RBAC separation.
- Approval workflow and infrastructure-changing execution remain outside this slice.

### ATLAS-IMP-015 Validation Evidence

- Backend Ruff check and format verification passed across 185 source and test files.
- Strict backend type checking passed across all 185 source and test files.
- Full backend test suite passed: 185 tests, including 22 browser-session tests for opaque
  credential handling, cookie attributes, CSRF enforcement, safe reads, logout and revocation,
  absolute and idle expiry, malformed and ambiguous authentication, exact RBAC separation,
  configuration bounds, concurrent-session limits, required-audit failure, digest-only storage,
  secret-safe validation errors, and stale-update protection against revocation races.
- Session state changes use optimistic version checks, so a concurrent request cannot overwrite and
  resurrect a revoked or expired session; concurrent creation is serialized before enforcing the
  per-subject limit.
- Frontend TypeScript, ESLint, integrated user-flow test, and production build all passed without a
  frontend contract change in this backend security foundation.
- A fresh live API process exposed the new endpoint and failed closed when no identity provider was
  enabled: invalid login returned a generic 401 and emitted neither a cookie nor CSRF credential.
- Successful cookie creation and authenticated safe/unsafe request behavior were exercised through
  the full FastAPI integration boundary using an injected deterministic identity-provider adapter.
- Real enterprise directory login was not attempted because no customer LDAPS endpoint, trust
  bundle, or test account is configured; that environment-bound validation remains outstanding.
- External API-token issuance remains disabled; only its distinct credential-kind domain boundary
  exists until exact token permission and scope enforcement is implemented.
- GitHub quality gates passed on the review-linked tracker commit: backend in 27 seconds and
  frontend in 38 seconds.

### ATLAS-IMP-014 Acceptance Criteria

- The enterprise directory provider implements the existing identity-provider port and produces the
  same normalized subject contract used by development identity; replacing the adapter does not
  bypass authentication, RBAC, policy, approval, or audit boundaries.
- Production-capable directory endpoints are versioned and `ldaps://` only, require CA-backed
  certificate and hostname validation, use bounded connection and response timeouts, and never
  downgrade to plain LDAP or disabled certificate verification.
- Basic credentials are accepted only for the directory provider, decoded with strict bounds, used
  only for the bind operation, excluded from representations and audit records, and never retained,
  queued, reported, or sent to an LLM.
- User principals and search filters are constructed from validated usernames and escaped values;
  ambiguous, duplicate, missing, malformed, oversized, or control-character attributes fail closed.
- Directory endpoints use deterministic bounded failover for provider unavailability; rejected
  credentials do not fan out across endpoints and provider outages never become authenticated
  identities.
- Stable internal subject and group identifiers are derived deterministically without exposing raw
  directory object identifiers or distinguished names in durable Atlas identifiers.
- Directory groups grant no authority by themselves. Only explicit, versioned allowlist mappings can
  add Atlas group and role identifiers, and existing exact-scope assignments remain mandatory.
- Group retrieval is bounded by configured count and nesting depth; overflow, unsupported nesting,
  unmapped groups, and stale or incomplete results cannot silently broaden access.
- Authentication success, denial, and provider failure are audited with stable subject context when
  known, method and assurance, generic result codes, and no password, token, raw claim, or directory
  secret disclosure.
- Configuration rejects simultaneous development and enterprise providers, incomplete directory
  profiles, insecure endpoints, missing trust configuration, invalid mapping identifiers, and
  synthetic directory mode in production.
- Tests cover success, denial, malformed credentials, secret redaction, TLS configuration, exact
  group mapping, group limits, deterministic failover, provider outage, and authentication-versus-
  authorization separation.
- This slice provides authentication decision support only; it does not add approval workflow,
  directory account provisioning, autonomous role assignment, or infrastructure execution authority.

### ATLAS-IMP-014 Validation Evidence

- Backend Ruff check and format verification passed across 181 files.
- Strict backend type checking passed across all 178 source and test files.
- Full backend test suite passed: 163 tests, including thirteen directory-identity tests for
  normalized identities, explicit group mapping, malformed credentials, deterministic failover,
  rejection without failover, bounded group retrieval, provider outage audit, generic credential
  denial, authentication-versus-authorization separation, TLS-only configuration, nested-group
  rejection, and trust-file validation before network access.
- Frontend TypeScript, ESLint, integrated user-flow test, and production build all passed without a
  frontend contract change.
- The production/stable `ldap3==2.9.1` release is pinned in `uv.lock`; TLS uses platform-required
  certificate validation and the configured CA file, while insecure LDAP and trust downgrade are
  rejected.
- The live development API remained healthy and returned the existing server-configured development
  identity, confirming adapter selection did not regress the local workflow.
- A live enterprise LDAPS bind was not attempted because no customer directory endpoint, trust
  bundle, or test account is configured; network integration validation remains environment-bound.
- GitHub backend CI passed in 25 seconds and frontend CI passed in 35 seconds on PR #26 head
  `b159f348f96da18c5151c05b1b02bc2de7b0de56` before the final documentation-only update.

### ATLAS-IMP-013 Acceptance Criteria

- Selected audit and security events are normalized into a versioned vendor-neutral contract that
  retains original event ID and type, occurrence time, correlation, category, severity and reason,
  outcome, result code, mapping version, classification, and redaction state.
- RFC 5424 messages use UTC timestamps, stable priority, logical hostname, app name, message ID,
  escaped structured data, bounded UTF-8 content, and a digest without treating free-form text as
  the machine-authoritative source.
- The first destination is versioned, TLS-only, server-authenticated, independently queued, bounded,
  and monitored for certificate expiry; TCP and UDP are disabled with no insecure downgrade.
- Schema, classification, filter, mapping, redaction, message-size, destination, certificate, and
  queue validation occurs before transport dispatch and fails closed without leaking event data.
- Stable event IDs survive retries; duplicate transport delivery is possible and explicitly
  documented, while retry uses bounded attempts and deterministic backoff in the synthetic slice.
- Delivery states distinguish queued, retrying, transport-delivered, and dead-letter outcomes;
  unknown or failed delivery is never represented as successful SIEM ingestion.
- Transport acceptance proves only Syslog handoff. SIEM ingestion, parsing, correlation, alerting,
  and ticket creation remain unknown unless independently acknowledged.
- Required security-export authorization and audit failure blocks overview or explicit test-event
  operations; hidden destinations and fields do not leak through errors or counts.
- An explicit user-initiated test event exercises the same normalization, redaction, mapping, queue,
  TLS transport, receipt, and audit path as selected production events.
- The web workspace shows destination profile and version, TLS and certificate state, queue depth,
  delivery counts, last transport receipt, mapping/redaction preview, limitations, and a test-event
  control without exposing secrets or raw credentials.
- Export processing cannot authorize infrastructure action, alter source audit records, downgrade
  transport security, claim SIEM ingestion, or trigger autonomous remediation.

### ATLAS-IMP-013 Validation Evidence

- Backend Ruff check and format verification passed across 177 files.
- Strict backend type checking passed across all 174 source and test files.
- Full backend test suite passed: 150 tests, including eleven security-export tests for
  authentication, exact assignment and scope, TLS-only destination health, RFC 5424 preview,
  explicit test delivery, redaction and framing, stable retry identity, bounded dead-letter,
  expired-certificate failure, queue capacity, and required-audit failure.
- Frontend TypeScript, ESLint, integrated user-flow test, and production build all passed.
- Live API validation returned one server-authenticated TLS destination, zero queued records,
  transport-delivered test-event state, and explicit false SIEM-ingestion confirmation.
- The live web workspace displayed destination and certificate health, queue and handoff counts,
  RFC 5424 mapping preview, safety limitations, and successful explicit test-event feedback without
  claiming SIEM ingestion or infrastructure authority.
- GitHub backend CI passed in 24 seconds and frontend CI passed in 30 seconds on PR #25 head
  `1e96eac042297fbed383e0a269a8ea79eed2d59f` before the final documentation-only update.

### ATLAS-IMP-012 Acceptance Criteria

- Report requests bind to one authorized storage target and one exact immutable recommendation ID
  and version, report type, audience, classification boundary, and optional incident reference.
- Reports are immutable and versioned and retain owner, source lineage, creation and expiry,
  classification, redaction state, reviewer state, component versions, and content digest.
- Technical report sections expose section-level complete, partial, or failed state; scope,
  evidence, preference, alternatives, risk, impact, interruption, duration, recovery, unknowns,
  policy, and human-review boundaries remain visible.
- Material report statements cite authorized evidence from the exact source recommendation;
  inaccessible, stale, missing, or conflicting evidence remains a limitation and is never rendered
  as a successful conclusion.
- The first export is deterministic Markdown generated from the validated structured artifact;
  report rendering cannot add claims, targets, permissions, approval, or execution authority.
- Optional ITSM handoff is a labeled draft bound to an exact incident reference and report version,
  with normalized field mapping, artifact references, classification, redaction, and an idempotency
  key.
- Repeating the same report request returns the same artifact and handoff draft; a changed source
  version or material request creates a distinct artifact.
- The ITSM draft never changes an external record, closes an incident, approves a change, grants
  permission, or represents recommendation review as execution authority.
- Hidden targets, unauthorized evidence, source-version mismatch, unsupported report type,
  classification overflow, invalid incident reference, content-digest mismatch, and required audit
  failure fail closed without partial report disclosure.
- The web workspace generates and displays report state, source lineage, section status, evidence
  references, limitations, redaction, reviewer state, ITSM draft status, and safety boundaries and
  offers a deterministic Markdown download.
- Atlas remains decision support; report generation and ITSM handoff preparation do not authorize
  or execute infrastructure operations or external ticket mutations.

### ATLAS-IMP-012 Validation Evidence

- Backend Ruff check and format verification passed across 166 files.
- Strict backend type checking passed across 163 source and test files.
- Full backend test suite passed: 139 tests, including thirteen report tests for authentication,
  exact assignment and scope, source lineage, section state and evidence, Markdown integrity,
  idempotent review-only ITSM drafts, optional handoff, linked versions, safe source errors,
  incident validation, fail-closed audit, and digest validation.
- Frontend TypeScript, ESLint, integrated user-flow test, and production build all passed.
- Live API validation produced six section-level states with attributable evidence and limitations,
  a 64-character SHA-256 digest, pending review, and an idempotent ITSM draft with dispatch and
  external mutation both denied.
- The live web flow completed investigation, RCA, recommendation, report, and ITSM draft creation;
  source lineage, section states, limitations, download, and both authority boundaries were visible.
- The 1280-pixel desktop report workspace was visually inspected without incoherent overlap or
  page-level horizontal overflow; wide comparison content remains internally scrollable.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-011 Acceptance Criteria

- Recommendation requests are bound to one authorized storage target and one exact source RCA case
  version, accountable audience, decision horizon, constraints, and maximum capability class.
- Artifacts and options are immutable and versioned with owner, state, expiry, source lineage,
  component versions, policy outcomes, and review status.
- The first slice represents investigate, escalate, defer or no-action, restoration-planning, and
  remediation-planning options without executing, approving, or silently generating commands.
- Every option retains applicability, intended outcome, conceptual steps, capability class,
  evidence balance, assumptions, unknowns, risk dimensions, impact, interruption, duration,
  preconditions, success criteria, stop conditions, recovery, governance, and residual risk.
- Deterministic validation excludes prohibited options and blocks consequential options that lack
  current impact, rollback, applicability, readiness, or authoritative procedure evidence.
- Comparison keeps evidence strength, effectiveness, impact, reversibility, duration, complexity,
  policy, and residual risk visible rather than reducing them to one opaque score.
- The preferred option is lower-risk, reversible, evidence-supported, and read-only when it can
  answer the immediate decision; ties or insufficient evidence produce no preferred option.
- Escalation and no-action remain explicit alternatives with trigger, expiry, and residual risk.
- Hidden targets, unauthorized evidence, non-allowlisted capabilities, stale citations, unsupported
  preference, and required audit failures fail closed without partial artifact disclosure.
- The web workspace compares options, explains preference and exclusions, and shows impact,
  interruption, readiness, recovery, policy, expiry, human review, and decision-support boundaries.
- Recommendation review or approval never authorizes infrastructure execution.

### ATLAS-IMP-011 Validation Evidence

- Backend Ruff check and format verification passed across 155 files.
- Strict backend type checking passed across 152 source and test files.
- Full backend test suite passed: 126 tests; one dependency deprecation warning remains outside
  this task's scope.
- Frontend TypeScript, ESLint, user-flow test, and production build all passed.
- The integrated UI test covers health check, bounded investigation, provisional RCA, and governed
  recommendation comparison through the no-execution decision boundary.
- Live API and recommendation UI validation passed with `execution_authorized=false`.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-010 Acceptance Criteria

- The first RCA domain is storage and the bounded fault families are controller or path
  degradation and transient or observation-source failure.
- Every case is immutable and versioned and retains owner, state, severity, incident references,
  target scope, analysis window, source investigation artifact, component versions, and lineage.
- Cases distinguish symptoms, possible triggers, contributing conditions, recovery factors,
  observation failures, and coincidental events without converting correlation into causation.
- Affected and explicitly unaffected components and services remain separate; graph reachability
  never becomes confirmed service impact.
- Ranked hypotheses retain mechanism, expected affected and unaffected entities, expected sequence,
  supporting and contradicting evidence, missing observations, confounders, and assumptions.
- Diagnostic plans are exact, bounded, allowlisted C0/C1 operations with declared duration, load,
  output, timeout, stop behavior, role, policy, classification, retention, and result branches.
- Confirmation levels are categorical and no case can become confirmed without domain criteria and
  attributable eligible human review.
- Missing, stale, conflicting, inaccessible, or insufficient evidence produces provisional or
  inconclusive state, an explicit blocker, and the safest useful next check.
- Authorization, scope, evidence, citation, capability, confirmation, and required audit failures
  fail closed without exposing hidden targets or partial unauthorized case data.
- The web workspace shows incident scope, symptoms, affected and unaffected context, ranked
  hypotheses, evidence balance, diagnostics, gaps, provisional statement, and review status.
- RCA remains decision support and cannot authorize or execute remediation.

### ATLAS-IMP-010 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 141 source and test files.
- Backend pytest suite passed: 114 tests, including eleven RCA tests for authentication, exact
  assignment and scope, immutable incident-target version lineage, causal taxonomy, evidence
  balance, affected and explicitly unaffected scope, timeline integrity, generic target errors,
  evidence budgets, fail-closed audit, and allowlisted diagnostics.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live API validation returned a versioned provisional case with two ranked fault-family
  hypotheses, pending attributable review, explicit evidence gaps, and false root-cause and impact
  confirmation flags.
- The live web flow completed investigation followed by RCA case creation and displayed incident
  scope, symptoms, affected, possible, and explicitly unaffected context, ranked hypotheses,
  evidence balance, bounded C1 diagnostics, blocker, safest next step, provisional cause statement,
  and the decision-support safety boundary.
- The 1280-pixel desktop view was visually inspected with no incoherent overlap or page-level
  horizontal overflow in the RCA workspace.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-009 Acceptance Criteria

- Investigation requests are limited to an exact authorized organization, environment, site,
  resource, target, question, time window, and bounded evidence budget.
- Artifacts are immutable and versioned and retain the prior version reference, requester,
  intended decision, component versions, stop reason, and safety boundary.
- Material statements remain typed as observations, retrieved facts, calculated findings,
  correlations, inferences, hypotheses, assumptions, unknowns, or recommendations.
- Material claims reference current authorized evidence or explicitly declare why evidence is
  unavailable; unresolved, stale, and contradicting evidence remains visible.
- Timeline entries preserve occurrence, observation, and ingestion time without claiming temporal
  order proves causality.
- Multiple hypotheses retain supporting and contradicting evidence, categorical confidence,
  limiting factors, and safe discriminating checks.
- Graph reachability, recent change, correlation, and historical similarity are never labeled root
  cause or confirmed outage in this slice.
- Schema, citation, scope, evidence-budget, capability, and audit failures fail closed without
  exposing hidden targets or partial unauthorized artifacts.
- The web workspace communicates what is known, inferred, assumed, conflicting, and unknown,
  explains confidence, and shows the safest next evidence without private chain-of-thought.
- Atlas remains decision support and does not authorize or execute infrastructure changes.

### ATLAS-IMP-009 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 130 source and test files.
- Backend pytest suite passed: 103 tests, including ten investigation tests for exact
  authorization, immutable version links, typed claims, evidence references, normalized time,
  hidden-target non-disclosure, evidence budgets, fail-closed audit, allowlisted checks, and exact
  resource scope.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live API validation returned all eight implemented epistemic claim types, two alternative
  hypotheses, explicit stopping behavior, and false root-cause and outage confirmation flags.
- The live web flow created a versioned artifact from the selected storage target and displayed
  known, inferred, and unknown statements, confidence rationale, typed claims, alternatives,
  bounded C1 checks, normalized UTC timeline, stop reason, and safety boundary.
- Desktop and 390-pixel mobile views were inspected with no incoherent overlap or page-level
  horizontal overflow; inventory tables remain bounded and internally scrollable.
- Browser console validation reported no errors or warnings during the investigation flow.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-008 Acceptance Criteria

- Health-check definitions are immutable and versioned, and retain owner, target scope, connector
  capability, schedule, thresholds, timeout, step, and evidence limits.
- Definitions can be enabled or disabled without changing historical runs.
- Schedule evaluation is deterministic and reports the last and next due times without relying on
  an LLM or an in-process timer as authoritative state.
- On-demand execution is limited to an allowlisted C1 read-only connector capability and exact
  authorized target scope.
- Runs retain definition and connector versions, actor, trigger, timestamps, state, observations,
  findings, evidence, freshness, partial-result reasons, and safety notice.
- Completed, partial, timed-out, failed, and cancelled states are distinct; unknown outcomes are
  never represented as healthy.
- Step, evidence, duration, and target limits fail closed before connector dispatch or truncate to
  an explicit partial result where the contract permits.
- Required authorization and audit failures block protected health-check responses.
- The web workspace shows enabled checks, schedule state, latest run, findings, freshness,
  evidence, partial context, and an explicit read-only decision-support boundary.

### ATLAS-IMP-008 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 119 source and test files.
- Backend pytest suite passed: 93 tests, including eleven health-check tests for exact
  authorization, deterministic schedules, versioned definitions, partial results, safe timeout,
  disabled dispatch, generic target errors, result budgets, and fail-closed pre-dispatch audit.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live API validation returned two versioned C1 definitions with deterministic 15- and 60-minute
  schedules and evidence-linked partial and completed latest runs.
- A live manual controller check completed as `partial`, retained the authenticated requester,
  and did not represent missing event-log evidence as healthy or as a confirmed outage.
- Desktop and 390-pixel mobile views were inspected with no incoherent overlap or page-level
  horizontal overflow; health-check tabs and tables remain bounded and internally scrollable.
- Browser console validation reported no errors or warnings during overview and manual-run flows.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-007 Acceptance Criteria

- Canonical entities, relationships, observations, and snapshots retain source, time, freshness,
  confidence basis, classification, and access metadata.
- The first modeled path covers storage, volume, datastore, virtual machine, technical service,
  and business service entities.
- Authorization filters entities and relationships before traversal and again before output.
- Hidden nodes cannot leak through counts, labels, path shapes, errors, or completeness metadata.
- Blast-radius traversal is bounded by direction, relationship type, depth, and node limits.
- Every affected entity includes an exact relationship and evidence path from the starting entity.
- Results distinguish directly affected, possibly affected, and unknown scope.
- Graph reachability is never presented as a confirmed outage or a production digital twin.
- Missing redundancy, stale branches, and incomplete service mappings remain explicit.
- Required graph-read audit failure blocks the protected response.
- The web workspace displays the dependency path, impact scope, freshness, and graph gaps.

### ATLAS-IMP-007 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 108 source and test files.
- Backend pytest suite passed: 82 tests, including eight graph impact tests for exact scope,
  bounded traversal, pre-traversal authorization, hidden-node non-disclosure, evidence paths,
  safe target errors, and fail-closed audit behavior.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live desktop and 390-pixel mobile views were inspected with no incoherent overlap; the
  dependency path remains horizontally scrollable within its bounded workspace.
- Live selection tests confirmed B28 maps through ERP dependencies and G400 maps through the
  Analytics service without inventing a business-service dependency.
- The UI labels the result as D0-D1 dependency analysis, exposes stale/partial graph context,
  and does not present graph reachability as an outage.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-006 Completion Criteria

- The Model Gateway is the only application path to a model transport.
- Endpoint routing is deterministic by task class, classification, lifecycle, and evaluation state.
- Model transports receive bounded provider-neutral invocations and no infrastructure credentials.
- Knowledge chunks carry organization, environment, classification, ACL, lifecycle, version, and
  exact citation metadata before becoming retrievable.
- Unauthorized chunks are excluded before relevance scoring and revalidated after ranking.
- Empty authorized retrieval is a valid result and is never presented as success or evidence.
- Model output citations must resolve to the exact authorized retrieval package.
- Grounded answers distinguish evidence-backed summary text and explicit unknowns.
- Required retrieval and model audit failures block the protected response.
- Evaluation covers citation recall, resolution, empty results, and zero ACL leakage.

### ATLAS-IMP-006 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 97 source and test files.
- Backend pytest suite passed: 74 tests, including pre-score ACL filtering, classification denial,
  exact citation validation, empty authorized retrieval, audit failure, bounded input, and safe API
  denial behavior.
- The retrieval evaluation harness passed fixed citation-recall and zero-leakage cases.
- The OpenAI-compatible adapter passed Reader Token isolation, structured request, and malformed
  provider-response tests.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed without regressions.
- Live HTTP smoke tests returned one exact authorized citation for a grounded query and did not
  invoke the model when no authorized relevant evidence was available.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-001 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 25 source files.
- Backend pytest suite passed: 7 tests.
- Frontend ESLint and TypeScript checks passed.
- Frontend Vitest suite passed and the production bundle built successfully.
- API liveness, correlation ID, platform status, and frontend proxy smoke tests passed.
- Desktop and 390-pixel mobile layouts were visually inspected with no horizontal overflow or console errors.
- Windows Command Prompt bootstrap and quality-check entry points passed without PowerShell execution-policy changes.
- Compose YAML parsed successfully with database, backend, and frontend services.
- Docker runtime validation remains unavailable on this workstation and is delegated to CI or a Docker-capable reviewer.

## Planned Tasks

The next implementation task will be added after its vertical slice is selected from the approved
roadmap and its dependencies and acceptance criteria are recorded.

## Blocked Tasks

No task is currently blocked.

Environment limitation for ATLAS-IMP-001: Docker is not installed on the current workstation. Compose assets will be generated and statically inspected, but runtime Compose validation requires a Docker-capable environment.

## Completed Tasks

| Task ID | Title | Completion Evidence |
| --- | --- | --- |
| ATLAS-IMP-001 | Runnable development foundation | Merged through [PR #12](https://github.com/ozdemirumit/Project_Atlas/pull/12); local and GitHub quality gates passed |
| ATLAS-IMP-002 | Identity and authorization foundation | Merged through [PR #13](https://github.com/ozdemirumit/Project_Atlas/pull/13); local and GitHub quality gates passed |
| ATLAS-IMP-003 | Connector registry and simulator framework | Merged through [PR #14](https://github.com/ozdemirumit/Project_Atlas/pull/14); 41 backend tests and all GitHub quality gates passed |
| ATLAS-IMP-004 | Hitachi Ops Center read-only connector candidate | Merged through [PR #15](https://github.com/ozdemirumit/Project_Atlas/pull/15); 55 backend tests and all GitHub quality gates passed |
| ATLAS-IMP-005 | Storage inventory and health vertical slice | Merged through [PR #16](https://github.com/ozdemirumit/Project_Atlas/pull/16); 60 backend tests, live UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-006 | Local LLM and governed RAG foundation | Merged through [PR #17](https://github.com/ozdemirumit/Project_Atlas/pull/17); 74 backend tests, retrieval evaluation, live API smoke tests, and all GitHub quality gates passed |
| ATLAS-IMP-007 | Infrastructure Graph and storage impact vertical slice | Completed through [PR #19](https://github.com/ozdemirumit/Project_Atlas/pull/19); 82 backend tests, live desktop/mobile UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-008 | Scheduled storage health checks vertical slice | Completed through [PR #20](https://github.com/ozdemirumit/Project_Atlas/pull/20); 93 backend tests, live desktop/mobile UI and manual-run validation, and all GitHub quality gates passed |
| ATLAS-IMP-009 | Evidence-grounded investigation and reasoning vertical slice | Completed through [PR #21](https://github.com/ozdemirumit/Project_Atlas/pull/21); 103 backend tests, live desktop/mobile investigation validation, and all GitHub quality gates passed |
| ATLAS-IMP-010 | Storage fault-family Root Cause Analysis vertical slice | Completed through [PR #22](https://github.com/ozdemirumit/Project_Atlas/pull/22); 114 backend tests, live API and desktop UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-011 | Storage Recommendation Engine vertical slice | Completed through [PR #23](https://github.com/ozdemirumit/Project_Atlas/pull/23); 126 backend tests, live recommendation API/UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-012 | Technical Decision Report and controlled ITSM handoff vertical slice | Completed through [PR #24](https://github.com/ozdemirumit/Project_Atlas/pull/24); 139 backend tests, live report and ITSM draft API/UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-013 | TLS Syslog security export vertical slice | Completed through [PR #25](https://github.com/ozdemirumit/Project_Atlas/pull/25); 150 backend tests, live API/UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-014 | Enterprise LDAP/AD identity provider | Completed through [PR #26](https://github.com/ozdemirumit/Project_Atlas/pull/26); 163 backend tests, live development-adapter validation, and all GitHub quality gates passed |
| ATLAS-IMP-015 | Secure browser-session and bounded API-credential foundation | Completed through [PR #27](https://github.com/ozdemirumit/Project_Atlas/pull/27); 185 backend tests, frontend validation, live fail-closed API validation, and all GitHub quality gates passed |
| ATLAS-IMP-016 | Enterprise browser login and CSRF-aware web session lifecycle | Completed through [PR #28](https://github.com/ozdemirumit/Project_Atlas/pull/28); 185 backend tests, four frontend scenarios, live desktop/390px mobile login validation, and all GitHub quality gates passed |
| ATLAS-IMP-017 | Self-service session inventory and governed revocation | Completed through [PR #29](https://github.com/ozdemirumit/Project_Atlas/pull/29); 192 backend tests, four frontend scenarios, live API and desktop/390px mobile validation, and all GitHub quality gates passed |
| ATLAS-IMP-018 | Immutable approval packet and human review foundation | Completed through [PR #30](https://github.com/ozdemirumit/Project_Atlas/pull/30); 203 backend tests, five frontend scenarios, live desktop/390px mobile validation, and all GitHub quality gates passed |
| ATLAS-IMP-019 | Governed personal API credential lifecycle | Completed through [PR #31](https://github.com/ozdemirumit/Project_Atlas/pull/31); 213 backend tests, five frontend tests, live API/UI enterprise session, token, bearer, revoke, desktop/mobile validation, and all GitHub quality gates passed |

## Status Rules

- `Planned`: accepted scope exists but work has not started.
- `In Progress`: one active branch owns the task.
- `Blocked`: progress requires a missing decision, dependency, permission, or environment.
- `Review`: implementation and available validation are complete; a pull request is open.
- `Done`: required review is resolved and the implementation pull request is merged.

Git history, code, tests, and pull requests are authoritative when this tracker is stale. Every implementation session must reconcile the tracker against repository evidence before editing and update it before completion.
