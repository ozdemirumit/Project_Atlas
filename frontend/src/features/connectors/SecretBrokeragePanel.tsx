import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, KeyRound, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { ConnectorRuntimeTrustGrant } from "../../api/runtimeTrustGrants";
import { createConnectorSecretBrokerageAuthorization } from "../../api/secretBrokerageAuthorizations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "be0056e233010d40f427b23cd80f6089e52264adf8a503d39c0d130fa85ced59",
  "environment.test": "aa196713871b6e9574c083cce4177fe057c832e9ab3c8ab9fdce4741c5306e8d",
};

export function SecretBrokeragePanel({ runtimeTrust }: { runtimeTrust: ConnectorRuntimeTrustGrant }) {
  const [profileId, setProfileId] = useState("connector-secret-brokerage-profile.development-memory-only");
  const [profileDigest, setProfileDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-secret-brokerage-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[runtimeTrust.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Authorize exact future memory-only secret brokerage without issuing a lease, resolving credentials, starting runtime, or connecting to a target.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorSecretBrokerageAuthorization });
  const authorization = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) && /^[a-f0-9]{64}$/.test(profileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return <section className="target-configuration-panel secret-brokerage-panel" aria-labelledby="secret-brokerage-title">
    <div className="section-heading"><div><p className="eyebrow">SIGNED MEMORY-ONLY BROKERAGE BOUNDARY</p><h3 id="secret-brokerage-title">Secret brokerage</h3></div><KeyRound size={24} /></div>
    {!authorization && <><div className="mcp-builder-review-fields">
      <label><span>Brokerage profile ID</span><input value={profileId} onChange={(event) => setProfileId(event.target.value)} /></label>
      <label><span>Brokerage profile digest</span><input value={profileDigest} onChange={(event) => setProfileDigest(event.target.value)} spellCheck={false} /></label>
      <label><span>Brokerage policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
      <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
    </div><label><span>Authorization purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
      <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Authorization grants no lease issuance, secret resolution, process start, package load, target connection, invocation, execution, deployment, or mutation authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ runtimeTrust, profileId, profileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <KeyRound size={16} />}Authorize brokerage</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Secret brokerage unavailable</h3><p>Runtime lineage, credential posture, signed delivery controls, scope, hardware-backed assurance, or separation failed.</p></div></div>}
    {authorization && <div className="package-signing-record"><div className="section-heading"><div><strong>Future brokerage governed</strong><code>{authorization.authorization_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />authorized</span></div><div className="mcp-builder-facts"><div><span>Lease</span><strong>not issued</strong></div><div><span>Secrets</span><strong>not resolved</strong></div><div><span>Runtime</span><strong>not started</strong></div><div><span>State</span><strong>{authorization.instance_state}</strong></div></div><p className="muted-copy">A future isolated runtime may request a fresh single-use lease only after independent revalidation. No secret, lease handle, process, package, target session, invocation, deployment, or infrastructure change exists.</p></div>}
  </section>;
}
