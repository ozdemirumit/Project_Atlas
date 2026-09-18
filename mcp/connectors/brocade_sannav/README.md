# Brocade SANnav Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-261. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `brocade.sannav.fabric.inventory.read` | C1 read-only | `GET /external-api/v1/discovery/fabrics/`, `GET /external-api/v1/discovery/fabric-members/` |
| `brocade.sannav.fabric.health.read` | C1 read-only | `POST /external-api/v2/fault/events/` (bounded time window, scoped to one fabric via `eventProductDetails`) |

The self-test and connection-test probe both call `GET /external-api/v1/about/` (SANnav's
version/compatibility endpoint, introduced in v2.3.1) and confirm the response identifies a
compatible SANnav Management Portal instance -- mirroring the Hitachi Ops Center candidate's own
dedicated version check exactly. No login/logout, session mutation, zoning, configuration change,
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

Reviewed against Broadcom's authoritative **SANnav Management Portal REST API Reference Manual,
v3.0.1x** (publication SANnav-301x-REST-API-RM100, March 26, 2026) and, for the two inventory
endpoints, also against a real, independently-authored working example script:

- SANnav Management Portal REST API Reference Manual, v3.0.1x (SANnav-301x-REST-API-RM100) --
  the vendor's full, authoritative schema reference. Confirms every endpoint and response
  envelope this connector uses, including the request/response shape for the fault/events read
  and the existence of a dedicated version/compatibility endpoint (`GET /external-api/v1/about/`).
- [Working fabric/switch inventory example](https://github.com/chipcopper/SANnav-fabric-inventory/blob/master/sannav_fabric_inventory.py) --
  independently confirms the login header shape, the `/discovery/fabrics/` and
  `/discovery/fabric-members/` endpoints, and their exact response field names (`Fabrics`,
  `principalSwitchWwn`, `name`, `Switches`, `ipAddress`) against a real instance, not vendor prose
  alone.

**A real bug found and fixed during reconciliation against the authoritative manual**: the
`POST /external-api/v2/fault/events/` request body previously scoped events to a fabric using an
`ORIGIN`-column filter with the switch WWN as its value -- but `ORIGIN`'s documented values are
event-source labels (`"Syslog Message"`, `"SNMP Trap"`, ...), never a WWN, so that filter never
matched anything real. The manual's own worked example confirms the correct field is the
top-level `eventProductDetails` array of virtual switch WWNs; `read_fabric_fault_summary()` now
uses that instead. The response-envelope guess (checking `"events"`/`"Events"`/`"data"`/`"Data"`/
`"totalCount"` defensively) is also gone: the manual's `FaultEventsResponse` schema confirms the
real shape is a top-level `"events"` array plus a `"totalRecords"` total count.

**Known gap that remains, stated plainly**: per-event severity is still not parsed. The manual's
own worked example returns a `severityGroup` value (`"MAJOR"`) that does not appear in its own
declared `SeverityGroup` enum (`ALL`/`ALERT`/`ERROR`/`WARNING`/`INFO`/`UNKNOWN`) -- that specific
vocabulary is internally inconsistent even in Broadcom's authoritative reference, so
`read_fabric_fault_summary()` still only counts events rather than classifying them by severity.
This is stated in `client.py` and `domain.py` as code comments, not silently assumed correct.

## Promotion Requirements

1. Review the exact source version and capability mapping with a SAN fabric domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Resolve the `severityGroup` vocabulary inconsistency with Broadcom (or verify it live against a
   real SANnav instance) and extend `read_fabric_fault_summary()` with real per-severity
   classification once resolved.
4. Run contract tests against an approved non-production SANnav endpoint using a least-privileged
   read-only identity.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
