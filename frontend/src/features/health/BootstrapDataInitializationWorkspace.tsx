import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Database } from "lucide-react";

import {
  initializeBootstrapData,
  type BootstrapDataInitializationResult,
  type BootstrapDataPlan,
} from "../../api/bootstrapData";
import type { BootstrapDataExecution, BootstrapState } from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapDataInitializationWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  dataPlan: BootstrapDataPlan;
  scope: CurrentIdentity["scope"];
  state: BootstrapState;
  trustPlan: BootstrapTrustPlan;
};

function workflowFingerprint({
  configuration,
  dataPlan,
  scope,
  state,
  trustPlan,
}: BootstrapDataInitializationWorkspaceProps): string {
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
    run?.trust_provisioning?.execution_id ?? null,
    run?.trust_provisioning?.state ?? null,
    run?.trust_provisioning?.result_code ?? null,
    run?.trust_provisioning?.trust_plan_digest ?? null,
    run?.data_initialization?.execution_id ?? null,
    run?.data_initialization?.state ?? null,
    run?.data_initialization?.result_code ?? null,
    run?.data_initialization?.data_plan_digest ?? null,
    run?.data_initialization?.migration_artifact_digest ?? null,
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
    trustPlan.release_id,
    trustPlan.profile,
    trustPlan.organization_id,
    trustPlan.environment_id,
    trustPlan.site_id,
    trustPlan.configuration_digest,
    trustPlan.trust_plan_digest,
    dataPlan.schema_version,
    dataPlan.state,
    dataPlan.result_code,
    dataPlan.release_id,
    dataPlan.profile,
    dataPlan.organization_id,
    dataPlan.environment_id,
    dataPlan.site_id,
    dataPlan.configuration_digest,
    dataPlan.trust_plan_digest,
    dataPlan.migration_artifact_digest,
    dataPlan.data_plan_digest,
    dataPlan.target_id,
    dataPlan.target_kind,
    dataPlan.current_revision,
    dataPlan.target_revision,
    dataPlan.target_state,
    dataPlan.backup_applicability,
    dataPlan.migrations.map((migration) => [
      migration.migration_id,
      migration.sequence,
      migration.sha256,
      migration.from_revision,
      migration.to_revision,
      migration.compatibility,
      migration.reversible,
      migration.destructive,
      migration.recovery_code,
      migration.expected_object_count,
    ]),
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function isAvailable({
  configuration,
  dataPlan,
  scope,
  state,
  trustPlan,
}: BootstrapDataInitializationWorkspaceProps): boolean {
  const run = state.run;
  const migrationsAreBounded = dataPlan.migrations.every((migration, index, migrations) => {
    const previous = migrations[index - 1];
    return (
      migration.compatibility === "expand" &&
      migration.reversible === true &&
      migration.destructive === false &&
      (index === 0
        ? migration.from_revision === dataPlan.current_revision
        : previous?.to_revision === migration.from_revision) &&
      (index < migrations.length - 1 || migration.to_revision === dataPlan.target_revision)
    );
  });
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.data" &&
      run.data_initialization?.state !== "running" &&
      run.completed_phase_ids.includes("phase.trust") &&
      run.trust_provisioning?.state === "completed" &&
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
      trustPlan.release_id === run.release_id &&
      trustPlan.profile === run.profile &&
      trustPlan.organization_id === scope.organization_id &&
      trustPlan.environment_id === scope.environment_id &&
      trustPlan.site_id === scope.site_id &&
      trustPlan.configuration_digest === run.configuration_digest &&
      run.trust_provisioning.trust_plan_digest === trustPlan.trust_plan_digest &&
      dataPlan.state === "passed" &&
      dataPlan.migrations.length > 0 &&
      migrationsAreBounded &&
      dataPlan.release_id === run.release_id &&
      dataPlan.profile === run.profile &&
      dataPlan.organization_id === scope.organization_id &&
      dataPlan.environment_id === scope.environment_id &&
      dataPlan.site_id === scope.site_id &&
      dataPlan.configuration_digest === run.configuration_digest &&
      dataPlan.trust_plan_digest === trustPlan.trust_plan_digest,
  );
}

