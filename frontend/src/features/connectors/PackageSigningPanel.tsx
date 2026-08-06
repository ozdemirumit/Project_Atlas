import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createConnectorPackageSigningReceipt } from "../../api/packageSigning";
import type { ConnectorPublisherAttestation } from "../../api/publisherAttestations";
import { RegistryPublicationPanel } from "./RegistryPublicationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "aaa767201869bf63768fe7f57941754094b8d981b93c793b55eecb73b3261881",
  "environment.test": "a2706feb2283004ae5b7c89d0f3b4cfc2413b148091521ccfc816bf2d37d2546",
};

export function PackageSigningPanel({
  attestation,
}: {
  attestation: ConnectorPublisherAttestation;
}) {
  const [policyId, setPolicyId] = useState("connector-package-signing-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[attestation.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Sign this exact attested package for later registry governance review.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorPackageSigningReceipt });
  const receipt = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="package-signing-panel" aria-labelledby="package-signing-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PACKAGE INTEGRITY</p>
          <h3 id="package-signing-title">Governed package signature</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {!receipt && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Signing policy ID</span>
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
            <span>Signing purpose</span>
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
              Signing grants no registry, installation, runtime, execution, or deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ attestation, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <KeyRound size={16} />}
            Request package signature
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Package signing unavailable</h3>
            <p>Attestation, policy, identity separation, signer, or signature binding failed.</p>
          </div>
        </div>
      )}

      {receipt && (
        <>
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{receipt.receipt_id}</strong>
              <code>{receipt.signature.signature_digest}</code>
            </div>
            <span className="state-badge healthy"><KeyRound size={14} />signed</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Signer</span><strong>{receipt.signature.signer_workload_id}</strong></div>
            <div><span>Key reference</span><strong>{receipt.signature.key_id}</strong></div>
            <div><span>Algorithm</span><strong>{receipt.signature.algorithm}</strong></div>
            <div><span>Expires</span><strong>{new Date(receipt.signature.expires_at).toLocaleString()}</strong></div>
          </div>
          <p className="muted-copy">
            The exact package is signed. Registry publication and every runtime stage remain separate.
          </p>
        </div>
        {receipt.eligible_for_registry_governance && (
          <RegistryPublicationPanel signing={receipt} />
        )}
        </>
      )}
    </section>
  );
}
