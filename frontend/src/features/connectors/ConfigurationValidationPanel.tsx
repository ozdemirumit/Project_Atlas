import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createConnectorConfigurationValidation } from "../../api/configurationValidations";
import type { ConnectorCredentialAssignment } from "../../api/credentialAssignments";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development": "5c683a88f96dd8597098811fb868453e1566767f92ffe940ea2f05cb2ef02aab",
  "environment.test": "87f2aa7ef9bfea98d67dcfda63dc5714539eea19a63d1418358b629e5b58935c",
};

export function ConfigurationValidationPanel({ assignment }: { assignment: ConnectorCredentialAssignment }) {
  const [evidenceId, setEvidenceId] = useState("connector-configuration-evidence.development-read-only-probe");
  const [evidenceDigest, setEvidenceDigest] = useState("");
  const [policyId, setPolicyId] = useState("connector-configuration-validation-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[assignment.environment_id] ?? "");
  const [purpose, setPurpose] = useState("Verify signed bounded configuration evidence without secret, network, enablement, or runtime authority.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorConfigurationValidation });
  const validation = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(evidenceId) && /^[a-f0-9]{64}$/.test(evidenceDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return (
    <section className="target-configuration-panel configuration-validation-panel" aria-labelledby="configuration-validation-title">
      <div className="section-heading"><div><p className="eyebrow">SIGNED READ-ONLY PROBE EVIDENCE</p><h3 id="configuration-validation-title">Configuration validation</h3></div><ShieldCheck size={24} /></div>
      {!validation && <>
        <div className="mcp-builder-review-fields">
          <label><span>Evidence ID</span><input value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} /></label>
          <label><span>Evidence digest</span><input value={evidenceDigest} onChange={(event) => setEvidenceDigest(event.target.value)} spellCheck={false} /></label>
          <label><span>Validation policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
          <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
        </div>
        <label><span>Validation purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
        <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Validation grants no target access, secret resolution, capability, enablement, runtime, execution, deployment, or mutation authority.</span></label>
        <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ assignment, evidenceId, evidenceDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}Verify evidence</button>
      </>}
      {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Configuration validation unavailable</h3><p>Assignment lineage, signed evidence, policy, freshness, scope, or separation failed.</p></div></div>}
      {validation && <div className="package-signing-record"><div className="section-heading"><div><strong>{validation.configuration_result}</strong><code>{validation.validation_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />verified</span></div><div className="mcp-builder-facts"><div><span>Connectivity</span><strong>{validation.connectivity_result}</strong></div><div><span>TLS</span><strong>{validation.tls_result}</strong></div><div><span>Authorization</span><strong>{validation.authorization_result}</strong></div><div><span>State</span><strong>{validation.instance_state}</strong></div></div><p className="muted-copy">Only signed bounded classifications were verified. Target coordinates, secret material, raw probe output, connector enablement, capabilities, and runtime remain unavailable here.</p></div>}
    </section>
  );
}
