import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  Boxes,
  PackagePlus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState, type FormEvent } from "react";

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

export default function InstalledMcpManagementWorkspace() {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [retiring, setRetiring] = useState<ConnectorInstanceRecord | null>(null);
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
                  <td>{instance.instance_state === "disabled_unconfigured" && <button className="icon-button" type="button" title="Retire MCP" aria-label={`Retire ${instance.display_name}`} onClick={() => { retireMutation.reset(); setRetiring(instance); }}><Archive size={16} /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="installed-mcp-footnote"><span>{activeCount} active in this result</span><span>Packages and lifecycle history are preserved.</span></div>
      {adding && <AddMcpDialog packages={packages} policies={policies} pending={createMutation.isPending} onCancel={() => setAdding(false)} onSubmit={(input) => createMutation.mutate(input)} />}
      {retiring && <RetireMcpDialog instance={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ instance: retiring, reason })} />}
    </section>
  );
}
