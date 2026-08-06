import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Archive, BadgeCheck, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { ConnectorBoundedInvocation } from "../../api/boundedInvocations";
import { createConnectorInvocationEvidence } from "../../api/invocationEvidence";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "f06fd15735d2a77887160bbed9ea603da8e2a449f65fcc3431ce57fb20c32b6f",
  "environment.test": "a3c3d7c01400e96943d08a4a42092a1e2ee162c27bf0f2767a6149a1a85e194f",
};

export function InvocationEvidencePanel({
  invocation,
}: {
  invocation: ConnectorBoundedInvocation;
}) {
  const [policyId, setPolicyId] = useState(
    "connector-invocation-evidence-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[invocation.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Preserve the exact governed connector observations as immutable evidence.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorInvocationEvidence });
  const evidence = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section
      className="target-configuration-panel invocation-evidence-panel"
      aria-labelledby="invocation-evidence-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">IMMUTABLE OPERATIONAL EVIDENCE</p>
          <h3 id="invocation-evidence-title">Evidence preservation</h3>
        </div>
        <Archive size={24} />
      </div>
      {!evidence && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Ingestion policy ID</span>
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
            <span>Preservation purpose</span>
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              rows={3}
              maxLength={1000}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              Ingestion is one-way. It preserves only the exact governed result and does not create
              approved knowledge, publish retrieval content, expose model context, continue a
              workflow, or grant operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ invocation, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Archive size={16} />}
            Preserve evidence
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Evidence preservation unavailable</h3>
            <p>
              Source lineage, governance policy, immutable storage proof, or cleanup validation
              failed. An uncertain claimed attempt is not retried automatically.
            </p>
          </div>
        </div>
      )}
      {evidence && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>Evidence preserved</strong>
              <code>{evidence.evidence_package_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} />immutable
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Items</span>
              <strong>{evidence.evidence_item_count}</strong>
            </div>
            <div>
              <span>Classification</span>
              <strong>{evidence.classification.replace("classification.", "")}</strong>
            </div>
            <div>
              <span>Encryption</span>
              <strong>at rest</strong>
            </div>
            <div>
              <span>Retrieval</span>
              <strong>not published</strong>
            </div>
          </div>
          <p className="muted-copy">
            The exact redacted result is preserved under fixed access and retention policy. It is
            not approved knowledge, model context, a workflow continuation, or change authority.
          </p>
        </div>
      )}
    </section>
  );
}
