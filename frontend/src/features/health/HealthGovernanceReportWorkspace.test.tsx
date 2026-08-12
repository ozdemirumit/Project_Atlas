import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApprovalRecord } from "../../api/approvals";
import type { ItsmHandoffHumanReview, TechnicalReport } from "../../api/reports";
import HealthGovernanceReportWorkspace from "./HealthGovernanceReportWorkspace";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const approval: ApprovalRecord = {
  request_id: "approval.test",
  version: 1,
  state: "pending",
  packet: {
    canonicalization_version: "atlas-approval-packet.v1",
    canonical_digest: "d".repeat(64),
    requested_by: "subject.requester",
    purpose: "Review a bounded diagnostic recommendation.",
    created_at: "2026-08-10T09:00:00Z",
    expires_at: "2026-08-10T10:00:00Z",
    target_id: "storage.test",
    recommendation_id: "recommendation.test",
    recommendation_version: 2,
    option_id: "option.observe",
    option_version: 1,
    option_title: "Collect read-only path evidence",
    option_category: "diagnostic",
    option_confidence: "moderate",
    confidence_rationale: "Current evidence supports another bounded observation.",
    overall_risk: "low",
    risk_rationales: ["The operation is read only."],
    evidence_references: ["evidence.test"],
    evidence_summaries: ["A current path warning is present."],
    alternatives: ["Wait for scheduled collection."],
    assumptions: ["The connector remains read only."],
    unknowns: ["Physical port state"],
    affected_components: ["storage.test"],
    possibly_affected_services: ["Service A"],
    blast_radius: "One storage target; service impact unconfirmed",
    impact_confirmed: false,
    graph_maturity: "partial",
    impact_gaps: ["Service ownership is incomplete."],
    duration_minimum_minutes: 1,
    duration_maximum_minutes: 5,
    interruption_expected_mode: "none",
    interruption_worst_credible_mode: "diagnostic delay",
    interruption_expected_minutes: [0, 0],
    interruption_worst_credible_minutes: [0, 5],
    interruption_unknowns: ["Collection queue time"],
    plan_steps: [
      {
        order: 1,
        step_id: "step.observe",
        conceptual_action: "Collect the authorized path state.",
        capability_id: "storage.paths.read",
        capability_class: "C1",
        expected_output: "A bounded path observation.",
        stop_condition: "Stop when the record limit is reached.",
      },
    ],
    preconditions: ["The target is authorized."],
    verification_criteria: ["A current observation is returned."],
    stop_conditions: ["The connector denies scope."],
    recovery_strategy: "No infrastructure recovery is required for a read-only query.",
    rollback_feasible: true,
    recovery_duration_minimum_minutes: 0,
    recovery_duration_maximum_minutes: 0,
    recovery_gaps: ["No change is planned."],
    policy_constraints: ["No autonomous infrastructure change"],
    execution_authorized: false,
  },
  decisions: [],
  execution_authorized: false,
};

const technicalReport: TechnicalReport = {
  report_id: "report.test",
  version: 3,
  prior_version_id: null,
  owner: "Storage Operations",
  state: "review_required",
  requested_by: "subject.requester",
  created_at: "2026-08-10T09:05:00Z",
  expires_at: "2026-08-11T09:05:00Z",
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  target_id: "storage.test",
  report_type: "technical_decision",
  audience: "technical_operations",
  classification: "internal",
  redaction_state: "validated",
  source: {
    recommendation_id: "recommendation.test",
    recommendation_version: 2,
    recommendation_state: "provisional",
    recommendation_created_at: "2026-08-10T09:00:00Z",
    recommendation_expires_at: "2026-08-11T09:00:00Z",
    rca_case_id: "rca.test",
    rca_case_version: 4,
    target_id: "storage.test",
    evidence_ids: ["evidence.test"],
    component_versions: ["storage.test@7"],
  },
  sections: [
    {
      section_id: "summary",
      title: "Decision summary",
      state: "partial",
      statements: ["A read-only diagnostic is preferred."],
      evidence_references: ["evidence.test"],
      limitations: ["Service impact is not confirmed."],
    },
  ],
  review: {
    status: "pending",
    reviewer_id: null,
    reviewed_at: null,
    rationale: null,
  },
  itsm_handoff: {
    draft_id: "itsm.test",
    idempotency_key: "i".repeat(64),
    state: "review_required",
    external_system: "unconfigured_itsm",
    operation: "append_labeled_analysis",
    incident_reference: "INC-TEST",
    report_id: "report.test",
    report_version: 3,
    generated_content_label: "Atlas generated decision-support draft",
    field_mappings: [
      {
        field: "work_notes",
        value: "Review the bounded recommendation.",
        source_reference: "report.test",
      },
    ],
    artifact_references: ["report.test"],
    classification: "internal",
    redaction_state: "validated",
    human_review_required: true,
    dispatch_authorized: false,
    external_record_mutated: false,
  },
  rendered_markdown: "# Atlas report",
  content_digest: "c".repeat(64),
  component_versions: ["storage.test@7"],
  data_profile: "authorized",
  execution_authorized: false,
  external_mutation_authorized: false,
  safety_notice: "Decision support only; no execution or external mutation is authorized.",
};

