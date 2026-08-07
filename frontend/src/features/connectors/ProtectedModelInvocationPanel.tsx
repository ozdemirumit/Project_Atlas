import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BrainCircuit, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { ProtectedModelContextResult } from "../../api/modelContextAssembly";
import { createProtectedModelInvocation } from "../../api/protectedModelInvocation";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "1258f01a19005053a0725277c4f50c924944bd77fab186f1c475d9d9edaf2977",
};

export function ProtectedModelInvocationPanel({
  contextResult,
}: {
  contextResult: ProtectedModelContextResult;
}) {
  const context = contextResult.context;
  const [policyId, setPolicyId] = useState("protected-model-invocation-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[context.environment_id] ?? "",
  );
  const [draftAcknowledged, setDraftAcknowledged] = useState(false);
  const [validationAcknowledged, setValidationAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedModelInvocation });
  const result = mutation.data?.data;
  const canSubmit =
    context.model_context_available &&
    !context.model_invoked &&
    draftAcknowledged &&
    validationAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="model-invocation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">GOVERNED MODEL BOUNDARY</p>
          <h3 id="model-invocation-title">Invoke approved local model</h3>
        </div>
        <BrainCircuit size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Invocation policy ID</span>
              <input value={policyId} onChange={(event) => setPolicyId(event.target.value)} />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} />
            </label>
          </div>
          <label className="approval-check">
            <input type="checkbox" checked={draftAcknowledged} onChange={(event) => setDraftAcknowledged(event.target.checked)} />
            <span>Model output remains an untrusted protected draft.</span>
          </label>
          <label className="approval-check">
            <input type="checkbox" checked={validationAcknowledged} onChange={(event) => setValidationAcknowledged(event.target.checked)} />
            <span>Citations and unknowns require independent validation.</span>
          </label>
          <label className="approval-check">
            <input type="checkbox" checked={authorityAcknowledged} onChange={(event) => setAuthorityAcknowledged(event.target.checked)} />
            <span>Invocation grants no answer, tool, workflow, or operational authority.</span>
          </label>
          <button className="primary-button" type="button" disabled={!canSubmit} onClick={() => mutation.mutate({ contextResult, policyId, policyDigest })}>
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <BrainCircuit size={16} />}
            Invoke model
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div><h3>Model invocation unavailable</h3><p>Context, access, endpoint evaluation, policy, and protected vault must remain valid.</p></div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>Protected model invocation completed</strong>
          <code>{result.invocation.invocation_id}</code>
          <p className="muted-copy">{result.manifest.model_id} via {result.manifest.endpoint_profile_id}. {result.manifest.input_tokens} input and {result.manifest.output_tokens} output tokens.</p>
          <p className="muted-copy">{result.manifest.citation_count} validated citation reference and {result.manifest.unknown_count} explicit unknowns. Draft content remains protected and no final answer or operation was authorized.</p>
        </div>
      )}
    </div>
  );
}
