# Project Atlas

## Testing Strategy

| Field | Value |
| --- | --- |
| Document ID | ATLAS-056 |
| Version | 1.0.0 |
| Status | Approved |
| Document Owner | Quality Engineering Owner |
| Reviewers | Architecture Owner, Security Architecture, Backend Engineering, Frontend Engineering, Platform Engineering, AI Architecture, Infrastructure Domain Architects, Site Reliability Engineering, Audit and Compliance |
| Approver | Umit Ozdemir (acting Architecture Owner) |
| Approval Date | 2026-08-03 |
| Last Updated | 2026-08-03 |
| Related Documents | [ATLAS-003](003_Project_Principles.md), [ATLAS-020](020_MCP_Framework.md), [ATLAS-023](023_Workflow_Engine.md), [ATLAS-025](025_Policy_Engine.md), [ATLAS-032](032_Audit.md), [ATLAS-038](038_Deployment_and_Bootstrap.md), [ATLAS-040](040_AI_Agents.md), [ATLAS-047](047_Guardrails.md), [ATLAS-050](050_API.md), [ATLAS-051](051_Backend.md), [ATLAS-052](052_Frontend.md), [ATLAS-053](053_Database.md), [ATLAS-054](054_VectorDB.md), [ATLAS-055](055_Coding_Standards.md), [ATLAS-057](057_Deployment.md), [ATLAS-058](058_CI_CD.md), [ATLAS-059](059_Release_Process.md) |
| Supersedes | ATLAS-056 version 0.1.0 |

## 1. Purpose

This document defines verification, validation, evaluation, and release-testing strategy for Project Atlas.

Testing must provide evidence that deterministic controls work, AI behavior remains within defined quality and safety bounds, and deployment or recovery procedures are reproducible. An AI assertion that code is correct is never test evidence.

## 2. Scope

### In Scope

- Test levels, ownership, environments, data, automation, traceability, and release gates
- Functional, contract, security, isolation, workflow, connector, AI, RAG, frontend, data, deployment, resilience, and recovery testing
- Performance, accessibility, compatibility, migration, offline, and operational validation
- Defect, flakiness, coverage, evidence, and continuous-evaluation practices

### Out of Scope

- Final tool selection before language and CI ADRs
- Customer acceptance criteria unique to one deployment
- Claiming exhaustive proof for all infrastructure or model behavior
- Running destructive tests against production infrastructure

## 3. Objectives

- Scale test depth with capability class, data sensitivity, and blast radius
- Verify controls through negative and bypass cases, not only happy paths
- Test realistic failure, timeout, duplicate, stale, partial, and unknown states
- Evaluate AI quality, grounding, calibration, safety, and usefulness
- Validate installation, upgrade, rollback, backup, and restore
- Preserve reproducible test evidence for release decisions
- Detect regression before customer environments become the test system

## 4. Testing Principles

- Test behavior and contracts, not private implementation details.
- Use the lowest test level that proves a requirement, then add cross-boundary coverage by risk.
- Every production defect should create a regression case where feasible.
- Security controls require adversarial and direct-API tests.
- C2-C5-related planning and controls require stronger verification than informational features.
- Deterministic and probabilistic behavior use different assertion methods.
- Test data contains no uncontrolled customer secrets or production records.
- Flaky tests are defects.
- Skipped mandatory tests block release.
- Passing tests do not waive human review.

## 5. Risk-Based Test Matrix

| Risk factor | Required increase in testing |
| --- | --- |
| Authentication, authorization, policy, approval, or audit | Unit, integration, direct API, bypass, concurrency, failure, and E2E |
| Organization or classification isolation | Cross-boundary negative suites at every data path |
| Connector C1-C2 | Contract, simulator, lab, timeout, partial, rate, and safe-load tests |
| C3-C5 plan or future runtime | Formal safety review, exact binding, impact, rollback, lab, and human acceptance |
| AI recommendation or RCA | Grounding, citation, calibration, adversarial, domain, and human evaluation |
| Schema, migration, retention, or deletion | Prior-version, volume, rollback/recovery, projection, backup, and restore |
| External integration | Contract, idempotency, replay, throttling, schema drift, and outage |
| Privileged UI | Backend enforcement, accessible review, stale state, and anti-coercion tests |

