import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  CircleHelp,
  Clock3,
  FileText,
  RefreshCw,
  Scale,
  ShieldCheck,
} from "lucide-react";

import type { InvestigationArtifact } from "../../api/investigations";
import type { RcaCase } from "../../api/rca";
import type { RecommendationArtifact } from "../../api/recommendations";

export interface HealthDecisionSupportWorkspaceProps {
  canBuildRca: boolean;
  canCompareOptions: boolean;
  investigationError: boolean;
  investigationPending: boolean;
  onBuildRca: () => void;
  onCompareOptions: () => void;
  rcaCase?: RcaCase;
  rcaError: boolean;
  rcaPending: boolean;
  reasoningArtifact?: InvestigationArtifact;
  recommendation?: RecommendationArtifact;
  recommendationError: boolean;
  recommendationPending: boolean;
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function ReasoningPanel({
  artifact,
  error,
  pending,
}: {
  artifact?: InvestigationArtifact;
  error: boolean;
  pending: boolean;
}) {
  return (
    <section className="workspace-section reasoning-section" aria-live="polite">
      <div className="section-heading">
        <div><p className="eyebrow">EVIDENCE-GROUNDED INVESTIGATION</p><h2>Reasoning artifact</h2></div>
        {artifact && <span className="reasoning-version"><BrainCircuit size={14} /> Version {artifact.version}</span>}
      </div>

      {!artifact && !pending && !error && (
        <div className="reasoning-empty">
          <BrainCircuit size={21} />
          <div><strong>Start a bounded investigation</strong><p>The selected target will be assessed from authorized evidence without claiming root cause or outage.</p></div>
        </div>
      )}
      {pending && (
        <div className="reasoning-empty">
          <Clock3 size={20} />
          <div><strong>Assembling governed evidence</strong><p>Scope, citations, epistemic types, and safety checks are being validated.</p></div>
        </div>
      )}
      {error && (
        <div className="reasoning-empty reasoning-error" role="alert">
          <AlertTriangle size={20} />
          <div><strong>Investigation unavailable</strong><p>No conclusion is shown when the governed artifact cannot be validated.</p></div>
        </div>
      )}

      {artifact && (
        <>
          <div className="reasoning-summary-grid">
            <div><span>Confidence</span><strong className={`confidence ${artifact.summary.confidence}`}>{artifact.summary.confidence}</strong><p>{artifact.summary.confidence_rationale}</p></div>
            <div><span>Supported decision</span><strong>{artifact.summary.supported_decision}</strong></div>
            <div><span>Not supported</span><strong>{artifact.summary.unsupported_decision}</strong></div>
          </div>
          <div className="reasoning-facts-grid">
            <div><h3>Known</h3><ul>{artifact.summary.known.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><h3>Inferred</h3><ul>{artifact.summary.inferred.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><h3>Unknown</h3><ul>{artifact.summary.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </div>
          <div className="reasoning-body-grid">
            <div className="claim-ledger">
              <h3>Typed claim ledger</h3>
              {artifact.claims.map((claim) => (
                <article key={claim.claim_id}>
                  <div><span className={`epistemic-type ${claim.epistemic_type}`}>{claim.epistemic_type.replaceAll("_", " ")}</span><span className={`confidence ${claim.confidence}`}>{claim.confidence}</span></div>
                  <strong>{claim.text}</strong>
                  <small>{claim.supporting_evidence.length} supporting / {claim.contradicting_evidence.length} contradicting evidence</small>
                </article>
              ))}
            </div>
            <div className="hypothesis-ledger">
              <h3>Alternative hypotheses</h3>
              {artifact.hypotheses.map((hypothesis) => (
                <article key={hypothesis.hypothesis_id}>
                  <div><span className="state-badge">{hypothesis.state}</span><span className={`confidence ${hypothesis.confidence}`}>{hypothesis.confidence}</span></div>
                  <strong>{hypothesis.statement}</strong><p>{hypothesis.confidence_rationale}</p>
                  <div className="next-check"><ShieldCheck size={14} /><span>{hypothesis.discriminating_checks[0]?.title} | {hypothesis.discriminating_checks[0]?.capability_class} read-only</span></div>
                </article>
              ))}
            </div>
          </div>
          <div className="reasoning-timeline">
            <h3>Normalized UTC timeline</h3>
            {artifact.timeline.map((event) => <div key={event.event_id}><span>{formatTimestamp(event.occurred_at)}</span><strong>{event.summary}</strong><small>{event.evidence_references.length} linked evidence</small></div>)}
          </div>
          <div className="reasoning-stop"><CircleHelp size={16} /><div><strong>Stop reason</strong><p>{artifact.stop_reason}</p><span>{artifact.summary.safest_next_check}</span></div></div>
          <div className="safety-notice"><ShieldCheck size={16} /><span>{artifact.safety_notice}</span></div>
        </>
      )}
    </section>
  );
}

function RcaPanel({
  canBuild,
  error,
  onBuild,
  pending,
  rcaCase,
}: {
  canBuild: boolean;
  error: boolean;
  onBuild: () => void;
  pending: boolean;
  rcaCase?: RcaCase;
}) {
  return (
    <section className="workspace-section rca-section" aria-live="polite">
      <div className="section-heading rca-heading">
        <div><p className="eyebrow">ROOT CAUSE ANALYSIS</p><h2>Governed RCA case</h2></div>
        <button className="run-check-button" type="button" disabled={!canBuild || pending} onClick={onBuild}>
          {pending ? <RefreshCw className="spin" size={14} /> : <FileText size={14} />} Build RCA case
        </button>
      </div>
      {!rcaCase && !pending && !error && <div className="reasoning-empty"><FileText size={21} /><div><strong>Investigation evidence required</strong><p>Build a provisional case after the governed reasoning artifact is available. Root cause and service impact remain unconfirmed.</p></div></div>}
      {pending && <div className="reasoning-empty"><Clock3 size={20} /><div><strong>Building immutable RCA case</strong><p>Evidence balance, causal taxonomy, and diagnostics are being checked.</p></div></div>}
      {error && <div className="reasoning-empty reasoning-error" role="alert"><AlertTriangle size={20} /><div><strong>RCA case unavailable</strong><p>No cause statement is shown when governance checks fail.</p></div></div>}

      {rcaCase && (
        <>
          <div className="rca-summary-grid">
            <div><span>Case version</span><strong>Version {rcaCase.version}</strong><small>{rcaCase.incident_references[0]?.reference_id}</small></div>
            <div><span>State</span><strong className={`rca-state ${rcaCase.state}`}>{rcaCase.state}</strong><small>{rcaCase.severity} severity</small></div>
            <div><span>Owner</span><strong>{rcaCase.owner}</strong><small>{rcaCase.target_id}</small></div>
            <div><span>Human review</span><strong>{rcaCase.human_review.status}</strong><small>Attributable review required</small></div>
          </div>
          <div className="rca-impact-grid">
            <div><h3>Observed symptom</h3><strong>{rcaCase.symptoms[0]?.statement}</strong><p>{rcaCase.symptoms[0]?.current_state}</p></div>
            <div><h3>Affected / possible</h3><strong>{rcaCase.impact_scope.affected_entities.join(", ")}</strong><p>Possible services: {rcaCase.impact_scope.possibly_affected_services.join(", ")}</p></div>
            <div><h3>Explicitly unaffected</h3><strong>{rcaCase.impact_scope.explicitly_unaffected_entities.join(", ")}</strong><p>{rcaCase.impact_scope.limitations[0]}</p></div>
          </div>
          <div className="rca-body-grid">
            <div className="rca-hypotheses">
              <h3>Ranked hypotheses</h3>
              {rcaCase.hypotheses.map((hypothesis) => (
                <article key={hypothesis.hypothesis_id}>
                  <div className="rca-hypothesis-title"><span className="rca-rank">#{hypothesis.rank}</span><span className="epistemic-type">{hypothesis.cause_type.replaceAll("_", " ")}</span><span className={`confidence ${hypothesis.confirmation_level}`}>{hypothesis.confirmation_level.replaceAll("_", " ")}</span></div>
                  <strong>{hypothesis.statement}</strong><p>{hypothesis.mechanism}</p>
                  <small>{hypothesis.supporting_evidence.length} supporting / {hypothesis.contradicting_evidence.length} contradicting / {hypothesis.missing_expected_observations.length} missing</small>
                  <div className="rca-sequence">{hypothesis.expected_sequence.map((step) => <span key={step}>{step}</span>)}</div>
                </article>
              ))}
            </div>
            <div className="rca-diagnostics">
              <h3>Bounded diagnostics</h3>
              {rcaCase.hypotheses.flatMap((hypothesis) => hypothesis.diagnostic_steps.map((step) => (
                <article key={`${hypothesis.hypothesis_id}-${step.step_id}`}>
                  <div><ShieldCheck size={14} /><span>{step.capability_class}</span></div><strong>{step.question}</strong><p>{step.capability_id}</p>
                  <small>{step.timeout_seconds}s timeout | max {step.max_output_records} records | {step.approval_required ? "approval required" : "no approval"}</small>
                </article>
              )))}
            </div>
          </div>
          <div className="rca-gaps-grid">
            <div><h3>Evidence gaps</h3><ul>{rcaCase.evidence_gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul></div>
            <div><h3>Current blocker</h3><p>{rcaCase.blocker}</p><strong>{rcaCase.safest_next_step}</strong></div>
          </div>
          <div className="rca-provisional"><CircleHelp size={17} /><div><strong>Provisional cause statement</strong><p>{rcaCase.provisional_statement.statement}</p><span>{rcaCase.provisional_statement.prevention_or_verification_implication}</span></div></div>
          <div className="safety-notice"><ShieldCheck size={16} /><span>{rcaCase.safety_notice}</span></div>
        </>
      )}
    </section>
  );
}

function RecommendationPanel({
  canCompare,
  error,
  onCompare,
  pending,
  recommendation,
}: {
  canCompare: boolean;
  error: boolean;
  onCompare: () => void;
  pending: boolean;
  recommendation?: RecommendationArtifact;
}) {
  return (
    <section className="workspace-section recommendation-section" aria-live="polite">
      <div className="section-heading recommendation-heading">
        <div><p className="eyebrow">RECOMMENDATION ENGINE</p><h2>Operational choices</h2></div>
        <button className="run-check-button recommendation-button" type="button" disabled={!canCompare || pending} onClick={onCompare}>
          {pending ? <RefreshCw className="spin" size={14} /> : <Scale size={14} />} Compare options
        </button>
      </div>
      {!recommendation && !pending && !error && <div className="reasoning-empty"><Scale size={21} /><div><strong>Governed RCA case required</strong><p>Compare diagnostic, escalation, deferral, and blocked change-planning choices after the provisional RCA case is available.</p></div></div>}
      {pending && <div className="reasoning-empty"><Clock3 size={20} /><div><strong>Comparing operational choices</strong><p>Evidence, risk, reversibility, interruption, and policy are being validated.</p></div></div>}
      {error && <div className="reasoning-empty reasoning-error" role="alert"><AlertTriangle size={20} /><div><strong>Recommendation unavailable</strong><p>No preferred option is shown when source or governance checks fail.</p></div></div>}

      {recommendation && (
        <>
          <div className="recommendation-summary-grid">
            <div><span>Artifact</span><strong>Version {recommendation.version}</strong><small>{recommendation.state.replaceAll("_", " ")}</small></div>
            <div><span>Source RCA</span><strong>Version {recommendation.source_case_version}</strong><small>{recommendation.source_case_state}</small></div>
            <div><span>Human review</span><strong>{recommendation.human_review.status}</strong><small>{recommendation.accountable_audience}</small></div>
            <div><span>Expires</span><strong>{formatTimestamp(recommendation.expires_at)}</strong><small>{recommendation.horizon.replaceAll("_", " ")}</small></div>
          </div>
          <div className="preferred-option-banner"><CheckCircle2 size={18} /><div><span>Preferred for the current decision</span><strong>{recommendation.options.find((option) => option.option_id === recommendation.preferred_option_id)?.title ?? "No option preferred"}</strong><p>{recommendation.preference_rationale}</p></div></div>
          <div className="recommendation-options">
            <h3>Compared options</h3>
            <div>{recommendation.options.map((option) => (
              <article className={`${option.state} ${option.preference}`} key={option.option_id}>
                <div className="recommendation-option-head"><span className="recommendation-category">{option.category.replaceAll("_", " ")}</span><span className={`recommendation-state ${option.state}`}>{option.state}</span><span className={`risk-level ${option.overall_risk}`}>{option.overall_risk} risk</span></div>
                <strong>{option.title}</strong><p>{option.intended_outcome}</p>
                <div className="recommendation-option-metrics"><span>Evidence <strong>{option.confidence}</strong></span><span>Duration <strong>{option.duration.minimum_minutes}-{option.duration.maximum_minutes} min</strong></span><span>Interruption <strong>{option.interruption.expected_mode}</strong></span></div>
                <div className="recommendation-plan">{option.plan_steps.map((step) => <div key={step.step_id}><span>{step.order}</span><p>{step.conceptual_action}</p><small>{step.capability_class} | {step.capability_id ?? "human procedure"}</small></div>)}</div>
                {option.state === "blocked" ? <div className="recommendation-exclusions"><strong>Blocked by policy and readiness</strong><ul>{option.exclusion_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div> : <div className="recommendation-readiness"><span>Rollback {option.recovery.rollback_feasible ? "credible" : "not established"}</span><span>{option.policy_outcome.replaceAll("_", " ")}</span></div>}
              </article>
            ))}</div>
          </div>
          <div className="recommendation-comparison">
            <h3>Visible comparison dimensions</h3>
            <div className="table-wrap"><table><thead><tr><th>Dimension</th>{recommendation.options.map((option) => <th key={option.option_id}>{option.category.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{recommendation.comparisons.map((comparison) => <tr key={comparison.dimension}><td>{comparison.dimension.replaceAll("_", " ")}</td>{recommendation.options.map((option) => <td key={option.option_id}>{comparison.option_values.find(([optionId]) => optionId === option.option_id)?.[1] ?? "Unknown"}</td>)}</tr>)}</tbody></table></div>
          </div>
          <div className="recommendation-policy-grid">
            <div><h3>Policy constraints</h3><ul>{recommendation.policy_constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul></div>
            <div><h3>Decision boundary</h3><p>{recommendation.execution_authorized ? "Execution authority present" : "No execution authority"}</p><strong>Review does not grant RBAC, approval, or runtime authority.</strong></div>
          </div>
          <div className="safety-notice"><ShieldCheck size={16} /><span>{recommendation.safety_notice}</span></div>
        </>
      )}
    </section>
  );
}

export default function HealthDecisionSupportWorkspace(props: HealthDecisionSupportWorkspaceProps) {
  return (
    <div className="health-decision-support-workspace" aria-label="Health decision support">
      <ReasoningPanel artifact={props.reasoningArtifact} error={props.investigationError} pending={props.investigationPending} />
      <RcaPanel canBuild={props.canBuildRca} error={props.rcaError} onBuild={props.onBuildRca} pending={props.rcaPending} rcaCase={props.rcaCase} />
      <RecommendationPanel canCompare={props.canCompareOptions} error={props.recommendationError} onCompare={props.onCompareOptions} pending={props.recommendationPending} recommendation={props.recommendation} />
    </div>
  );
}
