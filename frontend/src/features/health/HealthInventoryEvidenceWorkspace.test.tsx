import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StorageOverview } from "../../api/storage";
import HealthInventoryEvidenceWorkspace from "./HealthInventoryEvidenceWorkspace";

afterEach(cleanup);

const overview: StorageOverview = {
  snapshot_id: "snapshot.health.test",
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  target_id: "storage-array.test",
  data_profile: "synthetic_lab",
  generated_at: "2026-08-10T00:00:00Z",
  assets: [
    {
      asset_id: "asset.array-01",
      storage_device_id: "device.01",
      vendor: "Atlas Lab",
      model: "Array 01",
      serial_number: 1001,
      health: "warning",
      observed_at: "2026-08-10T00:00:00Z",
      evidence_references: ["evidence.array-01"],
    },
    {
      asset_id: "asset.array-02",
      storage_device_id: "device.02",
      vendor: "Atlas Lab",
      model: "Array 02",
      serial_number: 1002,
      health: "healthy",
      observed_at: "2026-08-10T00:00:00Z",
      evidence_references: ["evidence.array-02"],
    },
  ],
  findings: [
    {
      finding_id: "finding.test",
      asset_id: "asset.array-01",
      severity: "warning",
      component: "Controller 1",
      summary: "A bounded warning is present.",
      observed_at: "2026-08-10T00:00:00Z",
      evidence_references: ["evidence.array-01"],
      status: "open",
    },
  ],
  evidence: [
    {
      reference: "evidence.array-01",
      source: "Read-only array observation",
      source_version: "v1",
      observed_at: "2026-08-10T00:00:00Z",
      freshness: "current",
      trust_basis: "Signed synthetic lab response.",
    },
    {
      reference: "evidence.array-02",
      source: "Unselected array observation",
      source_version: "v1",
      observed_at: "2026-08-10T00:00:00Z",
      freshness: "current",
      trust_basis: "Separate signed synthetic lab response.",
    },
  ],
  investigation: {
    investigation_id: "investigation.test",
    title: "Controller warning investigation",
    state: "provisional",
    summary: "The warning remains evidence bounded.",
    hypotheses: [],
    unknowns: ["Current physical controller state"],
    next_checks: ["Repeat the approved read-only observation"],
    evidence_references: ["evidence.array-01"],
    updated_at: "2026-08-10T00:00:00Z",
  },
  report: {
    report_id: "report.test",
    title: "Storage health assessment",
    generated_at: "2026-08-10T00:00:00Z",
    executive_summary: "One bounded warning requires review.",
    confirmed_facts: ["Two arrays are in the authorized snapshot."],
    provisional_findings: ["Controller 1 may require specialist review."],
    unknowns: ["Physical controller state is not confirmed."],
    evidence_references: ["evidence.array-01"],
    safety_notice: "Decision support only. No infrastructure action is authorized.",
  },
};

describe("HealthInventoryEvidenceWorkspace", () => {
  it("presents authorized inventory and selects through the bounded callback", () => {
    const onSelectAsset = vi.fn();
    render(
      <HealthInventoryEvidenceWorkspace
        impactError={false}
        impactLoading={false}
        onSelectAsset={onSelectAsset}
        overview={overview}
        selectedAsset={overview.assets[0]}
        selectedEvidence={[overview.evidence[0]!]}
      />,
    );

    expect(screen.getByRole("region", { name: "Storage summary" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Storage systems" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Array 02/i }));
    expect(onSelectAsset).toHaveBeenCalledWith("asset.array-02");
  });

  it("shows only supplied linked evidence and keeps missing impact fail closed", () => {
    render(
      <HealthInventoryEvidenceWorkspace
        impactError
        impactLoading={false}
        onSelectAsset={vi.fn()}
        overview={overview}
        selectedAsset={overview.assets[0]}
        selectedEvidence={[overview.evidence[0]!]}
      />,
    );

    expect(screen.getByText("Read-only array observation")).toBeVisible();
    expect(screen.queryByText("Unselected array observation")).toBeNull();
    expect(
      screen.getByText(/Dependency impact is unavailable; no service impact is inferred/i),
    ).toBeVisible();
    expect(screen.getByText(/No infrastructure action is authorized/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /execute|deploy|restart|apply/i })).toBeNull();
  });
});
