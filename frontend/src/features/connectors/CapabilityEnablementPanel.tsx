import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Power, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorCapabilityEnablement } from "../../api/capabilityEnablements";
import type { ConnectorConfigurationValidation } from "../../api/configurationValidations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "3037f7c378ac3046e92be04e9b71015d63780b6ce961de131e02b13b788da438",
  "environment.test": "888a0063716d7b06062154a9b5b941e99e420691f7b4534c656e771e1e6c23d8",
};

export function CapabilityEnablementPanel({ validation }: { validation: ConnectorConfigurationValidation }) {
  const [profileId, setProfileId] = useState("connector-capability-profile.development-read-only");
  const [profileDigest, setProfileDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-capability-enablement-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[validation.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Enable exact governed C0 and C1 capabilities without secret, runtime, execution, or deployment authority.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorCapabilityEnablement });
  const enablement = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) && /^[a-f0-9]{64}$/.test(profileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return <section className="target-configuration-panel capability-enablement-panel" aria-labelledby="capability-enablement-title">
    <div className="section-heading"><div><p className="eyebrow">SIGNED C0/C1 CAPABILITY PROFILE</p><h3 id="capability-enablement-title">Capability enablement</h3></div><Power size={24} /></div>
    {!enablement && <><div className="mcp-builder-review-fields">
      <label><span>Capability profile ID</span><input value={profileId} onChange={(event) => setProfileId(event.target.value)} /></label>
      <label><span>Capability profile digest</span><input value={profileDigest} onChange={(event) => setProfileDigest(event.target.value)} spellCheck={false} /></label>
      <label><span>Enablement policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
      <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
    </div><label><span>Enablement purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
      <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Enablement selects only signed C0/C1 metadata and grants no secret resolution, connection, runtime trust, execution, deployment, or mutation authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ validation, profileId, profileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Power size={16} />}Enable governed capabilities</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Capability enablement unavailable</h3><p>Validation lineage, signed profile, manifest parity, policy, scope, or separation failed.</p></div></div>}
    {enablement && <div className="package-signing-record"><div className="section-heading"><div><strong>{enablement.capabilities.length} governed capabilities</strong><code>{enablement.enablement_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />enabled</span></div><div className="mcp-builder-facts"><div><span>Classes</span><strong>{[...new Set(enablement.capabilities.map((item) => item.capability_class))].join(", ")}</strong></div><div><span>Runtime trust</span><strong>not granted</strong></div><div><span>Execution</span><strong>not authorized</strong></div><div><span>State</span><strong>{enablement.instance_state}</strong></div></div><p className="muted-copy">Administrative enablement selected only signed manifest-bound capabilities. No connector process, secret, target connection, invocation, runtime trust, deployment, or infrastructure change occurred.</p></div>}
  </section>;
}
