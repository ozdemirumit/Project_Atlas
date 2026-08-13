import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Ban,
  CalendarClock,
  CheckCircle2,
  Database,
  FileClock,
  History,
  LockKeyhole,
  Plus,
  RefreshCw,
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
  listWorkflowPlans,
  listWorkflowRunAttempts,
  WORKFLOW_PLAN_SAFETY_NOTICE,
  type WorkflowDefinition,
  type WorkflowRunPlan,
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

              {selectedPlan.state === "planned" && (
                <div className="workflow-plan-composer" aria-labelledby="workflow-cancel-title">
                  <div className="workflow-section-heading">
                    <div><p className="eyebrow">WITHDRAW INTENT</p><h3 id="workflow-cancel-title">Cancel this plan</h3></div>
                    <span>History is preserved</span>
                  </div>
                  <label>
                    Cancellation reason
                    <textarea
                      value={cancellationReason}
                      maxLength={500}
                      onChange={(event) => setCancellationReason(event.target.value)}
                      placeholder="Why this unstarted plan is being withdrawn"
                    />
                  </label>
                  <label>
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
