import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, UserCheck } from "lucide-react";

import type { BootstrapDataPlan } from "../../api/bootstrapData";
import {
  handoffBootstrapIdentity,
  type BootstrapIdentityHandoffResult,
  type BootstrapIdentityPlan,
} from "../../api/bootstrapIdentity";
import type { BootstrapServicePlan } from "../../api/bootstrapServices";
import type { BootstrapIdentityExecution, BootstrapState } from "../../api/bootstrapState";
import type { BootstrapTrustPlan } from "../../api/bootstrapTrust";
import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import type { CurrentIdentity } from "../../api/identity";

type BootstrapIdentityHandoffWorkspaceProps = {
  configuration: DeploymentConfigurationPreview;
  dataPlan: BootstrapDataPlan;
  identityPlan: BootstrapIdentityPlan;
  scope: CurrentIdentity["scope"];
  servicePlan: BootstrapServicePlan;
  state: BootstrapState;
  trustPlan: BootstrapTrustPlan;
};

function workflowFingerprint({
  configuration,
  dataPlan,
  identityPlan,
  scope,
  servicePlan,
  state,
  trustPlan,
}: BootstrapIdentityHandoffWorkspaceProps): string {
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
    run?.service_deployment?.execution_id ?? null,
    run?.service_deployment?.state ?? null,
    run?.service_deployment?.result_code ?? null,
    run?.service_deployment?.release_id ?? null,
    run?.service_deployment?.profile ?? null,
    run?.service_deployment?.configuration_digest ?? null,
    run?.service_deployment?.trust_plan_digest ?? null,
    run?.service_deployment?.data_plan_digest ?? null,
    run?.service_deployment?.service_plan_digest ?? null,
    run?.service_deployment?.target_id ?? null,
    run?.service_deployment?.deployed_service_count ?? 0,
    run?.service_deployment?.ready_service_count ?? 0,
    run?.service_deployment?.passed_probe_count ?? 0,
    run?.service_deployment?.service_statuses.map((service) => [
      service.service_id,
      service.state,
      service.startup_passed,
      service.readiness_passed,
      service.liveness_passed,
    ]) ?? [],
    run?.identity_handoff?.execution_id ?? null,
    run?.identity_handoff?.state ?? null,
    run?.identity_handoff?.result_code ?? null,
    run?.identity_handoff?.identity_plan_digest ?? null,
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
    servicePlan.services.map((service) => [
      service.service_id,
      service.sequence,
      service.dependencies,
      service.workload_identity_id,
      service.endpoint_class,
      service.run_as_root,
      service.privileged,
      service.arbitrary_public_egress,
    ]),
    identityPlan.schema_version,
    identityPlan.state,
    identityPlan.result_code,
    identityPlan.release_id,
    identityPlan.profile,
    identityPlan.organization_id,
    identityPlan.environment_id,
    identityPlan.site_id,
    identityPlan.configuration_digest,
    identityPlan.trust_plan_digest,
    identityPlan.data_plan_digest,
    identityPlan.service_plan_digest,
    identityPlan.identity_plan_digest,
    identityPlan.target_id,
    identityPlan.target_kind,
    identityPlan.target_state,
    identityPlan.bootstrap_administrator_subject_id,
    identityPlan.credential_verifier_reference_id,
    identityPlan.credential_replacement_required,
    identityPlan.recovery_identity_id,
    identityPlan.recovery_seal_required,
    identityPlan.provider_id,
    identityPlan.provider_protocol,
    identityPlan.pilot_subject_id,
    identityPlan.group_mappings.map((mapping) => [
      mapping.mapping_id,
      mapping.directory_group_reference,
      mapping.role_ids,
    ]),
    identityPlan.credential_material_present,
    identityPlan.directory_mutation_authorized,
    identityPlan.provider_activation_authorized,
    identityPlan.account_mutation_authorized,
    identityPlan.session_or_token_mutation_authorized,
    identityPlan.infrastructure_mutation_authorized,
    identityPlan.ai_operation_authorized,
    scope.organization_id,
    scope.environment_id,
    scope.site_id,
  ]);
}

