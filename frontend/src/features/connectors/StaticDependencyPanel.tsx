import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, ScanSearch, UserX } from "lucide-react";
import { useState } from "react";

import {
  analyzeConnectorPackageStaticDependencies,
  type ConnectorPackageAuthorityBehaviorValidation,
} from "../../api/connectors";
import { VulnerabilityPanel } from "./VulnerabilityPanel";

type Props = {
  source: ConnectorPackageAuthorityBehaviorValidation;
  subjectId: string;
};

export function StaticDependencyPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: analyzeConnectorPackageStaticDependencies });

  const separated = Boolean(
    ![
      source.validated_by,
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

  return (
    <>
      {source.outcome === "passed" && !separated && !mutation.data && (
        <div className="workspace-message warning-state" role="status">
          <UserX size={20} />
          <div>
            <h3>Independent static analyst required</h3>
            <p>
              Prior package validators cannot analyze this stage. Continue with a different
              authorized session.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-review-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">STATIC AND DEPENDENCY ANALYSIS</p>
              <h3>Inspect source structure and dependency hygiene</h3>
              <p>Offline structural evidence only. No package code or dependency is loaded.</p>
            </div>
            <span className="state-badge neutral">
              <ScanSearch size={14} /> No execution
            </span>
          </div>
          <label className="mcp-builder-confirmation">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I am the independent static analyst. I understand this does not perform
            vulnerability, malware, license, build, or runtime validation.
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
              <ScanSearch size={16} />
            )}
            Analyze source and dependencies
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Static analysis unavailable</h3>
            <p>Exact lineage, source structure, or dependency hygiene did not pass.</p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE STATIC DEPENDENCY REPORT</p>
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
              <span>Source files</span>
              <strong>{mutation.data.data.source_summary.source_file_count}</strong>
            </div>
            <div>
              <span>Imports</span>
              <strong>{mutation.data.data.source_summary.import_count}</strong>
            </div>
            <div>
              <span>Runtime dependencies</span>
              <strong>{mutation.data.data.dependency_summary.runtime_dependency_count}</strong>
            </div>
            <div>
              <span>Promotion</span>
              <strong>{mutation.data.data.promotion_blocked ? "Blocked" : "Not blocked"}</strong>
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
            <div className="mcp-builder-validation-checks">
              {mutation.data.data.findings.map((finding) => (
                <article key={finding.evidence_fingerprint} data-state="failed">
                  <AlertTriangle size={16} />
                  <div>
                    <strong>{finding.rule_code}</strong>
                    <p>{finding.summary}</p>
                    <code>
                      {finding.relative_path}:{finding.line_number}
                    </code>
                  </div>
                  <span>{finding.category}</span>
                </article>
              ))}
            </div>
          )}
          <div className="mcp-builder-limitations">
            <strong>Static analysis boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <VulnerabilityPanel
          key={mutation.data.data.analysis_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
