import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorTargetSessionVerification,
  getConnectorTargetSessionVerificationOptions,
  getConnectorTargetSessionVerifications,
} from "./targetSessionVerifications";
import {
  targetSessionVerificationInventoryItem as verification,
  targetSessionVerificationOption as option,
} from "../features/connectors/testTargetSessionFixture";
import { runtimeActivationInventoryItem as activation } from "../features/connectors/testRuntimeActivationFixture";

afterEach(() => vi.restoreAllMocks());

describe("target session verification API client", () => {
  it("reloads minimized inventory only within the requested runtime scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [verification] }), { status: 200 }),
    );

    await expect(getConnectorTargetSessionVerifications({
      sourceRuntimeActivationId: activation.activation_id,
    })).resolves.toEqual([verification]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      `source_runtime_activation_id=${encodeURIComponent(activation.activation_id)}`,
    );
  });

  it("rejects inventory that crosses the requested runtime scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{ ...verification, source_runtime_activation_id: "connector-runtime-activation.foreign" }],
      }), { status: 200 }),
    );

    await expect(getConnectorTargetSessionVerifications({
      sourceRuntimeActivationId: activation.activation_id,
    })).rejects.toThrow("crossed the requested runtime scope");
  });

  it("accepts the exact minimized server option contract", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option] }), { status: 200 }),
    );

    await expect(getConnectorTargetSessionVerificationOptions(activation.activation_id))
      .resolves.toEqual([option]);
  });

  it.each([
    ["target_id", "target.storage-east"],
    ["target_address", "10.0.0.10"],
    ["target_hostname", "storage.internal"],
    ["target_endpoint", "https://storage.internal"],
    ["target_port", 443],
    ["credential_profile_id", "credential.test"],
    ["secret_reference_id", "secret.test"],
    ["secret_store_profile_id", "store.test"],
    ["broker_id", "broker.test"],
    ["lease_handle", "lease.test"],
    ["session_handle", "session.test"],
    ["session_token", "unsafe"],
    ["certificate_body", "unsafe"],
    ["network_route", "route.test"],
    ["command", "show storage"],
    ["raw_vendor_output", "unsafe"],
    ["protocol_transcript", "unsafe"],
    ["signature", "unsafe"],
  ])("rejects prohibited target-session option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorTargetSessionVerificationOptions(activation.activation_id))
      .rejects.toThrow("unsafe evidence");
  });

  it.each([
    ["target_id", "target.storage-east"],
    ["target_address", "10.0.0.10"],
    ["target_hostname", "storage.internal"],
    ["target_endpoint", "https://storage.internal"],
    ["credential_profile_id", "credential.test"],
    ["secret_reference_id", "secret.test"],
    ["secret_value", "unsafe"],
    ["lease_handle", "lease.test"],
    ["session_handle", "session.test"],
    ["session_expires_at", "2030-01-01T00:00:00Z"],
    ["certificate_body", "unsafe"],
    ["raw_target_response", "unsafe"],
    ["raw_vendor_output", "unsafe"],
    ["request_fingerprint", "unsafe"],
    ["idempotency_key", "unsafe"],
  ])("rejects prohibited minimized inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...verification, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorTargetSessionVerifications())
      .rejects.toThrow("unsafe records");
  });

  it("posts only the exact selected server option and bounded acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: verification }), { status: 201 }),
    );

    await expect(createConnectorTargetSessionVerification({
      activation,
      option,
      purpose: "  Verify one bounded read-only target session and close all ephemeral handles.  ",
    })).resolves.toEqual({ data: verification });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toEqual({
      schema_version: "atlas.connector-target-session-input.v1",
      source_runtime_activation_id: activation.activation_id,
      source_runtime_activation_digest: option.source_runtime_activation_digest,
      package_digest: option.package_digest,
      session_profile_id: option.session_profile_id,
      session_profile_digest: option.session_profile_digest,
      session_policy_id: option.session_policy_id,
      session_policy_digest: option.session_policy_digest,
      purpose: "Verify one bounded read-only target session and close all ephemeral handles.",
      acknowledged_bounded_session_grants_no_invocation_execution_or_deployment: true,
    });
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("rejects a response that does not match the selected signed option", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: { ...verification, session_policy_digest: "f".repeat(64) },
      }), { status: 201 }),
    );

    await expect(createConnectorTargetSessionVerification({
      activation,
      option,
      purpose: "Verify one bounded read-only target session and close all ephemeral handles.",
    })).rejects.toThrow("does not match the exact governed evidence");
  });
});