## 6. Test Levels

### Static Verification

- Formatting, linting, typing, schema, architecture, secret, dependency, and documentation checks

### Unit Tests

- Pure domain behavior, parsers, validators, calculations, state machines, and policy rules

### Component Tests

- One deployable component with real internal dependencies and controlled external ports

### Integration Tests

- Real supported database, queue, object, vector, identity, model, or adapter combinations

### Contract Tests

- API, event, MCP, webhook, integration, schema, and compatibility behavior

### System Tests

- Deployed Atlas services working together through supported entry points

### End-to-End Tests

- Core user journeys from browser or external client through durable outcome

### Operational Validation

- Install, upgrade, rollback, backup, restore, failover, offline, monitoring, and support procedures

## 7. Traceability

- Requirements and stable principle or guardrail IDs map to test cases.
- APIs, events, connector capabilities, workflows, policies, and migrations map to contract suites.
- Test evidence identifies code, document, schema, prompt, model, artifact, environment, and dataset versions.
- Release gates report passed, failed, skipped, quarantined, and not-applicable tests with reasons.
- Defects link to failing test and affected requirement.
- Exceptions have owner, expiry, compensating control, and release approval.

## 8. Test Environments

| Environment | Purpose | Data and target posture |
| --- | --- | --- |
| Local | Fast developer feedback | Synthetic data and in-process fakes or containers |
| CI ephemeral | Repeatable isolated verification | Generated fixtures and supported service containers |
| Integration | Multi-component and adapter validation | Synthetic data and simulators |
| Vendor lab | Approved real-system connector and procedure testing | Non-production targets and controlled credentials |
| Pre-production | Release, scale, security, deployment, and recovery | Production-like synthetic or approved masked data |
| Offline lab | Air-gapped bundle and update testing | Signed internal artifacts only |

Production testing is limited to approved non-destructive validation and operational drills under change control.

## 9. Test Data

- Synthetic data is the default.
- Fixtures include organization, environment, site, vendor, version, time, classification, role, and lifecycle diversity.
- Sensitive and adversarial markers are recognizable and safe.
- Masked data requires privacy review and proven de-identification.
- Datasets are versioned, checksummed, documented, and licensed.
- Expected answers and reviewer rationale are separate from model-visible input.
- Test data includes stale, conflicting, missing, malformed, duplicated, delayed, and unauthorized records.
- Cleanup is verified so test artifacts do not leak across runs.

## 10. Unit Testing

Unit suites prioritize:

- Domain state transitions and invariants
- Value objects, normalization, time, units, identifiers, and scope
- Permission, policy, capability-class, approval, and guardrail rules
- Risk, impact, duration, confidence, and deterministic calculations
- Parsers, schema validation, redaction, and error mapping
- Idempotency and retry classification
- Branch, timeout, cancellation, and compensation logic
- Version compatibility and lifecycle behavior

Unit tests are fast, isolated, deterministic, and independent of network or wall clock.

## 11. API Testing

- OpenAPI lint and implementation conformance
- Request and response schema, unknown field, and content type
- Authentication, session, CSRF, scope, permission, policy, and approval
- Hidden resource, count, search, and pagination isolation
- Stable errors and no internal data leakage
- Cursor tampering, ETag, concurrency, idempotency, and replay
- File size, archive, type, malware, and download authorization
- Long-running state, cancellation, partial, timeout, and unknown
- SSE sequence, reconnect, draft/final, error, and terminal event
- Rate limit, quota, overload, and dependency failure

## 12. Authentication and RBAC Testing

- LDAP or selected provider success, failure, failover, TLS, group, and stale membership
- Session fixation, expiry, revocation, logout, replay, and step-up
- Local bootstrap, recovery, break-glass, and lockout
- Default deny and permission atomicity
- Organization, environment, site, domain, resource, and capability scopes
- Group mapping, nested groups, conflicts, expiry, and revocation propagation
- Temporary elevation and delegation
- Separation of duties and distinct human approver
- Service identity and audience isolation
- UI and direct API equivalence