function serviceDeploymentIsReady(
  state: BootstrapState,
  servicePlan: BootstrapServicePlan,
): boolean {
  const execution = state.run?.service_deployment;
  if (
    !execution ||
    execution.state !== "completed" ||
    execution.release_id !== servicePlan.release_id ||
    execution.profile !== servicePlan.profile ||
    execution.configuration_digest !== servicePlan.configuration_digest ||
    execution.trust_plan_digest !== servicePlan.trust_plan_digest ||
    execution.data_plan_digest !== servicePlan.data_plan_digest ||
    execution.service_plan_digest !== servicePlan.service_plan_digest ||
    execution.target_id !== servicePlan.target_id ||
    execution.deployed_service_count !== servicePlan.services.length ||
    execution.ready_service_count !== servicePlan.services.length ||
    execution.passed_probe_count !== servicePlan.services.length * 3 ||
    execution.service_statuses.length !== servicePlan.services.length
  ) {
    return false;
  }

  const expectedServices = new Set(servicePlan.services.map((service) => service.service_id));
  const seen = new Set<string>();
  return execution.service_statuses.every((service) => {
    if (
      !expectedServices.has(service.service_id) ||
      seen.has(service.service_id) ||
      service.state !== "ready" ||
      !service.startup_passed ||
      !service.readiness_passed ||
      !service.liveness_passed
    ) {
      return false;
    }
    seen.add(service.service_id);
    return true;
  });
}

