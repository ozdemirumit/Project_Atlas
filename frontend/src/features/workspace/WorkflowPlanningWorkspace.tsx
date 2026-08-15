import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Ban,
  CalendarClock,
  CheckCircle2,
  Database,
  FileClock,
  FileJson2,
  History,
  Link2,
  LockKeyhole,
  Network,
  Plus,
  RefreshCw,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";

import { ApiRequestError } from "../../api/client";
import { listOperationalConversations } from "../../api/conversations";
import {
  cancelWorkflowPlan,
  createWorkflowPlan,
  getWorkflowMaterializedRun,
  getWorkflowOrchestrationLease,
  listWorkflowDefinitions,
  listWorkflowAttemptDispatchIntents,
  listWorkflowDispatchOutboxEntries,
  listWorkflowDispatchEventEnvelopes,
  listWorkflowDispatchOutboxPublicationLeases,
  listWorkflowEndpointResolutionAuthorizationLeases,
  listWorkflowPhysicalTransportCredentialAccessAuthorizationLeases,
  listWorkflowPhysicalTransportCredentialMaterializations,
  listWorkflowPhysicalTransportCredentialAssignmentSnapshots,
  listWorkflowPhysicalTransportCredentialAssignmentFreshnessAdmissions,
  listWorkflowPhysicalTransportEndpointMaterializations,
  listWorkflowEventByteArtifacts,
  listWorkflowEventLogicalChannelBindings,
  listWorkflowEventTransportAdmissions,
  listWorkflowPlans,
  listWorkflowPhysicalTransportCredentialAssignmentBindings,
  listWorkflowPhysicalTransportRouteBindings,
  listWorkflowPhysicalTransportRouteFreshnessAdmissions,
  listWorkflowRunAttempts,
  listWorkflowTransportCompatibilityAdmissions,
  listWorkflowTransportProfileSnapshots,
  listWorkflowTransportRouteSnapshots,
  WORKFLOW_PLAN_SAFETY_NOTICE,
  type WorkflowDefinition,
  type WorkflowRunPlan,
  type WorkflowTransportEventContract,
} from "../../api/workflows";

interface WorkflowPlanningWorkspaceProps {
  environmentId: string;
  organizationId: string;
  ownerSubjectId: string;
  siteId: string;
  onBack: () => void;
}

function readableKind(kind: string): string {
  return kind.replaceAll("_", " ");
}

function shortDigest(value: string): string {
  return `${value.slice(0, 12)}...${value.slice(-8)}`;
}