## 13. Policy and Approval Testing

- Deterministic allow, deny, approval-required, and exception outcomes
- Policy precedence, conflict, version, simulation, and rollback
- Exact approval binding to target, parameters, plan, impact, policy, connector, and window
- Role, scope, assurance, separation, stage, quorum, expiry, and revocation
- ITSM approval synchronization, replay, reschedule, and conflict
- Changed evidence, topology, risk, credential, or precondition before handoff
- Concurrent decisions and stale writes
- Audit outage and control-service failure
- Verification that approval cannot grant permission or override guardrails

## 14. Audit and Logging Testing

- Mandatory event coverage from request through final state
- Stable event schema, IDs, time, identity, authority, target, and outcome
- Duplicate, retry, gap, order, clock skew, and delayed events
- Append-only integrity and tamper detection
- Secret and sensitive-data redaction across every producer
- Audit outage fail-closed behavior
- Retention, legal hold, export, backup, and restore
- Operational log levels, sampling, suppression, buffering, and loss alerts
- Correlation across API, workflow, AI, connector, and integration

## 15. Workflow Testing

- Definition schema and version compatibility
- State transitions, timers, schedules, waits, and human tasks
- Duplicate event, retry, idempotency, and out-of-order delivery
- Cancellation before, during, after, and too late
- Timeout, partial, unknown, compensation, and recovery
- Worker crash, lease expiry, restart, and graceful shutdown
- Policy and approval re-evaluation at consequential boundaries
- Orphaned owner and expired schedule
- Upgrade and rollback with in-flight runs
- Complete audit and operation-resource projection

## 16. Connector Testing

### Contract

- Manifest, package signature, compatibility, capability, parameter, result, and error schemas

### Simulator

- Success, empty, denied, timeout, throttle, malformed, partial, unknown, and vendor-error fixtures

### Isolation

- Filesystem, network, process, credential, resource, and organization boundaries

### Capability

- Target scope, least privilege, read-only default, C0-C5 classification, output bounds, and idempotency

### Vendor Lab

- Supported product and version behavior, rate, load, failover, and non-destructive validation

Generated connectors require static analysis, dependency review, malicious-input tests, and human domain review before lab use.

## 17. Knowledge and RAG Testing

- Source registration, parsing, malware, active content, and quarantine
- Chunk and citation integrity
- Authority, applicability, version, freshness, conflict, and supersession
- Organization, classification, source ACL, and hidden-result isolation
- Lexical, vector, hybrid, rerank, and empty-result behavior
- Prompt injection and malicious-document resistance
- Source suspend, permission change, deletion, index cleanup, and non-return after restore
- Retrieval precision, recall, ranking, and citation support
- Generated knowledge labeling and approval
- Offline embedding and model update

## 18. AI Evaluation

AI suites evaluate:

- Structured-output validity
- Claim support and citation correctness
- Fact, inference, assumption, hypothesis, and unknown distinction
- Product, version, target, and temporal correctness
- Alternative hypotheses and counterevidence
- Confidence calibration and response to missing evidence
- Risk, impact, interruption, duration, preconditions, and recovery completeness
- Tool selection and scope restraint
- Refusal, guardrail, DLP, and prompt-injection behavior
- Human usefulness, correction, and disagreement

Assertions use rubrics, deterministic validators, expert review, and statistical comparison rather than exact prose matching.

## 19. AI Dataset Design

- Cases are versioned and immutable within an evaluation run.
- Ground truth distinguishes known fact, reviewer judgment, and unresolved ambiguity.
- Holdout sets prevent prompt tuning against all evaluation cases.
- Cases include normal, insufficient, stale, conflicting, adversarial, no-answer, and permission-denied scenarios.
- Domain sets include product and version differences.
- Prompt, model, agent, retrieval, tool, and guardrail versions are captured.
- Score uncertainty and sample size are reported.
- Failed safety cases are never averaged away by high quality scores.

## 20. RCA, Recommendation, and Impact Evaluation

