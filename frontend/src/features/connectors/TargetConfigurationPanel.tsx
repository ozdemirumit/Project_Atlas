import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Link2, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { ConnectorInstanceRecord } from "../../api/connectorInstances";
import { createConnectorTargetConfiguration } from "../../api/targetConfigurations";
import { CredentialAssignmentPanel } from "./CredentialAssignmentPanel";

const EVIDENCE: Record<string, { profile: string; policy: string }> = {
  "environment.development": {
    profile: "ac24f2f42d0e4abb3bc1cc88786c703aea9b1402694864b6fba59dedd946d8b1",
    policy: "65f94e1f98af78dd52245ccd1da1f841aeb3ac89511fcea69eb9c594143a4a2d",
  },
  "environment.test": {
    profile: "ca89d6869dcc287db6c90c0139f3e115bd65a5606db94b892ee4323239ef757f",
    policy: "e5415043823d4a68f674259f26a9d673ef169642b76789873746e95ef6eb223d",
  },
};

export function TargetConfigurationPanel({ instance }: { instance: ConnectorInstanceRecord }) {
  const evidence = EVIDENCE[instance.environment_id];
  const [targetProfileId, setTargetProfileId] = useState(
    "connector-target-profile.development-storage",
  );
  const [targetProfileDigest, setTargetProfileDigest] = useState(evidence?.profile ?? "");
  const [policyId, setPolicyId] = useState(
    "connector-target-configuration-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(evidence?.policy ?? "");
  const [purpose, setPurpose] = useState(
    "Bind signed target configuration without credentials, enablement, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorTargetConfiguration });
  const binding = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(targetProfileId) &&
    /^[a-f0-9]{64}$/.test(targetProfileDigest) &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section className="target-configuration-panel" aria-labelledby="target-configuration-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED TARGET PROFILE</p>
          <h3 id="target-configuration-title">Governed target binding</h3>
        </div>
        <Link2 size={24} />
      </div>
      {!binding && (
        <>
          <div className="mcp-builder-review-fields">
            <label><span>Target profile ID</span><input value={targetProfileId} onChange={(event) => setTargetProfileId(event.target.value)} /></label>
            <label><span>Target profile digest</span><input value={targetProfileDigest} onChange={(event) => setTargetProfileDigest(event.target.value)} spellCheck={false} /></label>
            <label><span>Configuration policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
            <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
          </div>
          <label><span>Binding purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
          <label className="approval-check">
            <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
            <span>Binding grants no credential, capability, enablement, runtime, execution, or deployment authority.</span>
          </label>
          <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ instance, targetProfileId, targetProfileDigest, policyId, policyDigest, purpose })}>
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Link2 size={16} />}
            Bind governed target
          </button>
        </>
      )}
      {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Target binding unavailable</h3><p>Instance lineage, target profile, policy, scope, or separation failed.</p></div></div>}
      {binding && (
        <div className="package-signing-record">
          <div className="section-heading"><div><strong>{binding.target_product}</strong><code>{binding.binding_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />configured</span></div>
          <div className="mcp-builder-facts">
            <div><span>Instance</span><strong>{binding.instance_key}</strong></div>
            <div><span>Site</span><strong>{binding.site_id}</strong></div>
            <div><span>Target type</span><strong>{binding.target_type}</strong></div>
            <div><span>State</span><strong>{binding.instance_state}</strong></div>
          </div>
          <p className="muted-copy">The governed target profile is bound. Endpoint, trust, route, credentials, health validation, capabilities, and runtime remain unavailable here.</p>
        </div>
      )}
      {binding && <CredentialAssignmentPanel binding={binding} />}
    </section>
  );
}
