import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorTargetConfigurationBinding } from "../../api/targetConfigurations";
import { TargetConfigurationPanel } from "./TargetConfigurationPanel";
import { connectorInstanceRecord as instance } from "./testInstanceFixture";

const binding = {
  binding_id: "connector-target-configuration-binding.test",
  schema_version: "atlas.connector-target-configuration-binding.v1",
  version: 1,
  source_instance_record_id: instance.record_id,
  source_instance_record_digest: instance.canonical_digest,
  organization_id: instance.organization_id,
  environment_id: instance.environment_id,
  package_digest: instance.package_digest,
  connector_id: instance.connector_id,
  release_version: instance.release_version,
  manifest_digest: instance.manifest_digest,
  instance_id: instance.instance_id,
  instance_key: instance.instance_key,
  display_name: instance.display_name,
  owner_id: instance.owner_id,
  target_profile_id: "connector-target-profile.development-storage",
  target_profile_digest:
    "ac24f2f42d0e4abb3bc1cc88786c703aea9b1402694864b6fba59dedd946d8b1",
  site_id: "site.development-primary",
  target_type: "storage-array",
  target_product: "Synthetic Storage",
  target_version: "version.1.0",
  configuration_policy_id: "connector-target-configuration-policy.development",
  configuration_policy_digest:
    "65f94e1f98af78dd52245ccd1da1f841aeb3ac89511fcea69eb9c594143a4a2d",
  configuration_policy_version: "version.1.0",
  configuration_version: 1,
  instance_state: "disabled_target_configured",
  bound_by: "subject.connector-independent-target-configurator",
  purpose: "Bind signed target configuration without runtime authority.",
  bound_at: "2026-08-06T00:00:00Z",
  canonical_digest: "9".repeat(64),
  package_installed: true,
  instance_created: true,
  target_configured: true,
  eligible_for_credential_governance: true,
  promotion_blocked: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorTargetConfigurationBinding;

afterEach(() => vi.unstubAllGlobals());

describe("TargetConfigurationPanel", () => {
  it("binds only exact governed profile and policy evidence without target internals", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: binding }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <TargetConfigurationPanel instance={instance} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /endpoint|address|host|port|certificate|trust|route|proxy|secret|credential/i,
      }),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Binding grants no credential, capability, enablement, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Bind governed target" }));

    expect(await screen.findByText(binding.binding_id)).toBeVisible();
    expect(screen.getByText(binding.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_instance_record_id: instance.record_id,
      source_instance_record_digest: instance.canonical_digest,
      package_digest: instance.package_digest,
      target_profile_id: binding.target_profile_id,
      target_profile_digest: binding.target_profile_digest,
      configuration_policy_id: binding.configuration_policy_id,
      configuration_policy_digest: binding.configuration_policy_digest,
      acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority: true,
    });
    for (const forbidden of [
      "endpoint",
      "endpoint_origin",
      "target_id",
      "host",
      "port",
      "certificate",
      "trust_profile_id",
      "network_route_profile_id",
      "proxy_profile_id",
      "secret_reference",
      "credential",
      "capability",
      "runtime",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
