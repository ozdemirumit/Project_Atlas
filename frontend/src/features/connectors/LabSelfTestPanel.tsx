import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FlaskConical, RefreshCw, UserX } from "lucide-react";
import { useState } from "react";

import {
  validateConnectorPackageLabSelfTest,
  type ConnectorPackageContractValidation,
  type ConnectorPackageRunnerValidation,
} from "../../api/connectors";
import { FinalValidationPanel } from "./FinalValidationPanel";

type Props = {
  source: ConnectorPackageRunnerValidation;
  contractSource: ConnectorPackageContractValidation;
  subjectId: string;
};

export function LabSelfTestPanel({ source, contractSource, subjectId }: Props) {
  const [labPlanId, setLabPlanId] = useState("connector-lab-plan.development-readonly");
  const [labPlanDigest, setLabPlanDigest] = useState(
    "ca40dd40e192ccb62e644cd5151e2445c0fa018f8849ded22eada41a1c93f770",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: validateConnectorPackageLabSelfTest });

  const separated = Boolean(
    ![
      source.validated_by,
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
            <h3>Independent lab operator required</h3>
            <p>
              Runner and prior package actors cannot perform this lab self-test. Continue with a
              different authorized session.
            </p>
          </div>
        </div>
      )}
      {source.outcome === "passed" && separated && !mutation.data && (
        <section className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">READ-ONLY LAB SELF-TEST</p>
              <h3>Validate the approved non-production plan</h3>
              <p>
                The platform resolves target, trust, and short-lived access from the approved
                plan. No write capability is available.
              </p>
            </div>
            <FlaskConical size={24} />
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Approved lab plan ID</span>
              <input
                value={labPlanId}
                onChange={(event) => setLabPlanId(event.target.value)}
                autoComplete="off"
              />
            </label>
            <label>
              <span>Approved plan digest</span>
              <input
                value={labPlanDigest}
                onChange={(event) => setLabPlanDigest(event.target.value)}
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
              I am the independent lab operator. This run is restricted to the approved
              non-production target and read-only C0/C1 capabilities.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={
              !acknowledged ||
              !/^[a-z][a-z0-9_.:-]{2,127}$/.test(labPlanId) ||
              !/^[a-f0-9]{64}$/.test(labPlanDigest) ||
              mutation.isPending
            }
            onClick={() => {
              mutation.mutate({ source, labPlanId, labPlanDigest });
            }}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <FlaskConical size={16} />
            )}
            Run lab self-test
          </button>
        </section>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Lab self-test unavailable</h3>
            <p>
              Exact lineage, plan approval, lease, read-only policy, target identity, or cleanup
              did not reconcile.
            </p>
          </div>
        </div>
      )}
      {mutation.data?.data && (
        <div className="mcp-builder-validation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">IMMUTABLE LAB REPORT</p>
              <strong>{mutation.data.data.self_test_id}</strong>
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
              <span>Target</span>
              <strong>{mutation.data.data.target_alias}</strong>
            </div>
            <div>
              <span>Product</span>
              <strong>{mutation.data.data.product_family}</strong>
            </div>
            <div>
              <span>Version</span>
              <strong>{mutation.data.data.observed_product_version}</strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>{`${mutation.data.data.tested_capability_count}/${mutation.data.data.capability_count}`}</strong>
            </div>
            <div>
              <span>Requests</span>
              <strong>{mutation.data.data.request_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Access</span>
              <strong>{mutation.data.data.credentials_revoked ? "Revoked" : "Unresolved"}</strong>
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
            <strong>Lab boundaries</strong>
            <ul>
              {mutation.data.data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {mutation.data?.data.outcome === "passed" && (
        <FinalValidationPanel
          key={mutation.data.data.self_test_id}
          source={mutation.data.data}
          contractSource={contractSource}
          subjectId={subjectId}
        />
      )}
    </>
  );
}
