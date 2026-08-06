import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { ConnectorCapabilityEnablement } from "../../api/capabilityEnablements";
import { createConnectorRuntimeTrustGrant } from "../../api/runtimeTrustGrants";
import { SecretBrokeragePanel } from "./SecretBrokeragePanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "42157b3d8b23514b4f754a2f0f9f507122c6718289a2ae8986e226287d718d33",
  "environment.test": "f6230e143452ea69647a9e9a5dae7c464dd7614b800b56efa57494b21b87e316",
};

export function RuntimeTrustPanel({ enablement }: { enablement: ConnectorCapabilityEnablement }) {
  const [profileId, setProfileId] = useState("connector-runtime-trust-profile.development-isolated-read-only");
  const [profileDigest, setProfileDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-runtime-trust-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[enablement.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Bind the exact enabled connector to an isolated runtime without starting it or granting secret, target, execution, or deployment authority.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorRuntimeTrustGrant });
  const grant = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) && /^[a-f0-9]{64}$/.test(profileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return <section className="target-configuration-panel runtime-trust-panel" aria-labelledby="runtime-trust-title">
    <div className="section-heading"><div><p className="eyebrow">SIGNED ISOLATED RUNTIME BOUNDARY</p><h3 id="runtime-trust-title">Runtime trust</h3></div><ShieldCheck size={24} /></div>
    {!grant && <><div className="mcp-builder-review-fields">
      <label><span>Runtime profile ID</span><input value={profileId} onChange={(event) => setProfileId(event.target.value)} /></label>
      <label><span>Runtime profile digest</span><input value={profileDigest} onChange={(event) => setProfileDigest(event.target.value)} spellCheck={false} /></label>
      <label><span>Trust policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
      <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
    </div><label><span>Trust purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
      <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Trust binds only the signed isolated runtime boundary and grants no process start, package load, secret resolution, target connection, invocation, execution, deployment, or mutation authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ enablement, profileId, profileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}Grant runtime trust</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Runtime trust unavailable</h3><p>Enablement lineage, signed runtime controls, trust policy, freshness, scope, hardware-backed assurance, or separation failed.</p></div></div>}
    {grant && <div className="package-signing-record"><div className="section-heading"><div><strong>Isolated boundary trusted</strong><code>{grant.grant_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />trusted</span></div><div className="mcp-builder-facts"><div><span>Runner</span><strong>not started</strong></div><div><span>Secrets</span><strong>not resolved</strong></div><div><span>Target</span><strong>not connected</strong></div><div><span>State</span><strong>{grant.instance_state}</strong></div></div><p className="muted-copy">The signed runtime boundary is bound and eligible for later secret brokerage. No connector process, package, credential, target connection, capability invocation, execution, deployment, or infrastructure change occurred.</p></div>}
    {grant && <SecretBrokeragePanel runtimeTrust={grant} />}
  </section>;
}
