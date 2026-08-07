import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BookOpenCheck, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalKnowledgeIndexStage } from "../../api/indexStagingValidation";
import { createOperationalKnowledgeRetrievalPublication } from "../../api/retrievalIndexPublication";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "12bce34b1d52617aebc841a088cd8ed3adf517a0bfefc44aa5c8885962000234",
};

export function RetrievalIndexPublicationPanel({
  indexStage,
}: {
  indexStage: OperationalKnowledgeIndexStage;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-retrieval-publication-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[indexStage.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Atomically publish the governed protected retrieval index for authorized use.",
  );
  const [visibilityAcknowledged, setVisibilityAcknowledged] = useState(false);
  const [disclosureAcknowledged, setDisclosureAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeRetrievalPublication });
  const publication = mutation.data?.data;
  const canSubmit =
    indexStage.index_validated &&
    !indexStage.retrieval_published &&
    visibilityAcknowledged &&
    disclosureAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="retrieval-publication-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">ATOMIC RETRIEVAL VISIBILITY</p>
          <h3 id="retrieval-publication-title">Publish protected retrieval index</h3>
        </div>
        <BookOpenCheck size={24} />
      </div>
      {!publication && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Publication policy ID</span>
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
            <span>Publication purpose</span>
            <textarea
              value={purpose}
              rows={3}
              maxLength={1000}
              onChange={(event) => setPurpose(event.target.value)}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={visibilityAcknowledged}
              onChange={(event) => setVisibilityAcknowledged(event.target.checked)}
            />
            <span>Publication creates only policy-filtered retrieval visibility.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={disclosureAcknowledged}
              onChange={(event) => setDisclosureAcknowledged(event.target.checked)}
            />
            <span>No vector-store route, alias, point, payload, filter, or vector is exposed.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No model context, workflow, deployment, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ indexStage, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <BookOpenCheck size={16} />
            )}
            Publish retrieval index
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Retrieval publication unavailable</h3>
            <p>Validated lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {publication && (
        <div className="correction-record">
          <strong>Protected retrieval index published</strong>
          <code>{publication.publication_id}</code>
          <p className="muted-copy">
            Atomic policy-filtered visibility is active. No content, vector, route identity, query
            result, model context, workflow, or operation authority was exposed.
          </p>
        </div>
      )}
    </div>
  );
}
