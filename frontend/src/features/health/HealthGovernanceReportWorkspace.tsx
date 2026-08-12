import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Download,
  FileChartColumn,
  FileText,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  X,
} from "lucide-react";

import type { ApprovalRecord } from "../../api/approvals";
import type {
  ItsmHandoffHumanReview,
  ItsmHandoffReviewOutcome,
  TechnicalReport,
} from "../../api/reports";

export type ApprovalDecisionOutcome = "approve" | "reject" | "needs_evidence" | "defer";

export interface HealthGovernanceReportWorkspaceProps {
  approval?: ApprovalRecord;
  approvalDecisionError: boolean;
  approvalDecisionPending: boolean;
  approvalError: boolean;
  approvalLoading: boolean;
  approvalRationale: string;
  canGenerateReport: boolean;
  canReviewApproval: boolean;
  canReviewItsmHandoff: boolean;
  canSubmitApproval: boolean;
  itsmHandoffReview?: ItsmHandoffHumanReview;
  itsmHandoffReviewAcknowledged: boolean;
  itsmHandoffReviewError: boolean;
  itsmHandoffReviewPending: boolean;
  itsmHandoffReviewRationale: string;
  onApprovalRationaleChange: (value: string) => void;
  onDecideApproval: (outcome: ApprovalDecisionOutcome) => void;
  onDecideItsmHandoffReview: (outcome: ItsmHandoffReviewOutcome) => void;
  onDownloadReport: () => void;
  onGenerateReport: () => void;
  onItsmHandoffReviewAcknowledgedChange: (value: boolean) => void;
  onItsmHandoffReviewRationaleChange: (value: string) => void;
  onSubmitApproval: () => void;
  reportError: boolean;
  reportPending: boolean;
  technicalReport?: TechnicalReport;
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function ApprovalPanel({
  approval,
  approvalDecisionError,
  approvalDecisionPending,
  approvalError,
  approvalLoading,
  approvalRationale,
  canReviewApproval,
  canSubmitApproval,
  onApprovalRationaleChange,
  onDecideApproval,
  onSubmitApproval,
}: Pick<
  HealthGovernanceReportWorkspaceProps,
  | "approval"
  | "approvalDecisionError"
  | "approvalDecisionPending"
  | "approvalError"
  | "approvalLoading"
  | "approvalRationale"
  | "canReviewApproval"
  | "canSubmitApproval"
  | "onApprovalRationaleChange"
  | "onDecideApproval"
  | "onSubmitApproval"
>) {
  return (
    <section className="workspace-section approval-section" aria-live="polite">
      <div className="section-heading approval-heading">
        <div>
          <p className="eyebrow">HUMAN GOVERNANCE</p>
          <h2>Immutable approval review</h2>
        </div>
        <button
          className="run-check-button approval-submit"
          type="button"
          disabled={!canSubmitApproval || approvalLoading || Boolean(approval)}
          onClick={onSubmitApproval}
        >
          {approvalLoading ? (
            <RefreshCw className="spin" size={14} />
          ) : (
            <UserCheck size={14} />
          )}
          Submit for human review
        </button>
      </div>

      {!approval && !approvalLoading && !approvalError && (
        <div className="reasoning-empty">
          <UserCheck size={21} />
          <div>
            <strong>Governed recommendation required</strong>
            <p>An exact option is bound to an immutable packet before human review.</p>
          </div>
        </div>
      )}
      {approvalLoading && (
        <div className="reasoning-empty">
          <Clock3 size={20} />
          <div>
            <strong>Building immutable packet</strong>
            <p>Source versions, evidence, risk, impact, recovery, and expiry are being bound.</p>
          </div>
        </div>
      )}
      {approvalError && (
        <div className="reasoning-empty reasoning-error" role="alert">
          <AlertTriangle size={20} />
          <div>
            <strong>Approval unavailable</strong>
            <p>No review controls are shown when packet validation fails.</p>
          </div>
        </div>
      )}

      {approval && (
        <>
          <div className="approval-summary-grid">
            <div>
              <span>State</span>
              <strong>{approval.state.replaceAll("_", " ")}</strong>
              <small>Version {approval.version}</small>
            </div>
            <div>
              <span>Requester</span>
              <strong>{approval.packet.requested_by}</strong>
              <small>{approval.packet.purpose}</small>
            </div>
            <div>
              <span>Risk</span>
              <strong>{approval.packet.overall_risk}</strong>
              <small>{approval.packet.option_confidence} confidence</small>
            </div>
            <div>
              <span>Expires</span>
              <strong>{formatTimestamp(approval.packet.expires_at)}</strong>
              <small>{approval.packet.canonicalization_version}</small>
            </div>
          </div>

          <div className="approval-digest">
            <ShieldCheck size={17} />
            <div>
              <span>Canonical packet digest</span>
              <strong>{approval.packet.canonical_digest}</strong>
            </div>
          </div>

          <div className="approval-focus">
            <div>
              <span>Exact option</span>
              <strong>{approval.packet.option_title}</strong>
              <p>{approval.packet.confidence_rationale}</p>
            </div>
            <div>
              <span>Impact boundary</span>
              <strong>{approval.packet.blast_radius}</strong>
              <p>
                {approval.packet.impact_confirmed ? "Impact confirmed" : "Impact remains unconfirmed"}
                {" · "}
                {approval.packet.graph_maturity}
              </p>
            </div>
            <div>
              <span>Interruption</span>
              <strong>{approval.packet.interruption_expected_mode}</strong>
              <p>Worst credible: {approval.packet.interruption_worst_credible_mode}</p>
            </div>
            <div>
              <span>Recovery</span>
              <strong>
                {approval.packet.rollback_feasible ? "Rollback described" : "Rollback not established"}
              </strong>
              <p>{approval.packet.recovery_strategy}</p>
            </div>
          </div>

          <div className="approval-evidence-grid">
            <div>
              <h3>Evidence and assumptions</h3>
              <ul>
                {approval.packet.evidence_summaries.map((item, index) => (
                  <li key={`evidence-${index}-${item}`}>{item}</li>
                ))}
                {approval.packet.assumptions.map((item, index) => (
                  <li key={`assumption-${index}-${item}`}>Assumption: {item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Unknowns and gaps</h3>
              <ul>
                {[
                  ...approval.packet.unknowns,
                  ...approval.packet.impact_gaps,
                  ...approval.packet.recovery_gaps,
                ].map((item, index) => (
                  <li key={`gap-${index}-${item}`}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="approval-plan">
            <h3>Bound ordered plan</h3>
            {approval.packet.plan_steps.map((step) => (
              <div key={step.step_id}>
                <span>{step.order}</span>
                <p>{step.conceptual_action}</p>
                <small>
                  {step.capability_class} · {step.stop_condition}
                </small>
              </div>
            ))}
          </div>

          <div className="approval-review-boundary">
            <div>
              <strong>
                {approval.execution_authorized ? "Execution authority present" : "No execution authority"}
              </strong>
              <p>
                An approval records a human decision only. It grants no RBAC, connector, or runtime
                permission.
              </p>
            </div>
            {approval.decisions.length > 0 && (
              <div className="approval-history">
                <span>Decision history</span>
                {approval.decisions.map((item) => (
                  <p key={item.decision_id}>
                    <strong>{item.outcome.replaceAll("_", " ")}</strong> by {item.reviewer_id}:{" "}
                    {item.rationale}
                  </p>
                ))}
              </div>
            )}
          </div>

          {approval.state === "pending" && !canReviewApproval && (
            <div className="approval-ineligible">
              <LockKeyhole size={17} />
              <div>
                <strong>Separated reviewer required</strong>
                <p>
                  The requester, a non-human identity, or development assurance cannot decide this
                  packet.
                </p>
              </div>
            </div>
          )}
          {canReviewApproval && (
            <div className="approval-controls">
              <label htmlFor="approval-rationale">Decision rationale</label>
              <textarea
                id="approval-rationale"
                value={approvalRationale}
                onChange={(event) => onApprovalRationaleChange(event.target.value)}
                maxLength={1000}
                placeholder="Record the evidence-based reason for this decision..."
              />
              <div>
                {(
                  [
                    ["approve", "Approve", CheckCircle2],
                    ["reject", "Reject", X],
                    ["needs_evidence", "Needs evidence", CircleHelp],
                    ["defer", "Defer", Clock3],
                  ] as const
                ).map(([outcome, label, Icon]) => (
                  <button
                    key={outcome}
                    type="button"
                    disabled={approvalRationale.trim().length < 5 || approvalDecisionPending}
                    onClick={() => onDecideApproval(outcome)}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {approvalDecisionError && (
            <div className="impact-message impact-error" role="alert">
              <AlertTriangle size={18} /> Decision was not recorded; reload the immutable packet
              before retrying.
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ReportPanel({
  canGenerateReport,
  canReviewItsmHandoff,
  itsmHandoffReview,
  itsmHandoffReviewAcknowledged,
  itsmHandoffReviewError,
  itsmHandoffReviewPending,
  itsmHandoffReviewRationale,
  onDecideItsmHandoffReview,
  onDownloadReport,
  onGenerateReport,
  onItsmHandoffReviewAcknowledgedChange,
  onItsmHandoffReviewRationaleChange,
  reportError,
  reportPending,
  technicalReport,
}: Pick<
  HealthGovernanceReportWorkspaceProps,
  | "canGenerateReport"
  | "canReviewItsmHandoff"
  | "itsmHandoffReview"
  | "itsmHandoffReviewAcknowledged"
  | "itsmHandoffReviewError"
  | "itsmHandoffReviewPending"
  | "itsmHandoffReviewRationale"
  | "onDecideItsmHandoffReview"
  | "onDownloadReport"
  | "onGenerateReport"
  | "onItsmHandoffReviewAcknowledgedChange"
  | "onItsmHandoffReviewRationaleChange"
  | "reportError"
  | "reportPending"
  | "technicalReport"
>) {
  return (
    <section className="workspace-section report-section" aria-live="polite">
      <div className="section-heading report-heading">
        <div>
          <p className="eyebrow">TECHNICAL REPORT</p>
          <h2>Decision report and ITSM handoff</h2>
        </div>
        <div className="report-heading-actions">
          {technicalReport && (
            <button
              className="icon-button report-download"
              type="button"
              aria-label="Download technical report"
              title="Download Markdown report"
              onClick={onDownloadReport}
            >
              <Download size={15} />
            </button>
          )}
          <button
            className="run-check-button report-button"
            type="button"
            disabled={!canGenerateReport || reportPending}
            onClick={onGenerateReport}
          >
            {reportPending ? (
              <RefreshCw className="spin" size={14} />
            ) : (
              <FileChartColumn size={14} />
            )}
            Generate report
          </button>
        </div>
      </div>

      {!technicalReport && !reportPending && !reportError && (
        <div className="reasoning-empty">
          <FileChartColumn size={21} />
          <div>
            <strong>Governed recommendation required</strong>
            <p>
              Generate a source-bound technical report and a review-only ITSM handoff draft after
              the option comparison is available.
            </p>
          </div>
        </div>
      )}
      {reportPending && (
        <div className="reasoning-empty">
          <Clock3 size={20} />
          <div>
            <strong>Validating report source and evidence</strong>
            <p>Lineage, classification, redaction, integrity, and audit are being checked.</p>
          </div>
        </div>
      )}
      {reportError && (
        <div className="reasoning-empty reasoning-error" role="alert">
          <AlertTriangle size={20} />
          <div>
            <strong>Technical report unavailable</strong>
            <p>No partial report or ITSM draft is disclosed after a validation failure.</p>
          </div>
        </div>
      )}

      {technicalReport && (
        <>
          <div className="report-summary-grid">
            <div>
              <span>Report</span>
              <strong>Version {technicalReport.version}</strong>
              <small>{technicalReport.state.replaceAll("_", " ")}</small>
            </div>
            <div>
              <span>Audience</span>
              <strong>{technicalReport.audience.replaceAll("_", " ")}</strong>
              <small>{technicalReport.classification}</small>
            </div>
            <div>
              <span>Human review</span>
              <strong>{technicalReport.review.status}</strong>
              <small>{technicalReport.owner}</small>
            </div>
            <div>
              <span>Redaction</span>
              <strong>{technicalReport.redaction_state}</strong>
              <small>Expires {formatTimestamp(technicalReport.expires_at)}</small>
            </div>
          </div>

          <div className="report-lineage">
            <FileText size={18} />
            <div>
              <span>Immutable source lineage</span>
              <strong>
                Recommendation v{technicalReport.source.recommendation_version} · RCA v
                {technicalReport.source.rca_case_version}
              </strong>
              <p>
                {technicalReport.source.evidence_ids.length} authorized evidence references · digest{" "}
                {technicalReport.content_digest.slice(0, 16)}…
              </p>
            </div>
          </div>

          <div className="report-sections">
            <h3>Structured report sections</h3>
            <div>
              {technicalReport.sections.map((section) => (
                <article key={section.section_id} className={section.state}>
                  <div className="report-section-head">
                    <strong>{section.title}</strong>
                    <span>{section.state}</span>
                  </div>
                  <ul>
                    {section.statements.map((statement, index) => (
                      <li key={`${section.section_id}-statement-${index}`}>{statement}</li>
                    ))}
                  </ul>
                  {section.evidence_references.length > 0 && (
                    <div className="report-evidence">
                      <span>Evidence</span>
                      {section.evidence_references.map((reference, index) => (
                        <code key={`${section.section_id}-evidence-${index}`}>{reference}</code>
                      ))}
                    </div>
                  )}
                  {section.limitations.length > 0 && (
                    <div className="report-limitations">
                      <strong>Limitations</strong>
                      <ul>
                        {section.limitations.map((limitation, index) => (
                          <li key={`${section.section_id}-limitation-${index}`}>{limitation}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>

          {technicalReport.itsm_handoff && (
            <div className="itsm-handoff">
              <div>
                <span>ITSM HANDOFF DRAFT</span>
                <h3>{technicalReport.itsm_handoff.incident_reference}</h3>
                <p>{technicalReport.itsm_handoff.generated_content_label}</p>
              </div>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{technicalReport.itsm_handoff.state.replaceAll("_", " ")}</dd>
                </div>
                <div>
                  <dt>Operation</dt>
                  <dd>{technicalReport.itsm_handoff.operation.replaceAll("_", " ")}</dd>
                </div>
                <div>
                  <dt>External dispatch</dt>
                  <dd>
                    {technicalReport.itsm_handoff.dispatch_authorized ? "Authorized" : "Not authorized"}
                  </dd>
                </div>
                <div>
                  <dt>Record mutation</dt>
                  <dd>{technicalReport.itsm_handoff.external_record_mutated ? "Recorded" : "None"}</dd>
                </div>
              </dl>
              <div className="itsm-fields">
                {technicalReport.itsm_handoff.field_mappings.map((mapping) => (
                  <div key={mapping.field}>
                    <span>{mapping.field.replaceAll("_", " ")}</span>
                    <strong>{mapping.value}</strong>
                  </div>
                ))}
              </div>
              <p className="itsm-idempotency">
                Idempotency {technicalReport.itsm_handoff.idempotency_key.slice(0, 20)}…
              </p>
            </div>
          )}

          {technicalReport.itsm_handoff && (
            <section className="itsm-review" aria-live="polite">
              <div className="itsm-review-heading">
                <div>
                  <span>ATTRIBUTABLE HUMAN REVIEW</span>
                  <h3>Review the exact handoff draft</h3>
                </div>
                <strong className={itsmHandoffReview?.review_complete ? "complete" : "pending"}>
                  {itsmHandoffReview
                    ? itsmHandoffReview.outcome.replaceAll("_", " ")
                    : "Pending"}
                </strong>
              </div>

              {itsmHandoffReviewPending && (
                <div className="itsm-review-message">
                  <RefreshCw className="spin" size={17} />
                  <div>
                    <strong>Validating immutable review state</strong>
                    <p>The exact report, digest, draft and reviewer scope are being checked.</p>
                  </div>
                </div>
              )}

              {itsmHandoffReviewError && (
                <div className="itsm-review-message error" role="alert">
                  <AlertTriangle size={17} />
                  <div>
                    <strong>Review unavailable</strong>
                    <p>No review decision is accepted when source or authorization checks fail.</p>
                  </div>
                </div>
              )}

              {itsmHandoffReview && (
                <div className="itsm-review-record">
                  <div>
                    <UserCheck size={18} />
                    <div>
                      <strong>{itsmHandoffReview.reviewer_id}</strong>
                      <span>{formatTimestamp(itsmHandoffReview.decided_at)}</span>
                    </div>
                  </div>
                  <p>{itsmHandoffReview.rationale}</p>
                  <dl>
                    <div>
                      <dt>Review complete</dt>
                      <dd>{itsmHandoffReview.review_complete ? "Yes" : "No"}</dd>
                    </div>
                    <div>
                      <dt>Dispatch authority</dt>
                      <dd>{itsmHandoffReview.dispatch_authorized ? "Present" : "None"}</dd>
                    </div>
                    <div>
                      <dt>ITSM approval</dt>
                      <dd>
                        {itsmHandoffReview.itsm_approval_satisfied
                          ? "Satisfied"
                          : "Not satisfied"}
                      </dd>
                    </div>
                    <div>
                      <dt>Execution authority</dt>
                      <dd>{itsmHandoffReview.execution_authorized ? "Present" : "None"}</dd>
                    </div>
                  </dl>
                  <code>Digest {itsmHandoffReview.canonical_digest.slice(0, 20)}...</code>
                </div>
              )}

              {!itsmHandoffReview && !itsmHandoffReviewPending && canReviewItsmHandoff && (
                <div className="itsm-review-form">
                  <label htmlFor="itsm-review-rationale">Review rationale</label>
                  <textarea
                    id="itsm-review-rationale"
                    rows={3}
                    maxLength={1000}
                    value={itsmHandoffReviewRationale}
                    onChange={(event) =>
                      onItsmHandoffReviewRationaleChange(event.target.value)
                    }
                  />
                  <label className="itsm-review-acknowledgement">
                    <input
                      type="checkbox"
                      checked={itsmHandoffReviewAcknowledged}
                      onChange={(event) =>
                        onItsmHandoffReviewAcknowledgedChange(event.target.checked)
                      }
                    />
                    <span>
                      I reviewed this exact draft and understand that this records review evidence
                      only. It does not dispatch, approve a workflow or authorize execution.
                    </span>
                  </label>
                  <div className="itsm-review-actions">
                    <button
                      type="button"
                      className="run-check-button"
                      disabled={
                        !itsmHandoffReviewAcknowledged ||
                        itsmHandoffReviewRationale.trim().length < 5
                      }
                      onClick={() => onDecideItsmHandoffReview("accept")}
                    >
                      <CheckCircle2 size={14} />
                      Accept handoff draft
                    </button>
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={
                        !itsmHandoffReviewAcknowledged ||
                        itsmHandoffReviewRationale.trim().length < 5
                      }
                      onClick={() => onDecideItsmHandoffReview("needs_evidence")}
                    >
                      <CircleHelp size={14} />
                      Needs evidence
                    </button>
                    <button
                      type="button"
                      className="secondary-action danger"
                      disabled={
                        !itsmHandoffReviewAcknowledged ||
                        itsmHandoffReviewRationale.trim().length < 5
                      }
                      onClick={() => onDecideItsmHandoffReview("reject")}
                    >
                      <X size={14} />
                      Reject handoff draft
                    </button>
                  </div>
                </div>
              )}

              {!itsmHandoffReview && !itsmHandoffReviewPending && !canReviewItsmHandoff && (
                <div className="itsm-review-message">
                  <LockKeyhole size={17} />
                  <div>
                    <strong>Enterprise reviewer required</strong>
                    <p>
                      A separate human with the ITSM reviewer role and MFA-backed browser session
                      must review this exact draft.
                    </p>
                  </div>
                </div>
              )}

              <div className="itsm-review-boundary">
                <ShieldCheck size={15} />
                <span>No ticket dispatch, external mutation, workflow approval or execution.</span>
              </div>
            </section>
          )}

          <div className="report-boundary-grid">
            <div>
              <h3>Execution boundary</h3>
              <strong>
                {technicalReport.execution_authorized
                  ? "Execution authority present"
                  : "No execution authority"}
              </strong>
            </div>
            <div>
              <h3>External-system boundary</h3>
              <strong>
                {technicalReport.external_mutation_authorized
                  ? "External mutation authority present"
                  : "No external mutation authority"}
              </strong>
            </div>
          </div>
          <div className="safety-notice">
            <ShieldCheck size={16} />
            <span>{technicalReport.safety_notice}</span>
          </div>
        </>
      )}
    </section>
  );
}

export default function HealthGovernanceReportWorkspace(
  props: HealthGovernanceReportWorkspaceProps,
) {
  return (
    <div className="health-governance-report-workspace">
      <ApprovalPanel {...props} />
      <ReportPanel {...props} />
    </div>
  );
}
