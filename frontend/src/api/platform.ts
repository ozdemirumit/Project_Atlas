export type ComponentStatus = {
  name: string;
  status: "healthy" | "degraded" | "unavailable" | "disabled";
  required: boolean;
  code: string;
};

export type PlatformStatus = {
  service: string;
  version: string;
  environment: string;
  status: "healthy" | "degraded" | "unavailable";
  components: ComponentStatus[];
  warnings: string[];
};

type PlatformStatusResponse = {
  data: PlatformStatus;
  meta: {
    correlation_id: string;
    generated_at: string;
  };
};

export async function getPlatformStatus(): Promise<PlatformStatusResponse> {
  const response = await fetch("/api/v1/platform/status", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Platform status request failed with ${response.status}`);
  }

  return (await response.json()) as PlatformStatusResponse;
}
