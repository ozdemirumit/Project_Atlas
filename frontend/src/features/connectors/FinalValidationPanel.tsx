import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldCheck, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageFinal,
  type ConnectorPackageContractValidation,
  type ConnectorPackageLabSelfTest,
} from "../../api/connectors";
import { PackageApprovalPanel } from "./PackageApprovalPanel";

type Props = {
  source: ConnectorPackageLabSelfTest;
  contractSource: ConnectorPackageContractValidation;
  subjectId: string;
};

export function FinalValidationPanel({ source, contractSource, subjectId }: Props) {
  const [policyId, setPolicyId] = useState("connector-final-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    "bed76a50dd603345e42fb5206b44bead8da5f5ff6a27033913d899dcf7989149",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageFinal });

  const separated = Boolean(
    ![
      source.validated_by,
      source.source_runner_validated_by,
      source.lab_plan_approved_by,
      source.credential_custodied_by,
      contractSource.validated_by,
      contractSource.source_license_analyzed_by,
      contractSource.source_malware_analyzed_by,
      contractSource.source_vulnerability_analyzed_by,
      contractSource.source_static_analyzed_by,
      contractSource.source_authority_validated_by,
      contractSource.source_schema_validated_by,
      contractSource.source_content_scanned_by,
      contractSource.source_inventoried_by,
      contractSource.source_manifest_validated_by,
      contractSource.source_acquired_by,
      contractSource.source_custodied_by,
      contractSource.source_domain_reviewed_by,
      contractSource.source_security_reviewed_by,
      contractSource.source_lab_operated_by,
    ].includes(subjectId),
  );

  return (
    <>
      {source.outcome === "passed" && !separated && !mutation.data && (
        <div className="workspace-message error-state" role="alert">
          <UserX size={20} />
          <div>
            <h3>Independent final validator required</h3>
            <p>No prior package, runner, lab, policy, or custody actor can perform final validation.</p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">GOVERNED FINAL VALIDATION</p>
              <h3>Reconcile the complete evidence chain</h3>
              <p>
                The signed policy evaluates exact lineage, coverage, freshness, limitations, and
                risk. This step cannot approve or operate a connector.
              </p>
            </div>
            <ShieldCheck size={24} />
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Final-validation policy ID</span>
              <input
                value={policyId}
                onChange={(event) => setPolicyId(event.target.value)}
                autoComplete="off"
              />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input
                value={policyDigest}
                onChange={(event) => setPolicyDigest(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            </label>
          </div>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              I am the independent final validator. I understand this creates evidence only and
              does not approve, sign, install, enable, or execute the connector.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={
              !acknowledged ||
              !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
              !/^[a-f0-9]{64}$/.test(policyDigest) ||
              mutation.isPending
            }
            onClick={() => {
              mutation.mutate({ source, policyId, policyDigest });
            }}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ShieldCheck size={16} />
            )}
            Run final validation
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Final validation unavailable</h3>
            <p>
              Exact lineage, actor separation, signed policy, evidence freshness, coverage, or
              risk did not reconcile.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE FINAL REPORT</p>
              <strong>{mutation.data.data.validation_id}</strong>
              <code>{mutation.data.data.canonical_digest}</code>
            </div>
            <span
              className={`state-badge ${
                mutation.data.data.eligible_for_human_approval ? "healthy" : "critical"
              }`}
            >
              {mutation.data.data.eligible_for_human_approval ? (
                <CheckCircle2 size={14} />
              ) : (
                <AlertTriangle size={14} />
              )}
              {mutation.data.data.outcome}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Policy</span>
              <strong>{mutation.data.data.policy_version}</strong>
            </div>
            <div>
              <span>Stages</span>
              <strong>{`${mutation.data.data.passed_stage_count}/${mutation.data.data.stage_count}`}</strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>{`${mutation.data.data.tested_capability_count}/${mutation.data.data.capability_count}`}</strong>
            </div>
            <div>
              <span>Blocking risks</span>
              <strong>{mutation.data.data.blocking_risk_count.toLocaleString()}</strong>
            </div>
          </div>
          <div className="mcp-builder-validation-checks">
            {mutation.data.data.stage_evidence.map((stage) => (
              <article
                key={stage.stage_code}
                data-state={stage.promotion_blocked ? "failed" : "passed"}
              >
                {stage.promotion_blocked ? (
                  <AlertTriangle size={16} />
                ) : (
                  <CheckCircle2 size={16} />
                )}
                <div>
                  <strong>{stage.stage_code}</strong>
                  <p>{stage.evidence_id}</p>
                </div>
                <span>{stage.outcome}</span>
              </article>
            ))}
          </div>
          {mutation.data.data.risks.length > 0 && (
            <div className="mcp-builder-limitations">
              <strong>Risk summary</strong>
              <ul>
                {mutation.data.data.risks.map((risk) => (
                  <li key={risk.code}>
                    {risk.code}: {risk.next_step}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mcp-builder-limitations">
            <strong>Final-validation boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <PackageApprovalPanel
          key={mutation.data.data.validation_id}
          source={mutation.data.data}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
