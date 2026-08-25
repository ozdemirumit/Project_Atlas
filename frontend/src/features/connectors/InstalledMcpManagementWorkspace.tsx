import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpCircle,
  BookMarked,
  Boxes,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileCheck2,
  KeyRound,
  Link2,
  LogIn,
  PackagePlus,
  Play,
  Power,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCheck,
  UserX,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createBundledConnectorInstance,
  getBundledConnectorCatalog,
  type BundledConnectorDescriptor,
} from "../../api/bundledConnectorCatalog";
import {
  getConnectorCapabilityEnablements,
  type ConnectorCapabilityEnablementInventoryItem,
} from "../../api/capabilityEnablements";
import {
  getConnectorConfigurationValidations,
  toConnectorConfigurationValidationInventoryItem,
  type ConnectorConfigurationValidation,
  type ConnectorConfigurationValidationInventoryItem,
} from "../../api/configurationValidations";
import {
  getConnectorCredentialAssignments,
  type ConnectorCredentialAssignment,
  type ConnectorCredentialAssignmentInventoryItem,
} from "../../api/credentialAssignments";
import {
  assessConnectorUpgradeSigningProviderConformance,
  createConnectorUpgradeApprovalRequest,
  createConnectorUpgradeChangeContextDraft,
  createConnectorUpgradeEvidenceReceipt,
  createConnectorUpgradeSignedEvidenceReceipt,
  decideConnectorUpgradeApproval,
  downloadConnectorUpgradeEvidenceReceipt,
  downloadConnectorUpgradeSignedEvidenceReceipt,
  getConnectorUpgradeApprovalRecord,
  getConnectorUpgradeEvidenceSigningKeyTrustInventory,
  getConnectorUpgradeSigningProviderOnboardingReadiness,
  getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  getLatestConnectorUpgradeSigningProviderConformance,
  getLatestConnectorUpgradeApprovalRevalidation,
  getConnectorUpgradeHandoffReadiness,
  getLatestConnectorUpgradeChangeContextDraft,
  getConnectorUpgradeReadiness,
  isConnectorUpgradeEvidenceReceipt,
  isConnectorUpgradeSignedEvidenceReceipt,
  revalidateConnectorUpgradeApproval,
  verifyConnectorUpgradeEvidenceReceipt,
  verifyConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeApprovalOutcome,
  type ConnectorUpgradeCandidate,
  type ConnectorUpgradeEvidenceReceipt,
  type ConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeSigningProviderConformanceAssessment,
  type ConnectorUpgradeSigningProviderOnboardingReadiness,
  type ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  getConnectorUpgradePlan,
  type ConnectorUpgradePlan,
} from "../../api/connectorUpgradeReadiness";
import {
  createConnectorInstance,
  getConnectorInstanceCreationPolicies,
  getConnectorInstances,
  retireConnectorInstance,
  type ConnectorInstanceRecord,
  type ConnectorInstanceCreationPolicy,
} from "../../api/connectorInstances";
import {
  getConnectorPackageInstallations,
  type ConnectorPackageInstallationReceipt,
} from "../../api/packageInstallations";
import {
  getConnectorInvocationAuthorizations,
  type ConnectorInvocationAuthorizationInventoryItem,
} from "../../api/invocationAuthorizations";
import {
  getConnectorBoundedInvocations,
  type ConnectorBoundedInvocationInventoryItem,
} from "../../api/boundedInvocations";
import {
  getConnectorInvocationEvidence,
  type ConnectorInvocationEvidenceInventoryItem,
} from "../../api/invocationEvidence";
import {
  getOperationalEvidenceKnowledgeDrafts,
  operationalEvidenceKnowledgeDraftQueryKey,
  type OperationalEvidenceKnowledgeDraftInventoryItem,
} from "../../api/evidenceDrafts";
import {
  getOperationalKnowledgeReviewRequests,
  operationalKnowledgeReviewRequestQueryKey,
  type OperationalKnowledgeReviewRequestInventoryItem,
} from "../../api/knowledgeReviewRequests";
import {
  getOperationalKnowledgeReviewerAssignments,
  operationalKnowledgeReviewerAssignmentQueryKey,
  type OperationalKnowledgeReviewerAssignmentClaimStatus,
  type OperationalKnowledgeReviewerAssignmentInventoryEntry,
  type OperationalKnowledgeReviewerAssignmentInventoryItem,
} from "../../api/reviewerAssignments";
import {
  getConnectorRuntimeTrustGrants,
  type ConnectorRuntimeTrustGrantInventoryItem,
} from "../../api/runtimeTrustGrants";
import {
  getConnectorRuntimeActivations,
  type ConnectorRuntimeActivationInventoryItem,
} from "../../api/runtimeActivations";
import {
  deactivateConnectorRuntime,
  getConnectorRuntimeDeactivations,
  type ConnectorRuntimeDeactivation,
} from "../../api/runtimeDeactivations";
import {
  getConnectorSecretBrokerageAuthorizations,
  type ConnectorSecretBrokerageAuthorizationInventoryItem,
} from "../../api/secretBrokerageAuthorizations";
import {
  getConnectorTargetSessionVerifications,
  type ConnectorTargetSessionVerificationInventoryItem,
} from "../../api/targetSessionVerifications";
import {
  getConnectorTargetConfigurations,
  type ConnectorTargetConfigurationBinding,
} from "../../api/targetConfigurations";
import { CredentialAssignmentPanel } from "./CredentialAssignmentPanel";
import { CapabilityEnablementPanel } from "./CapabilityEnablementPanel";
import { ConfigurationValidationPanel } from "./ConfigurationValidationPanel";
import { RuntimeTrustPanel } from "./RuntimeTrustPanel";
import { RuntimeActivationPanel } from "./RuntimeActivationPanel";
import { SecretBrokeragePanel } from "./SecretBrokeragePanel";
import { TargetConfigurationPanel } from "./TargetConfigurationPanel";
import { TargetSessionPanel } from "./TargetSessionPanel";
import { InvocationAuthorizationPanel } from "./InvocationAuthorizationPanel";
import { BoundedInvocationPanel } from "./BoundedInvocationPanel";
import { InvocationEvidencePanel } from "./InvocationEvidencePanel";
import { EvidenceKnowledgeDraftPanel } from "./EvidenceKnowledgeDraftPanel";
import { KnowledgeDraftReviewRequestPanel } from "./KnowledgeDraftReviewRequestPanel";
import { ReviewerAssignmentPanel } from "./ReviewerAssignmentPanel";

