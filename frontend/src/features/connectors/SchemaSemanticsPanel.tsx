import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileCheck2, RefreshCw, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageSchemaSemantics,
  type ConnectorPackageContentPolicyScan,
} from "../../api/connectors";
import { AuthorityBehaviorPanel } from "./AuthorityBehaviorPanel";

type Props = {
  source: ConnectorPackageContentPolicyScan;
  subjectId: string;
};

export function SchemaSemanticsPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageSchemaSemantics });

  const separated = Boolean(
    ![
      source.scanned_by,
      source.source_inventoried_by,
      source.source_validated_by,
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
            <h3>Independent schema validator required</h3>
            <p>
              Sign in with an authorized identity that did not perform Builder, custody, intake,
              inventory, or content scanning.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-handoff-action">
          <div>
            <p className="eyebrow">VALIDATION PIPELINE STEP 5</p>
            <strong>Validate schema semantics</strong>
            <p>
              Check closed, bounded configuration and capability contracts without resolving
              references or executing code.
            </p>
          </div>
          <label className="confirmation-row">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I am the independent schema validator. I understand draft contracts may block
            promotion without changing the package.
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
              <FileCheck2 size={16} />
            )}
            Validate schema semantics
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Schema validation unavailable</h3>
            <p>
              Exact lineage, package bytes, authorization, or separation of duties did not pass.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE SCHEMA SEMANTICS REPORT</p>
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
              <span>Schemas</span>
              <strong>{mutation.data.data.schemas.length}</strong>
            </div>
            <div>
              <span>Findings</span>
              <strong>{mutation.data.data.findings.length}</strong>
            </div>
            <div>
              <span>Closed contracts</span>
              <strong>
                {mutation.data.data.schemas.filter((schema) => schema.closed_object).length}
              </strong>
            </div>
            <div>
              <span>Promotion</span>
              <strong>{mutation.data.data.promotion_blocked ? "Blocked" : "Not blocked"}</strong>
            </div>
          </div>
          <div className="mcp-builder-validation-checks">
            {mutation.data.data.schemas.map((schema) => (
              <article
                key={schema.digest}
                data-state={schema.semantically_complete ? "passed" : "failed"}
              >
                {schema.semantically_complete ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <AlertTriangle size={16} />
                )}
                <div>
                  <strong>{schema.relative_path}</strong>
                  <p>
                    {schema.property_count} properties, {schema.required_count} required
                  </p>
                </div>
                <span>{schema.purpose}</span>
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
                      {finding.json_pointer}
                    </small>
                  </div>
                  <span>{finding.kind}</span>
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
            <strong>Schema boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <AuthorityBehaviorPanel
          key={mutation.data.data.validation_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
