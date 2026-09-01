import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileCheck2, RefreshCw, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageContracts,
  type ConnectorPackageLicenseAnalysis,
} from "../../api/connectors";
import { RunnerPanel } from "./RunnerPanel";

type Props = {
  source: ConnectorPackageLicenseAnalysis;
  subjectId: string;
};

export function ContractPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageContracts });

  const separated = Boolean(
    ![
      source.analyzed_by,
      source.source_malware_analyzed_by,
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

  return (
    <>
      {source.outcome === "passed" && !separated && !mutation.data && (
        <div className="workspace-message error-state" role="alert">
          <UserX size={20} />
          <div>
            <h3>Independent contract validator required</h3>
            <p>
              License and prior package actors cannot validate this contract. Continue with a
              different authorized session.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">STATIC CONTRACT VALIDATION</p>
              <h3>Validate package contract bindings</h3>
              <p>
                Parse the exact manifest, schemas, handlers, tests, and synthetic fixtures without
                importing or executing package code.
              </p>
            </div>
            <FileCheck2 size={24} />
          </div>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              I am the independent contract validator. This stage proves static consistency only
              and grants no execution authority.
            </span>
          </label>
          <button
            className="primary-button"
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
            Validate contracts
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Contract validation unavailable</h3>
            <p>
              Exact lineage, archive integrity, or a required contract family did not reconcile.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE CONTRACT REPORT</p>
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
              <strong>{mutation.data.data.coverage.capability_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Covered</span>
              <strong>
                {mutation.data.data.coverage.covered_capability_count.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>Contract tests</span>
              <strong>{mutation.data.data.coverage.contract_test_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Orphan artifacts</span>
              <strong>{mutation.data.data.coverage.orphan_artifact_count.toLocaleString()}</strong>
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
                    <small>{finding.artifact_scope}</small>
                  </div>
                  <span>{finding.severity}</span>
                </article>
              ))}
            </div>
          )}
          <div className="mcp-builder-limitations">
            <strong>Contract boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <RunnerPanel
          key={mutation.data.data.validation_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
