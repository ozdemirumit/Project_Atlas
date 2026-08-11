import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";

import {
  provisionBootstrapTrust,
  type BootstrapTrustPlan,
  type BootstrapTrustProvisioningResult,
} from "../../api/bootstrapTrust";
import type { BootstrapState, BootstrapTrustExecution } from "../../api/bootstrapState";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapTrustProvisioningWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  scope: CurrentIdentity["scope"];
  state: BootstrapState;
  trustPlan: BootstrapTrustPlan;
};

function workflowFingerprint({
  configuration,
  scope,
  state,
  trustPlan,
}: BootstrapTrustProvisioningWorkspaceProps): string {
  const run = state.run;
  return JSON.stringify([
    run?.run_id ?? null,
    run?.version ?? 0,
    run?.state ?? null,
    run?.current_phase_id ?? null,
    run?.release_id ?? null,
    run?.profile ?? null,
    run?.plan_digest ?? null,
    run?.resume_key ?? null,
    run?.configuration_digest ?? null,
    run?.organization_id ?? null,
    run?.environment_id ?? null,
    run?.site_id ?? null,
    run?.lease_expires_at ?? null,
    run?.completed_phase_ids ?? [],
    run?.configuration_rendering?.execution_id ?? null,
    run?.configuration_rendering?.state ?? null,
    run?.configuration_rendering?.result_code ?? null,
    run?.configuration_rendering?.configuration_digest ?? null,
    run?.trust_provisioning?.execution_id ?? null,
    run?.trust_provisioning?.state ?? null,
    run?.trust_provisioning?.result_code ?? null,
    run?.trust_provisioning?.trust_plan_digest ?? null,
    state.lease_held_by_current_actor,
    configuration.preview_id,
    configuration.schema_version,
    configuration.state,
    configuration.release_id,
    configuration.profile,
    configuration.organization_id,
    configuration.environment_id,
    configuration.site_id,
    configuration.configuration_digest,
    trustPlan.schema_version,
    trustPlan.state,
    trustPlan.result_code,
    trustPlan.release_id,
    trustPlan.profile,
    trustPlan.organization_id,
    trustPlan.environment_id,
    trustPlan.site_id,
    trustPlan.configuration_digest,
    trustPlan.trust_plan_digest,
    trustPlan.anchors.map((anchor) => [
      anchor.anchor_id,
      anchor.source_id,
      anchor.purpose,
      anchor.sha256,
      anchor.not_before,
      anchor.not_after,
      anchor.non_production_only,
    ]),
    trustPlan.workload_identities.map((identity) => [
      identity.identity_id,
      identity.service_id,
      identity.instance_id,
      identity.owner_subject_id,
      identity.purpose,
      identity.environment_id,
      identity.audiences,
      identity.secret_reference_ids,
    ]),
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function isAvailable({
  configuration,
  scope,
  state,
  trustPlan,
}: BootstrapTrustProvisioningWorkspaceProps): boolean {
  const run = state.run;
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.trust" &&
      run.trust_provisioning?.state !== "running" &&
      run.completed_phase_ids.includes("phase.configure") &&
      run.configuration_rendering?.state === "completed" &&
      run.configuration_rendering.configuration_digest === run.configuration_digest &&
      run.organization_id === scope.organization_id &&
      run.environment_id === scope.environment_id &&
      run.site_id === scope.site_id &&
      configuration.state === "passed" &&
      configuration.release_id === run.release_id &&
      configuration.profile === run.profile &&
      configuration.organization_id === scope.organization_id &&
      configuration.environment_id === scope.environment_id &&
      configuration.site_id === scope.site_id &&
      configuration.configuration_digest === run.configuration_digest &&
      trustPlan.state === "passed" &&
      trustPlan.anchors.length > 0 &&
      trustPlan.workload_identities.length > 0 &&
      trustPlan.release_id === run.release_id &&
      trustPlan.profile === run.profile &&
      trustPlan.organization_id === scope.organization_id &&
      trustPlan.environment_id === scope.environment_id &&
      trustPlan.site_id === scope.site_id &&
      trustPlan.configuration_digest === run.configuration_digest,
  );
}

type TrustReviewProps = {
  available: boolean;
  fingerprint: string;
  pending: boolean;
  trustPlan: BootstrapTrustPlan;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function TrustReview({
  available,
  fingerprint,
  pending,
  trustPlan,
  onConfirm,
  onStart,
}: TrustReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;

  if (!reviewing) {
    return (
      <div className="trust-provisioning-action">
        <div>
          <strong>Provision public trust and workload identities</strong>
          <p>
            Publishes only approved public certificates and opaque secret-reference metadata.
            Private keys, credential values, data, services, and infrastructure remain unchanged.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            onStart();
            setJustification("");
            setReviewing(true);
          }}
        >
          <ShieldCheck size={14} /> Review trust
        </button>
      </div>
    );
  }

  return (
    <div className="trust-provisioning-confirmation" role="dialog">
      <div>
        <strong>Confirm public trust-store change</strong>
        <p>
          Trust plan {trustPlan.trust_plan_digest.slice(0, 12)}... will publish {" "}
          {trustPlan.anchors.length} public anchor and {trustPlan.workload_identities.length} workload
          identity record. Existing exact output is reused.
        </p>
      </div>
      <label>
        Trust justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the approved reason for publishing public trust metadata"
        />
      </label>
      <div className="trust-provisioning-confirm-actions">
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setReviewing(false);
            setJustification("");
          }}
        >
          Cancel
        </button>
        <button
          className="trust-provisioning-confirm"
          type="button"
          disabled={justification.trim().length < 12 || pending}
          onClick={() => onConfirm({ fingerprint, justification: justification.trim() })}
        >
          <ShieldCheck size={14} /> Confirm trust
        </button>
      </div>
    </div>
  );
}