- Root-cause top-k recall and false-positive rate
- Timeline and affected-scope correctness
- Alternative-hypothesis and discriminating-check quality
- Recommendation option coverage and tradeoff clarity
- Unsafe or infeasible option rejection
- Affected and unaffected entity precision and recall
- Service mapping and redundancy detection
- Duration, interruption, recovery, and risk calibration
- No-supportable-recommendation behavior
- Estimated versus actual outcome after reviewed changes

False-safe impact predictions and unsupported confirmed causes are release-severity failures.

## 21. Guardrail and Red Team Testing

- Direct, indirect, encoded, obfuscated, multilingual, nested, and fragmented prompt injection
- Secret extraction and transformed exfiltration
- Cross-user, cross-organization, cross-environment, and cross-classification leakage
- Tool, target, parameter, destination, and capability substitution
- Hallucinated citation, command, approval, impact, and success
- Model, tool, policy, audit, and guardrail outage
- Loop, context, token, query, graph, and output resource exhaustion
- Malicious connector, runbook, workflow, mapping, and generated code
- Approval persuasion, replay, and confused deputy
- Offline stale-signature and compromised-artifact scenarios

Red-team findings become regression tests when they can be represented safely.

## 22. Frontend Testing

- Component, state, form, table, graph, and error behavior
- Chat SSE, reconnect, provisional/final, cancellation, and operation task center
- Authentication, session, scope change, hidden resources, and backend denial
- Investigation, recommendation, impact, workflow, and audit journeys
- Exact approval packet, step-up, reject, needs-evidence, defer, expiry, and revocation
- Content sanitization, external links, downloads, clipboard, and URL privacy
- Keyboard, screen reader, contrast, zoom, reduced motion, and focus
- Desktop, tablet, and small-screen layout without overlap
- Performance budgets and large authorized datasets

## 23. Database and Migration Testing

- Constraints, repositories, transactions, outbox, and optimistic concurrency
- Organization isolation across joins, counts, search, cache, and export
- Migration from every supported prior release
- Representative data volume, lock duration, and backfill resume
- Expand-and-contract mixed-version operation where required
- Retention, legal hold, deletion, tombstone, and derived-store cleanup
- Backup, restore, point-in-time recovery where supported, and projection rebuild
- HA failover, replica lag, leases, and migration lock
- Secret leakage in queries, errors, database logs, and backups

## 24. Integration Testing

- LDAP or federation, ITSM, Syslog, SIEM, notification, model endpoint, and object store
- Valid authentication, trust, mapping, and least privilege
- Idempotency, webhook signature, replay, duplicate, ordering, and conflict
- Timeout, throttling, API deprecation, schema drift, and credential rotation
- Certificate expiry, invalid hostname, and no insecure downgrade
- Queue backlog, offline export, and reconciliation
- AI-generated content labels and sensitive-data minimization
- Verification that external state cannot bypass Atlas authority

## 25. Performance Testing

Workloads include:

- API reads and controlled mutations
- Concurrent chat and model requests
- Inventory, graph, search, hybrid retrieval, and reports
- Connector health checks and scheduled workflows
- Event, audit, log, and integration throughput
- Knowledge ingestion and re-index
- Database migration and restore

Measure throughput, latency percentiles, queue age, error, saturation, resource use, and degradation. Performance testing preserves organization isolation and safe limits.

## 26. Reliability and Chaos Testing

- Process and node termination
- Database failover and replica lag
- Queue, cache, object, vector, graph, and search outage
- Model timeout and invalid response
- Connector runtime crash and network partition
- LDAP, ITSM, SIEM, Syslog, and DNS failure
- Clock skew and certificate expiry
- Disk or queue capacity pressure
- Audit ingestion failure
- Rolling upgrade and rollback during in-flight work

Chaos exercises run in controlled environments with explicit abort conditions and evidence.

## 27. Deployment Testing

- Clean install for every supported profile
- Preflight no-change failure
- Connected, proxy, mirrored, and offline artifact acquisition
- Signature, checksum, SBOM, trust, and secret validation
- Idempotent rerun and interrupted resume
- Configuration and certificate rotation
- Upgrade, migration, rollback, and uninstall preservation
- End-to-end verification report
- Support-bundle redaction
- No arbitrary internet dependency in restricted mode

