import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SecurityExportOverview } from "../../api/securityExport";
import SecurityExportWorkspace from "./SecurityExportWorkspace";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const overview: SecurityExportOverview = {
  generated_at: "2026-08-10T09:00:00Z",
  mapping_version: "atlas.security.v1",
  normalized_schema_version: "1.0",
  destinations: [
    {
      destination_id: "destination.test",
      version: 1,
      name: "Enterprise SIEM",
      state: "active",
      transport: "tls",
      host: "siem.example.test",
      port: 6514,
      tls_server_authentication: true,
      tls_hostname_validation: true,
      trust_reference_id: "trust.test",
      client_identity_secret_reference_id: null,
      certificate_not_after: "2027-08-10T09:00:00Z",
      facility: 16,
      selected_categories: ["audit"],
      classification_ceiling: "C2",
      max_queue_records: 1000,
      max_attempts: 3,
    },
  ],
  health: [
    {
      destination_id: "destination.test",
      state: "active",
      queue_depth: 2,
      delivered_count: 18,
      retrying_count: 1,
      dead_letter_count: 0,
      certificate_days_remaining: 365,
      last_transport_handoff_at: "2026-08-10T08:59:00Z",
      collector_acknowledgement_available: true,
      siem_ingestion_confirmed: false,
      limitations: ["Downstream SIEM indexing is not observable."],
    },
  ],
  recent_deliveries: [],
  preview_message: {
    priority: 134,
    message_id: "ATLAS_TEST",
    payload: "<134>1 2026-08-10T09:00:00Z atlas test - ATLAS_TEST - bounded preview",
    payload_bytes: 74,
    content_digest: "0123456789abcdef0123456789abcdef",
  },
  safety_notice: "Transport evidence does not authorize configuration or infrastructure change.",
};

const baseProps = {
  error: false,
  loading: false,
  onSendTestEvent: vi.fn(),
  testDelivered: false,
  testError: false,
  testPending: false,
};

describe("SecurityExportWorkspace", () => {
  it("presents explicit loading, unavailable and incomplete states", () => {
    const { rerender } = render(<SecurityExportWorkspace {...baseProps} loading />);

    expect(screen.getByText("Reading authorized export health")).toBeVisible();

    rerender(<SecurityExportWorkspace {...baseProps} error />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Export health is unavailable; no delivery is inferred.",
    );

    rerender(<SecurityExportWorkspace {...baseProps} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "A complete authorized destination and health record are required.",
    );
    expect(screen.queryByRole("button", { name: "Send test event" })).toBeNull();
  });

  it("presents bounded transport evidence and SIEM uncertainty", () => {
    render(<SecurityExportWorkspace {...baseProps} overview={overview} />);

    expect(screen.getByRole("heading", { name: "Syslog and SIEM delivery" })).toBeVisible();
    expect(screen.getByText("Enterprise SIEM")).toBeVisible();
    expect(screen.getByText("siem.example.test:6514")).toBeVisible();
    expect(screen.getByText("RFC 5424 preview")).toBeVisible();
    expect(screen.getByText("Not confirmed")).toBeVisible();
    expect(screen.getByText("Downstream SIEM indexing is not observable.")).toBeVisible();
    expect(screen.getByText(/does not authorize configuration or infrastructure change/)).toBeVisible();
  });

  it("delegates only the bounded test-event request", () => {
    const onSendTestEvent = vi.fn();
    render(
      <SecurityExportWorkspace
        {...baseProps}
        onSendTestEvent={onSendTestEvent}
        overview={overview}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Send test event" }));

    expect(onSendTestEvent).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: /configure|restart|deploy/i })).toBeNull();
  });

  it("keeps pending, success and failure outcomes explicit", () => {
    const { rerender } = render(
      <SecurityExportWorkspace {...baseProps} overview={overview} testPending />,
    );

    expect(screen.getByRole("button", { name: "Sending" })).toBeDisabled();

    rerender(<SecurityExportWorkspace {...baseProps} overview={overview} testDelivered />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Transport handoff recorded. SIEM ingestion remains unconfirmed.",
    );

    rerender(<SecurityExportWorkspace {...baseProps} overview={overview} testError />);
    expect(screen.getByRole("alert")).toHaveTextContent("Test event was not delivered.");
  });
});

