import { afterEach, describe, expect, it, vi } from "vitest";

import { getPlatformStatus } from "./platform";

function responseWithPosture(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      service: "atlas-api",
      version: "0.1.0",
      environment: "test",
      status: "healthy",
      components: [],
      warnings: [],
      operational_posture: {
        contract_id: "platform-posture.advisory-only",
        contract_version: "1.0.0",
        platform_mode: "advisory_only",
        operational_execution_enabled: false,
        process_resume_consumption_enabled: false,
        dispatch_enabled: false,
        infrastructure_mutation_enabled: false,
        ai_execution_authorized: false,
        contract_digest: "edfde9fc024bab918b587740e23d96e95f8dc3329e8e34f28897dad590c212c1",
        ...overrides,
      },
    },
    meta: { correlation_id: "cor_test", generated_at: "2026-08-21T00:00:00Z" },
  };
}

describe("platform status advisory-only contract", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts the immutable advisory-only posture", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(responseWithPosture()), { status: 200 }),
    );

    const response = await getPlatformStatus();

    expect(response.data.operational_posture.platform_mode).toBe("advisory_only");
  });

  it.each([
    "operational_execution_enabled",
    "process_resume_consumption_enabled",
    "dispatch_enabled",
    "infrastructure_mutation_enabled",
    "ai_execution_authorized",
  ])("rejects enabled %s", async (field) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(responseWithPosture({ [field]: true })), { status: 200 }),
    );

    await expect(getPlatformStatus()).rejects.toThrow("advisory-only contract");
  });

  it("rejects a substituted contract digest", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify(responseWithPosture({ contract_digest: "a".repeat(64) })),
        { status: 200 },
      ),
    );

    await expect(getPlatformStatus()).rejects.toThrow("advisory-only contract");
  });
});
