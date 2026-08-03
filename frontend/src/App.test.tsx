import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const platformResponse = {
  data: {
    service: "atlas-api",
    version: "0.1.0",
    environment: "test",
    status: "healthy",
    components: [],
    warnings: [],
  },
  meta: {
    correlation_id: "test-correlation",
    generated_at: "2026-08-03T10:00:00Z",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Atlas application shell", () => {
  it("shows the governed operations workspace and platform status", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(platformResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Infrastructure investigation" })).toBeVisible();
    expect(screen.getByText("Human decision required")).toBeVisible();
    expect(await screen.findByText("test")).toBeVisible();
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
  });
});
