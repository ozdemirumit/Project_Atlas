# Commvault CommServe Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-267. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `commvault.commserve.job.status.read` | C1 read-only | `GET /webservice/Job` |

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

**Known gaps, stated plainly**: Commvault's own documentation states its complete job-status
vocabulary is longer than what could be independently confirmed via real, working examples during
connector construction, so this connector only models the values directly evidenced
(`Completed`, `Running`, `Waiting`, `Suspended`, `Killed`); any other value maps to `UNKNOWN`
rather than being guessed at a severity. Client inventory, backup/storage policy, and
recovery-point catalog concepts are real, confirmed Commvault domain areas this first pass does
not implement -- only the job-status health signal was built. See `source-provenance.json`'s
`unconfirmed_gaps` for the complete list.

## Promotion Requirements

1. Review the exact source version and capability mapping with a backup domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the full job-status vocabulary and the gaps stated above against a real, non-production
   CommServe (or Commvault's authoritative REST API reference) before promotion.
4. Run contract tests against an approved non-production CommServe using a least-privileged,
   read-only account.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
