import { afterEach, describe, expect, it, vi } from "vitest";

import { getTechnicalReport } from "./reports";

afterEach(() => vi.unstubAllGlobals());

describe("technical report recovery client", () => {
  it("loads the exact encoded report without mutation authority", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            report_id: "report:technical/unsafe",
            execution_authorized: false,
            external_mutation_authorized: false,
          },
          meta: { correlation_id: "cor-report-read", generated_at: "2026-08-13T12:00:00Z" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getTechnicalReport("report:technical/unsafe");

    expect(result.data.execution_authorized).toBe(false);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/reports/report%3Atechnical%2Funsafe");
    expect(init.method).toBeUndefined();
    expect(init.body).toBeUndefined();
  });

  it("fails closed when the report cannot be recovered", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 409 })));

    await expect(getTechnicalReport("report.missing")).rejects.toThrow(
      "Technical report unavailable",
    );
  });
});