function servicePlanIsBounded(servicePlan: BootstrapServicePlan): boolean {
  const seen = new Set<string>();
  let previousSequence = Number.NEGATIVE_INFINITY;
  for (const service of servicePlan.services) {
    if (
      !service.service_id.trim() ||
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

function identityPlanIsBounded(identityPlan: BootstrapIdentityPlan): boolean {
  if (
    !identityPlan.target_id.trim() ||
    !identityPlan.target_kind.trim() ||
    !identityPlan.bootstrap_administrator_subject_id.trim() ||
    !identityPlan.credential_verifier_reference_id.trim() ||
    !identityPlan.recovery_identity_id.trim() ||
    !identityPlan.provider_id.trim() ||
    !identityPlan.pilot_subject_id.trim() ||
    identityPlan.credential_material_present ||
    identityPlan.directory_mutation_authorized ||
    identityPlan.provider_activation_authorized ||
    identityPlan.account_mutation_authorized ||
    identityPlan.session_or_token_mutation_authorized ||
    identityPlan.infrastructure_mutation_authorized ||
    identityPlan.ai_operation_authorized ||
    !identityPlan.credential_replacement_required ||
    !identityPlan.recovery_seal_required ||
    identityPlan.provider_protocol !== "ldaps"
  ) {
    return false;
  }

  const mappingIds = new Set<string>();
  const directoryGroups = new Set<string>();
  for (const mapping of identityPlan.group_mappings) {
    if (
      !mapping.mapping_id.trim() ||
      !mapping.directory_group_reference.trim() ||
      mappingIds.has(mapping.mapping_id) ||
      directoryGroups.has(mapping.directory_group_reference) ||
      mapping.role_ids.length === 0 ||
      mapping.role_ids.some((role) => !role.trim()) ||
      new Set(mapping.role_ids).size !== mapping.role_ids.length
    ) {
      return false;
    }
    mappingIds.add(mapping.mapping_id);
    directoryGroups.add(mapping.directory_group_reference);
  }
  return mappingIds.size > 0;
}

function isAvailable({
  configuration,
  dataPlan,
  identityPlan,
  scope,
  servicePlan,
  state,
  trustPlan,
}: BootstrapIdentityHandoffWorkspaceProps): boolean {
  const run = state.run;
  return Boolean(
    run &&
      run.state !== "completed" &&
      state.lease_held_by_current_actor &&
      run.current_phase_id === "phase.identity" &&
      run.identity_handoff?.state !== "running" &&
      run.completed_phase_ids.includes("phase.services") &&
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
      dataPlan.state === "passed" &&
      dataPlan.release_id === run.release_id &&
      dataPlan.profile === run.profile &&
      dataPlan.organization_id === scope.organization_id &&
      dataPlan.environment_id === scope.environment_id &&
      dataPlan.site_id === scope.site_id &&
      dataPlan.configuration_digest === run.configuration_digest &&
      dataPlan.trust_plan_digest === trustPlan.trust_plan_digest &&
      servicePlan.state === "passed" &&
      servicePlan.release_id === run.release_id &&
      servicePlan.profile === run.profile &&
      servicePlan.organization_id === scope.organization_id &&
      servicePlan.environment_id === scope.environment_id &&
      servicePlan.site_id === scope.site_id &&
      servicePlan.configuration_digest === run.configuration_digest &&
      servicePlan.trust_plan_digest === trustPlan.trust_plan_digest &&
      servicePlan.data_plan_digest === dataPlan.data_plan_digest &&
      servicePlan.migration_artifact_digest === dataPlan.migration_artifact_digest &&
      servicePlanIsBounded(servicePlan) &&
      serviceDeploymentIsReady(state, servicePlan) &&
      identityPlan.state === "passed" &&
      identityPlanIsBounded(identityPlan) &&
      identityPlan.release_id === run.release_id &&
      identityPlan.profile === run.profile &&
      identityPlan.organization_id === scope.organization_id &&
      identityPlan.environment_id === scope.environment_id &&
      identityPlan.site_id === scope.site_id &&
      identityPlan.configuration_digest === run.configuration_digest &&
      identityPlan.trust_plan_digest === trustPlan.trust_plan_digest &&
      identityPlan.data_plan_digest === dataPlan.data_plan_digest &&
      identityPlan.service_plan_digest === servicePlan.service_plan_digest,
  );
}

type IdentityReviewProps = {
  available: boolean;
  fingerprint: string;
  identityPlan: BootstrapIdentityPlan;
  pending: boolean;
  onConfirm: (input: { fingerprint: string; justification: string }) => void;
  onStart: () => void;
};

function IdentityReview({
  available,
  fingerprint,
  identityPlan,
  pending,
  onConfirm,
  onStart,
}: IdentityReviewProps) {
  const [reviewing, setReviewing] = useState(false);
  const [justification, setJustification] = useState("");

  if (!available) return null;
  if (!reviewing) {
    return (
      <div className="data-initialization-action identity-handoff-action">
        <div>
          <strong>Publish governed identity handoff</strong>
          <p>
            Reviews the restricted administrator, recovery seal, LDAPS provider, pilot identity,
            and {identityPlan.group_mappings.length} group mappings. No credential, account,
            directory, provider, session, or token is changed.
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
          <UserCheck size={14} /> Review identity handoff
        </button>
      </div>
    );
  }

  return (
    <div className="data-initialization-confirmation identity-handoff-confirmation" role="dialog">
      <div>
        <strong>Confirm synthetic identity handoff</strong>
        <p>
          Target {identityPlan.target_id} is {identityPlan.target_state}. Only one Atlas-owned,
          secret-free identity state document will be atomically published.
        </p>
      </div>
      <div className="identity-plan-summary">
        <div>
          <span>Administrator</span>
          <code>{identityPlan.bootstrap_administrator_subject_id}</code>
          <small>Credential replacement required</small>
        </div>
        <div>
          <span>Recovery identity</span>
          <code>{identityPlan.recovery_identity_id}</code>
          <small>Recovery seal required</small>
        </div>
        <div>
          <span>Enterprise provider</span>
          <code>{identityPlan.provider_id}</code>
          <small>LDAPS metadata only</small>
        </div>
        <div>
          <span>Pilot identity</span>
          <code>{identityPlan.pilot_subject_id}</code>
          <small>Validation reference only</small>
        </div>
      </div>
      <div className="identity-mapping-list">
        {identityPlan.group_mappings.map((mapping) => (
          <div key={mapping.mapping_id}>
            <div>
              <code>{mapping.directory_group_reference}</code>
              <small>{mapping.mapping_id}</small>
            </div>
            <strong>{mapping.role_ids.join(", ")}</strong>
          </div>
        ))}
      </div>
      <label>
        Identity-handoff justification
        <input
          value={justification}
          maxLength={500}
          onChange={(event) => setJustification(event.target.value)}
          placeholder="Record the reviewed reason for publishing identity state"
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
          <UserCheck size={14} /> Confirm identity
        </button>
      </div>
    </div>
  );
}

function IdentityResult({
  execution,
  replayed,
}: {
  execution: BootstrapIdentityExecution;
  replayed: boolean;
}) {
  return (
    <div
      className={`data-initialization-result identity-handoff-result ${execution.state}`}
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
            Identity handoff {execution.state}
            {replayed ? " (replayed)" : ""}
          </strong>
          <code>{execution.result_code}</code>
        </div>
        <span className={`state-badge ${execution.state}`}>{execution.state}</span>
      </div>
      <div className="data-initialization-summary">
        <div>
          <span>Group mappings</span>
          <strong>{execution.group_mapping_count}</strong>
        </div>
        <div>
          <span>Validations</span>
          <strong>{execution.validation_count}</strong>
        </div>
        <div>
          <span>Recovery seal</span>
          <strong>{execution.bootstrap_material_sealed ? "Verified" : "Pending"}</strong>
        </div>
        <div>
          <span>Real identity systems</span>
          <strong>Unchanged</strong>
        </div>
      </div>
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
          No partial identity state was published. Correct the bounded failure and retry under the
          active lease. No credential, account, directory, provider, session, or token changed.
        </p>
      )}
    </div>
  );
}

export default function BootstrapIdentityHandoffWorkspace(
  props: BootstrapIdentityHandoffWorkspaceProps,
) {
  const { configuration, dataPlan, identityPlan, scope, servicePlan, state, trustPlan } = props;
  const queryClient = useQueryClient();
  const [reviewEpoch, setReviewEpoch] = useState(0);
  const [result, setResult] = useState<BootstrapIdentityHandoffResult | null>(null);
  const fingerprint = workflowFingerprint(props);
  const available = isAvailable(props);
  const execution = result?.execution ?? state.run?.identity_handoff ?? null;

  const refreshBootstrapEvidence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      queryClient.invalidateQueries({ queryKey: ["bootstrap-identity-plan"] }),
    ]);
  };

  const identityMutation = useMutation({
    mutationFn: async (input: { fingerprint: string; justification: string }) => {
      if (!available || input.fingerprint !== fingerprint) {
        throw new Error("Identity handoff evidence changed before confirmation");
      }
      return handoffBootstrapIdentity({
        state,
        configuration,
        trustPlan,
        dataPlan,
        servicePlan,
        identityPlan,
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

  if (!available && !execution && !identityMutation.isError) return null;

  return (
    <>
      <IdentityReview
        key={`${fingerprint}:${reviewEpoch}`}
        available={available}
        fingerprint={fingerprint}
        identityPlan={identityPlan}
        pending={identityMutation.isPending}
        onConfirm={(input) => identityMutation.mutate(input)}
        onStart={() => {
          identityMutation.reset();
          setResult(null);
        }}
      />

      {identityMutation.isError && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={16} /> Identity state was not published. Evidence was refreshed;
          record a new review intent before retrying.
        </div>
      )}

      {execution && <IdentityResult execution={execution} replayed={result?.replayed ?? false} />}
    </>
  );
}
