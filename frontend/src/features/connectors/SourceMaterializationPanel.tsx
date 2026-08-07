import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileLock2, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalKnowledgePublicationPreparation } from "../../api/publicationPreparations";
import { createOperationalKnowledgeSourceMaterialization } from "../../api/sourceMaterializations";
import { DeterministicChunkingPanel } from "./DeterministicChunkingPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "3f3da2e148239e47fb3039374eac428461225a05a5bb23a96a1e2389063978ab",
};

export function SourceMaterializationPanel({
  preparation,
}: {
  preparation: OperationalKnowledgePublicationPreparation;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-source-materialization-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[preparation.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Materialize the exact approved source inside the protected knowledge boundary.",
  );
  const [sourceAcknowledged, setSourceAcknowledged] = useState(false);
  const [boundaryAcknowledged, setBoundaryAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeSourceMaterialization });
  const materialization = mutation.data?.data;
  const canSubmit =
    preparation.publication_prepared &&
    sourceAcknowledged &&
    boundaryAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="source-materialization-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED SOURCE</p>
          <h3 id="source-materialization-title">Materialize approved source</h3>
        </div>
        <FileLock2 size={24} />
      </div>
      {!materialization && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Materialization policy ID</span>
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
            <span>Materialization purpose</span>
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
              checked={sourceAcknowledged}
              onChange={(event) => setSourceAcknowledged(event.target.checked)}
            />
            <span>The exact approved source and governance bindings are immutable.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={boundaryAcknowledged}
              onChange={(event) => setBoundaryAcknowledged(event.target.checked)}
            />
            <span>Protected content remains inside the trusted materialization boundary.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No chunking, indexing, retrieval, workflow, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ preparation, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileLock2 size={16} />}
            Materialize protected source
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Source materialization unavailable</h3>
            <p>Preparation lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {materialization && (
        <>
          <div className="correction-record">
            <strong>Protected source materialized</strong>
            <code>{materialization.materialization_id}</code>
            <p className="muted-copy">
              Integrity and governance are bound. No content, coordinate, chunk, vector, or index was exposed.
            </p>
          </div>
          <DeterministicChunkingPanel materialization={materialization} />
        </>
      )}
    </div>
  );
}
