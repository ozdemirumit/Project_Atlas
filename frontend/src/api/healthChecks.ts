export type HealthCheckDefinition = {
  definition_id: string;
  version: number;
  title: string;
  owner: string;
  enabled: boolean;
  target_id: string;
  connector_id: string;
  connector_version: string;
  capability_id: string;
  capability_class: string;
  schedule: {
    interval_minutes: number;
    anchor_at: string;
  };
  thresholds: Array<{
    metric: string;
    warning_condition: string;
    critical_condition: string;
    unit: string | null;
  }>;
  limits: {
    timeout_seconds: number;
    max_steps: number;
    max_evidence_records: number;
    max_targets: number;
  };
  evidence_requirements: string[];
};

export type HealthCheckRun = {
  run_id: string;
  definition_id: string;
  definition_version: number;
  connector_id: string;
  connector_version: string;
  capability_id: string;
  target_id: string;
  trigger: "manual" | "scheduled";
  requested_by: string;
  started_at: string;
  completed_at: string;
  state: "completed" | "partial" | "timed_out" | "failed" | "cancelled";
  step_count: number;
  observations: Array<{
    observation_id: string;
    target_id: string;
    component: string;
    metric: string;
    value: string;
    unit: string | null;
    state: "normal" | "warning" | "critical" | "unknown";
    observed_at: string;
    freshness: "current" | "aging" | "stale" | "unknown";
    evidence_references: string[];
  }>;
  findings: Array<{
    finding_id: string;
    severity: "warning" | "critical" | "unknown";
    title: string;
    summary: string;
    observation_ids: string[];
    evidence_references: string[];
  }>;
  evidence: Array<{
    reference: string;
    source: string;
    source_version: string;
    observed_at: string;
    freshness: "current" | "aging" | "stale" | "unknown";
    trust_basis: string;
  }>;
  partial_reasons: string[];
  unknowns: string[];
  safety_notice: string;
};

export type HealthCheckOverview = {
  generated_at: string;
  data_profile: string;
  definitions: HealthCheckDefinition[];
  schedules: Array<{
    definition_id: string;
    enabled: boolean;
    interval_minutes: number;
    last_due_at: string;
    next_due_at: string;
  }>;
  latest_runs: HealthCheckRun[];
  safety_notice: string;
};

type HealthCheckOverviewResponse = {
  data: HealthCheckOverview;
  meta: { correlation_id: string; generated_at: string };
};

type HealthCheckRunResponse = {
  data: HealthCheckRun;
  meta: { correlation_id: string; generated_at: string };
};

export async function getHealthCheckOverview(): Promise<HealthCheckOverviewResponse> {
  const response = await apiFetch("/api/v1/health-checks/overview", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Health-check overview request failed with ${response.status}`);
  }
  return (await response.json()) as HealthCheckOverviewResponse;
}

export async function runHealthCheck(definitionId: string): Promise<HealthCheckRunResponse> {
  const response = await apiFetch(`/api/v1/health-checks/${encodeURIComponent(definitionId)}/runs`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Health-check run request failed with ${response.status}`);
  }
  return (await response.json()) as HealthCheckRunResponse;
}
import { apiFetch } from "./client";