function TrustResult({
  execution,
  replayed,
}: {
  execution: BootstrapTrustExecution;
  replayed: boolean;
}) {
  return (
    <div className={`trust-provisioning-result ${execution.state}`} role="status">
      <div className="trust-provisioning-result-heading">
        {execution.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <AlertTriangle size={18} />
        )}
        <div>
          <strong>
            Trust provisioning {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="trust-provisioning-summary">
        <div>
          <span>Public anchors</span>
          <strong>{execution.anchor_count}</strong>
        </div>
        <div>
          <span>Workload identities</span>
          <strong>{execution.workload_identity_count}</strong>
        </div>
        <div>
          <span>Files</span>
          <strong>{execution.file_count}</strong>
        </div>
        <div>
          <span>Verified bytes</span>
          <strong>{execution.total_bytes.toLocaleString()}</strong>
        </div>
      </div>
      {execution.evidence.length > 0 && (
        <div className="trust-evidence-list">
          {execution.evidence.map((item) => (
            <div key={item.file_id}>
              <div>
                <code>{item.file_id}</code>
                <span>{item.disposition}</span>
              </div>
              <code>{item.sha256.slice(0, 20)}...</code>
            </div>
          ))}
        </div>
      )}
      {execution.state === "failed" && (
        <p className="trust-recovery-note">
          Prior trust state was preserved. Correct the bounded failure and retry under the active
          lease. No private key or credential value was changed.
        </p>
      )}
    </div>
  );
}

export default function BootstrapTrustProvisioningWorkspace(
  props: BootstrapTrustProvisioningWorkspaceProps,
) {
  const { configuration, scope, state, trustPlan } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapTrustProvisioningResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.trust_provisioning ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
    ]);
  };

  const trustMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Trust provisioning evidence changed before confirmation");
      }
      return provisionBootstrapTrust({
        state,
        configuration,
        trustPlan,
        scope,
        justification: input.justification,
      });
    },
    onSuccess: async (response) => {
      setResult(response.data);
      setReviewEpoch((current) => current + 1);
      await refreshBootstrapEvidence();
    },
    onError: async () => {
      setReviewEpoch((current) => current + 1);
      await refreshBootstrapEvidence();
    },
  });

  if (!available && !execution && !trustMutation.isError) return null;

  return (
    <>
      <TrustReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        fingerprint={fingerprint}
        pending={trustMutation.isPending}
        trustPlan={trustPlan}
        onConfirm={(input) => trustMutation.mutate(input)}
        onStart={() => {
          trustMutation.reset();
          setResult(null);
        }}
      />

      {trustMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Trust metadata was not published. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && <TrustResult execution={execution} replayed={result?.replayed ?? false} />}
    </>
  );
}
