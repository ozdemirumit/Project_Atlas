import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createBundledConnectorInstance,
  getBundledConnectorCatalog,
  type BundledConnectorDescriptor,
} from "./bundledConnectorCatalog";

const descriptor = {
  catalog_item_id: "catalog.connector.hitachi.opscenter",
  schema_version: "atlas.bundled-connector-descriptor.v1",
  version: 1,
  connector_id: "connector.hitachi.opscenter",
  display_name: "Hitachi Ops Center API Configuration Manager",
  vendor_name: "Hitachi Vantara",
  release_version: "version.0.1.0",
  sdk_profile: "atlas.python312.v1",
  capability_ids: ["capability.hitachi.inventory"],
  capability_classes: ["C1"],
  canonical_digest: "a".repeat(64),
  trusted_bundled: true,
  development_only: true,
  catalog_evidence_only: true,
  target_authority_granted: false,
  credential_authority_granted: false,
  capability_authority_granted: false,
  network_authority_granted: false,
  runtime_authority_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies BundledConnectorDescriptor;

const instance = {
  record_id: "connector-instance-record.test",
  version: 1,
  organization_id: "organization.development",
  environment_id: "environment.development",
  connector_id: descriptor.connector_id,
  release_version: descriptor.release_version,
  instance_id: "connector-instance.test",
  instance_key: "hitachi-opscenter-01",
  display_name: "Hitachi Ops Center 01",
  instance_state: "disabled_unconfigured",
  purpose: "Create a disabled connector for configuration.",
  created_at: "2026-08-25T12:00:00Z",
  canonical_digest: "b".repeat(64),
  eligible_for_configuration_governance: true,
  target_configured: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} as const;

afterEach(() => vi.unstubAllGlobals());

describe("bundled connector catalog API", () => {
  it("lists the bounded development catalog", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: [descriptor] }))));
    await expect(getBundledConnectorCatalog()).resolves.toEqual([descriptor]);
  });

  it("creates a disabled unconfigured connector instance", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: instance }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(createBundledConnectorInstance({
      descriptor,
      instanceKey: instance.instance_key,
      displayName: instance.display_name,
      purpose: instance.purpose,
    })).resolves.toEqual(instance);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toContain('"acknowledged_instance_is_disabled_and_grants_no_authority":true');
  });
});
