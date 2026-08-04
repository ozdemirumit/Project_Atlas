import type { BootstrapPlan } from "./bootstrapPlan";
import { isBootstrapRun, type BootstrapState } from "./bootstrapState";
import { apiFetch } from "./client";
import type { DeploymentConfigurationPreview } from "./deploymentConfiguration";
import type { CurrentIdentity } from "./identity";

export type BootstrapClaimResult = {
  run: NonNullable<BootstrapState["run"]>;
  replayed: boolean;
  reclaimed_expired_lease: boolean;
  execution_authorized: false;
  infrastructure_mutation_authorized: false;
};

type BootstrapClaimResponse = { data: BootstrapClaimResult };

function isClaimResponse(value: unknown): value is BootstrapClaimResponse {
  if (typeof value !== "object" || value === null || !("data" in value)) return false;
  const data = value.data;
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Record<string, unknown>;
  return (
    isBootstrapRun(candidate.run) &&
    typeof candidate.replayed === "boolean" &&
    typeof candidate.reclaimed_expired_lease === "boolean" &&
    candidate.execution_authorized === false &&
    candidate.infrastructure_mutation_authorized === false
  );
}

export async function claimBootstrapLease(input: {
  state: BootstrapState;
  plan: BootstrapPlan;
  configuration: DeploymentConfigurationPreview;
  scope: CurrentIdentity["scope"];
  justification: string;
}): Promise<BootstrapClaimResponse> {
  const current = input.state.run;
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  const response = await apiFetch("/api/v1/platform/bootstrap-state/claims", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `bootstrap-claim.${current?.version ?? 0}.${nonce}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.bootstrap-claim.v1",
      release_id: current?.release_id ?? input.plan.release_id,
      profile: current?.profile ?? input.plan.profile,
      organization_id: current?.organization_id ?? input.scope.organization_id,
      environment_id: current?.environment_id ?? input.scope.environment_id,
      site_id: current?.site_id ?? input.scope.site_id,
      plan_digest: current?.plan_digest ?? input.plan.plan_digest,
      resume_key: current?.resume_key ?? input.plan.resume_key,
      configuration_digest:
        current?.configuration_digest ?? input.configuration.configuration_digest,
      phase_ids: current?.phase_ids ?? input.plan.phases.map((phase) => phase.phase_id),
      lease_minutes: 10,
      justification: input.justification,
    }),
  });
  if (!response.ok) throw new Error(`Bootstrap lease claim failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isClaimResponse(payload)) throw new Error("Bootstrap lease claim returned malformed state");
  return payload;
}
