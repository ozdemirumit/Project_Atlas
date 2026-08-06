import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, KeyRound, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorCredentialAssignment } from "../../api/credentialAssignments";
import type { ConnectorTargetConfigurationBinding } from "../../api/targetConfigurations";

const EVIDENCE: Record<string, { profile: string; policy: string }> = {
  "environment.development": {
    profile: "0279f90b6ac015d81a154b723ddbd9bc687b6fccdf286b50cb99ca71e66e1867",
    policy: "a9ba1da0bb85635e926d69e839c38952153d4349b9e456921101f3b0799f2cca",
  },
  "environment.test": {
    profile: "9e56a097667e7ff0259cf8c52587a01537f812edda0bd00af3c2be7585ca25fc",
    policy: "4781f6fc663d419ac0d82868139c31e9f95654fd2a0ea5931f9cca8c4b078e4a",
  },
};

export function CredentialAssignmentPanel({ binding }: { binding: ConnectorTargetConfigurationBinding }) {
  const evidence = EVIDENCE[binding.environment_id];
  const [credentialProfileId, setCredentialProfileId] = useState("connector-credential-profile.development-storage-reader");
  const [credentialProfileDigest, setCredentialProfileDigest] = useState(evidence?.profile ?? "");
  const [policyId, setPolicyId] = useState("connector-credential-assignment-policy.development");
  const [policyDigest, setPolicyDigest] = useState(evidence?.policy ?? "");
  const [purpose, setPurpose] = useState("Assign governed credential metadata without secret, enablement, or runtime access.");
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorCredentialAssignment });
  const assignment = mutation.data?.data;
  const canSubmit = acknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(credentialProfileId) && /^[a-f0-9]{64}$/.test(credentialProfileDigest) && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && purpose.trim().length >= 20 && !mutation.isPending;

  return (
    <section className="target-configuration-panel credential-assignment-panel" aria-labelledby="credential-assignment-title">
      <div className="section-heading"><div><p className="eyebrow">SIGNED CREDENTIAL PROFILE</p><h3 id="credential-assignment-title">Governed credential assignment</h3></div><KeyRound size={24} /></div>
      {!assignment && <>
        <div className="mcp-builder-review-fields">
          <label><span>Credential profile ID</span><input value={credentialProfileId} onChange={(event) => setCredentialProfileId(event.target.value)} /></label>
          <label><span>Credential profile digest</span><input value={credentialProfileDigest} onChange={(event) => setCredentialProfileDigest(event.target.value)} spellCheck={false} /></label>
          <label><span>Assignment policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label>
          <label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label>
        </div>
        <label><span>Assignment purpose</span><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} maxLength={1000} /></label>
        <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Assignment grants no secret access, credential resolution, capability, enablement, runtime, execution, or deployment authority.</span></label>
        <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ binding, credentialProfileId, credentialProfileDigest, policyId, policyDigest, purpose })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <KeyRound size={16} />}Assign credential profile</button>
      </>}
      {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Credential assignment unavailable</h3><p>Target lineage, credential profile, policy, scope, rotation, or separation failed.</p></div></div>}
      {assignment && <div className="package-signing-record"><div className="section-heading"><div><strong>{assignment.credential_class}</strong><code>{assignment.assignment_id}</code></div><span className="state-badge neutral"><BadgeCheck size={14} />assigned</span></div><div className="mcp-builder-facts"><div><span>Authentication</span><strong>{assignment.authentication_method}</strong></div><div><span>Privilege</span><strong>{assignment.privilege_class}</strong></div><div><span>Rotation</span><strong>{assignment.rotation_state}</strong></div><div><span>State</span><strong>{assignment.instance_state}</strong></div></div><p className="muted-copy">Only governed credential metadata is assigned. Secret reference internals, values, credential resolution, enablement, health validation, capabilities, and runtime remain unavailable here.</p></div>}
    </section>
  );
}
