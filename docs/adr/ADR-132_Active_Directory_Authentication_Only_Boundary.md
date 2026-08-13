# ADR-132: Active Directory Authentication-Only Boundary

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Owner, Security Architecture, Identity Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-020, ATLAS-030, ATLAS-031, ATLAS-047 |

## Context

Atlas requires enterprise authentication through LDAP/LDAPS or federation and may map validated
directory groups to Atlas roles. The phrase "Active Directory integration" can otherwise be read as
permission to manage directory objects or introduce an infrastructure connector for Active
Directory. That is outside the intended product boundary.

## Decision

Active Directory integration in Atlas is limited to authentication and the minimum read-only
directory queries needed to validate an identity and obtain bounded group membership for Atlas role
mapping.

Atlas will not provide an Active Directory MCP connector or any Active Directory management
capability. It will not create, update, disable, enable, delete or move directory users, groups,
computers or organizational units; change or reset passwords; modify group membership; edit Group
Policy; administer domain controllers; or execute arbitrary LDAP writes, PowerShell commands or
directory-management workflows.

Directory credentials are identity-provider credentials, not infrastructure-operation credentials.
Successful authentication creates an Atlas subject context only. It does not grant directory
administration authority and cannot be converted into an MCP target or capability.

## Allowed Behavior

- TLS-validated LDAP bind or approved federated authentication
- Bounded user lookup required for authentication
- Bounded, read-only direct or nested group resolution with explicit limits
- Stable subject and group identifier normalization
- Mapping validated groups to Atlas roles and scopes
- Authentication health checks that disclose no credentials or directory contents
- Audit of authentication outcome and normalized identity context without passwords or bind secrets

## Prohibited Behavior

- Active Directory or LDAP MCP package, instance, capability or marketplace entry
- Directory object lifecycle management or synchronization
- Password, membership, Group Policy, domain-controller or organizational-unit administration
- Arbitrary LDAP query/write, PowerShell or command execution exposed to users, agents or LLMs
- Sending directory credentials, raw attributes or search results to an LLM
- Treating an Atlas approval, workflow or chat acknowledgement as directory-write authorization

## Consequences

- AD remains an external authoritative identity provider and not managed infrastructure in Atlas.
- Identity integration can be hardened independently from the MCP framework.
- Product, architecture, prompts, marketplace and future roadmap items must not propose an AD MCP or
  directory-management feature.
- A future change to this boundary requires an explicit superseding product decision; it cannot be
  introduced as an implementation detail.

## Validation

- LDAPS authentication, certificate, timeout, bounded lookup and group-mapping tests
- Static tests that no directory write operation or AD MCP capability is registered
- Secret-redaction and model-context exclusion tests for passwords, bind credentials and raw results
- Documentation and marketplace review against this prohibited-capability list
