import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Braces, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createProtectedModelContext } from "../../api/modelContextAssembly";
import type { OperationalKnowledgeRetrievalResult } from "../../api/protectedRetrieval";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "0c9ee239e03dfc1b09a7897ffe61ee116616a26b26f319d5503c390061255a29",
};

export function ModelContextAssemblyPanel({
  retrievalResult,
}: {
  retrievalResult: OperationalKnowledgeRetrievalResult;
}) {
  const retrieval = retrievalResult.retrieval;
  const [policyId, setPolicyId] = useState("protected-model-context-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[retrieval.environment_id] ?? "",
  );
  const [objective, setObjective] = useState(
    "Analyze the retrieved controller-warning evidence and preserve citations, conflicts, and unknowns.",
  );
  const [intentAcknowledged, setIntentAcknowledged] = useState(false);
  const [citationsAcknowledged, setCitationsAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedModelContext });
  const result = mutation.data?.data;
  const canSubmit =
    retrieval.knowledge_retrieved &&
    !retrieval.model_context_available &&
    intentAcknowledged &&
    citationsAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    objective.trim().length >= 3 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="model-context-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED AI BOUNDARY</p>
          <h3 id="model-context-title">Assemble governed model context</h3>
        </div>
        <Braces size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Context policy ID</span>
              <input value={policyId} onChange={(event) => setPolicyId(event.target.value)} />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input
                value={policyDigest}
                onChange={(event) => setPolicyDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
          </div>
          <label>
            <span>Analysis objective</span>
            <textarea
              value={objective}
              rows={3}
              maxLength={4000}
              onChange={(event) => setObjective(event.target.value)}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={intentAcknowledged}
              onChange={(event) => setIntentAcknowledged(event.target.checked)}
            />
            <span>User intent and retrieved text remain untrusted data.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={citationsAcknowledged}
              onChange={(event) => setCitationsAcknowledged(event.target.checked)}
            />
            <span>Evidence units keep immutable citation and safety boundaries.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Assembly does not invoke a model, tool, workflow, or operation.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ retrievalResult, policyId, policyDigest, objective })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Braces size={16} />}
            Assemble context
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Context assembly unavailable</h3>
            <p>Retrieval lineage, current access, policy, citations, and budget must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>Protected model context assembled</strong>
          <code>{result.context.context_id}</code>
          <p className="muted-copy">
            {result.manifest.included_evidence_count} citation-bound evidence unit,{" "}
            {result.manifest.estimated_token_count} of {result.manifest.maximum_estimated_tokens}{" "}
            estimated tokens.
          </p>
          <p className="muted-copy">
            The context body remains protected. No model, tool, workflow, deployment, or
            infrastructure action ran.
          </p>
        </div>
      )}
    </div>
  );
}
