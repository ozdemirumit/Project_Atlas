# Commvault CommServe Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-267/269/271. It cannot create an enabled
connector instance until the exact package digest receives domain, security, lab, and
environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `commvault.commserve.job.status.read` | C1 read-only | `GET /webservice/Job` |
| `commvault.commserve.client.inventory.read` | C1 read-only | `GET /webservice/Client` |
| `commvault.commserve.storagepolicy.inventory.read` | C1 read-only | `GET /webservice/V2/StoragePolicy`, `GET /webservice/V2/StoragePolicy/{id}?propertyLevel=10` |
| `commvault.commserve.recoverypoint.browse.read` | C1 read-only | `GET /webservice/Subclient?clientId={id}`, `GET /webservice/Subclient/{id}/Browse?path=%5C` |

The self-test reuses a narrow, one-hour-lookback job-status read (no confirmed dedicated
version/compatibility endpoint exists). One configured connector instance manages exactly one
CommServe, identified by its management endpoint -- like vCenter and both Huawei connectors,
there is nothing analogous to a per-instance `system_id` to configure here.

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
- **Session-based, like every other non-Brocade connector, with one genuine, confirmed
  difference**: Commvault's real REST API requires `POST webservice/Login` to obtain a session
  token, returned in the login response *body* (`token` field) rather than a header -- but that
  token is then presented on every subsequent request via a header literally named `Authtoken`,
  which is unlike every other connector's token header (`X-Auth-Token`,
  `vmware-api-session-id`) or `Authorization: Bearer`/`Basic` scheme. `POST webservice/Logout`
  ends it. This connector performs a complete, bounded login -> read -> logout cycle for every
  single read, and never caches or persists the session token beyond that one bounded operation.
- Application wiring and credential brokerage remain deliberately separate from this candidate.

## Source Provenance

Endpoint paths, field names, and the exact login/logout shape were confirmed directly from
Commvault's own official documentation, including a literal example JSON response:

- [Commvault REST API: Get List of Jobs](https://api.commvault.com/docs/latest/api/cv/JobOperations/get-list-of-jobs/) --
  official machine-generated reference showing the complete `jobs`/`jobSummary` response shape
  verbatim, including every field this connector reads.
- [Commvault REST API: POST Login](https://documentation.commvault.com/v11/software/rest_api_authentication_post_login.html) --
  official documentation confirming the exact login endpoint, request body, and the `token`
  response field.
- [Commvault REST API Authentication Operations: Login](https://api.commvault.com/docs/SP40/api/cv/AuthenticationOperations/login/) --
  a second, independent official source corroborating the `Authtoken` header requirement for
  subsequent requests.
- [Commvault REST API: Get Client](https://api.commvault.com/docs/latest/api/cv/ClientOperations/get-client/) --
  official machine-generated reference showing the `clientProperties` response shape
  (`client.clientEntity`); `clientProps.IsDeletedClient` and `client.osInfo.Type` are documented
  only for the single-client `GET Client/{clientId}` endpoint, not this list endpoint, and are
  therefore read defensively as optional here (see `source-provenance.json`).
- [Commvault REST API: Get Storage Policies](https://api.commvault.com/docs/SP40/api/cv/Storage/get-storage-policies/) --
  official machine-generated reference showing the `policies` list response shape
  (`numberOfStreams`, `storagePolicy.storagePolicyId/Name`); the full path (with its `V2` prefix)
  was independently corroborated from a second real source describing the same endpoint family.
- Commvault REST API Reference (official PDF, complete, "Updated Sunday, January 18, 2026") --
  supplied directly by the customer; used to re-verify this connector's documented parameter
  tables in full (not just individual reference pages), confirming the complete job-status
  vocabulary, the `IsDeletedClient`/`osInfo.Type` field-scoping nuance, the `numberOfCopies`
  field-scoping nuance and its real Details-endpoint source, and the Subclient/Browse read path
  (with a literal, complete example response for both `GET Subclient` and
  `GET Subclient/{id}/Browse`). See `supplementary_document` in `source-provenance.json`.

**Known gaps, stated plainly**: this connector models the complete, real 19-value job-status
vocabulary (confirmed directly against the official REST API reference's own "Valid values are"
table for `jobSummary.status`) -- any value genuinely outside that set still maps to `UNKNOWN`
rather than being guessed at a severity. `clientProps.IsDeletedClient` and `client.osInfo.Type`
are read defensively as optional on the Client list read: the official reference's documented
response-parameter table for that exact list endpoint does not include either field (only the
single-client `GET Client/{clientId}` endpoint's table does), confirmed further by a literal
example list response whose `clientProps` element carries only `enableAccessControl`. Similarly,
`numberOfCopies` is not part of the StoragePolicy list endpoint's documented response -- it is
read via a separate, bounded per-policy `GET StoragePolicy/{id}?propertyLevel=10` Details call
(first 25 policies), mirroring the vCenter host-to-cluster membership precedent from
ATLAS-IMP-268. The recovery-point catalog (`GET Subclient` + `GET Subclient/{id}/Browse`) is a
**small, bounded sample, not exhaustive**: the first 3 clients' first 3 subclients' first 5
root-level browse items each, chosen to avoid the client x subclient x item fan-out a full crawl
would require; its two real, documented response-shape ambiguities (a sibling `browseResponses`
entry carrying only an aggregate count, and `dataResultSet` collapsing from a list to a single
object for exactly one item) are both handled defensively rather than assumed. No cross-vendor
graph relationship (e.g. `BACKED_BY`) is asserted: no confirmed field connects a Commvault client
or policy to entities from any other connector in this project. See `source-provenance.json`'s
`unconfirmed_gaps` for the complete list.

## Promotion Requirements

1. Review the exact source version and capability mapping with a backup domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the gaps stated above -- especially the recovery-point sample's bounded scope --
   against a real, non-production CommServe before promotion.
4. Run contract tests against an approved non-production CommServe using a least-privileged,
   read-only account.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
