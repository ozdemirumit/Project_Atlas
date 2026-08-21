import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpCircle,
  Boxes,
  ClipboardList,
  Download,
  FileCheck2,
  Link2,
  LogIn,
  PackagePlus,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCheck,
  UserX,
  X,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { ApiRequestError } from "../../api/client";
import {
  assessConnectorUpgradeSigningProviderConformance,
  createConnectorUpgradeApprovalRequest,
  createConnectorUpgradeChangeContextDraft,
  createConnectorUpgradeEvidenceReceipt,
  createConnectorUpgradeSignedEvidenceReceipt,
  decideConnectorUpgradeApproval,
  downloadConnectorUpgradeEvidenceReceipt,
  downloadConnectorUpgradeSignedEvidenceReceipt,
  getConnectorUpgradeApprovalRecord,
  getConnectorUpgradeEvidenceSigningKeyTrustInventory,
  getConnectorUpgradeSigningProviderOnboardingReadiness,
  getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  getLatestConnectorUpgradeSigningProviderConformance,
  getLatestConnectorUpgradeApprovalRevalidation,
  getConnectorUpgradeHandoffReadiness,
  getLatestConnectorUpgradeChangeContextDraft,
  getConnectorUpgradeReadiness,
  isConnectorUpgradeEvidenceReceipt,
  isConnectorUpgradeSignedEvidenceReceipt,
  revalidateConnectorUpgradeApproval,
  verifyConnectorUpgradeEvidenceReceipt,
  verifyConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeApprovalOutcome,
  type ConnectorUpgradeCandidate,
  type ConnectorUpgradeEvidenceReceipt,
  type ConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeSigningProviderConformanceAssessment,
  type ConnectorUpgradeSigningProviderOnboardingReadiness,
  type ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  getConnectorUpgradePlan,
  type ConnectorUpgradePlan,
} from "../../api/connectorUpgradeReadiness";
import {
  createConnectorInstance,
  getConnectorInstanceCreationPolicies,
  getConnectorInstances,
  retireConnectorInstance,
  type ConnectorInstanceRecord,
  type ConnectorInstanceCreationPolicy,
} from "../../api/connectorInstances";
import {
  getConnectorPackageInstallations,
  type ConnectorPackageInstallationReceipt,
} from "../../api/packageInstallations";
import {
  getConnectorTargetConfigurations,
  type ConnectorTargetConfigurationBinding,
} from "../../api/targetConfigurations";
import { TargetConfigurationPanel } from "./TargetConfigurationPanel";

type LifecycleFilter = "active" | "retired" | "all";

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function AddMcpDialog({
  packages,
  policies,
  pending,
  onCancel,
  onOpenBuilder,
  onSubmit,
}: {
  packages: ConnectorPackageInstallationReceipt[];
  policies: ConnectorInstanceCreationPolicy[];
  pending: boolean;
  onCancel: () => void;
  onOpenBuilder: () => void;
  onSubmit: (input: Parameters<typeof createConnectorInstance>[0]) => void;
}) {
  const [receiptId, setReceiptId] = useState(packages[0]?.receipt_id ?? "");
  const installation = packages.find((item) => item.receipt_id === receiptId) ?? packages[0];
  const policy = policies.find(
    (item) =>
      item.environment_id === installation?.environment_id &&
      item.organization_id === installation.organization_id &&
      item.allowed_sdk_profiles.includes(installation.sdk_profile),
  );
  const [instanceKey, setInstanceKey] = useState(
    installation ? `${installation.connector_id}-managed` : "",
  );
  const [displayName, setDisplayName] = useState(
    installation ? `${installation.connector_id} managed` : "",
  );
  const [purpose, setPurpose] = useState(
    "Create a disabled MCP identity for governed lifecycle management.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const policyId = policy?.policy_id ?? "";
  const policyDigest = policy?.canonical_digest ?? "";
  const valid = Boolean(
    installation &&
      /^[a-z][a-z0-9_.:-]{2,127}$/.test(instanceKey) &&
      displayName.trim().length >= 3 &&
      purpose.trim().length >= 20 &&
      /^[a-f0-9]{64}$/.test(policyDigest) &&
      acknowledged,
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || !installation) return;
    onSubmit({
      installation,
      instanceKey,
      displayName,
      policyId,
      policyDigest,
      purpose,
    });
  };

  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <form className="installed-mcp-dialog" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="add-mcp-title">
        <header>
          <div>
            <p className="eyebrow">GOVERNED INSTANCE</p>
            <h3 id="add-mcp-title">Add MCP</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close Add MCP" onClick={onCancel}><X size={17} /></button>
        </header>
        {installation ? (
          <>
            <label>
              <span>Installed package</span>
              <select
                value={installation.receipt_id}
                onChange={(event) => {
                  const next = packages.find((item) => item.receipt_id === event.target.value);
                  setReceiptId(event.target.value);
                  if (next) {
                    setInstanceKey(`${next.connector_id}-managed`);
                    setDisplayName(`${next.connector_id} managed`);
                  }
                }}
              >
                {packages.map((item) => (
                  <option value={item.receipt_id} key={item.receipt_id}>
                    {item.connector_id} {item.release_version}
                  </option>
                ))}
              </select>
            </label>
            <div className="installed-mcp-form-grid">
              <label>
                <span>Instance key</span>
                <input
                  value={instanceKey}
                  onChange={(event) => setInstanceKey(event.target.value.toLowerCase())}
                  pattern={"[a-z][a-z0-9_.:\\-]{2,127}"}
                  required
                />
              </label>
              <label>
                <span>Display name</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={3} maxLength={200} required />
              </label>
            </div>
            <label>
              <span>Purpose</span>
              <textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} minLength={20} maxLength={1000} rows={3} required />
            </label>
            <div className="installed-mcp-package-facts">
              <span>Package digest <code>{installation.package_digest.slice(0, 16)}</code></span>
              <span>Publisher <strong>{installation.publisher_id}</strong></span>
            </div>
            {!policy && (
              <div className="installed-mcp-status error-state" role="alert">
                <AlertTriangle size={18} /> No current signed instance policy matches this package.
              </div>
            )}
            <label className="approval-check">
              <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
              <span>The MCP remains disabled and unconfigured. This grants no target, credential, capability, runtime, execution, deployment or infrastructure authority.</span>
            </label>
          </>
        ) : (
          <div className="installed-mcp-empty compact">
            <AlertTriangle size={20} />
            <div><strong>No governed package is installed</strong><span>Complete the Builder, assurance, approval and package installation workflow first.</span></div>
            <button type="button" className="secondary-button" onClick={onOpenBuilder}>
              <PackagePlus size={15} /> Open Builder workflow
            </button>
          </div>
        )}
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="primary-button" disabled={!valid || pending}>
            {pending ? <RefreshCw className="spin" size={16} /> : <PackagePlus size={16} />}
            Add disabled MCP
          </button>
        </footer>
      </form>
    </div>
  );
}

