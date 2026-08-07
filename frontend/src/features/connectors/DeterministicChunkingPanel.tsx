import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Boxes, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeChunkSet } from "../../api/deterministicChunking";
import type { OperationalKnowledgeSourceMaterialization } from "../../api/sourceMaterializations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "7750a2e2ab5c0c50a651ee86002657ea83a51f6ff9937e9b9e5205854568255c",
};

export function DeterministicChunkingPanel({
  materialization,
}: {
  materialization: OperationalKnowledgeSourceMaterialization;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-chunking-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[materialization.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Create the deterministic protected chunk set for approved operational knowledge.",
  );
  const [boundaryAcknowledged, setBoundaryAcknowledged] = useState(false);
  const [profileAcknowledged, setProfileAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeChunkSet });
  const chunkSet = mutation.data?.data;
  const canSubmit =
    materialization.source_materialized &&
    !materialization.chunks_created &&
    boundaryAcknowledged &&
    profileAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="deterministic-chunking-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED SEGMENTATION</p>
          <h3 id="deterministic-chunking-title">Create deterministic chunk set</h3>
        </div>
        <Boxes size={24} />
      </div>
      {!chunkSet && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Chunking policy ID</span>
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
            <span>Chunking purpose</span>
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
            <span>Protected content remains inside the trusted chunking boundary.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={profileAcknowledged}
              onChange={(event) => setProfileAcknowledged(event.target.checked)}
            />
            <span>The preparation-bound chunking profile is immutable.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No embedding, indexing, retrieval, workflow, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ materialization, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Boxes size={16} />}
            Create protected chunk set
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Deterministic chunking unavailable</h3>
            <p>Materialization lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {chunkSet && (
        <div className="correction-record">
          <strong>Deterministic chunk set created</strong>
          <code>{chunkSet.chunk_set_id}</code>
          <p className="muted-copy">
            {chunkSet.chunk_count} immutable chunks are bound by signed manifests. No content,
            coordinate, embedding, vector, or index was exposed.
          </p>
        </div>
      )}
    </div>
  );
}
