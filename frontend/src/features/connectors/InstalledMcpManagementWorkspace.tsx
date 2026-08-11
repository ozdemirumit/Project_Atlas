import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArrowUpCircle,
  Boxes,
  ClipboardList,
  PackagePlus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  createConnectorUpgradeApprovalRequest,
  getConnectorUpgradeReadiness,
  type ConnectorUpgradeCandidate,
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

type LifecycleFilter = "active" | "retired" | "all";

function AddMcpDialog({
  packages,
  policies,
  pending,
  onCancel,
  onSubmit,
}: {
  packages: ConnectorPackageInstallationReceipt[];
  policies: ConnectorInstanceCreationPolicy[];
  pending: boolean;
  onCancel: () => void;
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
            <div><strong>No governed package is installed</strong><span>Complete the Builder, assurance, approval and package installation workflow below first.</span></div>
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
          <div><p className="eyebrow">PRESERVE HISTORY</p><h3 id="retire-mcp-title">Retire {instance.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close retire MCP" onClick={onCancel}><X size={17} /></button>
        </header>
        <div className="installed-mcp-retirement-impact">
          <Archive size={20} />
          <p>This removes the unused instance from active management. It does not delete its package or evidence, stop a runtime, revoke a credential or contact infrastructure.</p>
        </div>
        <label><span>Retirement reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={20} maxLength={1000} rows={4} required /></label>
        <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I understand that history is preserved and no runtime or infrastructure action is performed.</span></label>
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="installed-mcp-retire" disabled={!valid || pending}>{pending ? <RefreshCw className="spin" size={16} /> : <Archive size={16} />}Retire MCP</button>
        </footer>
      </form>
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

function UpgradePlanEvidence({ plan }: { plan: ConnectorUpgradePlan }) {
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
      {plan.plan_eligible && <UpgradeApprovalRequestPanel plan={plan} />}
    </section>
  );
}

function UpgradeApprovalRequestPanel({ plan }: { plan: ConnectorUpgradePlan }) {
  const [purpose, setPurpose] = useState(
    "Submit this exact connector upgrade plan for independent human review.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorUpgradeApprovalRequest });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!acknowledged || purpose.trim().length < 20) return;
    mutation.mutate({ plan, purpose });
  };
  if (mutation.data) {
    return (
      <section className="installed-mcp-approval-request" aria-live="polite">
        <div className="installed-mcp-approval-heading"><ShieldCheck size={18} /><div><strong>Pending human review</strong><span>{mutation.data.request_id}</span></div></div>
        <dl><div><dt>Exact plan</dt><dd>{mutation.data.plan_digest.slice(0, 16)}</dd></div><div><dt>Expires</dt><dd>{new Date(mutation.data.expires_at).toLocaleString()}</dd></div><div><dt>Separation</dt><dd>Requester cannot decide</dd></div></dl>
        <p>The request records no approval, grants no execution authority and performs no infrastructure change.</p>
      </section>
    );
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
  onCancel,
}: {
  instance: ConnectorInstanceRecord;
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
        {planQuery.data && <UpgradePlanEvidence plan={planQuery.data} />}
        <footer><button type="button" className="secondary-button" onClick={onCancel}>Close review</button></footer>
      </section>
    </div>
  );
}

export default function InstalledMcpManagementWorkspace() {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [retiring, setRetiring] = useState<ConnectorInstanceRecord | null>(null);
  const [reviewing, setReviewing] = useState<ConnectorInstanceRecord | null>(null);
  const packageQuery = useQuery({
    queryKey: ["connector-package-installations"],
    queryFn: getConnectorPackageInstallations,
  });
  const policyQuery = useQuery({
    queryKey: ["connector-instance-creation-policies"],
    queryFn: getConnectorInstanceCreationPolicies,
  });
  const instanceQuery = useQuery({
    queryKey: ["connector-instances", lifecycle, search],
    queryFn: () => getConnectorInstances({ lifecycle, query: search }),
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
  const packages = packageQuery.data ?? [];
  const policies = policyQuery.data ?? [];
  const activeCount = instances.filter(
    (item) => item.instance_state === "disabled_unconfigured",
  ).length;
  const refresh = () => {
    void packageQuery.refetch();
    void policyQuery.refetch();
    void instanceQuery.refetch();
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
          <button className="primary-button" type="button" disabled={packageQuery.isLoading || policyQuery.isLoading} onClick={() => { createMutation.reset(); setAdding(true); }}><PackagePlus size={16} />Add MCP</button>
        </div>
      </div>
      <div className="installed-mcp-toolbar">
        <div className="installed-mcp-filters" aria-label="MCP lifecycle filter">
          {(["active", "retired", "all"] as const).map((value) => (
            <button type="button" data-active={lifecycle === value} aria-pressed={lifecycle === value} onClick={() => setLifecycle(value)} key={value}>{value === "active" ? "Active" : value === "retired" ? "Retired" : "All"}</button>
          ))}
        </div>
        <label className="installed-mcp-search"><Search size={16} /><span className="sr-only">Search installed MCPs</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search MCPs" maxLength={200} /></label>
      </div>
      {(instanceQuery.isError || packageQuery.isError || policyQuery.isError) && (
        <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} /><div><strong>Enterprise connector inventory is unavailable</strong><span>Sign in with an authorized MFA browser session and refresh.</span></div></div>
      )}
      {createMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} />MCP creation failed. Review the exact package, identity key and policy boundary.</div>}
      {retireMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} />MCP retirement failed. Configured instances require governed decommissioning first.</div>}
      {!instanceQuery.isError && !instanceQuery.isLoading && instances.length === 0 ? (
        <div className="installed-mcp-empty"><Boxes size={24} /><div><strong>No {lifecycle === "all" ? "" : lifecycle} MCP instances</strong><span>{packages.length ? "Select Add MCP to create a disabled instance from a governed package." : "Complete package installation in the Builder workflow below, then return here to add an MCP."}</span></div></div>
      ) : (
        <div className="installed-mcp-table-wrap">
          <table className="installed-mcp-table">
            <thead><tr><th>MCP</th><th>Package</th><th>State</th><th>Owner</th><th>Lifecycle event</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {instances.map((instance) => (
                <tr key={instance.record_id}>
                  <td><strong>{instance.display_name}</strong><code>{instance.instance_key}</code></td>
                  <td><strong>{instance.connector_id}</strong><span>{instance.release_version}</span></td>
                  <td><span className={`state-badge ${instance.instance_state === "retired" ? "neutral" : "pending"}`}>{instance.instance_state === "retired" ? "Retired" : "Disabled"}</span></td>
                  <td>{instance.owner_id}</td>
                  <td>
                    <span className="installed-mcp-event-label">
                      {instance.instance_state === "retired" ? "Retired" : "Created"}
                    </span>
                    {new Date(instance.retired_at ?? instance.created_at).toLocaleString()}
                  </td>
                  <td>{instance.instance_state === "disabled_unconfigured" && <div className="installed-mcp-row-actions"><button className="icon-button" type="button" title="Review update" aria-label={`Review update for ${instance.display_name}`} onClick={() => setReviewing(instance)}><ArrowUpCircle size={16} /></button><button className="icon-button" type="button" title="Retire MCP" aria-label={`Retire ${instance.display_name}`} onClick={() => { retireMutation.reset(); setRetiring(instance); }}><Archive size={16} /></button></div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="installed-mcp-footnote"><span>{activeCount} active in this result</span><span>Packages and lifecycle history are preserved.</span></div>
      {adding && <AddMcpDialog packages={packages} policies={policies} pending={createMutation.isPending} onCancel={() => setAdding(false)} onSubmit={(input) => createMutation.mutate(input)} />}
      {retiring && <RetireMcpDialog instance={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ instance: retiring, reason })} />}
      {reviewing && <UpgradeReadinessDialog instance={reviewing} onCancel={() => setReviewing(null)} />}
    </section>
  );
}
