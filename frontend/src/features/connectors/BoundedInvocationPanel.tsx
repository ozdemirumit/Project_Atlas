import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Play, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createConnectorBoundedInvocation } from "../../api/boundedInvocations";
import type { ConnectorInvocationAuthorization } from "../../api/invocationAuthorizations";
import { InvocationEvidencePanel } from "./InvocationEvidencePanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "e0f70ea92c5b6eeddb1a1818c595d2f6896a4ff585379d789737d0c1413870fa",
  "environment.test": "561de47a52e523602ee7c068c52e25a6278b2dbb20178932991c220590b2d0c5",
};

export function BoundedInvocationPanel({
  authorization,
}: {
  authorization: ConnectorInvocationAuthorization;
}) {
  const [policyId, setPolicyId] = useState(
    "connector-bounded-invocation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[authorization.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Invoke one authorized read-only capability and close every ephemeral resource.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorBoundedInvocation });
  const invocation = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <>
    <section
      className="target-configuration-panel bounded-invocation-panel"
      aria-labelledby="bounded-invocation-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">ATOMIC SINGLE-USE READ</p>
          <h3 id="bounded-invocation-title">Bounded invocation</h3>
        </div>
        <Play size={24} />
      </div>
      {!invocation && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Invocation policy ID</span>
              <input
                value={policyId}
                onChange={(event) => setPolicyId(event.target.value)}
              />
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
            <span>Invocation purpose</span>
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
              The authorization is consumed before the call and cannot be released or retried if
              the outcome is uncertain. Exactly one read-only capability may run; no scheduling,
              evidence ingestion, execution, deployment, or infrastructure mutation is granted.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ authorization, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            Invoke once
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Bounded invocation unavailable</h3>
            <p>
              Authorization, exact permission, policy, signed receipt, or cleanup proof failed.
              An uncertain consumed attempt must not be retried.
            </p>
          </div>
        </div>
      )}
      {invocation && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>Invocation completed</strong>
              <code>{invocation.invocation_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} />closed safely
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Capability</span>
              <strong>invoked once</strong>
            </div>
            <div>
              <span>Result</span>
              <strong>validated</strong>
            </div>
            <div>
              <span>Target</span>
              <strong>disconnected</strong>
            </div>
            <div>
              <span>Evidence</span>
              <strong>not ingested</strong>
            </div>
          </div>
          <p className="muted-copy">
            The authorization was consumed and the exact read-only capability ran once. The result
            is redacted and signed, every ephemeral resource is closed, and no workflow or change
            authority was created.
          </p>
        </div>
      )}
    </section>
    {invocation && <InvocationEvidencePanel invocation={invocation} />}
    </>
  );
}
