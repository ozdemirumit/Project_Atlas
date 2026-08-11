import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Server } from "lucide-react";

import type { BootstrapDataPlan } from "../../api/bootstrapData";
import {
  deployBootstrapServices,
  type BootstrapServiceDeploymentResult,
  type BootstrapServicePlan,
} from "../../api/bootstrapServices";
import type { BootstrapServiceExecution, BootstrapState } from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapServiceDeploymentWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  dataPlan: BootstrapDataPlan;
  scope: CurrentIdentity["scope"];
  servicePlan: BootstrapServicePlan;
  state: BootstrapState;
  trustPlan: BootstrapTrustPlan;
};

function workflowFingerprint({
  configuration,
  dataPlan,
  scope,
  servicePlan,
  state,
  trustPlan,
}: BootstrapServiceDeploymentWorkspaceProps): string {
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
    run?.data_initialization?.execution_id ?? null,
    run?.data_initialization?.state ?? null,
    run?.data_initialization?.result_code ?? null,
    run?.data_initialization?.data_plan_digest ?? null,
    run?.data_initialization?.migration_artifact_digest ?? null,
    run?.service_deployment?.execution_id ?? null,
    run?.service_deployment?.state ?? null,
    run?.service_deployment?.result_code ?? null,
    run?.service_deployment?.service_plan_digest ?? null,
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
    dataPlan.release_id,
    dataPlan.profile,
    dataPlan.organization_id,
    dataPlan.environment_id,
    dataPlan.site_id,
    dataPlan.configuration_digest,
    dataPlan.trust_plan_digest,
    dataPlan.data_plan_digest,
    dataPlan.migration_artifact_digest,
    servicePlan.schema_version,
    servicePlan.state,
    servicePlan.result_code,
    servicePlan.release_id,
    servicePlan.profile,
    servicePlan.organization_id,
    servicePlan.environment_id,
    servicePlan.site_id,
    servicePlan.configuration_digest,
    servicePlan.trust_plan_digest,
    servicePlan.data_plan_digest,
    servicePlan.migration_artifact_digest,
    servicePlan.service_plan_digest,
    servicePlan.target_id,
    servicePlan.target_kind,
    servicePlan.target_state,
    servicePlan.services.map((service) => [
      service.service_id,
      service.sequence,
      service.artifact_id,
      service.artifact_sha256,
      service.dependencies,
      service.workload_identity_id,
      service.endpoint_class,
      service.cpu_limit_millicores,
      service.memory_limit_mb,
      service.startup_probe_id,
      service.readiness_probe_id,
      service.liveness_probe_id,
      service.run_as_root,
      service.privileged,
      service.arbitrary_public_egress,
    ]),
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function servicesAreBounded(servicePlan: BootstrapServicePlan): boolean {
  const seen = new Set<string>();
  let previousSequence = Number.NEGATIVE_INFINITY;
  for (const service of servicePlan.services) {
    if (
      seen.has(service.service_id) ||
      service.sequence <= previousSequence ||
      service.endpoint_class !== "private" ||
      service.run_as_root ||
      service.privileged ||
      service.arbitrary_public_egress ||
      service.dependencies.some((dependency) => !seen.has(dependency))
    ) {
      return false;
    }
    seen.add(service.service_id);
    previousSequence = service.sequence;
  }
  return seen.size > 0;
}

function isAvailable({
  configuration,
  dataPlan,
  scope,
  servicePlan,
  state,
  trustPlan,
}: BootstrapServiceDeploymentWorkspaceProps): boolean {
  const run = state.run;
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.services" &&
      run.service_deployment?.state !== "running" &&
      run.completed_phase_ids.includes("phase.data") &&
      run.data_initialization?.state === "completed" &&
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
      run.data_initialization.trust_plan_digest === trustPlan.trust_plan_digest &&
      dataPlan.state === "passed" &&
      dataPlan.release_id === run.release_id &&
      dataPlan.profile === run.profile &&
      dataPlan.organization_id === scope.organization_id &&
      dataPlan.environment_id === scope.environment_id &&
      dataPlan.site_id === scope.site_id &&
      dataPlan.configuration_digest === run.configuration_digest &&
      dataPlan.trust_plan_digest === trustPlan.trust_plan_digest &&
      run.data_initialization.data_plan_digest === dataPlan.data_plan_digest &&
      run.data_initialization.migration_artifact_digest === dataPlan.migration_artifact_digest &&
      servicePlan.state === "passed" &&
      servicesAreBounded(servicePlan) &&
      servicePlan.release_id === run.release_id &&
      servicePlan.profile === run.profile &&
      servicePlan.organization_id === scope.organization_id &&
      servicePlan.environment_id === scope.environment_id &&
      servicePlan.site_id === scope.site_id &&
      servicePlan.configuration_digest === run.configuration_digest &&
      servicePlan.trust_plan_digest === trustPlan.trust_plan_digest &&
      servicePlan.data_plan_digest === dataPlan.data_plan_digest &&
      servicePlan.migration_artifact_digest === dataPlan.migration_artifact_digest,
  );
}

