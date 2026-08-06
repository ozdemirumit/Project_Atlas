import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorInstanceRecord } from "../../api/connectorInstances";
import { ConnectorInstanceCreationPanel } from "./ConnectorInstanceCreationPanel";
import { installationReceipt as receipt } from "./testInstallationFixture";

const record = {
  record_id: "connector-instance-record.test",
  schema_version: "atlas.connector-instance-record.v1",
  version: 1,
  source_installation_receipt_id: receipt.receipt_id,
  source_installation_receipt_digest: receipt.canonical_digest,
  organization_id: receipt.organization_id,
  environment_id: receipt.environment_id,
  package_digest: receipt.package_digest,
  connector_id: receipt.connector_id,
  release_version: receipt.release_version,
  manifest_digest: receipt.manifest_digest,
  sdk_profile: receipt.sdk_profile,
  instance_policy_id: "connector-instance-creation-policy.development",
  instance_policy_digest:
    "f26624c1e18a25c13bc8cf7d29aed3d17d1ff0d3949a47af422fe1f256fb5401",
  instance_policy_version: "version.1.0",
  instance_id: "connector-instance.test",
  instance_key: "storage-east",
  display_name: "Storage East",
  instance_state: "disabled_unconfigured",
  owner_id: "subject.connector-independent-instance-creator",
  support_group_id: "group.connector-platform-support",
  created_by: "subject.connector-independent-instance-creator",
  purpose: "Create a disabled connector instance without target or runtime authority.",
  created_at: "2026-08-06T00:00:00Z",
  canonical_digest: "8".repeat(64),
  package_published: true,
  connector_registered: true,
  package_installed: true,
  instance_created: true,
  eligible_for_configuration_governance: true,
  promotion_blocked: false,
  target_configured: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorInstanceRecord;

afterEach(() => vi.unstubAllGlobals());

describe("ConnectorInstanceCreationPanel", () => {
  it("creates only a disabled identity without target, secret, capability, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: record }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ConnectorInstanceCreationPanel installation={receipt} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name:
        /target address|endpoint|secret reference|credential|capability|network route|proxy|schedule|runtime command/i,
      }),
    ).toBeNull();
    fireEvent.change(screen.getByLabelText("Instance key"), {
      target: { value: record.instance_key },
    });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: record.display_name },
    });
    fireEvent.click(
      screen.getByLabelText(
        "The instance remains disabled and unconfigured, with no target, secret, capability, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create disabled instance" }));

    expect(await screen.findByText(record.instance_id)).toBeVisible();
    expect(screen.getByText(record.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /configure|enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_installation_receipt_id: receipt.receipt_id,
      source_installation_receipt_digest: receipt.canonical_digest,
      package_digest: receipt.package_digest,
      instance_key: record.instance_key,
      instance_policy_id: record.instance_policy_id,
      instance_policy_digest: record.instance_policy_digest,
      acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: true,
    });
    for (const forbidden of [
      "instance_id",
      "state",
      "target",
      "endpoint",
      "secret_reference",
      "credential",
      "capability",
      "proxy",
      "network_route",
      "schedule",
      "runtime",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
