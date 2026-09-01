import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, Scale, UserX } from "lucide-react";
import { useState } from "react";

import {
  analyzeConnectorPackageLicenses,
  type ConnectorPackageMalwareAnalysis,
} from "../../api/connectors";
import { ContractPanel } from "./ContractPanel";

type Props = {
  source: ConnectorPackageMalwareAnalysis;
  subjectId: string;
};

export function LicensePanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: analyzeConnectorPackageLicenses });

  const separated = Boolean(
    ![
      source.analyzed_by,
      source.source_vulnerability_analyzed_by,
      source.source_static_analyzed_by,
      source.source_authority_validated_by,
      source.source_schema_validated_by,
      source.source_content_scanned_by,
      source.source_inventoried_by,
      source.source_manifest_validated_by,
      source.source_acquired_by,
      source.source_custodied_by,
      source.source_domain_reviewed_by,
      source.source_security_reviewed_by,
      source.source_lab_operated_by,
    ].includes(subjectId),
  );

  const eligible = source.outcome === "passed" && !source.promotion_blocked;

  return (
    <>
      {eligible && !separated && !mutation.data && (
        <div className="workspace-message warning-state" role="status">
          <UserX size={20} />
          <div>
            <h3>Independent license analyst required</h3>
            <p>
              Every prior package-analysis actor is excluded. Continue with a different authorized
              session.
            </p>
          </div>
        </div>
      )}
      {eligible && separated && !mutation.data && (
        <section className="mcp-builder-review-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">LICENSE POLICY ANALYSIS</p>
              <h3>Compare represented licenses to policy</h3>
              <p>
                Evaluate opaque package, source, and dependency subjects against the trusted
                internal policy snapshot.
              </p>
            </div>
            <span className="state-badge neutral">
              <Scale size={14} /> Decision support
            </span>
          </div>
          <label className="mcp-builder-confirmation">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I am the independent license analyst. I understand this policy comparison is not
            legal advice and grants no redistribution or runtime authority.
          </label>
          <button
            className="run-check-button mcp-builder-submit"
            type="button"
            disabled={!acknowledged || mutation.isPending}
            onClick={() => {
              mutation.mutate(source);
            }}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <Scale size={16} />
            )}
            Analyze license policy
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>License analysis unavailable</h3>
            <p>Exact lineage, policy trust, coverage, or package metadata reconciliation did not pass.</p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE LICENSE REPORT</p>
              <strong>{mutation.data.data.analysis_id}</strong>
              <code>{mutation.data.data.canonical_digest}</code>
            </div>
            <span
              className={`state-badge ${
                mutation.data.data.outcome === "passed" ? "healthy" : "critical"
              }`}
            >
              {mutation.data.data.outcome === "passed" ? (
                <CheckCircle2 size={14} />
              ) : (
                <AlertTriangle size={14} />
              )}
              {mutation.data.data.outcome}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Policy snapshot</span>
              <strong>{mutation.data.data.policy_snapshot.snapshot_version}</strong>
            </div>
            <div>
              <span>Scanned subjects</span>
              <strong>
                {mutation.data.data.subject_summary.scanned_subject_count.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>Permitted</span>
              <strong>{mutation.data.data.subject_summary.permitted_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Blocking subjects</span>
              <strong>
                {(
                  mutation.data.data.subject_summary.review_required_count +
                  mutation.data.data.subject_summary.prohibited_count +
                  mutation.data.data.subject_summary.unknown_count
                ).toLocaleString()}
              </strong>
            </div>
          </div>
          <div className="mcp-builder-validation-checks">
            {mutation.data.data.checks.map((check) => (
              <article key={check.code} data-state={check.state}>
                {check.state === "passed" ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <AlertTriangle size={16} />
                )}
                <div>
                  <strong>{check.code}</strong>
                  <p>{check.summary}</p>
                </div>
                <span>{check.state}</span>
              </article>
            ))}
          </div>
          {mutation.data.data.findings.length > 0 && (
            <div className="mcp-builder-findings">
              {mutation.data.data.findings.map((finding) => (
                <article
                  key={`${finding.rule_id}-${finding.subject_fingerprint}`}
                  data-state="failed"
                >
                  <AlertTriangle size={16} />
                  <div>
                    <strong>{finding.rule_id}</strong>
                    <p>{finding.summary}</p>
                    <small>
                      {finding.subject_scope} · {finding.disposition}
                    </small>
                  </div>
                  <span>{finding.severity}</span>
                </article>
              ))}
            </div>
          )}
          <div className="mcp-builder-limitations">
            <strong>License policy boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <ContractPanel
          key={mutation.data.data.analysis_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
