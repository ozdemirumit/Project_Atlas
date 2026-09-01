import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FlaskConical, Play, RefreshCw, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageRunner,
  type ConnectorPackageContractValidation,
} from "../../api/connectors";
import { LabSelfTestPanel } from "./LabSelfTestPanel";

type Props = {
  source: ConnectorPackageContractValidation;
  subjectId: string;
};

export function RunnerPanel({ source, subjectId }: Props) {
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageRunner });

  const separated = Boolean(
    ![
      source.validated_by,
      source.source_license_analyzed_by,
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
            <h3>Independent runner validator required</h3>
            <p>
              Contract and prior package actors cannot run this package. Continue with a
              different authorized session.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">ISOLATED RUNNER</p>
              <h3>Exercise disconnected synthetic behavior</h3>
              <p>
                Invoke every accepted capability with the platform harness. Package tests,
                network, credentials, targets, and models remain unavailable.
              </p>
            </div>
            <FlaskConical size={24} />
          </div>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              I am the independent runner validator. This executes only the fixed disconnected
              synthetic harness and grants no runtime authority.
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
              <Play size={16} />
            )}
            Run isolated validation
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Runner validation unavailable</h3>
            <p>
              Exact lineage, archive integrity, process isolation, synthetic behavior, or cleanup
              did not reconcile.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE RUNNER REPORT</p>
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
              <strong>{mutation.data.data.capability_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Invoked</span>
              <strong>{mutation.data.data.invoked_capability_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Fail closed</span>
              <strong>{mutation.data.data.fail_closed_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Bounded results</span>
              <strong>{mutation.data.data.bounded_literal_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Runtime</span>
              <strong>{mutation.data.data.runtime_version}</strong>
            </div>
            <div>
              <span>Workspace</span>
              <strong>{mutation.data.data.workspace_removed ? "Removed" : "Unresolved"}</strong>
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
          <div className="mcp-builder-limitations">
            <strong>Runner boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <LabSelfTestPanel
          key={mutation.data.data.validation_id}
          source={mutation.data.data}
          contractSource={source}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
