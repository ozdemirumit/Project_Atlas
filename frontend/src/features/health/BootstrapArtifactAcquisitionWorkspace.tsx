import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, PackageCheck } from "lucide-react";

import {
  acquireBootstrapArtifacts,
  type BootstrapArtifactAcquisitionResult,
} from "../../api/bootstrapArtifactAcquisition";
import type { BootstrapPlan } from "../../api/bootstrapPlan";
import type { BootstrapArtifactExecution, BootstrapState } from "../../api/bootstrapState";
import type { CurrentIdentity } from "../../api/identity";
import type { ReleasePreflight } from "../../api/releasePreflight";

type BootstrapArtifactAcquisitionWorkspaceProps = {
  formatTimestamp: (value: string | undefined) => string;
  plan: BootstrapPlan;
  preflight: ReleasePreflight;
  scope: CurrentIdentity["scope"];
  state: BootstrapState;
};

function workflowFingerprint({
  plan,
  preflight,
  scope,
  state,
}: BootstrapArtifactAcquisitionWorkspaceProps): string {
  const run = state.run;
  return JSON.stringify([
    run?.run_id ?? null,
    run?.version ?? 0,
    run?.state ?? null,
    run?.current_phase_id ?? null,
    run?.plan_digest ?? null,
    run?.resume_key ?? null,
    run?.release_id ?? null,
    run?.profile ?? null,
    run?.organization_id ?? null,
    run?.environment_id ?? null,
    run?.site_id ?? null,
    run?.lease_expires_at ?? null,
    run?.artifact_acquisition?.execution_id ?? null,
    run?.artifact_acquisition?.state ?? null,
    run?.artifact_acquisition?.result_code ?? null,
    run?.artifact_acquisition?.manifest_digest ?? null,
    run?.artifact_acquisition?.preflight_report_id ?? null,
    state.lease_held_by_current_actor,
    plan.plan_id,
    plan.state,
    plan.release_id,
    plan.profile,
    plan.organization_id,
    plan.environment_id,
    plan.site_id,
    plan.plan_digest,
    plan.resume_key,
    preflight.report_id,
    preflight.release_id,
    preflight.manifest_digest,
    preflight.mode,
    preflight.profile,
    preflight.state,
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function isAvailable({
  plan,
  preflight,
  scope,
  state,
}: BootstrapArtifactAcquisitionWorkspaceProps): boolean {
  const run = state.run;
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.acquire" &&
      run.artifact_acquisition?.state !== "running" &&
      plan.state === "ready" &&
      plan.release_id === run.release_id &&
      plan.profile === run.profile &&
      plan.organization_id === scope.organization_id &&
      plan.environment_id === scope.environment_id &&
      plan.site_id === scope.site_id &&
      plan.plan_digest === run.plan_digest &&
      plan.resume_key === run.resume_key &&
      run.organization_id === scope.organization_id &&
      run.environment_id === scope.environment_id &&
      run.site_id === scope.site_id &&
      preflight.release_id === run.release_id &&
      preflight.profile === run.profile &&
      (preflight.state === "passed" || preflight.state === "warning"),
  );
}

type AcquisitionReviewProps = {
  available: boolean;
  fingerprint: string;
  pending: boolean;
  preflight: ReleasePreflight;
  onConfirm: (input: {
    fingerprint: string;
    justification: string;
    warningAccepted: boolean;
  }) => void;
  onStart: () => void;
};

function AcquisitionReview({
  available,
  fingerprint,
  pending,
  preflight,
  onConfirm,
  onStart,
}: AcquisitionReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");
  const [warningAccepted, setWarningAccepted] = useState(false);

  if (!available) return null;

  if (!reviewing) {
    return (
      <div className="artifact-acquisition-action">
        <div>
          <strong>Acquire and verify release artifacts</strong>
          <p>
            Writes only the immutable release set to the governed Atlas artifact store.
            Configuration, services, and infrastructure remain unchanged.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            onStart();
            setJustification("");
            setWarningAccepted(false);
            setReviewing(true);
          }}
        >
          <PackageCheck size={14} /> Review acquisition
        </button>
      </div>
    );
  }

  return (
    <div className="artifact-acquisition-confirmation" role="dialog">
      <div>
        <strong>Confirm artifact storage change</strong>
        <p>
          Release {preflight.release_version} will be staged and checksum-verified in{" "}
          {preflight.mode} mode. Existing verified files are reused and conflicting files are
          preserved.
        </p>
      </div>
      <label>
        Change justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the approved reason for acquiring this release"
        />
      </label>
      {preflight.state === "warning" && (
        <label className="artifact-warning-acceptance">
          <input
            type="checkbox"
            checked={warningAccepted}
            onChange={(event) => setWarningAccepted(event.target.checked)}
          />
          <span>I accept the reviewed preflight warning for this lab run.</span>
        </label>
      )}
      <div className="artifact-acquisition-confirm-actions">
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setReviewing(false);
            setJustification("");
            setWarningAccepted(false);
          }}
        >
          Cancel
        </button>
        <button
          className="artifact-acquisition-confirm"
          type="button"
          disabled={
            justification.trim().length < 12 ||
            (preflight.state === "warning" && !warningAccepted) ||
            pending
          }
          onClick={() =>
            onConfirm({
              fingerprint,
              justification: justification.trim(),
              warningAccepted,
            })
          }
        >
          <PackageCheck size={14} /> Confirm acquisition
        </button>
      </div>
    </div>
  );
}

