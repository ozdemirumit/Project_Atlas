import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Copy,
  Database,
  Download,
  FileCheck2,
  FileCode2,
  FileText,
  FlaskConical,
  GitBranch,
  KeyRound,
  LogIn,
  Monitor,
  PackageCheck,
  Network,
  Play,
  RefreshCw,
  ScanSearch,
  Search,
  Send,
  Server,
  ShieldCheck,
  LockKeyhole,
  Trash2,
  Scale,
  UserCheck,
  UserX,
  X,
} from "lucide-react";
import { lazy, Suspense, type FormEvent, useState } from "react";

import {
  createApiCredential,
  getApiCredentials,
  revokeApiCredential,
} from "./api/apiCredentials";
import { getAuditExportOverview, retryAuditExport } from "./api/auditExport";
import {
  previewBootstrapDataPlan,
} from "./api/bootstrapData";
import {
  deployBootstrapServices,
  previewBootstrapServicePlan,
  type BootstrapServiceDeploymentResult,
} from "./api/bootstrapServices";
import {
  handoffBootstrapIdentity,
  previewBootstrapIdentityPlan,
  type BootstrapIdentityHandoffResult,
} from "./api/bootstrapIdentity";
import {
  previewBootstrapIntegrationPlan,
  validateBootstrapIntegrations,
  type BootstrapIntegrationValidationResult,
} from "./api/bootstrapIntegrations";
import {
  previewBootstrapVerificationPlan,
  verifyBootstrapEndToEnd,
  type BootstrapVerificationResult,
} from "./api/bootstrapVerification";
import {
  completeBootstrapHandoff,
  previewBootstrapHandoffPlan,
  type BootstrapHandoffResult,
} from "./api/bootstrapHandoff";
import { getBootstrapPlan } from "./api/bootstrapPlan";
import { previewBootstrapInvalidation } from "./api/bootstrapInvalidation";
import { rebaseBootstrapPlan, type BootstrapRebaseResult } from "./api/bootstrapRebase";
import { getBootstrapState } from "./api/bootstrapState";
import { previewBootstrapTrustPlan } from "./api/bootstrapTrust";
import { previewDeploymentConfiguration } from "./api/deploymentConfiguration";
import { getStorageImpact } from "./api/graph";
import {
  createApprovalRequest,
  decideApprovalRequest,
  getApprovalRequest,
} from "./api/approvals";
import { getHealthCheckOverview, runHealthCheck } from "./api/healthChecks";
import { getCurrentIdentity } from "./api/identity";
import { ConnectorLifecycleOverview } from "./features/connectors/ConnectorLifecycleOverview";
import {
  ApplicationSidebar,
  ApplicationTopbar,
} from "./features/shell/ApplicationShell";
import { WorkspaceLoadBoundary } from "./features/shell/WorkspaceLoadBoundary";
import type { HealthViewId, WorkspaceId } from "./features/shell/workspace";
import { HealthWorkspaceNavigation } from "./features/health/HealthWorkspaceNavigation";
import { healthViewDescriptor } from "./features/health/healthWorkspace";
import { PackageApprovalPanel } from "./features/connectors/PackageApprovalPanel";
import {
  acquireConnectorPackage,
  analyzeConnectorPackageLicenses,
  analyzeConnectorPackageMalware,
  analyzeConnectorPackageStaticDependencies,
  analyzeConnectorPackageVulnerabilities,
  inventoryConnectorPackage,
  scanConnectorPackageContent,
  validateConnectorPackage,
  validateConnectorPackageAuthorityBehavior,
  validateConnectorPackageContracts,
  validateConnectorPackageFinal,
  validateConnectorPackageLabSelfTest,
  validateConnectorPackageRunner,
  validateConnectorPackageSchemaSemantics,
} from "./api/connectors";
import {
  createMcpBuilderDomainReview,
  createMcpBuilderCandidateHandoff,
  createMcpBuilderDesignCheckpoint,
  createMcpBuilderGeneration,
  createMcpBuilderLabValidation,
  createMcpBuilderProject,
  createMcpBuilderSecurityReview,
  createMcpBuilderValidation,
  downloadMcpBuilderCandidateArchive,
  getMcpBuilderGeneratedFile,
  type McpBuilderDesignDecision,
  type McpBuilderDomainDecision,
  type McpBuilderProject,
  type McpBuilderSecurityAssessment,
  type McpBuilderSecurityControl,
} from "./api/mcpBuilder";
import {
  createUpgradeHumanReviewCompletionReceipt,
  createUpgradeHumanReview,
  createUpgradeChangeReviewPacket,
  decideUpgradeHumanReview,
  getUpgradeHumanReviewInbox,
  previewUpgradeChangeReview,
  type UpgradeChangeReviewPacket,
  type UpgradeChangeReviewPreview,
  type UpgradeHumanReview,
  type UpgradeReviewCompletionReceipt,
} from "./api/changeReviews";
import {
  disableGovernedIdentity,
  getIdentityGovernance,
  revokeGovernedApiCredential,
  revokeGovernedSession,
} from "./api/identityGovernance";
import { createStorageInvestigation } from "./api/investigations";
import { getPlatformStatus } from "./api/platform";
import { createStorageRca } from "./api/rca";
import { createStorageRecommendation } from "./api/recommendations";
import {
  createLogicalBackup,
  LOGICAL_BACKUP_COMPONENTS,
  previewLogicalBackup,
  validateLogicalRestore,
  type LogicalBackup,
  type RestoreValidation,
} from "./api/recovery";
import {
  getReleasePreflight,
  type ReleasePreflightMode,
  type ReleasePreflightProfile,
} from "./api/releasePreflight";
import { createStorageTechnicalReport } from "./api/reports";
import {
  createBrowserSession,
  getBrowserSessions,
  logoutBrowserSession,
  revokeBrowserSession,
} from "./api/sessions";
import {
  getSecurityExportOverview,
  sendSecurityExportTestEvent,
} from "./api/securityExport";
import { getStorageOverview, type StorageAsset } from "./api/storage";
import {
  exportSupportBundle,
  previewSupportBundle,
  SUPPORT_BUNDLE_COMPONENTS,
  type SupportBundleExport,
} from "./api/supportBundles";
import {
  createWorkloadIdentity,
  getWorkloadIdentities,
  revokeWorkloadCredential,
  rotateWorkloadCredential,
} from "./api/workloadIdentities";
import {
  previewUpgradeReadiness,
  simulateUpgradeRollback,
  type UpgradeSimulation,
} from "./api/upgrades";

