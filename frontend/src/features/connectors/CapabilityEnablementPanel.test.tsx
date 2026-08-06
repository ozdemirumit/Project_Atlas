import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorCapabilityEnablement } from "../../api/capabilityEnablements";
import { CapabilityEnablementPanel } from "./CapabilityEnablementPanel";
import { configurationValidation as validation } from "./testConfigurationValidationFixture";

const profileDigest = "d".repeat(64);
const policyDigest = "3037f7c378ac3046e92be04e9b71015d63780b6ce961de131e02b13b788da438";
const enablement = {
  enablement_id: "connector-capability-enablement.test",
  schema_version: "atlas.connector-capability-enablement.v1",
  version: 1,
  source_validation_id: validation.validation_id,
  source_validation_digest: validation.canonical_digest,
  organization_id: validation.organization_id,
  environment_id: validation.environment_id,
  package_digest: validation.package_digest,
  connector_id: validation.connector_id,
  release_version: validation.release_version,
  manifest_digest: validation.manifest_digest,
  instance_id: validation.instance_id,
  instance_key: validation.instance_key,
  display_name: validation.display_name,
  owner_id: validation.owner_id,
  target_profile_id: validation.target_profile_id,
  target_profile_digest: validation.target_profile_digest,
  site_id: validation.site_id,
  target_type: validation.target_type,
  target_product: validation.target_product,
  credential_profile_id: validation.credential_profile_id,
  credential_profile_digest: validation.credential_profile_digest,
  capability_profile_id: "connector-capability-profile.development-read-only",
  capability_profile_digest: profileDigest,
  capabilities: [
    {
      capability_id: "health.read",
      capability_class: "C1",
      required_permission: "connector.health.read",
    },
  ],
  enablement_policy_id: "connector-capability-enablement-policy.development",
  enablement_policy_digest: policyDigest,
  enablement_policy_version: "policy-v1",
  enablement_version: 1,
  instance_state: "enabled_capabilities_governed",
  enabled_by: "subject.connector-capability-enabler",
  purpose: "Enable governed read-only capability metadata without runtime authority.",
  enabled_at: "2026-08-06T00:00:00Z",
  canonical_digest: "e".repeat(64),
  configuration_validated: true,
  connectivity_evidence_verified: true,
  eligible_for_capability_governance: true,
  capability_governance_applied: true,
  connector_enabled: true,
  eligible_for_runtime_trust: true,
  promotion_blocked: false,
  credentials_resolved: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorCapabilityEnablement;

afterEach(() => vi.unstubAllGlobals());

describe("CapabilityEnablementPanel", () => {
  it("enables only an exact signed manifest-bound profile without operational inputs", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: enablement }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CapabilityEnablementPanel validation={validation} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /endpoint|target ip|host|port|username|password|token|secret reference|vault|command|parameter|runtime/i,
      }),
    ).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Capability profile digest" }), {
      target: { value: profileDigest },
    });
    fireEvent.click(
      screen.getByLabelText(
        "Enablement selects only signed C0/C1 metadata and grants no secret resolution, connection, runtime trust, execution, deployment, or mutation authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Enable governed capabilities" }));

    expect(await screen.findByText(enablement.enablement_id)).toBeVisible();
    expect(screen.getByText(enablement.instance_state)).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.getByText("not authorized")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_validation_id: validation.validation_id,
      source_validation_digest: validation.canonical_digest,
      package_digest: validation.package_digest,
      capability_profile_id: enablement.capability_profile_id,
      capability_profile_digest: profileDigest,
      enablement_policy_id: enablement.enablement_policy_id,
      enablement_policy_digest: policyDigest,
      acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: true,
    });
    for (const forbidden of [
      "capabilities",
      "capability_class",
      "required_permission",
      "endpoint_url",
      "target_ip",
      "host",
      "port",
      "secret_reference_id",
      "secret_value",
      "username",
      "password",
      "access_token",
      "command",
      "parameters",
      "runtime_trust_granted",
      "execution_authorized",
      "deployment_approved",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