function AcquisitionResult({
  execution,
  formatTimestamp,
  replayed,
}: {
  execution: BootstrapArtifactExecution;
  formatTimestamp: BootstrapArtifactAcquisitionWorkspaceProps["formatTimestamp"];
  replayed: boolean;
}) {
  return (
    <div className={`artifact-acquisition-result ${execution.state}`} role="status">
      <div className="artifact-acquisition-result-heading">
        {execution.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <AlertTriangle size={18} />
        )}
        <div>
          <strong>
            Artifact acquisition {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="artifact-acquisition-summary">
        <div>
          <span>Mode</span>
          <strong>{execution.mode}</strong>
        </div>
        <div>
          <span>Artifacts</span>
          <strong>{execution.artifact_count}</strong>
        </div>
        <div>
          <span>Verified bytes</span>
          <strong>{execution.total_bytes.toLocaleString()}</strong>
        </div>
        <div>
          <span>Completed</span>
          <strong>{formatTimestamp(execution.completed_at ?? undefined)}</strong>
        </div>
      </div>
      {execution.evidence.length > 0 && (
        <div className="artifact-evidence-list">
          {execution.evidence.map((item) => (
            <div key={item.artifact_id}>
              <div>
                <code>{item.artifact_id}</code>
                <span>{item.disposition}</span>
              </div>
              <code>{item.sha256.slice(0, 20)}...</code>
            </div>
          ))}
        </div>
      )}
      {execution.state === "failed" && (
        <p className="artifact-recovery-note">
          Verified prior content was preserved. Correct the bounded failure and retry this phase
          under the active lease.
        </p>
      )}
    </div>
  );
}

export default function BootstrapArtifactAcquisitionWorkspace(
  props: BootstrapArtifactAcquisitionWorkspaceProps,
) {
  const { formatTimestamp, preflight, scope, state } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapArtifactAcquisitionResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.artifact_acquisition ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
    ]);
  };

  const acquisitionMutation = useMutation({
    mutationFn: async (input: {
      fingerprint: string;
      justification: string;
      warningAccepted: boolean;
    }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Artifact acquisition evidence changed before confirmation");
      }
      return acquireBootstrapArtifacts({
        state,
        preflight,
        scope,
        justification: input.justification,
        warningAccepted: input.warningAccepted,
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

  if (!available && !execution && !acquisitionMutation.isError) return null;

  return (
    <>
      <AcquisitionReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        fingerprint={fingerprint}
        pending={acquisitionMutation.isPending}
        preflight={preflight}
        onConfirm={(input) => acquisitionMutation.mutate(input)}
        onStart={() => {
          acquisitionMutation.reset();
          setResult(null);
        }}
      />

      {acquisitionMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Artifact acquisition was not started. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && (
        <AcquisitionResult
          execution={execution}
          formatTimestamp={formatTimestamp}
          replayed={result?.replayed ?? false}
        />
      )}
    </>
  );
}
