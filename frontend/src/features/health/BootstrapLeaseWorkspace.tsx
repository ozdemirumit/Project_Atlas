import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, LockKeyhole } from "lucide-react";

import { claimBootstrapLease, type BootstrapClaimResult } from "../../api/bootstrapClaim";
import type { BootstrapPlan } from "../../api/bootstrapPlan";
import type { BootstrapState } from "../../api/bootstrapState";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapLeaseWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  plan: BootstrapPlan;
  scope: CurrentIdentity["scope"];
  state: BootstrapState;
};

function workflowFingerprint({
  configuration,
  plan,
  scope,
  state,
}: BootstrapLeaseWorkspaceProps): string {
  return JSON.stringify([
    state.run?.run_id ?? null,
    state.run?.version ?? 0,
    state.run?.state ?? null,
    state.lease_available,
    state.lease_held_by_current_actor,
    plan.state,
    plan.plan_digest,
    plan.resume_key,
    configuration.state,
    configuration.configuration_digest,
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function resultTitle(result: BootstrapClaimResult): string {
  if (result.replayed) return "Coordination lease replay confirmed";
  if (result.reclaimed_expired_lease) return "Expired coordination lease reclaimed";
  return "Coordination lease established";
}

type BootstrapLeaseReviewProps = {
  available: boolean;
  fingerprint: string;
  pending: boolean;
  state: BootstrapState;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function BootstrapLeaseReview({
  available,
  fingerprint,
  pending,
  state,
  onConfirm,
  onStart,
}: BootstrapLeaseReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;

  if (!reviewing) {
    return (
      <div className="bootstrap-claim-action">
        <div>
          <strong>{state.run ? "Reclaim coordination lease" : "Initialize bootstrap run"}</strong>
          <p>
            Establishes the exact plan lock and checkpoint boundary. It does not run a phase or
            write release artifacts.
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
          <LockKeyhole size={14} /> Review lease
        </button>
      </div>
    );
  }

  return (
    <div className="bootstrap-claim-confirmation" role="dialog">
      <div>
        <strong>Confirm bootstrap coordination lease</strong>
        <p>
          The exact release, configuration, plan, phase order and run revision will be locked to
          this browser session for 10 minutes.
        </p>
      </div>
      <label>
        Lease justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the reviewed reason for coordinating this bootstrap run"
        />
      </label>
      <div className="bootstrap-claim-confirm-actions">
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
          className="bootstrap-claim-confirm"
          type="button"
          disabled={justification.trim().length < 12 || pending}
          onClick={() =>
            onConfirm({ fingerprint, justification: justification.trim() })
          }
        >
          <LockKeyhole size={14} /> Confirm lease
        </button>
      </div>
    </div>
  );
}

export default function BootstrapLeaseWorkspace(props: BootstrapLeaseWorkspaceProps) {
  const { configuration, plan, scope, state } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapClaimResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = Boolean(
    state.lease_available &&
      plan.state === "ready" &&
      configuration.state === "passed" &&
      state.run?.state !== "completed",
  );

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
    ]);
  };

  const claimMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Bootstrap lease evidence changed before confirmation");
      }
      return claimBootstrapLease({
        state,
        plan,
        configuration,
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

  if (!available && !result && !claimMutation.isError) return null;

  return (
    <>
      <BootstrapLeaseReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        fingerprint={fingerprint}
        pending={claimMutation.isPending}
        state={state}
        onConfirm={(input) => claimMutation.mutate(input)}
        onStart={() => {
          claimMutation.reset();
          setResult(null);
        }}
      />

      {claimMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> The coordination lease was not established. Evidence was
          refreshed; record a new review intent before retrying.
        </div>
      )}

      {result && (
        <div className="bootstrap-claim-result" role="status">
          <CheckCircle2 size={18} />
          <div>
            <strong>{resultTitle(result)}</strong>
            <p>
              Run {result.run.run_id} is locked at server revision {result.run.version}. No phase
              execution is authorized.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