type DataReviewProps = {
  available: boolean;
  dataPlan: BootstrapDataPlan;
  fingerprint: string;
  pending: boolean;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function DataReview({
  available,
  dataPlan,
  fingerprint,
  pending,
  onConfirm,
  onStart,
}: DataReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;

  if (!reviewing) {
    return (
      <div className="data-initialization-action">
        <div>
          <strong>Initialize governed schema state</strong>
          <p>
            Applies {dataPlan.migrations.length} ordered, reversible migration records to the
            approved {dataPlan.target_kind} target. External databases, services, backups, and
            infrastructure remain unchanged.
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
          <Database size={14} /> Review data
        </button>
      </div>
    );
  }

  return (
    <div className="data-initialization-confirmation" role="dialog">
      <div>
        <strong>Confirm clean data-schema initialization</strong>
        <p>
          Target {dataPlan.target_id} is {dataPlan.target_state}. Schema revision will move from {" "}
          {dataPlan.current_revision} to {dataPlan.target_revision}. Backup is not applicable to
          this clean, synthetic initialization.
        </p>
      </div>
      <div className="data-migration-list">
        {dataPlan.migrations.map((migration) => (
          <div key={migration.migration_id}>
            <span>{migration.sequence}</span>
            <div>
              <code>{migration.migration_id}</code>
              <small>
                {migration.from_revision} to {migration.to_revision} / {" "}
                {migration.expected_object_count} objects
              </small>
            </div>
            <strong>reversible</strong>
          </div>
        ))}
      </div>
      <label>
        Data justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the reviewed reason for initializing schema state"
        />
      </label>
      <div className="data-initialization-confirm-actions">
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
          className="data-initialization-confirm"
          type="button"
          disabled={justification.trim().length < 12 || pending}
          onClick={() => onConfirm({ fingerprint, justification: justification.trim() })}
        >
          <Database size={14} /> Confirm data
        </button>
      </div>
    </div>
  );
}

function DataResult({
  execution,
  replayed,
}: {
  execution: BootstrapDataExecution;
  replayed: boolean;
}) {
  return (
    <div className={`data-initialization-result ${execution.state}`} role="status">
      <div className="data-initialization-result-heading">
        {execution.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <AlertTriangle size={18} />
        )}
        <div>
          <strong>
            Data initialization {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="data-initialization-summary">
        <div>
          <span>Revision</span>
          <strong>
            {execution.from_revision} to {execution.to_revision}
          </strong>
        </div>
        <div>
          <span>Migrations</span>
          <strong>{execution.migration_count}</strong>
        </div>
        <div>
          <span>Verified objects</span>
          <strong>{execution.verified_object_count}</strong>
        </div>
        <div>
          <span>Backup</span>
          <strong>Not applicable</strong>
        </div>
      </div>
      {execution.evidence.length > 0 && (
        <div className="data-evidence-list">
          {execution.evidence.map((item) => (
            <div key={item.evidence_id}>
              <div>
                <code>{item.evidence_id}</code>
                <span>{item.disposition}</span>
              </div>
              <code>{item.sha256.slice(0, 20)}...</code>
            </div>
          ))}
        </div>
      )}
      {execution.state === "failed" && (
        <p className="data-recovery-note">
          No partial schema state was published. Correct the bounded failure and retry under the
          active lease. No external database, backup, service, or infrastructure was changed.
        </p>
      )}
    </div>
  );
}

export default function BootstrapDataInitializationWorkspace(
  props: BootstrapDataInitializationWorkspaceProps,
) {
  const { configuration, dataPlan, scope, state, trustPlan } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapDataInitializationResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.data_initialization ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-data-plan"] }),
    ]);
  };

  const dataMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Data initialization evidence changed before confirmation");
      }
      return initializeBootstrapData({
        state,
        configuration,
        trustPlan,
        dataPlan,
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

  if (!available && !execution && !dataMutation.isError) return null;

  return (
    <>
      <DataReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        dataPlan={dataPlan}
        fingerprint={fingerprint}
        pending={dataMutation.isPending}
        onConfirm={(input) => dataMutation.mutate(input)}
        onStart={() => {
          dataMutation.reset();
          setResult(null);
        }}
      />

      {dataMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Schema state was not initialized. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && <DataResult execution={execution} replayed={result?.replayed ?? false} />}
    </>
  );
}

