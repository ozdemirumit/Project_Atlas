import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorBoundedInvocation,
  getConnectorBoundedInvocationOptions,
  getConnectorBoundedInvocations,
} from "./boundedInvocations";
import {
  boundedInvocationInventoryItem as invocation,
  boundedInvocationOption as option,
} from "../features/connectors/testBoundedInvocationFixture";
import {
  invocationAuthorizationInventoryItem as authorization,
} from "../features/connectors/testInvocationAuthorizationFixture";

afterEach(() => vi.restoreAllMocks());

describe("bounded invocation API client", () => {
  it("reloads minimized immutable inventory within the exact authorization scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [invocation] }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocations({
      sourceAuthorizationId: authorization.authorization_id,
    })).resolves.toEqual([invocation]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      "source_authorization_id=" + encodeURIComponent(authorization.authorization_id),
    );
  });

  it("rejects inventory that crosses the requested authorization scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{ ...invocation, source_authorization_id: "connector-authorization.foreign" }],
      }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocations({
      sourceAuthorizationId: authorization.authorization_id,
    })).rejects.toThrow("crossed the requested authorization scope");
  });

  it("accepts exact server options including explicit stronger assurance", async () => {
    const strongerOption = { ...option, required_assurance_level: "hardware_backed" as const };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [strongerOption] }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocationOptions(authorization.authorization_id))
      .resolves.toEqual([strongerOption]);
  });

  it.each([
    ["target_address", "10.0.0.10"],
    ["command", "show health"],
    ["handler", "unsafe.handler"],
    ["input", { unsafe: true }],
    ["secret_reference_id", "secret.test"],
    ["session_handle", "session.test"],
    ["idempotency_key", "raw-key"],
    ["mfa_challenge", "unsafe"],
  ])("rejects prohibited option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocationOptions(authorization.authorization_id))
      .rejects.toThrow("unsafe evidence");
  });

  it.each([
    "source_authorization_digest",
    "package_digest",
    "required_permission",
    "invocation_policy_id",
    "invocation_policy_digest",
    "maximum_timeout_seconds",
    "maximum_output_bytes",
    "maximum_observations",
  ])("rejects an option missing exact field %s", async (field) => {
    const incomplete = { ...option } as Record<string, unknown>;
    delete incomplete[field];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [incomplete] }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocationOptions(authorization.authorization_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("posts only the selected server option coordinates and purpose", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: invocation }), { status: 201 }),
    );

    await expect(createConnectorBoundedInvocation({
      authorization,
      option,
      purpose: "Invoke one authorized read-only capability and close every ephemeral resource.",
    })).resolves.toEqual({ data: invocation });
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(
      typeof init?.body === "string" ? init.body : "{}",
    ) as Record<string, unknown>;
    expect(body).toEqual({
      schema_version: "atlas.connector-bounded-invocation-input.v1",
      source_authorization_id: option.source_authorization_id,
      source_authorization_digest: option.source_authorization_digest,
      package_digest: option.package_digest,
      invocation_policy_id: option.invocation_policy_id,
      invocation_policy_digest: option.invocation_policy_digest,
      purpose: "Invoke one authorized read-only capability and close every ephemeral resource.",
      acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome: true,
    });
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it.each([
    ["raw_output", "unsafe"],
    ["target_endpoint", "https://storage.internal"],
    ["command", "show health"],
    ["consumption_claim_id", "claim.internal"],
    ["invoked_by", "subject.internal"],
    ["purpose", "internal purpose"],
  ])("rejects non-minimized completion field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...invocation, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorBoundedInvocations({
      sourceAuthorizationId: authorization.authorization_id,
    })).rejects.toThrow("unsafe records");
  });
});
