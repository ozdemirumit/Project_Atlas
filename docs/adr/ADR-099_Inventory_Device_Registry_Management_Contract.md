# ADR-099: Inventory Device Registry Management Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Infrastructure Operations, Security Architecture
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-016,
  ATLAS-031, ATLAS-032, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-055,
  ATLAS-056

## Context

Health Overview presents an authorized synthetic storage observation. It is evidence for health
analysis, not an authoritative inventory registry. Atlas therefore has no visible or persistent
way to register a device, distinguish active and retired records, or remove a device from active
inventory use without losing history.

An enterprise inventory mutation must preserve organization and environment isolation, RBAC,
audit history, optimistic concurrency and idempotency. It must not store credentials, infer
health, contact a target or authorize infrastructure execution.

## Decision

Atlas will introduce a separate `inventory` domain module and a Device Registry surface in Health
Overview. The registry owns manually declared infrastructure device lifecycle records. Existing
storage observations remain independent evidence and are not rewritten by registry mutations.

The first device types are storage, SAN switch, virtualization, server, backup, network and other.
Records contain a stable device key, display name, type, vendor, model, optional serial number,
optional management address, purpose, exact scope, lifecycle, actors, timestamps, version and
canonical digest. Credentials and secret values are forbidden.

## API Contract

The first version exposes:

- `GET /api/v1/inventory/devices` for bounded active, retired or all-scope inventory;
- `POST /api/v1/inventory/devices` for acknowledged manual registration;
- `GET /api/v1/inventory/devices/{device_id}` for one exact authorized record; and
- `POST /api/v1/inventory/devices/{device_id}/retirements` for version-bound retirement.

Create and retirement requests require an idempotency key. Retirement requires the current
version, a reason and explicit acknowledgement. Responses are no-store and omit request
fingerprints and idempotency metadata.

## Lifecycle

Removal from active inventory is modeled as `active -> retired`. Retirement preserves the same
stable identity, increments the version and records actor, time and reason. No hard-delete API is
exposed. A future reactivation contract requires a separate ADR and cannot silently overwrite
retirement evidence.

## Persistence

The application service depends on a repository port. Development without `DATABASE_URL` uses a
process-local memory adapter and identifies that limitation in the UI. Configured deployments use
a PostgreSQL adapter and migration `20260811_0095`, with scope-key, create-idempotency and
retirement-idempotency uniqueness constraints plus optimistic version updates.

PostgreSQL is authoritative when configured. The memory adapter makes no durability claim.

## Security And Audit

Read, create and retire use distinct permissions and exact C0/C2 scope assignments. Browser
session authentication and CSRF protection govern enterprise UI mutations. The explicitly enabled
development identity may manage only the local development registry without a browser session;
this exception is unavailable in test and production. Every service read and mutation emits
`atlas.inventory.device` audit evidence. Authorization failures remain generic and do not disclose
hidden inventory.

The registry never resolves credentials, opens a target session, invokes an MCP capability,
changes infrastructure, infers target health or grants AI execution authority.

## Presentation

Health Overview presents Registered Infrastructure before observed storage evidence. Operators can
filter active, retired and all records, search declared metadata, open Add Device, and retire an
active record through an impact-aware confirmation. The interface labels memory versus durable
persistence and uses retirement rather than a destructive delete control.

## Consequences

- Device lifecycle management becomes visible and testable without corrupting observed evidence.
- Enterprise deployments receive durable records and concurrency protection.
- Development remains runnable without PostgreSQL while making its persistence limitation clear.
- Device registration does not imply connectivity, health, MCP installation or execution rights.
- Graph relationships, discovery reconciliation, bulk import and reactivation remain future
  governed slices.

## Verification

- API tests cover authentication, RBAC denial, create/list/retire, secret exclusion,
  acknowledgement, idempotency, optimistic version conflict and audit evidence.
- Component tests cover visible lifecycle controls, complete registration, explicit retirement and
  filter query ownership without a hard-delete action.
- Full backend format, lint, mypy and tests pass.
- Full frontend ESLint, both TypeScript projects, tests and production build pass with a separate
  lazy registry chunk.
- Live desktop and mobile checks must cover login, add/cancel, disabled confirmation, successful
  register/retire behavior, responsive fit and clean console/network behavior.

## Follow-Up

Complete live validation and delivery for IMP-143, then implement IMP-144 MCP Lifecycle management
with installed inventory, governed install/update/retire controls and the same RBAC, audit,
idempotency, persistence and reversible-lifecycle rules.