## 28. Backup and Recovery Testing

- Scheduled backup success and integrity
- Restore into isolated environment
- Transactional, object, audit, workflow, approval, and policy consistency
- Derived graph, vector, and search rebuild
- Deleted, expired, suspended, and revoked state preservation
- External-effect and outbox reconciliation
- Recovery point and time measurement
- Site or node failover according to deployment profile
- Access denial and organization isolation after restore

A successful backup without restore evidence is insufficient.

## 29. Compatibility Testing

- Supported browser, OS, database, orchestrator, model endpoint, and dependency versions
- API, event, connector, workflow, policy, prompt, runbook, and schema versions
- Current and prior supported platform releases
- Connector package against declared vendor products and versions
- Offline bundle upgrade paths
- Mixed-version rolling deployment where supported
- Deprecated endpoint and migration-window behavior
- Restore of backups only into declared compatible versions

## 30. Security Testing

- Threat-model-derived misuse and abuse cases
- SAST, dependency, container, infrastructure, secret, and license scanning
- Dynamic API and browser security tests
- Authentication, session, CSRF, CORS, SSRF, injection, path, deserialization, and file handling
- Privilege escalation and authorization bypass
- Network, process, connector, model, and organization isolation
- Encryption, certificate, key, and credential rotation
- Audit integrity and non-disablement
- Penetration testing before production milestones
- Remediation verification and regression

## 31. Test Doubles and Simulators

- Fakes implement published ports and model deterministic state.
- Stubs return one declared response.
- Mocks verify boundary interaction sparingly.
- Simulators model vendor protocol, state, timing, errors, and version behavior.
- Contract fixtures are shared between connector and platform tests.
- Test doubles do not make integration tests appear to validate real vendor behavior.
- Simulators include malformed, delayed, partial, and unknown outcomes.
- Production credentials are prohibited.

## 32. Coverage

- Line coverage is a signal, not a quality target by itself.
- Critical domain transitions, permissions, policies, approvals, guardrails, errors, and recovery require explicit behavior coverage.
- Branch and mutation coverage may apply to deterministic high-risk modules.
- Contract and evaluation coverage track schemas, event types, connector capabilities, and AI scenarios.
- Untested code in a critical path requires documented rationale and reviewer acceptance.
- Coverage must not incentivize trivial assertions or exclusion abuse.

## 33. Flaky Tests

- A flaky test is identified, owned, and repaired promptly.
- Automatic rerun can collect evidence but cannot turn an initial failure into silent pass.
- Quarantine requires issue, owner, reason, impact, and expiry.
- Mandatory security and safety tests cannot be quarantined to ship.
- Time, randomness, network, concurrency, and shared-state sources are controlled.
- Flake rate and quarantine age are monitored.

## 34. Defect Severity

Release-blocking examples include:

- Cross-organization or restricted-data leakage
- Authentication, authorization, policy, approval, audit, or guardrail bypass
- Secret exposure
- Direct AI access to C3-C5 capabilities
- False success for unknown or partial operation
- Corrupting migration or failed restore
- Unsupported root-cause confirmation or false-safe high-impact recommendation
- Inaccessible critical approval workflow
- Tampered artifact accepted as trusted

Severity considers realistic impact, not test-layer location.

## 35. CI Test Tiers

### Pull Request

- Static checks, unit, component, contract, changed-area integration, documentation, and fast AI safety smoke suite

### Main Branch

- Full integration, system, browser, migration, connector simulator, retrieval, and AI evaluation suites

### Nightly or Scheduled

- Performance trend, extended AI evaluation, fuzzing, adversarial, chaos, compatibility, and long-running workflow tests

### Release Candidate

- Clean deployment, upgrade, rollback, backup/restore, offline bundle, security, full evaluation, and manual evidence review

## 36. Release Gates

A release cannot proceed with:

- Failed mandatory test or unresolved release-blocking defect
- Missing required traceability or test evidence
- Regressed safety, isolation, audit, or restore behavior
- Unapproved evaluation threshold regression
- Skipped required deployment or upgrade path
- Expired test exception
- Unknown artifact provenance or failed signature
- Unsupported migration or rollback state