function RetireMcpDialog({
  instance,
  pending,
  onCancel,
  onSubmit,
}: {
  instance: ConnectorInstanceRecord;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const valid = reason.trim().length >= 20 && acknowledged;
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <form className="installed-mcp-dialog retirement" role="dialog" aria-modal="true" aria-labelledby="retire-mcp-title" onSubmit={(event) => { event.preventDefault(); if (valid) onSubmit(reason); }}>
        <header>
          <div><p className="eyebrow">GOVERNED RETIREMENT</p><h3 id="retire-mcp-title">Remove {instance.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close remove MCP" onClick={onCancel}><X size={17} /></button>
        </header>
        <div className="installed-mcp-retirement-impact">
          <Archive size={20} />
          <p>This removes the unused instance from active management. It does not delete its package or evidence, stop a runtime, revoke a credential or contact infrastructure.</p>
        </div>
        <label><span>Retirement reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={20} maxLength={1000} rows={4} required /></label>
        <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I understand that history is preserved and no runtime or infrastructure action is performed.</span></label>
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="installed-mcp-retire" disabled={!valid || pending}>{pending ? <RefreshCw className="spin" size={16} /> : <Archive size={16} />}Confirm retirement</button>
        </footer>
      </form>
    </div>
  );
}

function TargetConfigurationDialog({
  binding,
  instance,
  onBindingCreated,
  onCancel,
  onRequestEnterpriseLogin,
}: {
  binding?: ConnectorTargetConfigurationBinding;
  instance: ConnectorInstanceRecord;
  onBindingCreated: (binding: ConnectorTargetConfigurationBinding) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog target-configuration-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="target-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED TARGET METADATA</p>
            <h3 id="target-mcp-title">Manage target for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close target configuration"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          This boundary binds only signed target metadata. It does not expose endpoints, assign
          credentials, test connectivity, enable the connector, or contact infrastructure.
        </p>
        <TargetConfigurationPanel
          existingBinding={binding}
          instance={instance}
          onBindingCreated={onBindingCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function UpgradeCandidateCard({
  candidate,
  onReviewPlan,
}: {
  candidate: ConnectorUpgradeCandidate;
  onReviewPlan: () => void;
}) {
  const changes = [
    ...candidate.capability_changes.map(
      (item) => `${item.change_type}: ${item.capability_id}`,
    ),
    ...candidate.target_products_added.map((item) => `target added: ${item}`),
    ...candidate.target_products_removed.map((item) => `target removed: ${item}`),
    ...candidate.network_destinations_added.map((item) => `network added: ${item}`),
    ...candidate.network_destinations_removed.map((item) => `network removed: ${item}`),
  ];
  return (
    <article className="installed-mcp-upgrade-candidate">
      <header>
        <div><strong>{candidate.release_version}</strong><span>{candidate.upgrade_class} update</span></div>
        <span className={`installed-mcp-risk ${candidate.risk_level}`}>{candidate.risk_level} risk</span>
      </header>
      <dl className="installed-mcp-upgrade-facts">
        <div><dt>Publisher</dt><dd>{candidate.publisher_id}</dd></div>
        <div><dt>SDK profile</dt><dd>{candidate.sdk_profile}</dd></div>
        <div><dt>Policy review</dt><dd>{candidate.policy_review_required ? "Required" : "Not required"}</dd></div>
        <div><dt>Configuration migration</dt><dd>{candidate.configuration_migration_required ? "Required" : "Not required"}</dd></div>
      </dl>
      <div className="installed-mcp-upgrade-changes">
        <strong>Manifest changes</strong>
        {changes.length ? <ul>{changes.map((item) => <li key={item}>{item}</li>)}</ul> : <span>No capability, target or network changes.</span>}
        <span>Configuration keys {candidate.configuration_key_delta >= 0 ? "+" : ""}{candidate.configuration_key_delta}; secret references {candidate.secret_reference_delta >= 0 ? "+" : ""}{candidate.secret_reference_delta}</span>
      </div>
      <div className="installed-mcp-rollback"><Archive size={15} /><span>Rollback anchor <code>{candidate.rollback_receipt_id}</code></span></div>
      {!candidate.review_eligible && <div className="installed-mcp-status error-state"><AlertTriangle size={17} /><span>Review blocked: {candidate.blockers.join(", ")}</span></div>}
      <button type="button" className="secondary-button installed-mcp-plan-button" onClick={onReviewPlan}><ClipboardList size={15} />Review plan for {candidate.release_version}</button>
    </article>
  );
}

function UpgradePlanEvidence({ plan, subjectId }: { plan: ConnectorUpgradePlan; subjectId: string }) {
  const interruption = plan.estimated_interruption_min_minutes === null
    ? "Not established"
    : `${plan.estimated_interruption_min_minutes}-${plan.estimated_interruption_max_minutes} minutes`;
  return (
    <section className="installed-mcp-plan" aria-labelledby="connector-upgrade-plan-title">
      <header>
        <div><p className="eyebrow">NON-EXECUTABLE PLAN</p><h4 id="connector-upgrade-plan-title">{plan.current_release_version} to {plan.candidate_release_version}</h4></div>
        <span className={`state-badge ${plan.plan_eligible ? "pending" : "blocked"}`}>{plan.plan_state.replaceAll("_", " ")}</span>
      </header>
      <div className="installed-mcp-plan-summary"><span>Interruption <strong>{interruption}</strong></span><span>Rollback window <strong>{plan.rollback_window_minutes} minutes</strong></span><span>Human approval <strong>Required</strong></span></div>
      {plan.blockers.length > 0 && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><div><strong>Plan blocked</strong><span>{plan.blockers.join(", ")}</span></div></div>}
      <div className="installed-mcp-plan-columns">
        <div><strong>Prerequisites</strong><ul>{plan.prerequisite_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><strong>Ordered plan</strong><ol>{plan.steps.map((step) => <li key={step.step_id}><span>{step.phase.replaceAll("_", " ")}</span><small>{step.expected_minutes} min{step.requires_service_interruption ? " | interruption" : ""}</small></li>)}</ol></div>
        <div><strong>Stop conditions</strong><ul>{plan.stop_condition_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><strong>Rollback</strong><ol>{plan.rollback_step_ids.map((item) => <li key={item}>{item}</li>)}</ol></div>
        <div><strong>Post-validation</strong><ul>{plan.validation_check_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
      </div>
      {plan.unknowns.length > 0 && <div className="installed-mcp-plan-unknowns"><strong>Unknowns</strong><ul>{plan.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>}
      <p className="installed-mcp-plan-boundary">This plan does not rebind a package, migrate configuration, stop a session, contact a target, restore data or authorize execution.</p>
      {plan.plan_eligible && <UpgradeApprovalRequestPanel plan={plan} subjectId={subjectId} />}
    </section>
  );
}

const APPROVAL_OUTCOMES: Array<{ value: ConnectorUpgradeApprovalOutcome; label: string }> = [
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "needs_evidence", label: "Request evidence" },
  { value: "defer", label: "Defer" },
];

function UpgradeApprovalRequestPanel({ plan, subjectId }: { plan: ConnectorUpgradePlan; subjectId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["connector-upgrade-approval-record", plan.source_record_id, plan.candidate_receipt_id];
  const [purpose, setPurpose] = useState(
    "Submit this exact connector upgrade plan for independent human review.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const [outcome, setOutcome] = useState<ConnectorUpgradeApprovalOutcome | null>(null);
  const [rationale, setRationale] = useState("");
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const [revalidationPurpose, setRevalidationPurpose] = useState(
    "Revalidate the exact approved plan without granting handoff authority.",
  );
  const [revalidationAcknowledged, setRevalidationAcknowledged] = useState(false);
  const [changeJustification, setChangeJustification] = useState("Prepare this exact connector upgrade for governed ITSM and maintenance-window review.");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [changeAcknowledged, setChangeAcknowledged] = useState(false);
  const [receiptAcknowledged, setReceiptAcknowledged] = useState(false);
  const [signatureAcknowledged, setSignatureAcknowledged] = useState(false);
  const [verificationReceipt, setVerificationReceipt] =
    useState<ConnectorUpgradeEvidenceReceipt | null>(null);
  const [verificationSignedReceipt, setVerificationSignedReceipt] =
    useState<ConnectorUpgradeSignedEvidenceReceipt | null>(null);
  const [verificationFileName, setVerificationFileName] = useState("");
  const [verificationFileError, setVerificationFileError] = useState("");
  const [verificationAcknowledged, setVerificationAcknowledged] = useState(false);
  const recordQuery = useQuery({
    queryKey,
    queryFn: () => getConnectorUpgradeApprovalRecord(plan),
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: createConnectorUpgradeApprovalRequest,
    onSuccess: (request) => {
      setAcknowledged(false);
      queryClient.setQueryData(queryKey, {
        request,
        decision: null,
        state: "pending",
        approval_valid: false,
        approval_granted: false,
        decision_recorded: false,
        separation_of_duties_enforced: true,
        package_rebound: false,
        configuration_changed: false,
        target_contacted: false,
        execution_authorized: false,
        infrastructure_mutation_performed: false,
      });
    },
  });
  const decisionMutation = useMutation({
    mutationFn: decideConnectorUpgradeApproval,
    onSuccess: (record) => {
      queryClient.setQueryData(queryKey, record);
      setDecisionAcknowledged(false);
    },
  });
  const record = decisionMutation.data ?? recordQuery.data;
  const revalidationQueryKey = ["connector-upgrade-approval-revalidation", record?.request.request_id];
  const revalidationQuery = useQuery({
    queryKey: revalidationQueryKey,
    queryFn: () => getLatestConnectorUpgradeApprovalRevalidation(record!),
    enabled: record?.state === "approved" && record.decision?.outcome === "approve",
    retry: false,
  });
  const revalidationMutation = useMutation({
    mutationFn: revalidateConnectorUpgradeApproval,
    onSuccess: (revalidation) => {
      queryClient.setQueryData(revalidationQueryKey, revalidation);
      setRevalidationAcknowledged(false);
    },
  });
  const pending = record?.state === "pending" && record.decision === null;
  const requesterIsCurrentSubject = record?.request.requested_by === subjectId;
  const revalidation = revalidationMutation.data ?? revalidationQuery.data;
  const handoffReadinessQuery = useQuery({
    queryKey: ["connector-upgrade-handoff-readiness", record?.request.request_id, revalidation?.canonical_digest],
    queryFn: () => getConnectorUpgradeHandoffReadiness(record!),
    enabled: Boolean(revalidation),
    retry: false,
  });
  const evidenceReceiptMutation = useMutation({
    mutationFn: createConnectorUpgradeEvidenceReceipt,
    onSuccess: () => setReceiptAcknowledged(false),
  });
  const evidenceReceiptVerificationMutation = useMutation({
    mutationFn: verifyConnectorUpgradeEvidenceReceipt,
    onSuccess: () => setVerificationAcknowledged(false),
  });
  const signedEvidenceReceiptMutation = useMutation({
    mutationFn: createConnectorUpgradeSignedEvidenceReceipt,
    onSuccess: () => setSignatureAcknowledged(false),
  });
  const signedEvidenceVerificationMutation = useMutation({
    mutationFn: verifyConnectorUpgradeSignedEvidenceReceipt,
    onSuccess: () => setVerificationAcknowledged(false),
  });
  const changeContextQueryKey = ["connector-upgrade-change-context", record?.request.request_id];
  const changeContextQuery = useQuery({
    queryKey: changeContextQueryKey,
    queryFn: () => getLatestConnectorUpgradeChangeContextDraft(record!),
    enabled: Boolean(revalidation), retry: false,
  });
  const changeContextMutation = useMutation({
    mutationFn: createConnectorUpgradeChangeContextDraft,
    onSuccess: (draft) => {
      queryClient.setQueryData(changeContextQueryKey, draft);
      setChangeAcknowledged(false);
    },
  });
  const canRevalidate = Boolean(
    record?.state === "approved" && record.decision?.outcome === "approve" &&
    subjectId !== record.request.requested_by && subjectId !== record.decision.decided_by,
  );
  const canCreateChangeContext = revalidation?.revalidated_by === subjectId;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!acknowledged || purpose.trim().length < 20) return;
    mutation.mutate({ plan, purpose });
  };
  if (record) {
    return (
      <section className="installed-mcp-approval-request" aria-live="polite">
        <div className="installed-mcp-approval-heading"><ShieldCheck size={18} /><div><strong>{record.state === "pending" ? "Pending human review" : `Human decision: ${record.state.replaceAll("_", " ")}`}</strong><span>{record.request.request_id}</span></div></div>
        <dl><div><dt>Exact plan</dt><dd>{record.request.plan_digest.slice(0, 16)}</dd></div><div><dt>Expires</dt><dd>{new Date(record.request.expires_at).toLocaleString()}</dd></div><div><dt>Separation</dt><dd>Requester cannot decide</dd></div></dl>
        {pending && requesterIsCurrentSubject && <div className="installed-mcp-status error-state" role="status"><UserX size={17} /><div><strong>Independent approver required</strong><span>{record.request.requested_by} cannot decide this request.</span></div></div>}
        {pending && !requesterIsCurrentSubject && (
          <div className="installed-mcp-approval-decision">
            <div className="installed-mcp-approval-outcomes" role="group" aria-label="Approval decision">
              {APPROVAL_OUTCOMES.map((item) => <button type="button" key={item.value} aria-pressed={outcome === item.value} onClick={() => setOutcome(item.value)}>{item.label}</button>)}
            </div>
            <label>Decision rationale<textarea value={rationale} minLength={20} maxLength={1000} onChange={(event) => setRationale(event.target.value)} /></label>
            <label className="checkbox-row"><input type="checkbox" checked={decisionAcknowledged} onChange={(event) => setDecisionAcknowledged(event.target.checked)} /><span>This records a human decision only. It grants no package, runtime or execution authority.</span></label>
            {decisionMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The decision was rejected because identity, policy, expiry or exact plan evidence changed.</span></div>}
            <button className="primary-button" type="button" disabled={!outcome || rationale.trim().length < 20 || !decisionAcknowledged || decisionMutation.isPending} onClick={() => { if (outcome) decisionMutation.mutate({ record, outcome, rationale }); }}><UserCheck size={16} />{decisionMutation.isPending ? "Recording decision..." : "Record decision"}</button>
          </div>
        )}
        {record.decision && <div className="installed-mcp-approval-result"><strong>{record.decision.outcome.replaceAll("_", " ")}</strong><span>{record.decision.decided_by}</span><p>{record.decision.rationale}</p><small>{new Date(record.decision.decided_at).toLocaleString()}</small></div>}
        {record.state === "approved" && record.decision?.outcome === "approve" && (
          <div className="installed-mcp-approval-decision">
            <div className="installed-mcp-approval-heading"><UserCheck size={18} /><div><strong>Independent approval revalidation</strong><span>A third person verifies the exact request, decision, plan and policy lineage.</span></div></div>
            {revalidation ? (
              <div className="installed-mcp-approval-result">
                <strong>Governance ready</strong>
                <span>Revalidated by {revalidation.revalidated_by}</span>
                <p>Approval was current at revalidation. Handoff remains blocked.</p>
                <small>Valid until {new Date(revalidation.valid_until).toLocaleString()}</small>
                <ul>{revalidation.check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul>
                {handoffReadinessQuery.data && (
                  <div className={`installed-mcp-status ${handoffReadinessQuery.data.assessment_state === "blocked" ? "error-state" : ""}`} role="status">
                    {handoffReadinessQuery.data.assessment_state === "blocked" ? <AlertTriangle size={17} /> : <ShieldCheck size={17} />}
                    <div>
                      <strong>{handoffReadinessQuery.data.assessment_state === "blocked" ? "Handoff blocked" : "Evidence review complete"}</strong>
                      <span>No artifact was issued and the approval remains unconsumed.</span>
                      {handoffReadinessQuery.data.blocker_ids.length > 0 && <><p>Required evidence missing</p><ul>{handoffReadinessQuery.data.blocker_ids.map((blockerId) => <li key={blockerId}>{blockerId}</li>)}</ul></>}
                      <p>Satisfied checks</p>
                      <ul>{handoffReadinessQuery.data.satisfied_check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul>
                      {handoffReadinessQuery.data.audit_readiness_evidence_current && <p>Audit readiness evidence verified and bound to this exact revalidation.</p>}
                      {handoffReadinessQuery.data.itsm_change_evidence_current && <p>Authoritative ITSM change evidence verified and bound to this exact plan.</p>}
                      {handoffReadinessQuery.data.maintenance_window_evidence_current && <p>Approved maintenance-window evidence is current. No handoff or execution authority was issued.</p>}
                      {handoffReadinessQuery.data.not_applicable_check_ids.length > 0 && <><p>Not applicable in this context</p><ul>{handoffReadinessQuery.data.not_applicable_check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul></>}
                      <small>Applicability policy {handoffReadinessQuery.data.applicability_policy_version}</small>
                    </div>
                  </div>
                )}
                {handoffReadinessQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Handoff readiness could not be assessed from current governed evidence.</span></div>}
                {handoffReadinessQuery.data?.assessment_state === "evidence_complete" && (
                  <>
                    <div className="installed-mcp-approval-decision">
                      <strong>Non-executable evidence receipt</strong>
                      <p>Preserve the exact completed review as a safe JSON record. The receipt cannot be used by a runtime and grants no handoff authority.</p>
                      {evidenceReceiptMutation.data ? (
                        <div className="installed-mcp-approval-result">
                          <strong>Evidence receipt ready</strong>
                          <span>{evidenceReceiptMutation.data.receipt_id}</span>
                          <p>Runtime acceptable: no. Approval consumed: no.</p>
                          <small>Valid until {new Date(evidenceReceiptMutation.data.valid_until).toLocaleString()}</small>
                          <button className="secondary-button" type="button" onClick={() => downloadConnectorUpgradeEvidenceReceipt(evidenceReceiptMutation.data)}><Download size={16} />Download JSON receipt</button>
                          {signedEvidenceReceiptMutation.data ? (
                            <div className="installed-mcp-status" role="status">
                              <ShieldCheck size={17} />
                              <div>
                                <strong>Origin authenticated</strong>
                                <span>{signedEvidenceReceiptMutation.data.signature.key_id} / {signedEvidenceReceiptMutation.data.signature.key_version}</span>
                                <p>Signature grants no approval, handoff, runtime or execution authority.</p>
                                <button className="secondary-button" type="button" onClick={() => downloadConnectorUpgradeSignedEvidenceReceipt(signedEvidenceReceiptMutation.data)}><Download size={16} />Download signed receipt</button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <label className="checkbox-row"><input type="checkbox" checked={signatureAcknowledged} onChange={(event) => setSignatureAcknowledged(event.target.checked)} /><span>Authenticate Atlas origin only. The signature is not approval or execution authority.</span></label>
                              {signedEvidenceReceiptMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Origin authentication is unavailable or the receipt is no longer current.</span></div>}
                              <button className="secondary-button" type="button" disabled={!signatureAcknowledged || signedEvidenceReceiptMutation.isPending} onClick={() => signedEvidenceReceiptMutation.mutate({ record, receipt: evidenceReceiptMutation.data })}><ShieldCheck size={16} />{signedEvidenceReceiptMutation.isPending ? "Authenticating origin..." : "Authenticate Atlas origin"}</button>
                            </>
                          )}
                        </div>
                      ) : (
                        <>
                          <label className="checkbox-row"><input type="checkbox" checked={receiptAcknowledged} onChange={(event) => setReceiptAcknowledged(event.target.checked)} /><span>This receipt is evidence only. It grants no approval, handoff, runtime or execution authority.</span></label>
                          {evidenceReceiptMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The receipt was rejected because current governed evidence changed.</span></div>}
                          <button className="primary-button" type="button" disabled={!receiptAcknowledged || evidenceReceiptMutation.isPending} onClick={() => evidenceReceiptMutation.mutate({ record, readiness: handoffReadinessQuery.data! })}><ClipboardList size={16} />{evidenceReceiptMutation.isPending ? "Creating receipt..." : "Create evidence receipt"}</button>
                        </>
                      )}
                    </div>
                    <div className="installed-mcp-approval-decision">
                      <strong>Verify evidence receipt</strong>
                      <label className="installed-mcp-receipt-file"><FileCheck2 size={18} /><span><strong>{verificationFileName || "Select receipt JSON"}</strong><small>JSON, maximum 64 KB</small></span><input aria-label="Receipt JSON" type="file" accept=".json,application/json" onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        setVerificationFileError("");
                        setVerificationReceipt(null);
                        setVerificationSignedReceipt(null);
                        setVerificationFileName(file?.name ?? "");
                        setVerificationAcknowledged(false);
                        evidenceReceiptVerificationMutation.reset();
                        signedEvidenceVerificationMutation.reset();
                        if (!file) return;
                        if (file.size > 65_536) {
                          setVerificationFileError("The receipt exceeds the 64 KB verification limit.");
                          return;
                        }
                        void file.text().then((content) => {
                          try {
                            const candidate: unknown = JSON.parse(content);
                            if (isConnectorUpgradeSignedEvidenceReceipt(candidate) && candidate.request_id === record.request.request_id) {
                              setVerificationSignedReceipt(candidate);
                            } else if (isConnectorUpgradeEvidenceReceipt(candidate) && candidate.request_id === record.request.request_id) {
                              setVerificationReceipt(candidate);
                            } else {
                              throw new Error("unsafe receipt");
                            }
                          } catch {
                            setVerificationFileError("The file is not a safe receipt for this exact approval request.");
                          }
                        });
                      }} /></label>
                      {verificationFileError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>{verificationFileError}</span></div>}
                      {signedEvidenceVerificationMutation.data ? (
                        <div className={`installed-mcp-status ${signedEvidenceVerificationMutation.data.authenticity_state === "authentic" && signedEvidenceVerificationMutation.data.current_state_matches ? "" : "error-state"}`} role="status">
                          {signedEvidenceVerificationMutation.data.authenticity_state === "authentic" && signedEvidenceVerificationMutation.data.current_state_matches ? <ShieldCheck size={17} /> : <AlertTriangle size={17} />}
                          <div><strong>Signature {signedEvidenceVerificationMutation.data.authenticity_state}</strong><span>Integrity valid: yes. Atlas origin authenticated: {signedEvidenceVerificationMutation.data.authenticity_proven ? "yes" : "no"}. Current state matches: {signedEvidenceVerificationMutation.data.current_state_matches ? "yes" : "no"}.</span><small>{signedEvidenceVerificationMutation.data.key_id} / {signedEvidenceVerificationMutation.data.key_version}</small></div>
                        </div>
                      ) : evidenceReceiptVerificationMutation.data ? (
                        <div className={`installed-mcp-status ${evidenceReceiptVerificationMutation.data.verification_state === "current" ? "" : "error-state"}`} role="status">
                          {evidenceReceiptVerificationMutation.data.verification_state === "current" ? <ShieldCheck size={17} /> : <AlertTriangle size={17} />}
                          <div><strong>Receipt {evidenceReceiptVerificationMutation.data.verification_state}</strong><span>Integrity valid: yes. Current state matches: {evidenceReceiptVerificationMutation.data.current_state_matches ? "yes" : "no"}. Authenticity proven: no.</span></div>
                        </div>
                      ) : (
                        <>
                          <label className="checkbox-row"><input type="checkbox" checked={verificationAcknowledged} onChange={(event) => setVerificationAcknowledged(event.target.checked)} /><span>{verificationSignedReceipt ? "A valid signature authenticates Atlas origin only; it is not approval or execution authority." : "Digest integrity is not authenticity, approval, runtime acceptance or execution authority."}</span></label>
                          {(evidenceReceiptVerificationMutation.isError || signedEvidenceVerificationMutation.isError) && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The receipt failed integrity, origin or authorized current-state verification.</span></div>}
                          <button className="secondary-button" type="button" disabled={(!verificationReceipt && !verificationSignedReceipt) || !verificationAcknowledged || evidenceReceiptVerificationMutation.isPending || signedEvidenceVerificationMutation.isPending} onClick={() => { if (verificationSignedReceipt) signedEvidenceVerificationMutation.mutate({ record, signedReceipt: verificationSignedReceipt }); else if (verificationReceipt) evidenceReceiptVerificationMutation.mutate({ record, receipt: verificationReceipt }); }}><FileCheck2 size={16} />{evidenceReceiptVerificationMutation.isPending || signedEvidenceVerificationMutation.isPending ? "Verifying receipt..." : verificationSignedReceipt ? "Verify signed receipt" : "Verify evidence receipt"}</button>
                        </>
                      )}
                    </div>
                  </>
                )}
                {handoffReadinessQuery.data && (changeContextMutation.data ?? changeContextQuery.data) ? (
                  <div className="installed-mcp-approval-result">
                    <strong>Change-context draft recorded</strong>
                    <span>{(changeContextMutation.data ?? changeContextQuery.data)!.itsm_draft_title}</span>
                    <p>Not dispatched. This internal draft grants no window or handoff authority.</p>
                    <small>{new Date((changeContextMutation.data ?? changeContextQuery.data)!.proposed_window_start).toLocaleString()} to {new Date((changeContextMutation.data ?? changeContextQuery.data)!.proposed_window_end).toLocaleString()}</small>
                  </div>
                ) : handoffReadinessQuery.data && canCreateChangeContext ? (
                  <div className="installed-mcp-approval-decision">
                    <strong>Prepare change-context draft</strong>
                    <label>Proposed window start<input type="datetime-local" value={windowStart} onChange={(event) => setWindowStart(event.target.value)} /></label>
                    <label>Proposed window end<input type="datetime-local" value={windowEnd} onChange={(event) => setWindowEnd(event.target.value)} /></label>
                    <label>Change justification<textarea value={changeJustification} minLength={20} maxLength={1000} onChange={(event) => setChangeJustification(event.target.value)} /></label>
                    <label className="checkbox-row"><input type="checkbox" checked={changeAcknowledged} onChange={(event) => setChangeAcknowledged(event.target.checked)} /><span>This creates an internal draft only. It does not dispatch to ITSM, approve the window, issue a handoff or authorize execution.</span></label>
                    {changeContextMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The draft was rejected because readiness, window or exact approval evidence changed.</span></div>}
                    <button className="primary-button" type="button" disabled={!changeAcknowledged || !windowStart || !windowEnd || changeJustification.trim().length < 20 || changeContextMutation.isPending} onClick={() => changeContextMutation.mutate({ record, readiness: handoffReadinessQuery.data, proposedWindowStart: windowStart, proposedWindowEnd: windowEnd, justification: changeJustification })}><ClipboardList size={16} />{changeContextMutation.isPending ? "Recording draft..." : "Record change-context draft"}</button>
                  </div>
                ) : handoffReadinessQuery.data ? <div className="installed-mcp-status" role="status"><UserX size={17} /><span>The latest independent verifier must prepare the change-context draft.</span></div> : null}
              </div>
            ) : canRevalidate ? (
              <>
                <label>Revalidation purpose<textarea value={revalidationPurpose} minLength={20} maxLength={1000} onChange={(event) => setRevalidationPurpose(event.target.value)} /></label>
                <label className="checkbox-row"><input type="checkbox" checked={revalidationAcknowledged} onChange={(event) => setRevalidationAcknowledged(event.target.checked)} /><span>This produces evidence only. It grants no handoff, package, runtime or execution authority.</span></label>
                {revalidationMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Revalidation failed because identity separation, approval lineage, policy or plan freshness changed.</span></div>}
                <button className="primary-button" type="button" disabled={!revalidationAcknowledged || revalidationPurpose.trim().length < 20 || revalidationMutation.isPending} onClick={() => revalidationMutation.mutate({ record, purpose: revalidationPurpose })}><UserCheck size={16} />{revalidationMutation.isPending ? "Revalidating approval..." : "Revalidate approval"}</button>
              </>
            ) : (
              <div className="installed-mcp-status error-state" role="status"><UserX size={17} /><div><strong>Third verifier required</strong><span>The requester and approver cannot revalidate this approval.</span></div></div>
            )}
          </div>
        )}
        <p>The record grants no execution authority and performs no package, runtime or infrastructure change.</p>
      </section>
    );
  }
  if (recordQuery.isLoading || (mutation.isSuccess && recordQuery.isFetching)) {
    return <div className="installed-mcp-status"><RefreshCw className="spin" size={17} /><span>Checking governed approval state...</span></div>;
  }
  return (
    <form className="installed-mcp-approval-request" onSubmit={submit}>
      <div className="installed-mcp-approval-heading"><ShieldCheck size={18} /><div><strong>Request independent human review</strong><span>Bound to this exact immutable plan and active approval policy.</span></div></div>
      <label>Review purpose<textarea value={purpose} minLength={20} maxLength={1000} onChange={(event) => setPurpose(event.target.value)} /></label>
      <label className="checkbox-row"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>This creates a review request only. It is not approval and grants no execution authority.</span></label>
      {mutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The approval request was rejected or the plan evidence changed.</span></div>}
      <button className="primary-button" type="submit" disabled={!acknowledged || purpose.trim().length < 20 || mutation.isPending}><ShieldCheck size={16} />{mutation.isPending ? "Requesting review..." : "Request human approval"}</button>
    </form>
  );
}

function UpgradeReadinessDialog({
  instance,
  subjectId,
  onCancel,
}: {
  instance: ConnectorInstanceRecord;
  subjectId: string;
  onCancel: () => void;
}) {
  const [candidateReceiptId, setCandidateReceiptId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["connector-upgrade-readiness", instance.record_id],
    queryFn: () => getConnectorUpgradeReadiness(instance.record_id),
  });
  const planQuery = useQuery({
    queryKey: ["connector-upgrade-plan", instance.record_id, candidateReceiptId],
    queryFn: () => getConnectorUpgradePlan(instance.record_id, candidateReceiptId ?? ""),
    enabled: candidateReceiptId !== null,
  });
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section className="installed-mcp-dialog upgrade-review" role="dialog" aria-modal="true" aria-labelledby="upgrade-mcp-title">
        <header>
          <div><p className="eyebrow">DECISION SUPPORT ONLY</p><h3 id="upgrade-mcp-title">Review update for {instance.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close update review" onClick={onCancel}><X size={17} /></button>
        </header>
        <div className="installed-mcp-upgrade-boundary"><ShieldCheck size={18} /><p>This review compares governed package evidence only. It does not install an update, change configuration, contact infrastructure or authorize execution.</p></div>
        {query.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={18} /><span>Comparing exact package and manifest lineage...</span></div>}
        {query.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} /><span>Update readiness is unavailable for this MCP.</span></div>}
        {query.data && (
          <>
            <div className="installed-mcp-upgrade-current"><span>Current governed release</span><strong>{query.data.current_release_version}</strong><code>{query.data.current_package_digest.slice(0, 16)}</code></div>
            {query.data.candidates.length ? (
              <div className="installed-mcp-upgrade-list">{query.data.candidates.map((candidate) => <UpgradeCandidateCard candidate={candidate} key={candidate.receipt_id} onReviewPlan={() => setCandidateReceiptId(candidate.receipt_id)} />)}</div>
            ) : (
              <div className="installed-mcp-empty compact"><ArrowUpCircle size={20} /><div><strong>No newer governed package is installed</strong><span>Complete package assurance and installation in MCP Builder before reviewing an update.</span></div></div>
            )}
          </>
        )}
        {planQuery.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={18} /><span>Building exact upgrade plan evidence...</span></div>}
        {planQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} /><span>Upgrade plan is unavailable or source evidence changed.</span></div>}
        {planQuery.data && <UpgradePlanEvidence plan={planQuery.data} subjectId={subjectId} />}
        <footer><button type="button" className="secondary-button" onClick={onCancel}>Close review</button></footer>
      </section>
    </div>
  );
}

function SigningProviderOnboardingReadiness({
  dossier,
}: {
  dossier: ConnectorUpgradeSigningProviderOnboardingReadiness;
}) {
  return (
    <div className="installed-mcp-onboarding-result">
      <div className={`installed-mcp-conformance-state ${
        dossier.provider_onboarding_ready ? "conformant" : "blocked"
      }`}>
        {dossier.provider_onboarding_ready
          ? <ShieldCheck size={18} />
          : <AlertTriangle size={18} />}
        <div>
          <strong>{dossier.provider_onboarding_ready
            ? "Production evidence complete"
            : `${dossier.required_external_inputs.length} requirements blocked`}</strong>
          <span>{dossier.provider_class} / {dossier.key_id ?? "No eligible key"}</span>
          <span>{dossier.algorithm ?? "No eligible algorithm"} / {dossier.policy_version}</span>
        </div>
      </div>
      <dl className="installed-mcp-onboarding-policy">
        <div><dt>Policy</dt><dd>{dossier.policy_id}</dd></div>
        <div><dt>Issued by</dt><dd>{dossier.policy_issued_by}</dd></div>
        <div><dt>Expires</dt><dd>{new Date(dossier.policy_expires_at).toLocaleString()}</dd></div>
        <div><dt>Digest</dt><dd><code>{dossier.policy_digest.slice(0, 16)}</code></dd></div>
        <div><dt>Provenance</dt><dd>{dossier.policy_provenance_verified
          ? "Issuer attestation verified"
          : "Policy blocked"}</dd></div>
        <div><dt>Trust key</dt><dd>{dossier.policy_trust_key_id} / {dossier.policy_trust_key_version}</dd></div>
        <div><dt>Algorithm</dt><dd>{dossier.policy_trust_algorithm}</dd></div>
        <div><dt>Attestation</dt><dd><code>{dossier.policy_attestation_digest.slice(0, 16)}</code></dd></div>
      </dl>
      <div className="installed-mcp-onboarding-requirements" role="list">
        {dossier.requirements.map((requirement) => (
          <div
            className={`installed-mcp-onboarding-requirement ${requirement.state}`}
            key={requirement.requirement_id}
            role="listitem"
          >
            {requirement.state === "satisfied"
              ? <ShieldCheck size={15} />
              : <AlertTriangle size={15} />}
            <div>
              <strong>{requirement.requirement_id.replaceAll("-", " ")}</strong>
              <span>{requirement.state === "satisfied"
                ? "Authoritative evidence satisfied"
                : requirement.reason_code.split(".").at(-1)?.replaceAll("-", " ")}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SigningProviderOnboardingPolicyProvenance({
  diagnostic,
}: {
  diagnostic: ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic;
}) {
  const guidanceLabel = (identifier: string, prefix: string) => identifier
    .replace(prefix, "")
    .replaceAll(".", " ")
    .replaceAll("-", " ");
  return (
    <div className="installed-mcp-onboarding-result installed-mcp-provenance-diagnostic">
      <div className={`installed-mcp-conformance-state ${
        diagnostic.provenance_verified ? "conformant" : "blocked"
      }`}>
        {diagnostic.provenance_verified
          ? <ShieldCheck size={18} />
          : <AlertTriangle size={18} />}
        <div>
          <strong>{diagnostic.provenance_verified
            ? "Policy provenance verified"
            : `${diagnostic.reason_codes.length} provenance checks blocked`}</strong>
          <span>{diagnostic.policy_id ?? "No safe policy reference"}</span>
          <span>{diagnostic.valid_until
            ? `Valid until ${new Date(diagnostic.valid_until).toLocaleString()}`
            : "No verified validity horizon"}</span>
        </div>
      </div>
      <dl className="installed-mcp-onboarding-policy">
        <div><dt>Issuer</dt><dd>{diagnostic.policy_issued_by ?? "Unavailable"}</dd></div>
        <div><dt>Attestation</dt><dd>{diagnostic.attestation_id ?? "Unavailable"}</dd></div>
        <div><dt>Trust key</dt><dd>{diagnostic.trust_key_id
          ? `${diagnostic.trust_key_id} / ${diagnostic.trust_key_version}`
          : "Unavailable"}</dd></div>
        <div><dt>Algorithm</dt><dd>{diagnostic.trust_algorithm ?? "Unavailable"}</dd></div>
        <div><dt>Policy digest</dt><dd><code>{diagnostic.policy_digest?.slice(0, 16) ?? "Unavailable"}</code></dd></div>
        <div><dt>Diagnostic</dt><dd><code>{diagnostic.canonical_digest.slice(0, 16)}</code></dd></div>
      </dl>
      <div className="installed-mcp-onboarding-requirements" role="list">
        {diagnostic.checks.map((check) => (
          <div
            className={`installed-mcp-onboarding-requirement ${check.state}`}
            key={check.check_id}
            role="listitem"
          >
            {check.state === "verified"
              ? <ShieldCheck size={15} />
              : <AlertTriangle size={15} />}
            <div>
              <strong>{check.check_id.replaceAll("-", " ")}</strong>
              <span>{check.reason_code.split(".").at(-1)?.replaceAll("-", " ")}</span>
              {check.state !== "verified" && check.owner_role_id &&
                check.evidence_requirement_id && check.next_action_id ? (
                  <div className="installed-mcp-provenance-guidance">
                    <span><b>Owner</b> {guidanceLabel(check.owner_role_id, "role.")}</span>
                    <span><b>Evidence</b> {guidanceLabel(
                      check.evidence_requirement_id,
                      "evidence.",
                    )}</span>
                    <span><b>Next step</b> {guidanceLabel(check.next_action_id, "action.")}</span>
                    {check.external_input_required ? (
                      <span className="installed-mcp-provenance-external">
                        External deployment input required
                      </span>
                    ) : null}
                  </div>
                ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function InstalledMcpManagementWorkspace({
  onOpenBuilder,
  onRequestEnterpriseLogin,
  subjectId,
}: {
  onOpenBuilder?: () => void;
  onRequestEnterpriseLogin?: () => void;
  subjectId: string;
}) {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [retiring, setRetiring] = useState<ConnectorInstanceRecord | null>(null);
  const [reviewing, setReviewing] = useState<ConnectorInstanceRecord | null>(null);
  const [targeting, setTargeting] = useState<ConnectorInstanceRecord | null>(null);
  const packageQuery = useQuery({
    queryKey: ["connector-package-installations", subjectId],
    queryFn: getConnectorPackageInstallations,
    enabled: Boolean(subjectId),
  });
  const policyQuery = useQuery({
    queryKey: ["connector-instance-creation-policies", subjectId],
    queryFn: getConnectorInstanceCreationPolicies,
    enabled: Boolean(subjectId),
  });
  const instanceQuery = useQuery({
    queryKey: ["connector-instances", subjectId, lifecycle, search],
    queryFn: () => getConnectorInstances({ lifecycle, query: search }),
    enabled: Boolean(subjectId),
  });
  const bindingQuery = useQuery({
    queryKey: ["connector-target-bindings", subjectId],
    queryFn: () => getConnectorTargetConfigurations(),
    enabled: Boolean(subjectId),
  });
  const signingTrustQuery = useQuery({
    queryKey: ["connector-upgrade-signing-key-trust", subjectId],
    queryFn: getConnectorUpgradeEvidenceSigningKeyTrustInventory,
    enabled: Boolean(subjectId),
  });
  const signingConformanceQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-conformance", subjectId],
    queryFn: getLatestConnectorUpgradeSigningProviderConformance,
    enabled: Boolean(subjectId),
    retry: false,
  });
  const signingConformanceMutation = useMutation({
    mutationFn: assessConnectorUpgradeSigningProviderConformance,
    onSuccess: (assessment: ConnectorUpgradeSigningProviderConformanceAssessment) => {
      queryClient.setQueryData(
        ["connector-upgrade-signing-provider-conformance", subjectId],
        assessment,
      );
      void queryClient.invalidateQueries({
        queryKey: ["connector-upgrade-signing-provider-onboarding-readiness"],
      });
    },
  });
  const signingOnboardingQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-onboarding-readiness", subjectId],
    queryFn: getConnectorUpgradeSigningProviderOnboardingReadiness,
    enabled: Boolean(subjectId),
  });
  const signingOnboardingProvenanceQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-onboarding-policy-provenance", subjectId],
    queryFn: getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
    enabled: Boolean(subjectId),
  });
  const createMutation = useMutation({
    mutationFn: createConnectorInstance,
    onSuccess: async () => {
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["connector-instances"] });
    },
  });
  const retireMutation = useMutation({
    mutationFn: retireConnectorInstance,
    onSuccess: async () => {
      setRetiring(null);
      await queryClient.invalidateQueries({ queryKey: ["connector-instances"] });
    },
  });
  const instances = instanceQuery.data ?? [];
  const targetBindings = bindingQuery.data ?? [];
  const bindingByInstance = new Map(
    targetBindings.map((binding) => [binding.source_instance_record_id, binding]),
  );
  const packages = packageQuery.data ?? [];
  const policies = policyQuery.data ?? [];
  const activeCount = instances.filter(
    (item) => item.instance_state === "disabled_unconfigured",
  ).length;
  const lifecycleQueryErrors = [
    instanceQuery.error,
    bindingQuery.error,
    packageQuery.error,
    policyQuery.error,
  ].filter((error) => error !== null);
  const lifecycleQueryFailed = lifecycleQueryErrors.length > 0;
  const sessionAuthenticationFailed = lifecycleQueryErrors.some((error) => hasStatus(error, 401));
  const lifecycleAuthorizationFailed = lifecycleQueryErrors.some((error) => hasStatus(error, 403));
  const lifecycleMutationError = createMutation.error ?? retireMutation.error;
  const mutationAuthenticationFailed = hasStatus(lifecycleMutationError, 401);
  const mutationAuthorizationFailed = hasStatus(lifecycleMutationError, 403);
  const mutationConflict = hasStatus(lifecycleMutationError, 409);
  const mutationAction = createMutation.error ? "creation" : "retirement";
  const openBuilder = () => {
    setAdding(false);
    if (onOpenBuilder) {
      onOpenBuilder();
      return;
    }
    document.getElementById("connector-view-builder")?.scrollIntoView?.({
      behavior: "smooth",
      block: "start",
    });
  };
  const refresh = () => {
    void packageQuery.refetch();
    void policyQuery.refetch();
    void instanceQuery.refetch();
    void bindingQuery.refetch();
    void signingTrustQuery.refetch();
    void signingConformanceQuery.refetch();
    void signingOnboardingQuery.refetch();
    void signingOnboardingProvenanceQuery.refetch();
  };

  return (
    <section className="installed-mcp-workspace" aria-labelledby="installed-mcp-title">
      <div className="installed-mcp-heading">
        <div>
          <p className="eyebrow">MCP INVENTORY</p>
          <h2 id="installed-mcp-title">Installed MCPs</h2>
          <p>Governed connector instances and their exact installed package lineage.</p>
        </div>
        <div className="installed-mcp-heading-actions">
          <span className="state-badge neutral"><ShieldCheck size={14} /> no runtime authority</span>
          <button className="icon-button" type="button" title="Refresh MCP inventory" aria-label="Refresh MCP inventory" onClick={refresh}><RefreshCw size={17} /></button>
          <button className="primary-button" type="button" disabled={packageQuery.isLoading || packageQuery.isError || policyQuery.isLoading || policyQuery.isError} title="Add MCP" onClick={() => { createMutation.reset(); setAdding(true); }}><PackagePlus size={16} />Add MCP</button>
        </div>
      </div>
      <div className="installed-mcp-readiness" aria-label="MCP lifecycle prerequisites">
        <span data-ready="true">
          <ShieldCheck size={15} />
          Backend authorization enforced
        </span>
        <span data-ready={!packageQuery.isLoading && !packageQuery.isError && packages.length > 0}>
          {packageQuery.isLoading ? <RefreshCw className="spin" size={15} /> : <PackagePlus size={15} />}
          {packageQuery.isLoading
            ? "Checking packages"
            : packageQuery.isError
              ? "Package inventory unavailable"
            : packages.length > 0
              ? `${packages.length} governed package${packages.length === 1 ? "" : "s"}`
              : "Governed package required"}
        </span>
        <span data-ready={!policyQuery.isLoading && !policyQuery.isError && policies.length > 0}>
          {policyQuery.isLoading ? <RefreshCw className="spin" size={15} /> : <FileCheck2 size={15} />}
          {policyQuery.isLoading
            ? "Checking policy"
            : policyQuery.isError
              ? "Policy inventory unavailable"
            : policies.length > 0
              ? `${policies.length} creation polic${policies.length === 1 ? "y" : "ies"}`
              : "Creation policy required"}
        </span>
        {!packageQuery.isLoading && !packageQuery.isError && packages.length === 0 && (
          <button type="button" className="secondary-button" onClick={openBuilder}>
            <PackagePlus size={15} /> Open Builder workflow
          </button>
        )}
      </div>
      <details className="installed-mcp-signing-diagnostics">
        <summary>
          <span><ShieldCheck size={16} /> Security and onboarding diagnostics</span>
          <small>Signing trust, provider readiness and policy provenance</small>
        </summary>
      <section className="installed-mcp-signing-trust" aria-labelledby="signing-trust-title">
        <div className="installed-mcp-signing-trust-heading">
          <div>
            <p className="eyebrow">EVIDENCE AUTHENTICITY</p>
            <h3 id="signing-trust-title">Signing trust</h3>
          </div>
          {signingTrustQuery.data && (
            <span className={`state-badge ${signingTrustQuery.data.provider_available ? "success" : "neutral"}`}>
              {signingTrustQuery.data.provider_state}
            </span>
          )}
        </div>
        {signingTrustQuery.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={17} /><span>Reading scoped signing trust...</span></div>}
        {signingTrustQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Signing trust metadata is unavailable for this scope.</span></div>}
        {signingTrustQuery.data && signingTrustQuery.data.keys.length === 0 && (
          <div className="installed-mcp-status"><ShieldCheck size={17} /><div><strong>No trusted signing key</strong><span>{signingTrustQuery.data.provider_class}. Production signing remains fail-closed.</span></div></div>
        )}
        {signingTrustQuery.data?.keys.map((key) => (
          <div className="installed-mcp-signing-key" key={`${key.key_id}:${key.key_version}`}>
            <ShieldCheck size={18} />
            <div><strong>{key.key_id}</strong><span>{key.key_version} / {key.signer_profile_id}</span></div>
            <div><strong>{key.effective_state.replaceAll("_", " ")}</strong><span>Valid until {new Date(key.expires_at).toLocaleString()}</span></div>
            <div><strong>{key.verification_trusted ? "Verification trusted" : "Verification blocked"}</strong><span>{key.algorithm}</span></div>
          </div>
        ))}
        {signingTrustQuery.data && <p className="installed-mcp-signing-boundary">Read-only metadata. No key management or signing authority.</p>}
        <div className="installed-mcp-conformance" aria-labelledby="signing-conformance-title">
          <div className="installed-mcp-conformance-heading">
            <div>
              <span>PROVIDER DIAGNOSTIC</span>
              <strong id="signing-conformance-title">Signing-provider conformance</strong>
            </div>
            <button
              type="button"
              className="secondary-button"
              disabled={signingConformanceMutation.isPending}
              onClick={() => signingConformanceMutation.mutate()}
            >
              {signingConformanceMutation.isPending
                ? <RefreshCw className="spin" size={15} />
                : <Activity size={15} />}
              Run assessment
            </button>
          </div>
          {signingConformanceQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Reading latest provider evidence...</span>
            </div>
          )}
          {(signingConformanceQuery.isError || signingConformanceMutation.isError) && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Signing-provider conformance evidence is unavailable.</span>
            </div>
          )}
          {!signingConformanceQuery.isLoading && !signingConformanceQuery.data &&
            !signingConformanceQuery.isError && (
              <div className="installed-mcp-status">
                <Activity size={17} />
                <span>No bounded provider assessment has been recorded for this scope.</span>
              </div>
            )}
          {signingConformanceQuery.data && (
            <div className="installed-mcp-conformance-result">
              <div className={
                `installed-mcp-conformance-state ${
                  signingConformanceQuery.data.signing_provider_conformant
                    ? "conformant" : "blocked"
                }`
              }>
                {signingConformanceQuery.data.signing_provider_conformant
                  ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
                <div>
                  <strong>{signingConformanceQuery.data.state.replaceAll("_", " ")}</strong>
                  <span>{signingConformanceQuery.data.provider_class}</span>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Key reference</dt>
                  <dd>{signingConformanceQuery.data.key_id ?? "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Algorithm</dt>
                  <dd>{signingConformanceQuery.data.algorithm ?? "Not observed"}</dd>
                </div>
                <div>
                  <dt>Policy</dt>
                  <dd>{signingConformanceQuery.data.policy_version}</dd>
                </div>
                <div>
                  <dt>Valid until</dt>
                  <dd>{new Date(signingConformanceQuery.data.valid_until).toLocaleString()}</dd>
                </div>
              </dl>
              <p>
                {signingConformanceQuery.data.production_approved
                  ? "Provider is approved for production by the active policy."
                  : "Provider is not approved for production; production remains fail-closed."}
              </p>
            </div>
          )}
          <p className="installed-mcp-signing-boundary">
            Server-generated challenge only. No key management, receipt signing or execution authority.
          </p>
        </div>
        <div className="installed-mcp-onboarding" aria-labelledby="signing-onboarding-title">
          <div className="installed-mcp-signing-trust-heading">
            <div>
              <p className="eyebrow">PRODUCTION EVIDENCE</p>
              <h3 id="signing-onboarding-title">Provider onboarding readiness</h3>
            </div>
            {signingOnboardingQuery.data && (
              <span className={`state-badge ${
                signingOnboardingQuery.data.provider_onboarding_ready ? "success" : "neutral"
              }`}>
                {signingOnboardingQuery.data.provider_onboarding_ready
                  ? "ready"
                  : "evidence required"}
              </span>
            )}
          </div>
          {signingOnboardingQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Evaluating production onboarding evidence...</span>
            </div>
          )}
          {signingOnboardingQuery.isError && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Production onboarding is policy-blocked for this scope.</span>
            </div>
          )}
          {signingOnboardingQuery.data && (
            <SigningProviderOnboardingReadiness dossier={signingOnboardingQuery.data} />
          )}
          <p className="installed-mcp-signing-boundary">
            Evidence only. No provider configuration, key management, signing or execution authority.
          </p>
        </div>
        <div className="installed-mcp-onboarding" aria-labelledby="signing-onboarding-provenance-title">
          <div className="installed-mcp-signing-trust-heading">
            <div>
              <p className="eyebrow">TRUST DIAGNOSTIC</p>
              <h3 id="signing-onboarding-provenance-title">Policy provenance diagnostic</h3>
            </div>
            {signingOnboardingProvenanceQuery.data && (
              <span className={`state-badge ${
                signingOnboardingProvenanceQuery.data.provenance_verified ? "success" : "neutral"
              }`}>
                {signingOnboardingProvenanceQuery.data.state}
              </span>
            )}
          </div>
          {signingOnboardingProvenanceQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Checking policy provenance evidence...</span>
            </div>
          )}
          {signingOnboardingProvenanceQuery.isError && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Policy provenance diagnostic is unavailable for this scope.</span>
            </div>
          )}
          {signingOnboardingProvenanceQuery.data && (
            <SigningProviderOnboardingPolicyProvenance
              diagnostic={signingOnboardingProvenanceQuery.data}
            />
          )}
          <p className="installed-mcp-signing-boundary">
            Read-only diagnostic. No trust-store, policy, key or provider mutation authority.
          </p>
        </div>
      </section>
      </details>
      <div className="installed-mcp-toolbar">
        <div className="installed-mcp-filters" aria-label="MCP lifecycle filter">
          {(["active", "retired", "all"] as const).map((value) => (
            <button type="button" data-active={lifecycle === value} aria-pressed={lifecycle === value} onClick={() => setLifecycle(value)} key={value}>{value === "active" ? "Active" : value === "retired" ? "Retired" : "All"}</button>
          ))}
        </div>
        <label className="installed-mcp-search"><Search size={16} /><span className="sr-only">Search installed MCPs</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search MCPs" maxLength={200} /></label>
      </div>
      {lifecycleQueryFailed && (
        <div className="installed-mcp-status error-state" role="alert">
          <AlertTriangle size={18} />
          <div>
            <strong>{sessionAuthenticationFailed
              ? "Your signed-in session has expired"
              : lifecycleAuthorizationFailed
                ? "Connector lifecycle permission is required"
                : "Connector lifecycle data is unavailable"}</strong>
            <span>{sessionAuthenticationFailed
              ? "Sign in again; the MCP inventory will refresh automatically."
              : lifecycleAuthorizationFailed
                ? "This signed-in account is missing a required role or scope."
                : "The instance, package or policy inventory could not be loaded. Retry the request."}</span>
          </div>
          {sessionAuthenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !sessionAuthenticationFailed && !lifecycleAuthorizationFailed ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {instanceQuery.isLoading && (
        <div className="installed-mcp-status" role="status"><RefreshCw className="spin" size={18} /><span>Loading MCP lifecycle inventory...</span></div>
      )}
      {lifecycleMutationError && (
        <div className="installed-mcp-status error-state" role="alert">
          {mutationAuthenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
          <div>
            <strong>
              {mutationAuthenticationFailed
                ? "Your signed-in session has expired"
                : mutationAuthorizationFailed
                  ? "Connector lifecycle permission is required"
                  : mutationConflict
                    ? "MCP lifecycle changed"
                    : `MCP ${mutationAction} failed`}
            </strong>
            <span>
              {mutationAuthenticationFailed
                ? "Sign in again before changing MCP lifecycle records."
                : mutationAuthorizationFailed
                  ? "This signed-in account is missing the required role or scope."
                  : mutationConflict
                    ? "Refresh the MCP inventory and review the current package or instance state."
                    : mutationAction === "creation"
                      ? "Review the exact package, instance key, and creation policy."
                      : "Configured instances require governed decommissioning before retirement."}
            </span>
          </div>
          {mutationAuthenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : mutationConflict ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Refresh inventory
            </button>
          ) : null}
        </div>
      )}
      {!instanceQuery.isError && !instanceQuery.isLoading && instances.length === 0 ? (
        <div className="installed-mcp-empty"><Boxes size={24} /><div><strong>No {lifecycle === "all" ? "" : lifecycle} MCP instances</strong><span>{packages.length ? "Select Add MCP to create a disabled instance from a governed package." : "Complete package installation in the Builder workflow, then return here to add an MCP."}</span></div></div>
      ) : !instanceQuery.isLoading && !instanceQuery.isError ? (
        <div className="installed-mcp-table-wrap">
          <table className="installed-mcp-table">
            <thead><tr><th>MCP</th><th>Package</th><th>State</th><th>Owner</th><th>Lifecycle event</th><th>Actions</th></tr></thead>
            <tbody>
              {instances.map((instance) => {
                const binding = bindingByInstance.get(instance.record_id);
                const configured = Boolean(binding);
                return (
                  <tr key={instance.record_id}>
                    <td><strong>{instance.display_name}</strong><code>{instance.instance_key}</code></td>
                    <td><strong>{instance.connector_id}</strong><span>{instance.release_version}</span></td>
                    <td>
                      <span className={`state-badge ${instance.instance_state === "retired" ? "neutral" : "pending"}`}>
                        {instance.instance_state === "retired"
                          ? "Retired"
                          : configured
                            ? "Disabled / target configured"
                            : "Disabled / unconfigured"}
                      </span>
                    </td>
                    <td>{instance.owner_id}</td>
                    <td>
                      <span className="installed-mcp-event-label">
                        {instance.instance_state === "retired"
                          ? "Retired"
                          : binding
                            ? "Target bound"
                            : "Created"}
                      </span>
                      {new Date(binding?.bound_at ?? instance.retired_at ?? instance.created_at).toLocaleString()}
                    </td>
                    <td>
                      {instance.instance_state === "disabled_unconfigured" && bindingQuery.isSuccess && (
                        <div className="installed-mcp-row-actions">
                          <button
                            className="secondary-button installed-mcp-row-action"
                            type="button"
                            title={configured ? "View governed target metadata" : "Bind governed target metadata"}
                            aria-label={`${configured ? "View" : "Manage"} target for ${instance.display_name}`}
                            onClick={() => setTargeting(instance)}
                          >
                            <Link2 size={15} /><span>{configured ? "View target" : "Manage target"}</span>
                          </button>
                          <button className="secondary-button installed-mcp-row-action" type="button" title="Review governed update evidence" aria-label={`Review update for ${instance.display_name}`} onClick={() => setReviewing(instance)}><ArrowUpCircle size={15} /><span>Review update</span></button>
                          {!configured && (
                            <button className="secondary-button installed-mcp-row-action danger" type="button" title="Remove from active management and preserve history" aria-label={`Remove ${instance.display_name}`} onClick={() => { retireMutation.reset(); setRetiring(instance); }}><Archive size={15} /><span>Remove</span></button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="installed-mcp-footnote"><span>{activeCount} active in this result</span><span>Target bindings remain disabled metadata. Remove preserves history. Updates remain review-only.</span></div>
      {adding && <AddMcpDialog packages={packages} policies={policies} pending={createMutation.isPending} onCancel={() => setAdding(false)} onOpenBuilder={openBuilder} onSubmit={(input) => createMutation.mutate(input)} />}
      {retiring && <RetireMcpDialog instance={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ instance: retiring, reason })} />}
      {reviewing && <UpgradeReadinessDialog instance={reviewing} subjectId={subjectId} onCancel={() => setReviewing(null)} />}
      {targeting && (
        <TargetConfigurationDialog
          instance={targeting}
          binding={bindingByInstance.get(targeting.record_id)}
          onBindingCreated={(binding) => {
            queryClient.setQueryData<ConnectorTargetConfigurationBinding[]>(
              ["connector-target-bindings", subjectId],
              (current = []) => [
                ...current.filter(
                  (item) => item.source_instance_record_id !== binding.source_instance_record_id,
                ),
                binding,
              ],
            );
          }}
          onCancel={() => setTargeting(null)}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        />
      )}
    </section>
  );
}
