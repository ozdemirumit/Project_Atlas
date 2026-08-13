import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createConnectorInvocationAuthorization } from "../../api/invocationAuthorizations";
import type { ConnectorTargetSessionVerification } from "../../api/targetSessionVerifications";
import { BoundedInvocationPanel } from "./BoundedInvocationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "41ddc05ce6e7946c0e8cd4a9e50f2ab23fbc49b217183a5f2114c2325e84d2e1",
  "environment.test": "b3230d9c7e4ac2adc980513c63b05fcdeda40fda1d8948e471391e4f88d750f1",
};

export function InvocationAuthorizationPanel({
  targetSession,
}: {
  targetSession: ConnectorTargetSessionVerification;
}) {
  const [capabilityId, setCapabilityId] = useState("capability.storage.health.read");
  const [profileId, setProfileId] = useState(
    "connector-invocation-profile.development-read-only",
  );
  const [profileDigest, setProfileDigest] = useState("");
  const [envelopeId, setEnvelopeId] = useState(
    "connector-invocation-input-envelope.development-empty",
  );
  const [envelopeDigest, setEnvelopeDigest] = useState("");
  const [policyId, setPolicyId] = useState(
    "connector-invocation-authorization-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[targetSession.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Authorize one bounded read-only capability invocation without invoking or scheduling it.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createConnectorInvocationAuthorization });
  const authorization = mutation.data?.data;
  const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
  const digest = /^[a-f0-9]{64}$/;
  const canSubmit =
    acknowledged &&
    stableId.test(capabilityId) &&
    stableId.test(profileId) &&
    digest.test(profileDigest) &&
    stableId.test(envelopeId) &&
    digest.test(envelopeDigest) &&
    stableId.test(policyId) &&
    digest.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <><section
      className="target-configuration-panel invocation-authorization-panel"
      aria-labelledby="invocation-authorization-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SINGLE-USE CAPABILITY AUTHORIZATION</p>
          <h3 id="invocation-authorization-title">Invocation authorization</h3>
        </div>
        <ShieldCheck size={24} />
      </div>
      {!authorization && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Capability ID</span>
              <input
                value={capabilityId}
                onChange={(event) => setCapabilityId(event.target.value)}
              />
            </label>
            <label>
              <span>Invocation profile ID</span>
              <input
                value={profileId}
                onChange={(event) => setProfileId(event.target.value)}
              />
            </label>
            <label>
              <span>Invocation profile digest</span>
              <input
                value={profileDigest}
                onChange={(event) => setProfileDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              <span>Input envelope ID</span>
              <input
                value={envelopeId}
                onChange={(event) => setEnvelopeId(event.target.value)}
              />
            </label>
            <label>
              <span>Input envelope digest</span>
              <input
                value={envelopeDigest}
                onChange={(event) => setEnvelopeDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              <span>Authorization policy ID</span>
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
            <span>Authorization purpose</span>
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
              Authorization is short-lived, single-use, non-renewable, and unconsumed. It grants
              no target connection, capability invocation, scheduling, result ingestion,
              execution, deployment, or infrastructure mutation.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                targetSession,
                capabilityId,
                profileId,
                profileDigest,
                envelopeId,
                envelopeDigest,
                policyId,
                policyDigest,
                purpose,
              })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ShieldCheck size={16} />
            )}
            Authorize invocation
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Invocation authorization unavailable</h3>
            <p>
              Session lineage, enabled capability, exact permission, signed authorization-policy
              evidence, requested scope, or separation of duties failed.
            </p>
          </div>
        </div>
      )}
      {authorization && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>Invocation authorized</strong>
              <code>{authorization.authorization_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} />single use
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Class</span>
              <strong>{authorization.capability_class}</strong>
            </div>
            <div>
              <span>Permission</span>
              <strong>verified</strong>
            </div>
            <div>
              <span>State</span>
              <strong>unconsumed</strong>
            </div>
            <div>
              <span>Expires</span>
              <strong>{new Date(authorization.expires_at).toLocaleTimeString()}</strong>
            </div>
          </div>
          <p className="muted-copy">
            The exact capability is eligible for one bounded invocation. No connection was
            opened, no capability was called, and no execution or deployment authority exists.
          </p>
        </div>
      )}
    </section>{authorization && <BoundedInvocationPanel authorization={authorization} />}</>
  );
}