Risk acceptance is explicit, scoped, approved, expiring where applicable, and included in release evidence.

## 37. Test Evidence

Release evidence contains:

- Source and artifact commit IDs
- Environment and dependency versions
- Test suite and dataset versions
- Model, prompt, agent, retrieval, guardrail, connector, and policy versions
- Results, logs, reports, coverage, and evaluation statistics
- Failed, skipped, quarantined, and not-applicable details
- Security and operational review outcomes
- Exceptions and residual risks
- Integrity checks and storage location

Evidence excludes secrets and protected test payloads.

## 38. Observability of Quality

- Pass, failure, skip, quarantine, and flake rates
- Test duration and queue time
- Defect escape and regression rate
- Coverage of requirements, APIs, events, capabilities, and guardrail IDs
- AI quality, calibration, refusal, and safety trends
- Connector and vendor-version coverage
- Deployment, migration, backup, and restore success
- Accessibility and security defect trends
- Exception age and release risk

## 39. MVP Scope

### Included

- Static, unit, component, integration, API contract, and system test foundation
- Authentication, RBAC, policy, approval, audit, and organization-isolation suites
- Connector simulator and one approved vendor-lab path
- Knowledge retrieval and first-domain AI evaluation
- Guardrail and prompt-injection adversarial tests
- Frontend core journey and accessibility tests
- Database migration, clean deployment, offline bundle, backup, and restore tests
- Pull-request, main, scheduled, and release-candidate gates

### Excluded

- Destructive tests on production infrastructure
- Universal vendor compatibility
- Claim that one AI benchmark proves production quality
- Shipping with quarantined mandatory safety tests
- Customer data as default test input
- Manual-only regression strategy

## 40. Dependencies and Traceability

- ATLAS-003 requires demonstrated reliability and safety.
- ATLAS-020, ATLAS-023, and ATLAS-025 define connector, workflow, and policy behavior.
- ATLAS-032 defines audit verification.
- ATLAS-038 defines bootstrap validation.
- ATLAS-040 and ATLAS-047 define agent evaluation and guardrail testing.
- ATLAS-050 through ATLAS-055 define implementation contracts.
- ATLAS-057 through ATLAS-059 define deployment, CI/CD, and release evidence.

## 41. Assumptions

- CI and lab environments can run supported local dependencies.
- Domain experts can review first-domain AI and connector cases.
- Offline release paths can be exercised in an isolated lab.
- Some expensive suites run on schedules or release candidates rather than every commit.

## 42. Open Questions and ADR Backlog

- Which unit, browser, contract, load, security, and AI evaluation tools are selected?
- What thresholds block release for coverage, retrieval, RCA, impact, and guardrails?
- Which first vendor lab and infrastructure domain are available?
- What pre-production scale represents initial enterprise use?
- Which chaos and penetration tests are required before MVP production readiness?
- How long is release evidence retained and where?

## 43. Acceptance Criteria

This document is ready to enter Review when:

- Test levels, environments, data, ownership, risk matrix, and traceability are agreed.
- Deterministic controls have negative, bypass, concurrency, failure, and direct-API tests.
- AI behavior has domain, grounding, calibration, safety, and human evaluation.
- Connector, RAG, frontend, database, deployment, recovery, offline, and accessibility coverage is defined.
- Mandatory release gates and defect severity prevent unsafe risk averaging.
- Test evidence is reproducible, versioned, and secret-free.
- Architecture, quality, security, engineering, AI, domain, operations, and audit reviewers accept the strategy.

## 44. Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | 2026-07-21 | Project Atlas Team | Initial test areas, principles, MVP scope, and questions |
| 0.2.0 | 2026-08-03 | Quality Engineering Owner | Added risk matrix, test levels and environments, control and connector suites, AI and RAG evaluation, frontend, data, integration, performance, chaos, deployment, recovery, security, CI tiers, release gates, and evidence |
| 1.0.0 | 2026-08-03 | Umit Ozdemir | Approved as the first binding documentation baseline under the designated approver authority |
