import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, Scale } from "lucide-react";
import { useState } from "react";

import { createProtectedDraftAdjudication } from "../../api/protectedDraftAdjudication";
import type { ProtectedModelInvocationResult } from "../../api/protectedModelInvocation";
import { ProtectedAnswerPresentationPanel } from "./ProtectedAnswerPresentationPanel";

const POLICY_DIGESTS: Record<string, string> = { "environment.development": "49e2f63008b81c15ceecbd952ab33e1eee812f5a1c369a2ddaa78cdc508f0976" };

export function ProtectedDraftAdjudicationPanel({ invocationResult }: { invocationResult: ProtectedModelInvocationResult }) {
  const invocation = invocationResult.invocation;
  const [policyId, setPolicyId] = useState("protected-draft-adjudication-policy.development");
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[invocation.environment_id] ?? "");
  const [draftAcknowledged, setDraftAcknowledged] = useState(false);
  const [presentationAcknowledged, setPresentationAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedDraftAdjudication });
  const result = mutation.data?.data;
  const canSubmit = invocation.model_invoked && invocation.protected_draft_available && !invocation.answer_generated && draftAcknowledged && presentationAcknowledged && authorityAcknowledged && /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) && /^[a-f0-9]{64}$/.test(policyDigest) && !mutation.isPending;

  return <div className="final-resolution-panel" aria-labelledby="draft-adjudication-title">
    <div className="section-heading"><div><p className="eyebrow">INDEPENDENT DRAFT GATE</p><h3 id="draft-adjudication-title">Adjudicate protected model draft</h3></div><Scale size={24} /></div>
    {!result && <><div className="mcp-builder-review-fields"><label><span>Adjudication policy ID</span><input value={policyId} onChange={(event) => setPolicyId(event.target.value)} /></label><label><span>Signed policy digest</span><input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} /></label></div>
      <label className="approval-check"><input type="checkbox" checked={draftAcknowledged} onChange={(event) => setDraftAcknowledged(event.target.checked)} /><span>Model output remains untrusted protected content.</span></label>
      <label className="approval-check"><input type="checkbox" checked={presentationAcknowledged} onChange={(event) => setPresentationAcknowledged(event.target.checked)} /><span>Adjudication does not display or publish draft content.</span></label>
      <label className="approval-check"><input type="checkbox" checked={authorityAcknowledged} onChange={(event) => setAuthorityAcknowledged(event.target.checked)} /><span>Eligibility grants no answer, workflow, tool, or operational authority.</span></label>
      <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ invocationResult, policyId, policyDigest })}>{mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Scale size={16} />}Adjudicate draft</button></>}
    {mutation.isError && <div className="workspace-message error-state" role="alert"><AlertTriangle size={20} /><div><h3>Draft adjudication unavailable</h3><p>Invocation lineage, policy, protected artifacts, and current access must remain valid.</p></div></div>}
    {result && <><div className="correction-record"><strong>{result.manifest.outcome === "adjudication-outcome.eligible" ? "Draft eligible for later presentation review" : "Draft rejected by adjudication"}</strong><code>{result.adjudication.adjudication_id}</code><p className="muted-copy">{result.manifest.check_count} deterministic checks, {result.manifest.citation_count} citation references, and {result.manifest.unknown_count} explicit unknowns.</p><p className="muted-copy">Draft content remains protected. No final answer, model retry, tool, workflow, or infrastructure action ran.</p></div>{result.manifest.outcome === "adjudication-outcome.eligible" && <ProtectedAnswerPresentationPanel adjudicationResult={result} />}</>}
  </div>;
}