const itsmHandoffReview: ItsmHandoffHumanReview = {
  review_id: "itsm-handoff-review.test",
  schema_version: "atlas.itsm-handoff-human-review.v1",
  version: 1,
  outcome: "accept",
  report_id: technicalReport.report_id,
  report_version: technicalReport.version,
  report_digest: technicalReport.content_digest,
  handoff_draft_id: "itsm.test",
  handoff_digest: "h".repeat(64),
  handoff_idempotency_key: "i".repeat(64),
  incident_reference: "INC-TEST",
  operation: "append_labeled_analysis",
  requester_id: technicalReport.requested_by,
  reviewer_id: "subject.itsm.reviewer",
  reviewer_role_id: "role.itsm-reviewer",
  organization_id: technicalReport.organization_id,
  environment_id: technicalReport.environment_id,
  site_id: technicalReport.site_id,
  rationale: "The exact source-bound draft is suitable for accountable review handoff.",
  acknowledged_review_only: true,
  request_fingerprint: "f".repeat(64),
  idempotency_key: "itsm-review.test",
  canonical_digest: "d".repeat(64),
  decided_at: "2026-08-10T09:20:00Z",
  expires_at: technicalReport.expires_at,
  review_complete: true,
  dispatch_authorized: false,
  external_record_mutated: false,
  itsm_approval_satisfied: false,
  workflow_approved: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

const baseProps = {
  approvalDecisionError: false,
  approvalDecisionPending: false,
  approvalError: false,
  approvalLoading: false,
  approvalRationale: "",
  canGenerateReport: false,
  canReviewApproval: false,
  canReviewItsmHandoff: false,
  canSubmitApproval: false,
  itsmHandoffReviewAcknowledged: false,
  itsmHandoffReviewError: false,
  itsmHandoffReviewPending: false,
  itsmHandoffReviewRationale: "",
  onApprovalRationaleChange: vi.fn(),
  onDecideApproval: vi.fn(),
  onDecideItsmHandoffReview: vi.fn(),
  onDownloadReport: vi.fn(),
  onGenerateReport: vi.fn(),
  onItsmHandoffReviewAcknowledgedChange: vi.fn(),
  onItsmHandoffReviewRationaleChange: vi.fn(),
  onSubmitApproval: vi.fn(),
  reportError: false,
  reportPending: false,
};

describe("HealthGovernanceReportWorkspace", () => {
  it("presents fail-closed empty governance and report states", () => {
    render(<HealthGovernanceReportWorkspace {...baseProps} />);

    expect(screen.getByRole("heading", { name: "Immutable approval review" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Decision report and ITSM handoff" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Submit for human review" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate report" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /execute|dispatch|deploy|restart/i })).toBeNull();
  });

  it("keeps pending and failed states explicit without disclosing stale artifacts", () => {
    const { rerender } = render(
      <HealthGovernanceReportWorkspace {...baseProps} approvalLoading reportPending />,
    );

    expect(screen.getByText("Building immutable packet")).toBeVisible();
    expect(screen.getByText("Validating report source and evidence")).toBeVisible();

    rerender(
      <HealthGovernanceReportWorkspace {...baseProps} approvalError reportError />,
    );
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(screen.queryByText("Immutable source lineage")).toBeNull();
  });

  it("presents immutable history, lineage, ITSM draft, and no-authority boundaries", () => {
    const onDownloadReport = vi.fn();
    const decidedApproval = {
      ...approval,
      state: "approved" as const,
      decisions: [
        {
          decision_id: "decision.test",
          request_version: 1,
          outcome: "approve",
          reviewer_id: "subject.reviewer",
          decided_at: "2026-08-10T09:15:00Z",
          rationale: "The evidence supports this bounded diagnostic.",
        },
      ],
    };
    render(
      <HealthGovernanceReportWorkspace
        {...baseProps}
        approval={decidedApproval}
        canGenerateReport
        onDownloadReport={onDownloadReport}
        technicalReport={technicalReport}
      />,
    );

    expect(screen.getByText("Decision history")).toBeVisible();
    expect(screen.getByText(/by subject.reviewer/)).toBeVisible();
    expect(screen.getByText("Immutable source lineage")).toBeVisible();
    expect(screen.getByText("ITSM HANDOFF DRAFT")).toBeVisible();
    expect(screen.getByText("Enterprise reviewer required")).toBeVisible();
    expect(screen.getByText("Not authorized")).toBeVisible();
    expect(screen.getAllByText("No execution authority")).toHaveLength(2);
    expect(screen.getByText("No external mutation authority")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Download technical report" }));
    expect(onDownloadReport).toHaveBeenCalledOnce();
  });

  it("delegates controlled rationale and reviewer decisions through bounded callbacks", () => {
    const onApprovalRationaleChange = vi.fn();
    const onDecideApproval = vi.fn();
    render(
      <HealthGovernanceReportWorkspace
        {...baseProps}
        approval={approval}
        approvalRationale="Current evidence supports approval."
        canReviewApproval
        onApprovalRationaleChange={onApprovalRationaleChange}
        onDecideApproval={onDecideApproval}
      />,
    );

    fireEvent.change(screen.getByLabelText("Decision rationale"), {
      target: { value: "Needs one more observation." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Needs evidence" }));

    expect(onApprovalRationaleChange).toHaveBeenCalledWith("Needs one more observation.");
    expect(onDecideApproval).toHaveBeenCalledWith("needs_evidence");
  });

  it("requires rationale and explicit review-only acknowledgement before a handoff decision", () => {
    const onRationaleChange = vi.fn();
    const onAcknowledgedChange = vi.fn();
    const onDecide = vi.fn();
    const { rerender } = render(
      <HealthGovernanceReportWorkspace
        {...baseProps}
        canReviewItsmHandoff
        onDecideItsmHandoffReview={onDecide}
        onItsmHandoffReviewAcknowledgedChange={onAcknowledgedChange}
        onItsmHandoffReviewRationaleChange={onRationaleChange}
        technicalReport={technicalReport}
      />,
    );

    expect(screen.getByRole("button", { name: "Accept handoff draft" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review rationale"), {
      target: { value: "The exact draft is suitable for review." },
    });
    fireEvent.click(
      screen.getByLabelText(/I reviewed this exact draft and understand/i),
    );
    expect(onRationaleChange).toHaveBeenCalledWith("The exact draft is suitable for review.");
    expect(onAcknowledgedChange).toHaveBeenCalledWith(true);

    rerender(
      <HealthGovernanceReportWorkspace
        {...baseProps}
        canReviewItsmHandoff
        itsmHandoffReviewAcknowledged
        itsmHandoffReviewRationale="The exact draft is suitable for review."
        onDecideItsmHandoffReview={onDecide}
        onItsmHandoffReviewAcknowledgedChange={onAcknowledgedChange}
        onItsmHandoffReviewRationaleChange={onRationaleChange}
        technicalReport={technicalReport}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept handoff draft" }));
    expect(onDecide).toHaveBeenCalledWith("accept");
  });

  it("presents immutable review evidence without implying dispatch or execution authority", () => {
    render(
      <HealthGovernanceReportWorkspace
        {...baseProps}
        itsmHandoffReview={itsmHandoffReview}
        technicalReport={technicalReport}
      />,
    );

    expect(screen.getByText("subject.itsm.reviewer")).toBeVisible();
    expect(screen.getByText(itsmHandoffReview.rationale)).toBeVisible();
    expect(screen.getByText("Not satisfied")).toBeVisible();
    expect(screen.getByText(/No ticket dispatch, external mutation/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /dispatch|execute|approve workflow/i })).toBeNull();
  });
});