type ServiceReviewProps = {
  available: boolean;
  fingerprint: string;
  pending: boolean;
  servicePlan: BootstrapServicePlan;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function ServiceReview({
  available,
  fingerprint,
  pending,
  servicePlan,
  onConfirm,
  onStart,
}: ServiceReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;
  if (!reviewing) {
    return (
      <div className="data-initialization-action service-deployment-action">
        <div>
          <strong>Publish governed service state</strong>
          <p>
            Reviews {servicePlan.services.length} ordered Atlas services, their dependencies,
            resource limits, and health probes. No process, container, operating-system service,
            port, or network is changed.
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
          <Server size={14} /> Review services
        </button>
      </div>
    );
  }

  return (
    <div className="data-initialization-confirmation service-deployment-confirmation" role="dialog">
      <div>
        <strong>Confirm synthetic service-state deployment</strong>
        <p>
          Target {servicePlan.target_id} is {servicePlan.target_state}. Only an Atlas-owned state
          document will be atomically published after all bounded checks pass.
        </p>
      </div>
      <div className="service-plan-list">
        {servicePlan.services.map((service) => (
          <div key={service.service_id}>
            <span>{service.sequence}</span>
            <div>
              <code>{service.service_id}</code>
              <small>
                {service.dependencies.length > 0
                  ? `after ${service.dependencies.join(", ")}`
                  : "first service"}
                {" / "}
                {service.cpu_limit_millicores}m CPU / {service.memory_limit_mb} MB
              </small>
            </div>
            <strong>3 probes</strong>
          </div>
        ))}
      </div>
      <label>
        Service-state justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the reviewed reason for publishing service state"
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
          <Server size={14} /> Confirm services
        </button>
      </div>
    </div>
  );
}

function ServiceResult({
  execution,
  replayed,
}: {
  execution: BootstrapServiceExecution;
  replayed: boolean;
}) {
  return (
    <div
      className={`data-initialization-result service-deployment-result ${execution.state}`}
      role="status"
    >
      <div className="data-initialization-result-heading">
        {execution.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <AlertTriangle size={18} />
        )}
        <div>
          <strong>
            Service-state deployment {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="data-initialization-summary">
        <div>
          <span>Deployed</span>
          <strong>{execution.deployed_service_count}</strong>
        </div>
        <div>
          <span>Ready</span>
          <strong>{execution.ready_service_count}</strong>
        </div>
        <div>
          <span>Passed probes</span>
          <strong>{execution.passed_probe_count}</strong>
        </div>
        <div>
          <span>Real runtime</span>
          <strong>Unchanged</strong>
        </div>
      </div>
      {execution.service_statuses.length > 0 && (
        <div className="service-status-list">
          {execution.service_statuses.map((status) => (
            <div key={status.service_id}>
              <code>{status.service_id}</code>
              <span>{status.startup_passed ? "startup passed" : "startup failed"}</span>
              <span>{status.readiness_passed ? "readiness passed" : "readiness failed"}</span>
              <span>{status.liveness_passed ? "liveness passed" : "liveness failed"}</span>
            </div>
          ))}
        </div>
      )}
      {execution.evidence.map((item) => (
        <div className="service-state-evidence" key={item.evidence_id}>
          <div>
            <code>{item.evidence_id}</code>
            <span>{item.disposition}</span>
          </div>
          <code>{item.sha256.slice(0, 20)}...</code>
        </div>
      ))}
      {execution.state === "failed" && (
        <p className="data-recovery-note">
          No partial service state was published. Correct the bounded failure and retry under the
          active lease. No process, container, operating-system service, port, or network changed.
        </p>
      )}
    </div>
  );
}

export default function BootstrapServiceDeploymentWorkspace(
  props: BootstrapServiceDeploymentWorkspaceProps,
) {
  const { configuration, dataPlan, scope, servicePlan, state, trustPlan } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapServiceDeploymentResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.service_deployment ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-service-plan"] }),
    ]);
  };

  const serviceMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Service deployment evidence changed before confirmation");
      }
      return deployBootstrapServices({
        state,
        configuration,
        trustPlan,
        dataPlan,
        servicePlan,
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

  if (!available && !execution && !serviceMutation.isError) return null;

  return (
    <>
      <ServiceReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        fingerprint={fingerprint}
        pending={serviceMutation.isPending}
        servicePlan={servicePlan}
        onConfirm={(input) => serviceMutation.mutate(input)}
        onStart={() => {
          serviceMutation.reset();
          setResult(null);
        }}
      />

      {serviceMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Service state was not published. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && <ServiceResult execution={execution} replayed={result?.replayed ?? false} />}
    </>
  );
}
