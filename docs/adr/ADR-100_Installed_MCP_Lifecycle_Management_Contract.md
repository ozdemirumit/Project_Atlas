# ADR-100: Installed MCP Lifecycle Management Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: MCP Platform Architecture, Infrastructure Operations, Security Architecture
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-016,
  ATLAS-020, ATLAS-021, ATLAS-031, ATLAS-032, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-055, ATLAS-056

## Context

The Connectors workspace exposes the complete governed Builder and supply-chain workflow, but its
first viewport contains only static lifecycle coverage. Operators cannot see installed package
receipts or connector instances, add an instance from an approved installation, or remove an
unused instance from active management.

Atlas already owns immutable package installation receipts and disabled connector instance
creation records. A new direct endpoint or uploaded executable would bypass package acquisition,
validation, human approval, signing, registry publication and installation custody. Lifecycle
management must therefore compose the existing records and preserve their authority boundaries.

## Decision

Atlas will add an Installed MCPs management workspace backed by bounded list operations for
governed package installation receipts and connector instances. Add MCP selects one exact
installed receipt and invokes the existing connector instance creation contract. The resulting
instance remains disabled and unconfigured and has no target, credential, capability, runtime,
execution, deployment or infrastructure authority.

Remove MCP is represented as instance retirement, not hard deletion or package removal.
Retirement is permitted only before target configuration exists. Configured or later-stage
instances require a future ordered decommissioning workflow that revokes runtime and credential
authority before retirement.

## API Contract

The first management version adds:

- `GET /api/v1/connectors/package-installation-receipts` for scope-bound installed package
  discovery;
- `GET /api/v1/connectors/instances/creation-policies` for minimized current signed policy
  discovery;
- `GET /api/v1/connectors/instances` for active, retired or all instance inventory; and
- `POST /api/v1/connectors/instances/{record_id}/retirements` for version-bound retirement.

The existing `POST /api/v1/connectors/instances` remains the only Add MCP mutation. Retirement
requires the current version, a bounded reason, explicit acknowledgement and an idempotency key.
Responses are no-store and omit policy signer identity, custody locations, fingerprints,
idempotency metadata, target configuration, secret references and credentials.

## Lifecycle

The initial transition is `disabled_unconfigured -> retired`. Retirement preserves record and
instance identity, immutable package and approval lineage, creation evidence and audit history.
It increments the record version and records actor, time, reason and a new canonical digest.

Retired records cannot be configured or reused as active creation records. Reactivation, package
upgrade and retirement of configured or active instances require separate exact workflows and
cannot overwrite retirement evidence.

## Persistence

The existing connector instance repository becomes lifecycle-aware. Memory persistence remains a
development-only process boundary. PostgreSQL adds indexed lifecycle and version columns plus
retirement idempotency metadata and performs optimistic updates. Existing version-one records are
backfilled as `disabled_unconfigured` without altering their canonical payload.

Package installation receipts remain immutable; their repository adds only scoped listing.

## Security And Audit

Package and instance reads use existing read permissions. Creation keeps the existing controlled
change permission and enterprise human MFA requirement. Retirement receives a distinct
controlled-change permission and requires a CSRF-protected enterprise browser session.

Every list and retirement operation records safe audit evidence. Scope mismatch is
non-disclosing. Retirement rejects any instance that has a target configuration binding and does
not stop processes, contact MCP servers, remove files, revoke credentials or mutate infrastructure.

## Presentation

Installed MCPs appears before lifecycle coverage and Builder intake. It shows package, release,
instance identity, state, owner and creation/retirement time. Operators can filter, refresh, open
Add MCP and retire eligible instances through an impact-aware confirmation. No hard-delete icon or
misleading autonomous install action is exposed.

When no governed package is available, Add MCP explains that the package must complete the
Builder and assurance workflow below. Technical lineage fields remain available only inside the
explicit add review, not in the inventory table.

## Consequences

- The user-visible management gap closes without weakening the supply-chain trust model.
- Unused connector identities can leave active management while evidence remains intact.
- Configured and active connector decommissioning stays fail-closed until ordered revocation is
  implemented.
- Package upgrade, reactivation, bulk actions and marketplace acquisition remain future governed
  slices.

## Verification

- API tests cover scoped package/instance lists, safe response fields, create integration,
  retirement, acknowledgement, idempotency, optimistic conflict, configured-instance rejection,
  audit evidence and retired-source rejection.
- Component tests cover visible add/retire controls, package selection, empty-state guidance,
  lifecycle filters, confirmation and absence of hard delete.
- Full backend and frontend quality gates pass.
- Live desktop and mobile checks cover add/cancel/retire behavior, responsive fit and clean
  lifecycle network/console behavior.
