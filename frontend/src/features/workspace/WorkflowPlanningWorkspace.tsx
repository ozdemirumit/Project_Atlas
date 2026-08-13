import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  FileClock,
  LockKeyhole,
  Plus,
  RefreshCw,
  Workflow,
} from "lucide-react";

import { ApiRequestError } from "../../api/client";
import { listOperationalConversations } from "../../api/conversations";
import {
  createWorkflowPlan,
  listWorkflowDefinitions,
  listWorkflowPlans,
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
  const loading = targetQuery.isLoading || definitionQuery.isLoading || plansQuery.isLoading;
  const failed = targetQuery.isError || definitionQuery.isError || plansQuery.isError;
  const sessionExpired = [targetQuery.error, definitionQuery.error, plansQuery.error].some(
    (error) => error instanceof ApiRequestError && error.status === 401,
  );
  const canCreate = Boolean(
    selectedDefinition && targetId && purpose.trim() && inputSummary.trim() && !createMutation.isPending,
  );

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
                {selectedDefinition.steps.map((step) => <li key={step.step_id}><span>{step.ordinal}</span><div><strong>{step.title}</strong><small>{readableKind(step.kind)} · {step.capability_class} · not started</small></div></li>)}
              </ol>
            )}
            {authorizedTargets.length === 0 && <div className="workflow-empty-state">No authorized storage target is available in this scope.</div>}
            {createMutation.isError && <div className="workspace-message error-state" role="alert">Plan creation failed. The request did not change infrastructure.</div>}
            <button className="primary-action" type="button" disabled={!canCreate} onClick={() => selectedDefinition && createMutation.mutate(selectedDefinition)}><Plus size={16} /> Create plan</button>
          </section>

          <section className="workflow-plan-history" aria-labelledby="workflow-history-title">
            <div className="workflow-section-heading"><div><p className="eyebrow">PLAN HISTORY</p><h2 id="workflow-history-title">Planned runs</h2></div><span>{plansQuery.data?.durable ? "durable" : "development memory"}</span></div>
            {(plansQuery.data?.plans.length ?? 0) === 0 ? (
              <div className="workflow-empty-state"><FileClock size={20} /> No workflow plans in this scope.</div>
            ) : (
              <div className="workflow-plan-list">{plansQuery.data?.plans.map((plan) => <button type="button" key={plan.plan_id} onClick={() => setSelectedPlan(plan)}><CalendarClock size={18} /><span><strong>{definitions.find((item) => item.definition_id === plan.definition_id)?.title ?? plan.definition_id}</strong><small>{plan.target_id} · {new Date(plan.created_at).toLocaleString()}</small></span><span className="state-badge neutral">planned</span></button>)}</div>
            )}
          </section>

          {selectedPlan && (
            <section className="workflow-plan-detail" aria-labelledby="workflow-plan-detail-title">
              <div className="workflow-section-heading"><div><p className="eyebrow">EXACT PLAN</p><h2 id="workflow-plan-detail-title">{selectedPlan.plan_id}</h2></div><button className="icon-button" type="button" aria-label="Close plan detail" onClick={() => setSelectedPlan(null)}>×</button></div>
              <dl><div><dt>State</dt><dd>planned</dd></div><div><dt>Target</dt><dd>{selectedPlan.target_id}</dd></div><div><dt>Definition</dt><dd>{selectedPlan.definition_id} v{selectedPlan.definition_version}</dd></div><div><dt>Storage</dt><dd>{selectedPlan.durable ? "durable" : "development memory"}</dd></div></dl>
              <ol className="workflow-step-preview">{selectedPlan.steps.map((step) => <li key={step.step_id}><CheckCircle2 size={17} /><div><strong>{step.step_id}</strong><small>{readableKind(step.kind)} · {step.state}</small></div></li>)}</ol>
              <div className="workflow-safety-boundary"><LockKeyhole size={18} /><span>No connector, approval, ITSM, runbook, worker or infrastructure action ran.</span></div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
