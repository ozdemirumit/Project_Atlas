import { afterEach, expect, it, vi } from "vitest";

import { apiFetch } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "atlas_csrf=; Max-Age=0; path=/";
});

it("adds the CSRF cookie only to unsafe same-origin requests", async () => {
  document.cookie = "atlas_csrf=csrf_reload_safe; path=/; SameSite=Strict";
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(null, { status: 204 }));

  await apiFetch("/api/v1/identity/me");
  await apiFetch("/api/v1/security-export/test-event", { method: "POST" });

  const safeHeaders = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
  const unsafeHeaders = new Headers(fetchMock.mock.calls[1]?.[1]?.headers);
  expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe("same-origin");
  expect(safeHeaders.has("X-CSRF-Token")).toBe(false);
  expect(unsafeHeaders.get("X-CSRF-Token")).toBe("csrf_reload_safe");
});

it("rejects cross-origin requests before sending CSRF material", async () => {
  document.cookie = "atlas_csrf=csrf_must_not_leave_origin; path=/; SameSite=Strict";
  const fetchMock = vi.spyOn(globalThis, "fetch");

  await expect(apiFetch("https://outside.example/api", { method: "POST" })).rejects.toMatchObject({
    status: 0,
  });
  expect(fetchMock).not.toHaveBeenCalled();
});
