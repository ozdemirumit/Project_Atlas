import { useMutation } from "@tanstack/react-query";
import { Activity, AlertTriangle, BadgeCheck, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorRuntimeActivation } from "../../api/runtimeActivations";
import type { ConnectorSecretBrokerageAuthorization } from "../../api/secretBrokerageAuthorizations";
import { TargetSessionPanel } from "./TargetSessionPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "08fa8725d665a3f670d665385c90af861e1eedb7b1898b693cc2b265fdbca337",
  "environment.test": "77e7877e211369c21316fc4127f40ee3e834b9f879b2e468379098a689ac7071",
};

export function RuntimeActivationPanel({ brokerage }: { brokerage: ConnectorSecretBrokerageAuthorization }) {
  const [profileId, setProfileId] = useState("connector-runtime-activation-profile.development-synthetic");
  const [profileDigest, setProfileDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-runtime-activation-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[brokerage.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Activate the exact isolated connector runtime and verify local health without target connection or capability invocation.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorRuntimeActivation });
  const activation = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) && /^[a-f0-9]{64}$/.test(profileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return <><section className="target-configuration-panel runtime-activation-panel" aria-labelledby="runtime-activation-title">
    <div className="section-heading"><div><p className="eyebrow">SIGNED ISOLATED ACTIVATION BOUNDARY</p><h3 id="runtime-activation-title">Runtime activation</h3></div><Activity size={24} /></div>
    {!activation && <><div className="mcp-builder-review-fields">
      <label><span>Activation profile ID</span><input value={profileId} onChange={(event) => setProfileId(event.target.value)} /></label>
      <label><span>Activation profile digest</span><input value={profileDigest} onChange={(event) => setProfileDigest(event.target.value)} spellCheck={false} /></label>
      <label><span>Activation policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
      <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
    </div><label><span>Activation purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
      <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Activation starts only the exact isolated runtime and local health probes. It grants no target connection, capability invocation, execution, deployment, or infrastructure mutation authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ brokerage, profileId, profileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Activity size={16} />}Activate runtime</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Runtime activation unavailable</h3><p>Brokerage lineage, signed runtime controls, health evidence, scope, hardware-backed assurance, or separation failed.</p></div></div>}
    {activation && <div className="package-signing-record"><div className="section-heading"><div><strong>Runtime healthy</strong><code>{activation.activation_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />healthy</span></div><div className="mcp-builder-facts"><div><span>Runner</span><strong>started</strong></div><div><span>Package</span><strong>loaded</strong></div><div><span>Lease</span><strong>closed</strong></div><div><span>Target</span><strong>not connected</strong></div></div><p className="muted-copy">Signed local health evidence is complete and the delivery channel is closed. No target session, capability invocation, deployment, or infrastructure change is authorized.</p></div>}
  </section>{activation && <TargetSessionPanel activation={activation} />}</>;
}
