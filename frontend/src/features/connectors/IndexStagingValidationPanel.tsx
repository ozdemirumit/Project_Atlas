import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Database, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalKnowledgeEmbeddingSet } from "../../api/embeddingGeneration";
import { createOperationalKnowledgeIndexStage } from "../../api/indexStagingValidation";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "27d5da7c0da2b3def91285b2714095ebc6f1e2fbc8b968254bc023fc2c6dc733",
};

export function IndexStagingValidationPanel({
  embeddingSet,
}: {
  embeddingSet: OperationalKnowledgeEmbeddingSet;
}) {
  const [policyId, setPolicyId] = useState("operational-knowledge-index-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[embeddingSet.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Stage and validate the governed inactive knowledge retrieval projection.",
  );
  const [boundaryAcknowledged, setBoundaryAcknowledged] = useState(false);
  const [inactiveAcknowledged, setInactiveAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeIndexStage });
  const indexStage = mutation.data?.data;
  const canSubmit =
    embeddingSet.embeddings_created &&
    !embeddingSet.index_staged &&
    boundaryAcknowledged &&
    inactiveAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="index-staging-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">INACTIVE PROJECTION</p>
          <h3 id="index-staging-title">Stage and validate retrieval index</h3>
        </div>
        <Database size={24} />
      </div>
      {!indexStage && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Index policy ID</span>
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
            <span>Staging purpose</span>
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
            <span>Protected vectors remain inside the trusted local index boundary.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={inactiveAcknowledged}
              onChange={(event) => setInactiveAcknowledged(event.target.checked)}
            />
            <span>The validated projection remains sealed and inactive.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No publication, retrieval, workflow, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ embeddingSet, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Database size={16} />}
            Stage and validate index
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Index staging unavailable</h3>
            <p>Embedding lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {indexStage && (
        <div className="correction-record">
          <strong>Inactive retrieval projection validated</strong>
          <code>{indexStage.index_staging_id}</code>
          <p className="muted-copy">
            {indexStage.staged_point_count} protected points were reconciled and sealed. No content,
            vector, collection, point identity, query result, or retrieval authority was exposed.
          </p>
        </div>
      )}
    </div>
  );
}
