import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { ConnectorPackageApprovalRecord } from "../../api/connectors";
import { createConnectorPublisherAttestation } from "../../api/publisherAttestations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "296d294eec2036effbbe1e5a40eb825a0e88dd49b65ddea3bedc97088fe31af0",
  "environment.test": "b32432dc6f0fe56e622d11cf4b94f9d65f2faa8fd40e7db24e35a5b911c12717",
};

export function PublisherAttestationPanel({
  approval,
}: {
  approval: ConnectorPackageApprovalRecord;
}) {
  const [claimId, setClaimId] = useState("connector-publisher-claim.development");
  const [claimDigest, setClaimDigest] = useState("");
  const [policyId, setPolicyId] = useState(
    "connector-publisher-attestation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[approval.request.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Independently verify publisher identity and package provenance evidence.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorPublisherAttestation });
  const report = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(claimId) &&
    /^[a-f0-9]{64}$/.test(claimDigest) &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section className="publisher-attestation-panel" aria-labelledby="publisher-attestation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PUBLISHER GOVERNANCE</p>
          <h3 id="publisher-attestation-title">Publisher identity and provenance</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {!report && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Publisher claim ID</span>
              <input value={claimId} onChange={(event) => setClaimId(event.target.value)} />
            </label>
            <label>
              <span>Publisher claim digest</span>
              <input
                value={claimDigest}
                onChange={(event) => setClaimDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              <span>Attestation policy ID</span>
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
            <span>Verification purpose</span>
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
              Attestation grants no signing, registry, installation, runtime, or execution authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                approval,
                claimId,
                claimDigest,
                policyId,
                policyDigest,
                purpose,
              })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <BadgeCheck size={16} />}
            Verify publisher evidence
          </button>
        </>
      )}

      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Publisher verification unavailable</h3>
            <p>Approval, claim, policy, identity separation, freshness, or binding did not reconcile.</p>
          </div>
        </div>
      )}

      {report && (
        <div className="publisher-attestation-record">
          <div className="section-heading">
            <div>
              <strong>{report.publisher_display_name}</strong>
              <code>{report.canonical_digest}</code>
            </div>
            <span className={`state-badge ${report.publisher_attested ? "healthy" : "warning"}`}>
              <BadgeCheck size={14} />
              {report.outcome}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Publisher</span><strong>{report.publisher_id}</strong></div>
            <div><span>Connector</span><strong>{report.connector_id}</strong></div>
            <div><span>Release</span><strong>{report.release_version}</strong></div>
            <div><span>Verifier</span><strong>{report.verified_by}</strong></div>
          </div>
          <p className="muted-copy">
            Publisher evidence is bound to this package. Signing and every later lifecycle stage remain separate.
          </p>
        </div>
      )}
    </section>
  );
}
