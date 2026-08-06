import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, PackageCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { ConnectorPackageSigningReceipt } from "../../api/packageSigning";
import { createConnectorRegistryPublication } from "../../api/registryPublications";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "682b5447532c5fa571a30f20eab4a5a4a238560655d394ac75f9701ec41145d9",
  "environment.test": "31fd85d77d811278fb0ab5259af2f5fed9f8e69357a720bbbb289a02c723c247",
};

export function RegistryPublicationPanel({
  signing,
}: {
  signing: ConnectorPackageSigningReceipt;
}) {
  const [policyId, setPolicyId] = useState(
    "connector-registry-publication-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[signing.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Publish this exact signed package to the governed internal registry.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorRegistryPublication });
  const receipt = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="registry-publication-panel" aria-labelledby="registry-publication-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">INTERNAL CUSTODY</p>
          <h3 id="registry-publication-title">Governed registry publication</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {!receipt && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Publication policy ID</span>
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
            <span>Publication purpose</span>
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
              Publication grants no registration, installation, runtime, execution, or deployment
              authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ signing, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <PackageCheck size={16} />
            )}
            Publish signed package
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Registry publication unavailable</h3>
            <p>Signature, package custody, policy, identity separation, or registry binding failed.</p>
          </div>
        </div>
      )}

      {receipt && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{receipt.receipt_id}</strong>
              <code>{receipt.publication.publication_digest}</code>
            </div>
            <span className="state-badge healthy">
              <PackageCheck size={14} />published
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Artifact</span><strong>{receipt.publication.artifact_reference}</strong></div>
            <div><span>Registry profile</span><strong>{receipt.publication.registry_profile_id}</strong></div>
            <div><span>Verifier</span><strong>{receipt.verification.verifier_workload_id}</strong></div>
            <div><span>Publisher</span><strong>{receipt.publication.publisher_workload_id}</strong></div>
          </div>
          <p className="muted-copy">
            The exact signed package is in immutable internal custody. Registration and every runtime
            stage remain separate.
          </p>
        </div>
      )}
    </section>
  );
}
