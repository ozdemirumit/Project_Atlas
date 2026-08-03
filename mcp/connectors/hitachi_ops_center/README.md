# Hitachi Ops Center Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-004. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `hitachi.opscenter.storage.inventory.read` | C1 read-only | `GET /v1/objects/storages` |
| `hitachi.opscenter.storage.health.read` | C1 read-only | `GET /v1/objects/storages/{storageDeviceId}/components/instance` |

The self-test uses only `GET /configuration/version`. No refresh, registration, session mutation,
configuration change, job submission, or CLI operation is included.

## Safety Boundary

- The connector receives a pre-authenticated, endpoint-bound transport from the isolated runner.
- Connector code cannot resolve, serialize, log, or return credentials.
- Storage device identifiers are fixed allowlist bindings; caller input cannot expand target scope.
- Inventory output excludes management, SVP, and controller IP addresses.
- Collection count, nesting depth, status fields, response shape, and target identifiers are bounded.
- Unknown, empty, malformed, timeout, permission, throttle, and unavailable results remain distinct.
- Tests use synthetic documentation-derived data only. No production data or credentials exist here.
- There is no production HTTP adapter in this candidate.

## Source Provenance

Reviewed against the official Hitachi Vantara **Ops Center API Configuration Manager REST API
Reference Guide**, version 11.0.x, part number MK-99CFM000-25, published 2026-03-16:

- [Reference guide](https://docs.hitachivantara.com/r/en-us/mk-99cfm000/latest)
- [Getting the version information](https://docs.hitachivantara.com/r/en-us/mk-99cfm000/latest/common-operations-in-the-rest-api/getting-the-version-information)
- [Getting a list of storage systems](https://docs.hitachivantara.com/r/en-us/mk-99cfm000/latest/common-operations-in-the-rest-api/getting-a-list-of-storage-systems)
- [Getting hardware information](https://docs.hitachivantara.com/r/en-us/mk-99cfm000/latest/monitoring-storage-systems/getting-information-about-the-hardware-installed-in-a-storage-system)

The storage list and version endpoints require no vendor role according to the reference. The
hardware endpoint requires `Storage Administrator (View Only)`. Atlas still treats all three as
live C1 access and applies its own authorization, target binding, policy, audit, and quarantine.

## Promotion Requirements

1. Review the exact source version and capability mapping with a Hitachi storage domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Run contract tests against an approved non-production Configuration Manager endpoint using a
   least-privileged read-only identity.
4. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
5. Complete security review and explicit environment approval before package promotion.
