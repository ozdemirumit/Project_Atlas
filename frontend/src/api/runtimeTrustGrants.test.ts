import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorRuntimeTrustGrant,
  getConnectorRuntimeTrustGrantOptions,
  getConnectorRuntimeTrustGrants,
} from "./runtimeTrustGrants";
import { capabilityEnablementInventoryItem as enablement } from "../features/connectors/testCapabilityEnablementFixture";
import {
  runtimeTrustGrantInventoryItem as grant,
  runtimeTrustGrantOption as option,
} from "../features/connectors/testRuntimeTrustFixture";

afterEach(() => vi.restoreAllMocks());

describe("runtime trust API client", () => {
  it("reloads minimized inventory only within the requested enablement scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [grant] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeTrustGrants({ sourceEnablementId: enablement.enablement_id }))
      .resolves.toEqual([grant]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      `source_enablement_id=${encodeURIComponent(enablement.enablement_id)}`,
    );
  });

  it.each([
    ["signature", "unsafe"],
    ["secret_reference_id", "secret.test"],
    ["target_hostname", "storage.internal"],
    ["command", "show storage"],
    ["mutable_runner_configuration", { privileged: true }],
  ])("rejects unknown runtime option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeTrustGrantOptions(enablement.enablement_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("posts only the exact server-selected profile and policy", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: grant }), { status: 201 }),
    );

    await createConnectorRuntimeTrustGrant({
      enablement,
      option,
      purpose: "Bind the exact signed runtime boundary without operational authority.",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_enablement_id: enablement.enablement_id,
      source_enablement_digest: option.source_enablement_digest,
      package_digest: option.package_digest,
      runtime_profile_id: option.runtime_profile_id,
      runtime_profile_digest: option.runtime_profile_digest,
      trust_policy_id: option.trust_policy_id,
      trust_policy_digest: option.trust_policy_digest,
      acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: true,
    });
    for (const forbidden of [
      "runner_runtime_id", "runner_pool_id", "runner_image_digest", "runner_workload_identity_id",
      "isolation_profile_id", "filesystem_policy_id", "egress_policy_id",
      "secret_delivery_policy_id", "target_profile_id", "credential_profile_id", "command",
      "parameters", "execution_authorized", "deployment_approved",
    ]) expect(body).not.toHaveProperty(forbidden);
  });

  it("fails closed on cross-scope or authority-expanded inventory", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{ ...grant, source_enablement_id: "connector-capability-enablement.outside" }],
      }), { status: 200 }),
    );
    await expect(getConnectorRuntimeTrustGrants({ sourceEnablementId: enablement.enablement_id }))
      .rejects.toThrow("crossed the requested enablement scope");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ data: [{ ...grant, execution_authorized: true }] }), { status: 200 }),
    );
    await expect(getConnectorRuntimeTrustGrants()).rejects.toThrow("unsafe records");
  });
});
