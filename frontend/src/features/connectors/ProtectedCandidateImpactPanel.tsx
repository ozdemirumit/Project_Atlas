import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Network, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createProtectedCandidateImpact,
  type ProtectedCandidateImpactResult,
} from "../../api/protectedCandidateImpacts";
import type { ProtectedRecommendationCandidateResult } from "../../api/protectedRecommendationCandidates";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "82516d0dd62515f9803795cd71bbf7003517edfd4b39ac94e32b0b36ba0da787",
};

export function ProtectedCandidateImpactPanel({
  candidateResult,
}: {
  candidateResult: ProtectedRecommendationCandidateResult;
}) {
  const candidateSet = candidateResult.candidate_set;
  const [policyId, setPolicyId] = useState("protected-candidate-impact-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[candidateSet.environment_id] ?? "",
  );
  const [reachabilityAcknowledged, setReachabilityAcknowledged] = useState(false);
  const [provisionalAcknowledged, setProvisionalAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedCandidateImpact });
  const result: ProtectedCandidateImpactResult | undefined = mutation.data?.data;
  const canSubmit =
    candidateSet.recommendation_candidates_generated &&
    !candidateSet.service_impact_analyzed &&
    reachabilityAcknowledged &&
    provisionalAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="candidate-impact-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED GRAPH ENRICHMENT</p>
          <h3 id="candidate-impact-title">Analyze service reachability</h3>
        </div>
        <Network size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Impact policy ID</span>
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
          <label className="approval-check">
            <input
              type="checkbox"
              checked={reachabilityAcknowledged}
              onChange={(event) => setReachabilityAcknowledged(event.target.checked)}
            />
            <span>Graph reachability is dependency evidence, not proof of an outage.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={provisionalAcknowledged}
              onChange={(event) => setProvisionalAcknowledged(event.target.checked)}
            />
            <span>Impact, interruption, duration, risk, and recovery remain provisional.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Enrichment grants no recommendation, workflow, or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ candidateResult, policyId, policyDigest })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Network size={16} />}
            Analyze reachability
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Impact enrichment unavailable</h3>
            <p>Candidate lineage, graph snapshot, policy, access, and protected artifacts must remain current.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>Service reachability analyzed</strong>
          <code>{result.impact_analysis.impact_analysis_id}</code>
          <p className="muted-copy">
            {result.manifest.candidate_count} candidates, {result.manifest.path_count} dependency
            paths, {result.manifest.modeled_entity_count} modeled entities, and {" "}
            {result.manifest.technical_service_count + result.manifest.business_service_count}
            service mappings were evaluated.
          </p>
          <div className="connector-capability-list" aria-label="Graph analysis status">
            <span className="connector-capability" data-state="available">
              {result.manifest.graph_freshness}
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.graph_completeness}
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.gap_count} graph gaps
            </span>
          </div>
          <p className="muted-copy">{result.manifest.safety_notice}</p>
        </div>
      )}
    </div>
  );
}
