import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Link2, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorTargetSessionVerification } from "../../api/targetSessionVerifications";
import type { ConnectorRuntimeActivation } from "../../api/runtimeActivations";
import { InvocationAuthorizationPanel } from "./InvocationAuthorizationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "c8cbf384b946a4388058ee0a9dbf3ba71b86a3138f5c8d12f2b09fd342ad797c",
  "environment.test": "83f60c5e5a0d4535b2d24ab0bab34d3716e82419d50bc7daa317acfc1f3c13a7",
};

export function TargetSessionPanel({ activation }: { activation: ConnectorRuntimeActivation }) {
  const [profileId, setProfileId] = useState("connector-target-session-profile.development-synthetic");
  const [profileDigest, setProfileDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-target-session-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[activation.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Verify one bounded read-only target session, validate identity and TLS, then close every ephemeral handle.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorTargetSessionVerification });
  const verification = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) && /^[a-f0-9]{64}$/.test(profileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return <><section className="target-configuration-panel target-session-panel" aria-labelledby="target-session-title">
    <div className="section-heading"><div><p className="eyebrow">BOUNDED READ-ONLY CONNECTIVITY EVIDENCE</p><h3 id="target-session-title">Target session verification</h3></div><Link2 size={24} /></div>
    {!verification && <><div className="mcp-builder-review-fields">
      <label><span>Session profile ID</span><input value={profileId} onChange={(event) => setProfileId(event.target.value)} /></label>
      <label><span>Session profile digest</span><input value={profileDigest} onChange={(event) => setProfileDigest(event.target.value)} spellCheck={false} /></label>
      <label><span>Session policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
      <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
    </div><label><span>Verification purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
      <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Verification permits one bounded read-only connection and immediately closes its session, delivery channel, and secret lease. It grants no reusable session, capability invocation, execution, deployment, scheduling, or infrastructure mutation authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ activation, profileId, profileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Link2 size={16} />}Verify target session</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Target session verification unavailable</h3><p>Runtime lineage, signed network controls, TLS, target identity, read-only privilege, scope, assurance, or separation failed.</p></div></div>}
    {verification && <div className="package-signing-record"><div className="section-heading"><div><strong>Target session verified</strong><code>{verification.verification_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />closed safely</span></div><div className="mcp-builder-facts"><div><span>Target identity</span><strong>verified</strong></div><div><span>TLS</span><strong>verified</strong></div><div><span>Privilege</span><strong>read-only</strong></div><div><span>Session</span><strong>closed</strong></div></div><p className="muted-copy">Connectivity evidence is signed and complete. The target session, delivery channel, and lease are closed; no capability was invoked and no reusable connection remains.</p></div>}
  </section>{verification && <InvocationAuthorizationPanel targetSession={verification} />}</>;
}