const HealthInventoryEvidenceWorkspace = lazy(
  () => import("./features/health/HealthInventoryEvidenceWorkspace"),
);
const HealthDecisionSupportWorkspace = lazy(
  () => import("./features/health/HealthDecisionSupportWorkspace"),
);
const HealthGovernanceReportWorkspace = lazy(
  () => import("./features/health/HealthGovernanceReportWorkspace"),
);
const HealthScheduledChecksWorkspace = lazy(
  () => import("./features/health/HealthScheduledChecksWorkspace"),
);
const SecurityExportWorkspace = lazy(
  () => import("./features/health/SecurityExportWorkspace"),
);
const ReleasePreflightWorkspace = lazy(
  () => import("./features/health/ReleasePreflightWorkspace"),
);
const DeploymentConfigurationWorkspace = lazy(
  () => import("./features/health/DeploymentConfigurationWorkspace"),
);
const BootstrapPlanWorkspace = lazy(
  () => import("./features/health/BootstrapPlanWorkspace"),
);
const BootstrapCheckpointWorkspace = lazy(
  () => import("./features/health/BootstrapCheckpointWorkspace"),
);
const BootstrapLeaseWorkspace = lazy(
  () => import("./features/health/BootstrapLeaseWorkspace"),
);
const BootstrapArtifactAcquisitionWorkspace = lazy(
  () => import("./features/health/BootstrapArtifactAcquisitionWorkspace"),
);
const BootstrapConfigurationRenderingWorkspace = lazy(
  () => import("./features/health/BootstrapConfigurationRenderingWorkspace"),
);
const BootstrapTrustProvisioningWorkspace = lazy(
  () => import("./features/health/BootstrapTrustProvisioningWorkspace"),
);
const BootstrapDataInitializationWorkspace = lazy(
  () => import("./features/health/BootstrapDataInitializationWorkspace"),
);
const BootstrapInvalidationWorkspace = lazy(
  () => import("./features/health/BootstrapInvalidationWorkspace"),
);

