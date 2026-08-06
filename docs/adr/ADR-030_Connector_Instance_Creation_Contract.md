# ADR-030: Connector Instance Creation Contract

**Status:** Accepted
**Date:** 2026-08-06
**Decision Owners:** Product Owner, Solution Architecture, Security Architecture

## Context

ADR-029 places one exact registered connector package into a governed immutable installation store.
Its receipt sets `package_installed` and `eligible_for_instance_governance`, but creates no connector
instance, target configuration, credential access, capability enablement, runtime trust, execution,
deployment, or infrastructure authority.

The MCP framework requires package-version and connector-instance state to be tracked separately.
One installed package version may support multiple independently governed instances. Creating an
instance must therefore establish only an identity and immutable package lineage. It must not be
treated as configuration, connectivity, health validation, enablement, or execution.

## Decision

Atlas will create a connector instance as an immutable version-one governance record in state
`disabled_unconfigured`. Creation is a C3 administrative operation performed by an authenticated,
MFA-protected human with exact tenant scope and dedicated permission.

### Request Contract

The create request contains only:

- exact installation receipt ID and canonical digest;
- exact package digest;
- a tenant-scoped stable instance key and bounded display name;
- exact signed instance-creation policy ID and digest;
- bounded business purpose;
- explicit acknowledgement that no target, credential, runtime, enablement, or execution authority
  is granted; and
- idempotency and correlation identifiers.

Callers cannot provide an instance ID, connector or release identity, package/store reference,
endpoint, site, target, certificate, proxy, network route, secret reference, capability, schedule,
configuration, health result, runtime setting, command, deployment setting, or lifecycle state.

### Source Reverification

Before mutation, the service reloads the current installation receipt through its owning service and
revalidates:

- receipt canonical integrity and exact request digest;
- organization and environment scope;
- complete registration, publication, signing, approval, validation, and acquisition lineage;
- connector, release, package, publisher, provenance, manifest, SDK, registry, installation policy,
  installer, custody, store, and artifact-reference bindings;
- installed and instance-governance-eligible state; and
- absence of promotion blocks or later authority.

The source service returns the complete upstream actor set. The instance creator must be distinct
from every upstream human, policy signer, workload, publisher, installer, and custodian.

### Policy Contract

An immutable signed policy fixes:

- required installation receipt and instance-record schemas;
- maximum installation age and required assurance level;
- required installation/store/artifact profiles;
- allowed SDK profiles and capability classes;
- instance state `disabled_unconfigured`;
- support group and naming bounds;
- separation-of-duty identities; and
- organization and environment scope.

Customer input cannot weaken these controls. Expired, modified, wrong-scope, incompatible, or
incorrectly signed policy evidence fails closed.

### Identity And State

The platform derives an opaque stable instance ID from the tenant, connector, release, source
installation receipt, and normalized instance key. The record preserves the original key and display
name as non-secret administrative metadata. The creating human becomes the initial accountable
owner; the policy supplies the support group.

A valid record sets only:

- `package_published = true`;
- `connector_registered = true`;
- `package_installed = true`;
- `instance_created = true`;
- `eligible_for_configuration_governance = true`; and
- `instance_state = disabled_unconfigured`.

It keeps `target_configured`, `credentials_resolved`, `connector_enabled`,
`runtime_trust_granted`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false. It contains no endpoint, target, credential, secret,
network, capability-enablement, schedule, runtime, command, or deployment data.

### Persistence And Idempotency

Records are immutable, deterministic, create-if-absent, and equivalent in memory and PostgreSQL.
The repository enforces uniqueness for:

- record ID;
- organization, environment, and normalized instance key; and
- creator and idempotency key.

One installation may anchor multiple differently keyed instances. Reuse returns the original record
only when the same creator, idempotency key, and request fingerprint match. All collisions fail
closed.

### Audit And API

A required intent audit succeeds before persistence. A required completion audit succeeds before
the record is committed. Read and create APIs use dedicated default-deny RBAC, exact scope, browser
session authentication, CSRF protection for mutation, strict extra-field rejection, safe errors,
`Cache-Control: no-store`, and minimized response evidence.

Audit and web responses exclude internal store references, installer and custodian identities,
request fingerprints, idempotency keys, raw manifests, package bytes, signatures, keys, endpoints,
target names, and secret-reference names.

### Deployment Behavior

Production uses durable PostgreSQL persistence. If durable persistence or required policy/audit
dependencies are unavailable, instance creation fails closed. Development may use an explicit
in-memory repository and signed development policy; it still grants no runtime or infrastructure
authority.

## Consequences

### Positive

- Multiple instances can be governed independently without weakening package custody.
- Instance identity and ownership exist before sensitive configuration is introduced.
- Target, credential, enablement, and runtime boundaries remain independently reviewable.
- Exact immutable lineage supports later configuration and incident evidence.

### Costs

- Instance creation adds another policy, audit, API, persistence, and lifecycle boundary.
- Configuration, target binding, credential assignment, health validation, enablement, and runtime
  trust remain separate work.

## Rejected Alternatives

### Create and Configure in One Request

Rejected because endpoint, target, trust, and secret inputs have materially different risk and
approval requirements.

### One Instance per Installed Package

Rejected because one package version must support multiple tenant-scoped target instances.

### Caller-Provided Instance ID or Lifecycle State

Rejected because it permits identity collision, state skipping, and policy bypass. Atlas derives the
ID and fixes the initial state.

### Create an Enabled Instance

Rejected because enablement requires complete configuration, exact target and credential bindings,
runtime trust, health verification, and additional human governance.

## Follow-Up

The next independent lifecycle contracts cover target/configuration binding, secret-reference
assignment, capability enablement, runtime trust, and governed invocation.
