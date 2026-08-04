export type EvidenceRecord = {
  reference: string;
  source: string;
  source_version: string;
  observed_at: string;
  freshness: "current" | "aging" | "stale" | "unknown";
  trust_basis: string;
};

export type StorageAsset = {
  asset_id: string;
  storage_device_id: string;
  vendor: string;
  model: string;
  serial_number: number;
  health: "healthy" | "warning" | "critical" | "unknown";
  observed_at: string;
  evidence_references: string[];
};

export type HealthFinding = {
  finding_id: string;
  asset_id: string;
  severity: "warning" | "critical" | "unknown";
  component: string;
  summary: string;
  observed_at: string;
  evidence_references: string[];
  status: string;
};

export type StorageOverview = {
  snapshot_id: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  target_id: string;
  data_profile: string;
  generated_at: string;
  assets: StorageAsset[];
  findings: HealthFinding[];
  evidence: EvidenceRecord[];
  investigation: {
    investigation_id: string;
    title: string;
    state: "provisional" | "inconclusive" | "reviewed";
    summary: string;
    hypotheses: Array<{
      hypothesis_id: string;
      title: string;
      state: string;
      rationale: string;
      confidence_basis: string;
      evidence_references: string[];
      contradicting_evidence: string[];
    }>;
    unknowns: string[];
    next_checks: string[];
    evidence_references: string[];
    updated_at: string;
  };
  report: {
    report_id: string;
    title: string;
    generated_at: string;
    executive_summary: string;
    confirmed_facts: string[];
    provisional_findings: string[];
    unknowns: string[];
    evidence_references: string[];
    safety_notice: string;
  };
};

type StorageOverviewResponse = {
  data: StorageOverview;
  meta: {
    correlation_id: string;
    generated_at: string;
  };
};

export async function getStorageOverview(): Promise<StorageOverviewResponse> {
  const response = await apiFetch("/api/v1/storage/overview", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Storage overview request failed with ${response.status}`);
  }
  return (await response.json()) as StorageOverviewResponse;
}
import { apiFetch } from "./client";
