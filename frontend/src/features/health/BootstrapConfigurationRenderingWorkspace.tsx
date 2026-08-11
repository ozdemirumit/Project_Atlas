import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileText } from "lucide-react";

import {
  renderBootstrapConfiguration,
  type BootstrapConfigurationRenderingResult,
} from "../../api/bootstrapConfigurationRendering";
import type {
  BootstrapConfigurationExecution,
  BootstrapState,
} from "../../api/bootstrapState";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapConfigurationRenderingWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  formatTimestamp: (value: string | undefined) => string;
  scope: CurrentIdentity["scope"];
  state: BootstrapState;
};

function workflowFingerprint({
  configuration,
  scope,
  state,
}: BootstrapConfigurationRenderingWorkspaceProps): string {
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
    run?.artifact_acquisition?.execution_id ?? null,
    run?.artifact_acquisition?.state ?? null,
    run?.artifact_acquisition?.result_code ?? null,
    run?.configuration_rendering?.execution_id ?? null,
    run?.configuration_rendering?.state ?? null,
    run?.configuration_rendering?.result_code ?? null,
    state.lease_held_by_current_actor,
    configuration.preview_id,
    configuration.schema_version,
    configuration.release_id,
    configuration.profile,
    configuration.organization_id,
    configuration.environment_id,
    configuration.site_id,
    configuration.state,
    configuration.configuration_digest,
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function isAvailable({
  configuration,
  scope,
  state,
}: BootstrapConfigurationRenderingWorkspaceProps): boolean {
  const run = state.run;
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.configure" &&
      run.configuration_rendering?.state !== "running" &&
      run.completed_phase_ids.includes("phase.acquire") &&
      run.artifact_acquisition?.state === "completed" &&
      run.organization_id === scope.organization_id &&
      run.environment_id === scope.environment_id &&
      run.site_id === scope.site_id &&
      configuration.state === "passed" &&
      configuration.release_id === run.release_id &&
      configuration.profile === run.profile &&
      configuration.organization_id === scope.organization_id &&
      configuration.environment_id === scope.environment_id &&
      configuration.site_id === scope.site_id &&
      configuration.configuration_digest === run.configuration_digest,
  );
}

type ConfigurationReviewProps = {
  available: boolean;
  configuration: DeploymentConfigurationPreview;
  fingerprint: string;
  pending: boolean;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function ConfigurationReview({
  available,
  configuration,
  fingerprint,
  pending,
  onConfirm,
  onStart,
}: ConfigurationReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;

  if (!reviewing) {
    return (
      <div className="configuration-rendering-action">
        <div>
          <strong>Render and validate effective configuration</strong>
          <p>
            Writes only canonical non-secret configuration to the governed Atlas configuration
            store. Trust, secrets, data, services, and infrastructure remain unchanged.
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
          <FileText size={14} /> Review configuration
        </button>
      </div>
    );
  }

  return (
    <div className="configuration-rendering-confirmation" role="dialog">
      <div>
        <strong>Confirm effective configuration change</strong>
        <p>
          Configuration {configuration.configuration_digest.slice(0, 12)}... will be recomputed,
          schema-validated, and atomically published. Existing exact output is reused and
          conflicting content is preserved.
        </p>
      </div>
      <label>
        Change justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the approved reason for rendering this configuration"
        />
      </label>
      <div className="configuration-rendering-confirm-actions">
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
          className="configuration-rendering-confirm"
          type="button"
          disabled={justification.trim().length < 12 || pending}
          onClick={() =>
            onConfirm({ fingerprint, justification: justification.trim() })
          }
        >
          <FileText size={14} /> Confirm configuration
        </button>
      </div>
    </div>
  );
}

function ConfigurationResult({
  execution,
  formatTimestamp,
  replayed,
}: {
  execution: BootstrapConfigurationExecution;
  formatTimestamp: BootstrapConfigurationRenderingWorkspaceProps["formatTimestamp"];
  replayed: boolean;
}) {
  return (
    <div className={`configuration-rendering-result ${execution.state}`} role="status">
      <div className="configuration-rendering-result-heading">
        {execution.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <AlertTriangle size={18} />
        )}
        <div>
          <strong>
            Configuration rendering {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="configuration-rendering-summary">
        <div>
          <span>Schema</span>
          <strong>v1</strong>
        </div>
        <div>
          <span>Files</span>
          <strong>{execution.file_count}</strong>
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
        <div className="configuration-evidence-list">
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
        <p className="configuration-recovery-note">
          Prior verified configuration was preserved. Correct the bounded failure and retry under
          the active lease.
        </p>
      )}
    </div>
  );
}

export default function BootstrapConfigurationRenderingWorkspace(
  props: BootstrapConfigurationRenderingWorkspaceProps,
) {
  const { configuration, formatTimestamp, scope, state } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapConfigurationRenderingResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.configuration_rendering ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
    ]);
  };

  const configurationMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Configuration rendering evidence changed before confirmation");
      }
      return renderBootstrapConfiguration({
        state,
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

  if (!available && !execution && !configurationMutation.isError) return null;

  return (
    <>
      <ConfigurationReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        configuration={configuration}
        fingerprint={fingerprint}
        pending={configurationMutation.isPending}
        onConfirm={(input) => configurationMutation.mutate(input)}
        onStart={() => {
          configurationMutation.reset();
          setResult(null);
        }}
      />

      {configurationMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Configuration was not published. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && (
        <ConfigurationResult
          execution={execution}
          formatTimestamp={formatTimestamp}
          replayed={result?.replayed ?? false}
        />
      )}
    </>
  );
}
