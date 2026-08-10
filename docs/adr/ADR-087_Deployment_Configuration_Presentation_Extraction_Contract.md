# ADR-087: Deployment Configuration Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-038, ATLAS-047, ATLAS-050, ATLAS-052,
  ATLAS-053, ATLAS-055, ATLAS-056, ATLAS-057, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086

## Context

IMP-130 extracted Release Preflight and reduced the transitional operational chunk to 826.14 KB.
The next contiguous read-only surface is the approximately 70-line Deployment Configuration
Preview. It shows deterministic redacted effective fields, source attribution, schema and digest
identity, and validation gates before any host mutation.

The preview query is composed from authorized identity scope and the selected release profile. The
panel itself does not own overlay inputs, secret resolution, file rendering, provisioning, port
changes, installation or service execution.

## Decision

Atlas will extract Deployment Configuration Preview presentation into a dedicated static lazy
Health feature. The parent retains the authorized query, identity scope, release profile and all
downstream bootstrap composition. It supplies one validated immutable preview.

### Presentation Ownership

- `DeploymentConfigurationWorkspace` owns profile/environment/schema/digest identity, effective
  field display, source labels, validation state, remediation and the preview-only safety notice.
- The feature owns no API client, React Query cache, identity, RBAC, overlay, secret manager, file,
  network, deployment, bootstrap or execution authority.
- Fields render only server-produced `display_value`. The feature never resolves a secret reference,
  requests plaintext or derives an unredacted value.

### Authorization And Loading Contract

- The feature uses one static local import and mounts only while Health is active and an authorized,
  schema-valid preview exists.
- A forbidden, malformed or absent preview remains absent and discloses no configuration metadata.
- Connector routes must not download, evaluate or mount the feature.
- The parent query remains authoritative for profile, identity scope, tenant isolation, validation
  and downstream plan invalidation/refetch behavior.

### Evidence And Authority Contract

- Field paths, redacted display values, source labels, validation evidence, remediation, schema and
  digests are server-produced immutable evidence.
- `mutation_authorized` and `execution_authorized` remain false and cannot be elevated by the
  presentation.
- A passed preview grants no file write, secret provisioning, port change, installation, service
  execution, bootstrap lease, phase execution or infrastructure mutation.

### Verification

- Focused tests cover configuration identity, redacted sensitive display, field source, validation,
  remediation, no-authority language and absence of mutation commands.
- Existing application tests preserve authorized preview composition and forbidden/malformed
  absence.
- ESLint, TypeScript, full Vitest and production build pass with a separate feature chunk.
- Live desktop/mobile checks cover evidence, overflow, route isolation and final application logs.

## Consequences

### Positive

- Configuration evidence gains one independently testable and loadable presentation owner.
- Secret-redaction and no-write boundaries remain explicit.
- The operational module shrinks without moving bootstrap authority.

### Costs

- Query and selected profile remain in the transitional parent.
- Bootstrap Plan and stateful Bootstrap workflow still require separate ownership decisions.

## Rejected Alternatives

### Move Preview Query Into The Feature

Rejected because identity scope, profile composition, cache invalidation and downstream bootstrap
planning are larger than presentation extraction requires.

### Resolve Secret References For Display

Rejected because configuration preview is a redacted evidence boundary and presentation has no
plaintext-secret purpose or authority.

### Extract Configuration And Bootstrap Execution Together

Rejected because deterministic preview and lease-bound phase mutation have different authorization,
audit and recovery contracts.

## Follow-Up

Extract the read-only Bootstrap Plan presentation, then design stateful Bootstrap workflow ownership
around lease, intent, exact-version, audit and recovery contracts.
