import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Component, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorInstance } from "../../api/connectorInstances";
import type { ConnectorPackageInstallationReceipt } from "../../api/packageInstallations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "f26624c1e18a25c13bc8cf7d29aed3d17d1ff0d3949a47af422fe1f256fb5401",
  "environment.test": "34eacbe4e2ac815f91553287c4598f58eb56b44e3ecf827b62dc6335e81c3873",
};

export function ConnectorInstanceCreationPanel({
  installation,
}: {
  installation: ConnectorPackageInstallationReceipt;
}) {
  const [instanceKey, setInstanceKey] = useState(`${installation.connector_id}-primary`);
  const [displayName, setDisplayName] = useState(`${installation.connector_id} primary`);
  const [policyId, setPolicyId] = useState("connector-instance-creation-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[installation.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Create a disabled connector instance without target, secret, enablement, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorInstance });
  const record = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(instanceKey) &&
    displayName.trim().length >= 3 &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="connector-instance-panel" aria-labelledby="connector-instance-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">DISABLED INSTANCE</p>
          <h3 id="connector-instance-title">Governed instance creation</h3>
        </div>
        <Component size={24} />
      </div>

      {!record && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Instance key</span>
              <input value={instanceKey} onChange={(event) => setInstanceKey(event.target.value)} />
            </label>
            <label>
              <span>Display name</span>
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </label>
            <label>
              <span>Instance policy ID</span>
              <input value={policyId} onChange={(event) => setPolicyId(event.target.value)} />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input
                value={policyDigest}
                onChange={(event) => setPolicyDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
          </div>
          <label>
            <span>Creation purpose</span>
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              rows={3}
              maxLength={1000}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              The instance remains disabled and unconfigured, with no target, secret, capability,
              runtime, execution, or deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                installation,
                instanceKey,
                displayName,
                policyId,
                policyDigest,
                purpose,
              })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Component size={16} />}
            Create disabled instance
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Instance creation unavailable</h3>
            <p>Installation lineage, policy, scope, identity, or separation failed.</p>
          </div>
        </div>
      )}

      {record && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{record.display_name}</strong>
              <code>{record.instance_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} />disabled
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Instance key</span><strong>{record.instance_key}</strong></div>
            <div><span>Release</span><strong>{record.release_version}</strong></div>
            <div><span>Owner</span><strong>{record.owner_id}</strong></div>
            <div><span>State</span><strong>{record.instance_state}</strong></div>
          </div>
          <p className="muted-copy">
            The identity exists, but target configuration, credentials, capabilities, health
            validation, enablement, runtime trust, and execution remain unavailable.
          </p>
        </div>
      )}
    </section>
  );
}
