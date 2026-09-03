# Huawei OceanStor Pacific Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-264. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `huawei.pacific.storage.cluster.read` | C1 read-only | `GET /api/v2/cluster/servers` |
| `huawei.pacific.storage.pool.read` | C1 read-only | `GET /api/v2/data_service/storagepool` |

The self-test reuses the cluster-node discovery read (no confirmed dedicated
version/compatibility endpoint exists). One configured connector instance manages exactly one
Pacific cluster, identified by its management endpoint -- unlike Dorado, Pacific's confirmed
endpoints carry no per-system path segment, so there is nothing analogous to a `system_id` to
configure here.

## Safety Boundary

- The connector receives a pre-authenticated credential reference from the isolated runner; it
  never receives a raw username or password from any caller.
- Connector code cannot resolve, serialize, log, or return credentials.
- Collection count and response byte size are bounded.
- Malformed, timeout, permission, throttle, and unavailable results remain distinct.
- Tests use synthetic documentation-derived data only. No production data or credentials exist here.
- The production HTTPS transport is endpoint-bound, blocks redirects, requires certificate and
  hostname verification, and bounds request duration and response bytes -- the same posture as
  every other candidate in this project.
- **Session-based, like Huawei Dorado, not like Hitachi or Brocade**: Pacific's real cluster-manager
  REST API requires `POST /api/v2/aa/sessions` to obtain a token, presented as `X-Auth-Token` on
  every subsequent request, and `DELETE /api/v2/aa/sessions` to end it. This connector performs a
  complete, bounded login -> read -> logout cycle for every single read, and never caches or
  persists the session token beyond that one bounded operation. Simpler than Dorado in one
  respect: Pacific's confirmed auth needs only a header token, no cookie.
- Application wiring and credential brokerage remain deliberately separate from this candidate.

## Source Provenance

Huawei's own TechDocs and administrator-guide pages returned empty content or HTTP 403 via
automated fetch during connector construction (the same difficulty found building the Dorado
candidate), so this connector's endpoints and field names were confirmed against two independent,
real, actively maintained, open-source sources instead of vendor prose alone:

- [OceanStor Pacific 8.1.0 product documentation](https://support.huawei.com/enterprise/en/doc/EDOC1100194144) --
  general product reference; specific REST endpoint pages were not fetchable during construction.
- [A real, maintained Icinga/Nagios check-plugin for cluster nodes](https://github.com/Linuxfabrik/monitoring-plugins/blob/main/check-plugins/huawei-pacific-node/huawei-pacific-node) --
  confirms `GET /api/v2/cluster/servers` and its node field names.
- [The same project's storage-pool check-plugin](https://github.com/Linuxfabrik/monitoring-plugins/blob/main/check-plugins/huawei-pacific-storagepool/huawei-pacific-storagepool) --
  confirms `GET /api/v2/data_service/storagepool` and its pool field names.
- [The shared huawei_pacific.py library backing both plugins](https://raw.githubusercontent.com/Linuxfabrik/lib/main/huawei_pacific.py) --
  confirms the exact login/logout request and response shape, and the exact `running_status`
  string values and pool `status` numeric-code mapping this connector relies on.

**Known gaps, stated plainly**: no default management port was confirmed for Pacific (unlike
Dorado's documented 8088), so this candidate's configuration schema requires the port to be set
explicitly rather than guessing one. A separate, real FusionStorage/DSware block-storage REST API
family also exists (used by the official OpenStack Cinder driver, under `/api/v1/`, with
endpoints like `/storagePool` and `/volume/create`) -- it was found and read during construction
but deliberately not used here, because the `/api/v2/` cluster-manager family is the one with
confirmed health/status fields relevant to this project's read-only monitoring purpose. See
`source-provenance.json`'s `unconfirmed_gaps` for the complete list, including `oam_agent_status`
and `warranty_status`, which this connector surfaces as informational-only observations since
their value vocabulary (unlike `running_status`'s) was never independently confirmed.

## Promotion Requirements

1. Review the exact source version and capability mapping with a storage domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the default management port and the gaps stated above against a real, non-production
   Pacific cluster (or Huawei's authoritative REST API reference) before promotion.
4. Run contract tests against an approved non-production Pacific endpoint using a
   least-privileged, read-only account.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
