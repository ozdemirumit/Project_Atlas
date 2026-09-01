import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, ScanSearch, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageAuthorityBehavior,
  type ConnectorPackageSchemaSemanticsValidation,
} from "../../api/connectors";
import { StaticDependencyPanel } from "./StaticDependencyPanel";

type Props = {
  source: ConnectorPackageSchemaSemanticsValidation;
  subjectId: string;
};

export function AuthorityBehaviorPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageAuthorityBehavior });

  const separated = Boolean(
    ![
      source.validated_by,
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
            <h3>Independent behavior validator required</h3>
            <p>
              The schema validator and all earlier package actors remain separated from
              implementation behavior review.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-handoff-action">
          <div>
            <p className="eyebrow">VALIDATION PIPELINE STEP 6</p>
            <strong>Compare declared authority</strong>
            <p>
              Inspect bounded Python AST evidence without importing, compiling, or executing
              connector code.
            </p>
          </div>
          <label className="confirmation-row">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I am the independent behavior validator. I understand static evidence is limited and
            grants no runtime authority.
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
            Compare authority and behavior
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Behavior validation unavailable</h3>
            <p>Exact lineage, package bytes, authorization, or bounded AST analysis did not pass.</p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE AUTHORITY BEHAVIOR REPORT</p>
              <strong>{mutation.data.data.validation_id}</strong>
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
              <span>Capabilities</span>
              <strong>{mutation.data.data.capabilities.length}</strong>
            </div>
            <div>
              <span>Findings</span>
              <strong>{mutation.data.data.findings.length}</strong>
            </div>
            <div>
              <span>Resolved</span>
              <strong>
                {
                  mutation.data.data.capabilities.filter(
                    (capability) => capability.statically_resolved,
                  ).length
                }
              </strong>
            </div>
            <div>
              <span>Promotion</span>
              <strong>{mutation.data.data.promotion_blocked ? "Blocked" : "Not blocked"}</strong>
            </div>
          </div>
          <div className="mcp-builder-validation-checks">
            {mutation.data.data.capabilities.map((capability) => (
              <article
                key={capability.capability_id}
                data-state={
                  capability.declaration_matches &&
                  capability.permission_matches &&
                  capability.behavior_compatible &&
                  capability.statically_resolved
                    ? "passed"
                    : "failed"
                }
              >
                {capability.behavior_compatible && capability.statically_resolved ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <AlertTriangle size={16} />
                )}
                <div>
                  <strong>{capability.capability_id}</strong>
                  <p>{capability.observed_categories.join(", ")}</p>
                  <small>{capability.required_permission}</small>
                </div>
                <span>{capability.declared_class}</span>
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
                    <small>
                      {finding.relative_path}
                      {finding.line_number > 0 ? `:${finding.line_number}` : ""}
                    </small>
                  </div>
                  <span>{finding.category}</span>
                </article>
              ))}
            </div>
          )}
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
          <div className="mcp-builder-limitations">
            <strong>Behavior boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <StaticDependencyPanel
          key={mutation.data.data.validation_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
