# MCP

This directory contains connector-facing framework assets, SDK material, validation fixtures, and
vendor connector packages as they are introduced.

The accepted foundation implementation currently lives in the backend modular-monolith boundary at
`backend/src/atlas/modules/connectors` and includes:

- immutable package registration with retained validation reports;
- C0 informational and C1 read-only capability enforcement;
- organization, environment, site, target, and package-scoped connector instances;
- disabled-by-default lifecycle with trusted self-test enablement;
- audited capability discovery; and
- a deterministic simulator with no network, secret, filesystem, or subprocess access.

Vendor-specific connector packages will be added here only after passing the framework validation and
quarantine requirements defined by ATLAS-020, ATLAS-021, ATLAS-022, and ATLAS-047.

Current candidates:

- [Hitachi Ops Center API Configuration Manager](connectors/hitachi_ops_center/README.md) -
  quarantined C1 inventory and hardware-health candidate using synthetic data only.
- [Brocade SANnav Management Portal](connectors/brocade_sannav/README.md) -
  quarantined C1 fabric-inventory and fault-summary candidate using synthetic data only.
