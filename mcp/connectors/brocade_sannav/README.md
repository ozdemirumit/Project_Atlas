# Brocade SANnav Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-261. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `brocade.sannav.fabric.inventory.read` | C1 read-only | `GET /external-api/v1/discovery/fabrics/`, `GET /external-api/v1/discovery/fabric-members/` |
| `brocade.sannav.fabric.health.read` | C1 read-only | `POST /external-api/v2/fault/events/` (bounded time window, filtered to one fabric) |

The self-test reuses the fabric-discovery read (SANnav has no confirmed dedicated
version/compatibility endpoint). No login/logout, session mutation, zoning, configuration change,
or CLI operation is included -- this connector deliberately uses SANnav's documented session-less
authentication mode instead of the stateful login/session flow.

## Safety Boundary

- The connector receives a pre-authenticated, endpoint-bound transport from the isolated runner.
- Connector code cannot resolve, serialize, log, or return credentials.
- Fabric identifiers are fixed allowlist bindings; caller input cannot expand target scope.
- Collection count, response byte size, and target identifiers are bounded.
- Malformed, timeout, permission, throttle, and unavailable results remain distinct.
- Tests use synthetic documentation-derived data only. No production data or credentials exist here.
- The production HTTPS transport is endpoint-bound, blocks redirects, requires certificate and
  hostname verification, and bounds request duration and response bytes -- the same posture as the
  Hitachi Ops Center candidate's transport, extended with POST support for the fault/events read.
- The transport accepts only absolute same-origin paths (plus one bounded query parameter for the
  fabric-members read) and strict JSON-object responses.
- A secret broker may provide a pre-authenticated Authorization header per request. The transport
  does not persist, log, expose, or return that header.
- Application wiring and credential brokerage remain deliberately separate from this candidate.

## Source Provenance

Reviewed against Broadcom's public SANnav Management Portal REST API documentation and a real,
independently-authored working example script (not vendor prose alone) for the endpoints that
could be fully confirmed:

- [SANnav REST API overview](https://techdocs.broadcom.com/us/en/fibre-channel-networking/sannav/management-portal-rest-api/3-0-0x/SANnav-Overview.html)
- [Working fabric/switch inventory example](https://github.com/chipcopper/SANnav-fabric-inventory/blob/master/sannav_fabric_inventory.py) --
  confirms the login header shape, the `/discovery/fabrics/` and `/discovery/fabric-members/`
  endpoints, and their exact response field names (`Fabrics`, `principalSwitchWwn`, `name`,
  `Switches`, `ipAddress`).
- [Retrieving a list of events (fault/events example)](https://techdocs.broadcom.com/us/en/fibre-channel-networking/sannav/management-portal-rest-api/3-0-0x/Python-Examples-REST-API/Retrieving-a-List-of-Events-REST-API.html) --
  confirms the `POST /external-api/v2/fault/events/` endpoint and full request body shape, but
  **not** the per-event response field names.

**Known gap, stated plainly**: the fault/events response schema (per-event severity, affected
switch, message field names) was not independently confirmed against a real SANnav instance or
Broadcom's full REST API Reference Manual PDF during construction -- see `source-provenance.json`.
`read_fabric_fault_summary()` therefore only counts events safely (checked defensively across
plausible response envelope shapes) rather than parsing unverified per-event fields. This is
stated in `client.py` and `domain.py` as code comments, not silently assumed correct.

## Promotion Requirements

1. Review the exact source version and capability mapping with a SAN fabric domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the fault/events response schema against a real, non-production SANnav instance (or
   Broadcom's authoritative schema reference) and extend `read_fabric_fault_summary()` with real
   per-event field parsing once confirmed.
4. Run contract tests against an approved non-production SANnav endpoint using a least-privileged
   read-only identity.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
