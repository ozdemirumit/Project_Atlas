import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, FileSearch, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorPackageRegistration } from "../../api/packageRegistrations";
import type { ConnectorRegistryPublicationReceipt } from "../../api/registryPublications";
import { PackageInstallationPanel } from "./PackageInstallationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "741387e94dbff4338845d602d69415e817605fd09b8d21337eb882728337fac6",
  "environment.test": "f06b1cd76d1e647988136a6de7872a0aa86ba2da8c5d165525ee3a6fc53432b7",
};

export function PackageRegistrationPanel({
  publication,
}: {
  publication: ConnectorRegistryPublicationReceipt;
}) {
  const [policyId, setPolicyId] = useState(
    "connector-package-registration-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[publication.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Register this exact published package without installation or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorPackageRegistration });
  const record = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="package-registration-panel" aria-labelledby="package-registration-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">CATALOG ADMISSION</p>
          <h3 id="package-registration-title">Governed package registration</h3>
        </div>
        <FileSearch size={24} />
      </div>

      {!record && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Registration policy ID</span>
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
            <span>Registration purpose</span>
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
              Registration grants no installation, instance, target, secret, runtime, execution, or
              deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ publication, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <BadgeCheck size={16} />}
            Register published package
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Package registration unavailable</h3>
            <p>Publication lineage, artifact integrity, manifest, policy, or separation failed.</p>
          </div>
        </div>
      )}

      {record && (
        <>
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{record.record_id}</strong>
              <code>{record.manifest.manifest_digest}</code>
            </div>
            <span className="state-badge healthy">
              <BadgeCheck size={14} />registered
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Connector</span><strong>{record.connector_id}</strong></div>
            <div><span>Release</span><strong>{record.release_version}</strong></div>
            <div><span>SDK profile</span><strong>{record.manifest.sdk_profile}</strong></div>
            <div><span>Capabilities</span><strong>{record.manifest.capabilities.length}</strong></div>
            <div><span>Target products</span><strong>{record.manifest.target_products.join(", ")}</strong></div>
            <div><span>Network declarations</span><strong>{record.manifest.network_destination_count}</strong></div>
          </div>
          <p className="muted-copy">
            The package is admitted to the governed catalog. Installation, configuration, enablement,
            runtime trust, and execution remain separate.
          </p>
        </div>
        <PackageInstallationPanel registration={record} />
        </>
      )}
    </section>
  );
}
