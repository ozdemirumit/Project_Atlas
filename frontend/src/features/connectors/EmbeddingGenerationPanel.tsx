import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BrainCircuit, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalKnowledgeChunkSet } from "../../api/deterministicChunking";
import { createOperationalKnowledgeEmbeddingSet } from "../../api/embeddingGeneration";
import { IndexStagingValidationPanel } from "./IndexStagingValidationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "26dcf51c4e6e0df81b7b4ef8603c74b8c91c50c0a492e303caee3d47f156f470",
};

export function EmbeddingGenerationPanel({
  chunkSet,
}: {
  chunkSet: OperationalKnowledgeChunkSet;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-embedding-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[chunkSet.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Create the governed local embedding set for approved operational knowledge.",
  );
  const [boundaryAcknowledged, setBoundaryAcknowledged] = useState(false);
  const [profileAcknowledged, setProfileAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeEmbeddingSet });
  const embeddingSet = mutation.data?.data;
  const canSubmit =
    chunkSet.chunks_created &&
    !chunkSet.embeddings_created &&
    boundaryAcknowledged &&
    profileAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="embedding-generation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">LOCAL MODEL SPACE</p>
          <h3 id="embedding-generation-title">Generate protected embeddings</h3>
        </div>
        <BrainCircuit size={24} />
      </div>
      {!embeddingSet && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Embedding policy ID</span>
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
            <span>Embedding purpose</span>
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
              checked={boundaryAcknowledged}
              onChange={(event) => setBoundaryAcknowledged(event.target.checked)}
            />
            <span>Protected chunks remain inside the trusted local embedding boundary.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={profileAcknowledged}
              onChange={(event) => setProfileAcknowledged(event.target.checked)}
            />
            <span>The approved model and tokenizer profile is immutable.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No indexing, retrieval, workflow, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ chunkSet, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <BrainCircuit size={16} />
            )}
            Generate protected embeddings
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Embedding generation unavailable</h3>
            <p>Chunk lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {embeddingSet && (
        <>
          <div className="correction-record">
            <strong>Protected embedding set created</strong>
            <code>{embeddingSet.embedding_set_id}</code>
            <p className="muted-copy">
              {embeddingSet.embedding_count} embeddings use a verified {embeddingSet.vector_dimension}
              -dimension local model space. No chunk content, vector value, endpoint, or index was
              exposed.
            </p>
          </div>
          <IndexStagingValidationPanel embeddingSet={embeddingSet} />
        </>
      )}
    </div>
  );
}