function safeHolderIdentifier(value: string): string {
  return value.length <= 24 ? value : `${value.slice(0, 14)}...${value.slice(-6)}`;
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function routeFreshnessWindowIsOpen(validUntil: string): boolean {
  return Date.parse(validUntil) > Date.now();
}

function credentialAssignmentFreshnessWindowIsOpen(validUntil: string): boolean {
  return Date.parse(validUntil) > Date.now();
}

function formatTransportEventContract(value: WorkflowTransportEventContract): string {
  return `${value.event_type} v${value.event_version}`;
}

export default function WorkflowPlanningWorkspace({
  environmentId,
  organizationId,
  ownerSubjectId,
  siteId,
  onBack,
}: WorkflowPlanningWorkspaceProps) {
  const queryClient = useQueryClient();
  const [definitionId, setDefinitionId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [purpose, setPurpose] = useState("");
  const [inputSummary, setInputSummary] = useState("");
  const [selectedPlan, setSelectedPlan] = useState<WorkflowRunPlan | null>(null);
  const [cancellationReason, setCancellationReason] = useState("");
  const [cancellationAcknowledged, setCancellationAcknowledged] = useState(false);
  const scope = useMemo(
    () => ({ organizationId, environmentId, siteId }),
    [environmentId, organizationId, siteId],
  );
  const transportProfileQuery = useQuery({
    queryKey: ["workflow-transport-profile-snapshots", organizationId, environmentId, siteId],
    queryFn: () => listWorkflowTransportProfileSnapshots({ scope }),
    retry: false,
  });
  const transportRouteSnapshotQuery = useQuery({
    queryKey: ["workflow-transport-route-snapshots", organizationId, environmentId, siteId],
    queryFn: () => listWorkflowTransportRouteSnapshots({ scope }),
    retry: false,
  });
  const physicalTransportCredentialAssignmentSnapshotQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-credential-assignment-snapshots",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: listWorkflowPhysicalTransportCredentialAssignmentSnapshots,
    retry: false,
  });
  const physicalTransportRouteBindingQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-route-bindings",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => listWorkflowPhysicalTransportRouteBindings({ scope }),
    retry: false,
  });
  const physicalTransportCredentialAssignmentBindingQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-credential-assignment-bindings",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: listWorkflowPhysicalTransportCredentialAssignmentBindings,
    retry: false,
  });
  const physicalTransportCredentialAssignmentFreshnessAdmissionQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-credential-assignment-freshness-admissions",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      listWorkflowPhysicalTransportCredentialAssignmentFreshnessAdmissions({ scope }),
    retry: false,
  });
  const physicalTransportCredentialAccessAuthorizationLeaseQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-credential-access-authorization-leases",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      listWorkflowPhysicalTransportCredentialAccessAuthorizationLeases({ scope }),
    retry: false,
  });
  const physicalTransportRouteFreshnessAdmissionQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-route-freshness-admissions",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => listWorkflowPhysicalTransportRouteFreshnessAdmissions({ scope }),
    retry: false,
  });
  const endpointResolutionAuthorizationLeaseQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-endpoint-resolution-authorization-leases",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => listWorkflowEndpointResolutionAuthorizationLeases({ scope }),
    retry: false,
  });
  const endpointMaterializationQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-endpoint-materializations",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => listWorkflowPhysicalTransportEndpointMaterializations({ scope }),
    retry: false,
  });
  const credentialMaterializationQuery = useQuery({
    queryKey: [
      "workflow-physical-transport-credential-materializations",
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => listWorkflowPhysicalTransportCredentialMaterializations({ scope }),
    retry: false,
  });
  const targetQuery = useQuery({
    queryKey: ["workflow-targets", organizationId, environmentId, siteId, ownerSubjectId],
    queryFn: () =>
      listOperationalConversations({
        organizationId,
        environmentId,
        siteId,
        ownerSubjectId,
      }),
    retry: false,
  });
  const definitionQuery = useQuery({
    queryKey: ["workflow-definitions", organizationId, environmentId, siteId],
    queryFn: listWorkflowDefinitions,
    retry: false,
  });
  const authorizedTargets = useMemo(
    () => targetQuery.data?.authorizedTargets ?? [],
    [targetQuery.data?.authorizedTargets],
  );
  const authorizedTargetIds = useMemo(
    () => authorizedTargets.map((target) => target.targetId),
    [authorizedTargets],
  );
  const plansQuery = useQuery({
    queryKey: ["workflow-plans", organizationId, environmentId, siteId, authorizedTargetIds],
    queryFn: () => listWorkflowPlans({ scope, authorizedTargetIds }),
    enabled: targetQuery.isSuccess,
    retry: false,
  });
  const leaseQuery = useQuery({
    queryKey: [
      "workflow-orchestration-lease",
      selectedPlan?.plan_id,
      selectedPlan?.canonical_digest,
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => {
      if (!selectedPlan) throw new ApiRequestError("No workflow plan is selected", 422);
      return getWorkflowOrchestrationLease({
        plan: selectedPlan,
        scope,
        authorizedTargetIds,
      });
    },
    enabled: Boolean(selectedPlan),
    retry: false,
  });
  const materializedRunQuery = useQuery({
    queryKey: [
      "workflow-materialized-run",
      selectedPlan?.plan_id,
      selectedPlan?.canonical_digest,
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => {
      if (!selectedPlan) throw new ApiRequestError("No workflow plan is selected", 422);
      return getWorkflowMaterializedRun({
        plan: selectedPlan,
        scope,
        authorizedTargetIds,
      });
    },
    enabled: Boolean(selectedPlan),
    retry: false,
  });
  const materializedRun = materializedRunQuery.data?.run ?? null;
  const attemptQuery = useQuery({
    queryKey: [
      "workflow-run-attempts",
      materializedRun?.run_id,
      materializedRun?.canonical_digest,
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () => {
      if (!materializedRun) throw new ApiRequestError("No workflow run is selected", 422);
      return listWorkflowRunAttempts({
        run: materializedRun,
        scope,
        authorizedTargetIds,
      });
    },
    enabled: Boolean(materializedRun),
    retry: false,
  });
  const materializedAttempts = attemptQuery.data?.attempts ?? [];
  const dispatchIntentQuery = useQuery({
    queryKey: [
      "workflow-attempt-dispatch-intents",
      materializedAttempts.map((attempt) => [attempt.attempt_id, attempt.canonical_digest]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        materializedAttempts.map((attempt) =>
          listWorkflowAttemptDispatchIntents({ attempt, scope, authorizedTargetIds }),
        ),
      ),
    enabled: attemptQuery.isSuccess && materializedAttempts.length > 0,
    retry: false,
  });
  const dispatchIntents =
    dispatchIntentQuery.data?.flatMap((inventory) => inventory.dispatch_intents) ?? [];
  const dispatchOutboxQuery = useQuery({
    queryKey: [
      "workflow-dispatch-outbox-entries",
      dispatchIntents.map((intent) => [intent.dispatch_intent_id, intent.canonical_digest]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        dispatchIntents.map((dispatchIntent) =>
          listWorkflowDispatchOutboxEntries({ dispatchIntent, scope, authorizedTargetIds }),
        ),
      ),
    enabled: dispatchIntentQuery.isSuccess && dispatchIntents.length > 0,
    retry: false,
  });
  const dispatchOutboxEntries =
    dispatchOutboxQuery.data?.flatMap((inventory) => inventory.outbox_entries) ?? [];
  const publicationLeaseQuery = useQuery({
    queryKey: [
      "workflow-dispatch-outbox-publication-leases",
      dispatchOutboxEntries.map((entry) => [entry.outbox_entry_id, entry.canonical_digest]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        dispatchOutboxEntries.map((outboxEntry) =>
          listWorkflowDispatchOutboxPublicationLeases({
            outboxEntry,
            scope,
            authorizedTargetIds,
          }),
        ),
      ),
    enabled: dispatchOutboxQuery.isSuccess && dispatchOutboxEntries.length > 0,
    retry: false,
  });
  const publicationLeases =
    publicationLeaseQuery.data?.flatMap((inventory) => inventory.publication_leases) ?? [];
  const eventEnvelopeQuery = useQuery({
    queryKey: [
      "workflow-dispatch-event-envelopes",
      dispatchOutboxEntries.map((entry) => [entry.outbox_entry_id, entry.canonical_digest]),
      publicationLeases.map((lease) => [lease.publication_lease_id, lease.canonical_digest]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        dispatchOutboxEntries.map((outboxEntry) =>
          listWorkflowDispatchEventEnvelopes({
            outboxEntry,
            publicationLease:
              publicationLeases.find(
                (lease) => lease.outbox_entry_id === outboxEntry.outbox_entry_id,
              ) ?? null,
            scope,
            authorizedTargetIds,
          }),
        ),
      ),
    enabled: publicationLeaseQuery.isSuccess && dispatchOutboxEntries.length > 0,
    retry: false,
  });
  const eventEnvelopesForAdmission =
    eventEnvelopeQuery.data?.flatMap((inventory) => inventory.event_envelopes) ?? [];
  const transportAdmissionSources = eventEnvelopesForAdmission.flatMap((eventEnvelope) => {
    const outboxEntry = dispatchOutboxEntries.find(
      (entry) => entry.outbox_entry_id === eventEnvelope.payload.outbox_entry_id,
    );
    if (!outboxEntry) return [];
    return [
      {
        eventEnvelope,
        outboxEntry,
        publicationLease:
          publicationLeases.find(
            (lease) => lease.publication_lease_id === eventEnvelope.publication_lease_id,
          ) ?? null,
      },
    ];
  });
  const transportAdmissionQuery = useQuery({
    queryKey: [
      "workflow-event-transport-admissions",
      transportAdmissionSources.map(({ eventEnvelope }) => [
        eventEnvelope.event_id,
        eventEnvelope.canonical_digest,
      ]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        transportAdmissionSources.map(({ eventEnvelope, outboxEntry, publicationLease }) =>
          listWorkflowEventTransportAdmissions({
            eventEnvelope,
            outboxEntry,
            publicationLease,
            scope,
            authorizedTargetIds,
          }),
        ),
      ),
    enabled:
      eventEnvelopeQuery.isSuccess &&
      eventEnvelopesForAdmission.length > 0 &&
      transportAdmissionSources.length === eventEnvelopesForAdmission.length,
    retry: false,
  });
  const transportAdmissionsForArtifacts =
    transportAdmissionQuery.data?.flatMap((inventory) => inventory.transport_admissions) ?? [];
  const byteArtifactSources = transportAdmissionsForArtifacts.flatMap((transportAdmission) => {
    const source = transportAdmissionSources.find(
      ({ eventEnvelope }) => eventEnvelope.event_id === transportAdmission.event_id,
    );
    return source ? [{ ...source, transportAdmission }] : [];
  });
  const byteArtifactQuery = useQuery({
    queryKey: [
      "workflow-event-byte-artifacts",
      byteArtifactSources.map(({ transportAdmission }) => [
        transportAdmission.transport_admission_id,
        transportAdmission.canonical_digest,
      ]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        byteArtifactSources.map(
          ({ transportAdmission, eventEnvelope, outboxEntry, publicationLease }) =>
            listWorkflowEventByteArtifacts({
              transportAdmission,
              eventEnvelope,
              outboxEntry,
              publicationLease,
              scope,
              authorizedTargetIds,
            }),
        ),
      ),
    enabled:
      transportAdmissionQuery.isSuccess &&
      transportAdmissionsForArtifacts.length > 0 &&
      byteArtifactSources.length === transportAdmissionsForArtifacts.length,
    retry: false,
  });
  const byteArtifactsForBindings =
    byteArtifactQuery.data?.flatMap((inventory) => inventory.byte_artifacts) ?? [];
  const logicalChannelBindingQuery = useQuery({
    queryKey: [
      "workflow-event-logical-channel-bindings",
      byteArtifactsForBindings.map((artifact) => [
        artifact.byte_artifact_id,
        artifact.canonical_digest,
      ]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        byteArtifactsForBindings.map((byteArtifact) =>
          listWorkflowEventLogicalChannelBindings({
            byteArtifact,
            scope,
            authorizedTargetIds,
          }),
        ),
      ),
    enabled: byteArtifactQuery.isSuccess && byteArtifactsForBindings.length > 0,
    retry: false,
  });
  const logicalChannelBindingsForCompatibility =
    logicalChannelBindingQuery.data?.flatMap(
      (inventory) => inventory.logical_channel_bindings,
    ) ?? [];
  const transportCompatibilityAdmissionQuery = useQuery({
    queryKey: [
      "workflow-transport-compatibility-admissions",
      logicalChannelBindingsForCompatibility.map((binding) => [
        binding.logical_channel_binding_id,
        binding.canonical_digest,
      ]),
      organizationId,
      environmentId,
      siteId,
    ],
    queryFn: () =>
      Promise.all(
        logicalChannelBindingsForCompatibility.map((logicalChannelBinding) =>
          listWorkflowTransportCompatibilityAdmissions({
            logicalChannelBinding,
            scope,
            authorizedTargetIds,
          }),
        ),
      ),
    enabled:
      logicalChannelBindingQuery.isSuccess &&
      logicalChannelBindingsForCompatibility.length > 0,
    retry: false,
  });
  const definitions = definitionQuery.data?.definitions ?? [];
  const selectedDefinition = definitions.find((item) => item.definition_id === definitionId);
  const createMutation = useMutation({
    mutationFn: (definition: WorkflowDefinition) =>
      createWorkflowPlan({
        definition,
        targetId,
        purpose,
        inputSummary,
        scope,
        authorizedTargetIds,
      }),
    onSuccess: (plan) => {
      setSelectedPlan(plan);
      setPurpose("");
      setInputSummary("");
      void queryClient.invalidateQueries({ queryKey: ["workflow-plans"] });
    },
  });
  const cancelMutation = useMutation({
    mutationFn: (plan: WorkflowRunPlan) =>
      cancelWorkflowPlan({
        plan,
        reason: cancellationReason,
        acknowledgeNoExternalUndo: cancellationAcknowledged,
        scope,
        authorizedTargetIds,
      }),
    onSuccess: (plan) => {
      setSelectedPlan(plan);
      setCancellationReason("");
      setCancellationAcknowledged(false);
      void queryClient.invalidateQueries({ queryKey: ["workflow-plans"] });
    },
  });
  const loading = targetQuery.isLoading || definitionQuery.isLoading || plansQuery.isLoading;
  const failed = targetQuery.isError || definitionQuery.isError || plansQuery.isError;
  const sessionExpired = [targetQuery.error, definitionQuery.error, plansQuery.error].some(
    (error) => error instanceof ApiRequestError && error.status === 401,
  );
  const canCreate = Boolean(
    selectedDefinition && targetId && purpose.trim() && inputSummary.trim() && !createMutation.isPending,
  );
  const canCancel = Boolean(
    selectedPlan?.state === "planned" &&
      cancellationReason.trim() &&
      cancellationAcknowledged &&
      !cancelMutation.isPending,
  );
  const cancellationSessionExpired =
    cancelMutation.error instanceof ApiRequestError && cancelMutation.error.status === 401;
  const leaseErrorStatus =
    leaseQuery.error instanceof ApiRequestError ? leaseQuery.error.status : undefined;
  const materializedRunErrorStatus =
    materializedRunQuery.error instanceof ApiRequestError
      ? materializedRunQuery.error.status
      : undefined;
  const attemptErrorStatus =
    attemptQuery.error instanceof ApiRequestError ? attemptQuery.error.status : undefined;
  const dispatchIntentErrorStatus =
    dispatchIntentQuery.error instanceof ApiRequestError
      ? dispatchIntentQuery.error.status
      : undefined;
  const dispatchOutboxErrorStatus =
    dispatchOutboxQuery.error instanceof ApiRequestError
      ? dispatchOutboxQuery.error.status
      : undefined;
  const publicationLeaseErrorStatus =
    publicationLeaseQuery.error instanceof ApiRequestError
      ? publicationLeaseQuery.error.status
      : undefined;
  const eventEnvelopeErrorStatus =
    eventEnvelopeQuery.error instanceof ApiRequestError
      ? eventEnvelopeQuery.error.status
      : undefined;
  const transportAdmissionErrorStatus =
    transportAdmissionQuery.error instanceof ApiRequestError
      ? transportAdmissionQuery.error.status
      : undefined;
  const byteArtifactErrorStatus =
    byteArtifactQuery.error instanceof ApiRequestError
      ? byteArtifactQuery.error.status
      : undefined;
  const logicalChannelBindingErrorStatus =
    logicalChannelBindingQuery.error instanceof ApiRequestError
      ? logicalChannelBindingQuery.error.status
      : undefined;
  const transportCompatibilityAdmissionErrorStatus =
    transportCompatibilityAdmissionQuery.error instanceof ApiRequestError
      ? transportCompatibilityAdmissionQuery.error.status
      : undefined;
  const transportProfileErrorStatus =
    transportProfileQuery.error instanceof ApiRequestError
      ? transportProfileQuery.error.status
      : undefined;
  const transportRouteSnapshotErrorStatus =
    transportRouteSnapshotQuery.error instanceof ApiRequestError
      ? transportRouteSnapshotQuery.error.status
      : undefined;
  const physicalTransportCredentialAssignmentSnapshotErrorStatus =
    physicalTransportCredentialAssignmentSnapshotQuery.error instanceof ApiRequestError
      ? physicalTransportCredentialAssignmentSnapshotQuery.error.status
      : undefined;
  const physicalTransportRouteBindingErrorStatus =
    physicalTransportRouteBindingQuery.error instanceof ApiRequestError
      ? physicalTransportRouteBindingQuery.error.status
      : undefined;
  const physicalTransportCredentialAssignmentBindingErrorStatus =
    physicalTransportCredentialAssignmentBindingQuery.error instanceof ApiRequestError
      ? physicalTransportCredentialAssignmentBindingQuery.error.status
      : undefined;
  const physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus =
    physicalTransportCredentialAssignmentFreshnessAdmissionQuery.error instanceof ApiRequestError
      ? physicalTransportCredentialAssignmentFreshnessAdmissionQuery.error.status
      : undefined;
  const physicalTransportCredentialAccessAuthorizationLeaseErrorStatus =
    physicalTransportCredentialAccessAuthorizationLeaseQuery.error instanceof ApiRequestError
      ? physicalTransportCredentialAccessAuthorizationLeaseQuery.error.status
      : undefined;
  const physicalTransportRouteFreshnessAdmissionErrorStatus =
    physicalTransportRouteFreshnessAdmissionQuery.error instanceof ApiRequestError
      ? physicalTransportRouteFreshnessAdmissionQuery.error.status
      : undefined;
  const endpointResolutionAuthorizationLeaseErrorStatus =
    endpointResolutionAuthorizationLeaseQuery.error instanceof ApiRequestError
      ? endpointResolutionAuthorizationLeaseQuery.error.status
      : undefined;
  const endpointMaterializationErrorStatus =
    endpointMaterializationQuery.error instanceof ApiRequestError
      ? endpointMaterializationQuery.error.status
      : undefined;
  const credentialMaterializationErrorStatus =
    credentialMaterializationQuery.error instanceof ApiRequestError
      ? credentialMaterializationQuery.error.status
      : undefined;
  const eventEnvelopes = eventEnvelopesForAdmission;
  const transportAdmissions = transportAdmissionsForArtifacts;
  const byteArtifacts =
    byteArtifactQuery.data?.flatMap((inventory) => inventory.byte_artifacts) ?? [];
  const logicalChannelBindings =
    logicalChannelBindingsForCompatibility;
  const transportCompatibilityAdmissions =
    transportCompatibilityAdmissionQuery.data?.flatMap(
      (inventory) => inventory.transport_compatibility_admissions,
    ) ?? [];

  const selectPlan = (plan: WorkflowRunPlan) => {
    setSelectedPlan(plan);
    setCancellationReason("");
    setCancellationAcknowledged(false);
    cancelMutation.reset();
  };

  const refresh = () => {
    void targetQuery.refetch();
    void definitionQuery.refetch();
    if (targetQuery.isSuccess) void plansQuery.refetch();
  };

  return (
    <div className="workflow-planning-workspace">
      <header className="workflow-planning-header">
        <button className="icon-button" type="button" onClick={onBack} aria-label="Back to workspace">
          <ArrowLeft size={18} />
        </button>
        <div>
          <p className="eyebrow">OPERATIONAL PLANNING</p>
          <h1>Workflow plans</h1>
          <p>Versioned, reviewable plans for bounded infrastructure analysis.</p>
        </div>
        <span className="state-badge neutral">planning only</span>
      </header>

      <div className="workflow-safety-boundary" role="note">
        <LockKeyhole size={19} />
        <div><strong>No execution authority</strong><span>{WORKFLOW_PLAN_SAFETY_NOTICE}</span></div>
      </div>

      <section
        className="workflow-transport-profile-band"
        aria-labelledby="workflow-transport-profile-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">DEPLOYMENT CAPABILITY EVIDENCE</p>
            <h2 id="workflow-transport-profile-title">Transport capability profiles</h2>
          </div>
          <span>Read only</span>
        </div>
        {transportProfileQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading transport capability profiles...</span>
          </div>
        )}
        {transportProfileQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {transportProfileErrorStatus === 401
                  ? "Your session has expired"
                  : transportProfileErrorStatus === 403
                    ? "Transport capability profile permission is missing"
                    : "Transport capability profiles are unavailable"}
              </strong>
              <span>
                {transportProfileErrorStatus === 401
                  ? "Sign in again to continue."
                  : transportProfileErrorStatus === 403
                    ? "Your current role or scope cannot inspect transport capability profiles."
                    : "No deployment capability or operational state is inferred from this failed read."}
              </span>
            </div>
            {transportProfileErrorStatus !== 401 && transportProfileErrorStatus !== 403 && (
              <button
                className="secondary-action"
                type="button"
                aria-label="Retry transport capability profile read"
                onClick={() => void transportProfileQuery.refetch()}
              >
                <RefreshCw size={16} />
                Retry
              </button>
            )}
          </div>
        )}
        {transportProfileQuery.isSuccess &&
          transportProfileQuery.data.transport_profile_snapshots.length === 0 && (
            <div className="workflow-empty-state">
              <Network size={19} /> No transport capability profiles are recorded in this scope.
            </div>
          )}
        {transportProfileQuery.isSuccess &&
          transportProfileQuery.data.transport_profile_snapshots.length > 0 && (
            <ol
              className="workflow-step-preview workflow-transport-profile-list"
              aria-label="Transport capability profiles"
            >
              {transportProfileQuery.data.transport_profile_snapshots.map((profile) => (
                <li key={profile.snapshot_id}>
                  <Network size={18} />
                  <div>
                    <strong>
                      <code title={profile.transport_profile_id}>
                        {safeHolderIdentifier(profile.transport_profile_id)}
                      </code>
                      <span className="state-badge neutral">{profile.state}</span>
                    </strong>
                    <div className="workflow-transport-profile-grid">
                      <span>
                        Revision <b>{profile.transport_profile_revision}</b> | deployment{" "}
                        <code title={profile.deployment_release_id}>
                          {safeHolderIdentifier(profile.deployment_release_id)}
                        </code>{" "}
                        | {profile.deployment_profile}
                      </span>
                      <span>
                        Organization {profile.scope.organization_id} | environment{" "}
                        {profile.scope.environment_id} | site {profile.scope.site_id}
                      </span>
                      <span>
                        Implementation{" "}
                        <code title={profile.transport_implementation_id}>
                          {safeHolderIdentifier(profile.transport_implementation_id)}
                        </code>{" "}
                        v{profile.transport_implementation_version}
                      </span>
                      <span>
                        Adapter <code title={profile.adapter_contract_id}>{profile.adapter_contract_id}</code>{" "}
                        v{profile.adapter_contract_version}
                      </span>
                      <span>
                        Event {profile.supported_event_contracts
                          .map(formatTransportEventContract)
                          .join(", ")}
                      </span>
                      <span>
                        Classification {profile.supported_classifications.join(", ")} | representation{" "}
                        {profile.supported_representations.join(", ")} | encoding{" "}
                        {profile.supported_encodings.join(", ")}
                      </span>
                      <span>
                        Delivery {profile.supported_delivery_semantics.join(", ")} | durable{" "}
                        {profile.durable_delivery_supported ? "supported" : "not supported"}
                      </span>
                      <span>
                        Ordering {profile.supported_ordering_key_kinds.join(", ")} | retention{" "}
                        {profile.supported_retention_classes.join(", ")}
                      </span>
                      <span>
                        Maximum {profile.maximum_message_byte_count.toLocaleString()} bytes | encryption{" "}
                        {profile.transport_encryption_required ? "required" : "not required"} | restricted network{" "}
                        {profile.restricted_network_supported ? "supported" : "not supported"}
                      </span>
                      <span>
                        Captured {formatTimestamp(profile.captured_at)} by{" "}
                        <code title={profile.snapshotter_subject_id}>
                          {safeHolderIdentifier(profile.snapshotter_subject_id)}
                        </code>
                      </span>
                      <span>
                        Snapshot <code title={profile.snapshot_id}>{safeHolderIdentifier(profile.snapshot_id)}</code>{" "}
                        | resource <code title={profile.transport_resource_id}>{safeHolderIdentifier(profile.transport_resource_id)}</code>
                      </span>
                      <span>
                        Source {shortDigest(profile.source_profile_digest)} | resource{" "}
                        {shortDigest(profile.transport_resource_digest)} | adapter{" "}
                        {shortDigest(profile.adapter_contract_digest)} | snapshot{" "}
                        <code title={profile.canonical_digest}>{shortDigest(profile.canonical_digest)}</code>
                      </span>
                      <span>
                        Authority route selection false | publication false | delivery false | dispatch false | execution false
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            These immutable records describe declared deployment capabilities only. They do not
            select or operate a transport.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-credential-access-authorization-lease-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">BOUNDED SINGLE-USE CREDENTIAL-ACCESS EVIDENCE</p>
            <h2 id="workflow-credential-access-authorization-lease-title">
              Credential-access authorization leases
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportCredentialAccessAuthorizationLeaseQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading credential-access authorization leases...</span>
          </div>
        )}
        {physicalTransportCredentialAccessAuthorizationLeaseQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportCredentialAccessAuthorizationLeaseErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportCredentialAccessAuthorizationLeaseErrorStatus === 403
                    ? "Credential-access lease permission is missing"
                    : "Credential-access authorization leases are unavailable"}
              </strong>
              <span>
                {physicalTransportCredentialAccessAuthorizationLeaseErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportCredentialAccessAuthorizationLeaseErrorStatus === 403
                    ? "Your current role or scope cannot inspect credential-access lease evidence."
                    : "No authorization or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportCredentialAccessAuthorizationLeaseErrorStatus !== 401 &&
              physicalTransportCredentialAccessAuthorizationLeaseErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry credential-access authorization lease read"
                  onClick={() =>
                    void physicalTransportCredentialAccessAuthorizationLeaseQuery.refetch()
                  }
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportCredentialAccessAuthorizationLeaseQuery.isSuccess &&
          physicalTransportCredentialAccessAuthorizationLeaseQuery.data
            .physical_transport_credential_access_authorization_leases.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <CalendarClock size={19} />
              <span>No credential-access authorization leases are recorded in this scope.</span>
            </div>
          )}
        {physicalTransportCredentialAccessAuthorizationLeaseQuery.isSuccess &&
          physicalTransportCredentialAccessAuthorizationLeaseQuery.data
            .physical_transport_credential_access_authorization_leases.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Credential-access authorization leases"
            >
              {physicalTransportCredentialAccessAuthorizationLeaseQuery.data.physical_transport_credential_access_authorization_leases.map(
                (lease) => (
                  <li key={lease.lease_id}>
                    <ShieldCheck size={18} />
                    <div>
                      <strong>
                        <code title={lease.lease_id}>{safeHolderIdentifier(lease.lease_id)}</code>
                        <span
                          className={`state-badge ${
                            lease.effective_state === "active" ? "neutral" : "warning"
                          }`}
                        >
                          {lease.effective_state === "active" ? "Active" : "Expired"}
                        </span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Freshness admission{" "}
                          <code title={lease.freshness_admission_id}>
                            {safeHolderIdentifier(lease.freshness_admission_id)}
                          </code>
                        </span>
                        <span>
                          Assignment revision{" "}
                          <code title={lease.assignment_revision}>
                            {safeHolderIdentifier(lease.assignment_revision)}
                          </code>
                        </span>
                        <span>
                          Credential generation {lease.credential_generation} | rotation epoch{" "}
                          {lease.rotation_epoch}
                        </span>
                        <span>
                          Policy <code title={lease.policy_id}>{safeHolderIdentifier(lease.policy_id)}</code>{" "}
                          v{lease.policy_version}
                        </span>
                        <span>
                          Organization {lease.scope.organization_id} | environment{" "}
                          {lease.scope.environment_id} | site {lease.scope.site_id}
                        </span>
                        <span>
                          Accessor <code title={lease.accessor_subject_id}>{safeHolderIdentifier(lease.accessor_subject_id)}</code>
                        </span>
                        <span>
                          Issued {formatTimestamp(lease.issued_at)} | valid until{" "}
                          {formatTimestamp(lease.valid_until)}
                        </span>
                        <span>
                          Immutable state {readableKind(lease.state)} | effective state{" "}
                          {lease.effective_state}
                        </span>
                        <span>Single use true | renewable false</span>
                        <span>
                          Integrity reference{" "}
                          <code title={lease.integrity_reference}>
                            {safeHolderIdentifier(lease.integrity_reference)}
                          </code>
                        </span>
                        <span className="workflow-physical-route-binding-authority">
                          Authority credential access true | endpoint resolution false |
                          protected-artifact access false | route selection false | route binding
                          false | credential selection false | credential-assignment binding false |
                          credential brokerage false | credential resolution false | credential
                          delivery false | network access false | readiness probe false |
                          publication false | delivery false | dispatch false | execution false |
                          infrastructure mutation false
                        </span>
                      </div>
                    </div>
                  </li>
                ),
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            This immutable lease authorizes only one future access attempt by the named workload.
            It does not resolve, expose, transfer, or deliver protected material and grants no
            operational authority.
          </span>
        </div>
      </section>

      <section
        className="workflow-transport-route-band"
        aria-labelledby="workflow-transport-route-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">DEPLOYMENT ROUTE EVIDENCE</p>
            <h2 id="workflow-transport-route-title">Transport route snapshots</h2>
          </div>
          <span>Read only</span>
        </div>
        {transportRouteSnapshotQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading transport route snapshots...</span>
          </div>
        )}
        {transportRouteSnapshotQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {transportRouteSnapshotErrorStatus === 401
                  ? "Your session has expired"
                  : transportRouteSnapshotErrorStatus === 403
                    ? "Transport route snapshot permission is missing"
                    : "Transport route snapshots are unavailable"}
              </strong>
              <span>
                {transportRouteSnapshotErrorStatus === 401
                  ? "Sign in again to continue."
                  : transportRouteSnapshotErrorStatus === 403
                    ? "Your current role or scope cannot inspect transport route snapshots."
                    : "No route, readiness, or operational state is inferred from this failed read."}
              </span>
            </div>
            {transportRouteSnapshotErrorStatus !== 401 &&
              transportRouteSnapshotErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry transport route snapshot read"
                  onClick={() => void transportRouteSnapshotQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {transportRouteSnapshotQuery.isSuccess &&
          transportRouteSnapshotQuery.data.transport_route_snapshots.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <Network size={19} /> No transport route snapshots are recorded in this scope.
            </div>
          )}
        {transportRouteSnapshotQuery.isSuccess &&
          transportRouteSnapshotQuery.data.transport_route_snapshots.length > 0 && (
            <ol
              className="workflow-step-preview workflow-transport-route-list"
              aria-label="Transport route snapshots"
            >
              {transportRouteSnapshotQuery.data.transport_route_snapshots.map((route) => (
                <li key={route.snapshot_id}>
                  <Network size={18} />
                  <div>
                    <strong>
                      <code title={route.route_id}>
                        {safeHolderIdentifier(route.route_id)}
                      </code>
                      <span className="state-badge neutral">{route.state}</span>
                    </strong>
                    <div className="workflow-transport-route-grid">
                      <span>
                        Revision <b>{route.route_revision}</b> | deployment{" "}
                        <code title={route.deployment_release_id}>
                          {safeHolderIdentifier(route.deployment_release_id)}
                        </code>{" "}
                        | {route.deployment_profile}
                      </span>
                      <span>
                        Route set <code>{safeHolderIdentifier(route.route_set_id)}</code> | revision {route.route_set_revision}
                      </span>
                      <span>
                        Selection epoch <code>{safeHolderIdentifier(route.selection_epoch_id)}</code> | revision {route.selection_epoch_revision}
                      </span>
                      <span>
                        Organization {route.scope.organization_id} | environment{" "}
                        {route.scope.environment_id} | site {route.scope.site_id}
                      </span>
                      <span>
                        Profile <code title={route.transport_profile_id}>{safeHolderIdentifier(route.transport_profile_id)}</code>{" "}
                        | revision {route.transport_profile_revision}
                      </span>
                      <span>
                        Resource <code title={route.transport_resource_id}>{safeHolderIdentifier(route.transport_resource_id)}</code>
                      </span>
                      <span>
                        Implementation <code title={route.transport_implementation_id}>{safeHolderIdentifier(route.transport_implementation_id)}</code>{" "}
                        v{route.transport_implementation_version}
                      </span>
                      <span>
                        Adapter <code title={route.adapter_contract_id}>{safeHolderIdentifier(route.adapter_contract_id)}</code>{" "}
                        v{route.adapter_contract_version}
                      </span>
                      <span>
                        Endpoint set <code>{safeHolderIdentifier(route.endpoint_set_id)}</code>{" "}
                        | revision {route.endpoint_set_revision}
                      </span>
                      <span>
                        Destination <code>{safeHolderIdentifier(route.destination_id)}</code>{" "}
                        | revision {route.destination_revision}
                      </span>
                      <span>
                        Routing contract <code>{safeHolderIdentifier(route.routing_contract_id)}</code>{" "}
                        | revision {route.routing_contract_revision}
                      </span>
                      <span>
                        Security <code title={route.transport_security_policy_id}>{safeHolderIdentifier(route.transport_security_policy_id)}</code>{" "}
                        v{route.transport_security_policy_version} | TLS {route.minimum_tls_version} minimum | server authentication required
                      </span>
                      <span>
                        Network <code title={route.network_policy_id}>{safeHolderIdentifier(route.network_policy_id)}</code>{" "}
                        v{route.network_policy_version} | {route.source_zone_class} to {route.destination_zone_class} | restricted internal
                      </span>
                      <span>
                        Credential requirement <code title={route.credential_requirement_profile_id}>{safeHolderIdentifier(route.credential_requirement_profile_id)}</code>{" "}
                        v{route.credential_requirement_profile_version} | {route.authentication_mechanism_class} | {route.principal_class}
                      </span>
                      <span>
                        Captured {formatTimestamp(route.captured_at)} by{" "}
                        <code title={route.snapshotter_subject_id}>{safeHolderIdentifier(route.snapshotter_subject_id)}</code>
                      </span>
                      <span>
                        Snapshot <code title={route.snapshot_id}>{safeHolderIdentifier(route.snapshot_id)}</code>
                      </span>
                      <span className="workflow-transport-route-authority">
                        Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            These immutable snapshots expose opaque deployment references only. They do not bind,
            resolve, probe, credential, publish, deliver, dispatch, or execute a route.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-credential-assignment-snapshot-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">HISTORICAL ASSIGNMENT EVIDENCE</p>
            <h2 id="workflow-credential-assignment-snapshot-title">
              Transport credential-assignment snapshots
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportCredentialAssignmentSnapshotQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading transport credential-assignment snapshots...</span>
          </div>
        )}
        {physicalTransportCredentialAssignmentSnapshotQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportCredentialAssignmentSnapshotErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportCredentialAssignmentSnapshotErrorStatus === 403
                    ? "Credential-assignment snapshot permission is missing"
                    : "Transport credential-assignment snapshots are unavailable"}
              </strong>
              <span>
                {physicalTransportCredentialAssignmentSnapshotErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportCredentialAssignmentSnapshotErrorStatus === 403
                    ? "Your current role or scope cannot inspect credential-assignment snapshot evidence."
                    : "No assignment lifecycle or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportCredentialAssignmentSnapshotErrorStatus !== 401 &&
              physicalTransportCredentialAssignmentSnapshotErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry transport credential-assignment snapshot read"
                  onClick={() => void physicalTransportCredentialAssignmentSnapshotQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportCredentialAssignmentSnapshotQuery.isSuccess &&
          physicalTransportCredentialAssignmentSnapshotQuery.data
            .transport_credential_assignment_snapshots.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <Database size={19} />
              <span>No transport credential-assignment snapshots are recorded in this scope.</span>
            </div>
          )}
        {physicalTransportCredentialAssignmentSnapshotQuery.isSuccess &&
          physicalTransportCredentialAssignmentSnapshotQuery.data
            .transport_credential_assignment_snapshots.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Transport credential-assignment snapshots"
            >
              {physicalTransportCredentialAssignmentSnapshotQuery.data.transport_credential_assignment_snapshots.map(
                (snapshot) => (
                  <li key={snapshot.snapshot_id}>
                    <ShieldCheck size={18} />
                    <div>
                      <strong>
                        <code title={snapshot.assignment_id}>
                          {safeHolderIdentifier(snapshot.assignment_id)}
                        </code>
                        <span className="state-badge neutral">Active when captured</span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Assignment revision <b>{snapshot.assignment_revision}</b>
                        </span>
                        <span>
                          Snapshot{" "}
                          <code title={snapshot.snapshot_id}>
                            {safeHolderIdentifier(snapshot.snapshot_id)}
                          </code>
                        </span>
                        <span>
                          Generation {snapshot.credential_generation} | rotation epoch{" "}
                          {snapshot.rotation_epoch}
                        </span>
                        <span>Activated {formatTimestamp(snapshot.activated_at)}</span>
                        <span>Expires {formatTimestamp(snapshot.expires_at)}</span>
                        <span>Captured {formatTimestamp(snapshot.captured_at)}</span>
                        <span>Historical record state {snapshot.state}</span>
                        <span className="workflow-physical-route-binding-authority">
                          Authority endpoint resolution false | protected artifact access false |
                          credential selection false | credential access false | credential
                          brokerage false | credential resolution false | credential delivery false |
                          network access false | readiness probe false | publication false | delivery
                          false | dispatch false | execution false | infrastructure mutation false
                        </span>
                      </div>
                    </div>
                  </li>
                ),
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            These immutable records preserve historical assignment evidence only. The current
            browser session can inspect them but cannot create, select, authorize, resolve, reveal,
            probe, publish, deliver, dispatch, or execute anything.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-physical-route-binding-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">IMMUTABLE ROUTE BINDING EVIDENCE</p>
            <h2 id="workflow-physical-route-binding-title">Physical transport route bindings</h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportRouteBindingQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading physical transport route bindings...</span>
          </div>
        )}
        {physicalTransportRouteBindingQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportRouteBindingErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportRouteBindingErrorStatus === 403
                    ? "Physical transport route binding permission is missing"
                    : "Physical transport route bindings are unavailable"}
              </strong>
              <span>
                {physicalTransportRouteBindingErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportRouteBindingErrorStatus === 403
                    ? "Your current role or scope cannot inspect physical route binding evidence."
                    : "No binding or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportRouteBindingErrorStatus !== 401 &&
              physicalTransportRouteBindingErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry physical transport route binding read"
                  onClick={() => void physicalTransportRouteBindingQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportRouteBindingQuery.isSuccess &&
          physicalTransportRouteBindingQuery.data.physical_transport_route_bindings.length ===
            0 && (
            <div className="workflow-empty-state" role="status">
              <Link2 size={19} /> No physical transport route bindings are recorded in this scope.
            </div>
          )}
        {physicalTransportRouteBindingQuery.isSuccess &&
          physicalTransportRouteBindingQuery.data.physical_transport_route_bindings.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Physical transport route bindings"
            >
              {physicalTransportRouteBindingQuery.data.physical_transport_route_bindings.map(
                (binding) => (
                  <li key={binding.binding_id}>
                    <Link2 size={18} />
                    <div>
                      <strong>
                        <code title={binding.binding_id}>
                          {safeHolderIdentifier(binding.binding_id)}
                        </code>
                        <span className="state-badge neutral">{binding.state}</span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Logical binding{" "}
                          <code title={binding.logical_channel_binding_id}>
                            {safeHolderIdentifier(binding.logical_channel_binding_id)}
                          </code>
                        </span>
                        <span>
                          Compatibility admission{" "}
                          <code title={binding.compatibility_admission_id}>
                            {safeHolderIdentifier(binding.compatibility_admission_id)}
                          </code>
                        </span>
                        <span>
                          Profile snapshot{" "}
                          <code title={binding.transport_profile_snapshot_id}>
                            {safeHolderIdentifier(binding.transport_profile_snapshot_id)}
                          </code>
                        </span>
                        <span>
                          Route snapshot{" "}
                          <code title={binding.transport_route_snapshot_id}>
                            {safeHolderIdentifier(binding.transport_route_snapshot_id)}
                          </code>
                        </span>
                        <span>
                          Policy <code title={binding.policy_id}>{safeHolderIdentifier(binding.policy_id)}</code>{" "}
                          v{binding.policy_version}
                        </span>
                        <span>
                          Organization {binding.scope.organization_id} | environment{" "}
                          {binding.scope.environment_id} | site {binding.scope.site_id}
                        </span>
                        <span>
                          Bound {formatTimestamp(binding.bound_at)} by{" "}
                          <code title={binding.binder_subject_id}>
                            {safeHolderIdentifier(binding.binder_subject_id)}
                          </code>
                        </span>
                        <span>
                          Integrity reference{" "}
                          <code title={binding.integrity_reference}>
                            {safeHolderIdentifier(binding.integrity_reference)}
                          </code>
                        </span>
                        <span className="workflow-physical-route-binding-authority">
                          Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false
                        </span>
                      </div>
                    </div>
                  </li>
                ),
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            Binding records immutable lineage only. It grants no route selection, endpoint,
            credential, network, readiness, publication, delivery, dispatch, or execution authority.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-physical-transport-credential-assignment-binding-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">IMMUTABLE CREDENTIAL-ASSIGNMENT BINDING EVIDENCE</p>
            <h2 id="workflow-physical-transport-credential-assignment-binding-title">
              Physical transport credential-assignment bindings
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportCredentialAssignmentBindingQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading physical transport credential-assignment bindings...</span>
          </div>
        )}
        {physicalTransportCredentialAssignmentBindingQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportCredentialAssignmentBindingErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportCredentialAssignmentBindingErrorStatus === 403
                    ? "Physical transport credential-assignment binding permission is missing"
                    : "Physical transport credential-assignment bindings are unavailable"}
              </strong>
              <span>
                {physicalTransportCredentialAssignmentBindingErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportCredentialAssignmentBindingErrorStatus === 403
                    ? "Your current role or scope cannot inspect credential-assignment binding evidence."
                    : "No binding or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportCredentialAssignmentBindingErrorStatus !== 401 &&
              physicalTransportCredentialAssignmentBindingErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry physical transport credential-assignment binding read"
                  onClick={() =>
                    void physicalTransportCredentialAssignmentBindingQuery.refetch()
                  }
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportCredentialAssignmentBindingQuery.isSuccess &&
          physicalTransportCredentialAssignmentBindingQuery.data
            .physical_transport_credential_assignment_bindings.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <Link2 size={19} /> No physical transport credential-assignment bindings are recorded
              in this scope.
            </div>
          )}
        {physicalTransportCredentialAssignmentBindingQuery.isSuccess &&
          physicalTransportCredentialAssignmentBindingQuery.data
            .physical_transport_credential_assignment_bindings.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Physical transport credential-assignment bindings"
            >
              {physicalTransportCredentialAssignmentBindingQuery.data.physical_transport_credential_assignment_bindings.map(
                (binding) => (
                  <li key={binding.binding_id}>
                    <Link2 size={18} />
                    <div>
                      <strong>
                        <code title={binding.binding_id}>
                          {safeHolderIdentifier(binding.binding_id)}
                        </code>
                        <span className="state-badge neutral">{binding.state}</span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Route binding{" "}
                          <code title={binding.physical_transport_route_binding_id}>
                            {safeHolderIdentifier(binding.physical_transport_route_binding_id)}
                          </code>
                        </span>
                        <span>
                          Credential-assignment snapshot{" "}
                          <code title={binding.credential_assignment_snapshot_id}>
                            {safeHolderIdentifier(binding.credential_assignment_snapshot_id)}
                          </code>
                        </span>
                        <span>Bound {formatTimestamp(binding.bound_at)}</span>
                        <span>
                          Integrity reference{" "}
                          <code title={binding.integrity_reference}>
                            {safeHolderIdentifier(binding.integrity_reference)}
                          </code>
                        </span>
                      </div>
                    </div>
                  </li>
                ),
              )}
            </ol>
          )}
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-physical-transport-credential-assignment-freshness-admission-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">POINT-IN-TIME CREDENTIAL-ASSIGNMENT FRESHNESS EVIDENCE</p>
            <h2 id="workflow-physical-transport-credential-assignment-freshness-admission-title">
              Physical transport credential-assignment freshness admissions
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportCredentialAssignmentFreshnessAdmissionQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>
              Loading physical transport credential-assignment freshness admissions...
            </span>
          </div>
        )}
        {physicalTransportCredentialAssignmentFreshnessAdmissionQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus === 403
                    ? "Credential-assignment freshness permission is missing"
                    : "Credential-assignment freshness admissions are unavailable"}
              </strong>
              <span>
                {physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus === 403
                    ? "Your current role or scope cannot inspect credential-assignment freshness evidence."
                    : "No current-head, expiry, revocation or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus !== 401 &&
              physicalTransportCredentialAssignmentFreshnessAdmissionErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry physical transport credential-assignment freshness admission read"
                  onClick={() =>
                    void physicalTransportCredentialAssignmentFreshnessAdmissionQuery.refetch()
                  }
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportCredentialAssignmentFreshnessAdmissionQuery.isSuccess &&
          physicalTransportCredentialAssignmentFreshnessAdmissionQuery.data
            .physical_transport_credential_assignment_freshness_admissions.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <CalendarClock size={19} /> No physical transport credential-assignment freshness
              admissions are recorded in this scope.
            </div>
          )}
        {physicalTransportCredentialAssignmentFreshnessAdmissionQuery.isSuccess &&
          physicalTransportCredentialAssignmentFreshnessAdmissionQuery.data
            .physical_transport_credential_assignment_freshness_admissions.length > 0 && (
            <>
              <ol
                className="workflow-step-preview workflow-physical-route-binding-list"
                aria-label="Physical transport credential-assignment freshness admissions"
              >
                {physicalTransportCredentialAssignmentFreshnessAdmissionQuery.data.physical_transport_credential_assignment_freshness_admissions.map(
                  (admission) => {
                    const windowOpen = credentialAssignmentFreshnessWindowIsOpen(
                      admission.valid_until,
                    );
                    return (
                      <li key={admission.freshness_admission_id}>
                        <ShieldCheck size={18} />
                        <div>
                          <strong>
                            <code title={admission.freshness_admission_id}>
                              {safeHolderIdentifier(admission.freshness_admission_id)}
                            </code>
                            <span className="state-badge neutral">{admission.state}</span>
                            <span
                              className={`state-badge ${windowOpen ? "neutral" : "warning"}`}
                            >
                              {windowOpen ? "Time window open" : "Expired"}
                            </span>
                          </strong>
                          <div className="workflow-physical-route-binding-grid">
                            <span>
                              Credential-assignment binding{" "}
                              <code
                                title={
                                  admission.physical_transport_credential_assignment_binding_id
                                }
                              >
                                {safeHolderIdentifier(
                                  admission.physical_transport_credential_assignment_binding_id,
                                )}
                              </code>
                            </span>
                            <span>
                              Assignment snapshot{" "}
                              <code title={admission.credential_assignment_snapshot_id}>
                                {safeHolderIdentifier(admission.credential_assignment_snapshot_id)}
                              </code>
                            </span>
                            <span>
                              Assignment <code title={admission.assignment_id}>{safeHolderIdentifier(admission.assignment_id)}</code>{" "}
                              | revision <code title={admission.assignment_revision}>{safeHolderIdentifier(admission.assignment_revision)}</code>
                            </span>
                            <span>
                              Rotation epoch {admission.rotation_epoch} | credential generation{" "}
                              {admission.credential_generation}
                            </span>
                            <span>
                              Evaluated {formatTimestamp(admission.evaluated_at)} | valid until{" "}
                              {formatTimestamp(admission.valid_until)}
                            </span>
                            <span>
                              Policy <code title={admission.policy_id}>{safeHolderIdentifier(admission.policy_id)}</code>{" "}
                              v{admission.policy_version}
                            </span>
                            <span>
                              Organization {admission.scope.organization_id} | environment{" "}
                              {admission.scope.environment_id} | site {admission.scope.site_id}
                            </span>
                            <span>
                              Admitter <code title={admission.admitter_subject_id}>{safeHolderIdentifier(admission.admitter_subject_id)}</code>
                            </span>
                            <span>
                              Integrity reference{" "}
                              <code title={admission.integrity_reference}>
                                {safeHolderIdentifier(admission.integrity_reference)}
                              </code>
                            </span>
                            <span>
                              Zero authority: route selection and binding, endpoint resolution,
                              protected-artifact access, credential selection, assignment binding,
                              access, brokerage, resolution and delivery, network access, readiness
                              probes, publication, delivery, dispatch, execution and infrastructure
                              mutation are all false.
                            </span>
                          </div>
                        </div>
                      </li>
                    );
                  },
                )}
              </ol>
              <p className="workflow-safety-note">
                Freshness admissions are point-in-time evidence only. An open time window does not
                independently prove that the assignment remains the current, active or non-revoked
                head and grants no credential or operational authority.
              </p>
            </>
          )}
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-physical-route-freshness-admission-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">POINT-IN-TIME ROUTE FRESHNESS EVIDENCE</p>
            <h2 id="workflow-physical-route-freshness-admission-title">
              Physical transport route freshness admissions
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {physicalTransportRouteFreshnessAdmissionQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading physical transport route freshness admissions...</span>
          </div>
        )}
        {physicalTransportRouteFreshnessAdmissionQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {physicalTransportRouteFreshnessAdmissionErrorStatus === 401
                  ? "Your session has expired"
                  : physicalTransportRouteFreshnessAdmissionErrorStatus === 403
                    ? "Physical transport route freshness permission is missing"
                    : "Physical transport route freshness admissions are unavailable"}
              </strong>
              <span>
                {physicalTransportRouteFreshnessAdmissionErrorStatus === 401
                  ? "Sign in again to continue."
                  : physicalTransportRouteFreshnessAdmissionErrorStatus === 403
                    ? "Your current role or scope cannot inspect route freshness evidence."
                    : "No freshness or operational state is inferred from this failed read."}
              </span>
            </div>
            {physicalTransportRouteFreshnessAdmissionErrorStatus !== 401 &&
              physicalTransportRouteFreshnessAdmissionErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry physical transport route freshness admission read"
                  onClick={() => void physicalTransportRouteFreshnessAdmissionQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {physicalTransportRouteFreshnessAdmissionQuery.isSuccess &&
          physicalTransportRouteFreshnessAdmissionQuery.data
            .physical_transport_route_freshness_admissions.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <CalendarClock size={19} /> No physical transport route freshness admissions are
              recorded in this scope.
            </div>
          )}
        {physicalTransportRouteFreshnessAdmissionQuery.isSuccess &&
          physicalTransportRouteFreshnessAdmissionQuery.data
            .physical_transport_route_freshness_admissions.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Physical transport route freshness admissions"
            >
              {physicalTransportRouteFreshnessAdmissionQuery.data.physical_transport_route_freshness_admissions.map(
                (admission) => {
                  const windowOpen = routeFreshnessWindowIsOpen(admission.valid_until);
                  return (
                  <li key={admission.freshness_admission_id}>
                    <ShieldCheck size={18} />
                    <div>
                      <strong>
                        <code title={admission.freshness_admission_id}>
                          {safeHolderIdentifier(admission.freshness_admission_id)}
                        </code>
                        <span className="state-badge neutral">{admission.state}</span>
                        <span className={`state-badge ${windowOpen ? "neutral" : "warning"}`}>
                          {windowOpen ? "Window open" : "Expired"}
                        </span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Physical binding{" "}
                          <code title={admission.physical_transport_route_binding_id}>
                            {safeHolderIdentifier(
                              admission.physical_transport_route_binding_id,
                            )}
                          </code>
                        </span>
                        <span>
                          Route snapshot{" "}
                          <code title={admission.transport_route_snapshot_id}>
                            {safeHolderIdentifier(admission.transport_route_snapshot_id)}
                          </code>
                        </span>
                        <span>
                          Selection head{" "}
                          <code title={admission.selection_head_id}>
                            {safeHolderIdentifier(admission.selection_head_id)}
                          </code>{" "}
                          | generation {admission.selection_generation}
                        </span>
                        <span>
                          Policy <code title={admission.policy_id}>{safeHolderIdentifier(admission.policy_id)}</code>{" "}
                          v{admission.policy_version}
                        </span>
                        <span>
                          Organization {admission.scope.organization_id} | environment{" "}
                          {admission.scope.environment_id} | site {admission.scope.site_id}
                        </span>
                        <span>
                          Evaluated {formatTimestamp(admission.evaluated_at)} | valid until{" "}
                          {formatTimestamp(admission.valid_until)}
                        </span>
                        <span>
                          Admitted by{" "}
                          <code title={admission.admitter_subject_id}>
                            {safeHolderIdentifier(admission.admitter_subject_id)}
                          </code>
                        </span>
                        <span>
                          Integrity reference{" "}
                          <code title={admission.integrity_reference}>
                            {safeHolderIdentifier(admission.integrity_reference)}
                          </code>
                        </span>
                        <span className="workflow-physical-route-binding-authority">
                          Authority route selection false | route binding false | endpoint resolution false | credential access false | network access false | readiness probe false | publication false | delivery false | dispatch false | execution false
                        </span>
                      </div>
                    </div>
                  </li>
                  );
                },
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            Freshness admissions are point-in-time evidence only. They expose no route details and
            grant no endpoint, credential, network, readiness, publication, delivery, dispatch, or
            execution authority.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-endpoint-resolution-authorization-lease-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">BOUNDED SINGLE-USE AUTHORIZATION EVIDENCE</p>
            <h2 id="workflow-endpoint-resolution-authorization-lease-title">
              Endpoint-resolution authorization leases
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {endpointResolutionAuthorizationLeaseQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading endpoint-resolution authorization leases...</span>
          </div>
        )}
        {endpointResolutionAuthorizationLeaseQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {endpointResolutionAuthorizationLeaseErrorStatus === 401
                  ? "Your session has expired"
                  : endpointResolutionAuthorizationLeaseErrorStatus === 403
                    ? "Endpoint-resolution lease permission is missing"
                    : "Endpoint-resolution authorization leases are unavailable"}
              </strong>
              <span>
                {endpointResolutionAuthorizationLeaseErrorStatus === 401
                  ? "Sign in again to continue."
                  : endpointResolutionAuthorizationLeaseErrorStatus === 403
                    ? "Your current role or scope cannot inspect endpoint-resolution lease evidence."
                    : "No authorization, endpoint, or operational state is inferred from this failed read."}
              </span>
            </div>
            {endpointResolutionAuthorizationLeaseErrorStatus !== 401 &&
              endpointResolutionAuthorizationLeaseErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry endpoint-resolution authorization lease read"
                  onClick={() => void endpointResolutionAuthorizationLeaseQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {endpointResolutionAuthorizationLeaseQuery.isSuccess &&
          endpointResolutionAuthorizationLeaseQuery.data.endpoint_resolution_authorization_leases
            .length === 0 && (
            <div className="workflow-empty-state" role="status">
              <CalendarClock size={19} />
              <span>
                No endpoint-resolution authorization leases are recorded in this scope.
              </span>
            </div>
          )}
        {endpointResolutionAuthorizationLeaseQuery.isSuccess &&
          endpointResolutionAuthorizationLeaseQuery.data.endpoint_resolution_authorization_leases
            .length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Endpoint-resolution authorization leases"
            >
              {endpointResolutionAuthorizationLeaseQuery.data.endpoint_resolution_authorization_leases.map(
                (lease) => (
                  <li key={lease.lease_id}>
                    <ShieldCheck size={18} />
                    <div>
                      <strong>
                        <code title={lease.lease_id}>{safeHolderIdentifier(lease.lease_id)}</code>
                        <span
                          className={`state-badge ${
                            lease.effective_state === "active" ? "neutral" : "warning"
                          }`}
                        >
                          {lease.effective_state === "active"
                            ? "Active"
                            : lease.effective_state === "expired"
                              ? "Expired"
                              : "Consumed"}
                        </span>
                      </strong>
                      <div className="workflow-physical-route-binding-grid">
                        <span>
                          Freshness admission{" "}
                          <code title={lease.freshness_admission_id}>
                            {safeHolderIdentifier(lease.freshness_admission_id)}
                          </code>{" "}
                          | generation {lease.selection_generation}
                        </span>
                        <span>
                          Policy <code title={lease.policy_id}>{safeHolderIdentifier(lease.policy_id)}</code>{" "}
                          v{lease.policy_version}
                        </span>
                        <span>
                          Organization {lease.scope.organization_id} | environment{" "}
                          {lease.scope.environment_id} | site {lease.scope.site_id}
                        </span>
                        <span>
                          Resolver workload{" "}
                          <code title={lease.resolver_subject_id}>
                            {safeHolderIdentifier(lease.resolver_subject_id)}
                          </code>
                        </span>
                        <span>
                          Authorized {formatTimestamp(lease.authorized_at)} | expires{" "}
                          {formatTimestamp(lease.expires_at)}
                        </span>
                        <span>Single use true | renewable false</span>
                        <span>
                          Integrity reference{" "}
                          <code title={lease.integrity_reference}>
                            {safeHolderIdentifier(lease.integrity_reference)}
                          </code>
                        </span>
                        <span className="workflow-physical-route-binding-authority">
                          Authority endpoint resolution true for the named resolver workload only |
                          route selection false | route binding false | credential access false |
                          network access false | readiness probe false | publication false | delivery
                          false | dispatch false | execution false
                        </span>
                      </div>
                    </div>
                  </li>
                ),
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            Lease metadata is read-only. Only the named resolver workload may use an independently
            revalidated, unexpired lease for one future protected resolution attempt. The browser
            cannot issue, renew, transfer, consume, or resolve it, and no endpoint, locator,
            credential, network, readiness, publication, delivery, dispatch, or execution access is
            exposed.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-endpoint-materialization-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">PROTECTED MATERIALIZATION EVIDENCE</p>
            <h2 id="workflow-endpoint-materialization-title">
              Endpoint materialization results
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {endpointMaterializationQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading endpoint materialization results...</span>
          </div>
        )}
        {endpointMaterializationQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {endpointMaterializationErrorStatus === 401
                  ? "Your session has expired"
                  : endpointMaterializationErrorStatus === 403
                    ? "Endpoint materialization evidence permission is missing"
                    : "Endpoint materialization results are unavailable"}
              </strong>
              <span>
                {endpointMaterializationErrorStatus === 401
                  ? "Sign in again to continue."
                  : endpointMaterializationErrorStatus === 403
                    ? "Your current role or scope cannot inspect endpoint materialization evidence."
                    : "No materialization outcome or operational state is inferred from this failed read."}
              </span>
            </div>
            {endpointMaterializationErrorStatus !== 401 &&
              endpointMaterializationErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry endpoint materialization result read"
                  onClick={() => void endpointMaterializationQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {endpointMaterializationQuery.isSuccess &&
          endpointMaterializationQuery.data.physical_transport_endpoint_materializations.length ===
            0 && (
            <div className="workflow-empty-state" role="status">
              <Database size={19} />
              <span>No endpoint materialization results are recorded in this scope.</span>
            </div>
          )}
        {endpointMaterializationQuery.isSuccess &&
          endpointMaterializationQuery.data.physical_transport_endpoint_materializations.length >
            0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Endpoint materialization results"
            >
              {endpointMaterializationQuery.data.physical_transport_endpoint_materializations.map(
                (materialization) => {
                  const outcomeLabel =
                    materialization.outcome === "materialized_protected"
                      ? "Protected result stored"
                      : materialization.outcome === "failed_closed_consumed"
                        ? "Failed closed"
                        : "Outcome uncertain";
                  return (
                    <li key={materialization.materialization_id}>
                      {materialization.outcome === "materialized_protected" ? (
                        <ShieldCheck size={18} />
                      ) : (
                        <Ban size={18} />
                      )}
                      <div>
                        <strong>
                          <code title={materialization.materialization_id}>
                            {safeHolderIdentifier(materialization.materialization_id)}
                          </code>
                          <span
                            className={`state-badge ${
                              materialization.outcome === "materialized_protected"
                                ? "neutral"
                                : "warning"
                            }`}
                          >
                            {outcomeLabel}
                          </span>
                        </strong>
                        <div className="workflow-physical-route-binding-grid">
                          <span>
                            Consumed lease{" "}
                            <code title={materialization.lease_id}>
                              {safeHolderIdentifier(materialization.lease_id)}
                            </code>
                          </span>
                          <span>
                            Freshness admission{" "}
                            <code title={materialization.freshness_admission_id}>
                              {safeHolderIdentifier(materialization.freshness_admission_id)}
                            </code>{" "}
                            | generation {materialization.selection_generation}
                          </span>
                          <span>
                            Policy{" "}
                            <code title={materialization.policy_id}>
                              {safeHolderIdentifier(materialization.policy_id)}
                            </code>{" "}
                            v{materialization.policy_version}
                          </span>
                          <span>
                            Organization {materialization.scope.organization_id} | environment{" "}
                            {materialization.scope.environment_id} | site{" "}
                            {materialization.scope.site_id}
                          </span>
                          <span>
                            Resolver workload{" "}
                            <code title={materialization.resolver_subject_id}>
                              {safeHolderIdentifier(materialization.resolver_subject_id)}
                            </code>
                          </span>
                          <span>Lease consumed {formatTimestamp(materialization.consumed_at)}</span>
                          <span>
                            Result recorded{" "}
                            {materialization.recorded_at === null
                              ? "Not recorded"
                              : formatTimestamp(materialization.recorded_at)}
                          </span>
                          <span>
                            Protected storage{" "}
                            {materialization.protected_storage_verified
                              ? "Verified"
                              : "Not verified"}{" "}
                            | raw endpoint disclosed false
                          </span>
                          <span>
                            Integrity reference{" "}
                            <code title={materialization.integrity_reference}>
                              {safeHolderIdentifier(materialization.integrity_reference)}
                            </code>
                          </span>
                          <span className="workflow-physical-route-binding-authority">
                            Authority route selection false | route binding false | endpoint
                            resolution false | credential access false | network access false |
                            readiness probe false | publication false | delivery false | dispatch
                            false | execution false
                          </span>
                        </div>
                      </div>
                    </li>
                  );
                },
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            This read-only inventory confirms one-way lease consumption and minimized outcome
            evidence only. It exposes no endpoint coordinates, credentials, protected storage
            access, network access, or operational authority.
          </span>
        </div>
      </section>

      <section
        className="workflow-physical-route-binding-band"
        aria-labelledby="workflow-credential-materialization-title"
      >
        <div className="workflow-section-heading">
          <div>
            <p className="eyebrow">PROTECTED CREDENTIAL EVIDENCE</p>
            <h2 id="workflow-credential-materialization-title">
              Credential materialization attempts and results
            </h2>
          </div>
          <span>Read only</span>
        </div>
        {credentialMaterializationQuery.isLoading && (
          <div className="workflow-empty-state" role="status">
            <RefreshCw className="spin" size={18} />
            <span>Loading credential materialization evidence...</span>
          </div>
        )}
        {credentialMaterializationQuery.isError && (
          <div className="inline-error" role="alert">
            <div>
              <strong>
                {credentialMaterializationErrorStatus === 401
                  ? "Your session has expired"
                  : credentialMaterializationErrorStatus === 403
                    ? "Credential materialization evidence permission is missing"
                    : "Credential materialization evidence is unavailable"}
              </strong>
              <span>
                {credentialMaterializationErrorStatus === 401
                  ? "Sign in again to continue."
                  : credentialMaterializationErrorStatus === 403
                    ? "Your current role or scope cannot inspect credential materialization evidence."
                    : "No materialization result or operational state is inferred from this failed read."}
              </span>
            </div>
            {credentialMaterializationErrorStatus !== 401 &&
              credentialMaterializationErrorStatus !== 403 && (
                <button
                  className="secondary-action"
                  type="button"
                  aria-label="Retry credential materialization evidence read"
                  onClick={() => void credentialMaterializationQuery.refetch()}
                >
                  <RefreshCw size={16} />
                  Retry
                </button>
              )}
          </div>
        )}
        {credentialMaterializationQuery.isSuccess &&
          credentialMaterializationQuery.data
            .physical_transport_credential_materialization_attempts.length === 0 && (
            <div className="workflow-empty-state" role="status">
              <Database size={19} />
              <span>No credential materialization attempts are recorded in this scope.</span>
            </div>
          )}
        {credentialMaterializationQuery.isSuccess &&
          credentialMaterializationQuery.data
            .physical_transport_credential_materialization_attempts.length > 0 && (
            <ol
              className="workflow-step-preview workflow-physical-route-binding-list"
              aria-label="Credential materialization attempts and results"
            >
              {credentialMaterializationQuery.data.physical_transport_credential_materialization_attempts.map(
                (attempt) => {
                  const result =
                    credentialMaterializationQuery.data.physical_transport_credential_materialization_results.find(
                      (candidate) => candidate.attempt_id === attempt.attempt_id,
                    );
                  const outcomeLabel = result
                    ? result.state === "materialized_protected"
                      ? "Protected result recorded"
                      : "Materialization failed"
                    : "No known result";
                  return (
                    <li key={attempt.attempt_id}>
                      {result?.state === "materialized_protected" ? (
                        <ShieldCheck size={18} />
                      ) : (
                        <Ban size={18} />
                      )}
                      <div>
                        <strong>
                          <code title={attempt.attempt_id}>
                            {safeHolderIdentifier(attempt.attempt_id)}
                          </code>
                          <span
                            className={`state-badge ${
                              result?.state === "materialized_protected" ? "neutral" : "warning"
                            }`}
                          >
                            {outcomeLabel}
                          </span>
                        </strong>
                        <div className="workflow-physical-route-binding-grid">
                          <span>
                            Materialization <code title={attempt.materialization_id}>{safeHolderIdentifier(attempt.materialization_id)}</code>
                          </span>
                          <span>
                            Consumption claim <code title={attempt.consumption_claim_id}>{safeHolderIdentifier(attempt.consumption_claim_id)}</code>
                          </span>
                          <span>
                            Authorization lease <code title={attempt.authorization_lease_id}>{safeHolderIdentifier(attempt.authorization_lease_id)}</code>
                          </span>
                          <span>
                            Freshness admission <code title={attempt.freshness_admission_id}>{safeHolderIdentifier(attempt.freshness_admission_id)}</code>
                          </span>
                          <span>
                            Assignment snapshot <code title={attempt.credential_assignment_snapshot_id}>{safeHolderIdentifier(attempt.credential_assignment_snapshot_id)}</code>
                          </span>
                          <span>
                            Assignment <code title={attempt.assignment_id}>{safeHolderIdentifier(attempt.assignment_id)}</code> | revision {attempt.assignment_revision}
                          </span>
                          <span>
                            Credential generation {attempt.credential_generation} | rotation epoch {attempt.rotation_epoch}
                          </span>
                          <span>
                            Organization {attempt.scope.organization_id} | environment {attempt.scope.environment_id} | site {attempt.scope.site_id}
                          </span>
                          <span>
                            Accessor workload <code title={attempt.accessor_subject_id}>{safeHolderIdentifier(attempt.accessor_subject_id)}</code>
                          </span>
                          <span>
                            Policy <code title={attempt.policy_id}>{safeHolderIdentifier(attempt.policy_id)}</code> v{attempt.policy_version}
                          </span>
                          <span>Started {formatTimestamp(attempt.started_at)}</span>
                          <span>Freshness valid until {formatTimestamp(attempt.freshness_valid_until)}</span>
                          <span>Lease valid until {formatTimestamp(attempt.lease_valid_until)}</span>
                          {result && (
                            <>
                              <span>Completed {formatTimestamp(result.completed_at)}</span>
                              <span>
                                Usable until {result.usable_until === null ? "Not applicable" : formatTimestamp(result.usable_until)}
                              </span>
                              <span>
                                Failure class {result.failure_class === null ? "None" : readableKind(result.failure_class)}
                              </span>
                              <span>
                                Materializer <code title={result.materializer_id}>{safeHolderIdentifier(result.materializer_id)}</code> v{result.materializer_version}
                              </span>
                              <span>
                                Protected artifact revoked {String(result.protected_artifact_revoked)} | cleanup confirmed true
                              </span>
                              <span>
                                Result integrity <code title={result.integrity_reference}>{safeHolderIdentifier(result.integrity_reference)}</code>
                              </span>
                            </>
                          )}
                          <span>
                            Attempt integrity <code title={attempt.integrity_reference}>{safeHolderIdentifier(attempt.integrity_reference)}</code>
                          </span>
                          <span className="workflow-physical-route-binding-authority">
                            Authority endpoint resolution false | protected artifact access false |
                            route selection false | route binding false | credential selection false |
                            credential assignment binding false | credential access false |
                            credential brokerage false | credential resolution false | credential
                            delivery false | network access false | readiness probe false |
                            publication false | delivery false | dispatch false | execution false |
                            infrastructure mutation false
                          </span>
                        </div>
                      </div>
                    </li>
                  );
                },
              )}
            </ol>
          )}
        <div className="workflow-safety-boundary" role="note">
          <LockKeyhole size={18} />
          <span>
            This normal-session inventory is read-only. It exposes minimized lineage and outcome
            evidence only, with no credential content, protected-artifact access, materialization
            action, retry operation, delivery, network, dispatch, execution, or mutation authority.
          </span>
        </div>
      </section>

      {loading && (
        <div className="workspace-message" role="status"><RefreshCw className="spin" size={18} /><span>Loading authorized workflow context...</span></div>
      )}
      {failed && (
        <div className="workspace-message error-state" role="alert">
          <div><strong>{sessionExpired ? "Your session has expired" : "Workflow planning is unavailable"}</strong><p>{sessionExpired ? "Sign in again to continue." : "No plan data is inferred. Retry the authorized request."}</p></div>
          {!sessionExpired && <button type="button" onClick={refresh}><RefreshCw size={15} /> Retry</button>}
        </div>
      )}

      {!loading && !failed && (
        <>
          <section className="workflow-definition-band" aria-labelledby="workflow-definitions-title">
            <div className="workflow-section-heading">
              <div><p className="eyebrow">VERSIONED REGISTRY</p><h2 id="workflow-definitions-title">Available definitions</h2></div>
              <span>{definitions.length} definitions</span>
            </div>
            <div className="workflow-definition-list">
              {definitions.map((definition) => (
                <button
                  key={definition.definition_id}
                  type="button"
                  className="workflow-definition-row"
                  data-selected={definition.definition_id === definitionId}
                  onClick={() => setDefinitionId(definition.definition_id)}
                  aria-pressed={definition.definition_id === definitionId}
                >
                  <Workflow size={18} />
                  <span><strong>{definition.title}</strong><small>{definition.purpose}</small></span>
                  <code>v{definition.version}</code>
                </button>
              ))}
            </div>
          </section>

          <section className="workflow-plan-composer" aria-labelledby="workflow-create-title">
            <div className="workflow-section-heading">
              <div><p className="eyebrow">PLAN INTENT</p><h2 id="workflow-create-title">Create a run plan</h2></div>
              <span>No steps will run</span>
            </div>
            <div className="workflow-form-grid">
              <label>Definition<select value={definitionId} onChange={(event) => setDefinitionId(event.target.value)}><option value="">Select definition</option>{definitions.map((definition) => <option key={definition.definition_id} value={definition.definition_id}>{definition.title}</option>)}</select></label>
              <label>Authorized storage target<select value={targetId} onChange={(event) => setTargetId(event.target.value)}><option value="">Select target</option>{authorizedTargets.map((target) => <option key={target.targetId} value={target.targetId}>{target.displayName}</option>)}</select></label>
              <label>Purpose<input value={purpose} maxLength={240} onChange={(event) => setPurpose(event.target.value)} placeholder="Reason for creating this plan" /></label>
              <label>Input summary<textarea value={inputSummary} maxLength={1000} onChange={(event) => setInputSummary(event.target.value)} placeholder="Evidence and boundaries to consider" /></label>
            </div>
            {selectedDefinition && (
              <ol className="workflow-step-preview">
                {selectedDefinition.steps.map((step) => <li key={step.step_id}><span>{step.ordinal}</span><div><strong>{step.title}</strong><small>{readableKind(step.kind)} | {step.capability_class} | not started</small></div></li>)}
              </ol>
            )}
            {authorizedTargets.length === 0 && <div className="workflow-empty-state">No authorized storage target is available in this scope.</div>}
            {createMutation.isError && <div className="workspace-message error-state" role="alert">Plan creation failed. The request did not change infrastructure.</div>}
            <button className="primary-action" type="button" disabled={!canCreate} onClick={() => selectedDefinition && createMutation.mutate(selectedDefinition)}><Plus size={16} /> Create plan</button>
          </section>

          <section className="workflow-plan-history" aria-labelledby="workflow-history-title">
            <div className="workflow-section-heading"><div><p className="eyebrow">PLAN HISTORY</p><h2 id="workflow-history-title">Workflow plans</h2></div><span>{plansQuery.data?.durable ? "durable" : "development memory"}</span></div>
            {(plansQuery.data?.plans.length ?? 0) === 0 ? (
              <div className="workflow-empty-state"><FileClock size={20} /> No workflow plans in this scope.</div>
            ) : (
              <div className="workflow-plan-list">{plansQuery.data?.plans.map((plan) => <button type="button" key={plan.plan_id} onClick={() => selectPlan(plan)}><CalendarClock size={18} /><span><strong>{definitions.find((item) => item.definition_id === plan.definition_id)?.title ?? plan.definition_id}</strong><small>{plan.target_id} | {new Date(plan.created_at).toLocaleString()}</small></span><span className="state-badge neutral">{plan.state}</span></button>)}</div>
            )}
          </section>

          {selectedPlan && (
            <section className="workflow-plan-detail" aria-labelledby="workflow-plan-detail-title">
              <div className="workflow-section-heading"><div><p className="eyebrow">EXACT PLAN</p><h2 id="workflow-plan-detail-title">{selectedPlan.plan_id}</h2></div><button className="icon-button" type="button" aria-label="Close plan detail" onClick={() => setSelectedPlan(null)}><X size={17} /></button></div>
              <dl><div><dt>State</dt><dd>{selectedPlan.state}</dd></div><div><dt>Target</dt><dd>{selectedPlan.target_id}</dd></div><div><dt>Definition</dt><dd>{selectedPlan.definition_id} v{selectedPlan.definition_version}</dd></div><div><dt>Storage</dt><dd>{selectedPlan.durable ? "durable" : "development memory"}</dd></div></dl>
              <ol className="workflow-step-preview">{selectedPlan.steps.map((step) => <li key={step.step_id}><CheckCircle2 size={17} /><div><strong>{step.step_id}</strong><small>{readableKind(step.kind)} | {step.state}</small></div></li>)}</ol>

              <div aria-labelledby="workflow-lease-status-title">
                <div className="workflow-section-heading">
                  <div><p className="eyebrow">READ-ONLY COORDINATION</p><h3 id="workflow-lease-status-title">Orchestration lease</h3></div>
                  <span>No human controls</span>
                </div>
                {leaseQuery.isLoading && (
                  <div className="workspace-message" role="status">
                    <RefreshCw className="spin" size={17} />
                    <span>Loading authoritative lease status...</span>
                  </div>
                )}
                {leaseQuery.isError && (
                  <div className="workspace-message error-state" role="alert">
                    <div>
                      <strong>
                        {leaseErrorStatus === 401
                          ? "Your session has expired"
                          : leaseErrorStatus === 403
                            ? "Lease status permission is missing"
                            : "Lease status is unavailable"}
                      </strong>
                      <p>
                        {leaseErrorStatus === 401
                          ? "Sign in again to continue."
                          : leaseErrorStatus === 403
                            ? "Your current role cannot inspect orchestration lease status."
                            : "No lease state is inferred. Retry the read-only request."}
                      </p>
                    </div>
                    {leaseErrorStatus !== 401 && leaseErrorStatus !== 403 && (
                      <button type="button" onClick={() => void leaseQuery.refetch()}>
                        <RefreshCw size={15} /> Retry
                      </button>
                    )}
                  </div>
                )}
                {leaseQuery.isSuccess && leaseQuery.data.lease === null && (
                  <div className="workflow-empty-state">
                    <LockKeyhole size={19} /> No orchestration lease is recorded for this plan.
                  </div>
                )}
                {leaseQuery.isSuccess && leaseQuery.data.lease !== null && (
                  <>
                    <dl>
                      <div><dt>Status</dt><dd><span className="state-badge neutral">{leaseQuery.data.lease.effective_state}</span></dd></div>
                      <div><dt>Holder identifier</dt><dd><code title={leaseQuery.data.lease.worker_subject_id}>{safeHolderIdentifier(leaseQuery.data.lease.worker_subject_id)}</code></dd></div>
                      <div><dt>Fencing token</dt><dd>{leaseQuery.data.lease.fencing_token}</dd></div>
                      <div><dt>Plan digest binding</dt><dd><code title={leaseQuery.data.lease.plan_digest}>{shortDigest(leaseQuery.data.lease.plan_digest)}</code></dd></div>
                      <div><dt>Acquired</dt><dd>{formatTimestamp(leaseQuery.data.lease.acquired_at)}</dd></div>
                      <div><dt>Last heartbeat</dt><dd>{formatTimestamp(leaseQuery.data.lease.last_heartbeat_at)}</dd></div>
                      <div><dt>Expires</dt><dd>{formatTimestamp(leaseQuery.data.lease.expires_at)}</dd></div>
                      <div><dt>Observed</dt><dd>{formatTimestamp(leaseQuery.data.server_time)}</dd></div>
                    </dl>
                    <div className="workflow-safety-boundary" role="note">
                      <LockKeyhole size={18} />
                      <span>This lease coordinates ownership only. It grants no execution authority and did not run any plan step.</span>
                    </div>
                  </>
                )}
              </div>

              <div aria-labelledby="workflow-materialized-run-title">
                <div className="workflow-section-heading">
                  <div>
                    <p className="eyebrow">READ-ONLY RUN EVIDENCE</p>
                    <h3 id="workflow-materialized-run-title">Materialized run record</h3>
                  </div>
                  <span>No human controls</span>
                </div>
                {materializedRunQuery.isLoading && (
                  <div className="workspace-message" role="status">
                    <RefreshCw className="spin" size={17} />
                    <span>Loading authoritative run record...</span>
                  </div>
                )}
                {materializedRunQuery.isError && (
                  <div className="workspace-message error-state" role="alert">
                    <div>
                      <strong>
                        {materializedRunErrorStatus === 401
                          ? "Your session has expired"
                          : materializedRunErrorStatus === 403
                            ? "Run record permission is missing"
                            : "Run record is unavailable"}
                      </strong>
                      <p>
                        {materializedRunErrorStatus === 401
                          ? "Sign in again to continue."
                          : materializedRunErrorStatus === 403
                            ? "Your current role cannot inspect materialized run records."
                            : "No run state is inferred. Retry the read-only request."}
                      </p>
                    </div>
                    {materializedRunErrorStatus !== 401 && materializedRunErrorStatus !== 403 && (
                      <button type="button" onClick={() => void materializedRunQuery.refetch()}>
                        <RefreshCw size={15} /> Retry run record
                      </button>
                    )}
                  </div>
                )}
                {materializedRunQuery.isSuccess && materializedRunQuery.data.run === null && (
                  <div className="workflow-empty-state">
                    <Database size={19} /> No materialized run is recorded for this plan.
                  </div>
                )}
                {materializedRunQuery.isSuccess && materializedRunQuery.data.run !== null && (
                  <>
                    <dl>
                      <div><dt>Status</dt><dd><span className="state-badge neutral">{materializedRunQuery.data.run.state}</span></dd></div>
                      <div><dt>Run identifier</dt><dd><code title={materializedRunQuery.data.run.run_id}>{safeHolderIdentifier(materializedRunQuery.data.run.run_id)}</code></dd></div>
                      <div><dt>Materialized by</dt><dd><code title={materializedRunQuery.data.run.materialized_by_subject_id}>{safeHolderIdentifier(materializedRunQuery.data.run.materialized_by_subject_id)}</code></dd></div>
                      <div><dt>Created</dt><dd>{formatTimestamp(materializedRunQuery.data.run.created_at)}</dd></div>
                      <div><dt>Lease identifier</dt><dd><code title={materializedRunQuery.data.run.lease_id}>{safeHolderIdentifier(materializedRunQuery.data.run.lease_id)}</code></dd></div>
                      <div><dt>Fencing token</dt><dd>{materializedRunQuery.data.run.fencing_token}</dd></div>
                      <div><dt>Plan digest</dt><dd><code title={materializedRunQuery.data.run.plan_digest}>{shortDigest(materializedRunQuery.data.run.plan_digest)}</code></dd></div>
                      <div><dt>Definition digest</dt><dd><code title={materializedRunQuery.data.run.definition_digest}>{shortDigest(materializedRunQuery.data.run.definition_digest)}</code></dd></div>
                      <div><dt>Lease digest</dt><dd><code title={materializedRunQuery.data.run.lease_digest}>{shortDigest(materializedRunQuery.data.run.lease_digest)}</code></dd></div>
                      <div><dt>Run digest</dt><dd><code title={materializedRunQuery.data.run.canonical_digest}>{shortDigest(materializedRunQuery.data.run.canonical_digest)}</code></dd></div>
                      <div><dt>Observed</dt><dd>{formatTimestamp(materializedRunQuery.data.server_time)}</dd></div>
                    </dl>
                    <ol className="workflow-step-preview" aria-label="Materialized step records">
                      {materializedRunQuery.data.run.step_runs.map((step) => (
                        <li key={step.step_run_id}>
                          <span>{step.ordinal}</span>
                          <div>
                            <strong>{step.step_id}</strong>
                            <small>
                              {readableKind(step.kind)} | {step.capability_class} | {step.state} | {step.timeout_seconds}s
                              {step.depends_on.length > 0
                                ? ` | depends on ${step.depends_on.join(", ")}`
                                : " | no dependencies"}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                    <div className="workflow-safety-boundary" role="note">
                      <LockKeyhole size={18} />
                      <span>This durable record only freezes run and step identities. Every step remains not_started, and no execution authority is granted.</span>
                    </div>
                  </>
                )}
              </div>

              {materializedRun && (
                <div aria-labelledby="workflow-attempt-records-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY ATTEMPT EVIDENCE</p>
                      <h3 id="workflow-attempt-records-title">Materialized attempt records</h3>
                    </div>
                    <span>No human controls</span>
                  </div>
                  {attemptQuery.isLoading && (
                    <div className="workspace-message" role="status">
                      <RefreshCw className="spin" size={17} />
                      <span>Loading authoritative attempt records...</span>
                    </div>
                  )}
                  {attemptQuery.isError && (
                    <div className="workspace-message error-state" role="alert">
                      <div>
                        <strong>
                          {attemptErrorStatus === 401
                            ? "Your session has expired"
                            : attemptErrorStatus === 403
                              ? "Attempt evidence permission is missing"
                              : "Attempt evidence is unavailable"}
                        </strong>
                        <p>
                          {attemptErrorStatus === 401
                            ? "Sign in again to continue."
                            : attemptErrorStatus === 403
                              ? "Your current role cannot inspect materialized attempt records."
                              : "No attempt state is inferred. Retry the read-only request."}
                        </p>
                      </div>
                      {attemptErrorStatus !== 401 && attemptErrorStatus !== 403 && (
                        <button type="button" onClick={() => void attemptQuery.refetch()}>
                          <RefreshCw size={15} /> Retry attempt evidence
                        </button>
                      )}
                    </div>
                  )}
                  {attemptQuery.isSuccess && attemptQuery.data.attempts.length === 0 && (
                    <div className="workflow-empty-state">
                      <FileClock size={19} /> No materialized attempts are recorded for this run.
                    </div>
                  )}
                  {attemptQuery.isSuccess && attemptQuery.data.attempts.length > 0 && (
                    <>
                      <ol className="workflow-step-preview" aria-label="Materialized attempt records">
                        {attemptQuery.data.attempts.map((attempt) => (
                          <li key={attempt.attempt_id}>
                            <span>{attempt.attempt_number}</span>
                            <div>
                              <strong>
                                <code title={attempt.attempt_id}>
                                  {safeHolderIdentifier(attempt.attempt_id)}
                                </code>
                              </strong>
                              <small>
                                root step {attempt.step_id} | {attempt.state} | created {formatTimestamp(attempt.created_at)}
                              </small>
                              <small>
                                lease {safeHolderIdentifier(attempt.lease_id)} | fence {attempt.fencing_token}
                              </small>
                              <small>
                                run {shortDigest(attempt.run_digest)} | step {shortDigest(attempt.step_run_digest)} | plan {shortDigest(attempt.plan_digest)}
                              </small>
                              <small>
                                definition {shortDigest(attempt.definition_digest)} | lease {shortDigest(attempt.lease_digest)} | attempt {shortDigest(attempt.canonical_digest)}
                              </small>
                            </div>
                          </li>
                        ))}
                      </ol>
                      <dl>
                        <div><dt>Run identifier</dt><dd><code title={attemptQuery.data.run_id}>{safeHolderIdentifier(attemptQuery.data.run_id)}</code></dd></div>
                        <div><dt>Observed</dt><dd>{formatTimestamp(attemptQuery.data.server_time)}</dd></div>
                        <div><dt>Storage</dt><dd>{attemptQuery.data.durable ? "durable" : "development memory"}</dd></div>
                      </dl>
                    </>
                  )}
                  {attemptQuery.isSuccess && (
                    <div className="workflow-safety-boundary" role="note">
                      <LockKeyhole size={18} />
                      <span>These records preserve pre-dispatch attempt identity only. No action ran, and no execution authority is granted.</span>
                    </div>
                  )}
                </div>
              )}

              {attemptQuery.isSuccess && attemptQuery.data.attempts.length > 0 && (
                <div aria-labelledby="workflow-dispatch-intent-records-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY DISPATCH EVIDENCE</p>
                      <h3 id="workflow-dispatch-intent-records-title">Staged dispatch-intent records</h3>
                    </div>
                    <span>No human controls</span>
                  </div>
                  {dispatchIntentQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <FileClock size={19} />
                      <span>Loading authoritative dispatch-intent records...</span>
                    </div>
                  )}
                  {dispatchIntentQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {dispatchIntentErrorStatus === 401
                            ? "Your session has expired"
                            : dispatchIntentErrorStatus === 403
                              ? "Dispatch-intent evidence permission is missing"
                              : "Dispatch-intent evidence is unavailable"}
                        </strong>
                        <span>
                          {dispatchIntentErrorStatus === 401
                            ? "Sign in again to continue."
                            : dispatchIntentErrorStatus === 403
                              ? "Your current role cannot inspect staged dispatch-intent records."
                              : "No dispatch state is inferred. Retry the read-only request."}
                        </span>
                      </div>
                      {dispatchIntentErrorStatus !== 401 && dispatchIntentErrorStatus !== 403 && (
                        <button type="button" onClick={() => void dispatchIntentQuery.refetch()}>
                          <RefreshCw size={15} /> Retry intent evidence
                        </button>
                      )}
                    </div>
                  )}
                  {dispatchIntentQuery.isSuccess && dispatchIntents.length === 0 && (
                    <div className="workflow-empty-state">
                      <FileClock size={19} /> No dispatch intents are staged for these attempts.
                    </div>
                  )}
                  {dispatchIntentQuery.isSuccess && dispatchIntents.length > 0 && (
                    <>
                      <ol className="workflow-step-preview" aria-label="Staged dispatch-intent records">
                        {dispatchIntents.map((intent) => (
                          <li key={intent.dispatch_intent_id}>
                            <span>{intent.attempt_number}</span>
                            <div>
                              <strong>
                                <code title={intent.dispatch_intent_id}>
                                  {safeHolderIdentifier(intent.dispatch_intent_id)}
                                </code>
                              </strong>
                              <small>
                                step {intent.step_id} | {intent.state} | staged {formatTimestamp(intent.staged_at)}
                              </small>
                              <small>
                                worker {safeHolderIdentifier(intent.worker_subject_id)} | fence {intent.fencing_token}
                              </small>
                              <small>
                                attempt {shortDigest(intent.attempt_digest)} | run {shortDigest(intent.run_digest)} | step {shortDigest(intent.step_run_digest)}
                              </small>
                              <small>
                                plan {shortDigest(intent.plan_digest)} | lease {shortDigest(intent.lease_digest)} | intent {shortDigest(intent.canonical_digest)}
                              </small>
                            </div>
                          </li>
                        ))}
                      </ol>
                      <dl>
                        <div><dt>Attempts inspected</dt><dd>{dispatchIntentQuery.data.length}</dd></div>
                        <div><dt>Observed</dt><dd>{formatTimestamp(dispatchIntentQuery.data[0]!.server_time)}</dd></div>
                        <div><dt>Storage</dt><dd>{dispatchIntentQuery.data.every((item) => item.durable) ? "durable" : "development memory"}</dd></div>
                      </dl>
                    </>
                  )}
                  {dispatchIntentQuery.isSuccess && (
                    <div className="workflow-safety-boundary" role="note">
                      <LockKeyhole size={18} />
                      <span>No message was published, no worker or action ran, and no dispatch or execution authority is granted.</span>
                    </div>
                  )}
                </div>
              )}

              {dispatchIntentQuery.isSuccess && dispatchIntents.length > 0 && (
                <div aria-labelledby="workflow-dispatch-outbox-records-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY DURABLE EVIDENCE</p>
                      <h3 id="workflow-dispatch-outbox-records-title">Pending publication outbox records</h3>
                    </div>
                    <span>Database evidence only</span>
                  </div>
                  {dispatchOutboxQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <Database size={19} />
                      <span>Loading authoritative outbox records...</span>
                    </div>
                  )}
                  {dispatchOutboxQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {dispatchOutboxErrorStatus === 401
                            ? "Your session has expired"
                            : dispatchOutboxErrorStatus === 403
                              ? "Outbox evidence permission is missing"
                              : "Outbox evidence is unavailable"}
                        </strong>
                        <span>
                          {dispatchOutboxErrorStatus === 401
                            ? "Sign in again to continue."
                            : dispatchOutboxErrorStatus === 403
                              ? "Your current role cannot inspect pending publication evidence."
                              : "No publication state is inferred from this failed read."}
                        </span>
                      </div>
                    </div>
                  )}
                  {dispatchOutboxQuery.isSuccess && dispatchOutboxEntries.length > 0 && (
                    <ol className="workflow-step-preview" aria-label="Pending publication outbox records">
                      {dispatchOutboxEntries.map((entry) => (
                        <li key={entry.outbox_entry_id}>
                          <Database size={17} />
                          <div>
                            <strong>
                              <code title={entry.outbox_entry_id}>
                                {safeHolderIdentifier(entry.outbox_entry_id)}
                              </code>
                            </strong>
                            <small>
                              step {entry.step_id} | {readableKind(entry.state)} | admitted {formatTimestamp(entry.admitted_at)}
                            </small>
                            <small>
                              worker {safeHolderIdentifier(entry.worker_subject_id)} | fence {entry.fencing_token}
                            </small>
                            <small>
                              intent {shortDigest(entry.dispatch_intent_digest)} | attempt {shortDigest(entry.attempt_digest)} | run {shortDigest(entry.run_digest)}
                            </small>
                            <small>
                              step {shortDigest(entry.step_run_digest)} | plan {shortDigest(entry.plan_digest)} | lease {shortDigest(entry.lease_digest)} | outbox {shortDigest(entry.canonical_digest)}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>Pending publication is durable database evidence only. No broker is selected and no broker address, topic, or routing key is recorded. No publication, delivery, dispatch, or execution occurred or is authorized.</span>
                  </div>
                </div>
              )}

              {dispatchOutboxQuery.isSuccess && dispatchOutboxEntries.length > 0 && (
                <div aria-labelledby="workflow-publication-lease-evidence-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY LEASE EVIDENCE</p>
                      <h3 id="workflow-publication-lease-evidence-title">Publication lease evidence</h3>
                    </div>
                    <span>Current record only</span>
                  </div>
                  {publicationLeaseQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <FileClock size={19} />
                      <span>Loading authoritative publication lease evidence...</span>
                    </div>
                  )}
                  {publicationLeaseQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {publicationLeaseErrorStatus === 401
                            ? "Your session has expired"
                            : publicationLeaseErrorStatus === 403
                              ? "Publication lease evidence permission is missing"
                              : "Publication lease evidence is unavailable"}
                        </strong>
                        <span>
                          {publicationLeaseErrorStatus === 401
                            ? "Sign in again to continue."
                            : publicationLeaseErrorStatus === 403
                              ? "Your current role cannot inspect publication lease evidence."
                              : "No lease or publication state is inferred from this failed read."}
                        </span>
                      </div>
                    </div>
                  )}
                  {publicationLeaseQuery.isSuccess && publicationLeases.length > 0 && (
                    <ol
                      className="workflow-step-preview workflow-publication-lease-list"
                      aria-label="Publication lease evidence"
                    >
                      {publicationLeases.map((lease) => (
                        <li key={lease.publication_lease_id}>
                          <FileClock size={17} />
                          <div>
                            <strong>
                              <code title={lease.publication_lease_id}>
                                {safeHolderIdentifier(lease.publication_lease_id)}
                              </code>
                              <span className={`state-badge ${lease.effective_state}`}>
                                {lease.effective_state}
                              </span>
                            </strong>
                            <small>
                              publisher <code title={lease.publisher_subject_id}>{safeHolderIdentifier(lease.publisher_subject_id)}</code> | publication fence {lease.publication_fencing_token} | orchestration fence {lease.orchestration_fencing_token}
                            </small>
                            <small>
                              acquired {formatTimestamp(lease.acquired_at)} | heartbeat {formatTimestamp(lease.last_heartbeat_at)} | expires {formatTimestamp(lease.expires_at)}
                            </small>
                            <small>
                              outbox {shortDigest(lease.outbox_entry_digest)} | intent {shortDigest(lease.dispatch_intent_digest)} | attempt {shortDigest(lease.attempt_digest)}
                            </small>
                            <small>
                              run {shortDigest(lease.run_digest)} | step {shortDigest(lease.step_run_digest)} | plan {shortDigest(lease.plan_digest)} | lease {shortDigest(lease.canonical_digest)}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  {publicationLeaseQuery.isSuccess && publicationLeases.length === 0 && (
                    <div className="workflow-empty-state" role="status">
                      <FileClock size={19} />
                      <span>No publication lease has been acquired.</span>
                    </div>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>This lease is read-only coordination evidence. It grants no publication, delivery, dispatch, or execution authority.</span>
                  </div>
                </div>
              )}

              {dispatchOutboxQuery.isSuccess && dispatchOutboxEntries.length > 0 && (
                <div aria-labelledby="workflow-event-envelope-evidence-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY CANONICAL EVIDENCE</p>
                      <h3 id="workflow-event-envelope-evidence-title">
                        Canonical event-envelope evidence
                      </h3>
                    </div>
                    <span>Prepared data only</span>
                  </div>
                  {eventEnvelopeQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>Loading authoritative event-envelope evidence...</span>
                    </div>
                  )}
                  {eventEnvelopeQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {eventEnvelopeErrorStatus === 401
                            ? "Your session has expired"
                            : eventEnvelopeErrorStatus === 403
                              ? "Event-envelope evidence permission is missing"
                              : "Event-envelope evidence is unavailable"}
                        </strong>
                        <span>
                          {eventEnvelopeErrorStatus === 401
                            ? "Sign in again to continue."
                            : eventEnvelopeErrorStatus === 403
                              ? "Your current role or scope cannot inspect canonical event-envelope evidence."
                              : "No preparation, publication, delivery, dispatch, or execution state is inferred from this failed read."}
                        </span>
                      </div>
                    </div>
                  )}
                  {eventEnvelopeQuery.isSuccess && eventEnvelopes.length > 0 && (
                    <ol
                      className="workflow-step-preview workflow-event-envelope-list"
                      aria-label="Canonical event-envelope evidence"
                    >
                      {eventEnvelopes.map((envelope) => (
                        <li key={envelope.event_id}>
                          <FileJson2 size={17} />
                          <div>
                            <strong>
                              <code title={envelope.event_id}>
                                {safeHolderIdentifier(envelope.event_id)}
                              </code>
                              <span className="state-badge neutral">{envelope.state}</span>
                            </strong>
                            <small>
                              {envelope.event_type} v{envelope.event_version} | producer{" "}
                              <code title={envelope.producer}>{safeHolderIdentifier(envelope.producer)}</code>{" "}
                              v{envelope.producer_version}
                            </small>
                            <small>
                              occurred {formatTimestamp(envelope.occurred_at)} | recorded{" "}
                              {formatTimestamp(envelope.recorded_at)} | prepared{" "}
                              {formatTimestamp(envelope.prepared_at)}
                            </small>
                            <small>
                              subject {readableKind(envelope.subject_type)}:{" "}
                              <code title={envelope.subject_id}>{safeHolderIdentifier(envelope.subject_id)}</code>{" "}
                              | workflow <code title={envelope.workflow_id}>{safeHolderIdentifier(envelope.workflow_id)}</code>
                            </small>
                            <small>
                              organization {envelope.organization_id} | environment {envelope.environment_id} | site{" "}
                              {envelope.payload.scope.site_id} | target {envelope.payload.target_id}
                            </small>
                            <small>
                              correlation <code title={envelope.correlation_id}>{safeHolderIdentifier(envelope.correlation_id)}</code>{" "}
                              | causation <code title={envelope.causation_id}>{safeHolderIdentifier(envelope.causation_id)}</code>
                            </small>
                            <small>
                              classification {envelope.data_classification} | schema{" "}
                              <code title={envelope.schema_uri}>{envelope.schema_uri}</code>
                            </small>
                            <small>
                              publisher <code title={envelope.publisher_subject_id}>{safeHolderIdentifier(envelope.publisher_subject_id)}</code>{" "}
                              | publication fence {envelope.publication_fencing_token} | source fence{" "}
                              {envelope.orchestration_fencing_token}
                            </small>
                            <small>
                              publication lease {shortDigest(envelope.publication_lease_digest)} | source lease{" "}
                              {shortDigest(envelope.orchestration_lease_digest)} | outbox{" "}
                              {shortDigest(envelope.payload.outbox_entry_digest)}
                            </small>
                            <small>
                              intent {shortDigest(envelope.payload.dispatch_intent_digest)} | attempt{" "}
                              {shortDigest(envelope.payload.attempt_digest)} | run{" "}
                              {shortDigest(envelope.payload.run_digest)} | step{" "}
                              {shortDigest(envelope.payload.step_run_digest)} | plan{" "}
                              {shortDigest(envelope.payload.plan_digest)}
                            </small>
                            <small>
                              payload/outbox {shortDigest(envelope.payload.outbox_entry_digest)} | envelope{" "}
                              {shortDigest(envelope.canonical_digest)}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  {eventEnvelopeQuery.isSuccess && eventEnvelopes.length === 0 && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>No event envelope has been prepared.</span>
                    </div>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>
                      Prepared canonical data only. No transport is selected, no bytes were
                      serialized, no message was published or delivered, no worker was dispatched,
                      and no action was executed.
                    </span>
                  </div>
                </div>
              )}

              {eventEnvelopeQuery.isSuccess && eventEnvelopes.length > 0 && (
                <div aria-labelledby="workflow-transport-admission-evidence-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY POLICY EVIDENCE</p>
                      <h3 id="workflow-transport-admission-evidence-title">
                        Transport-admission evidence
                      </h3>
                    </div>
                    <span>Eligibility only</span>
                  </div>
                  {transportAdmissionQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>Loading authoritative transport-admission evidence...</span>
                    </div>
                  )}
                  {transportAdmissionQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {transportAdmissionErrorStatus === 401
                            ? "Your session has expired"
                            : transportAdmissionErrorStatus === 403
                              ? "Transport-admission evidence permission is missing"
                              : "Transport-admission evidence is unavailable"}
                        </strong>
                        <span>
                          {transportAdmissionErrorStatus === 401
                            ? "Sign in again to continue."
                            : transportAdmissionErrorStatus === 403
                              ? "Your current role or scope cannot inspect transport-admission evidence."
                              : "No admission, serialization, publication, delivery, dispatch, or execution state is inferred from this failed read."}
                        </span>
                      </div>
                      <button
                        className="secondary-action"
                        type="button"
                        aria-label="Retry transport-admission read"
                        onClick={() => void transportAdmissionQuery.refetch()}
                      >
                        <RefreshCw size={16} />
                        Retry
                      </button>
                    </div>
                  )}
                  {transportAdmissionQuery.isSuccess && transportAdmissions.length > 0 && (
                    <ol
                      className="workflow-step-preview workflow-transport-admission-list"
                      aria-label="Transport-admission evidence"
                    >
                      {transportAdmissions.map((admission) => (
                        <li key={admission.transport_admission_id}>
                          <FileJson2 size={17} />
                          <div>
                            <strong>
                              <code title={admission.transport_admission_id}>
                                {safeHolderIdentifier(admission.transport_admission_id)}
                              </code>
                              <span className="state-badge neutral">{admission.state}</span>
                            </strong>
                            <small>
                              policy <code title={admission.policy.policy_id}>{safeHolderIdentifier(admission.policy.policy_id)}</code>{" "}
                              v{admission.policy.policy_version} | {admission.policy.representation_name} | {admission.policy.encoding}
                            </small>
                            <small>
                              allowed {admission.policy.allowed_event_type} v{admission.policy.allowed_event_version} | classification{" "}
                              {admission.policy.allowed_data_classification}
                            </small>
                            <small>
                              schema <code title={admission.policy.allowed_schema_uri}>{admission.policy.allowed_schema_uri}</code>
                            </small>
                            <small>
                              canonical size {admission.canonical_byte_count.toLocaleString()} bytes | policy maximum{" "}
                              {admission.policy.maximum_canonical_byte_count.toLocaleString()} bytes
                            </small>
                            <small>
                              admitted {formatTimestamp(admission.admitted_at)} | organization {admission.scope.organization_id} | environment{" "}
                              {admission.scope.environment_id} | site {admission.scope.site_id} | target {admission.target_id}
                            </small>
                            <small>
                              publisher <code title={admission.publisher_subject_id}>{safeHolderIdentifier(admission.publisher_subject_id)}</code>{" "}
                              | publication fence {admission.publication_fencing_token} | source fence{" "}
                              {admission.orchestration_fencing_token}
                            </small>
                            <small>
                              policy {shortDigest(admission.policy.policy_digest)} | event {shortDigest(admission.event_digest)} | admission{" "}
                              {shortDigest(admission.canonical_digest)}
                            </small>
                            <small>
                              publication lease {shortDigest(admission.publication_lease_digest)} | source lease{" "}
                              {shortDigest(admission.orchestration_lease_digest)} | outbox {shortDigest(admission.outbox_entry_digest)}
                            </small>
                            <small>
                              intent {shortDigest(admission.dispatch_intent_digest)} | attempt {shortDigest(admission.attempt_digest)} | run{" "}
                              {shortDigest(admission.run_digest)} | step {shortDigest(admission.step_run_digest)} | plan{" "}
                              {shortDigest(admission.plan_digest)}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  {transportAdmissionQuery.isSuccess && transportAdmissions.length === 0 && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>No transport-admission decision has been recorded.</span>
                    </div>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>
                      Admission proves policy eligibility only. No broker, provider, or route was
                      selected; no wire bytes or message were created; nothing was serialized,
                      published, delivered, dispatched, or executed.
                    </span>
                  </div>
                </div>
              )}

              {transportAdmissionQuery.isSuccess && transportAdmissions.length > 0 && (
                <div aria-labelledby="workflow-byte-artifact-evidence-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY INTEGRITY EVIDENCE</p>
                      <h3 id="workflow-byte-artifact-evidence-title">
                        Byte-artifact metadata
                      </h3>
                    </div>
                    <span>Server-side bytes only</span>
                  </div>
                  {byteArtifactQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>Loading authoritative byte-artifact metadata...</span>
                    </div>
                  )}
                  {byteArtifactQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {byteArtifactErrorStatus === 401
                            ? "Your session has expired"
                            : byteArtifactErrorStatus === 403
                              ? "Byte-artifact metadata permission is missing"
                              : "Byte-artifact metadata is unavailable"}
                        </strong>
                        <span>
                          {byteArtifactErrorStatus === 401
                            ? "Sign in again to continue."
                            : byteArtifactErrorStatus === 403
                              ? "Your current role or scope cannot inspect byte-artifact metadata."
                              : "No materialization, publication, delivery, dispatch, or execution state is inferred from this failed read."}
                        </span>
                      </div>
                      <button
                        className="secondary-action"
                        type="button"
                        aria-label="Retry byte-artifact metadata read"
                        onClick={() => void byteArtifactQuery.refetch()}
                      >
                        <RefreshCw size={16} />
                        Retry
                      </button>
                    </div>
                  )}
                  {byteArtifactQuery.isSuccess && byteArtifacts.length > 0 && (
                    <ol
                      className="workflow-step-preview workflow-byte-artifact-list"
                      aria-label="Byte-artifact metadata"
                    >
                      {byteArtifacts.map((artifact) => (
                        <li key={artifact.byte_artifact_id}>
                          <FileJson2 size={17} />
                          <div>
                            <strong>
                              <code title={artifact.byte_artifact_id}>
                                {safeHolderIdentifier(artifact.byte_artifact_id)}
                              </code>
                              <span className="state-badge neutral">{artifact.state}</span>
                            </strong>
                            <small>
                              {artifact.representation_name} | {artifact.encoding.toUpperCase()} | {artifact.media_type}
                            </small>
                            <small>
                              {artifact.byte_count.toLocaleString()} bytes | SHA-256{" "}
                              <code title={artifact.content_sha256}>
                                {shortDigest(artifact.content_sha256)}
                              </code>
                            </small>
                            <small>
                              materialized {formatTimestamp(artifact.materialized_at)} | organization{" "}
                              {artifact.scope.organization_id} | environment {artifact.scope.environment_id} | site{" "}
                              {artifact.scope.site_id} | target {artifact.target_id}
                            </small>
                            <small>
                              publisher <code title={artifact.publisher_subject_id}>{safeHolderIdentifier(artifact.publisher_subject_id)}</code>{" "}
                              | publication fence {artifact.publication_fencing_token} | source fence{" "}
                              {artifact.orchestration_fencing_token}
                            </small>
                            <small>
                              policy <code title={artifact.policy_id}>{safeHolderIdentifier(artifact.policy_id)}</code>{" "}
                              v{artifact.policy_version} | digest {shortDigest(artifact.policy_digest)}
                            </small>
                            <small>
                              admission <code title={artifact.transport_admission_id}>{safeHolderIdentifier(artifact.transport_admission_id)}</code>{" "}
                              | digest {shortDigest(artifact.transport_admission_digest)}
                            </small>
                            <small>
                              event <code title={artifact.event_id}>{safeHolderIdentifier(artifact.event_id)}</code>{" "}
                              | digest {shortDigest(artifact.event_digest)} | outbox{" "}
                              <code title={artifact.outbox_entry_id}>{safeHolderIdentifier(artifact.outbox_entry_id)}</code>{" "}
                              | digest {shortDigest(artifact.outbox_entry_digest)}
                            </small>
                            <small>
                              intent {shortDigest(artifact.dispatch_intent_digest)} | attempt{" "}
                              {shortDigest(artifact.attempt_digest)} | run {shortDigest(artifact.run_digest)} | step{" "}
                              {shortDigest(artifact.step_run_digest)} | plan {shortDigest(artifact.plan_digest)}
                            </small>
                            <small>
                              publication lease <code title={artifact.publication_lease_id}>{safeHolderIdentifier(artifact.publication_lease_id)}</code>{" "}
                              | {shortDigest(artifact.publication_lease_digest)} | source lease{" "}
                              <code title={artifact.orchestration_lease_id}>{safeHolderIdentifier(artifact.orchestration_lease_id)}</code>{" "}
                              | {shortDigest(artifact.orchestration_lease_digest)}
                            </small>
                            <small>metadata digest {shortDigest(artifact.canonical_digest)}</small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  {byteArtifactQuery.isSuccess && byteArtifacts.length === 0 && (
                    <div className="workflow-empty-state" role="status">
                      <FileJson2 size={19} />
                      <span>No byte artifact has been materialized.</span>
                    </div>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>
                      Materialized means deterministic bytes exist in Atlas storage only. Raw bytes
                      and payload content are not exposed. No provider, route, credential, message,
                      publication, delivery, worker dispatch, or execution authority is present.
                    </span>
                  </div>
                </div>
              )}

              {byteArtifactQuery.isSuccess && byteArtifacts.length > 0 && (
                <div aria-labelledby="workflow-logical-channel-binding-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY LOGICAL ROUTING EVIDENCE</p>
                      <h3 id="workflow-logical-channel-binding-title">
                        Logical channel binding
                      </h3>
                    </div>
                    <span>Provider-neutral contract</span>
                  </div>
                  {logicalChannelBindingQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <Link2 size={19} />
                      <span>Loading authoritative logical channel binding...</span>
                    </div>
                  )}
                  {logicalChannelBindingQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {logicalChannelBindingErrorStatus === 401
                            ? "Your session has expired"
                            : logicalChannelBindingErrorStatus === 403
                              ? "Logical channel binding permission is missing"
                              : "Logical channel binding is unavailable"}
                        </strong>
                        <span>
                          {logicalChannelBindingErrorStatus === 401
                            ? "Sign in again to continue."
                            : logicalChannelBindingErrorStatus === 403
                              ? "Your current role or scope cannot inspect logical channel binding metadata."
                              : "No binding, publication, delivery, dispatch, or execution state is inferred from this failed read."}
                        </span>
                      </div>
                      <button
                        className="secondary-action"
                        type="button"
                        aria-label="Retry logical channel binding read"
                        onClick={() => void logicalChannelBindingQuery.refetch()}
                      >
                        <RefreshCw size={16} />
                        Retry
                      </button>
                    </div>
                  )}
                  {logicalChannelBindingQuery.isSuccess && logicalChannelBindings.length > 0 && (
                    <ol
                      className="workflow-step-preview workflow-logical-channel-binding-list"
                      aria-label="Logical channel binding"
                    >
                      {logicalChannelBindings.map((binding) => (
                        <li key={binding.logical_channel_binding_id}>
                          <Link2 size={17} />
                          <div>
                            <strong>
                              <code title={binding.logical_channel_binding_id}>
                                {safeHolderIdentifier(binding.logical_channel_binding_id)}
                              </code>
                              <span className="state-badge neutral">{binding.state}</span>
                            </strong>
                            <small>
                              channel <code title={binding.logical_channel_id}>{binding.logical_channel_id}</code>{" "}
                              v{binding.logical_channel_version}
                            </small>
                            <small>
                              {binding.delivery_semantics} | durable required | {binding.ordering_key_kind} ordering | retention{" "}
                              {binding.retention_class}
                            </small>
                            <small>
                              ordering key <code title={binding.ordering_key_value}>{safeHolderIdentifier(binding.ordering_key_value)}</code>
                            </small>
                            <small>
                              bound {formatTimestamp(binding.bound_at)} | organization {binding.scope.organization_id} | environment{" "}
                              {binding.scope.environment_id} | site {binding.scope.site_id} | target {binding.target_id}
                            </small>
                            <small>
                              publisher <code title={binding.publisher_subject_id}>{safeHolderIdentifier(binding.publisher_subject_id)}</code>{" "}
                              | publication fence {binding.publication_fencing_token} | source fence{" "}
                              {binding.orchestration_fencing_token}
                            </small>
                            <small>
                              policy <code title={binding.policy_id}>{safeHolderIdentifier(binding.policy_id)}</code>{" "}
                              v{binding.policy_version} | digest {shortDigest(binding.policy_digest)}
                            </small>
                            <small>
                              artifact <code title={binding.byte_artifact_id}>{safeHolderIdentifier(binding.byte_artifact_id)}</code>{" "}
                              | digest {shortDigest(binding.byte_artifact_digest)} | SHA-256{" "}
                              <code title={binding.content_sha256}>{shortDigest(binding.content_sha256)}</code> |{" "}
                              {binding.byte_count.toLocaleString()} bytes
                            </small>
                            <small>
                              admission <code title={binding.transport_admission_id}>{safeHolderIdentifier(binding.transport_admission_id)}</code>{" "}
                              | digest {shortDigest(binding.transport_admission_digest)} | event{" "}
                              <code title={binding.event_id}>{safeHolderIdentifier(binding.event_id)}</code> | digest{" "}
                              {shortDigest(binding.event_digest)}
                            </small>
                            <small>
                              outbox <code title={binding.outbox_entry_id}>{safeHolderIdentifier(binding.outbox_entry_id)}</code>{" "}
                              | digest {shortDigest(binding.outbox_entry_digest)} | intent{" "}
                              <code title={binding.dispatch_intent_id}>{safeHolderIdentifier(binding.dispatch_intent_id)}</code> | digest{" "}
                              {shortDigest(binding.dispatch_intent_digest)}
                            </small>
                            <small>
                              attempt <code title={binding.attempt_id}>{safeHolderIdentifier(binding.attempt_id)}</code> | digest{" "}
                              {shortDigest(binding.attempt_digest)} | run{" "}
                              <code title={binding.run_id}>{safeHolderIdentifier(binding.run_id)}</code> | digest{" "}
                              {shortDigest(binding.run_digest)}
                            </small>
                            <small>
                              step <code title={binding.step_run_id}>{safeHolderIdentifier(binding.step_run_id)}</code> | digest{" "}
                              {shortDigest(binding.step_run_digest)} | plan{" "}
                              <code title={binding.plan_id}>{safeHolderIdentifier(binding.plan_id)}</code> | digest{" "}
                              {shortDigest(binding.plan_digest)}
                            </small>
                            <small>
                              publication lease <code title={binding.publication_lease_id}>{safeHolderIdentifier(binding.publication_lease_id)}</code>{" "}
                              | {shortDigest(binding.publication_lease_digest)} | source lease{" "}
                              <code title={binding.orchestration_lease_id}>{safeHolderIdentifier(binding.orchestration_lease_id)}</code>{" "}
                              | {shortDigest(binding.orchestration_lease_digest)}
                            </small>
                            <small>
                              authority publication false | delivery false | dispatch false | execution false | metadata digest{" "}
                              {shortDigest(binding.canonical_digest)}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                  {logicalChannelBindingQuery.isSuccess && logicalChannelBindings.length === 0 && (
                    <div className="workflow-empty-state" role="status">
                      <Link2 size={19} />
                      <span>No logical channel binding has been recorded.</span>
                    </div>
                  )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>
                      Bound records logical requirements in Atlas storage only. No physical
                      provider, broker, endpoint, topic, stream, queue, partition, routing key,
                      credential, message, or network publication attempt exists. Publication,
                      delivery, dispatch, and execution authority remain zero.
                    </span>
                  </div>
                </div>
              )}

              {logicalChannelBindingQuery.isSuccess && logicalChannelBindings.length > 0 && (
                <div aria-labelledby="workflow-transport-compatibility-admission-title">
                  <div className="workflow-section-heading">
                    <div>
                      <p className="eyebrow">READ-ONLY POLICY EVIDENCE</p>
                      <h3 id="workflow-transport-compatibility-admission-title">
                        Transport compatibility admission
                      </h3>
                    </div>
                    <span>Declared contracts only</span>
                  </div>
                  {transportCompatibilityAdmissionQuery.isLoading && (
                    <div className="workflow-empty-state" role="status">
                      <ShieldCheck size={19} />
                      <span>Loading transport compatibility admission...</span>
                    </div>
                  )}
                  {transportCompatibilityAdmissionQuery.isError && (
                    <div className="inline-error" role="alert">
                      <div>
                        <strong>
                          {transportCompatibilityAdmissionErrorStatus === 401
                            ? "Your session has expired"
                            : transportCompatibilityAdmissionErrorStatus === 403
                              ? "Transport compatibility admission permission is missing"
                              : "Transport compatibility admission is unavailable"}
                        </strong>
                        <span>
                          {transportCompatibilityAdmissionErrorStatus === 401
                            ? "Sign in again to continue."
                            : transportCompatibilityAdmissionErrorStatus === 403
                              ? "Your current role or scope cannot inspect compatibility evidence."
                              : "No compatibility or operational state is inferred from this failed read."}
                        </span>
                      </div>
                      {transportCompatibilityAdmissionErrorStatus !== 401 &&
                        transportCompatibilityAdmissionErrorStatus !== 403 && (
                          <button
                            className="secondary-action"
                            type="button"
                            aria-label="Retry transport compatibility admission read"
                            onClick={() =>
                              void transportCompatibilityAdmissionQuery.refetch()
                            }
                          >
                            <RefreshCw size={16} />
                            Retry
                          </button>
                        )}
                    </div>
                  )}
                  {transportCompatibilityAdmissionQuery.isSuccess &&
                    transportCompatibilityAdmissions.length > 0 && (
                      <ol
                        className="workflow-step-preview workflow-transport-compatibility-admission-list"
                        aria-label="Transport compatibility admissions"
                      >
                        {transportCompatibilityAdmissions.map((admission) => (
                          <li key={admission.compatibility_admission_id}>
                            <ShieldCheck size={17} />
                            <div>
                              <strong>
                                <code title={admission.compatibility_admission_id}>
                                  {safeHolderIdentifier(
                                    admission.compatibility_admission_id,
                                  )}
                                </code>
                                <span className="state-badge neutral">{admission.state}</span>
                              </strong>
                              <small>
                                binding{" "}
                                <code title={admission.logical_channel_binding_id}>
                                  {safeHolderIdentifier(admission.logical_channel_binding_id)}
                                </code>{" "}
                                | digest {shortDigest(admission.logical_channel_binding_digest)}
                              </small>
                              <small>
                                profile snapshot{" "}
                                <code title={admission.transport_profile_snapshot_id}>
                                  {safeHolderIdentifier(admission.transport_profile_snapshot_id)}
                                </code>{" "}
                                | digest {shortDigest(admission.transport_profile_snapshot_digest)}
                              </small>
                              <small>
                                profile <code title={admission.transport_profile_id}>{safeHolderIdentifier(admission.transport_profile_id)}</code>{" "}
                                | revision {admission.transport_profile_revision}
                              </small>
                              <small>
                                policy <code title={admission.policy_id}>{safeHolderIdentifier(admission.policy_id)}</code>{" "}
                                v{admission.policy_version} | digest{" "}
                                {shortDigest(admission.policy_digest)}
                              </small>
                              <small>
                                organization {admission.scope.organization_id} | environment{" "}
                                {admission.scope.environment_id} | site {admission.scope.site_id}
                              </small>
                              <small>
                                event {admission.event_type} v{admission.event_version} | schema{" "}
                                <code title={admission.schema_uri}>{admission.schema_uri}</code>
                              </small>
                              <small>
                                {admission.data_classification} | {admission.representation_name} |{" "}
                                {admission.encoding} | {admission.delivery_semantics} | durable required
                              </small>
                              <small>
                                ordering {admission.ordering_key_kind} | retention {admission.retention_class}
                              </small>
                              <small>
                                logical maximum {admission.logical_maximum_byte_count.toLocaleString()} bytes | artifact{" "}
                                {admission.artifact_byte_count.toLocaleString()} bytes | profile maximum{" "}
                                {admission.profile_maximum_message_byte_count.toLocaleString()} bytes
                              </small>
                              <small>
                                admitted {formatTimestamp(admission.admitted_at)} by{" "}
                                <code title={admission.admitter_subject_id}>{safeHolderIdentifier(admission.admitter_subject_id)}</code>
                              </small>
                              <small>
                                authority route selection false | route binding false | credential access false | publication false | delivery false | dispatch false | execution false
                              </small>
                              <small>metadata digest {shortDigest(admission.canonical_digest)}</small>
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                  {transportCompatibilityAdmissionQuery.isSuccess &&
                    transportCompatibilityAdmissions.length === 0 && (
                      <div className="workflow-empty-state" role="status">
                        <ShieldCheck size={19} />
                        <span>No transport compatibility admission has been recorded.</span>
                      </div>
                    )}
                  <div className="workflow-safety-boundary" role="note">
                    <LockKeyhole size={18} />
                    <span>
                      Admission proves only that the exact declared contracts match under the
                      named policy. It creates no operational state and all seven authority flags
                      remain false.
                    </span>
                  </div>
                </div>
              )}

              {selectedPlan.state === "planned" && (
                <div
                  className="workflow-plan-composer workflow-cancel-form"
                  aria-labelledby="workflow-cancel-title"
                >
                  <div className="workflow-section-heading">
                    <div><p className="eyebrow">WITHDRAW INTENT</p><h3 id="workflow-cancel-title">Cancel this plan</h3></div>
                    <span>History is preserved</span>
                  </div>
                  <label className="workflow-cancel-field">
                    Cancellation reason
                    <textarea
                      value={cancellationReason}
                      maxLength={500}
                      onChange={(event) => setCancellationReason(event.target.value)}
                      placeholder="Why this unstarted plan is being withdrawn"
                    />
                  </label>
                  <label className="workflow-cancel-acknowledgement">
                    <input
                      type="checkbox"
                      checked={cancellationAcknowledged}
                      onChange={(event) => setCancellationAcknowledged(event.target.checked)}
                    />
                    I acknowledge that cancellation preserves history and cannot undo external work.
                  </label>
                  {cancelMutation.isError && (
                    <div className="workspace-message error-state" role="alert">
                      <div>
                        <strong>
                          {cancellationSessionExpired
                            ? "Your session has expired"
                            : "Cancellation was not recorded"}
                        </strong>
                        <p>
                          {cancellationSessionExpired
                            ? "Sign in again to continue."
                            : "Reload the exact plan before trying again."}
                        </p>
                      </div>
                    </div>
                  )}
                  <button
                    className="primary-action"
                    type="button"
                    disabled={!canCancel}
                    onClick={() => cancelMutation.mutate(selectedPlan)}
                  >
                    <Ban size={16} /> {cancelMutation.isPending ? "Cancelling..." : "Confirm cancellation"}
                  </button>
                </div>
              )}

              {selectedPlan.transition_history.length > 0 && (
                <div aria-labelledby="workflow-transition-history-title">
                  <div className="workflow-section-heading">
                    <div><p className="eyebrow">IMMUTABLE HISTORY</p><h3 id="workflow-transition-history-title">State transitions</h3></div>
                    <History size={18} />
                  </div>
                  <ol className="workflow-step-preview">
                    {selectedPlan.transition_history.map((transition) => (
                      <li key={transition.transition_id}>
                        <History size={17} />
                        <div>
                          <strong>{transition.prior_state} to {transition.new_state}</strong>
                          <small>{transition.reason} | {transition.actor_subject_id} | {new Date(transition.occurred_at).toLocaleString()}</small>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              <div className="workflow-safety-boundary"><LockKeyhole size={18} /><span>No connector, approval, ITSM, runbook, worker or infrastructure action ran.</span></div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
