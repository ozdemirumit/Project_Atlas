# Huawei OceanStor Dorado Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-262. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `huawei.dorado.storage.system.read` | C1 read-only | `GET /deviceManager/rest/{system_id}/system/` |
| `huawei.dorado.storage.controller.read` | C1 read-only | `GET /deviceManager/rest/{system_id}/controller` |
| `huawei.dorado.storage.pool.read` | C1 read-only | `GET /deviceManager/rest/{system_id}/storagepool` |

The self-test reuses the system-identity read (no confirmed dedicated version/compatibility
endpoint exists). One configured connector instance manages exactly one Dorado system, identified
by the `system_id` embedded in every request URL -- unlike Hitachi's single Configuration Manager
that fronts many arrays, there is no multi-target allowlist here.

## Safety Boundary

- The connector receives a pre-authenticated credential reference from the isolated runner; it
  never receives a raw username or password from any caller.
- Connector code cannot resolve, serialize, log, or return credentials.
- Collection count, response byte size, and the target system identifier are bounded.
- Malformed, timeout, permission, throttle, and unavailable results remain distinct.
- Tests use synthetic documentation-derived data only. No production data or credentials exist here.
- The production HTTPS transport is endpoint-bound, blocks redirects, requires certificate and
  hostname verification, and bounds request duration and response bytes -- the same posture as the
  Hitachi Ops Center and Brocade SANnav candidates' transports.
- **Different from every other connector in this codebase**: OceanStor's real REST API is
  session-based, not a static per-request header. A credential broker may provide a
  `username:password` pair; the transport performs a complete, bounded login -> read -> logout
  cycle for every single read, and never caches or persists the session token or cookie beyond
  that one bounded operation. See `client.py`/`https.py`/`ports.py` for the full rationale.
- Application wiring and credential brokerage remain deliberately separate from this candidate.

## Source Provenance

Reviewed against Huawei's public OceanStor Dorado 6.1.0 REST Interface Reference. Individual
TechDocs pages returned empty content via automated fetch during connector construction (mirroring
the difficulty found building the Brocade SANnav candidate), so field names and request/response
shapes were confirmed against two independent, real, working sources instead of vendor prose
alone:

- [OceanStor Dorado 6.1.0 REST Interface Reference](https://support.huawei.com/enterprise/en/doc/EDOC1100144155)
- [A real working OceanStor monitoring script](https://github.com/tcomerma/check_oceanstor/blob/master/OceanStor.py) --
  confirms the base URL structure, the session login/logout endpoint and request shape, the
  `{"error": ..., "data": ...}` response envelope, and the `/system/` and `/storagepool` endpoints
  and their exact field names.
- [A maintained Icinga/Nagios OceanStor Dorado monitoring-plugin description](https://docs.linuxfabrik.ch/monitoring-plugins/huawei-dorado-controller.html) --
  confirms the `/controller` endpoint and its field names, and the HEALTHSTATUS numeric code
  meanings this connector relies on.

**Known gap, stated plainly**: no confirmed pool identifier field exists on the `/storagepool`
response in either source used, so this connector reuses the pool's `NAME` field as its identity
rather than trusting an unconfirmed `ID` field. No configured capacity warning/depletion threshold
field exists on that object either (unlike Hitachi's `/pools`), so utilization is computed from
raw capacity and the health-check definition's own fixed threshold policy is applied, not a value
read from the array. This is stated in `domain.py`'s `HuaweiPoolCapacity.used_capacity_percent`
docstring and `source-provenance.json`, not silently assumed correct.

## Promotion Requirements

1. Review the exact source version and capability mapping with a storage domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the pool identity and capacity-threshold gaps above against a real, non-production
   Dorado instance (or Huawei's authoritative field reference) before promotion.
4. Run contract tests against an approved non-production Dorado endpoint using a
   least-privileged, read-only OceanStor account.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
