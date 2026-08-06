import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Box, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorPackageInstallation } from "../../api/packageInstallations";
import type { ConnectorPackageRegistrationRecord } from "../../api/packageRegistrations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "d9ba6c70baebf8d47188f831c55174c2b4c625e068b2df6d34002ae3eb4ad821",
  "environment.test": "04df5b8e1f47b22e854af72cdeb6c37f6d92371e1e24b990aa80e0b30d783532",
};

export function PackageInstallationPanel({
  registration,
}: {
  registration: ConnectorPackageRegistrationRecord;
}) {
  const [policyId, setPolicyId] = useState(
    "connector-package-installation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[registration.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Install this exact package without instance, target, secret, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorPackageInstallation });
  const receipt = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="package-installation-panel" aria-labelledby="package-installation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">IMMUTABLE INSTALLATION</p>
          <h3 id="package-installation-title">Governed package installation</h3>
        </div>
        <Box size={24} />
      </div>

      {!receipt && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Installation policy ID</span>
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
            <span>Installation purpose</span>
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
              Installation grants no instance, target, secret, enablement, runtime, execution, or
              deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ registration, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Box size={16} />}
            Install registered package
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Package installation unavailable</h3>
            <p>Registration lineage, artifact, manifest, policy, store, or separation failed.</p>
          </div>
        </div>
      )}

      {receipt && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{receipt.receipt_id}</strong>
              <code>{receipt.manifest_digest}</code>
            </div>
            <span className="state-badge healthy">
              <BadgeCheck size={14} />installed
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Connector</span><strong>{receipt.connector_id}</strong></div>
            <div><span>Release</span><strong>{receipt.release_version}</strong></div>
            <div><span>Installer profile</span><strong>{receipt.installation.installer_profile_id}</strong></div>
            <div><span>Store profile</span><strong>{receipt.installation.installation_store_profile_id}</strong></div>
          </div>
          <p className="muted-copy">
            The exact package is in non-executable installation custody. Instance creation, target
            and credential binding, enablement, runtime trust, and execution remain separate.
          </p>
        </div>
      )}
    </section>
  );
}