type LifecycleFilter = "active" | "retired" | "all";

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function AddMcpDialog({
  catalog,
  packages,
  policies,
  pending,
  onCancel,
  onOpenBuilder,
  onCatalogSubmit,
  onSubmit,
}: {
  catalog: BundledConnectorDescriptor[];
  packages: ConnectorPackageInstallationReceipt[];
  policies: ConnectorInstanceCreationPolicy[];
  pending: boolean;
  onCancel: () => void;
  onOpenBuilder: () => void;
  onCatalogSubmit: (input: Parameters<typeof createBundledConnectorInstance>[0]) => void;
  onSubmit: (input: Parameters<typeof createConnectorInstance>[0]) => void;
}) {
  const [receiptId, setReceiptId] = useState(packages[0]?.receipt_id ?? "");
  const installation = packages.find((item) => item.receipt_id === receiptId) ?? packages[0];
  const [catalogItemId, setCatalogItemId] = useState(catalog[0]?.catalog_item_id ?? "");
  const descriptor = catalog.find((item) => item.catalog_item_id === catalogItemId) ?? catalog[0];
  const source = installation ?? descriptor;
  const policy = policies.find(
    (item) =>
      item.environment_id === installation?.environment_id &&
      item.organization_id === installation.organization_id &&
      item.allowed_sdk_profiles.includes(installation.sdk_profile),
  );
  const [instanceKey, setInstanceKey] = useState(
    source ? `${source.connector_id}-managed` : "",
  );
  const [displayName, setDisplayName] = useState(
    installation
      ? `${installation.connector_id} managed`
      : descriptor
        ? `${descriptor.display_name} managed`
        : "",
  );
  const [purpose, setPurpose] = useState(
    "Create a disabled MCP identity for governed lifecycle management.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const policyId = policy?.policy_id ?? "";
  const policyDigest = policy?.canonical_digest ?? "";
  const valid = Boolean(
    source &&
      /^[a-z][a-z0-9_.:-]{2,127}$/.test(instanceKey) &&
      displayName.trim().length >= 3 &&
      purpose.trim().length >= 20 &&
      (descriptor || /^[a-f0-9]{64}$/.test(policyDigest)) &&
      acknowledged,
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    if (installation) {
      onSubmit({ installation, instanceKey, displayName, policyId, policyDigest, purpose });
    } else if (descriptor) {
      onCatalogSubmit({ descriptor, instanceKey, displayName, purpose });
    }
  };

  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <form className="installed-mcp-dialog" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="add-mcp-title">
        <header>
          <div>
            <p className="eyebrow">GOVERNED INSTANCE</p>
            <h3 id="add-mcp-title">Add MCP</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close Add MCP" onClick={onCancel}><X size={17} /></button>
        </header>
        {source ? (
          <>
            <label>
              <span>{installation ? "Installed package" : "Available MCP"}</span>
              {installation ? (
                <select
                  value={installation.receipt_id}
                  onChange={(event) => {
                    const next = packages.find((item) => item.receipt_id === event.target.value);
                    setReceiptId(event.target.value);
                    if (next) {
                      setInstanceKey(`${next.connector_id}-managed`);
                      setDisplayName(`${next.connector_id} managed`);
                    }
                  }}
                >
                  {packages.map((item) => (
                    <option value={item.receipt_id} key={item.receipt_id}>
                      {item.connector_id} {item.release_version}
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  value={descriptor?.catalog_item_id}
                  onChange={(event) => {
                    const next = catalog.find((item) => item.catalog_item_id === event.target.value);
                    setCatalogItemId(event.target.value);
                    if (next) {
                      setInstanceKey(`${next.connector_id}-managed`);
                      setDisplayName(`${next.display_name} managed`);
                    }
                  }}
                >
                  {catalog.map((item) => (
                    <option value={item.catalog_item_id} key={item.catalog_item_id}>
                      {item.vendor_name} - {item.display_name}
                    </option>
                  ))}
                </select>
              )}
            </label>
            <div className="installed-mcp-form-grid">
              <label>
                <span>Instance key</span>
                <input
                  value={instanceKey}
                  onChange={(event) => setInstanceKey(event.target.value.toLowerCase())}
                  pattern={"[a-z][a-z0-9_.:\\-]{2,127}"}
                  required
                />
              </label>
              <label>
                <span>Display name</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={3} maxLength={200} required />
              </label>
            </div>
            <label>
              <span>Purpose</span>
              <textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} minLength={20} maxLength={1000} rows={3} required />
            </label>
            <div className="installed-mcp-package-facts">
              <span>Package digest <code>{(installation?.package_digest ?? descriptor?.canonical_digest)?.slice(0, 16)}</code></span>
              <span>{installation ? "Publisher" : "Vendor"} <strong>{installation?.publisher_id ?? descriptor?.vendor_name}</strong></span>
            </div>
            {installation && !policy && (
              <div className="installed-mcp-status error-state" role="alert">
                <AlertTriangle size={18} /> No current signed instance policy matches this package.
              </div>
            )}
            <label className="approval-check">
              <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
              <span>The MCP remains disabled and unconfigured. This grants no target, credential, capability, runtime, execution, deployment or infrastructure authority.</span>
            </label>
          </>
        ) : (
          <div className="installed-mcp-empty compact">
            <AlertTriangle size={20} />
            <div><strong>No governed package is installed</strong><span>Complete the Builder, assurance, approval and package installation workflow first.</span></div>
            <button type="button" className="secondary-button" onClick={onOpenBuilder}>
              <PackagePlus size={15} /> Open Builder workflow
            </button>
          </div>
        )}
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="primary-button" disabled={!valid || pending}>
            {pending ? <RefreshCw className="spin" size={16} /> : <PackagePlus size={16} />}
            Add disabled MCP
          </button>
        </footer>
      </form>
    </div>
  );
}

function RetireMcpDialog({
  instance,
  pending,
  onCancel,
  onSubmit,
}: {
  instance: ConnectorInstanceRecord;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const valid = reason.trim().length >= 20 && acknowledged;
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <form className="installed-mcp-dialog retirement" role="dialog" aria-modal="true" aria-labelledby="retire-mcp-title" onSubmit={(event) => { event.preventDefault(); if (valid) onSubmit(reason); }}>
        <header>
          <div><p className="eyebrow">GOVERNED RETIREMENT</p><h3 id="retire-mcp-title">Remove {instance.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close remove MCP" onClick={onCancel}><X size={17} /></button>
        </header>
        <div className="installed-mcp-retirement-impact">
          <Archive size={20} />
          <p>This removes the unused instance from active management. It does not delete its package or evidence, stop a runtime, revoke a credential or contact infrastructure.</p>
        </div>
        <label><span>Retirement reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={20} maxLength={1000} rows={4} required /></label>
        <label className="approval-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I understand that history is preserved and no runtime or infrastructure action is performed.</span></label>
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="installed-mcp-retire" disabled={!valid || pending}>{pending ? <RefreshCw className="spin" size={16} /> : <Archive size={16} />}Confirm retirement</button>
        </footer>
      </form>
    </div>
  );
}

function TargetConfigurationDialog({
  binding,
  instance,
  onBindingCreated,
  onCancel,
  onRequestEnterpriseLogin,
}: {
  binding?: ConnectorTargetConfigurationBinding;
  instance: ConnectorInstanceRecord;
  onBindingCreated: (binding: ConnectorTargetConfigurationBinding) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog target-configuration-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="target-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED TARGET METADATA</p>
            <h3 id="target-mcp-title">Manage target for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close target configuration"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          This boundary binds only signed target metadata. It does not expose endpoints, assign
          credentials, test connectivity, enable the connector, or contact infrastructure.
        </p>
        <TargetConfigurationPanel
          existingBinding={binding}
          instance={instance}
          onBindingCreated={onBindingCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function CredentialAssignmentDialog({
  assignment,
  binding,
  instance,
  onAssignmentCreated,
  onCancel,
  onRequestEnterpriseLogin,
}: {
  assignment?: ConnectorCredentialAssignmentInventoryItem;
  binding: ConnectorTargetConfigurationBinding;
  instance: ConnectorInstanceRecord;
  onAssignmentCreated: (assignment: ConnectorCredentialAssignment) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog credential-assignment-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="credential-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED CREDENTIAL METADATA</p>
            <h3 id="credential-mcp-title">Manage credentials for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close credential assignment"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          This boundary assigns only signed credential metadata. It does not expose or resolve
          secrets, test connectivity, enable the connector, grant runtime authority, or contact
          infrastructure.
        </p>
        <CredentialAssignmentPanel
          binding={binding}
          existingAssignment={assignment}
          onAssignmentCreated={onAssignmentCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function ConfigurationValidationDialog({
  assignment,
  instance,
  onValidationCreated,
  onCancel,
  onRequestEnterpriseLogin,
  validation,
  sessionScopeKey,
}: {
  assignment: ConnectorCredentialAssignmentInventoryItem;
  instance: ConnectorInstanceRecord;
  onValidationCreated: (validation: ConnectorConfigurationValidation) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
  validation?: ConnectorConfigurationValidationInventoryItem;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog configuration-validation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="validation-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED PROBE EVIDENCE</p>
            <h3 id="validation-mcp-title">Validate configuration for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close configuration validation"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas verifies separately produced signed, read-only probe evidence. It does not resolve
          credentials, connect to the target, run a probe, enable capabilities, or grant runtime
          authority.
        </p>
        <ConfigurationValidationPanel
          assignment={assignment}
          existingValidation={validation}
          onValidationCreated={onValidationCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function CapabilityEnablementDialog({
  enablement,
  instance,
  onCancel,
  onEnablementCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
  validation,
}: {
  enablement?: ConnectorCapabilityEnablementInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onEnablementCreated: (enablement: ConnectorCapabilityEnablementInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
  validation: ConnectorConfigurationValidationInventoryItem;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog capability-enablement-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="capability-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED C0/C1 CAPABILITIES</p>
            <h3 id="capability-mcp-title">Manage capabilities for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close capability governance"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas applies only a server-provided signed capability profile and policy for this exact
          validated configuration. It does not resolve credentials, contact the target, start a
          connector, grant runtime trust, execute, or deploy anything.
        </p>
        <CapabilityEnablementPanel
          validation={validation}
          existingEnablement={enablement}
          onEnablementCreated={onEnablementCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function RuntimeTrustDialog({
  enablement,
  grant,
  instance,
  onCancel,
  onGrantCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  enablement: ConnectorCapabilityEnablementInventoryItem;
  grant?: ConnectorRuntimeTrustGrantInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onGrantCreated: (grant: ConnectorRuntimeTrustGrantInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog runtime-trust-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runtime-trust-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED RUNTIME ADMISSION</p>
            <h3 id="runtime-trust-mcp-title">Manage runtime trust for {instance.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close runtime trust"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas binds only a server-provided signed runtime profile and trust policy for this exact
          capability enablement. It does not start a connector, load a package, resolve secrets,
          contact a target, invoke capabilities, execute, deploy or mutate infrastructure.
        </p>
        <RuntimeTrustPanel
          enablement={enablement}
          existingGrant={grant}
          onGrantCreated={onGrantCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function SecretBrokerageDialog({
  authorization,
  instance,
  onAuthorizationCreated,
  onCancel,
  onRequestEnterpriseLogin,
  runtimeTrust,
  sessionScopeKey,
}: {
  authorization?: ConnectorSecretBrokerageAuthorizationInventoryItem;
  instance: ConnectorInstanceRecord;
  onAuthorizationCreated: (
    authorization: ConnectorSecretBrokerageAuthorizationInventoryItem,
  ) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
  runtimeTrust: ConnectorRuntimeTrustGrantInventoryItem;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog secret-brokerage-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="secret-brokerage-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED SECRET BROKERAGE</p>
            <h3 id="secret-brokerage-mcp-title">
              Manage secret brokerage for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close secret brokerage"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas authorizes only a server-provided signed brokerage profile and policy for this exact
          runtime trust grant. It does not resolve or deliver a secret, issue a lease, start a
          connector, connect, invoke, execute, deploy or mutate infrastructure.
        </p>
        <SecretBrokeragePanel
          runtimeTrust={runtimeTrust}
          existingAuthorization={authorization}
          onAuthorizationCreated={onAuthorizationCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function RuntimeActivationDialog({
  activation,
  brokerage,
  instance,
  onActivationCreated,
  onCancel,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  activation?: ConnectorRuntimeActivationInventoryItem;
  brokerage: ConnectorSecretBrokerageAuthorizationInventoryItem;
  instance: ConnectorInstanceRecord;
  onActivationCreated: (activation: ConnectorRuntimeActivationInventoryItem) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog runtime-activation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runtime-activation-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED RUNTIME ACTIVATION</p>
            <h3 id="runtime-activation-mcp-title">
              Manage runtime activation for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close runtime activation"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas activates only a server-provided signed isolated runtime boundary and verifies
          bounded local health. It exposes no credential material and does not connect to a target,
          invoke a capability, execute, deploy or mutate infrastructure.
        </p>
        <RuntimeActivationPanel
          brokerage={brokerage}
          existingActivation={activation}
          onActivationCreated={onActivationCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function RuntimeDeactivationDialog({
  activation,
  instance,
  onCancel,
  onDeactivated,
}: {
  activation: ConnectorRuntimeActivationInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onDeactivated: (deactivation: ConnectorRuntimeDeactivation) => void;
}) {
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () => deactivateConnectorRuntime({ activation, reason }),
    onSuccess: onDeactivated,
  });
  const boundedReason = reason.trim();

  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog runtime-activation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runtime-deactivation-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">RUNTIME CONTROL</p>
            <h3 id="runtime-deactivation-mcp-title">
              Disable runtime for {instance.display_name}
            </h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close runtime deactivation" onClick={onCancel}>
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          This stops the Atlas connector runtime and revokes its target authority. It does not
          contact or change the managed infrastructure.
        </p>
        <form
          className="installed-mcp-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <label>
            Reason
            <textarea
              value={reason}
              minLength={20}
              maxLength={1000}
              required
              placeholder="Explain why this Atlas runtime is being disabled."
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          {mutation.isError && (
            <p className="inline-error" role="alert">
              {mutation.error instanceof Error ? mutation.error.message : "Runtime deactivation failed"}
            </p>
          )}
          <footer>
            <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
            <button
              type="submit"
              className="primary-button"
              disabled={boundedReason.length < 20 || mutation.isPending}
            >
              <Power size={16} />
              {mutation.isPending ? "Disabling..." : "Disable runtime"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function TargetSessionDialog({
  activation,
  instance,
  onCancel,
  onRequestEnterpriseLogin,
  onVerificationCreated,
  sessionScopeKey,
  verification,
}: {
  activation: ConnectorRuntimeActivationInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
  onVerificationCreated: (
    verification: ConnectorTargetSessionVerificationInventoryItem,
  ) => void;
  sessionScopeKey: string;
  verification?: ConnectorTargetSessionVerificationInventoryItem;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog target-session-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="target-session-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED TARGET SESSION VERIFICATION</p>
            <h3 id="target-session-mcp-title">
              Manage target session for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close target session"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas uses only a server-provided signed profile and policy to verify one bounded
          read-only target session. The session, delivery channel and lease are closed immediately;
          no reusable connection, capability invocation, execution, deployment or infrastructure
          mutation authority remains.
        </p>
        <TargetSessionPanel
          activation={activation}
          existingVerification={verification}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          onVerificationCreated={onVerificationCreated}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function InvocationAuthorizationDialog({
  authorization,
  instance,
  onAuthorizationCreated,
  onCancel,
  onRequestEnterpriseLogin,
  sessionScopeKey,
  targetSession,
}: {
  authorization?: ConnectorInvocationAuthorizationInventoryItem;
  instance: ConnectorInstanceRecord;
  onAuthorizationCreated: (
    authorization: ConnectorInvocationAuthorizationInventoryItem,
  ) => void;
  onCancel: () => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
  targetSession: ConnectorTargetSessionVerificationInventoryItem;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog invocation-authorization-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="invocation-authorization-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">GOVERNED INVOCATION AUTHORIZATION</p>
            <h3 id="invocation-authorization-mcp-title">
              Manage invocation authorization for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close invocation authorization"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas authorizes only a server-provided exact capability, profile, input envelope and
          policy for the verified closed target session. This step does not invoke, schedule,
          execute, deploy or mutate infrastructure.
        </p>
        <InvocationAuthorizationPanel
          targetSession={targetSession}
          existingAuthorization={authorization}
          onAuthorizationCreated={onAuthorizationCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function BoundedInvocationDialog({
  authorization,
  instance,
  invocation,
  onCancel,
  onInvocationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  authorization: ConnectorInvocationAuthorizationInventoryItem;
  instance: ConnectorInstanceRecord;
  invocation?: ConnectorBoundedInvocationInventoryItem;
  onCancel: () => void;
  onInvocationCreated: (invocation: ConnectorBoundedInvocationInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog bounded-invocation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bounded-invocation-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">ATOMIC SINGLE-USE READ</p>
            <h3 id="bounded-invocation-mcp-title">
              Manage bounded invocation for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close bounded invocation"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas consumes one exact current authorization using only a server-provided signed option.
          The immutable completion proves cleanup and grants no retry, evidence ingestion,
          scheduling, execution, deployment or infrastructure mutation authority.
        </p>
        <BoundedInvocationPanel
          authorization={authorization}
          existingInvocation={invocation}
          onInvocationCreated={onInvocationCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function InvocationEvidenceDialog({
  invocation,
  instance,
  evidence,
  onCancel,
  onEvidenceCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  invocation: ConnectorBoundedInvocationInventoryItem;
  instance: ConnectorInstanceRecord;
  evidence?: ConnectorInvocationEvidenceInventoryItem;
  onCancel: () => void;
  onEvidenceCreated: (evidence: ConnectorInvocationEvidenceInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog invocation-evidence-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="invocation-evidence-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">IMMUTABLE OPERATIONAL EVIDENCE</p>
            <h3 id="invocation-evidence-mcp-title">
              Manage invocation evidence for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close invocation evidence"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas claims one exact completed invocation using only a server-provided signed option.
          Preservation is one-way and creates no knowledge, scheduling, workflow, execution,
          deployment or infrastructure mutation authority.
        </p>
        <InvocationEvidencePanel
          invocation={invocation}
          existingEvidence={evidence}
          onEvidenceCreated={onEvidenceCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function EvidenceKnowledgeDraftDialog({
  evidence,
  instance,
  onCancel,
  onDraftCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  evidence: ConnectorInvocationEvidenceInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onDraftCreated: (draft: OperationalEvidenceKnowledgeDraftInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog evidence-knowledge-draft-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-knowledge-draft-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">UNAPPROVED KNOWLEDGE DRAFT</p>
            <h3 id="evidence-knowledge-draft-mcp-title">
              Curate knowledge for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close knowledge draft"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas may create one immutable draft from this exact evidence using a server-provided
          signed option. This stage grants no review, publication, retrieval, model, workflow,
          execution, deployment or infrastructure mutation authority.
        </p>
        <EvidenceKnowledgeDraftPanel
          evidence={evidence}
          onDraftCreated={onDraftCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function KnowledgeDraftReviewRequestDialog({
  draft,
  instance,
  onCancel,
  onRequestCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: {
  draft: OperationalEvidenceKnowledgeDraftInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onRequestCreated: (reviewRequest: OperationalKnowledgeReviewRequestInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}) {
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog evidence-knowledge-draft-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="knowledge-review-request-mcp-title"
      >
        <header>
          <div>
            <p className="eyebrow">UNASSIGNED REVIEW REQUEST</p>
            <h3 id="knowledge-review-request-mcp-title">
              Request knowledge review for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close knowledge review request"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas may create one unassigned review request using an exact server-provided signed
          option. This stage exposes no protected content and grants no assignment, decision,
          approval, publication, model, workflow, execution or deployment authority.
        </p>
        <KnowledgeDraftReviewRequestPanel
          draft={draft}
          onRequestCreated={onRequestCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function ReviewerAssignmentDialog({
  reviewRequest,
  instance,
  onCancel,
  onAssignmentCreated,
  onRequestEnterpriseLogin,
  returnFocusTo,
  sessionScopeKey,
}: {
  reviewRequest: OperationalKnowledgeReviewRequestInventoryItem;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onAssignmentCreated: (
    assignment: OperationalKnowledgeReviewerAssignmentInventoryItem,
  ) => void;
  onRequestEnterpriseLogin?: () => void;
  returnFocusTo: HTMLElement | null;
  sessionScopeKey: string;
}) {
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.querySelector<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
    )?.focus();
    return () => returnFocusTo?.focus();
  }, [returnFocusTo]);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
    ));
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="installed-mcp-dialog evidence-knowledge-draft-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reviewer-assignment-mcp-title"
        aria-describedby="reviewer-assignment-mcp-description"
        onKeyDown={handleKeyDown}
      >
        <header>
          <div>
            <p className="eyebrow">INDEPENDENT REVIEW TRACKS</p>
            <h3 id="reviewer-assignment-mcp-title">
              Assign reviewers for {instance.display_name}
            </h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close reviewer assignment"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy" id="reviewer-assignment-mcp-description">
          Atlas may assign distinct domain and security review tracks using an exact server-provided
          signed option. Reviewer identity and protected content remain unavailable, and no
          inspection, decision, approval, publication, workflow or operational authority is granted.
        </p>
        <ReviewerAssignmentPanel
          reviewRequest={reviewRequest}
          onAssignmentCreated={onAssignmentCreated}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          sessionScopeKey={sessionScopeKey}
        />
        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}

function UpgradeCandidateCard({
  candidate,
  onReviewPlan,
}: {
  candidate: ConnectorUpgradeCandidate;
  onReviewPlan: () => void;
}) {
  const changes = [
    ...candidate.capability_changes.map(
      (item) => `${item.change_type}: ${item.capability_id}`,
    ),
    ...candidate.target_products_added.map((item) => `target added: ${item}`),
    ...candidate.target_products_removed.map((item) => `target removed: ${item}`),
    ...candidate.network_destinations_added.map((item) => `network added: ${item}`),
    ...candidate.network_destinations_removed.map((item) => `network removed: ${item}`),
  ];
  return (
    <article className="installed-mcp-upgrade-candidate">
      <header>
        <div><strong>{candidate.release_version}</strong><span>{candidate.upgrade_class} update</span></div>
        <span className={`installed-mcp-risk ${candidate.risk_level}`}>{candidate.risk_level} risk</span>
      </header>
      <dl className="installed-mcp-upgrade-facts">
        <div><dt>Publisher</dt><dd>{candidate.publisher_id}</dd></div>
        <div><dt>SDK profile</dt><dd>{candidate.sdk_profile}</dd></div>
        <div><dt>Policy review</dt><dd>{candidate.policy_review_required ? "Required" : "Not required"}</dd></div>
        <div><dt>Configuration migration</dt><dd>{candidate.configuration_migration_required ? "Required" : "Not required"}</dd></div>
      </dl>
      <div className="installed-mcp-upgrade-changes">
        <strong>Manifest changes</strong>
        {changes.length ? <ul>{changes.map((item) => <li key={item}>{item}</li>)}</ul> : <span>No capability, target or network changes.</span>}
        <span>Configuration keys {candidate.configuration_key_delta >= 0 ? "+" : ""}{candidate.configuration_key_delta}; secret references {candidate.secret_reference_delta >= 0 ? "+" : ""}{candidate.secret_reference_delta}</span>
      </div>
      <div className="installed-mcp-rollback"><Archive size={15} /><span>Rollback anchor <code>{candidate.rollback_receipt_id}</code></span></div>
      {!candidate.review_eligible && <div className="installed-mcp-status error-state"><AlertTriangle size={17} /><span>Review blocked: {candidate.blockers.join(", ")}</span></div>}
      <button type="button" className="secondary-button installed-mcp-plan-button" onClick={onReviewPlan}><ClipboardList size={15} />Review plan for {candidate.release_version}</button>
    </article>
  );
}

function UpgradePlanEvidence({ plan, subjectId }: { plan: ConnectorUpgradePlan; subjectId: string }) {
  const interruption = plan.estimated_interruption_min_minutes === null
    ? "Not established"
    : `${plan.estimated_interruption_min_minutes}-${plan.estimated_interruption_max_minutes} minutes`;
  return (
    <section className="installed-mcp-plan" aria-labelledby="connector-upgrade-plan-title">
      <header>
        <div><p className="eyebrow">NON-EXECUTABLE PLAN</p><h4 id="connector-upgrade-plan-title">{plan.current_release_version} to {plan.candidate_release_version}</h4></div>
        <span className={`state-badge ${plan.plan_eligible ? "pending" : "blocked"}`}>{plan.plan_state.replaceAll("_", " ")}</span>
      </header>
      <div className="installed-mcp-plan-summary"><span>Interruption <strong>{interruption}</strong></span><span>Rollback window <strong>{plan.rollback_window_minutes} minutes</strong></span><span>Human approval <strong>Required</strong></span></div>
      {plan.blockers.length > 0 && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><div><strong>Plan blocked</strong><span>{plan.blockers.join(", ")}</span></div></div>}
      <div className="installed-mcp-plan-columns">
        <div><strong>Prerequisites</strong><ul>{plan.prerequisite_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><strong>Ordered plan</strong><ol>{plan.steps.map((step) => <li key={step.step_id}><span>{step.phase.replaceAll("_", " ")}</span><small>{step.expected_minutes} min{step.requires_service_interruption ? " | interruption" : ""}</small></li>)}</ol></div>
        <div><strong>Stop conditions</strong><ul>{plan.stop_condition_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><strong>Rollback</strong><ol>{plan.rollback_step_ids.map((item) => <li key={item}>{item}</li>)}</ol></div>
        <div><strong>Post-validation</strong><ul>{plan.validation_check_ids.map((item) => <li key={item}>{item}</li>)}</ul></div>
      </div>
      {plan.unknowns.length > 0 && <div className="installed-mcp-plan-unknowns"><strong>Unknowns</strong><ul>{plan.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>}
      <p className="installed-mcp-plan-boundary">This plan does not rebind a package, migrate configuration, stop a session, contact a target, restore data or authorize execution.</p>
      {plan.plan_eligible && <UpgradeApprovalRequestPanel plan={plan} subjectId={subjectId} />}
    </section>
  );
}

const APPROVAL_OUTCOMES: Array<{ value: ConnectorUpgradeApprovalOutcome; label: string }> = [
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "needs_evidence", label: "Request evidence" },
  { value: "defer", label: "Defer" },
];

function UpgradeApprovalRequestPanel({ plan, subjectId }: { plan: ConnectorUpgradePlan; subjectId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["connector-upgrade-approval-record", plan.source_record_id, plan.candidate_receipt_id];
  const [purpose, setPurpose] = useState(
    "Submit this exact connector upgrade plan for independent human review.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const [outcome, setOutcome] = useState<ConnectorUpgradeApprovalOutcome | null>(null);
  const [rationale, setRationale] = useState("");
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const [revalidationPurpose, setRevalidationPurpose] = useState(
    "Revalidate the exact approved plan without granting handoff authority.",
  );
  const [revalidationAcknowledged, setRevalidationAcknowledged] = useState(false);
  const [changeJustification, setChangeJustification] = useState("Prepare this exact connector upgrade for governed ITSM and maintenance-window review.");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [changeAcknowledged, setChangeAcknowledged] = useState(false);
  const [receiptAcknowledged, setReceiptAcknowledged] = useState(false);
  const [signatureAcknowledged, setSignatureAcknowledged] = useState(false);
  const [verificationReceipt, setVerificationReceipt] =
    useState<ConnectorUpgradeEvidenceReceipt | null>(null);
  const [verificationSignedReceipt, setVerificationSignedReceipt] =
    useState<ConnectorUpgradeSignedEvidenceReceipt | null>(null);
  const [verificationFileName, setVerificationFileName] = useState("");
  const [verificationFileError, setVerificationFileError] = useState("");
  const [verificationAcknowledged, setVerificationAcknowledged] = useState(false);
  const recordQuery = useQuery({
    queryKey,
    queryFn: () => getConnectorUpgradeApprovalRecord(plan),
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: createConnectorUpgradeApprovalRequest,
    onSuccess: (request) => {
      setAcknowledged(false);
      queryClient.setQueryData(queryKey, {
        request,
        decision: null,
        state: "pending",
        approval_valid: false,
        approval_granted: false,
        decision_recorded: false,
        separation_of_duties_enforced: true,
        package_rebound: false,
        configuration_changed: false,
        target_contacted: false,
        execution_authorized: false,
        infrastructure_mutation_performed: false,
      });
    },
  });
  const decisionMutation = useMutation({
    mutationFn: decideConnectorUpgradeApproval,
    onSuccess: (record) => {
      queryClient.setQueryData(queryKey, record);
      setDecisionAcknowledged(false);
    },
  });
  const record = decisionMutation.data ?? recordQuery.data;
  const revalidationQueryKey = ["connector-upgrade-approval-revalidation", record?.request.request_id];
  const revalidationQuery = useQuery({
    queryKey: revalidationQueryKey,
    queryFn: () => getLatestConnectorUpgradeApprovalRevalidation(record!),
    enabled: record?.state === "approved" && record.decision?.outcome === "approve",
    retry: false,
  });
  const revalidationMutation = useMutation({
    mutationFn: revalidateConnectorUpgradeApproval,
    onSuccess: (revalidation) => {
      queryClient.setQueryData(revalidationQueryKey, revalidation);
      setRevalidationAcknowledged(false);
    },
  });
  const pending = record?.state === "pending" && record.decision === null;
  const requesterIsCurrentSubject = record?.request.requested_by === subjectId;
  const revalidation = revalidationMutation.data ?? revalidationQuery.data;
  const handoffReadinessQuery = useQuery({
    queryKey: ["connector-upgrade-handoff-readiness", record?.request.request_id, revalidation?.canonical_digest],
    queryFn: () => getConnectorUpgradeHandoffReadiness(record!),
    enabled: Boolean(revalidation),
    retry: false,
  });
  const evidenceReceiptMutation = useMutation({
    mutationFn: createConnectorUpgradeEvidenceReceipt,
    onSuccess: () => setReceiptAcknowledged(false),
  });
  const evidenceReceiptVerificationMutation = useMutation({
    mutationFn: verifyConnectorUpgradeEvidenceReceipt,
    onSuccess: () => setVerificationAcknowledged(false),
  });
  const signedEvidenceReceiptMutation = useMutation({
    mutationFn: createConnectorUpgradeSignedEvidenceReceipt,
    onSuccess: () => setSignatureAcknowledged(false),
  });
  const signedEvidenceVerificationMutation = useMutation({
    mutationFn: verifyConnectorUpgradeSignedEvidenceReceipt,
    onSuccess: () => setVerificationAcknowledged(false),
  });
  const changeContextQueryKey = ["connector-upgrade-change-context", record?.request.request_id];
  const changeContextQuery = useQuery({
    queryKey: changeContextQueryKey,
    queryFn: () => getLatestConnectorUpgradeChangeContextDraft(record!),
    enabled: Boolean(revalidation), retry: false,
  });
  const changeContextMutation = useMutation({
    mutationFn: createConnectorUpgradeChangeContextDraft,
    onSuccess: (draft) => {
      queryClient.setQueryData(changeContextQueryKey, draft);
      setChangeAcknowledged(false);
    },
  });
  const canRevalidate = Boolean(
    record?.state === "approved" && record.decision?.outcome === "approve" &&
    subjectId !== record.request.requested_by && subjectId !== record.decision.decided_by,
  );
  const canCreateChangeContext = revalidation?.revalidated_by === subjectId;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!acknowledged || purpose.trim().length < 20) return;
    mutation.mutate({ plan, purpose });
  };
  if (record) {
    return (
      <section className="installed-mcp-approval-request" aria-live="polite">
        <div className="installed-mcp-approval-heading"><ShieldCheck size={18} /><div><strong>{record.state === "pending" ? "Pending human review" : `Human decision: ${record.state.replaceAll("_", " ")}`}</strong><span>{record.request.request_id}</span></div></div>
        <dl><div><dt>Exact plan</dt><dd>{record.request.plan_digest.slice(0, 16)}</dd></div><div><dt>Expires</dt><dd>{new Date(record.request.expires_at).toLocaleString()}</dd></div><div><dt>Separation</dt><dd>Requester cannot decide</dd></div></dl>
        {pending && requesterIsCurrentSubject && <div className="installed-mcp-status error-state" role="status"><UserX size={17} /><div><strong>Independent approver required</strong><span>{record.request.requested_by} cannot decide this request.</span></div></div>}
        {pending && !requesterIsCurrentSubject && (
          <div className="installed-mcp-approval-decision">
            <div className="installed-mcp-approval-outcomes" role="group" aria-label="Approval decision">
              {APPROVAL_OUTCOMES.map((item) => <button type="button" key={item.value} aria-pressed={outcome === item.value} onClick={() => setOutcome(item.value)}>{item.label}</button>)}
            </div>
            <label>Decision rationale<textarea value={rationale} minLength={20} maxLength={1000} onChange={(event) => setRationale(event.target.value)} /></label>
            <label className="checkbox-row"><input type="checkbox" checked={decisionAcknowledged} onChange={(event) => setDecisionAcknowledged(event.target.checked)} /><span>This records a human decision only. It grants no package, runtime or execution authority.</span></label>
            {decisionMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The decision was rejected because identity, policy, expiry or exact plan evidence changed.</span></div>}
            <button className="primary-button" type="button" disabled={!outcome || rationale.trim().length < 20 || !decisionAcknowledged || decisionMutation.isPending} onClick={() => { if (outcome) decisionMutation.mutate({ record, outcome, rationale }); }}><UserCheck size={16} />{decisionMutation.isPending ? "Recording decision..." : "Record decision"}</button>
          </div>
        )}
        {record.decision && <div className="installed-mcp-approval-result"><strong>{record.decision.outcome.replaceAll("_", " ")}</strong><span>{record.decision.decided_by}</span><p>{record.decision.rationale}</p><small>{new Date(record.decision.decided_at).toLocaleString()}</small></div>}
        {record.state === "approved" && record.decision?.outcome === "approve" && (
          <div className="installed-mcp-approval-decision">
            <div className="installed-mcp-approval-heading"><UserCheck size={18} /><div><strong>Independent approval revalidation</strong><span>A third person verifies the exact request, decision, plan and policy lineage.</span></div></div>
            {revalidation ? (
              <div className="installed-mcp-approval-result">
                <strong>Governance ready</strong>
                <span>Revalidated by {revalidation.revalidated_by}</span>
                <p>Approval was current at revalidation. Handoff remains blocked.</p>
                <small>Valid until {new Date(revalidation.valid_until).toLocaleString()}</small>
                <ul>{revalidation.check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul>
                {handoffReadinessQuery.data && (
                  <div className={`installed-mcp-status ${handoffReadinessQuery.data.assessment_state === "blocked" ? "error-state" : ""}`} role="status">
                    {handoffReadinessQuery.data.assessment_state === "blocked" ? <AlertTriangle size={17} /> : <ShieldCheck size={17} />}
                    <div>
                      <strong>{handoffReadinessQuery.data.assessment_state === "blocked" ? "Handoff blocked" : "Evidence review complete"}</strong>
                      <span>No artifact was issued and the approval remains unconsumed.</span>
                      {handoffReadinessQuery.data.blocker_ids.length > 0 && <><p>Required evidence missing</p><ul>{handoffReadinessQuery.data.blocker_ids.map((blockerId) => <li key={blockerId}>{blockerId}</li>)}</ul></>}
                      <p>Satisfied checks</p>
                      <ul>{handoffReadinessQuery.data.satisfied_check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul>
                      {handoffReadinessQuery.data.audit_readiness_evidence_current && <p>Audit readiness evidence verified and bound to this exact revalidation.</p>}
                      {handoffReadinessQuery.data.itsm_change_evidence_current && <p>Authoritative ITSM change evidence verified and bound to this exact plan.</p>}
                      {handoffReadinessQuery.data.maintenance_window_evidence_current && <p>Approved maintenance-window evidence is current. No handoff or execution authority was issued.</p>}
                      {handoffReadinessQuery.data.not_applicable_check_ids.length > 0 && <><p>Not applicable in this context</p><ul>{handoffReadinessQuery.data.not_applicable_check_ids.map((checkId) => <li key={checkId}>{checkId}</li>)}</ul></>}
                      <small>Applicability policy {handoffReadinessQuery.data.applicability_policy_version}</small>
                    </div>
                  </div>
                )}
                {handoffReadinessQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Handoff readiness could not be assessed from current governed evidence.</span></div>}
                {handoffReadinessQuery.data?.assessment_state === "evidence_complete" && (
                  <>
                    <div className="installed-mcp-approval-decision">
                      <strong>Non-executable evidence receipt</strong>
                      <p>Preserve the exact completed review as a safe JSON record. The receipt cannot be used by a runtime and grants no handoff authority.</p>
                      {evidenceReceiptMutation.data ? (
                        <div className="installed-mcp-approval-result">
                          <strong>Evidence receipt ready</strong>
                          <span>{evidenceReceiptMutation.data.receipt_id}</span>
                          <p>Runtime acceptable: no. Approval consumed: no.</p>
                          <small>Valid until {new Date(evidenceReceiptMutation.data.valid_until).toLocaleString()}</small>
                          <button className="secondary-button" type="button" onClick={() => downloadConnectorUpgradeEvidenceReceipt(evidenceReceiptMutation.data)}><Download size={16} />Download JSON receipt</button>
                          {signedEvidenceReceiptMutation.data ? (
                            <div className="installed-mcp-status" role="status">
                              <ShieldCheck size={17} />
                              <div>
                                <strong>Origin authenticated</strong>
                                <span>{signedEvidenceReceiptMutation.data.signature.key_id} / {signedEvidenceReceiptMutation.data.signature.key_version}</span>
                                <p>Signature grants no approval, handoff, runtime or execution authority.</p>
                                <button className="secondary-button" type="button" onClick={() => downloadConnectorUpgradeSignedEvidenceReceipt(signedEvidenceReceiptMutation.data)}><Download size={16} />Download signed receipt</button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <label className="checkbox-row"><input type="checkbox" checked={signatureAcknowledged} onChange={(event) => setSignatureAcknowledged(event.target.checked)} /><span>Authenticate Atlas origin only. The signature is not approval or execution authority.</span></label>
                              {signedEvidenceReceiptMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Origin authentication is unavailable or the receipt is no longer current.</span></div>}
                              <button className="secondary-button" type="button" disabled={!signatureAcknowledged || signedEvidenceReceiptMutation.isPending} onClick={() => signedEvidenceReceiptMutation.mutate({ record, receipt: evidenceReceiptMutation.data })}><ShieldCheck size={16} />{signedEvidenceReceiptMutation.isPending ? "Authenticating origin..." : "Authenticate Atlas origin"}</button>
                            </>
                          )}
                        </div>
                      ) : (
                        <>
                          <label className="checkbox-row"><input type="checkbox" checked={receiptAcknowledged} onChange={(event) => setReceiptAcknowledged(event.target.checked)} /><span>This receipt is evidence only. It grants no approval, handoff, runtime or execution authority.</span></label>
                          {evidenceReceiptMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The receipt was rejected because current governed evidence changed.</span></div>}
                          <button className="primary-button" type="button" disabled={!receiptAcknowledged || evidenceReceiptMutation.isPending} onClick={() => evidenceReceiptMutation.mutate({ record, readiness: handoffReadinessQuery.data! })}><ClipboardList size={16} />{evidenceReceiptMutation.isPending ? "Creating receipt..." : "Create evidence receipt"}</button>
                        </>
                      )}
                    </div>
                    <div className="installed-mcp-approval-decision">
                      <strong>Verify evidence receipt</strong>
                      <label className="installed-mcp-receipt-file"><FileCheck2 size={18} /><span><strong>{verificationFileName || "Select receipt JSON"}</strong><small>JSON, maximum 64 KB</small></span><input aria-label="Receipt JSON" type="file" accept=".json,application/json" onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        setVerificationFileError("");
                        setVerificationReceipt(null);
                        setVerificationSignedReceipt(null);
                        setVerificationFileName(file?.name ?? "");
                        setVerificationAcknowledged(false);
                        evidenceReceiptVerificationMutation.reset();
                        signedEvidenceVerificationMutation.reset();
                        if (!file) return;
                        if (file.size > 65_536) {
                          setVerificationFileError("The receipt exceeds the 64 KB verification limit.");
                          return;
                        }
                        void file.text().then((content) => {
                          try {
                            const candidate: unknown = JSON.parse(content);
                            if (isConnectorUpgradeSignedEvidenceReceipt(candidate) && candidate.request_id === record.request.request_id) {
                              setVerificationSignedReceipt(candidate);
                            } else if (isConnectorUpgradeEvidenceReceipt(candidate) && candidate.request_id === record.request.request_id) {
                              setVerificationReceipt(candidate);
                            } else {
                              throw new Error("unsafe receipt");
                            }
                          } catch {
                            setVerificationFileError("The file is not a safe receipt for this exact approval request.");
                          }
                        });
                      }} /></label>
                      {verificationFileError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>{verificationFileError}</span></div>}
                      {signedEvidenceVerificationMutation.data ? (
                        <div className={`installed-mcp-status ${signedEvidenceVerificationMutation.data.authenticity_state === "authentic" && signedEvidenceVerificationMutation.data.current_state_matches ? "" : "error-state"}`} role="status">
                          {signedEvidenceVerificationMutation.data.authenticity_state === "authentic" && signedEvidenceVerificationMutation.data.current_state_matches ? <ShieldCheck size={17} /> : <AlertTriangle size={17} />}
                          <div><strong>Signature {signedEvidenceVerificationMutation.data.authenticity_state}</strong><span>Integrity valid: yes. Atlas origin authenticated: {signedEvidenceVerificationMutation.data.authenticity_proven ? "yes" : "no"}. Current state matches: {signedEvidenceVerificationMutation.data.current_state_matches ? "yes" : "no"}.</span><small>{signedEvidenceVerificationMutation.data.key_id} / {signedEvidenceVerificationMutation.data.key_version}</small></div>
                        </div>
                      ) : evidenceReceiptVerificationMutation.data ? (
                        <div className={`installed-mcp-status ${evidenceReceiptVerificationMutation.data.verification_state === "current" ? "" : "error-state"}`} role="status">
                          {evidenceReceiptVerificationMutation.data.verification_state === "current" ? <ShieldCheck size={17} /> : <AlertTriangle size={17} />}
                          <div><strong>Receipt {evidenceReceiptVerificationMutation.data.verification_state}</strong><span>Integrity valid: yes. Current state matches: {evidenceReceiptVerificationMutation.data.current_state_matches ? "yes" : "no"}. Authenticity proven: no.</span></div>
                        </div>
                      ) : (
                        <>
                          <label className="checkbox-row"><input type="checkbox" checked={verificationAcknowledged} onChange={(event) => setVerificationAcknowledged(event.target.checked)} /><span>{verificationSignedReceipt ? "A valid signature authenticates Atlas origin only; it is not approval or execution authority." : "Digest integrity is not authenticity, approval, runtime acceptance or execution authority."}</span></label>
                          {(evidenceReceiptVerificationMutation.isError || signedEvidenceVerificationMutation.isError) && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The receipt failed integrity, origin or authorized current-state verification.</span></div>}
                          <button className="secondary-button" type="button" disabled={(!verificationReceipt && !verificationSignedReceipt) || !verificationAcknowledged || evidenceReceiptVerificationMutation.isPending || signedEvidenceVerificationMutation.isPending} onClick={() => { if (verificationSignedReceipt) signedEvidenceVerificationMutation.mutate({ record, signedReceipt: verificationSignedReceipt }); else if (verificationReceipt) evidenceReceiptVerificationMutation.mutate({ record, receipt: verificationReceipt }); }}><FileCheck2 size={16} />{evidenceReceiptVerificationMutation.isPending || signedEvidenceVerificationMutation.isPending ? "Verifying receipt..." : verificationSignedReceipt ? "Verify signed receipt" : "Verify evidence receipt"}</button>
                        </>
                      )}
                    </div>
                  </>
                )}
                {handoffReadinessQuery.data && (changeContextMutation.data ?? changeContextQuery.data) ? (
                  <div className="installed-mcp-approval-result">
                    <strong>Change-context draft recorded</strong>
                    <span>{(changeContextMutation.data ?? changeContextQuery.data)!.itsm_draft_title}</span>
                    <p>Not dispatched. This internal draft grants no window or handoff authority.</p>
                    <small>{new Date((changeContextMutation.data ?? changeContextQuery.data)!.proposed_window_start).toLocaleString()} to {new Date((changeContextMutation.data ?? changeContextQuery.data)!.proposed_window_end).toLocaleString()}</small>
                  </div>
                ) : handoffReadinessQuery.data && canCreateChangeContext ? (
                  <div className="installed-mcp-approval-decision">
                    <strong>Prepare change-context draft</strong>
                    <label>Proposed window start<input type="datetime-local" value={windowStart} onChange={(event) => setWindowStart(event.target.value)} /></label>
                    <label>Proposed window end<input type="datetime-local" value={windowEnd} onChange={(event) => setWindowEnd(event.target.value)} /></label>
                    <label>Change justification<textarea value={changeJustification} minLength={20} maxLength={1000} onChange={(event) => setChangeJustification(event.target.value)} /></label>
                    <label className="checkbox-row"><input type="checkbox" checked={changeAcknowledged} onChange={(event) => setChangeAcknowledged(event.target.checked)} /><span>This creates an internal draft only. It does not dispatch to ITSM, approve the window, issue a handoff or authorize execution.</span></label>
                    {changeContextMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The draft was rejected because readiness, window or exact approval evidence changed.</span></div>}
                    <button className="primary-button" type="button" disabled={!changeAcknowledged || !windowStart || !windowEnd || changeJustification.trim().length < 20 || changeContextMutation.isPending} onClick={() => changeContextMutation.mutate({ record, readiness: handoffReadinessQuery.data, proposedWindowStart: windowStart, proposedWindowEnd: windowEnd, justification: changeJustification })}><ClipboardList size={16} />{changeContextMutation.isPending ? "Recording draft..." : "Record change-context draft"}</button>
                  </div>
                ) : handoffReadinessQuery.data ? <div className="installed-mcp-status" role="status"><UserX size={17} /><span>The latest independent verifier must prepare the change-context draft.</span></div> : null}
              </div>
            ) : canRevalidate ? (
              <>
                <label>Revalidation purpose<textarea value={revalidationPurpose} minLength={20} maxLength={1000} onChange={(event) => setRevalidationPurpose(event.target.value)} /></label>
                <label className="checkbox-row"><input type="checkbox" checked={revalidationAcknowledged} onChange={(event) => setRevalidationAcknowledged(event.target.checked)} /><span>This produces evidence only. It grants no handoff, package, runtime or execution authority.</span></label>
                {revalidationMutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Revalidation failed because identity separation, approval lineage, policy or plan freshness changed.</span></div>}
                <button className="primary-button" type="button" disabled={!revalidationAcknowledged || revalidationPurpose.trim().length < 20 || revalidationMutation.isPending} onClick={() => revalidationMutation.mutate({ record, purpose: revalidationPurpose })}><UserCheck size={16} />{revalidationMutation.isPending ? "Revalidating approval..." : "Revalidate approval"}</button>
              </>
            ) : (
              <div className="installed-mcp-status error-state" role="status"><UserX size={17} /><div><strong>Third verifier required</strong><span>The requester and approver cannot revalidate this approval.</span></div></div>
            )}
          </div>
        )}
        <p>The record grants no execution authority and performs no package, runtime or infrastructure change.</p>
      </section>
    );
  }
  if (recordQuery.isLoading || (mutation.isSuccess && recordQuery.isFetching)) {
    return <div className="installed-mcp-status"><RefreshCw className="spin" size={17} /><span>Checking governed approval state...</span></div>;
  }
  return (
    <form className="installed-mcp-approval-request" onSubmit={submit}>
      <div className="installed-mcp-approval-heading"><ShieldCheck size={18} /><div><strong>Request independent human review</strong><span>Bound to this exact immutable plan and active approval policy.</span></div></div>
      <label>Review purpose<textarea value={purpose} minLength={20} maxLength={1000} onChange={(event) => setPurpose(event.target.value)} /></label>
      <label className="checkbox-row"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>This creates a review request only. It is not approval and grants no execution authority.</span></label>
      {mutation.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>The approval request was rejected or the plan evidence changed.</span></div>}
      <button className="primary-button" type="submit" disabled={!acknowledged || purpose.trim().length < 20 || mutation.isPending}><ShieldCheck size={16} />{mutation.isPending ? "Requesting review..." : "Request human approval"}</button>
    </form>
  );
}

function UpgradeReadinessDialog({
  instance,
  subjectId,
  onCancel,
}: {
  instance: ConnectorInstanceRecord;
  subjectId: string;
  onCancel: () => void;
}) {
  const [candidateReceiptId, setCandidateReceiptId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["connector-upgrade-readiness", instance.record_id],
    queryFn: () => getConnectorUpgradeReadiness(instance.record_id),
  });
  const planQuery = useQuery({
    queryKey: ["connector-upgrade-plan", instance.record_id, candidateReceiptId],
    queryFn: () => getConnectorUpgradePlan(instance.record_id, candidateReceiptId ?? ""),
    enabled: candidateReceiptId !== null,
  });
  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section className="installed-mcp-dialog upgrade-review" role="dialog" aria-modal="true" aria-labelledby="upgrade-mcp-title">
        <header>
          <div><p className="eyebrow">DECISION SUPPORT ONLY</p><h3 id="upgrade-mcp-title">Review update for {instance.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close update review" onClick={onCancel}><X size={17} /></button>
        </header>
        <div className="installed-mcp-upgrade-boundary"><ShieldCheck size={18} /><p>This review compares governed package evidence only. It does not install an update, change configuration, contact infrastructure or authorize execution.</p></div>
        {query.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={18} /><span>Comparing exact package and manifest lineage...</span></div>}
        {query.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} /><span>Update readiness is unavailable for this MCP.</span></div>}
        {query.data && (
          <>
            <div className="installed-mcp-upgrade-current"><span>Current governed release</span><strong>{query.data.current_release_version}</strong><code>{query.data.current_package_digest.slice(0, 16)}</code></div>
            {query.data.candidates.length ? (
              <div className="installed-mcp-upgrade-list">{query.data.candidates.map((candidate) => <UpgradeCandidateCard candidate={candidate} key={candidate.receipt_id} onReviewPlan={() => setCandidateReceiptId(candidate.receipt_id)} />)}</div>
            ) : (
              <div className="installed-mcp-empty compact"><ArrowUpCircle size={20} /><div><strong>No newer governed package is installed</strong><span>Complete package assurance and installation in MCP Builder before reviewing an update.</span></div></div>
            )}
          </>
        )}
        {planQuery.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={18} /><span>Building exact upgrade plan evidence...</span></div>}
        {planQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={18} /><span>Upgrade plan is unavailable or source evidence changed.</span></div>}
        {planQuery.data && <UpgradePlanEvidence plan={planQuery.data} subjectId={subjectId} />}
        <footer><button type="button" className="secondary-button" onClick={onCancel}>Close review</button></footer>
      </section>
    </div>
  );
}

function SigningProviderOnboardingReadiness({
  dossier,
}: {
  dossier: ConnectorUpgradeSigningProviderOnboardingReadiness;
}) {
  return (
    <div className="installed-mcp-onboarding-result">
      <div className={`installed-mcp-conformance-state ${
        dossier.provider_onboarding_ready ? "conformant" : "blocked"
      }`}>
        {dossier.provider_onboarding_ready
          ? <ShieldCheck size={18} />
          : <AlertTriangle size={18} />}
        <div>
          <strong>{dossier.provider_onboarding_ready
            ? "Production evidence complete"
            : `${dossier.required_external_inputs.length} requirements blocked`}</strong>
          <span>{dossier.provider_class} / {dossier.key_id ?? "No eligible key"}</span>
          <span>{dossier.algorithm ?? "No eligible algorithm"} / {dossier.policy_version}</span>
        </div>
      </div>
      <dl className="installed-mcp-onboarding-policy">
        <div><dt>Policy</dt><dd>{dossier.policy_id}</dd></div>
        <div><dt>Issued by</dt><dd>{dossier.policy_issued_by}</dd></div>
        <div><dt>Expires</dt><dd>{new Date(dossier.policy_expires_at).toLocaleString()}</dd></div>
        <div><dt>Digest</dt><dd><code>{dossier.policy_digest.slice(0, 16)}</code></dd></div>
        <div><dt>Provenance</dt><dd>{dossier.policy_provenance_verified
          ? "Issuer attestation verified"
          : "Policy blocked"}</dd></div>
        <div><dt>Trust key</dt><dd>{dossier.policy_trust_key_id} / {dossier.policy_trust_key_version}</dd></div>
        <div><dt>Algorithm</dt><dd>{dossier.policy_trust_algorithm}</dd></div>
        <div><dt>Attestation</dt><dd><code>{dossier.policy_attestation_digest.slice(0, 16)}</code></dd></div>
      </dl>
      <div className="installed-mcp-onboarding-requirements" role="list">
        {dossier.requirements.map((requirement) => (
          <div
            className={`installed-mcp-onboarding-requirement ${requirement.state}`}
            key={requirement.requirement_id}
            role="listitem"
          >
            {requirement.state === "satisfied"
              ? <ShieldCheck size={15} />
              : <AlertTriangle size={15} />}
            <div>
              <strong>{requirement.requirement_id.replaceAll("-", " ")}</strong>
              <span>{requirement.state === "satisfied"
                ? "Authoritative evidence satisfied"
                : requirement.reason_code.split(".").at(-1)?.replaceAll("-", " ")}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SigningProviderOnboardingPolicyProvenance({
  diagnostic,
}: {
  diagnostic: ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic;
}) {
  const guidanceLabel = (identifier: string, prefix: string) => identifier
    .replace(prefix, "")
    .replaceAll(".", " ")
    .replaceAll("-", " ");
  return (
    <div className="installed-mcp-onboarding-result installed-mcp-provenance-diagnostic">
      <div className={`installed-mcp-conformance-state ${
        diagnostic.provenance_verified ? "conformant" : "blocked"
      }`}>
        {diagnostic.provenance_verified
          ? <ShieldCheck size={18} />
          : <AlertTriangle size={18} />}
        <div>
          <strong>{diagnostic.provenance_verified
            ? "Policy provenance verified"
            : `${diagnostic.reason_codes.length} provenance checks blocked`}</strong>
          <span>{diagnostic.policy_id ?? "No safe policy reference"}</span>
          <span>{diagnostic.valid_until
            ? `Valid until ${new Date(diagnostic.valid_until).toLocaleString()}`
            : "No verified validity horizon"}</span>
        </div>
      </div>
      <dl className="installed-mcp-onboarding-policy">
        <div><dt>Issuer</dt><dd>{diagnostic.policy_issued_by ?? "Unavailable"}</dd></div>
        <div><dt>Attestation</dt><dd>{diagnostic.attestation_id ?? "Unavailable"}</dd></div>
        <div><dt>Trust key</dt><dd>{diagnostic.trust_key_id
          ? `${diagnostic.trust_key_id} / ${diagnostic.trust_key_version}`
          : "Unavailable"}</dd></div>
        <div><dt>Algorithm</dt><dd>{diagnostic.trust_algorithm ?? "Unavailable"}</dd></div>
        <div><dt>Policy digest</dt><dd><code>{diagnostic.policy_digest?.slice(0, 16) ?? "Unavailable"}</code></dd></div>
        <div><dt>Diagnostic</dt><dd><code>{diagnostic.canonical_digest.slice(0, 16)}</code></dd></div>
      </dl>
      <div className="installed-mcp-onboarding-requirements" role="list">
        {diagnostic.checks.map((check) => (
          <div
            className={`installed-mcp-onboarding-requirement ${check.state}`}
            key={check.check_id}
            role="listitem"
          >
            {check.state === "verified"
              ? <ShieldCheck size={15} />
              : <AlertTriangle size={15} />}
            <div>
              <strong>{check.check_id.replaceAll("-", " ")}</strong>
              <span>{check.reason_code.split(".").at(-1)?.replaceAll("-", " ")}</span>
              {check.state !== "verified" && check.owner_role_id &&
                check.evidence_requirement_id && check.next_action_id ? (
                  <div className="installed-mcp-provenance-guidance">
                    <span><b>Owner</b> {guidanceLabel(check.owner_role_id, "role.")}</span>
                    <span><b>Evidence</b> {guidanceLabel(
                      check.evidence_requirement_id,
                      "evidence.",
                    )}</span>
                    <span><b>Next step</b> {guidanceLabel(check.next_action_id, "action.")}</span>
                    {check.external_input_required ? (
                      <span className="installed-mcp-provenance-external">
                        External deployment input required
                      </span>
                    ) : null}
                  </div>
                ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function InstalledMcpManagementWorkspace({
  onOpenBuilder,
  onRequestEnterpriseLogin,
  subjectId,
  organizationId,
  environmentId,
}: {
  onOpenBuilder?: () => void;
  onRequestEnterpriseLogin?: () => void;
  subjectId: string;
  organizationId: string;
  environmentId: string;
}) {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [retiring, setRetiring] = useState<ConnectorInstanceRecord | null>(null);
  const [reviewing, setReviewing] = useState<ConnectorInstanceRecord | null>(null);
  const [targeting, setTargeting] = useState<ConnectorInstanceRecord | null>(null);
  const [credentialing, setCredentialing] = useState<ConnectorInstanceRecord | null>(null);
  const [validating, setValidating] = useState<ConnectorInstanceRecord | null>(null);
  const [governingCapabilities, setGoverningCapabilities] =
    useState<ConnectorInstanceRecord | null>(null);
  const [establishingRuntimeTrust, setEstablishingRuntimeTrust] =
    useState<ConnectorInstanceRecord | null>(null);
  const [authorizingSecretBrokerage, setAuthorizingSecretBrokerage] =
    useState<ConnectorInstanceRecord | null>(null);
  const [activatingRuntime, setActivatingRuntime] =
    useState<ConnectorInstanceRecord | null>(null);
  const [deactivatingRuntime, setDeactivatingRuntime] =
    useState<ConnectorInstanceRecord | null>(null);
  const [verifyingTargetSession, setVerifyingTargetSession] =
    useState<ConnectorInstanceRecord | null>(null);
  const [authorizingInvocation, setAuthorizingInvocation] =
    useState<ConnectorInstanceRecord | null>(null);
  const [invokingBounded, setInvokingBounded] =
    useState<ConnectorInstanceRecord | null>(null);
  const [preservingInvocationEvidence, setPreservingInvocationEvidence] =
    useState<ConnectorInstanceRecord | null>(null);
  const [curatingKnowledge, setCuratingKnowledge] =
    useState<ConnectorInstanceRecord | null>(null);
  const [requestingKnowledgeReview, setRequestingKnowledgeReview] =
    useState<ConnectorInstanceRecord | null>(null);
  const [assigningKnowledgeReviewers, setAssigningKnowledgeReviewers] =
    useState<ConnectorInstanceRecord | null>(null);
  const [reviewerAssignmentReturnFocus, setReviewerAssignmentReturnFocus] =
    useState<HTMLElement | null>(null);
  const sessionScopeKey = JSON.stringify([subjectId, organizationId, environmentId]);
  const packageQuery = useQuery({
    queryKey: ["connector-package-installations", subjectId],
    queryFn: getConnectorPackageInstallations,
    enabled: Boolean(subjectId),
  });
  const policyQuery = useQuery({
    queryKey: ["connector-instance-creation-policies", subjectId],
    queryFn: getConnectorInstanceCreationPolicies,
    enabled: Boolean(subjectId),
  });
  const instanceQuery = useQuery({
    queryKey: ["connector-instances", subjectId, lifecycle, search],
    queryFn: () => getConnectorInstances({ lifecycle, query: search }),
    enabled: Boolean(subjectId),
  });
  const bindingQuery = useQuery({
    queryKey: ["connector-target-bindings", subjectId],
    queryFn: () => getConnectorTargetConfigurations(),
    enabled: Boolean(subjectId),
  });
  const assignmentQuery = useQuery({
    queryKey: ["connector-credential-assignments", subjectId],
    queryFn: () => getConnectorCredentialAssignments(),
    enabled: Boolean(subjectId),
  });
  const validationQuery = useQuery({
    queryKey: ["connector-configuration-validations", sessionScopeKey],
    queryFn: () => getConnectorConfigurationValidations(),
    enabled: Boolean(subjectId),
  });
  const enablementQuery = useQuery({
    queryKey: ["connector-capability-enablements", sessionScopeKey],
    queryFn: () => getConnectorCapabilityEnablements(),
    enabled: Boolean(subjectId),
  });
  const runtimeTrustQuery = useQuery({
    queryKey: ["connector-runtime-trust-grants", sessionScopeKey],
    queryFn: () => getConnectorRuntimeTrustGrants(),
    enabled: Boolean(subjectId),
  });
  const secretBrokerageQuery = useQuery({
    queryKey: ["connector-secret-brokerage-authorizations", sessionScopeKey],
    queryFn: () => getConnectorSecretBrokerageAuthorizations(),
    enabled: Boolean(subjectId),
  });
  const runtimeActivationQuery = useQuery({
    queryKey: ["connector-runtime-activations", sessionScopeKey],
    queryFn: () => getConnectorRuntimeActivations(),
    enabled: Boolean(subjectId),
  });
  const bundledCatalogQuery = useQuery({
    queryKey: ["bundled-connector-catalog", subjectId],
    queryFn: getBundledConnectorCatalog,
    enabled: Boolean(subjectId),
  });
  const runtimeDeactivationQuery = useQuery({
    queryKey: ["connector-runtime-deactivations", sessionScopeKey],
    queryFn: () => getConnectorRuntimeDeactivations(),
    enabled: Boolean(subjectId),
  });
  const targetSessionQuery = useQuery({
    queryKey: ["connector-target-session-verifications", sessionScopeKey],
    queryFn: () => getConnectorTargetSessionVerifications(),
    enabled: Boolean(subjectId),
  });
  const invocationAuthorizationQueries = useQueries({
    queries: (targetSessionQuery.isError ? [] : (targetSessionQuery.data ?? [])).map(
      (verification) => ({
        queryKey: [
          "connector-invocation-authorizations",
          sessionScopeKey,
          verification.verification_id,
        ],
        queryFn: () => getConnectorInvocationAuthorizations({
          sourceTargetSessionVerificationId: verification.verification_id,
        }),
        enabled: Boolean(subjectId),
      }),
    ),
  });
  const invocationAuthorizations = invocationAuthorizationQueries.flatMap((query) =>
    query.isSuccess && query.data[0] ? [query.data[0]] : []
  );
  const boundedInvocationQueries = useQueries({
    queries: invocationAuthorizations.map((authorization) => ({
      queryKey: [
        "connector-bounded-invocations",
        sessionScopeKey,
        authorization.authorization_id,
      ],
      queryFn: () => getConnectorBoundedInvocations({
        sourceAuthorizationId: authorization.authorization_id,
      }),
      enabled: Boolean(subjectId),
    })),
  });
  const boundedInvocations = boundedInvocationQueries.flatMap((query) =>
    query.isSuccess && query.data[0] ? [query.data[0]] : []
  );
  const invocationEvidenceQueries = useQueries({
    queries: boundedInvocations.map((invocation) => ({
      queryKey: [
        "connector-invocation-evidence",
        sessionScopeKey,
        invocation.invocation_id,
      ],
      queryFn: () => getConnectorInvocationEvidence({
        sourceInvocationId: invocation.invocation_id,
      }),
      enabled: Boolean(subjectId),
    })),
  });
  const invocationEvidenceSources = invocationEvidenceQueries.flatMap((query) =>
    query.isSuccess && query.data[0] ? [query.data[0]] : []
  );
  const knowledgeDraftQueries = useQueries({
    queries: invocationEvidenceSources.map((evidence) => ({
      queryKey: operationalEvidenceKnowledgeDraftQueryKey(
        sessionScopeKey,
        evidence.ingestion_id,
      ),
      queryFn: () => getOperationalEvidenceKnowledgeDrafts({ evidence }),
      enabled: Boolean(subjectId),
      retry: false,
    })),
  });
  const knowledgeDraftSources = knowledgeDraftQueries.flatMap((query) =>
    query.isSuccess && query.data[0] ? [query.data[0]] : []
  );
  const knowledgeReviewRequestQueries = useQueries({
    queries: knowledgeDraftSources.map((draft) => ({
      queryKey: operationalKnowledgeReviewRequestQueryKey(sessionScopeKey, draft.draft_id),
      queryFn: () => getOperationalKnowledgeReviewRequests({ draft }),
      enabled: Boolean(subjectId),
      retry: false,
    })),
  });
  const knowledgeReviewRequestSources = knowledgeReviewRequestQueries.flatMap((query) =>
    query.isSuccess && query.data[0] ? [query.data[0]] : []
  );
  const knowledgeReviewerAssignmentQueries = useQueries({
    queries: knowledgeReviewRequestSources.map((reviewRequest) => ({
      queryKey: operationalKnowledgeReviewerAssignmentQueryKey(
        sessionScopeKey,
        reviewRequest.review_request_id,
      ),
      queryFn: () => getOperationalKnowledgeReviewerAssignments({ reviewRequest }),
      enabled: Boolean(subjectId),
      retry: false,
    })),
  });
  const signingTrustQuery = useQuery({
    queryKey: ["connector-upgrade-signing-key-trust", subjectId],
    queryFn: getConnectorUpgradeEvidenceSigningKeyTrustInventory,
    enabled: Boolean(subjectId),
  });
  const signingConformanceQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-conformance", subjectId],
    queryFn: getLatestConnectorUpgradeSigningProviderConformance,
    enabled: Boolean(subjectId),
    retry: false,
  });
  const signingConformanceMutation = useMutation({
    mutationFn: assessConnectorUpgradeSigningProviderConformance,
    onSuccess: (assessment: ConnectorUpgradeSigningProviderConformanceAssessment) => {
      queryClient.setQueryData(
        ["connector-upgrade-signing-provider-conformance", subjectId],
        assessment,
      );
      void queryClient.invalidateQueries({
        queryKey: ["connector-upgrade-signing-provider-onboarding-readiness"],
      });
    },
  });
  const signingOnboardingQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-onboarding-readiness", subjectId],
    queryFn: getConnectorUpgradeSigningProviderOnboardingReadiness,
    enabled: Boolean(subjectId),
  });
  const signingOnboardingProvenanceQuery = useQuery({
    queryKey: ["connector-upgrade-signing-provider-onboarding-policy-provenance", subjectId],
    queryFn: getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
    enabled: Boolean(subjectId),
  });
  const createMutation = useMutation({
    mutationFn: createConnectorInstance,
    onSuccess: async () => {
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["connector-instances"] });
    },
  });
  const createBundledMutation = useMutation({
    mutationFn: createBundledConnectorInstance,
    onSuccess: async () => {
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["connector-instances"] });
    },
  });
  const retireMutation = useMutation({
    mutationFn: retireConnectorInstance,
    onSuccess: async () => {
      setRetiring(null);
      await queryClient.invalidateQueries({ queryKey: ["connector-instances"] });
    },
  });
  const instances = instanceQuery.data ?? [];
  const targetBindings = bindingQuery.data ?? [];
  const bindingByInstance = new Map(
    targetBindings.map((binding) => [binding.source_instance_record_id, binding]),
  );
  const credentialAssignments = assignmentQuery.data ?? [];
  const assignmentByBinding = new Map(
    credentialAssignments.map((assignment) => [assignment.source_target_binding_id, assignment]),
  );
  const configurationValidations = validationQuery.data ?? [];
  const validationByAssignment = new Map(
    configurationValidations.map((validation) => [validation.source_assignment_id, validation]),
  );
  const capabilityEnablements = enablementQuery.data ?? [];
  const enablementByValidation = new Map(
    capabilityEnablements.map((enablement) => [enablement.source_validation_id, enablement]),
  );
  const runtimeTrustGrants = runtimeTrustQuery.isError ? [] : (runtimeTrustQuery.data ?? []);
  const runtimeTrustByEnablement = new Map(
    runtimeTrustGrants.map((grant) => [grant.source_enablement_id, grant]),
  );
  const secretBrokerageAuthorizations = secretBrokerageQuery.isError
    ? []
    : (secretBrokerageQuery.data ?? []);
  const secretBrokerageByRuntimeTrust = new Map(
    secretBrokerageAuthorizations.map((authorization) => [
      authorization.source_runtime_trust_grant_id,
      authorization,
    ]),
  );
  const runtimeActivations = runtimeActivationQuery.isError
    ? []
    : (runtimeActivationQuery.data ?? []);
  const runtimeActivationBySecretBrokerage = new Map(
    runtimeActivations.map((activation) => [
      activation.source_brokerage_authorization_id,
      activation,
    ]),
  );
  const runtimeDeactivationByActivation = new Map(
    (runtimeDeactivationQuery.isError ? [] : (runtimeDeactivationQuery.data ?? [])).map(
      (deactivation) => [deactivation.activation_id, deactivation],
    ),
  );
  const targetSessionVerifications = targetSessionQuery.isError
    ? []
    : (targetSessionQuery.data ?? []);
  const targetSessionByRuntimeActivation = new Map(
    targetSessionVerifications.map((verification) => [
      verification.source_runtime_activation_id,
      verification,
    ]),
  );
  const invocationAuthorizationByTargetSession = new Map(
    invocationAuthorizationQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const targetSession = targetSessionVerifications[index];
      const authorization = query.data[0];
      return targetSession && authorization
        ? [[targetSession.verification_id, authorization] as const]
        : [];
    }),
  );
  const invocationAuthorizationInventoryReady = new Set(
    invocationAuthorizationQueries.flatMap((query, index) => {
      const targetSession = targetSessionVerifications[index];
      return query.isSuccess && targetSession ? [targetSession.verification_id] : [];
    }),
  );
  const invocationAuthorizationQueryErrors = invocationAuthorizationQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const boundedInvocationByAuthorization = new Map(
    boundedInvocationQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const authorization = invocationAuthorizations[index];
      const invocation = query.data[0];
      return authorization && invocation
        ? [[authorization.authorization_id, invocation] as const]
        : [];
    }),
  );
  const boundedInvocationInventoryReady = new Set(
    boundedInvocationQueries.flatMap((query, index) => {
      const authorization = invocationAuthorizations[index];
      return query.isSuccess && authorization ? [authorization.authorization_id] : [];
    }),
  );
  const boundedInvocationQueryErrors = boundedInvocationQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const invocationEvidenceByInvocation = new Map(
    invocationEvidenceQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const invocation = boundedInvocations[index];
      const evidence = query.data[0];
      return invocation && evidence
        ? [[invocation.invocation_id, evidence] as const]
        : [];
    }),
  );
  const invocationEvidenceInventoryReady = new Set(
    invocationEvidenceQueries.flatMap((query, index) => {
      const invocation = boundedInvocations[index];
      return query.isSuccess && invocation ? [invocation.invocation_id] : [];
    }),
  );
  const invocationEvidenceQueryErrors = invocationEvidenceQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const knowledgeDraftByEvidence = new Map(
    knowledgeDraftQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const evidence = invocationEvidenceSources[index];
      const draft = query.data[0];
      return evidence && draft ? [[evidence.ingestion_id, draft] as const] : [];
    }),
  );
  const knowledgeDraftInventoryReady = new Set(
    knowledgeDraftQueries.flatMap((query, index) => {
      const evidence = invocationEvidenceSources[index];
      return query.isSuccess && evidence ? [evidence.ingestion_id] : [];
    }),
  );
  const knowledgeDraftQueryErrors = knowledgeDraftQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const knowledgeDraftByInstance = new Map(
    knowledgeDraftSources.map((draft) => [draft.instance_id, draft] as const),
  );
  const knowledgeReviewRequestByDraft = new Map(
    knowledgeReviewRequestQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const draft = knowledgeDraftSources[index];
      const reviewRequest = query.data[0];
      return draft && reviewRequest ? [[draft.draft_id, reviewRequest] as const] : [];
    }),
  );
  const knowledgeReviewRequestInventoryReady = new Set(
    knowledgeReviewRequestQueries.flatMap((query, index) => {
      const draft = knowledgeDraftSources[index];
      return query.isSuccess && draft ? [draft.draft_id] : [];
    }),
  );
  const knowledgeReviewRequestQueryErrors = knowledgeReviewRequestQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const knowledgeReviewerAssignmentByReviewRequest = new Map(
    knowledgeReviewerAssignmentQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const reviewRequest = knowledgeReviewRequestSources[index];
      const assignment = query.data.find(
        (entry): entry is OperationalKnowledgeReviewerAssignmentInventoryItem =>
          entry.schema_version === "atlas.operational-knowledge-reviewer-assignment.v1",
      );
      return reviewRequest && assignment
        ? [[reviewRequest.review_request_id, assignment] as const]
        : [];
    }),
  );
  const knowledgeReviewerAssignmentClaimByReviewRequest = new Map(
    knowledgeReviewerAssignmentQueries.flatMap((query, index) => {
      if (!query.isSuccess) return [];
      const reviewRequest = knowledgeReviewRequestSources[index];
      const status = query.data.find(
        (entry): entry is OperationalKnowledgeReviewerAssignmentClaimStatus =>
          entry.schema_version ===
            "atlas.operational-knowledge-reviewer-assignment-claim-status.v1",
      );
      return reviewRequest && status
        ? [[reviewRequest.review_request_id, status] as const]
        : [];
    }),
  );
  const knowledgeReviewerAssignmentInventoryReady = new Set(
    knowledgeReviewerAssignmentQueries.flatMap((query, index) => {
      const reviewRequest = knowledgeReviewRequestSources[index];
      return query.isSuccess && reviewRequest ? [reviewRequest.review_request_id] : [];
    }),
  );
  const knowledgeReviewerAssignmentQueryErrors = knowledgeReviewerAssignmentQueries
    .map((query) => query.error)
    .filter((error) => error !== null);
  const packages = packageQuery.data ?? [];
  const bundledCatalog = bundledCatalogQuery.data ?? [];
  const availableConnectorCount = packages.length + bundledCatalog.length;
  const policies = policyQuery.data ?? [];
  const activeCount = instances.filter(
    (item) => item.instance_state === "disabled_unconfigured",
  ).length;
  const lifecycleQueryErrors = [
    instanceQuery.error,
    bindingQuery.error,
    assignmentQuery.error,
    validationQuery.error,
    packageQuery.error,
    bundledCatalogQuery.error,
    policyQuery.error,
  ].filter((error) => error !== null);
  const lifecycleQueryFailed = lifecycleQueryErrors.length > 0;
  const sessionAuthenticationFailed = lifecycleQueryErrors.some((error) => hasStatus(error, 401));
  const lifecycleAuthorizationFailed = lifecycleQueryErrors.some((error) => hasStatus(error, 403));
  const lifecycleMutationError = createMutation.error ?? createBundledMutation.error ?? retireMutation.error;
  const mutationAuthenticationFailed = hasStatus(lifecycleMutationError, 401);
  const mutationAuthorizationFailed = hasStatus(lifecycleMutationError, 403);
  const mutationConflict = hasStatus(lifecycleMutationError, 409);
  const mutationAction = createMutation.error || createBundledMutation.error ? "creation" : "retirement";
  const openBuilder = () => {
    setAdding(false);
    if (onOpenBuilder) {
      onOpenBuilder();
      return;
    }
    document.getElementById("connector-view-builder")?.scrollIntoView?.({
      behavior: "smooth",
      block: "start",
    });
  };
  const refresh = () => {
    void packageQuery.refetch();
    void bundledCatalogQuery.refetch();
    void policyQuery.refetch();
    void instanceQuery.refetch();
    void bindingQuery.refetch();
    void assignmentQuery.refetch();
    void validationQuery.refetch();
    void enablementQuery.refetch();
    void runtimeTrustQuery.refetch();
    void secretBrokerageQuery.refetch();
    void runtimeActivationQuery.refetch();
    void runtimeDeactivationQuery.refetch();
    void targetSessionQuery.refetch();
    for (const query of invocationAuthorizationQueries) void query.refetch();
    for (const query of boundedInvocationQueries) void query.refetch();
    for (const query of invocationEvidenceQueries) void query.refetch();
    for (const query of knowledgeDraftQueries) void query.refetch();
    for (const query of knowledgeReviewRequestQueries) void query.refetch();
    for (const query of knowledgeReviewerAssignmentQueries) void query.refetch();
    void signingTrustQuery.refetch();
    void signingConformanceQuery.refetch();
    void signingOnboardingQuery.refetch();
    void signingOnboardingProvenanceQuery.refetch();
  };

  return (
    <section className="installed-mcp-workspace" aria-labelledby="installed-mcp-title">
      <div className="installed-mcp-heading">
        <div>
          <p className="eyebrow">MCP INVENTORY</p>
          <h2 id="installed-mcp-title">Installed MCPs</h2>
          <p>Governed connector instances and their exact installed package lineage.</p>
        </div>
        <div className="installed-mcp-heading-actions">
          <span className="state-badge neutral"><ShieldCheck size={14} /> no runtime authority</span>
          <button className="icon-button" type="button" title="Refresh MCP inventory" aria-label="Refresh MCP inventory" onClick={refresh}><RefreshCw size={17} /></button>
          <button
            className="primary-button"
            type="button"
            disabled={
              (packageQuery.isLoading || policyQuery.isLoading || bundledCatalogQuery.isLoading) ||
              ((packageQuery.isError || policyQuery.isError) && bundledCatalogQuery.isError)
            }
            title="Add MCP"
            onClick={() => {
              createMutation.reset();
              createBundledMutation.reset();
              setAdding(true);
            }}
          ><PackagePlus size={16} />Add MCP</button>
        </div>
      </div>
      <div className="installed-mcp-readiness" aria-label="MCP lifecycle prerequisites">
        <span data-ready="true">
          <ShieldCheck size={15} />
          Backend authorization enforced
        </span>
        <span data-ready={availableConnectorCount > 0}>
          {packageQuery.isLoading || bundledCatalogQuery.isLoading
            ? <RefreshCw className="spin" size={15} />
            : <PackagePlus size={15} />}
          {packageQuery.isLoading || bundledCatalogQuery.isLoading
            ? "Checking MCP catalog"
            : availableConnectorCount > 0
              ? `${availableConnectorCount} MCP${availableConnectorCount === 1 ? "" : "s"} available`
              : "MCP catalog unavailable"}
        </span>
        <span data-ready={bundledCatalog.length > 0 || (!policyQuery.isLoading && !policyQuery.isError && policies.length > 0)}>
          {policyQuery.isLoading ? <RefreshCw className="spin" size={15} /> : <FileCheck2 size={15} />}
          {bundledCatalog.length > 0
            ? "Bundled catalog governed"
            : policyQuery.isLoading
            ? "Checking policy"
            : policyQuery.isError
              ? "Policy inventory unavailable"
            : policies.length > 0
              ? `${policies.length} creation polic${policies.length === 1 ? "y" : "ies"}`
              : "Creation policy required"}
        </span>
        {!packageQuery.isLoading && !bundledCatalogQuery.isLoading && availableConnectorCount === 0 && (
          <button type="button" className="secondary-button" onClick={openBuilder}>
            <PackagePlus size={15} /> Open Builder workflow
          </button>
        )}
      </div>
      <details className="installed-mcp-signing-diagnostics">
        <summary>
          <span><ShieldCheck size={16} /> Security and onboarding diagnostics</span>
          <small>Signing trust, provider readiness and policy provenance</small>
        </summary>
      <section className="installed-mcp-signing-trust" aria-labelledby="signing-trust-title">
        <div className="installed-mcp-signing-trust-heading">
          <div>
            <p className="eyebrow">EVIDENCE AUTHENTICITY</p>
            <h3 id="signing-trust-title">Signing trust</h3>
          </div>
          {signingTrustQuery.data && (
            <span className={`state-badge ${signingTrustQuery.data.provider_available ? "success" : "neutral"}`}>
              {signingTrustQuery.data.provider_state}
            </span>
          )}
        </div>
        {signingTrustQuery.isLoading && <div className="installed-mcp-status"><RefreshCw className="spin" size={17} /><span>Reading scoped signing trust...</span></div>}
        {signingTrustQuery.isError && <div className="installed-mcp-status error-state" role="alert"><AlertTriangle size={17} /><span>Signing trust metadata is unavailable for this scope.</span></div>}
        {signingTrustQuery.data && signingTrustQuery.data.keys.length === 0 && (
          <div className="installed-mcp-status"><ShieldCheck size={17} /><div><strong>No trusted signing key</strong><span>{signingTrustQuery.data.provider_class}. Production signing remains fail-closed.</span></div></div>
        )}
        {signingTrustQuery.data?.keys.map((key) => (
          <div className="installed-mcp-signing-key" key={`${key.key_id}:${key.key_version}`}>
            <ShieldCheck size={18} />
            <div><strong>{key.key_id}</strong><span>{key.key_version} / {key.signer_profile_id}</span></div>
            <div><strong>{key.effective_state.replaceAll("_", " ")}</strong><span>Valid until {new Date(key.expires_at).toLocaleString()}</span></div>
            <div><strong>{key.verification_trusted ? "Verification trusted" : "Verification blocked"}</strong><span>{key.algorithm}</span></div>
          </div>
        ))}
        {signingTrustQuery.data && <p className="installed-mcp-signing-boundary">Read-only metadata. No key management or signing authority.</p>}
        <div className="installed-mcp-conformance" aria-labelledby="signing-conformance-title">
          <div className="installed-mcp-conformance-heading">
            <div>
              <span>PROVIDER DIAGNOSTIC</span>
              <strong id="signing-conformance-title">Signing-provider conformance</strong>
            </div>
            <button
              type="button"
              className="secondary-button"
              disabled={signingConformanceMutation.isPending}
              onClick={() => signingConformanceMutation.mutate()}
            >
              {signingConformanceMutation.isPending
                ? <RefreshCw className="spin" size={15} />
                : <Activity size={15} />}
              Run assessment
            </button>
          </div>
          {signingConformanceQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Reading latest provider evidence...</span>
            </div>
          )}
          {(signingConformanceQuery.isError || signingConformanceMutation.isError) && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Signing-provider conformance evidence is unavailable.</span>
            </div>
          )}
          {!signingConformanceQuery.isLoading && !signingConformanceQuery.data &&
            !signingConformanceQuery.isError && (
              <div className="installed-mcp-status">
                <Activity size={17} />
                <span>No bounded provider assessment has been recorded for this scope.</span>
              </div>
            )}
          {signingConformanceQuery.data && (
            <div className="installed-mcp-conformance-result">
              <div className={
                `installed-mcp-conformance-state ${
                  signingConformanceQuery.data.signing_provider_conformant
                    ? "conformant" : "blocked"
                }`
              }>
                {signingConformanceQuery.data.signing_provider_conformant
                  ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
                <div>
                  <strong>{signingConformanceQuery.data.state.replaceAll("_", " ")}</strong>
                  <span>{signingConformanceQuery.data.provider_class}</span>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Key reference</dt>
                  <dd>{signingConformanceQuery.data.key_id ?? "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Algorithm</dt>
                  <dd>{signingConformanceQuery.data.algorithm ?? "Not observed"}</dd>
                </div>
                <div>
                  <dt>Policy</dt>
                  <dd>{signingConformanceQuery.data.policy_version}</dd>
                </div>
                <div>
                  <dt>Valid until</dt>
                  <dd>{new Date(signingConformanceQuery.data.valid_until).toLocaleString()}</dd>
                </div>
              </dl>
              <p>
                {signingConformanceQuery.data.production_approved
                  ? "Provider is approved for production by the active policy."
                  : "Provider is not approved for production; production remains fail-closed."}
              </p>
            </div>
          )}
          <p className="installed-mcp-signing-boundary">
            Server-generated challenge only. No key management, receipt signing or execution authority.
          </p>
        </div>
        <div className="installed-mcp-onboarding" aria-labelledby="signing-onboarding-title">
          <div className="installed-mcp-signing-trust-heading">
            <div>
              <p className="eyebrow">PRODUCTION EVIDENCE</p>
              <h3 id="signing-onboarding-title">Provider onboarding readiness</h3>
            </div>
            {signingOnboardingQuery.data && (
              <span className={`state-badge ${
                signingOnboardingQuery.data.provider_onboarding_ready ? "success" : "neutral"
              }`}>
                {signingOnboardingQuery.data.provider_onboarding_ready
                  ? "ready"
                  : "evidence required"}
              </span>
            )}
          </div>
          {signingOnboardingQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Evaluating production onboarding evidence...</span>
            </div>
          )}
          {signingOnboardingQuery.isError && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Production onboarding is policy-blocked for this scope.</span>
            </div>
          )}
          {signingOnboardingQuery.data && (
            <SigningProviderOnboardingReadiness dossier={signingOnboardingQuery.data} />
          )}
          <p className="installed-mcp-signing-boundary">
            Evidence only. No provider configuration, key management, signing or execution authority.
          </p>
        </div>
        <div className="installed-mcp-onboarding" aria-labelledby="signing-onboarding-provenance-title">
          <div className="installed-mcp-signing-trust-heading">
            <div>
              <p className="eyebrow">TRUST DIAGNOSTIC</p>
              <h3 id="signing-onboarding-provenance-title">Policy provenance diagnostic</h3>
            </div>
            {signingOnboardingProvenanceQuery.data && (
              <span className={`state-badge ${
                signingOnboardingProvenanceQuery.data.provenance_verified ? "success" : "neutral"
              }`}>
                {signingOnboardingProvenanceQuery.data.state}
              </span>
            )}
          </div>
          {signingOnboardingProvenanceQuery.isLoading && (
            <div className="installed-mcp-status">
              <RefreshCw className="spin" size={17} />
              <span>Checking policy provenance evidence...</span>
            </div>
          )}
          {signingOnboardingProvenanceQuery.isError && (
            <div className="installed-mcp-status error-state" role="alert">
              <AlertTriangle size={17} />
              <span>Policy provenance diagnostic is unavailable for this scope.</span>
            </div>
          )}
          {signingOnboardingProvenanceQuery.data && (
            <SigningProviderOnboardingPolicyProvenance
              diagnostic={signingOnboardingProvenanceQuery.data}
            />
          )}
          <p className="installed-mcp-signing-boundary">
            Read-only diagnostic. No trust-store, policy, key or provider mutation authority.
          </p>
        </div>
      </section>
      </details>
      <div className="installed-mcp-toolbar">
        <div className="installed-mcp-filters" aria-label="MCP lifecycle filter">
          {(["active", "retired", "all"] as const).map((value) => (
            <button type="button" data-active={lifecycle === value} aria-pressed={lifecycle === value} onClick={() => setLifecycle(value)} key={value}>{value === "active" ? "Active" : value === "retired" ? "Retired" : "All"}</button>
          ))}
        </div>
        <label className="installed-mcp-search"><Search size={16} /><span className="sr-only">Search installed MCPs</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search MCPs" maxLength={200} /></label>
      </div>
      {lifecycleQueryFailed && (
        <div className="installed-mcp-status error-state" role="alert">
          <AlertTriangle size={18} />
          <div>
            <strong>{sessionAuthenticationFailed
              ? "Your signed-in session has expired"
              : lifecycleAuthorizationFailed
                ? "Connector lifecycle permission is required"
                : "Connector lifecycle data is unavailable"}</strong>
            <span>{sessionAuthenticationFailed
              ? "Sign in again; the MCP inventory will refresh automatically."
              : lifecycleAuthorizationFailed
                ? "This signed-in account is missing a required role or scope."
                : "The instance, package or policy inventory could not be loaded. Retry the request."}</span>
          </div>
          {sessionAuthenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !sessionAuthenticationFailed && !lifecycleAuthorizationFailed ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {enablementQuery.isError && (
        <div className="installed-mcp-status error-state" role="alert">
          {hasStatus(enablementQuery.error, 401) ? (
            <LogIn size={18} />
          ) : (
            <AlertTriangle size={18} />
          )}
          <div>
            <strong>
              {hasStatus(enablementQuery.error, 401)
                ? "Your signed-in session has expired"
                : hasStatus(enablementQuery.error, 403)
                  ? "Capability governance permission is required"
                  : "Capability governance inventory is unavailable"}
            </strong>
            <span>
              Existing connector lifecycle evidence remains available. Capability controls stay
              hidden until this scoped inventory can be read.
            </span>
          </div>
          {hasStatus(enablementQuery.error, 401) && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !hasStatus(enablementQuery.error, 403) ? (
            <button type="button" onClick={() => void enablementQuery.refetch()}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {runtimeTrustQuery.isError && (
        <div className="installed-mcp-status error-state" role="alert">
          {hasStatus(runtimeTrustQuery.error, 401) ? <LogIn size={18} /> : <AlertTriangle size={18} />}
          <div>
            <strong>
              {hasStatus(runtimeTrustQuery.error, 401)
                ? "Your signed-in session has expired"
                : hasStatus(runtimeTrustQuery.error, 403)
                  ? "Runtime trust permission is required"
                  : "Runtime trust inventory is unavailable"}
            </strong>
            <span>
              Existing lifecycle and capability evidence remains available. Runtime trust controls
              stay hidden until this scoped inventory can be read.
            </span>
          </div>
          {hasStatus(runtimeTrustQuery.error, 401) && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !hasStatus(runtimeTrustQuery.error, 403) ? (
            <button type="button" onClick={() => void runtimeTrustQuery.refetch()}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {secretBrokerageQuery.isError && (
        <div className="installed-mcp-status error-state" role="alert">
          {hasStatus(secretBrokerageQuery.error, 401)
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {hasStatus(secretBrokerageQuery.error, 401)
                ? "Your signed-in session has expired"
                : hasStatus(secretBrokerageQuery.error, 403)
                  ? "Secret brokerage permission is required"
                  : "Secret brokerage inventory is unavailable"}
            </strong>
            <span>
              Existing lifecycle and runtime trust evidence remains available. Secret brokerage
              controls stay hidden until this scoped inventory can be read.
            </span>
          </div>
          {hasStatus(secretBrokerageQuery.error, 401) && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !hasStatus(secretBrokerageQuery.error, 403) ? (
            <button type="button" onClick={() => void secretBrokerageQuery.refetch()}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {runtimeActivationQuery.isError && (
        <div className="installed-mcp-status error-state" role="alert">
          {hasStatus(runtimeActivationQuery.error, 401)
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {hasStatus(runtimeActivationQuery.error, 401)
                ? "Your signed-in session has expired"
                : hasStatus(runtimeActivationQuery.error, 403)
                  ? "Runtime activation permission is required"
                  : "Runtime activation inventory is unavailable"}
            </strong>
            <span>
              Existing lifecycle and secret brokerage evidence remains available. Runtime health
              state and activation controls stay hidden until this scoped inventory can be read.
            </span>
          </div>
          {hasStatus(runtimeActivationQuery.error, 401) && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !hasStatus(runtimeActivationQuery.error, 403) ? (
            <button type="button" onClick={() => void runtimeActivationQuery.refetch()}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {targetSessionQuery.isError && (
        <div className="installed-mcp-status error-state" role="alert">
          {hasStatus(targetSessionQuery.error, 401)
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {hasStatus(targetSessionQuery.error, 401)
                ? "Your signed-in session has expired"
                : hasStatus(targetSessionQuery.error, 403)
                  ? "Target session verification permission is required"
                  : "Target session verification inventory is unavailable"}
            </strong>
            <span>
              Existing lifecycle and runtime-health evidence remains available. Target session
              state and verification controls stay hidden until this scoped inventory can be read.
            </span>
          </div>
          {hasStatus(targetSessionQuery.error, 401) && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !hasStatus(targetSessionQuery.error, 403) ? (
            <button type="button" onClick={() => void targetSessionQuery.refetch()}>
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {invocationAuthorizationQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {invocationAuthorizationQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {invocationAuthorizationQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : invocationAuthorizationQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Invocation authorization permission is required"
                  : "Invocation authorization inventory is unavailable"}
            </strong>
            <span>
              Verified target-session evidence remains visible. Authorization state and controls
              stay hidden until exact scoped inventory can be read.
            </span>
          </div>
          {invocationAuthorizationQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !invocationAuthorizationQueryErrors.some((error) => hasStatus(error, 403)) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of invocationAuthorizationQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Retry
            </button>
          ) : null}
        </div>
      )}
      {boundedInvocationQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {boundedInvocationQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {boundedInvocationQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : boundedInvocationQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Bounded invocation permission is required"
                  : "Bounded invocation inventory is unavailable"}
            </strong>
            <span>
              Invocation authorization evidence remains visible. Invocation completion state and
              controls stay hidden until exact authoritative inventory can be read.
            </span>
          </div>
          {boundedInvocationQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !boundedInvocationQueryErrors.some((error) => hasStatus(error, 403)) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of boundedInvocationQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Reload inventory
            </button>
          ) : null}
        </div>
      )}
      {invocationEvidenceQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {invocationEvidenceQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {invocationEvidenceQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : invocationEvidenceQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Evidence-preservation permission is required"
                  : "Invocation evidence inventory is unavailable"}
            </strong>
            <span>
              Bounded invocation completion remains visible. Evidence state and preservation
              controls stay hidden until exact authoritative inventory can be read.
            </span>
          </div>
          {invocationEvidenceQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !invocationEvidenceQueryErrors.some((error) => hasStatus(error, 403)) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of invocationEvidenceQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Reload inventory
            </button>
          ) : null}
        </div>
      )}
      {knowledgeDraftQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {knowledgeDraftQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {knowledgeDraftQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : knowledgeDraftQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Knowledge draft scope is required"
                  : "Knowledge draft inventory is unavailable"}
            </strong>
            <span>
              Preserved evidence remains visible. Draft state and curation controls stay hidden
              until exact authoritative inventory can be read.
            </span>
          </div>
          {knowledgeDraftQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !knowledgeDraftQueryErrors.some((error) => hasStatus(error, 403)) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of knowledgeDraftQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Reload inventory
            </button>
          ) : null}
        </div>
      )}
      {knowledgeReviewRequestQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {knowledgeReviewRequestQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {knowledgeReviewRequestQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : knowledgeReviewRequestQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Knowledge review request scope is required"
                  : "Knowledge review request inventory is unavailable"}
            </strong>
            <span>
              Immutable drafts remain visible. Review request state and controls stay hidden until
              exact authoritative inventory can be read.
            </span>
          </div>
          {knowledgeReviewRequestQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !knowledgeReviewRequestQueryErrors.some((error) => hasStatus(error, 403)) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of knowledgeReviewRequestQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Reload inventory
            </button>
          ) : null}
        </div>
      )}
      {knowledgeReviewerAssignmentQueryErrors.length > 0 && (
        <div className="installed-mcp-status error-state" role="alert">
          {knowledgeReviewerAssignmentQueryErrors.some((error) => hasStatus(error, 401))
            ? <LogIn size={18} />
            : <AlertTriangle size={18} />}
          <div>
            <strong>
              {knowledgeReviewerAssignmentQueryErrors.some((error) => hasStatus(error, 401))
                ? "Your signed-in session has expired"
                : knowledgeReviewerAssignmentQueryErrors.some((error) => hasStatus(error, 403))
                  ? "Reviewer assignment scope is required"
                  : "Reviewer assignment inventory is unavailable"}
            </strong>
            <span>
              Review requests remain visible. Assignment state and controls stay hidden until exact
              authoritative inventory can be read.
            </span>
          </div>
          {knowledgeReviewerAssignmentQueryErrors.some((error) => hasStatus(error, 401)) &&
          onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !knowledgeReviewerAssignmentQueryErrors.some(
            (error) => hasStatus(error, 403),
          ) ? (
            <button
              type="button"
              onClick={() => {
                for (const query of knowledgeReviewerAssignmentQueries) void query.refetch();
              }}
            >
              <RefreshCw size={15} /> Reload inventory
            </button>
          ) : null}
        </div>
      )}
      {instanceQuery.isLoading && (
        <div className="installed-mcp-status" role="status"><RefreshCw className="spin" size={18} /><span>Loading MCP lifecycle inventory...</span></div>
      )}
      {lifecycleMutationError && (
        <div className="installed-mcp-status error-state" role="alert">
          {mutationAuthenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
          <div>
            <strong>
              {mutationAuthenticationFailed
                ? "Your signed-in session has expired"
                : mutationAuthorizationFailed
                  ? "Connector lifecycle permission is required"
                  : mutationConflict
                    ? "MCP lifecycle changed"
                    : `MCP ${mutationAction} failed`}
            </strong>
            <span>
              {mutationAuthenticationFailed
                ? "Sign in again before changing MCP lifecycle records."
                : mutationAuthorizationFailed
                  ? "This signed-in account is missing the required role or scope."
                  : mutationConflict
                    ? "Refresh the MCP inventory and review the current package or instance state."
                    : mutationAction === "creation"
                      ? "Review the exact package, instance key, and creation policy."
                      : "Configured instances require governed decommissioning before retirement."}
            </span>
          </div>
          {mutationAuthenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : mutationConflict ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Refresh inventory
            </button>
          ) : null}
        </div>
      )}
      {!instanceQuery.isError && !instanceQuery.isLoading && instances.length === 0 ? (
        <div className="installed-mcp-empty"><Boxes size={24} /><div><strong>No {lifecycle === "all" ? "" : lifecycle} MCP instances</strong><span>{packages.length ? "Select Add MCP to create a disabled instance from a governed package." : "Complete package installation in the Builder workflow, then return here to add an MCP."}</span></div></div>
      ) : !instanceQuery.isLoading && !instanceQuery.isError ? (
        <div className="installed-mcp-table-wrap">
          <table className="installed-mcp-table">
            <thead><tr><th>MCP</th><th>Package</th><th>State</th><th>Owner</th><th>Lifecycle event</th><th>Actions</th></tr></thead>
            <tbody>
              {instances.map((instance) => {
                const binding = bindingByInstance.get(instance.record_id);
                const configured = Boolean(binding);
                const assignment = binding
                  ? assignmentByBinding.get(binding.binding_id)
                  : undefined;
                const credentialsAssigned = Boolean(assignment);
                const validation = assignment
                  ? validationByAssignment.get(assignment.assignment_id)
                  : undefined;
                const configurationValidated = Boolean(validation);
                const enablement = validation
                  ? enablementByValidation.get(validation.validation_id)
                  : undefined;
                const capabilitiesGoverned = Boolean(enablement);
                const runtimeTrust = enablement
                  ? runtimeTrustByEnablement.get(enablement.enablement_id)
                  : undefined;
                const runtimeTrusted = Boolean(runtimeTrust);
                const secretBrokerageAuthorization = runtimeTrust
                  ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
                  : undefined;
                const secretBrokerageGoverned = Boolean(secretBrokerageAuthorization);
                const runtimeActivation = secretBrokerageAuthorization
                  ? runtimeActivationBySecretBrokerage.get(secretBrokerageAuthorization.authorization_id)
                  : undefined;
                const runtimeDeactivation = runtimeActivation
                  ? runtimeDeactivationByActivation.get(runtimeActivation.activation_id)
                  : undefined;
                const runtimeHealthy = Boolean(runtimeActivation) && !runtimeDeactivation;
                const targetSessionVerification = runtimeHealthy && runtimeActivation
                  ? targetSessionByRuntimeActivation.get(runtimeActivation.activation_id)
                  : undefined;
                const targetSessionVerified = Boolean(targetSessionVerification);
                const invocationAuthorization = targetSessionVerification
                  ? invocationAuthorizationByTargetSession.get(
                    targetSessionVerification.verification_id,
                  )
                  : undefined;
                const invocationAuthorized = Boolean(invocationAuthorization);
                const boundedInvocation = invocationAuthorization
                  ? boundedInvocationByAuthorization.get(
                    invocationAuthorization.authorization_id,
                  )
                  : undefined;
                const capabilityInvoked = Boolean(boundedInvocation);
                const invocationEvidence = boundedInvocation
                  ? invocationEvidenceByInvocation.get(boundedInvocation.invocation_id)
                  : undefined;
                const evidencePreserved = Boolean(invocationEvidence);
                const knowledgeDraft = invocationEvidence
                  ? knowledgeDraftByEvidence.get(invocationEvidence.ingestion_id)
                  : undefined;
                const knowledgeDraftCreated = Boolean(knowledgeDraft);
                const knowledgeReviewRequest = knowledgeDraft
                  ? knowledgeReviewRequestByDraft.get(knowledgeDraft.draft_id)
                  : undefined;
                const knowledgeReviewRequested = Boolean(knowledgeReviewRequest);
                const knowledgeReviewerAssignment = knowledgeReviewRequest
                  ? knowledgeReviewerAssignmentByReviewRequest.get(
                      knowledgeReviewRequest.review_request_id,
                    )
                  : undefined;
                const knowledgeReviewerAssignmentClaim = knowledgeReviewRequest
                  ? knowledgeReviewerAssignmentClaimByReviewRequest.get(
                      knowledgeReviewRequest.review_request_id,
                    )
                  : undefined;
                const knowledgeReviewersAssigned = Boolean(knowledgeReviewerAssignment);
                const setupSteps = [
                  { complete: configured, label: "Target" },
                  { complete: credentialsAssigned, label: "Credential" },
                  { complete: configurationValidated, label: "Validation" },
                  { complete: capabilitiesGoverned, label: "Capabilities" },
                  { complete: runtimeTrusted, label: "Runtime trust" },
                  { complete: secretBrokerageGoverned, label: "Secret brokerage" },
                  { complete: runtimeHealthy, label: "Runtime" },
                  { complete: targetSessionVerified, label: "Target session" },
                ];
                const completedSetupSteps = setupSteps.filter((step) => step.complete).length;
                const nextSetupAction = !configured
                  ? {
                      icon: <Link2 size={15} />,
                      label: "Configure target",
                      onClick: () => setTargeting(instance),
                    }
                  : !credentialsAssigned
                    ? {
                        icon: <KeyRound size={15} />,
                        label: "Assign credential reference",
                        onClick: () => setCredentialing(instance),
                      }
                    : !configurationValidated
                      ? {
                          icon: <ShieldCheck size={15} />,
                          label: "Validate configuration",
                          onClick: () => setValidating(instance),
                        }
                      : !capabilitiesGoverned
                        ? enablementQuery.isSuccess ? {
                            icon: <ShieldCheck size={15} />,
                            label: "Govern capabilities",
                            onClick: () => setGoverningCapabilities(instance),
                          } : undefined
                        : !runtimeTrusted
                          ? runtimeTrustQuery.isSuccess ? {
                              icon: <ShieldCheck size={15} />,
                              label: "Establish runtime trust",
                              onClick: () => setEstablishingRuntimeTrust(instance),
                            } : undefined
                          : !secretBrokerageGoverned
                            ? secretBrokerageQuery.isSuccess ? {
                                icon: <KeyRound size={15} />,
                                label: "Authorize secret brokerage",
                                onClick: () => setAuthorizingSecretBrokerage(instance),
                              } : undefined
                            : !runtimeHealthy
                              ? runtimeDeactivation
                                ? undefined
                                : runtimeActivationQuery.isSuccess ? {
                                  icon: <Activity size={15} />,
                                  label: "Activate runtime",
                                  onClick: () => setActivatingRuntime(instance),
                                } : undefined
                              : !targetSessionVerified
                                ? targetSessionQuery.isSuccess ? {
                                    icon: <Link2 size={15} />,
                                    label: "Verify target session",
                                    onClick: () => setVerifyingTargetSession(instance),
                                  } : undefined
                                : undefined;
                const setupComplete = completedSetupSteps === setupSteps.length;
                return (
                  <tr key={instance.record_id}>
                    <td><strong>{instance.display_name}</strong><code>{instance.instance_key}</code></td>
                    <td><strong>{instance.connector_id}</strong><span>{instance.release_version}</span></td>
                    <td>
                      <span className={`state-badge ${
                        instance.instance_state === "retired"
                          ? "neutral"
                          : evidencePreserved || capabilityInvoked || invocationAuthorized || targetSessionVerified || runtimeHealthy || secretBrokerageGoverned || runtimeTrusted || capabilitiesGoverned
                            ? "success"
                            : "pending"
                      }`}>
                        {instance.instance_state === "retired"
                          ? "Retired"
                          : runtimeDeactivation
                            ? "Disabled / runtime stopped"
                          : knowledgeReviewersAssigned
                            ? "Enabled / reviewers assigned"
                          : knowledgeReviewerAssignmentClaim
                            ? "Enabled / assignment reconciliation"
                          : knowledgeReviewRequested
                            ? "Enabled / review requested"
                          : knowledgeDraftCreated
                            ? "Enabled / knowledge draft"
                          : evidencePreserved
                            ? "Enabled / evidence preserved"
                          : capabilityInvoked
                            ? "Enabled / capability invoked"
                          : invocationAuthorized
                            ? "Enabled / invocation authorized"
                          : targetSessionVerified
                            ? "Enabled / target session verified"
                          : runtimeHealthy
                            ? "Enabled / runtime healthy"
                          : secretBrokerageGoverned
                            ? "Enabled / secret brokerage governed"
                          : runtimeTrusted
                            ? "Enabled / runtime trusted"
                            : capabilitiesGoverned
                            ? "Enabled / capabilities governed"
                            : configurationValidated
                            ? "Disabled / configuration validated"
                            : credentialsAssigned
                            ? "Disabled / credentials assigned"
                            : configured
                              ? "Disabled / target configured"
                              : "Disabled / unconfigured"}
                      </span>
                    </td>
                    <td>{instance.owner_id}</td>
                    <td>
                      <span className="installed-mcp-event-label">
                        {instance.instance_state === "retired"
                          ? "Retired"
                          : runtimeDeactivation
                            ? "Runtime disabled"
                          : knowledgeReviewerAssignment
                            ? "Knowledge reviewers assigned"
                          : knowledgeReviewerAssignmentClaim
                            ? "Reviewer assignment reconciliation required"
                          : knowledgeReviewRequest
                            ? "Knowledge review requested"
                          : knowledgeDraft
                            ? "Knowledge draft created"
                          : invocationEvidence
                            ? "Evidence preserved"
                          : boundedInvocation
                            ? "Capability invoked"
                          : invocationAuthorization
                            ? "Invocation authorized"
                          : targetSessionVerification
                            ? "Target session verified"
                          : runtimeActivation
                            ? "Runtime healthy"
                          : secretBrokerageAuthorization
                            ? "Secret brokerage governed"
                          : runtimeTrust
                            ? "Runtime trusted"
                            : enablement
                            ? "Capabilities governed"
                            : validation
                            ? "Configuration validated"
                            : assignment
                            ? "Credentials assigned"
                            : binding
                              ? "Target bound"
                              : "Created"}
                      </span>
                      {new Date(runtimeDeactivation?.deactivated_at ?? knowledgeReviewerAssignment?.created_at ?? knowledgeReviewerAssignmentClaim?.claimed_at ?? knowledgeReviewRequest?.created_at ?? knowledgeDraft?.created_at ?? invocationEvidence?.ingested_at ?? boundedInvocation?.completed_at ?? invocationAuthorization?.authorized_at ?? targetSessionVerification?.verified_at ?? runtimeActivation?.healthy_at ?? secretBrokerageAuthorization?.authorized_at ?? runtimeTrust?.granted_at ?? enablement?.enabled_at ?? validation?.validated_at ?? assignment?.assigned_at ?? binding?.bound_at ?? instance.retired_at ?? instance.created_at).toLocaleString()}
                    </td>
                    <td>
                      {instance.instance_state === "disabled_unconfigured" &&
                        bindingQuery.isSuccess &&
                        assignmentQuery.isSuccess &&
                        validationQuery.isSuccess && (
                        <div className="installed-mcp-operator-flow">
                          <div className="installed-mcp-setup-progress">
                            <div>
                              <span>Setup progress</span>
                              <strong>{completedSetupSteps} of {setupSteps.length} complete</strong>
                            </div>
                            <div
                              className="installed-mcp-progress-track"
                              role="progressbar"
                              aria-label={`Setup progress for ${instance.display_name}`}
                              aria-valuemin={0}
                              aria-valuemax={setupSteps.length}
                              aria-valuenow={completedSetupSteps}
                            >
                              <span style={{ width: `${(completedSetupSteps / setupSteps.length) * 100}%` }} />
                            </div>
                            <ol aria-label={`Setup steps for ${instance.display_name}`}>
                              {setupSteps.map((step) => (
                                <li className={step.complete ? "complete" : undefined} key={step.label}>
                                  <span aria-hidden="true" />
                                  {step.label}
                                </li>
                              ))}
                            </ol>
                          </div>
                          <div className="installed-mcp-next-action">
                            <span>Next action</span>
                            {nextSetupAction ? (
                              <button
                                className="primary-button installed-mcp-row-action"
                                type="button"
                                aria-label={`${nextSetupAction.label} for ${instance.display_name}`}
                                onClick={nextSetupAction.onClick}
                              >
                                {nextSetupAction.icon}
                                <span>{nextSetupAction.label}</span>
                              </button>
                            ) : runtimeDeactivation ? (
                              <strong className="pending"><Power size={15} /> Runtime disabled</strong>
                            ) : setupComplete ? (
                              <strong><FileCheck2 size={15} /> Setup complete</strong>
                            ) : (
                              <strong className="pending"><AlertTriangle size={15} /> Action unavailable</strong>
                            )}
                          </div>
                          <details className="installed-mcp-advanced-governance">
                            <summary>
                              <ShieldCheck size={15} />
                              <span>Advanced governance</span>
                            </summary>
                            <div className="installed-mcp-row-actions">
                              {binding && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View target for ${instance.display_name}`} onClick={() => setTargeting(instance)}>
                                  <Link2 size={15} /><span>View target</span>
                                </button>
                              )}
                              {assignment && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View credentials for ${instance.display_name}`} onClick={() => setCredentialing(instance)}>
                                  <KeyRound size={15} /><span>View credentials</span>
                                </button>
                              )}
                              {validation && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View configuration for ${instance.display_name}`} onClick={() => setValidating(instance)}>
                                  <ShieldCheck size={15} /><span>View validation</span>
                                </button>
                              )}
                              {enablement && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View capabilities for ${instance.display_name}`} onClick={() => setGoverningCapabilities(instance)}>
                                  <ShieldCheck size={15} /><span>View capabilities</span>
                                </button>
                              )}
                              {runtimeTrust && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View runtime trust for ${instance.display_name}`} onClick={() => setEstablishingRuntimeTrust(instance)}>
                                  <ShieldCheck size={15} /><span>View runtime trust</span>
                                </button>
                              )}
                              {secretBrokerageAuthorization && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View secret brokerage for ${instance.display_name}`} onClick={() => setAuthorizingSecretBrokerage(instance)}>
                                  <KeyRound size={15} /><span>View secret brokerage</span>
                                </button>
                              )}
                              {runtimeActivation && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View runtime activation for ${instance.display_name}`} onClick={() => setActivatingRuntime(instance)}>
                                  <Activity size={15} /><span>View runtime activation</span>
                                </button>
                              )}
                              {runtimeHealthy && (
                                <button
                                  className="secondary-button installed-mcp-row-action"
                                  type="button"
                                  aria-label={`Disable runtime for ${instance.display_name}`}
                                  onClick={() => setDeactivatingRuntime(instance)}
                                >
                                  <Power size={15} /><span>Disable runtime</span>
                                </button>
                              )}
                              {targetSessionVerification && (
                                <button className="secondary-button installed-mcp-row-action" type="button" aria-label={`View target session for ${instance.display_name}`} onClick={() => setVerifyingTargetSession(instance)}>
                                  <Link2 size={15} /><span>View target session</span>
                                </button>
                              )}
                          {targetSessionVerification &&
                            invocationAuthorizationInventoryReady.has(
                              targetSessionVerification.verification_id,
                            ) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={invocationAuthorized
                                ? "View signed single-use invocation authorization evidence"
                                : "Authorize one exact capability for a later bounded invocation"}
                              aria-label={`${invocationAuthorized
                                ? "View authorization"
                                : "Authorize invocation"} for ${instance.display_name}`}
                              onClick={() => setAuthorizingInvocation(instance)}
                            >
                              <ShieldCheck size={15} />
                              <span>{invocationAuthorized
                                ? "View authorization"
                                : "Authorize invocation"}</span>
                            </button>
                          )}
                          {invocationAuthorization &&
                            boundedInvocationInventoryReady.has(
                              invocationAuthorization.authorization_id,
                            ) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={capabilityInvoked
                                ? "View immutable bounded invocation completion"
                                : "Invoke one exact authorized read-only capability"}
                              aria-label={`${capabilityInvoked
                                ? "View invocation"
                                : "Invoke once"} for ${instance.display_name}`}
                              onClick={() => setInvokingBounded(instance)}
                            >
                              <Play size={15} />
                              <span>{capabilityInvoked ? "View invocation" : "Invoke once"}</span>
                            </button>
                          )}
                          {boundedInvocation &&
                            invocationEvidenceInventoryReady.has(
                              boundedInvocation.invocation_id,
                            ) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={evidencePreserved
                                ? "View immutable invocation evidence"
                                : "Preserve the exact governed invocation result as evidence"}
                              aria-label={`${evidencePreserved
                                ? "View evidence"
                                : "Preserve evidence"} for ${instance.display_name}`}
                              onClick={() => setPreservingInvocationEvidence(instance)}
                            >
                              <Archive size={15} />
                              <span>{evidencePreserved ? "View evidence" : "Preserve evidence"}</span>
                            </button>
                          )}
                          {invocationEvidence &&
                            knowledgeDraftInventoryReady.has(invocationEvidence.ingestion_id) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={knowledgeDraft
                                ? "View immutable unapproved knowledge draft metadata"
                                : "Curate one immutable unapproved draft from preserved evidence"}
                              aria-label={`${knowledgeDraft
                                ? "View draft"
                                : "Curate knowledge"} for ${instance.display_name}`}
                              onClick={() => setCuratingKnowledge(instance)}
                            >
                              <BookMarked size={15} />
                              <span>{knowledgeDraft ? "View draft" : "Curate knowledge"}</span>
                            </button>
                          )}
                          {knowledgeDraft &&
                            knowledgeReviewRequestInventoryReady.has(knowledgeDraft.draft_id) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={knowledgeReviewRequest
                                ? "View the unassigned knowledge review request metadata"
                                : "Request review of this exact immutable knowledge draft"}
                              aria-label={`${knowledgeReviewRequest
                                ? "View request"
                                : "Request review"} for ${instance.display_name}`}
                              onClick={() => setRequestingKnowledgeReview(instance)}
                            >
                              <ClipboardCheck size={15} />
                              <span>{knowledgeReviewRequest ? "View request" : "Request review"}</span>
                            </button>
                          )}
                          {knowledgeReviewRequest &&
                            knowledgeReviewerAssignmentInventoryReady.has(
                              knowledgeReviewRequest.review_request_id,
                            ) && (
                            <button
                              className="secondary-button installed-mcp-row-action"
                              type="button"
                              title={knowledgeReviewerAssignment
                                ? "View authoritative reviewer assignment"
                                : knowledgeReviewerAssignmentClaim
                                  ? "View permanently consumed assignment claim status"
                                  : "Assign distinct domain and security review tracks"}
                              aria-label={`${knowledgeReviewerAssignment
                                ? "View assignment"
                                : knowledgeReviewerAssignmentClaim
                                  ? "View assignment status"
                                  : "Assign reviewers"} for ${instance.display_name}`}
                              onClick={(event) => {
                                setReviewerAssignmentReturnFocus(event.currentTarget);
                                setAssigningKnowledgeReviewers(instance);
                              }}
                            >
                              <UserCheck size={15} />
                              <span>{knowledgeReviewerAssignment
                                ? "View assignment"
                                : knowledgeReviewerAssignmentClaim
                                  ? "View assignment status"
                                  : "Assign reviewers"}</span>
                            </button>
                          )}
                          <button className="secondary-button installed-mcp-row-action" type="button" title="Review governed update evidence" aria-label={`Review update for ${instance.display_name}`} onClick={() => setReviewing(instance)}><ArrowUpCircle size={15} /><span>Review update</span></button>
                            </div>
                          </details>
                          {!configured && !credentialsAssigned && (
                            <button className="secondary-button installed-mcp-row-action danger" type="button" title="Remove from active management and preserve history" aria-label={`Remove ${instance.display_name}`} onClick={() => { retireMutation.reset(); setRetiring(instance); }}><Archive size={15} /><span>Remove</span></button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="installed-mcp-footnote"><span>{activeCount} active in this result</span><span>Lifecycle, bounded-invocation and immutable evidence records expose no secrets, commands, raw input or output. Preservation is one-way and grants no retry, knowledge publication, scheduling, workflow, execution, deployment or infrastructure mutation authority. Updates remain review-only.</span></div>
      {adding && (
        <AddMcpDialog
          catalog={bundledCatalog}
          packages={packages}
          policies={policies}
          pending={createMutation.isPending || createBundledMutation.isPending}
          onCancel={() => setAdding(false)}
          onOpenBuilder={openBuilder}
          onCatalogSubmit={(input) => createBundledMutation.mutate(input)}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}
      {retiring && <RetireMcpDialog instance={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ instance: retiring, reason })} />}
      {reviewing && <UpgradeReadinessDialog instance={reviewing} subjectId={subjectId} onCancel={() => setReviewing(null)} />}
      {targeting && (
        <TargetConfigurationDialog
          instance={targeting}
          binding={bindingByInstance.get(targeting.record_id)}
          onBindingCreated={(binding) => {
            queryClient.setQueryData<ConnectorTargetConfigurationBinding[]>(
              ["connector-target-bindings", subjectId],
              (current = []) => [
                ...current.filter(
                  (item) => item.source_instance_record_id !== binding.source_instance_record_id,
                ),
                binding,
              ],
            );
          }}
          onCancel={() => setTargeting(null)}
          onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        />
      )}
      {credentialing && (() => {
        const binding = bindingByInstance.get(credentialing.record_id);
        if (!binding) return null;
        return (
          <CredentialAssignmentDialog
            instance={credentialing}
            binding={binding}
            assignment={assignmentByBinding.get(binding.binding_id)}
            onAssignmentCreated={(assignment) => {
              queryClient.setQueryData<ConnectorCredentialAssignmentInventoryItem[]>(
                ["connector-credential-assignments", subjectId],
                (current = []) => [
                  ...current.filter(
                    (item) =>
                      item.source_target_binding_id !== assignment.source_target_binding_id,
                  ),
                  assignment,
                ],
              );
            }}
            onCancel={() => setCredentialing(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {validating && (() => {
        const binding = bindingByInstance.get(validating.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        if (!assignment) return null;
        return (
          <ConfigurationValidationDialog
            instance={validating}
            assignment={assignment}
            validation={validationByAssignment.get(assignment.assignment_id)}
            sessionScopeKey={sessionScopeKey}
            onValidationCreated={(validation) => {
              queryClient.setQueryData<ConnectorConfigurationValidationInventoryItem[]>(
                ["connector-configuration-validations", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_assignment_id !== validation.source_assignment_id,
                  ),
                  toConnectorConfigurationValidationInventoryItem(validation),
                ],
              );
            }}
            onCancel={() => setValidating(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {governingCapabilities && (() => {
        const binding = bindingByInstance.get(governingCapabilities.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        if (!validation) return null;
        return (
          <CapabilityEnablementDialog
            instance={governingCapabilities}
            validation={validation}
            enablement={enablementByValidation.get(validation.validation_id)}
            sessionScopeKey={sessionScopeKey}
            onEnablementCreated={(enablement) => {
              queryClient.setQueryData<ConnectorCapabilityEnablementInventoryItem[]>(
                ["connector-capability-enablements", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_validation_id !== enablement.source_validation_id,
                  ),
                  enablement,
                ],
              );
            }}
            onCancel={() => setGoverningCapabilities(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {establishingRuntimeTrust && (() => {
        const binding = bindingByInstance.get(establishingRuntimeTrust.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        if (!enablement) return null;
        return (
          <RuntimeTrustDialog
            instance={establishingRuntimeTrust}
            enablement={enablement}
            grant={runtimeTrustByEnablement.get(enablement.enablement_id)}
            sessionScopeKey={sessionScopeKey}
            onGrantCreated={(grant) => {
              queryClient.setQueryData<ConnectorRuntimeTrustGrantInventoryItem[]>(
                ["connector-runtime-trust-grants", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_enablement_id !== grant.source_enablement_id,
                  ),
                  grant,
                ],
              );
            }}
            onCancel={() => setEstablishingRuntimeTrust(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {authorizingSecretBrokerage && (() => {
        const binding = bindingByInstance.get(authorizingSecretBrokerage.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        if (!runtimeTrust) return null;
        return (
          <SecretBrokerageDialog
            instance={authorizingSecretBrokerage}
            runtimeTrust={runtimeTrust}
            authorization={secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)}
            sessionScopeKey={sessionScopeKey}
            onAuthorizationCreated={(authorization) => {
              queryClient.setQueryData<ConnectorSecretBrokerageAuthorizationInventoryItem[]>(
                ["connector-secret-brokerage-authorizations", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_runtime_trust_grant_id !==
                      authorization.source_runtime_trust_grant_id,
                  ),
                  authorization,
                ],
              );
            }}
            onCancel={() => setAuthorizingSecretBrokerage(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {activatingRuntime && (() => {
        const binding = bindingByInstance.get(activatingRuntime.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        if (!brokerage) return null;
        return (
          <RuntimeActivationDialog
            instance={activatingRuntime}
            brokerage={brokerage}
            activation={runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)}
            sessionScopeKey={sessionScopeKey}
            onActivationCreated={(activation) => {
              queryClient.setQueryData<ConnectorRuntimeActivationInventoryItem[]>(
                ["connector-runtime-activations", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_brokerage_authorization_id !==
                      activation.source_brokerage_authorization_id,
                  ),
                  activation,
                ],
              );
            }}
            onCancel={() => setActivatingRuntime(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {deactivatingRuntime && (() => {
        const binding = bindingByInstance.get(deactivatingRuntime.record_id);
        const assignment = binding ? assignmentByBinding.get(binding.binding_id) : undefined;
        const validation = assignment ? validationByAssignment.get(assignment.assignment_id) : undefined;
        const enablement = validation ? enablementByValidation.get(validation.validation_id) : undefined;
        const runtimeTrust = enablement ? runtimeTrustByEnablement.get(enablement.enablement_id) : undefined;
        const brokerage = runtimeTrust ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id) : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        if (!activation || runtimeDeactivationByActivation.has(activation.activation_id)) return null;
        return (
          <RuntimeDeactivationDialog
            activation={activation}
            instance={deactivatingRuntime}
            onCancel={() => setDeactivatingRuntime(null)}
            onDeactivated={(deactivation) => {
              queryClient.setQueryData<ConnectorRuntimeDeactivation[]>(
                ["connector-runtime-deactivations", sessionScopeKey],
                (current = []) => [
                  ...current.filter((item) => item.activation_id !== deactivation.activation_id),
                  deactivation,
                ],
              );
              setDeactivatingRuntime(null);
            }}
          />
        );
      })()}
      {verifyingTargetSession && (() => {
        const binding = bindingByInstance.get(verifyingTargetSession.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        if (!activation) return null;
        return (
          <TargetSessionDialog
            activation={activation}
            instance={verifyingTargetSession}
            verification={targetSessionByRuntimeActivation.get(activation.activation_id)}
            sessionScopeKey={sessionScopeKey}
            onVerificationCreated={(verification) => {
              queryClient.setQueryData<ConnectorTargetSessionVerificationInventoryItem[]>(
                ["connector-target-session-verifications", sessionScopeKey],
                (current = []) => [
                  ...current.filter(
                    (item) => item.source_runtime_activation_id !==
                      verification.source_runtime_activation_id,
                  ),
                  verification,
                ],
              );
            }}
            onCancel={() => setVerifyingTargetSession(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {authorizingInvocation && (() => {
        const binding = bindingByInstance.get(authorizingInvocation.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        const targetSession = activation
          ? targetSessionByRuntimeActivation.get(activation.activation_id)
          : undefined;
        if (!targetSession) return null;
        return (
          <InvocationAuthorizationDialog
            instance={authorizingInvocation}
            targetSession={targetSession}
            authorization={invocationAuthorizationByTargetSession.get(
              targetSession.verification_id,
            )}
            sessionScopeKey={sessionScopeKey}
            onAuthorizationCreated={(authorization) => {
              queryClient.setQueryData<ConnectorInvocationAuthorizationInventoryItem[]>(
                [
                  "connector-invocation-authorizations",
                  sessionScopeKey,
                  targetSession.verification_id,
                ],
                [authorization],
              );
            }}
            onCancel={() => setAuthorizingInvocation(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {invokingBounded && (() => {
        const binding = bindingByInstance.get(invokingBounded.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        const targetSession = activation
          ? targetSessionByRuntimeActivation.get(activation.activation_id)
          : undefined;
        const authorization = targetSession
          ? invocationAuthorizationByTargetSession.get(targetSession.verification_id)
          : undefined;
        if (!authorization) return null;
        return (
          <BoundedInvocationDialog
            authorization={authorization}
            instance={invokingBounded}
            invocation={boundedInvocationByAuthorization.get(authorization.authorization_id)}
            sessionScopeKey={sessionScopeKey}
            onInvocationCreated={(invocation) => {
              queryClient.setQueryData<ConnectorBoundedInvocationInventoryItem[]>(
                [
                  "connector-bounded-invocations",
                  sessionScopeKey,
                  authorization.authorization_id,
                ],
                [invocation],
              );
            }}
            onCancel={() => setInvokingBounded(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {preservingInvocationEvidence && (() => {
        const binding = bindingByInstance.get(preservingInvocationEvidence.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        const targetSession = activation
          ? targetSessionByRuntimeActivation.get(activation.activation_id)
          : undefined;
        const authorization = targetSession
          ? invocationAuthorizationByTargetSession.get(targetSession.verification_id)
          : undefined;
        const invocation = authorization
          ? boundedInvocationByAuthorization.get(authorization.authorization_id)
          : undefined;
        if (!invocation) return null;
        return (
          <InvocationEvidenceDialog
            invocation={invocation}
            instance={preservingInvocationEvidence}
            evidence={invocationEvidenceByInvocation.get(invocation.invocation_id)}
            sessionScopeKey={sessionScopeKey}
            onEvidenceCreated={(evidence) => {
              queryClient.setQueryData<ConnectorInvocationEvidenceInventoryItem[]>(
                [
                  "connector-invocation-evidence",
                  sessionScopeKey,
                  invocation.invocation_id,
                ],
                [evidence],
              );
            }}
            onCancel={() => setPreservingInvocationEvidence(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {curatingKnowledge && (() => {
        const binding = bindingByInstance.get(curatingKnowledge.record_id);
        const assignment = binding
          ? assignmentByBinding.get(binding.binding_id)
          : undefined;
        const validation = assignment
          ? validationByAssignment.get(assignment.assignment_id)
          : undefined;
        const enablement = validation
          ? enablementByValidation.get(validation.validation_id)
          : undefined;
        const runtimeTrust = enablement
          ? runtimeTrustByEnablement.get(enablement.enablement_id)
          : undefined;
        const brokerage = runtimeTrust
          ? secretBrokerageByRuntimeTrust.get(runtimeTrust.grant_id)
          : undefined;
        const activation = brokerage
          ? runtimeActivationBySecretBrokerage.get(brokerage.authorization_id)
          : undefined;
        const targetSession = activation
          ? targetSessionByRuntimeActivation.get(activation.activation_id)
          : undefined;
        const authorization = targetSession
          ? invocationAuthorizationByTargetSession.get(targetSession.verification_id)
          : undefined;
        const invocation = authorization
          ? boundedInvocationByAuthorization.get(authorization.authorization_id)
          : undefined;
        const evidence = invocation
          ? invocationEvidenceByInvocation.get(invocation.invocation_id)
          : undefined;
        if (!evidence || !knowledgeDraftInventoryReady.has(evidence.ingestion_id)) return null;
        return (
          <EvidenceKnowledgeDraftDialog
            evidence={evidence}
            instance={curatingKnowledge}
            sessionScopeKey={sessionScopeKey}
            onDraftCreated={(draft) => {
              queryClient.setQueryData<OperationalEvidenceKnowledgeDraftInventoryItem[]>(
                operationalEvidenceKnowledgeDraftQueryKey(
                  sessionScopeKey,
                  evidence.ingestion_id,
                ),
                [draft],
              );
            }}
            onCancel={() => setCuratingKnowledge(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {requestingKnowledgeReview && (() => {
        const draft = knowledgeDraftByInstance.get(requestingKnowledgeReview.instance_id);
        if (!draft || !knowledgeReviewRequestInventoryReady.has(draft.draft_id)) return null;
        return (
          <KnowledgeDraftReviewRequestDialog
            draft={draft}
            instance={requestingKnowledgeReview}
            sessionScopeKey={sessionScopeKey}
            onRequestCreated={(reviewRequest) => {
              queryClient.setQueryData<OperationalKnowledgeReviewRequestInventoryItem[]>(
                operationalKnowledgeReviewRequestQueryKey(sessionScopeKey, draft.draft_id),
                [reviewRequest],
              );
            }}
            onCancel={() => setRequestingKnowledgeReview(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
          />
        );
      })()}
      {assigningKnowledgeReviewers && (() => {
        const draft = knowledgeDraftByInstance.get(assigningKnowledgeReviewers.instance_id);
        const reviewRequest = draft ? knowledgeReviewRequestByDraft.get(draft.draft_id) : undefined;
        if (!reviewRequest || !knowledgeReviewRequestInventoryReady.has(reviewRequest.source_draft_id) ||
          !knowledgeReviewerAssignmentInventoryReady.has(reviewRequest.review_request_id)) {
          return null;
        }
        return (
          <ReviewerAssignmentDialog
            reviewRequest={reviewRequest}
            instance={assigningKnowledgeReviewers}
            sessionScopeKey={sessionScopeKey}
            onAssignmentCreated={(assignment) => {
              queryClient.setQueryData<OperationalKnowledgeReviewerAssignmentInventoryEntry[]>(
                operationalKnowledgeReviewerAssignmentQueryKey(
                  sessionScopeKey,
                  reviewRequest.review_request_id,
                ),
                [assignment],
              );
            }}
            onCancel={() => setAssigningKnowledgeReviewers(null)}
            onRequestEnterpriseLogin={onRequestEnterpriseLogin}
            returnFocusTo={reviewerAssignmentReturnFocus}
          />
        );
      })()}
    </section>
  );
}
