# VMware vCenter Server Connector Candidate

## Status

`Quarantined` generated candidate for ATLAS-IMP-266. It cannot create an enabled connector
instance until the exact package digest receives domain, security, lab, and environment approval.

## Supported Candidate Capabilities

| Capability | Class | Vendor request |
| --- | --- | --- |
| `vmware.vcenter.host.inventory.read` | C1 read-only | `GET /api/vcenter/host` |
| `vmware.vcenter.cluster.inventory.read` | C1 read-only | `GET /api/vcenter/cluster` |
| `vmware.vcenter.vm.inventory.read` | C1 read-only | `GET /api/vcenter/vm` |

The self-test reuses the host-inventory read (no confirmed dedicated version/compatibility
endpoint exists). One configured connector instance manages exactly one vCenter Server,
identified by its management endpoint -- like both Huawei connectors, there is nothing analogous
to a per-instance `system_id` to configure here.

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
- **Session-based, like both Huawei connectors, not like Hitachi or Brocade**: vCenter's real
  Automation API requires `POST /api/session` (HTTP Basic auth, empty body) to obtain a session
  token, presented as the `vmware-api-session-id` header on every subsequent request, and
  `DELETE /api/session` to end it. This connector performs a complete, bounded
  login -> read -> logout cycle for every single read, and never caches or persists the session
  token beyond that one bounded operation. **One real, confirmed difference from every prior
  connector**: the session token is returned in the `vmware-api-session-id` *response header*, not
  in a JSON response body -- confirmed directly from Broadcom's own official documentation's
  working curl example.
- Application wiring and credential brokerage remain deliberately separate from this candidate.

## Source Provenance

Endpoint paths and field names were confirmed directly from VMware's own generated Python client
source and official documentation, not vendor prose alone:

- [VMware vSphere Automation REST API Programming Guide 8.0](https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-sdks-tools/8-0/vmware-vsphere-automation-rest-programming-guide-8-0.html) --
  official Broadcom reference.
- [REST Access to vSphere APIs](https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-sdks-tools/8-0/an-introduction-getting-started-with-vsphere-apis-and-sdks-8-0/getting-started-with-vsphere-apis-and-sdks/rest-access-to-vsphere-apis.html) --
  confirms the exact `POST /api/session` curl example and the `vmware-api-session-id` response
  header, read directly rather than assumed.
- [VMware's own generated Python client source (`com.vmware.vcenter_client`)](https://vmware.github.io/vsphere-automation-sdk-python/vsphere/6.5/_modules/com/vmware/vcenter_client.html) --
  confirms `Host.Summary`/`Host.FilterSpec` and `Cluster.Summary`/`Cluster.FilterSpec` field names
  and the `Host.ConnectionState`/`Host.PowerState` enum members exactly.
- [Ansible's official `vmware.vmware_rest` collection documentation](https://docs.ansible.com/ansible/latest/collections/vmware/vmware_rest/vcenter_vm_info_module.html) --
  the `VM.Summary` class body could not be located in the fetched client-source excerpt (the
  vcenter_client.py source file's automated fetch was truncated before reaching it), so the VM
  field set (`vm`, `name`, `power_state`, `cpu_count`, `memory_size_MiB`) was independently
  confirmed here instead, since this module's documentation is machine-generated from the same
  real vSphere Automation API definitions and includes a literal example response.

**Known gaps, stated plainly**: no confirmed field on any list response (host, cluster, or VM
summary) carries a parent-cluster or running-host identifier, so this connector's graph adapter
does not assert host-to-cluster or VM-to-host relationships -- only entities. Datastore, network,
and resource-pool inventory are real, confirmed endpoints not implemented in this first pass. See
`source-provenance.json`'s `unconfirmed_gaps` for the complete list.

## Promotion Requirements

1. Review the exact source version and capability mapping with a virtualization domain owner.
2. Validate the package digest, dependency inventory, network destination, and certificate policy.
3. Confirm the session response-header behavior and the gaps stated above against a real,
   non-production vCenter Server before promotion.
4. Run contract tests against an approved non-production vCenter endpoint using a
   least-privileged, read-only account.
5. Compare sanitized lab responses with the synthetic fixtures and document schema differences.
6. Complete security review and explicit environment approval before package promotion.