function statusLabel(status: string | undefined): string {
  if (!status) return "Connecting";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function localDateTimeInput(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function shouldOpenInspector(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(min-width: 821px)").matches
  );
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function healthLabel(health: StorageAsset["health"]): string {
  return health.charAt(0).toUpperCase() + health.slice(1);
}

function apiGrantLabel(permissionId: string): string {
  return (
    {
      "identity.self.read": "Identity profile",
      "storage.overview.read": "Storage overview",
      "graph.storage-impact.read": "Dependency impact",
      "health-check.overview.read": "Health check overview",
      "approval.request.read": "Approval packet",
    }[permissionId] ?? permissionId
  );
}

function governanceIdempotencyKey(
  resource: "identity" | "session" | "token" | "workload-create" | "workload-rotate" | "workload-revoke",
  version: number,
): string {
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  return `governance-${resource}-${version}-${nonce}`;
}

type PendingWorkloadAction =
  | { kind: "create" }
  | { kind: "rotate"; identityId: string; version: number }
  | { kind: "revoke"; credentialId: string; version: number };

function downloadMarkdown(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

const MCP_BUILDER_SECURITY_CONTROLS: Array<{
  id: McpBuilderSecurityControl;
  label: string;
}> = [
  { id: "provenance", label: "Provenance" },
  { id: "supply_chain", label: "Supply chain" },
  { id: "credentials", label: "Credentials" },
  { id: "network", label: "Network" },
  { id: "input_output", label: "Input and output" },
  { id: "injection_execution", label: "Injection and execution" },
  { id: "logging_redaction", label: "Logging and redaction" },
  { id: "runner_privileges", label: "Runner privileges" },
  { id: "capability_governance", label: "Capability governance" },
];

interface OperationalApplicationProps {
  activeHealthView: HealthViewId;
  activeWorkspace: Exclude<WorkspaceId, "Workspace">;
  onNavigateHealthView: (view: HealthViewId) => void;
  onNavigate: (workspace: WorkspaceId) => void;
}

export function OperationalApplication({
  activeHealthView,
  activeWorkspace,
  onNavigateHealthView,
  onNavigate,
}: OperationalApplicationProps) {
  const queryClient = useQueryClient();
  const activeNavigation = activeWorkspace;
  const activeHealthViewDescriptor = healthViewDescriptor(activeHealthView);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(shouldOpenInspector);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedHealthCheckId, setSelectedHealthCheckId] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [approvalRequestId, setApprovalRequestId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("approval_request_id"),
  );
  const [approvalRationale, setApprovalRationale] = useState("");
  const [apiCredentialName, setApiCredentialName] = useState("");
  const [apiCredentialPurpose, setApiCredentialPurpose] = useState("");
  const [apiCredentialLifetime, setApiCredentialLifetime] = useState(30);
  const [selectedApiGrants, setSelectedApiGrants] = useState<string[]>([]);
  const [issuedApiToken, setIssuedApiToken] = useState<string | null>(null);
  const [governanceSearch, setGovernanceSearch] = useState("");
  const [governanceReason, setGovernanceReason] = useState("");
  const [workloadSearch, setWorkloadSearch] = useState("");
  const [workloadReason, setWorkloadReason] = useState("");
  const [workloadIdentityId, setWorkloadIdentityId] = useState(
    "workload.atlas.health.scheduler",
  );
  const [workloadDisplayName, setWorkloadDisplayName] = useState("Health scheduler");
  const [workloadServiceId, setWorkloadServiceId] = useState("service.health-scheduler");
  const [workloadInstanceId, setWorkloadInstanceId] = useState(
    "instance.health-scheduler.local-01",
  );
  const [workloadOwnerId, setWorkloadOwnerId] = useState(
    "subject.enterprise.platform-owner",
  );
  const [workloadPurpose, setWorkloadPurpose] = useState(
    "Run bounded Atlas health-check coordination.",
  );
  const [workloadAudience, setWorkloadAudience] = useState("service.health-check");
  const [workloadSecretReference, setWorkloadSecretReference] = useState(
    "secret.connector.health-readonly",
  );
  const [issuedWorkloadToken, setIssuedWorkloadToken] = useState<string | null>(null);
  const [pendingWorkloadAction, setPendingWorkloadAction] =
    useState<PendingWorkloadAction | null>(null);
  const [auditSearch, setAuditSearch] = useState("");
  const [auditOutcome, setAuditOutcome] = useState("");
  const [releaseMode, setReleaseMode] = useState<ReleasePreflightMode>("offline");
  const [releaseProfile, setReleaseProfile] =
    useState<ReleasePreflightProfile>("linux_lab");
  const [bootstrapRebaseJustification, setBootstrapRebaseJustification] = useState("");
  const [bootstrapRebasePending, setBootstrapRebasePending] = useState(false);
  const [bootstrapRebaseResult, setBootstrapRebaseResult] =
    useState<BootstrapRebaseResult | null>(null);
  const [serviceDeploymentJustification, setServiceDeploymentJustification] = useState("");
  const [serviceDeploymentPending, setServiceDeploymentPending] = useState(false);
  const [serviceDeploymentResult, setServiceDeploymentResult] =
    useState<BootstrapServiceDeploymentResult | null>(null);
  const [identityHandoffJustification, setIdentityHandoffJustification] = useState("");
  const [identityHandoffPending, setIdentityHandoffPending] = useState(false);
  const [identityHandoffResult, setIdentityHandoffResult] =
    useState<BootstrapIdentityHandoffResult | null>(null);
  const [integrationValidationJustification, setIntegrationValidationJustification] =
    useState("");
  const [integrationValidationPending, setIntegrationValidationPending] = useState(false);
  const [integrationValidationResult, setIntegrationValidationResult] =
    useState<BootstrapIntegrationValidationResult | null>(null);
  const [verificationJustification, setVerificationJustification] = useState("");
  const [verificationPending, setVerificationPending] = useState(false);
  const [verificationResult, setVerificationResult] =
    useState<BootstrapVerificationResult | null>(null);
  const [handoffJustification, setHandoffJustification] = useState("");
  const [handoffPending, setHandoffPending] = useState(false);
  const [handoffResult, setHandoffResult] = useState<BootstrapHandoffResult | null>(null);
  const [supportComponentIds, setSupportComponentIds] = useState<string[]>([
    ...SUPPORT_BUNDLE_COMPONENTS,
  ]);
  const [supportLookbackHours, setSupportLookbackHours] = useState(24);
  const [supportJustification, setSupportJustification] = useState("");
  const [supportPending, setSupportPending] = useState(false);
  const [supportResult, setSupportResult] = useState<SupportBundleExport | null>(null);
  const [backupComponentIds, setBackupComponentIds] = useState<string[]>([
    ...LOGICAL_BACKUP_COMPONENTS,
  ]);
  const [backupJustification, setBackupJustification] = useState("");
  const [backupPending, setBackupPending] = useState(false);
  const [backupResult, setBackupResult] = useState<LogicalBackup | null>(null);
  const [restoreValidation, setRestoreValidation] = useState<RestoreValidation | null>(null);
  const [upgradeJustification, setUpgradeJustification] = useState("");
  const [upgradePending, setUpgradePending] = useState(false);
  const [upgradeSimulation, setUpgradeSimulation] = useState<UpgradeSimulation | null>(null);
  const [changeReviewPreview, setChangeReviewPreview] =
    useState<UpgradeChangeReviewPreview | null>(null);
  const [changeReviewPacket, setChangeReviewPacket] =
    useState<UpgradeChangeReviewPacket | null>(null);
  const [changeReviewPending, setChangeReviewPending] = useState(false);
  const [changeReviewJustification, setChangeReviewJustification] = useState("");
  const [changeReviewWindowStart, setChangeReviewWindowStart] = useState("");
  const [changeReviewWindowEnd, setChangeReviewWindowEnd] = useState("");
  const [changeReviewAcknowledged, setChangeReviewAcknowledged] = useState(false);
  const [humanReview, setHumanReview] = useState<UpgradeHumanReview | null>(null);
  const [humanReviewPending, setHumanReviewPending] = useState(false);
  const [humanReviewJustification, setHumanReviewJustification] = useState("");
  const [humanReviewAcknowledged, setHumanReviewAcknowledged] = useState(false);
  const [selectedInboxReviewId, setSelectedInboxReviewId] = useState<string | null>(null);
  const [reviewDecisionOutcome, setReviewDecisionOutcome] = useState<
    "approve" | "reject" | "needs_evidence" | "defer"
  >("approve");
  const [reviewDecisionRationale, setReviewDecisionRationale] = useState("");
  const [reviewDecisionAcknowledged, setReviewDecisionAcknowledged] = useState(false);
  const [reviewDecisionResult, setReviewDecisionResult] =
    useState<UpgradeHumanReview | null>(null);
  const [completionReceiptAcknowledged, setCompletionReceiptAcknowledged] = useState(false);
  const [completionReceipt, setCompletionReceipt] =
    useState<UpgradeReviewCompletionReceipt | null>(null);
  const [pendingDisableSubjectId, setPendingDisableSubjectId] = useState<string | null>(null);
  const [investigationQuestion, setInvestigationQuestion] = useState(
    "What evidence explains the current storage warning?",
  );
  const [builderVendor, setBuilderVendor] = useState("");
  const [builderProduct, setBuilderProduct] = useState("");
  const [builderProductVersion, setBuilderProductVersion] = useState("");
  const [builderSourceAuthority, setBuilderSourceAuthority] = useState("");
  const [builderSourceOwner, setBuilderSourceOwner] = useState("");
  const [builderDocumentationVersion, setBuilderDocumentationVersion] = useState("");
  const [builderPublicationDate, setBuilderPublicationDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [builderLicenseId, setBuilderLicenseId] = useState("");
  const [builderClassification, setBuilderClassification] =
    useState<McpBuilderProject["classification"]>("internal");
  const [builderRedistributionAllowed, setBuilderRedistributionAllowed] = useState(false);
  const [builderSourceDocument, setBuilderSourceDocument] = useState("");
  const [builderSourceName, setBuilderSourceName] = useState("");
  const [builderFileError, setBuilderFileError] = useState("");
  const [builderBoundary, setBuilderBoundary] = useState(
    "Read-only inventory and health evidence for the declared product boundary.",
  );
  const [builderConfigurationKey, setBuilderConfigurationKey] = useState(
    "config.vendor-endpoint",
  );
  const [builderSecretReference, setBuilderSecretReference] = useState(
    "secret.vendor-api-key",
  );
  const [builderSourceEntity, setBuilderSourceEntity] = useState("vendor.storage-system");
  const [builderAtlasEntity, setBuilderAtlasEntity] = useState("atlas.storage-system");
  const [builderDesignAcknowledged, setBuilderDesignAcknowledged] = useState(false);
  const [builderGenerationAcknowledged, setBuilderGenerationAcknowledged] = useState(false)…189924 tokens truncated…                               )}
                                <div className="governance-record-footer">
                                  <code>v{credential.version}</code>
                                  {(credential.state === "active" ||
                                    credential.state === "retiring") && (
                                    <button
                                      className="governance-revoke"
                                      type="button"
                                      disabled={!workloadReason.trim()}
                                      onClick={() =>
                                        setPendingWorkloadAction({
                                          kind: "revoke",
                                          credentialId: credential.credential_id,
                                          version: credential.version,
                                        })
                                      }
                                    >
                                      <Trash2 size={14} /> Revoke credential
                                    </button>
                                  )}
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>
                      </div>
                    </section>
                  )}
                  {activeNavigation === "Health" && activeHealthView === "governance" && (
                    <WorkspaceLoadBoundary
                      compact
                      resetKey={securityExport?.generated_at ?? overview.snapshot_id}
                      workspace="Health"
                    >
                      <Suspense
                        fallback={
                          <div className="workspace-message" aria-live="polite" aria-busy="true">
                            <Clock3 size={22} />
                            <div>
                              <h2>Loading Security Export</h2>
                              <p>Preparing authorized Syslog and SIEM delivery evidence.</p>
                            </div>
                          </div>
                        }
                      >
                        <SecurityExportWorkspace
                          error={securityExportQuery.isError}
                          loading={securityExportQuery.isLoading}
                          onSendTestEvent={() => securityExportTestMutation.mutate()}
                          overview={securityExport}
                          testDelivered={Boolean(securityExportTestMutation.data)}
                          testError={securityExportTestMutation.isError}
                          testPending={securityExportTestMutation.isPending}
                        />
                      </Suspense>
                    </WorkspaceLoadBoundary>
                  )}

                  {activeNavigation === "Health" && activeHealthView === "overview" && (
                    <WorkspaceLoadBoundary
                      compact
                      resetKey={
                        healthChecks?.generated_at ??
                        selectedHealthCheck?.definition_id ??
                        overview.snapshot_id
                      }
                      workspace="Health"
                    >
                      <Suspense
                        fallback={
                          <div
                            className="workspace-message"
                            aria-live="polite"
                            aria-busy="true"
                          >
                            <Clock3 size={22} />
                            <div>
                              <h2>Loading scheduled health checks</h2>
                              <p>Preparing authorized read-only check presentation.</p>
                            </div>
                          </div>
                        }
                      >
                        <HealthScheduledChecksWorkspace
                          error={healthChecksQuery.isError}
                          loading={healthChecksQuery.isLoading}
                          onRunCheck={() => {
                            if (selectedHealthCheck) {
                              runHealthCheckMutation.mutate(selectedHealthCheck.definition_id);
                            }
                          }}
                          onSelectDefinition={setSelectedHealthCheckId}
                          overview={healthChecks}
                          runError={runHealthCheckMutation.isError}
                          runPending={runHealthCheckMutation.isPending}
                          selectedDefinition={selectedHealthCheck}
                          selectedRun={selectedHealthRun}
                          selectedSchedule={selectedHealthSchedule}
                        />
                      </Suspense>
                    </WorkspaceLoadBoundary>
                  )}

                  {activeNavigation === "Health" && activeHealthView === "investigate" && (
                    <WorkspaceLoadBoundary
                      compact
                      resetKey={
                        recommendation?.recommendation_id ??
                        rcaCase?.case_id ??
                        reasoningArtifact?.artifact_id ??
                        overview.snapshot_id
                      }
                      workspace="Health"
                    >
                      <Suspense
                        fallback={
                          <div
                            className="workspace-message"
                            aria-live="polite"
                            aria-busy="true"
                          >
                            <Clock3 size={22} />
                            <div>
                              <h2>Loading Health decision support</h2>
                              <p>
                                Preparing governed investigation, RCA, and recommendation evidence.
                              </p>
                            </div>
                          </div>
                        }
                      >
                        <HealthDecisionSupportWorkspace
                          canBuildRca={Boolean(reasoningArtifact && selectedAsset)}
                          canCompareOptions={Boolean(rcaCase)}
                          investigationError={investigationMutation.isError}
                          investigationPending={investigationMutation.isPending}
                          onBuildRca={() => {
                            if (reasoningArtifact && selectedAsset) {
                              recommendationMutation.reset();
                              reportMutation.reset();
                              rcaMutation.mutate({
                                targetId: selectedAsset.asset_id,
                                actualBehavior:
                                  reasoningArtifact.summary.known[0] ??
                                  `Storage health is ${selectedAsset.health}.`,
                              });
                            }
                          }}
                          onCompareOptions={() => {
                            if (rcaCase) {
                              reportMutation.reset();
                              approvalCreateMutation.reset();
                              approvalDecisionMutation.reset();
                              setApprovalRequestId(null);
                              const url = new URL(window.location.href);
                              url.searchParams.delete("approval_request_id");
                              window.history.replaceState({}, "", url);
                              recommendationMutation.mutate({
                                targetId: rcaCase.target_id,
                                caseId: rcaCase.case_id,
                                version: rcaCase.version,
                              });
                            }
                          }}
                          rcaCase={rcaCase}
                          rcaError={rcaMutation.isError}
                          rcaPending={rcaMutation.isPending}
                          reasoningArtifact={reasoningArtifact}
                          recommendation={recommendation}
                          recommendationError={recommendationMutation.isError}
                          recommendationPending={recommendationMutation.isPending}
                        />
                      </Suspense>
                    </WorkspaceLoadBoundary>
                  )}

                  {activeNavigation === "Health" && activeHealthView === "investigate" && (
                    <WorkspaceLoadBoundary
                      compact
                      resetKey={
                        technicalReport?.report_id ??
                        approval?.request_id ??
                        recommendation?.recommendation_id ??
                        overview.snapshot_id
                      }
                      workspace="Health"
                    >
                      <Suspense
                        fallback={
                          <div
                            className="workspace-message"
                            aria-live="polite"
                            aria-busy="true"
                          >
                            <Clock3 size={22} />
                            <div>
                              <h2>Loading Health governance</h2>
                              <p>Preparing approval and technical report presentation.</p>
                            </div>
                          </div>
                        }
                      >
                        <HealthGovernanceReportWorkspace
                          approval={approval}
                          approvalDecisionError={approvalDecisionMutation.isError}
                          approvalDecisionPending={approvalDecisionMutation.isPending}
                          approvalError={
                            approvalQuery.isError || approvalCreateMutation.isError
                          }
                          approvalLoading={
                            approvalQuery.isLoading || approvalCreateMutation.isPending
                          }
                          approvalRationale={approvalRationale}
                          canGenerateReport={Boolean(recommendation && incidentReference)}
                          canReviewApproval={canReviewApproval}
                          canSubmitApproval={Boolean(recommendation?.preferred_option_id)}
                          onApprovalRationaleChange={setApprovalRationale}
                          onDecideApproval={(outcome) => {
                            if (approval) {
                              approvalDecisionMutation.mutate({
                                requestId: approval.request_id,
                                version: approval.version,
                                outcome,
                                rationale: approvalRationale.trim(),
                              });
                            }
                          }}
                          onDownloadReport={() => {
                            if (technicalReport) {
                              downloadMarkdown(
                                `atlas-${technicalReport.target_id.split(".").at(-1) ?? "storage"}-decision-report-v${technicalReport.version}.md`,
                                technicalReport.rendered_markdown,
                              );
                            }
                          }}
                          onGenerateReport={() => {
                            if (recommendation && incidentReference) {
                              reportMutation.mutate({
                                targetId: recommendation.target_id,
                                recommendationId: recommendation.recommendation_id,
                                recommendationVersion: recommendation.version,
                                incidentReference,
                              });
                            }
                          }}
                          onSubmitApproval={() => {
                            if (recommendation?.preferred_option_id) {
                              approvalCreateMutation.mutate({
                                targetId: recommendation.target_id,
                                recommendationId: recommendation.recommendation_id,
                                recommendationVersion: recommendation.version,
                                optionId: recommendation.preferred_option_id,
                              });
                            }
                          }}
                          reportError={reportMutation.isError}
                          reportPending={reportMutation.isPending}
                          technicalReport={technicalReport}
                        />
                      </Suspense>
                    </WorkspaceLoadBoundary>
                  )}

                </>
              )}
            </div>

            {activeNavigation === "Health" && activeHealthView === "investigate" && (
              <div className="composer-wrap">
              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  const question = investigationQuestion.trim();
                  if (selectedAsset && question) {
                    rcaMutation.reset();
                    recommendationMutation.reset();
                    reportMutation.reset();
                    investigationMutation.mutate({ targetId: selectedAsset.asset_id, question });
                  }
                }}
              >
                <textarea
                  aria-label="Ask Atlas"
                  placeholder="Ask Atlas to investigate the selected storage system..."
                  rows={2}
                  value={investigationQuestion}
                  onChange={(event) => setInvestigationQuestion(event.target.value)}
                  disabled={!selectedAsset || investigationMutation.isPending}
                />
                <div className="composer-footer">
                  <span>Authorized evidence Â· 24-hour UTC window Â· decision support only</span>
                  <button
                    className="send-button"
                    type="submit"
                    aria-label="Start investigation"
                    disabled={
                      !selectedAsset ||
                      !investigationQuestion.trim() ||
                      investigationMutation.isPending
                    }
                  >
                    <Send size={17} />
                  </button>
                </div>
              </form>
              </div>
            )}
          </section>

          {inspectorOpen && activeNavigation === "Health" && (
            <aside className="inspector" aria-label="Current context">
              <div className="inspector-header">
                <div>
                  <p className="eyebrow">CURRENT CONTEXT</p>
                  <h2>{selectedAsset?.model ?? "Storage assessment"}</h2>
                </div>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="Close context panel"
                  onClick={() => setInspectorOpen(false)}
                >
                  <X size={18} />
                </button>
              </div>

              <section className="inspector-section">
                <h3>Runtime</h3>
                <dl className="status-list">
                  <div>
                    <dt>API</dt>
                    <dd>
                      <span className={`status-dot ${state ?? "loading"}`} />
                      {statusLabel(state)}
                    </dd>
                  </div>
                  <div>
                    <dt>Environment</dt>
                    <dd>{platform?.environment ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{platform?.version ?? "--"}</dd>
                  </div>
                </dl>
                {statusQuery.isError && (
                  <p className="inline-alert">The API is not reachable.</p>
                )}
              </section>

              <section className="inspector-section">
                <h3>Data boundary</h3>
                <dl className="status-list context-list">
                  <div>
                    <dt>Profile</dt>
                    <dd className="synthetic-label">Synthetic lab</dd>
                  </div>
                  <div>
                    <dt>Scope</dt>
                    <dd>{overview?.site_id ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>Target</dt>
                    <dd>{overview?.target_id ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>Generated</dt>
                    <dd>{formatTimestamp(overview?.generated_at)}</dd>
                  </div>
                </dl>
              </section>

              <section className="inspector-section">
                <h3>Selected system</h3>
                {selectedAsset ? (
                  <dl className="status-list context-list">
                    <div>
                      <dt>Model</dt>
                      <dd>{selectedAsset.model}</dd>
                    </div>
                    <div>
                      <dt>Serial</dt>
                      <dd>{selectedAsset.serial_number}</dd>
                    </div>
                    <div>
                      <dt>Health</dt>
                      <dd className={`${selectedAsset.health}-text`}>
                        {healthLabel(selectedAsset.health)}
                      </dd>
                    </div>
                    <div>
                      <dt>Evidence</dt>
                      <dd>{selectedAsset.evidence_references.length} linked</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="context-empty">No authorized storage context is loaded.</p>
                )}
              </section>

              <section className="inspector-section">
                <h3>Graph context</h3>
                {impact ? (
                  <dl className="status-list context-list">
                    <div>
                      <dt>Snapshot</dt>
                      <dd>{impact.snapshot_id}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{impact.freshness}</dd>
                    </div>
                    <div>
                      <dt>Completeness</dt>
                      <dd>{impact.completeness}</dd>
                    </div>
                    <div>
                      <dt>Path evidence</dt>
                      <dd>{longestImpactPath?.evidence_references.length ?? 0} linked</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="context-empty">No authorized graph context is loaded.</p>
                )}
              </section>

            </aside>
          )}
        </div>
      </main>
    </div>
  );
}

