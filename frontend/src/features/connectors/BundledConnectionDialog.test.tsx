import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getBundledConnectionConfiguration,
  saveBundledConnectionConfiguration,
  testBundledConnectorConnection,
} from "../../api/bundledConnectorConnections";
import { connectorInstanceRecord } from "./testInstanceFixture";
import { BundledConnectionDialog } from "./BundledConnectionDialog";

vi.mock("../../api/bundledConnectorConnections", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/bundledConnectorConnections")>();
  return {
    ...original,
    getBundledConnectionConfiguration: vi.fn(),
    saveBundledConnectionConfiguration: vi.fn(),
    testBundledConnectorConnection: vi.fn(),
  };
});

const configuration = {
  configuration_id: "connection_configuration.hitachi-test",
  connector_id: "connector.hitachi.opscenter.configuration-manager",
  instance_id: connectorInstanceRecord.instance_id,
  hostname: "opscenter.example.internal",
  port: 23450,
  trust_profile_id: "trust.system-ca",
  secret_reference_id: "secret.hitachi.readonly",
  configured_at: "2026-08-25T12:00:00Z",
  protocol: "https" as const,
  development_only: true as const,
  secret_material_stored: false as const,
  infrastructure_mutation_performed: false as const,
};

function renderDialog() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <BundledConnectionDialog
        instance={connectorInstanceRecord}
        onCancel={vi.fn()}
        onConfigured={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getBundledConnectionConfiguration).mockResolvedValue(null);
  vi.mocked(saveBundledConnectionConfiguration).mockResolvedValue(configuration);
  vi.mocked(testBundledConnectorConnection).mockResolvedValue({
    test_id: "connection-test.hitachi-test",
    connector_id: configuration.connector_id,
    instance_id: configuration.instance_id,
    outcome: "passed",
    result_code: "hitachi_api_compatible",
    retryable: false,
    checked_at: "2026-08-25T12:01:00Z",
    duration_ms: 42,
    read_only_request_performed: true,
    target_details_disclosed: false,
    secret_material_disclosed: false,
    managed_infrastructure_contacted: true,
    infrastructure_mutation_performed: false,
  });
});

describe("BundledConnectionDialog", () => {
  it("configures target metadata without collecting a raw secret and runs a read-only test", async () => {
    renderDialog();
    fireEvent.change(await screen.findByRole("textbox", { name: "Hostname or IP address" }), {
      target: { value: configuration.hostname },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save connection" }));

    await waitFor(() => expect(saveBundledConnectionConfiguration).toHaveBeenCalledOnce());
    expect(screen.queryByLabelText(/password|token|authorization header/i)).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(testBundledConnectorConnection).toHaveBeenCalledWith(
      connectorInstanceRecord.instance_id,
    ));
    expect(await screen.findByText("Connection passed")).toBeVisible();
    expect(screen.getByText(/hitachi api compatible/i)).toBeVisible();
  });
});
