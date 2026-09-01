import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, LockKeyhole, RefreshCw, ShieldCheck, UserX } from "lucide-react";
import { useState } from "react";

import {
  scanConnectorPackageContent,
  type ConnectorPackageSupplyChainInventory,
} from "../../api/connectors";
import { SchemaSemanticsPanel } from "./SchemaSemanticsPanel";

type Props = {
  source: ConnectorPackageSupplyChainInventory;
  subjectId: string;
};

export function ContentPolicyScanPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: scanConnectorPackageContent });

  const separated = Boolean(
    ![
      source.inventoried_by,
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
        <div className="workspace-message error-state" role="alert">
          <UserX size={20} />
          <div>
            <h3>Independent content-policy scan required</h3>
            <p>
              Inventory and prior package actors cannot scan this content. Continue with a
              different authorized session.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">CONTENT POLICY</p>
              <h3>Scan secrets and prohibited content</h3>
              <p>
                Inspect the exact inventory offline. Matched values and source snippets are never
                returned or retained.
              </p>
            </div>
            <span className="state-badge pending">
              <ShieldCheck size={14} /> awaiting scan
            </span>
          </div>
          <label className="mcp-builder-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I am the independent content-policy operator. I understand untrusted package text will
            be inspected without execution.
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
              <ShieldCheck size={16} />
            )}
            Run content-policy scan
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Content-policy scan unavailable</h3>
            <p>
              Exact inventory, package bytes, authorization, or separation of duties did not pass.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE CONTENT-POLICY REPORT</p>
              <strong>{mutation.data.data.scan_id}</strong>
              <code>{mutation.data.data.canonical_digest}</code>
              <small>
                Source inventory: <code>{mutation.data.data.source_inventory_digest}</code>
              </small>
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
              <span>Scanned files</span>
              <strong>{mutation.data.data.scanned_file_count}</strong>
            </div>
            <div>
              <span>Safe findings</span>
              <strong>{mutation.data.data.findings.length}</strong>
            </div>
            <div>
              <span>Secret scan</span>
              <strong>Complete</strong>
            </div>
            <div>
              <span>Promotion</span>
              <strong>{mutation.data.data.promotion_blocked ? "Blocked" : "Not blocked"}</strong>
            </div>
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
                      {finding.line_number ? ` · line ${finding.line_number}` : ""}
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
            <strong>Content-policy boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
          <div className="mcp-builder-boundary">
            <LockKeyhole size={18} />
            <p>
              No raw match is disclosed. Vulnerability, malware, license, code, contract, runner,
              and lab checks remain incomplete. No rejection, trust, execution, or deployment
              authority was granted.
            </p>
          </div>
        </section>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <SchemaSemanticsPanel
          key={mutation.data.data.scan_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
