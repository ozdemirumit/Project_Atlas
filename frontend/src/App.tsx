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
import { lazy, Suspense, type FormEvent, useEffect, useRef, useState } from "react";

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
  previewBootstrapServicePlan,
} from "./api/bootstrapServices";
import { previewBootstrapIdentityPlan } from "./api/bootstrapIdentity";
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
import { ConnectorWorkspaceNavigation } from "./features/connectors/ConnectorWorkspaceNavigation";
import {
  ApplicationSidebar,
  ApplicationTopbar,
} from "./features/shell/ApplicationShell";
import { WorkspaceLoadBoundary } from "./features/shell/WorkspaceLoadBoundary";
import type { ConnectorViewId, HealthViewId, WorkspaceId } from "./features/shell/workspace";
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
import {
  createStorageTechnicalReport,
  decideItsmHandoffReview,
  getItsmHandoffReview,
  getTechnicalReport,
  type ItsmHandoffReviewOutcome,
} from "./api/reports";
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
const InventoryDeviceRegistryWorkspace = lazy(
  () => import("./features/health/InventoryDeviceRegistryWorkspace"),
);
const ItsmIntegrationReadinessWorkspace = lazy(
  () => import("./features/health/ItsmIntegrationReadinessWorkspace"),
);
const InstalledMcpManagementWorkspace = lazy(
  () => import("./features/connectors/InstalledMcpManagementWorkspace"),
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
const BootstrapServiceDeploymentWorkspace = lazy(
  () => import("./features/health/BootstrapServiceDeploymentWorkspace"),
);
const BootstrapIdentityHandoffWorkspace = lazy(
  () => import("./features/health/BootstrapIdentityHandoffWorkspace"),
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

const connectorViewTargetIds: Record<ConnectorViewId, string> = {
  inventory: "connector-view-inventory",
  builder: "connector-view-builder",
  runtime: "connector-view-runtime",
  knowledge: "connector-view-knowledge",
};

interface OperationalApplicationProps {
  activeConnectorView: ConnectorViewId;
  activeHealthView: HealthViewId;
  activeWorkspace: Exclude<WorkspaceId, "Workspace">;
  onNavigateConnectorView: (view: ConnectorViewId) => void;
  onNavigateHealthView: (view: HealthViewId) => void;
  onNavigate: (workspace: WorkspaceId) => void;
}

export function OperationalApplication({
  activeConnectorView,
  activeHealthView,
  activeWorkspace,
  onNavigateConnectorView,
  onNavigateHealthView,
  onNavigate,
}: OperationalApplicationProps) {
  const queryClient = useQueryClient();
  const activeNavigation = activeWorkspace;
  const activeHealthViewDescriptor = healthViewDescriptor(activeHealthView);
  const connectorFocusTarget = useRef<ConnectorViewId | null>(null);

  useEffect(() => {
    if (activeNavigation !== "Connectors") return;
    const frame = window.requestAnimationFrame(() => {
      const target = document.getElementById(connectorViewTargetIds[activeConnectorView]);
      target?.scrollIntoView?.({
        block: "start",
        behavior:
          typeof window.matchMedia === "function" &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
      });
      if (connectorFocusTarget.current === activeConnectorView) {
        target?.focus({ preventScroll: true });
        connectorFocusTarget.current = null;
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeConnectorView, activeNavigation]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(shouldOpenInspector);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedHealthCheckId, setSelectedHealthCheckId] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [enterpriseLoginRequested, setEnterpriseLoginRequested] = useState(false);
  const [approvalRequestId, setApprovalRequestId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("approval_request_id"),
  );
  const [technicalReportId, setTechnicalReportId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("report_id"),
  );
  const [approvalRationale, setApprovalRationale] = useState("");
  const [itsmReviewRationale, setItsmReviewRationale] = useState("");
  const [itsmReviewAcknowledged, setItsmReviewAcknowledged] = useState(false);
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
  const [builderGenerationAcknowledged, setBuilderGenerationAcknowledged] = useState(false);
  const [builderValidationAcknowledged, setBuilderValidationAcknowledged] = useState(false);
  const [builderDomainReviewAcknowledged, setBuilderDomainReviewAcknowledged] = useState(false);
  const [builderDomainReviewSummary, setBuilderDomainReviewSummary] = useState(
    "Human domain review completed against the exact analyzed source lineage.",
  );
  const [builderDomainDecisions, setBuilderDomainDecisions] = useState<
    Record<string, McpBuilderDomainDecision>
  >({});
  const [builderSecurityReviewAcknowledged, setBuilderSecurityReviewAcknowledged] =
    useState(false);
  const [builderSecurityReviewSummary, setBuilderSecurityReviewSummary] = useState(
    "Independent security review completed against the exact immutable evidence.",
  );
  const [builderSecurityAssessments, setBuilderSecurityAssessments] = useState<
    Partial<Record<McpBuilderSecurityControl, McpBuilderSecurityAssessment>>
  >({});
  const [builderLabValidationAcknowledged, setBuilderLabValidationAcknowledged] =
    useState(false);
  const [builderCandidateHandoffAcknowledged, setBuilderCandidateHandoffAcknowledged] =
    useState(false);
  const [builderPackageAcquisitionAcknowledged, setBuilderPackageAcquisitionAcknowledged] =
    useState(false);
  const [builderPackageValidationAcknowledged, setBuilderPackageValidationAcknowledged] =
    useState(false);
  const [builderPackageInventoryAcknowledged, setBuilderPackageInventoryAcknowledged] =
    useState(false);
  const [builderContentPolicyScanAcknowledged, setBuilderContentPolicyScanAcknowledged] =
    useState(false);
  const [builderSchemaSemanticsAcknowledged, setBuilderSchemaSemanticsAcknowledged] =
    useState(false);
  const [builderAuthorityBehaviorAcknowledged, setBuilderAuthorityBehaviorAcknowledged] =
    useState(false);
  const [builderStaticDependencyAcknowledged, setBuilderStaticDependencyAcknowledged] =
    useState(false);
  const [builderVulnerabilityAcknowledged, setBuilderVulnerabilityAcknowledged] = useState(false);
  const [builderMalwareAcknowledged, setBuilderMalwareAcknowledged] = useState(false);
  const [builderLicenseAcknowledged, setBuilderLicenseAcknowledged] = useState(false);
  const [builderContractAcknowledged, setBuilderContractAcknowledged] = useState(false);
  const [builderRunnerAcknowledged, setBuilderRunnerAcknowledged] = useState(false);
  const [builderLabSelfTestAcknowledged, setBuilderLabSelfTestAcknowledged] = useState(false);
  const [builderFinalValidationAcknowledged, setBuilderFinalValidationAcknowledged] =
    useState(false);
  const [builderLabPlanId, setBuilderLabPlanId] = useState(
    "connector-lab-plan.development-readonly",
  );
  const [builderLabPlanDigest, setBuilderLabPlanDigest] = useState(
    "ca40dd40e192ccb62e644cd5151e2445c0fa018f8849ded22eada41a1c93f770",
  );
  const [builderFinalPolicyId, setBuilderFinalPolicyId] = useState(
    "connector-final-policy.development",
  );
  const [builderFinalPolicyDigest, setBuilderFinalPolicyDigest] = useState(
    "bed76a50dd603345e42fb5206b44bead8da5f5ff6a27033913d899dcf7989149",
  );
  const [builderSelectedGeneratedFile, setBuilderSelectedGeneratedFile] = useState("");
  const [builderDesignDecisions, setBuilderDesignDecisions] = useState<
    Record<string, McpBuilderDesignDecision>
  >({});

  const navigateToWorkspace = (workspace: WorkspaceId) => {
    setSidebarOpen(false);
    if (workspace !== "Health") setInspectorOpen(false);
    onNavigate(workspace);
  };

  const statusQuery = useQuery({
    queryKey: ["platform-status"],
    queryFn: getPlatformStatus,
    refetchInterval: 30_000,
    retry: 1,
  });
  const identityQuery = useQuery({
    queryKey: ["current-identity"],
    queryFn: getCurrentIdentity,
    retry: false,
  });
  const identity = identityQuery.data?.data;
  const builderGeneratedFileMutation = useMutation({
    mutationFn: getMcpBuilderGeneratedFile,
  });
  const builderCandidateHandoffMutation = useMutation({
    mutationFn: createMcpBuilderCandidateHandoff,
    onSuccess: () => setBuilderCandidateHandoffAcknowledged(false),
  });
  const builderPackageAcquisitionMutation = useMutation({
    mutationFn: acquireConnectorPackage,
    onSuccess: () => setBuilderPackageAcquisitionAcknowledged(false),
  });
  const builderPackageValidationMutation = useMutation({
    mutationFn: validateConnectorPackage,
    onSuccess: () => setBuilderPackageValidationAcknowledged(false),
  });
  const builderPackageInventoryMutation = useMutation({
    mutationFn: inventoryConnectorPackage,
    onSuccess: () => setBuilderPackageInventoryAcknowledged(false),
  });
  const builderContentPolicyScanMutation = useMutation({
    mutationFn: scanConnectorPackageContent,
    onSuccess: () => setBuilderContentPolicyScanAcknowledged(false),
  });
  const builderSchemaSemanticsMutation = useMutation({
    mutationFn: validateConnectorPackageSchemaSemantics,
    onSuccess: () => setBuilderSchemaSemanticsAcknowledged(false),
  });
  const builderAuthorityBehaviorMutation = useMutation({
    mutationFn: validateConnectorPackageAuthorityBehavior,
    onSuccess: () => setBuilderAuthorityBehaviorAcknowledged(false),
  });
  const builderStaticDependencyMutation = useMutation({
    mutationFn: analyzeConnectorPackageStaticDependencies,
    onSuccess: () => setBuilderStaticDependencyAcknowledged(false),
  });
  const builderVulnerabilityMutation = useMutation({
    mutationFn: analyzeConnectorPackageVulnerabilities,
    onSuccess: () => setBuilderVulnerabilityAcknowledged(false),
  });
  const builderMalwareMutation = useMutation({
    mutationFn: analyzeConnectorPackageMalware,
    onSuccess: () => setBuilderMalwareAcknowledged(false),
  });
  const builderLicenseMutation = useMutation({
    mutationFn: analyzeConnectorPackageLicenses,
    onSuccess: () => setBuilderLicenseAcknowledged(false),
  });
  const builderContractMutation = useMutation({
    mutationFn: validateConnectorPackageContracts,
    onSuccess: () => setBuilderContractAcknowledged(false),
  });
  const builderRunnerMutation = useMutation({
    mutationFn: validateConnectorPackageRunner,
    onSuccess: () => setBuilderRunnerAcknowledged(false),
  });
  const builderLabSelfTestMutation = useMutation({
    mutationFn: validateConnectorPackageLabSelfTest,
    onSuccess: () => setBuilderLabSelfTestAcknowledged(false),
  });
  const builderFinalValidationMutation = useMutation({
    mutationFn: validateConnectorPackageFinal,
    onSuccess: () => setBuilderFinalValidationAcknowledged(false),
  });
  const builderCandidateArchiveMutation = useMutation({
    mutationFn: downloadMcpBuilderCandidateArchive,
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },
  });
  const resetBuilderCandidateHandoff = () => {
    builderCandidateHandoffMutation.reset();
    builderCandidateArchiveMutation.reset();
    builderPackageAcquisitionMutation.reset();
    builderPackageValidationMutation.reset();
    builderPackageInventoryMutation.reset();
    builderContentPolicyScanMutation.reset();
    builderSchemaSemanticsMutation.reset();
    builderAuthorityBehaviorMutation.reset();
    builderStaticDependencyMutation.reset();
    builderVulnerabilityMutation.reset();
    builderMalwareMutation.reset();
    builderLicenseMutation.reset();
    builderContractMutation.reset();
    builderRunnerMutation.reset();
    builderLabSelfTestMutation.reset();
    builderFinalValidationMutation.reset();
    setBuilderCandidateHandoffAcknowledged(false);
    setBuilderPackageAcquisitionAcknowledged(false);
    setBuilderPackageValidationAcknowledged(false);
    setBuilderPackageInventoryAcknowledged(false);
    setBuilderContentPolicyScanAcknowledged(false);
    setBuilderSchemaSemanticsAcknowledged(false);
    setBuilderAuthorityBehaviorAcknowledged(false);
    setBuilderStaticDependencyAcknowledged(false);
    setBuilderVulnerabilityAcknowledged(false);
    setBuilderMalwareAcknowledged(false);
    setBuilderLicenseAcknowledged(false);
    setBuilderContractAcknowledged(false);
    setBuilderRunnerAcknowledged(false);
    setBuilderLabSelfTestAcknowledged(false);
    setBuilderFinalValidationAcknowledged(false);
  };
  const builderPackageValidationSeparated = Boolean(
    identity &&
      builderCandidateHandoffMutation.data?.data &&
      builderPackageAcquisitionMutation.data?.data &&
      ![
        builderCandidateHandoffMutation.data.data.custodied_by,
        builderCandidateHandoffMutation.data.data.domain_reviewed_by,
        builderCandidateHandoffMutation.data.data.security_reviewed_by,
        builderCandidateHandoffMutation.data.data.lab_operated_by,
        builderPackageAcquisitionMutation.data.data.acquired_by,
      ].includes(identity.subject_id),
  );
  const builderPackageInventorySeparated = Boolean(
    identity &&
      builderPackageValidationMutation.data?.data &&
      ![
        builderPackageValidationMutation.data.data.validated_by,
        builderPackageAcquisitionMutation.data?.data.acquired_by,
        builderCandidateHandoffMutation.data?.data.custodied_by,
        builderCandidateHandoffMutation.data?.data.domain_reviewed_by,
        builderCandidateHandoffMutation.data?.data.security_reviewed_by,
        builderCandidateHandoffMutation.data?.data.lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderContentPolicyScanSeparated = Boolean(
    identity &&
      builderPackageInventoryMutation.data?.data &&
      ![
        builderPackageInventoryMutation.data.data.inventoried_by,
        builderPackageInventoryMutation.data.data.source_validated_by,
        builderPackageInventoryMutation.data.data.source_acquired_by,
        builderPackageInventoryMutation.data.data.source_custodied_by,
        builderPackageInventoryMutation.data.data.source_domain_reviewed_by,
        builderPackageInventoryMutation.data.data.source_security_reviewed_by,
        builderPackageInventoryMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderSchemaSemanticsSeparated = Boolean(
    identity &&
      builderContentPolicyScanMutation.data?.data &&
      ![
        builderContentPolicyScanMutation.data.data.scanned_by,
        builderContentPolicyScanMutation.data.data.source_inventoried_by,
        builderContentPolicyScanMutation.data.data.source_validated_by,
        builderContentPolicyScanMutation.data.data.source_acquired_by,
        builderContentPolicyScanMutation.data.data.source_custodied_by,
        builderContentPolicyScanMutation.data.data.source_domain_reviewed_by,
        builderContentPolicyScanMutation.data.data.source_security_reviewed_by,
        builderContentPolicyScanMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderAuthorityBehaviorSeparated = Boolean(
    identity &&
      builderSchemaSemanticsMutation.data?.data &&
      ![
        builderSchemaSemanticsMutation.data.data.validated_by,
        builderSchemaSemanticsMutation.data.data.source_content_scanned_by,
        builderSchemaSemanticsMutation.data.data.source_inventoried_by,
        builderSchemaSemanticsMutation.data.data.source_manifest_validated_by,
        builderSchemaSemanticsMutation.data.data.source_acquired_by,
        builderSchemaSemanticsMutation.data.data.source_custodied_by,
        builderSchemaSemanticsMutation.data.data.source_domain_reviewed_by,
        builderSchemaSemanticsMutation.data.data.source_security_reviewed_by,
        builderSchemaSemanticsMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderStaticDependencySeparated = Boolean(
    identity &&
      builderAuthorityBehaviorMutation.data?.data &&
      ![
        builderAuthorityBehaviorMutation.data.data.validated_by,
        builderAuthorityBehaviorMutation.data.data.source_schema_validated_by,
        builderAuthorityBehaviorMutation.data.data.source_content_scanned_by,
        builderAuthorityBehaviorMutation.data.data.source_inventoried_by,
        builderAuthorityBehaviorMutation.data.data.source_manifest_validated_by,
        builderAuthorityBehaviorMutation.data.data.source_acquired_by,
        builderAuthorityBehaviorMutation.data.data.source_custodied_by,
        builderAuthorityBehaviorMutation.data.data.source_domain_reviewed_by,
        builderAuthorityBehaviorMutation.data.data.source_security_reviewed_by,
        builderAuthorityBehaviorMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderVulnerabilitySeparated = Boolean(
    identity &&
      builderStaticDependencyMutation.data?.data &&
      ![
        builderStaticDependencyMutation.data.data.analyzed_by,
        builderStaticDependencyMutation.data.data.source_authority_validated_by,
        builderStaticDependencyMutation.data.data.source_schema_validated_by,
        builderStaticDependencyMutation.data.data.source_content_scanned_by,
        builderStaticDependencyMutation.data.data.source_inventoried_by,
        builderStaticDependencyMutation.data.data.source_manifest_validated_by,
        builderStaticDependencyMutation.data.data.source_acquired_by,
        builderStaticDependencyMutation.data.data.source_custodied_by,
        builderStaticDependencyMutation.data.data.source_domain_reviewed_by,
        builderStaticDependencyMutation.data.data.source_security_reviewed_by,
        builderStaticDependencyMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderMalwareSeparated = Boolean(
    identity &&
      builderVulnerabilityMutation.data?.data &&
      ![
        builderVulnerabilityMutation.data.data.analyzed_by,
        builderVulnerabilityMutation.data.data.source_static_analyzed_by,
        builderVulnerabilityMutation.data.data.source_authority_validated_by,
        builderVulnerabilityMutation.data.data.source_schema_validated_by,
        builderVulnerabilityMutation.data.data.source_content_scanned_by,
        builderVulnerabilityMutation.data.data.source_inventoried_by,
        builderVulnerabilityMutation.data.data.source_manifest_validated_by,
        builderVulnerabilityMutation.data.data.source_acquired_by,
        builderVulnerabilityMutation.data.data.source_custodied_by,
        builderVulnerabilityMutation.data.data.source_domain_reviewed_by,
        builderVulnerabilityMutation.data.data.source_security_reviewed_by,
        builderVulnerabilityMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderLicenseSeparated = Boolean(
    identity &&
      builderMalwareMutation.data?.data &&
      ![
        builderMalwareMutation.data.data.analyzed_by,
        builderMalwareMutation.data.data.source_vulnerability_analyzed_by,
        builderMalwareMutation.data.data.source_static_analyzed_by,
        builderMalwareMutation.data.data.source_authority_validated_by,
        builderMalwareMutation.data.data.source_schema_validated_by,
        builderMalwareMutation.data.data.source_content_scanned_by,
        builderMalwareMutation.data.data.source_inventoried_by,
        builderMalwareMutation.data.data.source_manifest_validated_by,
        builderMalwareMutation.data.data.source_acquired_by,
        builderMalwareMutation.data.data.source_custodied_by,
        builderMalwareMutation.data.data.source_domain_reviewed_by,
        builderMalwareMutation.data.data.source_security_reviewed_by,
        builderMalwareMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderContractSeparated = Boolean(
    identity &&
      builderLicenseMutation.data?.data &&
      ![
        builderLicenseMutation.data.data.analyzed_by,
        builderLicenseMutation.data.data.source_malware_analyzed_by,
        builderLicenseMutation.data.data.source_vulnerability_analyzed_by,
        builderLicenseMutation.data.data.source_static_analyzed_by,
        builderLicenseMutation.data.data.source_authority_validated_by,
        builderLicenseMutation.data.data.source_schema_validated_by,
        builderLicenseMutation.data.data.source_content_scanned_by,
        builderLicenseMutation.data.data.source_inventoried_by,
        builderLicenseMutation.data.data.source_manifest_validated_by,
        builderLicenseMutation.data.data.source_acquired_by,
        builderLicenseMutation.data.data.source_custodied_by,
        builderLicenseMutation.data.data.source_domain_reviewed_by,
        builderLicenseMutation.data.data.source_security_reviewed_by,
        builderLicenseMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderRunnerSeparated = Boolean(
    identity &&
      builderContractMutation.data?.data &&
      ![
        builderContractMutation.data.data.validated_by,
        builderContractMutation.data.data.source_license_analyzed_by,
        builderContractMutation.data.data.source_malware_analyzed_by,
        builderContractMutation.data.data.source_vulnerability_analyzed_by,
        builderContractMutation.data.data.source_static_analyzed_by,
        builderContractMutation.data.data.source_authority_validated_by,
        builderContractMutation.data.data.source_schema_validated_by,
        builderContractMutation.data.data.source_content_scanned_by,
        builderContractMutation.data.data.source_inventoried_by,
        builderContractMutation.data.data.source_manifest_validated_by,
        builderContractMutation.data.data.source_acquired_by,
        builderContractMutation.data.data.source_custodied_by,
        builderContractMutation.data.data.source_domain_reviewed_by,
        builderContractMutation.data.data.source_security_reviewed_by,
        builderContractMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderLabSelfTestSeparated = Boolean(
    identity &&
      builderRunnerMutation.data?.data &&
      builderContractMutation.data?.data &&
      ![
        builderRunnerMutation.data.data.validated_by,
        builderContractMutation.data.data.validated_by,
        builderContractMutation.data.data.source_license_analyzed_by,
        builderContractMutation.data.data.source_malware_analyzed_by,
        builderContractMutation.data.data.source_vulnerability_analyzed_by,
        builderContractMutation.data.data.source_static_analyzed_by,
        builderContractMutation.data.data.source_authority_validated_by,
        builderContractMutation.data.data.source_schema_validated_by,
        builderContractMutation.data.data.source_content_scanned_by,
        builderContractMutation.data.data.source_inventoried_by,
        builderContractMutation.data.data.source_manifest_validated_by,
        builderContractMutation.data.data.source_acquired_by,
        builderContractMutation.data.data.source_custodied_by,
        builderContractMutation.data.data.source_domain_reviewed_by,
        builderContractMutation.data.data.source_security_reviewed_by,
        builderContractMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderFinalValidationSeparated = Boolean(
    identity &&
      builderLabSelfTestMutation.data?.data &&
      builderContractMutation.data?.data &&
      ![
        builderLabSelfTestMutation.data.data.validated_by,
        builderLabSelfTestMutation.data.data.source_runner_validated_by,
        builderLabSelfTestMutation.data.data.lab_plan_approved_by,
        builderLabSelfTestMutation.data.data.credential_custodied_by,
        builderContractMutation.data.data.validated_by,
        builderContractMutation.data.data.source_license_analyzed_by,
        builderContractMutation.data.data.source_malware_analyzed_by,
        builderContractMutation.data.data.source_vulnerability_analyzed_by,
        builderContractMutation.data.data.source_static_analyzed_by,
        builderContractMutation.data.data.source_authority_validated_by,
        builderContractMutation.data.data.source_schema_validated_by,
        builderContractMutation.data.data.source_content_scanned_by,
        builderContractMutation.data.data.source_inventoried_by,
        builderContractMutation.data.data.source_manifest_validated_by,
        builderContractMutation.data.data.source_acquired_by,
        builderContractMutation.data.data.source_custodied_by,
        builderContractMutation.data.data.source_domain_reviewed_by,
        builderContractMutation.data.data.source_security_reviewed_by,
        builderContractMutation.data.data.source_lab_operated_by,
      ].includes(identity.subject_id),
  );
  const builderLabValidationMutation = useMutation({
    mutationFn: createMcpBuilderLabValidation,
    onSuccess: () => {
      resetBuilderCandidateHandoff();
      setBuilderLabValidationAcknowledged(false);
    },
  });
  const builderSecurityReviewMutation = useMutation({
    mutationFn: createMcpBuilderSecurityReview,
    onSuccess: () => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
    },
  });
  const builderDomainReviewMutation = useMutation({
    mutationFn: createMcpBuilderDomainReview,
    onSuccess: (result) => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      builderSecurityReviewMutation.reset();
      setBuilderDomainReviewAcknowledged(false);
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
      const evidenceReference =
        result.data.capability_decisions[0]?.evidence_citations[0] ?? "";
      setBuilderSecurityAssessments(
        MCP_BUILDER_SECURITY_CONTROLS.reduce<
          Partial<Record<McpBuilderSecurityControl, McpBuilderSecurityAssessment>>
        >((current, control) => {
          current[control.id] = {
              control: control.id,
              decision: "accepted" as const,
              assessment: `Independent review confirms the bounded ${control.label.toLowerCase()} posture.`,
              evidenceReferences: [evidenceReference],
              findingCodes: [],
              requiredControls: [
                `Preserve the declared ${control.label.toLowerCase()} boundary through later lifecycle gates.`,
              ],
          };
          return current;
        }, {}),
      );
    },
  });
  const builderValidationMutation = useMutation({
    mutationFn: createMcpBuilderValidation,
    onSuccess: () => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      builderSecurityReviewMutation.reset();
      builderDomainReviewMutation.reset();
      setBuilderValidationAcknowledged(false);
      setBuilderDomainReviewAcknowledged(false);
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
      setBuilderSecurityAssessments({});
    },
  });
  const builderGenerationMutation = useMutation({
    mutationFn: createMcpBuilderGeneration,
    onSuccess: (result) => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      builderValidationMutation.reset();
      builderSecurityReviewMutation.reset();
      builderDomainReviewMutation.reset();
      setBuilderGenerationAcknowledged(false);
      setBuilderValidationAcknowledged(false);
      setBuilderDomainReviewAcknowledged(false);
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
      setBuilderSecurityAssessments({});
      setBuilderDomainDecisions({});
      const firstFile =
        result.data.files.find((item) => item.relative_path === "README.md") ??
        result.data.files[0];
      if (firstFile) {
        setBuilderSelectedGeneratedFile(firstFile.relative_path);
        builderGeneratedFileMutation.mutate({
          projectId: result.data.project_id,
          relativePath: firstFile.relative_path,
        });
      }
    },
  });
  const builderDesignMutation = useMutation({
    mutationFn: createMcpBuilderDesignCheckpoint,
    onSuccess: () => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      builderGenerationMutation.reset();
      builderGeneratedFileMutation.reset();
      builderValidationMutation.reset();
      builderSecurityReviewMutation.reset();
      builderDomainReviewMutation.reset();
      setBuilderGenerationAcknowledged(false);
      setBuilderValidationAcknowledged(false);
      setBuilderDomainReviewAcknowledged(false);
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
      setBuilderSecurityAssessments({});
      setBuilderDomainDecisions({});
      setBuilderSelectedGeneratedFile("");
    },
  });
  const builderMutation = useMutation({
    mutationFn: createMcpBuilderProject,
    onSuccess: (result) => {
      builderLabValidationMutation.reset();
      resetBuilderCandidateHandoff();
      builderDesignMutation.reset();
      builderGenerationMutation.reset();
      builderGeneratedFileMutation.reset();
      builderValidationMutation.reset();
      builderSecurityReviewMutation.reset();
      builderDomainReviewMutation.reset();
      setBuilderDesignAcknowledged(false);
      setBuilderGenerationAcknowledged(false);
      setBuilderValidationAcknowledged(false);
      setBuilderDomainReviewAcknowledged(false);
      setBuilderSecurityReviewAcknowledged(false);
      setBuilderLabValidationAcknowledged(false);
      setBuilderSecurityAssessments({});
      setBuilderDomainDecisions({});
      setBuilderSelectedGeneratedFile("");
      setBuilderDesignDecisions(
        Object.fromEntries(
          result.data.capability_candidates.map((candidate) => [
            candidate.candidate_id,
            {
              candidateId: candidate.candidate_id,
              decision: candidate.generation_blocked ? "exclude" : "include",
              analyzedClass: candidate.proposed_capability_class,
              requiredPermission: candidate.generation_blocked
                ? "permission.not-applicable"
                : "storage.system.read",
              rationale: candidate.generation_blocked
                ? "Excluded because analyzed evidence remains blocked or ambiguous."
                : "Included as an authenticated, bounded read-only operation.",
            },
          ]),
        ),
      );
    },
  });
  const updateBuilderDomainDecision = (
    candidateId: string,
    update: Partial<McpBuilderDomainDecision>,
  ) => {
    setBuilderDomainDecisions((current) => {
      const existing = current[candidateId];
      if (!existing) return current;
      return { ...current, [candidateId]: { ...existing, ...update } };
    });
  };
  const updateBuilderSecurityAssessment = (
    control: McpBuilderSecurityControl,
    update: Partial<McpBuilderSecurityAssessment>,
  ) => {
    setBuilderSecurityAssessments((current) => {
      const existing = current[control];
      if (!existing) return current;
      return { ...current, [control]: { ...existing, ...update } };
    });
  };
  const humanReviewInboxQuery = useQuery({
    queryKey: ["upgrade-human-review-inbox", identity?.subject_id],
    queryFn: () => getUpgradeHumanReviewInbox(),
    enabled: Boolean(identity),
    retry: false,
  });
  const humanReviewInbox = humanReviewInboxQuery.data?.data;
  const selectedInboxReview = humanReviewInbox?.items.find(
    (item) => item.review_id === selectedInboxReviewId,
  );
  const selectedInboxStage = selectedInboxReview?.stages.find(
    (stage) => stage.state === "pending",
  );
  const reviewDecisionMutation = useMutation({
    mutationFn: decideUpgradeHumanReview,
    onSuccess: async (result) => {
      setReviewDecisionResult(result.data);
      setCompletionReceiptAcknowledged(false);
      setCompletionReceipt(null);
      setSelectedInboxReviewId(null);
      setReviewDecisionOutcome("approve");
      setReviewDecisionRationale("");
      setReviewDecisionAcknowledged(false);
      await queryClient.invalidateQueries({ queryKey: ["upgrade-human-review-inbox"] });
    },
  });
  const completionReceiptMutation = useMutation({
    mutationFn: createUpgradeHumanReviewCompletionReceipt,
    onSuccess: (result) => {
      setCompletionReceipt(result.data);
      setCompletionReceiptAcknowledged(false);
    },
  });
  const loginMutation = useMutation({
    mutationFn: () => createBrowserSession(username, password),
    onSuccess: async () => {
      setEnterpriseLoginRequested(false);
      await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
    },
    onSettled: () => setPassword(""),
  });
  const logoutMutation = useMutation({
    mutationFn: logoutBrowserSession,
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["storage-overview"] });
      queryClient.removeQueries({ queryKey: ["storage-impact"] });
      queryClient.removeQueries({ queryKey: ["health-check-overview"] });
      queryClient.removeQueries({ queryKey: ["security-export-overview"] });
      queryClient.removeQueries({ queryKey: ["approval-request"] });
      queryClient.removeQueries({ queryKey: ["technical-report"] });
      queryClient.removeQueries({ queryKey: ["api-credentials"] });
      queryClient.removeQueries({ queryKey: ["identity-governance"] });
      queryClient.removeQueries({ queryKey: ["workload-identities"] });
      queryClient.removeQueries({ queryKey: ["audit-export-overview"] });
      queryClient.removeQueries({ queryKey: ["upgrade-human-review-inbox"] });
      queryClient.removeQueries({ queryKey: ["inventory-devices"] });
      queryClient.removeQueries({ queryKey: ["connector-package-installations"] });
      queryClient.removeQueries({ queryKey: ["connector-instance-creation-policies"] });
      queryClient.removeQueries({ queryKey: ["connector-instances"] });
      setApprovalRequestId(null);
      setTechnicalReportId(null);
      const url = new URL(window.location.href);
      url.searchParams.delete("approval_request_id");
      url.searchParams.delete("report_id");
      window.history.replaceState({}, "", url);
      setApprovalRationale("");
      setIssuedApiToken(null);
      setPendingDisableSubjectId(null);
      setSelectedInboxReviewId(null);
      setReviewDecisionOutcome("approve");
      setReviewDecisionRationale("");
      setReviewDecisionAcknowledged(false);
      setReviewDecisionResult(null);
      setCompletionReceiptAcknowledged(false);
      setCompletionReceipt(null);
      setGovernanceReason("");
      setWorkloadReason("");
      setIssuedWorkloadToken(null);
      setPendingWorkloadAction(null);
      setBootstrapRebaseJustification("");
      setBootstrapRebasePending(false);
      setBootstrapRebaseResult(null);
      setIntegrationValidationJustification("");
      setIntegrationValidationPending(false);
      setIntegrationValidationResult(null);
      setVerificationJustification("");
      setVerificationPending(false);
      setVerificationResult(null);
      setHandoffJustification("");
      setHandoffPending(false);
      setHandoffResult(null);
      setSupportComponentIds([...SUPPORT_BUNDLE_COMPONENTS]);
      setSupportLookbackHours(24);
      setSupportJustification("");
      setSupportPending(false);
      setSupportResult(null);
      setBackupComponentIds([...LOGICAL_BACKUP_COMPONENTS]);
      setBackupJustification("");
      setBackupPending(false);
      setBackupResult(null);
      setRestoreValidation(null);
      setUpgradeJustification("");
      setUpgradePending(false);
      setUpgradeSimulation(null);
      await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
    },
  });
  const sessionsQuery = useQuery({
    queryKey: ["browser-sessions"],
    queryFn: getBrowserSessions,
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const sessionInventory = sessionsQuery.data?.data;
  const sessions = sessionInventory?.sessions;
  const revokeSessionMutation = useMutation({
    mutationFn: revokeBrowserSession,
    onSuccess: async (_, sessionId) => {
      const revokedCurrent = sessions?.some(
        (session) => session.session_id === sessionId && session.current,
      );
      if (revokedCurrent) {
        queryClient.removeQueries({ queryKey: ["browser-sessions"] });
        await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["browser-sessions"] });
      }
    },
  });
  const apiCredentialsQuery = useQuery({
    queryKey: ["api-credentials"],
    queryFn: getApiCredentials,
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const apiCredentialInventory = apiCredentialsQuery.data?.data;
  const apiCredentials = apiCredentialInventory?.credentials;
  const availableApiGrants = apiCredentialInventory?.available_grants ?? [];
  const createApiCredentialMutation = useMutation({
    mutationFn: () =>
      createApiCredential({
        displayName: apiCredentialName,
        purpose: apiCredentialPurpose,
        expiresInMinutes: apiCredentialLifetime,
        permissionIds: selectedApiGrants,
      }),
    onSuccess: async (result) => {
      setIssuedApiToken(result.data.token);
      setApiCredentialName("");
      setApiCredentialPurpose("");
      await queryClient.invalidateQueries({ queryKey: ["api-credentials"] });
    },
  });
  const revokeApiCredentialMutation = useMutation({
    mutationFn: revokeApiCredential,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["api-credentials"] });
    },
  });
  const identityGovernanceQuery = useQuery({
    queryKey: ["identity-governance", governanceSearch],
    queryFn: () => getIdentityGovernance(governanceSearch),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const identityGovernance = identityGovernanceQuery.data?.data;
  const revokeGovernedSessionMutation = useMutation({
    mutationFn: revokeGovernedSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const disableGovernedIdentityMutation = useMutation({
    mutationFn: disableGovernedIdentity,
    onSuccess: async () => {
      setPendingDisableSubjectId(null);
      setGovernanceReason("");
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const revokeGovernedApiCredentialMutation = useMutation({
    mutationFn: revokeGovernedApiCredential,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const workloadIdentityQuery = useQuery({
    queryKey: ["workload-identities", workloadSearch],
    queryFn: () => getWorkloadIdentities(workloadSearch),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const workloadInventory = workloadIdentityQuery.data?.data;
  const createWorkloadIdentityMutation = useMutation({
    mutationFn: createWorkloadIdentity,
    onSuccess: async (result) => {
      setIssuedWorkloadToken(result.data.token);
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const rotateWorkloadCredentialMutation = useMutation({
    mutationFn: rotateWorkloadCredential,
    onSuccess: async (result) => {
      setIssuedWorkloadToken(result.data.token);
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const revokeWorkloadCredentialMutation = useMutation({
    mutationFn: revokeWorkloadCredential,
    onSuccess: async () => {
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const auditExportQuery = useQuery({
    queryKey: ["audit-export-overview", auditSearch, auditOutcome],
    queryFn: () => getAuditExportOverview(auditSearch, auditOutcome),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const auditExport = auditExportQuery.data?.data;
  const auditHealth = auditExport?.health?.[0];
  const releasePreflightQuery = useQuery({
    queryKey: ["release-preflight", releaseMode, releaseProfile],
    queryFn: () => getReleasePreflight(releaseMode, releaseProfile),
    enabled: Boolean(identity),
    retry: false,
  });
  const releasePreflight = releasePreflightQuery.data?.data;
  const deploymentConfigurationQuery = useQuery({
    queryKey: ["deployment-configuration-preview", releaseProfile, identity?.scope],
    queryFn: () => previewDeploymentConfiguration(releaseProfile, identity!.scope),
    enabled: Boolean(identity),
    retry: false,
  });
  const deploymentConfiguration = deploymentConfigurationQuery.data?.data;
  const bootstrapTrustPlanQuery = useQuery({
    queryKey: [
      "bootstrap-trust-plan",
      deploymentConfiguration?.configuration_digest,
      identity?.scope,
    ],
    queryFn: () => previewBootstrapTrustPlan(deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && deploymentConfiguration),
    retry: false,
  });
  const bootstrapTrustPlan = bootstrapTrustPlanQuery.data?.data;
  const bootstrapDataPlanQuery = useQuery({
    queryKey: [
      "bootstrap-data-plan",
      deploymentConfiguration?.configuration_digest,
      bootstrapTrustPlan?.trust_plan_digest,
      identity?.scope,
    ],
    queryFn: () =>
      previewBootstrapDataPlan(
        deploymentConfiguration!,
        bootstrapTrustPlan!,
        identity!.scope,
      ),
    enabled: Boolean(identity && deploymentConfiguration && bootstrapTrustPlan),
    retry: false,
  });
  const bootstrapDataPlan = bootstrapDataPlanQuery.data?.data;
  const bootstrapServicePlanQuery = useQuery({
    queryKey: [
      "bootstrap-service-plan",
      deploymentConfiguration?.configuration_digest,
      bootstrapTrustPlan?.trust_plan_digest,
      bootstrapDataPlan?.data_plan_digest,
      identity?.scope,
    ],
    queryFn: () =>
      previewBootstrapServicePlan(
        deploymentConfiguration!,
        bootstrapTrustPlan!,
        bootstrapDataPlan!,
        identity!.scope,
      ),
    enabled: Boolean(
      identity && deploymentConfiguration && bootstrapTrustPlan && bootstrapDataPlan,
    ),
    retry: false,
  });
  const bootstrapServicePlan = bootstrapServicePlanQuery.data?.data;
  const bootstrapIdentityPlanQuery = useQuery({
    queryKey: [
      "bootstrap-identity-plan",
      deploymentConfiguration?.configuration_digest,
      bootstrapTrustPlan?.trust_plan_digest,
      bootstrapDataPlan?.data_plan_digest,
      bootstrapServicePlan?.service_plan_digest,
      identity?.scope,
    ],
    queryFn: () =>
      previewBootstrapIdentityPlan(
        deploymentConfiguration!,
        bootstrapTrustPlan!,
        bootstrapDataPlan!,
        bootstrapServicePlan!,
        identity!.scope,
      ),
    enabled: Boolean(
      identity &&
        deploymentConfiguration &&
        bootstrapTrustPlan &&
        bootstrapDataPlan &&
        bootstrapServicePlan,
    ),
    retry: false,
  });
  const bootstrapIdentityPlan = bootstrapIdentityPlanQuery.data?.data;
  const bootstrapIntegrationPlanQuery = useQuery({
    queryKey: [
      "bootstrap-integration-plan",
      deploymentConfiguration?.configuration_digest,
      bootstrapTrustPlan?.trust_plan_digest,
      bootstrapDataPlan?.data_plan_digest,
      bootstrapServicePlan?.service_plan_digest,
      bootstrapIdentityPlan?.identity_plan_digest,
      identity?.scope,
    ],
    queryFn: () =>
      previewBootstrapIntegrationPlan(
        deploymentConfiguration!,
        bootstrapTrustPlan!,
        bootstrapDataPlan!,
        bootstrapServicePlan!,
        bootstrapIdentityPlan!,
        identity!.scope,
      ),
    enabled: Boolean(
      identity &&
        deploymentConfiguration &&
        bootstrapTrustPlan &&
        bootstrapDataPlan &&
        bootstrapServicePlan &&
        bootstrapIdentityPlan,
    ),
    retry: false,
  });
  const bootstrapIntegrationPlan = bootstrapIntegrationPlanQuery.data?.data;
  const bootstrapPlanQuery = useQuery({
    queryKey: [
      "bootstrap-plan",
      releasePreflight?.report_id,
      deploymentConfiguration?.preview_id,
    ],
    queryFn: () => getBootstrapPlan(releasePreflight!, deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && releasePreflight && deploymentConfiguration),
    retry: false,
  });
  const bootstrapPlan = bootstrapPlanQuery.data?.data;
  const bootstrapStateQuery = useQuery({
    queryKey: ["bootstrap-state"],
    queryFn: getBootstrapState,
    enabled: Boolean(identity),
    retry: false,
  });
  const bootstrapState = bootstrapStateQuery.data?.data;
  const bootstrapVerificationPlanQuery = useQuery({
    queryKey: [
      "bootstrap-verification-plan",
      bootstrapState?.run?.run_id,
      bootstrapState?.run?.version,
      bootstrapIntegrationPlan?.integration_plan_digest,
    ],
    queryFn: () =>
      previewBootstrapVerificationPlan({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        trustPlan: bootstrapTrustPlan!,
        dataPlan: bootstrapDataPlan!,
        servicePlan: bootstrapServicePlan!,
        identityPlan: bootstrapIdentityPlan!,
        integrationPlan: bootstrapIntegrationPlan!,
        scope: identity!.scope,
      }),
    enabled: Boolean(
      identity &&
        bootstrapState?.run?.current_phase_id === "phase.verify" &&
        deploymentConfiguration &&
        bootstrapTrustPlan &&
        bootstrapDataPlan &&
        bootstrapServicePlan &&
        bootstrapIdentityPlan &&
        bootstrapIntegrationPlan,
    ),
    retry: false,
  });
  const bootstrapVerificationPlan = bootstrapVerificationPlanQuery.data?.data;
  const bootstrapHandoffPlanQuery = useQuery({
    queryKey: [
      "bootstrap-handoff-plan",
      bootstrapState?.run?.run_id,
      bootstrapState?.run?.version,
      bootstrapState?.run?.end_to_end_verification?.verification_plan_digest,
    ],
    queryFn: () =>
      previewBootstrapHandoffPlan({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        trustPlan: bootstrapTrustPlan!,
        dataPlan: bootstrapDataPlan!,
        servicePlan: bootstrapServicePlan!,
        identityPlan: bootstrapIdentityPlan!,
        integrationPlan: bootstrapIntegrationPlan!,
        scope: identity!.scope,
      }),
    enabled: Boolean(
      identity &&
        bootstrapState?.run?.current_phase_id === "phase.handoff" &&
        bootstrapState.run.end_to_end_verification?.state === "completed" &&
        deploymentConfiguration &&
        bootstrapTrustPlan &&
        bootstrapDataPlan &&
        bootstrapServicePlan &&
        bootstrapIdentityPlan &&
        bootstrapIntegrationPlan,
    ),
    retry: false,
  });
  const bootstrapHandoffPlan = bootstrapHandoffPlanQuery.data?.data;
  const supportBundlePreviewQuery = useQuery({
    queryKey: [
      "support-bundle-preview",
      bootstrapState?.run?.run_id,
      bootstrapState?.run?.version,
      supportComponentIds,
      supportLookbackHours,
    ],
    queryFn: () =>
      previewSupportBundle({
        sourceRunId: bootstrapState!.run!.run_id,
        componentIds: supportComponentIds,
        lookbackHours: supportLookbackHours,
      }),
    enabled: Boolean(
      identity &&
        bootstrapState?.run?.state === "completed" &&
        bootstrapState.run.operational_handoff?.state === "completed" &&
        supportComponentIds.includes("support.release-manifest") &&
        supportComponentIds.includes("support.bootstrap-summary"),
    ),
    retry: false,
  });
  const supportBundlePreview = supportBundlePreviewQuery.data?.data;
  const backupPreviewQuery = useQuery({
    queryKey: [
      "logical-backup-preview",
      bootstrapState?.run?.run_id,
      bootstrapState?.run?.version,
      backupComponentIds,
    ],
    queryFn: () =>
      previewLogicalBackup(bootstrapState!.run!.run_id, backupComponentIds),
    enabled: Boolean(
      identity &&
        bootstrapState?.run?.state === "completed" &&
        bootstrapState.run.operational_handoff?.state === "completed" &&
        [
          "backup.release-state",
          "backup.configuration-state",
          "backup.checkpoint-state",
          "backup.verification-state",
          "backup.operational-handoff",
        ].every((item) => backupComponentIds.includes(item)),
    ),
    retry: false,
  });
  const backupPreview = backupPreviewQuery.data?.data;
  const upgradeReadinessQuery = useQuery({
    queryKey: [
      "upgrade-readiness",
      bootstrapState?.run?.run_id,
      bootstrapState?.run?.version,
      backupResult?.backup_id,
      restoreValidation?.validation_id,
    ],
    queryFn: () =>
      previewUpgradeReadiness({
        sourceRunId: bootstrapState!.run!.run_id,
        backupId: backupResult!.backup_id,
        restoreValidationId: restoreValidation!.validation_id,
      }),
    enabled: Boolean(
      identity &&
        bootstrapState?.run?.state === "completed" &&
        backupResult &&
        restoreValidation,
    ),
    retry: false,
  });
  const upgradeReadiness = upgradeReadinessQuery.data?.data;
  const bootstrapInvalidationQuery = useQuery({
    queryKey: [
      "bootstrap-invalidation",
      bootstrapPlan?.plan_digest,
      deploymentConfiguration?.configuration_digest,
    ],
    queryFn: () =>
      previewBootstrapInvalidation(bootstrapPlan!, deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && bootstrapPlan && deploymentConfiguration),
    retry: false,
  });
  const bootstrapInvalidation = bootstrapInvalidationQuery.data?.data;
  const bootstrapRebaseMutation = useMutation({
    mutationFn: () =>
      rebaseBootstrapPlan({
        state: bootstrapState!,
        preview: bootstrapInvalidation!,
        plan: bootstrapPlan!,
        configuration: deploymentConfiguration!,
        scope: identity!.scope,
        justification: bootstrapRebaseJustification.trim(),
      }),
    onSuccess: async (response) => {
      setBootstrapRebaseResult(response.data);
      setBootstrapRebasePending(false);
      setBootstrapRebaseJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const integrationValidationMutation = useMutation({
    mutationFn: () =>
      validateBootstrapIntegrations({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        trustPlan: bootstrapTrustPlan!,
        dataPlan: bootstrapDataPlan!,
        servicePlan: bootstrapServicePlan!,
        identityPlan: bootstrapIdentityPlan!,
        integrationPlan: bootstrapIntegrationPlan!,
        scope: identity!.scope,
        justification: integrationValidationJustification.trim(),
      }),
    onSuccess: async (response) => {
      setIntegrationValidationResult(response.data);
      setIntegrationValidationPending(false);
      setIntegrationValidationJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-integration-plan"] }),
      ]);
    },
  });
  const verificationMutation = useMutation({
    mutationFn: () =>
      verifyBootstrapEndToEnd({
        state: bootstrapState!,
        plan: bootstrapVerificationPlan!,
        scope: identity!.scope,
        justification: verificationJustification.trim(),
      }),
    onSuccess: async (response) => {
      setVerificationResult(response.data);
      setVerificationPending(false);
      setVerificationJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-verification-plan"] }),
      ]);
    },
  });
  const handoffMutation = useMutation({
    mutationFn: () =>
      completeBootstrapHandoff({
        state: bootstrapState!,
        plan: bootstrapHandoffPlan!,
        scope: identity!.scope,
        justification: handoffJustification.trim(),
      }),
    onSuccess: async (response) => {
      setHandoffResult(response.data);
      setHandoffPending(false);
      setHandoffJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-handoff-plan"] }),
      ]);
    },
  });
  const supportBundleMutation = useMutation({
    mutationFn: () =>
      exportSupportBundle({
        preview: supportBundlePreview!,
        justification: supportJustification.trim(),
      }),
    onSuccess: (response) => {
      setSupportResult(response.data);
      setSupportPending(false);
      setSupportJustification("");
    },
  });
  const backupMutation = useMutation({
    mutationFn: () => createLogicalBackup(backupPreview!, backupJustification.trim()),
    onSuccess: (response) => {
      setBackupResult(response.data);
      setBackupPending(false);
      setBackupJustification("");
      setRestoreValidation(null);
      setUpgradePending(false);
      setUpgradeJustification("");
      setUpgradeSimulation(null);
      setChangeReviewPreview(null);
      setChangeReviewPacket(null);
      setHumanReview(null);
    },
  });
  const restoreValidationMutation = useMutation({
    mutationFn: () => validateLogicalRestore(backupResult!),
    onSuccess: (response) => {
      setRestoreValidation(response.data);
      setUpgradePending(false);
      setUpgradeJustification("");
      setUpgradeSimulation(null);
      setChangeReviewPreview(null);
      setChangeReviewPacket(null);
      setHumanReview(null);
    },
  });
  const upgradeSimulationMutation = useMutation({
    mutationFn: () =>
      simulateUpgradeRollback(upgradeReadiness!, upgradeJustification.trim()),
    onSuccess: (response) => {
      setUpgradeSimulation(response.data);
      setUpgradePending(false);
      setUpgradeJustification("");
      setChangeReviewPreview(null);
      setChangeReviewPacket(null);
      setHumanReview(null);
    },
  });
  const changeReviewPreviewMutation = useMutation({
    mutationFn: () => previewUpgradeChangeReview(upgradeReadiness!, upgradeSimulation!),
    onSuccess: (response) => {
      const now = Date.now();
      setChangeReviewPreview(response.data);
      setChangeReviewWindowStart(localDateTimeInput(new Date(now + 60 * 60_000)));
      setChangeReviewWindowEnd(localDateTimeInput(new Date(now + 2 * 60 * 60_000)));
      setChangeReviewJustification("");
      setChangeReviewAcknowledged(false);
      setChangeReviewPending(true);
    },
  });
  const changeReviewPacketMutation = useMutation({
    mutationFn: () =>
      createUpgradeChangeReviewPacket({
        preview: changeReviewPreview!,
        plan: upgradeReadiness!,
        simulation: upgradeSimulation!,
        justification: changeReviewJustification.trim(),
        proposedWindowStart: changeReviewWindowStart,
        proposedWindowEnd: changeReviewWindowEnd,
      }),
    onSuccess: (response) => {
      setChangeReviewPacket(response.data);
      setChangeReviewPending(false);
      setChangeReviewJustification("");
      setChangeReviewAcknowledged(false);
    },
  });
  const humanReviewMutation = useMutation({
    mutationFn: () =>
      createUpgradeHumanReview(changeReviewPacket!, humanReviewJustification.trim()),
    onSuccess: (response) => {
      setHumanReview(response.data);
      setHumanReviewPending(false);
      setHumanReviewJustification("");
      setHumanReviewAcknowledged(false);
    },
  });
  const integrationExecution =
    integrationValidationResult?.execution ?? bootstrapState?.run?.integration_validation;
  const verificationExecution =
    verificationResult?.execution ?? bootstrapState?.run?.end_to_end_verification;
  const handoffExecution =
    handoffResult?.execution ?? bootstrapState?.run?.operational_handoff;
  const integrationPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.integrations" &&
      bootstrapState.run.integration_validation?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.identity") &&
      bootstrapState.run.identity_handoff?.state === "completed" &&
      bootstrapState.run.identity_handoff.validation_count === 5 &&
      bootstrapState.run.identity_handoff.enterprise_authentication_validated &&
      deploymentConfiguration?.state === "passed" &&
      deploymentConfiguration.configuration_digest === bootstrapState.run.configuration_digest &&
      bootstrapTrustPlan?.state === "passed" &&
      bootstrapDataPlan?.state === "passed" &&
      bootstrapServicePlan?.state === "passed" &&
      bootstrapIdentityPlan?.state === "passed" &&
      bootstrapState.run.identity_handoff.identity_plan_digest ===
        bootstrapIdentityPlan.identity_plan_digest &&
      bootstrapIntegrationPlan?.state === "passed" &&
      bootstrapIntegrationPlan.configuration_digest ===
        bootstrapState.run.configuration_digest &&
      bootstrapIntegrationPlan.identity_plan_digest ===
        bootstrapIdentityPlan.identity_plan_digest,
  );
  const verificationPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.verify" &&
      bootstrapState.run.end_to_end_verification?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.integrations") &&
      bootstrapState.run.integration_validation?.state === "completed" &&
      bootstrapState.run.integration_validation.mandatory_pass_count === 12 &&
      bootstrapState.run.integration_validation.activation_count === 0 &&
      bootstrapState.run.integration_validation.network_request_count === 0 &&
      bootstrapState.run.integration_validation.secret_resolution_count === 0 &&
      bootstrapIntegrationPlan?.state === "passed" &&
      bootstrapState.run.integration_validation.integration_plan_digest ===
        bootstrapIntegrationPlan.integration_plan_digest &&
      bootstrapVerificationPlan?.state === "passed" &&
      bootstrapVerificationPlan.source_run_id === bootstrapState.run.run_id &&
      bootstrapVerificationPlan.source_run_version === bootstrapState.run.version,
  );
  const handoffPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.handoff" &&
      bootstrapState.run.operational_handoff?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.verify") &&
      bootstrapState.run.end_to_end_verification?.state === "completed" &&
      bootstrapState.run.end_to_end_verification.failed_count === 0 &&
      bootstrapState.run.end_to_end_verification.skipped_count === 0 &&
      bootstrapState.run.end_to_end_verification.unresolved_mandatory_count === 0 &&
      bootstrapHandoffPlan?.state === "passed" &&
      bootstrapHandoffPlan.source_run_id === bootstrapState.run.run_id &&
      bootstrapHandoffPlan.source_run_version === bootstrapState.run.version &&
      bootstrapHandoffPlan.readiness_class ===
        "developer_linux_lab_bootstrap_complete" &&
      Object.values(bootstrapHandoffPlan.readiness_claims).every((value) => !value),
  );
  const retryAuditExportMutation = useMutation({
    mutationFn: retryAuditExport,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["audit-export-overview"] });
    },
  });
  const storageQuery = useQuery({
    queryKey: ["storage-overview"],
    queryFn: getStorageOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const platform = statusQuery.data?.data;
  const overview = storageQuery.data?.data;
  const state = statusQuery.isError ? "unavailable" : platform?.status;
  const warningAsset = overview?.assets.find((asset) => asset.health !== "healthy");
  const selectedAsset =
    overview?.assets.find((asset) => asset.asset_id === selectedAssetId) ??
    warningAsset ??
    overview?.assets[0];
  const impactAssetId = selectedAsset?.asset_id;
  const impactQuery = useQuery({
    queryKey: ["storage-impact", impactAssetId],
    queryFn: () => getStorageImpact(impactAssetId ?? ""),
    enabled: Boolean(identity && impactAssetId),
    retry: false,
  });
  const impact = impactQuery.data?.data;
  const healthChecksQuery = useQuery({
    queryKey: ["health-check-overview"],
    queryFn: getHealthCheckOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const healthChecks = healthChecksQuery.data?.data;
  const securityExportQuery = useQuery({
    queryKey: ["security-export-overview"],
    queryFn: getSecurityExportOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const securityExport = securityExportQuery.data?.data;
  const securityExportTestMutation = useMutation({
    mutationFn: sendSecurityExportTestEvent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["security-export-overview"] });
    },
  });
  const selectedHealthCheck =
    healthChecks?.definitions.find((item) => item.definition_id === selectedHealthCheckId) ??
    healthChecks?.definitions[0];
  const selectedHealthSchedule = healthChecks?.schedules.find(
    (item) => item.definition_id === selectedHealthCheck?.definition_id,
  );
  const selectedHealthRun = healthChecks?.latest_runs.find(
    (item) => item.definition_id === selectedHealthCheck?.definition_id,
  );
  const runHealthCheckMutation = useMutation({
    mutationFn: (definitionId: string) => runHealthCheck(definitionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["health-check-overview"] });
    },
  });
  const investigationMutation = useMutation({
    mutationFn: ({ targetId, question }: { targetId: string; question: string }) =>
      createStorageInvestigation(targetId, question),
  });
  const reasoningArtifact = investigationMutation.data?.data;
  const rcaMutation = useMutation({
    mutationFn: ({ targetId, actualBehavior }: { targetId: string; actualBehavior: string }) =>
      createStorageRca(targetId, actualBehavior),
  });
  const rcaCase = rcaMutation.data?.data;
  const recommendationMutation = useMutation({
    mutationFn: ({ targetId, caseId, version }: { targetId: string; caseId: string; version: number }) =>
      createStorageRecommendation(targetId, caseId, version),
  });
  const recommendation = recommendationMutation.data?.data;
  const approvalQuery = useQuery({
    queryKey: ["approval-request", approvalRequestId],
    queryFn: () => getApprovalRequest(approvalRequestId ?? ""),
    enabled: Boolean(identity && approvalRequestId),
    retry: false,
  });
  const approvalCreateMutation = useMutation({
    mutationFn: ({
      targetId,
      recommendationId,
      recommendationVersion,
      optionId,
    }: {
      targetId: string;
      recommendationId: string;
      recommendationVersion: number;
      optionId: string;
    }) => createApprovalRequest(targetId, recommendationId, recommendationVersion, optionId),
    onSuccess: (result) => {
      const requestId = result.data.request_id;
      setApprovalRequestId(requestId);
      const url = new URL(window.location.href);
      url.searchParams.set("approval_request_id", requestId);
      window.history.replaceState({}, "", url);
    },
  });
  const approvalDecisionMutation = useMutation({
    mutationFn: ({
      requestId,
      version,
      outcome,
      rationale,
    }: {
      requestId: string;
      version: number;
      outcome: "approve" | "reject" | "needs_evidence" | "defer";
      rationale: string;
    }) => decideApprovalRequest(requestId, version, outcome, rationale),
    onSuccess: (result) => {
      queryClient.setQueryData(["approval-request", result.data.request_id], result);
      setApprovalRationale("");
    },
  });
  const approval =
    approvalDecisionMutation.data?.data ??
    approvalCreateMutation.data?.data ??
    approvalQuery.data?.data;
  const canReviewApproval = Boolean(
    approval &&
      approval.state === "pending" &&
      identity?.subject_kind === "human" &&
      identity.subject_id !== approval.packet.requested_by &&
      identity.authentication.assurance_level !== "development",
  );
  const reportMutation = useMutation({
    mutationFn: ({
      targetId,
      recommendationId,
      recommendationVersion,
      incidentReference,
    }: {
      targetId: string;
      recommendationId: string;
      recommendationVersion: number;
      incidentReference: string;
    }) =>
      createStorageTechnicalReport(
        targetId,
        recommendationId,
        recommendationVersion,
        incidentReference,
      ),
    onSuccess: (result) => {
      const reportId = result.data.report_id;
      setTechnicalReportId(reportId);
      const url = new URL(window.location.href);
      url.searchParams.set("report_id", reportId);
      window.history.replaceState({}, "", url);
    },
  });
  const technicalReportQuery = useQuery({
    queryKey: ["technical-report", technicalReportId],
    queryFn: () => getTechnicalReport(technicalReportId ?? ""),
    enabled: Boolean(identity && technicalReportId),
    retry: false,
  });
  const technicalReport = reportMutation.data?.data ?? technicalReportQuery.data?.data;
  const clearTechnicalReportSelection = () => {
    reportMutation.reset();
    setTechnicalReportId(null);
    queryClient.removeQueries({ queryKey: ["technical-report"] });
    const url = new URL(window.location.href);
    url.searchParams.delete("report_id");
    window.history.replaceState({}, "", url);
  };
  const canReadItsmHandoffReview = Boolean(technicalReport?.itsm_handoff && identity);
  const hasItsmHandoffReviewDecisionIdentity = Boolean(
    canReadItsmHandoffReview &&
      identity?.credential_kind === "browser_session" &&
      identity.subject_kind === "human" &&
      identity.role_ids.includes("role.itsm-reviewer"),
  );
  const itsmHandoffReviewQuery = useQuery({
    queryKey: [
      "itsm-handoff-review",
      technicalReport?.report_id,
      technicalReport?.itsm_handoff?.draft_id,
    ],
    queryFn: () =>
      getItsmHandoffReview(
        technicalReport?.report_id ?? "",
        technicalReport?.itsm_handoff?.draft_id ?? "",
      ),
    enabled: canReadItsmHandoffReview,
  });
  const itsmHandoffReviewMutation = useMutation({
    mutationFn: ({
      report,
      outcome,
      rationale,
    }: {
      report: NonNullable<typeof technicalReport>;
      outcome: ItsmHandoffReviewOutcome;
      rationale: string;
    }) => decideItsmHandoffReview(report, outcome, rationale),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ["itsm-handoff-review", result.data.report_id, result.data.handoff_draft_id],
        result,
      );
      setItsmReviewRationale("");
      setItsmReviewAcknowledged(false);
    },
  });
  const itsmHandoffReview =
    itsmHandoffReviewMutation.data?.data ?? itsmHandoffReviewQuery.data?.data ?? undefined;
  const canReviewItsmHandoff = Boolean(
    hasItsmHandoffReviewDecisionIdentity &&
      !itsmHandoffReview &&
      identity?.subject_id !== technicalReport?.requested_by,
  );
  const incidentReference = rcaCase?.incident_references.find(
    (reference) => reference.reference_type === "incident",
  )?.reference_id;
  const longestImpactPath = impact
    ? [...impact.paths].sort((left, right) => right.entity_ids.length - left.entity_ids.length)[0]
    : undefined;
  const selectedEvidence =
    overview?.evidence.filter((item) =>
      selectedAsset?.evidence_references.includes(item.reference),
    ) ?? [];
  if (!identityQuery.isLoading && (identityQuery.data === null || enterpriseLoginRequested)) {
    const submitLogin = (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (username && password && !loginMutation.isPending) loginMutation.mutate();
    };
    return (
      <main className="login-shell">
        <section className="login-panel" aria-labelledby="login-title">
          <div className="login-brand">
            <div className="brand-mark" aria-hidden="true">A</div>
            <div><strong>ATLAS</strong><span>Enterprise Operations</span></div>
          </div>
          <div className="login-heading">
            <LockKeyhole size={22} />
            <div><h1 id="login-title">Sign in</h1><p>Enterprise identity</p></div>
          </div>
          <form onSubmit={submitLogin}>
            <label htmlFor="atlas-username">Username</label>
            <input
              id="atlas-username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              maxLength={128}
              required
              autoFocus
            />
            <label htmlFor="atlas-password">Password</label>
            <input
              id="atlas-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              maxLength={1024}
              required
            />
            {loginMutation.isError && (
              <p className="login-error" role="alert">Sign-in was not accepted.</p>
            )}
            <button
              className="login-submit"
              type="submit"
              disabled={!username || !password || loginMutation.isPending}
            >
              <LogIn size={18} />
              {loginMutation.isPending ? "Signing in" : "Sign in"}
            </button>
            {enterpriseLoginRequested && identity?.authentication.method === "development" && (
              <button
                className="login-development-return"
                type="button"
                onClick={() => setEnterpriseLoginRequested(false)}
              >
                Return to read-only development mode
              </button>
            )}
          </form>
        </section>
      </main>
    );
  }

  return (
    <div className="app-frame">
      <ApplicationSidebar
        activeWorkspace={activeNavigation}
        authenticationMethod={identity?.authentication.method}
        displayName={identity?.display_name}
        onClose={() => setSidebarOpen(false)}
        onNavigate={navigateToWorkspace}
        open={sidebarOpen}
        platformState={state}
      />

      <main className="main-area">
        <ApplicationTopbar
          inspectorOpen={inspectorOpen}
          logoutPending={logoutMutation.isPending}
          onLogout={() => logoutMutation.mutate()}
          onOpenNavigation={() => setSidebarOpen(true)}
          onToggleInspector={() => setInspectorOpen((open) => !open)}
          showInspector={activeNavigation === "Health"}
          showLogout={Boolean(identity && identity.authentication.method !== "development")}
        />

        <div
          className={`workspace-grid ${inspectorOpen && activeNavigation === "Health" ? "with-inspector" : ""}`}
        >
          <section className="conversation" aria-label={`${activeNavigation} workspace`}>
            <div className="conversation-heading">
              <div>
                <p className="eyebrow">
                  {activeNavigation === "Connectors" ? "MCP BUILDER" : "STORAGE HEALTH"}
                </p>
                <h1>
                  {activeNavigation === "Connectors"
                    ? "Governed connector analysis"
                    : activeHealthViewDescriptor.title}
                </h1>
                <p>
                  {activeNavigation === "Connectors"
                    ? "Quarantined OpenAPI evidence review for read-only connector candidates."
                    : activeHealthViewDescriptor.description}
                </p>
              </div>
              <span className="decision-badge">
                <ShieldCheck size={15} />
                Human decision required
              </span>
            </div>

            {activeNavigation === "Connectors" && (
            <div className="mcp-builder-workspace">
              <ConnectorWorkspaceNavigation
                activeView={activeConnectorView}
                onNavigate={onNavigateConnectorView}
              />
              <div id="connector-view-inventory" className="connector-view-anchor">
                <WorkspaceLoadBoundary compact resetKey="installed-mcp-management" workspace="Connectors">
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div><h2>Loading installed MCPs</h2><p>Preparing authorized package and instance lifecycle records.</p></div>
                      </div>
                    }
                  >
                    <InstalledMcpManagementWorkspace
                      onRequestEnterpriseLogin={() => setEnterpriseLoginRequested(true)}
                      onOpenBuilder={() => {
                        connectorFocusTarget.current = "builder";
                        onNavigateConnectorView("builder");
                      }}
                      subjectId={identity?.subject_id ?? ""}
                    />
                  </Suspense>
                </WorkspaceLoadBoundary>
              </div>
              <ConnectorLifecycleOverview activeView={activeConnectorView} />
              <section
                className="workspace-section mcp-builder-section connector-view-anchor"
                id="connector-view-builder"
                tabIndex={-1}
              >
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">SOURCE INTAKE</p>
                    <h2>OpenAPI source analysis</h2>
                    <p>OpenAPI 3.0 or 3.1 JSON, reviewed in an isolated laboratory boundary.</p>
                  </div>
                  <span className="state-badge pending">
                    <LockKeyhole size={14} /> No runtime authority
                  </span>
                </div>

                <form
                  className="mcp-builder-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!builderSourceDocument || builderMutation.isPending) return;
                    builderMutation.mutate({
                      vendor: builderVendor.trim(),
                      product: builderProduct.trim(),
                      productVersion: builderProductVersion.trim(),
                      sourceAuthority: builderSourceAuthority.trim(),
                      sourceOwner: builderSourceOwner.trim(),
                      documentationVersion: builderDocumentationVersion.trim(),
                      publicationDate: builderPublicationDate,
                      licenseId: builderLicenseId.trim(),
                      redistributionAllowed: builderRedistributionAllowed,
                      classification: builderClassification,
                      sourceDocument: builderSourceDocument,
                    });
                  }}
                >
                  <div className="mcp-builder-fields">
                    <label>
                      <span>Vendor</span>
                      <input
                        value={builderVendor}
                        onChange={(event) => setBuilderVendor(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Product</span>
                      <input
                        value={builderProduct}
                        onChange={(event) => setBuilderProduct(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Product version</span>
                      <input
                        value={builderProductVersion}
                        onChange={(event) => setBuilderProductVersion(event.target.value)}
                        maxLength={80}
                        required
                      />
                    </label>
                    <label>
                      <span>Documentation version</span>
                      <input
                        value={builderDocumentationVersion}
                        onChange={(event) => setBuilderDocumentationVersion(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Source authority</span>
                      <input
                        value={builderSourceAuthority}
                        onChange={(event) => setBuilderSourceAuthority(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Source owner</span>
                      <input
                        value={builderSourceOwner}
                        onChange={(event) => setBuilderSourceOwner(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Publication date</span>
                      <input
                        type="date"
                        value={builderPublicationDate}
                        onChange={(event) => setBuilderPublicationDate(event.target.value)}
                        required
                      />
                    </label>
                    <label>
                      <span>License identifier</span>
                      <input
                        value={builderLicenseId}
                        onChange={(event) => setBuilderLicenseId(event.target.value)}
                        maxLength={200}
                        required
                      />
                    </label>
                    <label>
                      <span>Classification</span>
                      <select
                        value={builderClassification}
                        onChange={(event) =>
                          setBuilderClassification(
                            event.target.value as McpBuilderProject["classification"],
                          )
                        }
                      >
                        <option value="public">Public</option>
                        <option value="internal">Internal</option>
                        <option value="confidential">Confidential</option>
                        <option value="restricted">Restricted</option>
                      </select>
                    </label>
                  </div>

                  <div className="mcp-builder-source">
                    <label className="mcp-builder-file">
                      <FileText size={20} />
                      <span>
                        <strong>{builderSourceName || "Select OpenAPI JSON"}</strong>
                        <small>Maximum 512 KB. Secrets and duplicate keys are rejected.</small>
                      </span>
                      <input
                        type="file"
                        accept=".json,application/json"
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          setBuilderFileError("");
                          builderMutation.reset();
                          builderDesignMutation.reset();
                          builderGenerationMutation.reset();
                          builderGeneratedFileMutation.reset();
                          builderValidationMutation.reset();
                          builderLabValidationMutation.reset();
                          resetBuilderCandidateHandoff();
                          builderSecurityReviewMutation.reset();
                          builderDomainReviewMutation.reset();
                          setBuilderValidationAcknowledged(false);
                          setBuilderDomainReviewAcknowledged(false);
                          setBuilderSecurityReviewAcknowledged(false);
                          setBuilderLabValidationAcknowledged(false);
                          setBuilderSecurityAssessments({});
                          setBuilderDomainDecisions({});
                          setBuilderDesignDecisions({});
                          setBuilderSelectedGeneratedFile("");
                          if (!file) {
                            setBuilderSourceName("");
                            setBuilderSourceDocument("");
                            return;
                          }
                          if (file.size > 524_288) {
                            setBuilderSourceName(file.name);
                            setBuilderSourceDocument("");
                            setBuilderFileError("The selected source exceeds the 512 KB limit.");
                            return;
                          }
                          setBuilderSourceName(file.name);
                          void file.text().then(setBuilderSourceDocument);
                        }}
                      />
                    </label>
                    <label className="mcp-builder-paste">
                      <span>OpenAPI JSON</span>
                      <textarea
                        aria-label="OpenAPI JSON"
                        value={builderSourceDocument}
                        onChange={(event) => {
                          const value = event.target.value;
                          setBuilderFileError("");
                          setBuilderSourceDocument(value);
                          setBuilderSourceName(value ? "Pasted OpenAPI JSON" : "");
                          builderMutation.reset();
                          builderDesignMutation.reset();
                          builderGenerationMutation.reset();
                          builderGeneratedFileMutation.reset();
                          builderValidationMutation.reset();
                          builderLabValidationMutation.reset();
                          resetBuilderCandidateHandoff();
                          builderSecurityReviewMutation.reset();
                          builderDomainReviewMutation.reset();
                          setBuilderValidationAcknowledged(false);
                          setBuilderDomainReviewAcknowledged(false);
                          setBuilderSecurityReviewAcknowledged(false);
                          setBuilderLabValidationAcknowledged(false);
                          setBuilderSecurityAssessments({});
                          setBuilderDomainDecisions({});
                          setBuilderDesignDecisions({});
                          setBuilderSelectedGeneratedFile("");
                        }}
                        maxLength={524_288}
                        rows={7}
                        placeholder='{"openapi":"3.1.0","info":{},"paths":{}}'
                      />
                    </label>
                    {builderFileError && <p role="alert">{builderFileError}</p>}
                    <label className="mcp-builder-check">
                      <input
                        type="checkbox"
                        checked={builderRedistributionAllowed}
                        onChange={(event) =>
                          setBuilderRedistributionAllowed(event.target.checked)
                        }
                      />
                      <span>Source license permits redistribution inside the organization</span>
                    </label>
                  </div>

                  <div className="mcp-builder-boundary">
                    <ShieldCheck size={18} />
                    <p>
                      Analysis records evidence only. It cannot generate packages, install a
                      connector, contact a vendor endpoint, call a model, or execute code.
                    </p>
                  </div>

                  <button
                    className="run-check-button mcp-builder-submit"
                    type="submit"
                    disabled={
                      !builderVendor.trim() ||
                      !builderProduct.trim() ||
                      !builderProductVersion.trim() ||
                      !builderSourceAuthority.trim() ||
                      !builderSourceOwner.trim() ||
                      !builderDocumentationVersion.trim() ||
                      !builderPublicationDate ||
                      !builderLicenseId.trim() ||
                      !builderSourceDocument ||
                      builderMutation.isPending
                    }
                  >
                    {builderMutation.isPending ? (
                      <RefreshCw className="spin" size={16} />
                    ) : (
                      <FlaskConical size={16} />
                    )}
                    Analyze source
                  </button>
                </form>

                {builderMutation.isError && (
                  <div className="workspace-message error-state" role="alert">
                    <AlertTriangle size={20} />
                    <div>
                      <h3>Source analysis unavailable</h3>
                      <p>The source did not pass the governed intake boundary.</p>
                    </div>
                  </div>
                )}

                {builderMutation.data?.data && (
                  <div className="mcp-builder-results">
                    <div className="mcp-builder-result-heading">
                      <div>
                        <p className="eyebrow">ANALYSIS EVIDENCE</p>
                        <h3>{builderMutation.data.data.api_title}</h3>
                        <code>{builderMutation.data.data.project_id}</code>
                      </div>
                      <span className={`state-badge ${builderMutation.data.data.state}`}>
                        {builderMutation.data.data.state.replaceAll("_", " ")}
                      </span>
                    </div>
                    <div className="mcp-builder-facts">
                      <div><span>OpenAPI</span><strong>{builderMutation.data.data.openapi_version}</strong></div>
                      <div><span>Candidates</span><strong>{builderMutation.data.data.capability_candidates.length}</strong></div>
                      <div><span>Blocked</span><strong>{builderMutation.data.data.capability_candidates.filter((item) => item.generation_blocked).length}</strong></div>
                      <div><span>Findings</span><strong>{builderMutation.data.data.findings.length}</strong></div>
                    </div>
                    <div className="mcp-builder-candidates">
                      {builderMutation.data.data.capability_candidates.map((candidate) => (
                        <article key={candidate.candidate_id}>
                          <span className={`capability-class ${candidate.proposed_capability_class.toLowerCase()}`}>
                            {candidate.proposed_capability_class}
                          </span>
                          <div>
                            <strong>{candidate.operation_id ?? `${candidate.method} ${candidate.path}`}</strong>
                            <p>{candidate.summary}</p>
                            <code>{candidate.method.toUpperCase()} {candidate.path}</code>
                          </div>
                          <span>{candidate.generation_blocked ? "Blocked" : "Read-only candidate"}</span>
                        </article>
                      ))}
                    </div>
                    {builderMutation.data.data.findings.length > 0 && (
                      <div className="mcp-builder-findings">
                        {builderMutation.data.data.findings.map((finding) => (
                          <div key={`${finding.code}:${finding.location}`}>
                            <AlertTriangle size={15} />
                            <span><strong>{finding.code}</strong>{finding.message}</span>
                            <code>{finding.location}</code>
                          </div>
                        ))}
                      </div>
                    )}
                    <section className="mcp-builder-design" aria-label="Human design checkpoint">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">HUMAN DESIGN CHECKPOINT</p>
                          <h3>Confirm connector boundaries</h3>
                          <p>
                            Review every candidate before an isolated generation task can be proposed.
                          </p>
                        </div>
                        <span className="state-badge pending">
                          <UserCheck size={14} /> Human evidence only
                        </span>
                      </div>
                      <form
                        className="mcp-builder-design-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          const project = builderMutation.data?.data;
                          if (!project || builderDesignMutation.isPending) return;
                          const decisions = project.capability_candidates
                            .map(
                              (candidate) =>
                                builderDesignDecisions[candidate.candidate_id],
                            )
                            .filter(
                              (decision): decision is McpBuilderDesignDecision =>
                                decision !== undefined,
                            );
                          if (decisions.length !== project.capability_candidates.length) return;
                          builderDesignMutation.mutate({
                            project,
                            connectorBoundary: builderBoundary.trim(),
                            configurationKeys: [builderConfigurationKey.trim()],
                            secretReferenceIds: [builderSecretReference.trim()],
                            sourceEntity: builderSourceEntity.trim(),
                            atlasEntity: builderAtlasEntity.trim(),
                            decisions,
                          });
                        }}
                      >
                        <div className="mcp-builder-design-fields">
                          <label className="wide-field">
                            <span>Connector boundary</span>
                            <textarea
                              value={builderBoundary}
                              onChange={(event) => setBuilderBoundary(event.target.value)}
                              maxLength={1000}
                              rows={3}
                              required
                            />
                          </label>
                          <label>
                            <span>Configuration key</span>
                            <input
                              value={builderConfigurationKey}
                              onChange={(event) => setBuilderConfigurationKey(event.target.value)}
                              pattern="[a-z][a-z0-9_.:-]{2,127}"
                              required
                            />
                          </label>
                          <label>
                            <span>Secret reference</span>
                            <input
                              value={builderSecretReference}
                              onChange={(event) => setBuilderSecretReference(event.target.value)}
                              pattern="[a-z][a-z0-9_.:-]{2,127}"
                              required
                            />
                          </label>
                          <label>
                            <span>Source entity</span>
                            <input
                              value={builderSourceEntity}
                              onChange={(event) => setBuilderSourceEntity(event.target.value)}
                              pattern="[a-z][a-z0-9_.:-]{2,127}"
                              required
                            />
                          </label>
                          <label>
                            <span>Atlas entity</span>
                            <input
                              value={builderAtlasEntity}
                              onChange={(event) => setBuilderAtlasEntity(event.target.value)}
                              pattern="[a-z][a-z0-9_.:-]{2,127}"
                              required
                            />
                          </label>
                        </div>
                        <div className="mcp-builder-destinations">
                          <span>Declared network destinations</span>
                          {builderMutation.data.data.declared_servers.length > 0 ? (
                            builderMutation.data.data.declared_servers.map((destination) => (
                              <code key={destination}>{destination}</code>
                            ))
                          ) : (
                            <strong>No destination evidence</strong>
                          )}
                        </div>
                        <div className="mcp-builder-decision-list">
                          {builderMutation.data.data.capability_candidates.map((candidate) => {
                            const decision = builderDesignDecisions[candidate.candidate_id];
                            if (!decision) return null;
                            return (
                              <fieldset key={candidate.candidate_id}>
                                <legend>
                                  <span
                                    className={`capability-class ${candidate.proposed_capability_class.toLowerCase()}`}
                                  >
                                    {candidate.proposed_capability_class}
                                  </span>
                                  {candidate.operation_id ?? `${candidate.method} ${candidate.path}`}
                                </legend>
                                <label>
                                  <span>Decision</span>
                                  <select
                                    value={decision.decision}
                                    disabled={candidate.generation_blocked}
                                    onChange={(event) =>
                                      setBuilderDesignDecisions((current) => ({
                                        ...current,
                                        [candidate.candidate_id]: {
                                          ...decision,
                                          decision: event.target.value as "include" | "exclude",
                                        },
                                      }))
                                    }
                                  >
                                    <option value="include">Include</option>
                                    <option value="exclude">Exclude</option>
                                  </select>
                                </label>
                                <label>
                                  <span>Minimum vendor permission</span>
                                  <input
                                    value={decision.requiredPermission}
                                    onChange={(event) =>
                                      setBuilderDesignDecisions((current) => ({
                                        ...current,
                                        [candidate.candidate_id]: {
                                          ...decision,
                                          requiredPermission: event.target.value,
                                        },
                                      }))
                                    }
                                    maxLength={160}
                                    required
                                  />
                                </label>
                                <label className="wide-field">
                                  <span>Rationale</span>
                                  <textarea
                                    value={decision.rationale}
                                    onChange={(event) =>
                                      setBuilderDesignDecisions((current) => ({
                                        ...current,
                                        [candidate.candidate_id]: {
                                          ...decision,
                                          rationale: event.target.value,
                                        },
                                      }))
                                    }
                                    maxLength={1000}
                                    rows={2}
                                    required
                                  />
                                </label>
                              </fieldset>
                            );
                          })}
                        </div>
                        <label className="mcp-builder-check">
                          <input
                            type="checkbox"
                            checked={builderDesignAcknowledged}
                            onChange={(event) =>
                              setBuilderDesignAcknowledged(event.target.checked)
                            }
                          />
                          <span>
                            I confirm this checkpoint records design evidence only and grants no
                            generation, runtime, credential, or execution authority.
                          </span>
                        </label>
                        <button
                          className="run-check-button mcp-builder-submit"
                          type="submit"
                          disabled={
                            !builderDesignAcknowledged ||
                            !builderBoundary.trim() ||
                            !builderConfigurationKey.trim() ||
                            !builderSecretReference.trim() ||
                            !builderSourceEntity.trim() ||
                            !builderAtlasEntity.trim() ||
                            !Object.values(builderDesignDecisions).some(
                              (decision) => decision.decision === "include",
                            ) ||
                            Object.values(builderDesignDecisions).some(
                              (decision) =>
                                !decision.requiredPermission.trim() || !decision.rationale.trim(),
                            ) ||
                            Boolean(builderDesignMutation.data) ||
                            builderDesignMutation.isPending
                          }
                        >
                          {builderDesignMutation.isPending ? (
                            <RefreshCw className="spin" size={16} />
                          ) : (
                            <FileCheck2 size={16} />
                          )}
                          Confirm design checkpoint
                        </button>
                      </form>
                      {builderDesignMutation.isError && (
                        <div className="workspace-message error-state" role="alert">
                          <AlertTriangle size={20} />
                          <div>
                            <h3>Design checkpoint unavailable</h3>
                            <p>The human design evidence did not pass the governed boundary.</p>
                          </div>
                        </div>
                      )}
                      {builderDesignMutation.data?.data && (
                        <div className="mcp-builder-design-result">
                          <CheckCircle2 size={20} />
                          <div>
                            <strong>Design checkpoint recorded</strong>
                            <code>{builderDesignMutation.data.data.checkpoint_id}</code>
                            <p>
                              {
                                builderDesignMutation.data.data.capability_decisions.filter(
                                  (decision) => decision.generation_eligible,
                                ).length
                              }{" "}
                              capability candidates are design-eligible. No artifacts were generated.
                            </p>
                          </div>
                        </div>
                      )}
                      {builderDesignMutation.data?.data && (
                        <section
                          className="mcp-builder-generation"
                          aria-label="Quarantined scaffold generation"
                        >
                          <div className="section-heading">
                            <div>
                              <p className="eyebrow">ISOLATED GENERATION</p>
                              <h3>Create a Python review scaffold</h3>
                              <p>
                                Produce deterministic source, schemas, tests, and traceability inside
                                the Atlas quarantine.
                              </p>
                            </div>
                            <span className="state-badge pending">
                              <LockKeyhole size={14} /> No runtime trust
                            </span>
                          </div>
                          {!builderGenerationMutation.data && (
                            <form
                              className="mcp-builder-generation-form"
                              onSubmit={(event) => {
                                event.preventDefault();
                                const project = builderMutation.data?.data;
                                const checkpoint = builderDesignMutation.data?.data;
                                if (
                                  !project ||
                                  !checkpoint ||
                                  !builderGenerationAcknowledged ||
                                  builderGenerationMutation.isPending
                                ) {
                                  return;
                                }
                                builderGenerationMutation.mutate({ project, checkpoint });
                              }}
                            >
                              <div className="mcp-builder-generation-contract">
                                <div>
                                  <span>Language profile</span>
                                  <code>atlas.python312.v1</code>
                                </div>
                                <div>
                                  <span>Template</span>
                                  <code>mcp-builder-python.v1</code>
                                </div>
                                <div>
                                  <span>Eligible capabilities</span>
                                  <strong>
                                    {
                                      builderDesignMutation.data.data.capability_decisions.filter(
                                        (decision) => decision.generation_eligible,
                                      ).length
                                    }
                                  </strong>
                                </div>
                              </div>
                              <div className="mcp-builder-boundary">
                                <ShieldCheck size={18} />
                                <p>
                                  Generation writes review files only. It does not call a model or
                                  network, run tests or code, create a package, or register, install,
                                  enable, or invoke a connector.
                                </p>
                              </div>
                              <label className="mcp-builder-check">
                                <input
                                  type="checkbox"
                                  checked={builderGenerationAcknowledged}
                                  onChange={(event) =>
                                    setBuilderGenerationAcknowledged(event.target.checked)
                                  }
                                />
                                <span>
                                  I authorize deterministic file creation inside quarantine and
                                  acknowledge that the output is untrusted and non-executable.
                                </span>
                              </label>
                              <button
                                className="run-check-button mcp-builder-submit"
                                type="submit"
                                disabled={
                                  !builderGenerationAcknowledged ||
                                  builderGenerationMutation.isPending
                                }
                              >
                                {builderGenerationMutation.isPending ? (
                                  <RefreshCw className="spin" size={16} />
                                ) : (
                                  <FileCode2 size={16} />
                                )}
                                Create quarantined scaffold
                              </button>
                            </form>
                          )}
                          {builderGenerationMutation.isError && (
                            <div className="workspace-message error-state" role="alert">
                              <AlertTriangle size={20} />
                              <div>
                                <h3>Scaffold generation unavailable</h3>
                                <p>The exact design or quarantine boundary could not be verified.</p>
                              </div>
                            </div>
                          )}
                          {builderGenerationMutation.data?.data && (
                            <div className="mcp-builder-generation-result">
                              <div className="mcp-builder-generation-summary">
                                <div>
                                  <p className="eyebrow">QUARANTINED ARTIFACT</p>
                                  <strong>{builderGenerationMutation.data.data.generation_id}</strong>
                                  <code>{builderGenerationMutation.data.data.artifact_digest}</code>
                                </div>
                                <span className="state-badge analyzed">
                                  <LockKeyhole size={14} /> quarantined
                                </span>
                              </div>
                              <div className="mcp-builder-facts">
                                <div>
                                  <span>Files</span>
                                  <strong>{builderGenerationMutation.data.data.files.length}</strong>
                                </div>
                                <div>
                                  <span>Bytes</span>
                                  <strong>
                                    {builderGenerationMutation.data.data.artifact_size_bytes.toLocaleString()}
                                  </strong>
                                </div>
                                <div>
                                  <span>Validation</span>
                                  <strong>Not run</strong>
                                </div>
                                <div>
                                  <span>Runtime trust</span>
                                  <strong>None</strong>
                                </div>
                              </div>
                              <div className="mcp-builder-file-browser">
                                <div className="mcp-builder-file-list" aria-label="Generated files">
                                  {builderGenerationMutation.data.data.files.map((file) => (
                                    <button
                                      key={file.relative_path}
                                      type="button"
                                      className={
                                        file.relative_path === builderSelectedGeneratedFile
                                          ? "selected"
                                          : ""
                                      }
                                      onClick={() => {
                                        setBuilderSelectedGeneratedFile(file.relative_path);
                                        builderGeneratedFileMutation.mutate({
                                          projectId: builderGenerationMutation.data.data.project_id,
                                          relativePath: file.relative_path,
                                        });
                                      }}
                                      aria-label={`Preview ${file.relative_path}`}
                                    >
                                      <FileText size={14} />
                                      <span>{file.relative_path}</span>
                                      <small>{file.size_bytes} B</small>
                                    </button>
                                  ))}
                                </div>
                                <div className="mcp-builder-file-preview">
                                  <div>
                                    <span>Verified file preview</span>
                                    <code>{builderSelectedGeneratedFile || "Select a file"}</code>
                                  </div>
                                  {builderGeneratedFileMutation.isPending && (
                                    <div className="mcp-builder-preview-state">
                                      <RefreshCw className="spin" size={16} /> Verifying content
                                    </div>
                                  )}
                                  {builderGeneratedFileMutation.isError && (
                                    <div className="mcp-builder-preview-state error-state">
                                      <AlertTriangle size={16} /> Preview unavailable
                                    </div>
                                  )}
                                  {builderGeneratedFileMutation.data?.data && (
                                    <pre>{builderGeneratedFileMutation.data.data.content}</pre>
                                  )}
                                </div>
                              </div>
                              <div className="mcp-builder-boundary">
                                <LockKeyhole size={18} />
                                <p>
                                  Artifact integrity is verified on every read. Validation, packaging,
                                  registration, installation, execution, and infrastructure mutation
                                  remain unavailable.
                                </p>
                              </div>
                              <section
                                className="mcp-builder-validation"
                                aria-label="Static scaffold validation"
                              >
                                <div className="section-heading">
                                  <div>
                                    <p className="eyebrow">STATIC VALIDATION</p>
                                    <h3>Inspect the quarantined scaffold</h3>
                                    <p>
                                      Verify integrity, deterministic structure, permissions,
                                      traceability, and fail-closed authority without running code.
                                    </p>
                                  </div>
                                  <span className="state-badge pending">
                                    <ShieldCheck size={14} /> Static evidence only
                                  </span>
                                </div>
                                {!builderValidationMutation.data && (
                                  <form
                                    className="mcp-builder-validation-form"
                                    onSubmit={(event) => {
                                      event.preventDefault();
                                      const project = builderMutation.data?.data;
                                      const checkpoint = builderDesignMutation.data?.data;
                                      const generation = builderGenerationMutation.data?.data;
                                      if (
                                        !project ||
                                        !checkpoint ||
                                        !generation ||
                                        !builderValidationAcknowledged ||
                                        builderValidationMutation.isPending
                                      ) {
                                        return;
                                      }
                                      const candidates = new Map(
                                        project.capability_candidates.map((candidate) => [
                                          candidate.candidate_id,
                                          candidate,
                                        ]),
                                      );
                                      setBuilderDomainDecisions(
                                        Object.fromEntries(
                                          checkpoint.capability_decisions
                                            .filter((decision) => decision.generation_eligible)
                                            .map((decision) => [
                                              decision.candidate_id,
                                              {
                                                candidateId: decision.candidate_id,
                                                confirmedClass: decision.confirmed_class,
                                                decision: "accepted" as const,
                                                supportedProductVersions:
                                                  project.intended_product_versions,
                                                vendorPermission: decision.required_permission,
                                                authenticationAssessment:
                                                  "Authentication uses an external governed secret reference.",
                                                sideEffectAssessment:
                                                  "The operation is read-only with no documented side effect.",
                                                errorBehaviorAssessment:
                                                  "Errors, timeouts, pagination, and rate limits fail closed.",
                                                healthGuidanceAssessment:
                                                  "A bounded response is informational health evidence.",
                                                evidenceCitations: [
                                                  candidates.get(decision.candidate_id)?.citation ??
                                                    "",
                                                ],
                                                missingCaseCodes: [],
                                                rationale:
                                                  "Authoritative source evidence supports the bounded behavior.",
                                              },
                                            ]),
                                        ),
                                      );
                                      builderValidationMutation.mutate({
                                        project,
                                        checkpoint,
                                        generation,
                                      });
                                    }}
                                  >
                                    <div className="mcp-builder-generation-contract">
                                      <div>
                                        <span>Validation profile</span>
                                        <code>atlas.static-validation.python312.v1</code>
                                      </div>
                                      <div>
                                        <span>Deterministic checks</span>
                                        <strong>15</strong>
                                      </div>
                                      <div>
                                        <span>Execution authority</span>
                                        <strong>None</strong>
                                      </div>
                                    </div>
                                    <div className="mcp-builder-boundary">
                                      <ShieldCheck size={18} />
                                      <p>
                                        This inspection reads quarantined files and parses static
                                        structure only. It does not import, compile, test, execute,
                                        package, install, connect to a target, or grant runtime trust.
                                      </p>
                                    </div>
                                    <label className="mcp-builder-check">
                                      <input
                                        type="checkbox"
                                        checked={builderValidationAcknowledged}
                                        onChange={(event) =>
                                          setBuilderValidationAcknowledged(event.target.checked)
                                        }
                                      />
                                      <span>
                                        I understand this produces static evidence only and does not
                                        approve the connector for packaging, installation, or use.
                                      </span>
                                    </label>
                                    <button
                                      className="run-check-button mcp-builder-submit"
                                      type="submit"
                                      disabled={
                                        !builderValidationAcknowledged ||
                                        builderValidationMutation.isPending
                                      }
                                    >
                                      {builderValidationMutation.isPending ? (
                                        <RefreshCw className="spin" size={16} />
                                      ) : (
                                        <ShieldCheck size={16} />
                                      )}
                                      Run static validation
                                    </button>
                                  </form>
                                )}
                                {builderValidationMutation.isError && (
                                  <div className="workspace-message error-state" role="alert">
                                    <AlertTriangle size={20} />
                                    <div>
                                      <h3>Static validation unavailable</h3>
                                      <p>
                                        The bound artifact could not be verified or the report was
                                        rejected.
                                      </p>
                                    </div>
                                  </div>
                                )}
                                {builderValidationMutation.data?.data && (
                                  <div className="mcp-builder-validation-result">
                                    <div className="mcp-builder-generation-summary">
                                      <div>
                                        <p className="eyebrow">IMMUTABLE VALIDATION REPORT</p>
                                        <strong>
                                          {builderValidationMutation.data.data.validation_id}
                                        </strong>
                                        <code>
                                          {builderValidationMutation.data.data.canonical_digest}
                                        </code>
                                      </div>
                                      <span
                                        className={`state-badge ${
                                          builderValidationMutation.data.data.state === "passed"
                                            ? "analyzed"
                                            : "failed"
                                        }`}
                                      >
                                        {builderValidationMutation.data.data.state === "passed" ? (
                                          <CheckCircle2 size={14} />
                                        ) : (
                                          <AlertTriangle size={14} />
                                        )}
                                        Static validation {builderValidationMutation.data.data.state}
                                      </span>
                                    </div>
                                    <div className="mcp-builder-facts">
                                      <div>
                                        <span>Passed</span>
                                        <strong>
                                          {builderValidationMutation.data.data.passed_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Failed</span>
                                        <strong>
                                          {builderValidationMutation.data.data.failed_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Skipped</span>
                                        <strong>
                                          {builderValidationMutation.data.data.skipped_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Runtime trust</span>
                                        <strong>None</strong>
                                      </div>
                                    </div>
                                    <div className="mcp-builder-validation-meta">
                                      <span>
                                        Profile
                                        <code>
                                          {
                                            builderValidationMutation.data.data
                                              .validation_profile
                                          }
                                        </code>
                                      </span>
                                      <span>
                                        Validator
                                        <code>
                                          {builderValidationMutation.data.data.validator_version}
                                        </code>
                                      </span>
                                    </div>
                                    <div
                                      className="mcp-builder-validation-checks"
                                      aria-label="Static validation checks"
                                    >
                                      {builderValidationMutation.data.data.checks.map((check) => (
                                        <article key={check.code} data-state={check.state}>
                                          {check.state === "passed" ? (
                                            <CheckCircle2 size={16} />
                                          ) : (
                                            <AlertTriangle size={16} />
                                          )}
                                          <div>
                                            <strong>{check.code}</strong>
                                            <p>{check.summary}</p>
                                            {check.evidence_paths.length > 0 && (
                                              <code>{check.evidence_paths.join(" · ")}</code>
                                            )}
                                            {check.remediation && <small>{check.remediation}</small>}
                                          </div>
                                          <span>{check.state}</span>
                                        </article>
                                      ))}
                                    </div>
                                    <div className="mcp-builder-limitations">
                                      <strong>Validation boundaries</strong>
                                      <ul>
                                        {builderValidationMutation.data.data.limitations.map(
                                          (limitation) => (
                                            <li key={limitation}>{limitation}</li>
                                          ),
                                        )}
                                      </ul>
                                    </div>
                                    <div className="mcp-builder-boundary">
                                      <LockKeyhole size={18} />
                                      <p>
                                        Domain review, security review, dependency resolution,
                                        runtime self-test, lab validation, package approval,
                                        registration, installation, and execution remain incomplete
                                        and unavailable.
                                      </p>
                                    </div>
                                    {builderValidationMutation.data.data.state === "passed" && (
                                      <section
                                        className="mcp-builder-domain-review"
                                        aria-label="Human domain review"
                                      >
                                        <div className="section-heading">
                                          <div>
                                            <p className="eyebrow">HUMAN DOMAIN REVIEW</p>
                                            <h3>Confirm vendor semantics by capability</h3>
                                            <p>
                                              Record product applicability, permissions, behavior,
                                              operational impact, and exact source lineage.
                                            </p>
                                          </div>
                                          <span className="state-badge pending">
                                            <UserCheck size={14} /> Human decision
                                          </span>
                                        </div>
                                        {!builderDomainReviewMutation.data && (
                                          <form
                                            className="mcp-builder-domain-review-form"
                                            onSubmit={(event) => {
                                              event.preventDefault();
                                              const project = builderMutation.data?.data;
                                              const checkpoint = builderDesignMutation.data?.data;
                                              const generation =
                                                builderGenerationMutation.data?.data;
                                              const validation =
                                                builderValidationMutation.data?.data;
                                              const decisions =
                                                Object.values(builderDomainDecisions);
                                              if (
                                                !project ||
                                                !checkpoint ||
                                                !generation ||
                                                !validation ||
                                                !builderDomainReviewAcknowledged ||
                                                !builderDomainReviewSummary.trim() ||
                                                decisions.length === 0 ||
                                                builderDomainReviewMutation.isPending
                                              ) {
                                                return;
                                              }
                                              builderDomainReviewMutation.mutate({
                                                project,
                                                checkpoint,
                                                generation,
                                                validation,
                                                decisions,
                                                summary: builderDomainReviewSummary,
                                              });
                                            }}
                                          >
                                            <div className="mcp-builder-domain-contract">
                                              <div>
                                                <span>Review profile</span>
                                                <code>atlas.domain-review.connector.v1</code>
                                              </div>
                                              <div>
                                                <span>Reviewer contract</span>
                                                <code>mcp-builder-domain-review.v1</code>
                                              </div>
                                              <div>
                                                <span>Downstream authority</span>
                                                <strong>None</strong>
                                              </div>
                                            </div>
                                            <div className="mcp-builder-domain-decisions">
                                              {Object.values(builderDomainDecisions).map(
                                                (decision) => {
                                                  const candidate =
                                                    builderMutation.data?.data.capability_candidates.find(
                                                      (item) =>
                                                        item.candidate_id === decision.candidateId,
                                                    );
                                                  return (
                                                    <article key={decision.candidateId}>
                                                      <div className="mcp-builder-domain-decision-heading">
                                                        <div>
                                                          <strong>
                                                            {candidate?.summary ??
                                                              decision.candidateId}
                                                          </strong>
                                                          <code>{decision.candidateId}</code>
                                                        </div>
                                                        <span className="state-badge analyzed">
                                                          {decision.confirmedClass}
                                                        </span>
                                                      </div>
                                                      <div className="mcp-builder-domain-fields">
                                                        <label>
                                                          Decision
                                                          <select
                                                            aria-label={`Domain decision ${decision.candidateId}`}
                                                            value={decision.decision}
                                                            onChange={(event) => {
                                                              const value = event.target.value as
                                                                | "accepted"
                                                                | "needs_evidence"
                                                                | "rejected";
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  decision: value,
                                                                  missingCaseCodes:
                                                                    value === "accepted"
                                                                      ? []
                                                                      : decision.missingCaseCodes
                                                                            .length > 0
                                                                        ? decision.missingCaseCodes
                                                                        : [
                                                                            "domain.evidence-gap",
                                                                          ],
                                                                },
                                                              );
                                                            }}
                                                          >
                                                            <option value="accepted">Accepted</option>
                                                            <option value="needs_evidence">
                                                              Needs evidence
                                                            </option>
                                                            <option value="rejected">Rejected</option>
                                                          </select>
                                                        </label>
                                                        <label>
                                                          Supported product versions
                                                          <input
                                                            aria-label={`Supported versions ${decision.candidateId}`}
                                                            required
                                                            value={decision.supportedProductVersions.join(
                                                              ", ",
                                                            )}
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  supportedProductVersions:
                                                                    event.target.value
                                                                      .split(",")
                                                                      .map((value) => value.trim())
                                                                      .filter(Boolean),
                                                                },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                        <label>
                                                          Vendor permission
                                                          <input
                                                            aria-label={`Vendor permission ${decision.candidateId}`}
                                                            readOnly
                                                            value={decision.vendorPermission}
                                                          />
                                                        </label>
                                                        <label>
                                                          Source citation
                                                          <input
                                                            aria-label={`Evidence citation ${decision.candidateId}`}
                                                            readOnly
                                                            value={decision.evidenceCitations.join(
                                                              ", ",
                                                            )}
                                                          />
                                                        </label>
                                                        <label className="wide-field">
                                                          Authentication assessment
                                                          <textarea
                                                            aria-label={`Authentication assessment ${decision.candidateId}`}
                                                            required
                                                            value={
                                                              decision.authenticationAssessment
                                                            }
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  authenticationAssessment:
                                                                    event.target.value,
                                                                },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                        <label className="wide-field">
                                                          Side effects and operational impact
                                                          <textarea
                                                            aria-label={`Side effect assessment ${decision.candidateId}`}
                                                            required
                                                            value={decision.sideEffectAssessment}
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  sideEffectAssessment:
                                                                    event.target.value,
                                                                },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                        <label className="wide-field">
                                                          Error, timeout, pagination, and rate behavior
                                                          <textarea
                                                            aria-label={`Error behavior assessment ${decision.candidateId}`}
                                                            required
                                                            value={decision.errorBehaviorAssessment}
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  errorBehaviorAssessment:
                                                                    event.target.value,
                                                                },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                        <label className="wide-field">
                                                          Health guidance
                                                          <textarea
                                                            aria-label={`Health guidance assessment ${decision.candidateId}`}
                                                            required
                                                            value={decision.healthGuidanceAssessment}
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                {
                                                                  healthGuidanceAssessment:
                                                                    event.target.value,
                                                                },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                        {decision.decision !== "accepted" && (
                                                          <label className="wide-field">
                                                            Missing-case codes
                                                            <input
                                                              aria-label={`Missing case codes ${decision.candidateId}`}
                                                              required
                                                              value={decision.missingCaseCodes.join(
                                                                ", ",
                                                              )}
                                                              onChange={(event) =>
                                                                updateBuilderDomainDecision(
                                                                  decision.candidateId,
                                                                  {
                                                                    missingCaseCodes:
                                                                      event.target.value
                                                                        .split(",")
                                                                        .map((value) => value.trim())
                                                                        .filter(Boolean),
                                                                  },
                                                                )
                                                              }
                                                            />
                                                          </label>
                                                        )}
                                                        <label className="wide-field">
                                                          Human rationale
                                                          <textarea
                                                            aria-label={`Domain rationale ${decision.candidateId}`}
                                                            required
                                                            value={decision.rationale}
                                                            onChange={(event) =>
                                                              updateBuilderDomainDecision(
                                                                decision.candidateId,
                                                                { rationale: event.target.value },
                                                              )
                                                            }
                                                          />
                                                        </label>
                                                      </div>
                                                    </article>
                                                  );
                                                },
                                              )}
                                            </div>
                                            <label className="mcp-builder-domain-summary">
                                              Review summary
                                              <textarea
                                                required
                                                value={builderDomainReviewSummary}
                                                onChange={(event) =>
                                                  setBuilderDomainReviewSummary(event.target.value)
                                                }
                                              />
                                            </label>
                                            <label className="mcp-builder-check">
                                              <input
                                                type="checkbox"
                                                checked={builderDomainReviewAcknowledged}
                                                onChange={(event) =>
                                                  setBuilderDomainReviewAcknowledged(
                                                    event.target.checked,
                                                  )
                                                }
                                              />
                                              <span>
                                                I am the accountable human domain reviewer. This
                                                decision records semantic evidence only and grants no
                                                security, lab, package, runtime, or execution approval.
                                              </span>
                                            </label>
                                            <button
                                              className="run-check-button mcp-builder-submit"
                                              type="submit"
                                              disabled={
                                                !builderDomainReviewAcknowledged ||
                                                builderDomainReviewMutation.isPending
                                              }
                                            >
                                              {builderDomainReviewMutation.isPending ? (
                                                <RefreshCw className="spin" size={16} />
                                              ) : (
                                                <UserCheck size={16} />
                                              )}
                                              Record domain review
                                            </button>
                                          </form>
                                        )}
                                        {builderDomainReviewMutation.isError && (
                                          <div className="workspace-message error-state" role="alert">
                                            <AlertTriangle size={20} />
                                            <div>
                                              <h3>Domain review unavailable</h3>
                                              <p>
                                                The exact evidence binding or capability assessment
                                                was rejected.
                                              </p>
                                            </div>
                                          </div>
                                        )}
                                        {builderDomainReviewMutation.data?.data && (
                                          <div className="mcp-builder-domain-result">
                                            <div className="mcp-builder-generation-summary">
                                              <div>
                                                <p className="eyebrow">IMMUTABLE DOMAIN REVIEW</p>
                                                <strong>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .review_id
                                                  }
                                                </strong>
                                                <code>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .canonical_digest
                                                  }
                                                </code>
                                              </div>
                                              <span
                                                className={`state-badge ${
                                                  builderDomainReviewMutation.data.data.state ===
                                                  "accepted"
                                                    ? "analyzed"
                                                    : "failed"
                                                }`}
                                              >
                                                {builderDomainReviewMutation.data.data.state ===
                                                "accepted" ? (
                                                  <CheckCircle2 size={14} />
                                                ) : (
                                                  <AlertTriangle size={14} />
                                                )}
                                                {builderDomainReviewMutation.data.data.state.replace(
                                                  "_",
                                                  " ",
                                                )}
                                              </span>
                                            </div>
                                            <div className="mcp-builder-facts">
                                              <div>
                                                <span>Accepted</span>
                                                <strong>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .accepted_count
                                                  }
                                                </strong>
                                              </div>
                                              <div>
                                                <span>Needs evidence</span>
                                                <strong>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .needs_evidence_count
                                                  }
                                                </strong>
                                              </div>
                                              <div>
                                                <span>Rejected</span>
                                                <strong>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .rejected_count
                                                  }
                                                </strong>
                                              </div>
                                              <div>
                                                <span>Reviewed by</span>
                                                <code>
                                                  {
                                                    builderDomainReviewMutation.data.data
                                                      .reviewed_by
                                                  }
                                                </code>
                                              </div>
                                            </div>
                                            <div className="mcp-builder-domain-evidence">
                                              {builderDomainReviewMutation.data.data.capability_decisions.map(
                                                (decision) => (
                                                  <article key={decision.candidate_id}>
                                                    <div>
                                                      <strong>{decision.candidate_id}</strong>
                                                      <code>
                                                        {decision.evidence_citations.join(", ")}
                                                      </code>
                                                    </div>
                                                    <span>{decision.decision.replace("_", " ")}</span>
                                                    <p>{decision.rationale}</p>
                                                    <small>
                                                      {decision.missing_case_codes.join(", ") ||
                                                        "No declared evidence gaps"}
                                                    </small>
                                                  </article>
                                                ),
                                              )}
                                            </div>
                                            <div className="mcp-builder-limitations">
                                              <strong>Domain-review boundaries</strong>
                                              <ul>
                                                {builderDomainReviewMutation.data.data.limitations.map(
                                                  (limitation) => (
                                                    <li key={limitation}>{limitation}</li>
                                                  ),
                                                )}
                                              </ul>
                                            </div>
                                            <div className="mcp-builder-boundary">
                                              <LockKeyhole size={18} />
                                              <p>
                                                Security review, dependency resolution, runtime
                                                self-test, lab validation, package approval,
                                                registration, installation, enablement, target access,
                                                execution, and infrastructure mutation remain false
                                                and unavailable.
                                              </p>
                                            </div>
                                            {builderDomainReviewMutation.data.data.state ===
                                              "accepted" && (
                                              <section
                                                className="mcp-builder-security-review"
                                                aria-label="Independent security review"
                                              >
                                                <div className="section-heading">
                                                  <div>
                                                    <p className="eyebrow">SECURITY REVIEW</p>
                                                    <h3>Assess the quarantined scaffold</h3>
                                                    <p>
                                                      Record independent security judgment across
                                                      provenance, supply chain, credentials, network,
                                                      validation, logging, privileges, and governance.
                                                    </p>
                                                  </div>
                                                  <span className="state-badge pending">
                                                    <ShieldCheck size={14} /> Independent human
                                                  </span>
                                                </div>
                                                {identity?.subject_id ===
                                                  builderDomainReviewMutation.data.data.reviewed_by &&
                                                  !builderSecurityReviewMutation.data && (
                                                    <div
                                                      className="workspace-message mcp-builder-security-sod"
                                                      role="status"
                                                    >
                                                      <UserX size={20} />
                                                      <div>
                                                        <h3>Independent reviewer required</h3>
                                                        <p>
                                                          The domain reviewer cannot approve the
                                                          security posture. Continue with a different
                                                          authorized security reviewer session.
                                                        </p>
                                                      </div>
                                                    </div>
                                                  )}
                                                {identity?.subject_id !==
                                                  builderDomainReviewMutation.data.data.reviewed_by &&
                                                  !builderSecurityReviewMutation.data && (
                                                    <form
                                                      className="mcp-builder-security-review-form"
                                                      onSubmit={(event) => {
                                                        event.preventDefault();
                                                        const project = builderMutation.data?.data;
                                                        const checkpoint =
                                                          builderDesignMutation.data?.data;
                                                        const generation =
                                                          builderGenerationMutation.data?.data;
                                                        const validation =
                                                          builderValidationMutation.data?.data;
                                                        const domainReview =
                                                          builderDomainReviewMutation.data?.data;
                                                        const assessments = Object.values(
                                                          builderSecurityAssessments,
                                                        );
                                                        if (
                                                          !project ||
                                                          !checkpoint ||
                                                          !generation ||
                                                          !validation ||
                                                          !domainReview ||
                                                          assessments.length !== 9 ||
                                                          !builderSecurityReviewAcknowledged ||
                                                          !builderSecurityReviewSummary.trim() ||
                                                          builderSecurityReviewMutation.isPending
                                                        ) {
                                                          return;
                                                        }
                                                        builderSecurityReviewMutation.mutate({
                                                          project,
                                                          checkpoint,
                                                          generation,
                                                          validation,
                                                          domainReview,
                                                          assessments,
                                                          summary: builderSecurityReviewSummary,
                                                        });
                                                      }}
                                                    >
                                                      <div className="mcp-builder-domain-contract">
                                                        <div>
                                                          <span>Review profile</span>
                                                          <code>
                                                            atlas.security-review.connector.v1
                                                          </code>
                                                        </div>
                                                        <div>
                                                          <span>Reviewer contract</span>
                                                          <code>
                                                            mcp-builder-security-review.v1
                                                          </code>
                                                        </div>
                                                        <div>
                                                          <span>Reviewer separation</span>
                                                          <strong>Required</strong>
                                                        </div>
                                                      </div>
                                                      <div className="mcp-builder-security-controls">
                                                        {MCP_BUILDER_SECURITY_CONTROLS.map(
                                                          (control) => {
                                                            const assessment =
                                                              builderSecurityAssessments[control.id];
                                                            if (!assessment) return null;
                                                            return (
                                                              <article key={control.id}>
                                                                <div className="mcp-builder-domain-decision-heading">
                                                                  <div>
                                                                    <strong>{control.label}</strong>
                                                                    <code>{control.id}</code>
                                                                  </div>
                                                                  <ShieldCheck size={18} />
                                                                </div>
                                                                <div className="mcp-builder-domain-fields">
                                                                  <label>
                                                                    Decision
                                                                    <select
                                                                      aria-label={`Security decision ${control.id}`}
                                                                      value={assessment.decision}
                                                                      onChange={(event) => {
                                                                        const decision = event.target
                                                                          .value as
                                                                          | "accepted"
                                                                          | "needs_remediation"
                                                                          | "rejected";
                                                                        updateBuilderSecurityAssessment(
                                                                          control.id,
                                                                          {
                                                                            decision,
                                                                            findingCodes:
                                                                              decision === "accepted"
                                                                                ? []
                                                                                : assessment
                                                                                      .findingCodes
                                                                                      .length > 0
                                                                                  ? assessment.findingCodes
                                                                                  : [
                                                                                      `security.${control.id}.finding`,
                                                                                    ],
                                                                          },
                                                                        );
                                                                      }}
                                                                    >
                                                                      <option value="accepted">
                                                                        Accepted
                                                                      </option>
                                                                      <option value="needs_remediation">
                                                                        Needs remediation
                                                                      </option>
                                                                      <option value="rejected">
                                                                        Rejected
                                                                      </option>
                                                                    </select>
                                                                  </label>
                                                                  <label>
                                                                    Evidence reference
                                                                    <input
                                                                      aria-label={`Security evidence ${control.id}`}
                                                                      readOnly
                                                                      value={assessment.evidenceReferences.join(
                                                                        ", ",
                                                                      )}
                                                                    />
                                                                  </label>
                                                                  <label className="wide-field">
                                                                    Independent assessment
                                                                    <textarea
                                                                      aria-label={`Security assessment ${control.id}`}
                                                                      required
                                                                      value={assessment.assessment}
                                                                      onChange={(event) =>
                                                                        updateBuilderSecurityAssessment(
                                                                          control.id,
                                                                          {
                                                                            assessment:
                                                                              event.target.value,
                                                                          },
                                                                        )
                                                                      }
                                                                    />
                                                                  </label>
                                                                  {assessment.decision !==
                                                                    "accepted" && (
                                                                    <label className="wide-field">
                                                                      Finding codes
                                                                      <input
                                                                        aria-label={`Security findings ${control.id}`}
                                                                        required
                                                                        value={assessment.findingCodes.join(
                                                                          ", ",
                                                                        )}
                                                                        onChange={(event) =>
                                                                          updateBuilderSecurityAssessment(
                                                                            control.id,
                                                                            {
                                                                              findingCodes:
                                                                                event.target.value
                                                                                  .split(",")
                                                                                  .map((value) =>
                                                                                    value.trim(),
                                                                                  )
                                                                                  .filter(Boolean),
                                                                            },
                                                                          )
                                                                        }
                                                                      />
                                                                    </label>
                                                                  )}
                                                                  <label className="wide-field">
                                                                    Required controls
                                                                    <textarea
                                                                      aria-label={`Required controls ${control.id}`}
                                                                      required
                                                                      value={assessment.requiredControls.join(
                                                                        "\n",
                                                                      )}
                                                                      onChange={(event) =>
                                                                        updateBuilderSecurityAssessment(
                                                                          control.id,
                                                                          {
                                                                            requiredControls:
                                                                              event.target.value
                                                                                .split("\n")
                                                                                .map((value) =>
                                                                                  value.trim(),
                                                                                )
                                                                                .filter(Boolean),
                                                                          },
                                                                        )
                                                                      }
                                                                    />
                                                                  </label>
                                                                </div>
                                                              </article>
                                                            );
                                                          },
                                                        )}
                                                      </div>
                                                      <label className="mcp-builder-domain-summary">
                                                        Security review summary
                                                        <textarea
                                                          required
                                                          value={builderSecurityReviewSummary}
                                                          onChange={(event) =>
                                                            setBuilderSecurityReviewSummary(
                                                              event.target.value,
                                                            )
                                                          }
                                                        />
                                                      </label>
                                                      <label className="mcp-builder-check">
                                                        <input
                                                          type="checkbox"
                                                          checked={
                                                            builderSecurityReviewAcknowledged
                                                          }
                                                          onChange={(event) =>
                                                            setBuilderSecurityReviewAcknowledged(
                                                              event.target.checked,
                                                            )
                                                          }
                                                        />
                                                        <span>
                                                          I am the independent human security
                                                          reviewer. This decision grants no lab,
                                                          package, installation, runtime, target, or
                                                          execution authority.
                                                        </span>
                                                      </label>
                                                      <button
                                                        className="run-check-button mcp-builder-submit"
                                                        type="submit"
                                                        disabled={
                                                          !builderSecurityReviewAcknowledged ||
                                                          builderSecurityReviewMutation.isPending
                                                        }
                                                      >
                                                        {builderSecurityReviewMutation.isPending ? (
                                                          <RefreshCw className="spin" size={16} />
                                                        ) : (
                                                          <ShieldCheck size={16} />
                                                        )}
                                                        Record security review
                                                      </button>
                                                    </form>
                                                  )}
                                                {builderSecurityReviewMutation.isError && (
                                                  <div
                                                    className="workspace-message error-state"
                                                    role="alert"
                                                  >
                                                    <AlertTriangle size={20} />
                                                    <div>
                                                      <h3>Security review unavailable</h3>
                                                      <p>
                                                        Reviewer separation, exact evidence, or the
                                                        complete control set was rejected.
                                                      </p>
                                                    </div>
                                                  </div>
                                                )}
                                                {builderSecurityReviewMutation.data?.data && (
                                                  <div className="mcp-builder-security-result">
                                                    <div className="mcp-builder-generation-summary">
                                                      <div>
                                                        <p className="eyebrow">
                                                          IMMUTABLE SECURITY REVIEW
                                                        </p>
                                                        <strong>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .review_id
                                                          }
                                                        </strong>
                                                        <code>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .canonical_digest
                                                          }
                                                        </code>
                                                      </div>
                                                      <span
                                                        className={`state-badge ${
                                                          builderSecurityReviewMutation.data.data
                                                            .state === "accepted"
                                                            ? "analyzed"
                                                            : "failed"
                                                        }`}
                                                      >
                                                        {builderSecurityReviewMutation.data.data
                                                          .state === "accepted" ? (
                                                          <CheckCircle2 size={14} />
                                                        ) : (
                                                          <AlertTriangle size={14} />
                                                        )}
                                                        {builderSecurityReviewMutation.data.data.state.replace(
                                                          "_",
                                                          " ",
                                                        )}
                                                      </span>
                                                    </div>
                                                    <div className="mcp-builder-facts">
                                                      <div>
                                                        <span>Accepted</span>
                                                        <strong>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .accepted_count
                                                          }
                                                        </strong>
                                                      </div>
                                                      <div>
                                                        <span>Needs remediation</span>
                                                        <strong>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .needs_remediation_count
                                                          }
                                                        </strong>
                                                      </div>
                                                      <div>
                                                        <span>Rejected</span>
                                                        <strong>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .rejected_count
                                                          }
                                                        </strong>
                                                      </div>
                                                      <div>
                                                        <span>Reviewed by</span>
                                                        <code>
                                                          {
                                                            builderSecurityReviewMutation.data.data
                                                              .reviewed_by
                                                          }
                                                        </code>
                                                      </div>
                                                    </div>
                                                    <div className="mcp-builder-security-evidence">
                                                      {builderSecurityReviewMutation.data.data.control_assessments.map(
                                                        (assessment) => (
                                                          <article key={assessment.control}>
                                                            <div>
                                                              <strong>
                                                                {assessment.control.replaceAll(
                                                                  "_",
                                                                  " ",
                                                                )}
                                                              </strong>
                                                              <code>
                                                                {assessment.evidence_references.join(
                                                                  ", ",
                                                                )}
                                                              </code>
                                                            </div>
                                                            <span>
                                                              {assessment.decision.replace(
                                                                "_",
                                                                " ",
                                                              )}
                                                            </span>
                                                            <p>{assessment.assessment}</p>
                                                            <small>
                                                              {assessment.finding_codes.join(
                                                                ", ",
                                                              ) || "No declared security findings"}
                                                            </small>
                                                          </article>
                                                        ),
                                                      )}
                                                    </div>
                                                    <div className="mcp-builder-limitations">
                                                      <strong>Security-review boundaries</strong>
                                                      <ul>
                                                        {builderSecurityReviewMutation.data.data.limitations.map(
                                                          (limitation) => (
                                                            <li key={limitation}>{limitation}</li>
                                                          ),
                                                        )}
                                                      </ul>
                                                    </div>
                                                    <div className="mcp-builder-boundary">
                                                      <LockKeyhole size={18} />
                                                      <p>
                                                        Lab validation, package creation, signing,
                                                        registration, installation, target access,
                                                        runtime trust, execution, and infrastructure
                                                        mutation remain false and unavailable.
                                                      </p>
                                                    </div>
                                                  </div>
                                                )}
                                                {builderSecurityReviewMutation.data?.data.state ===
                                                  "accepted" && (
                                                  <section
                                                    className="mcp-builder-lab-validation"
                                                    aria-label="Isolated lab validation"
                                                  >
                                                    <div className="workspace-section-heading">
                                                      <div>
                                                        <p className="eyebrow">ISOLATED LAB</p>
                                                        <h3>Verify the fail-closed scaffold</h3>
                                                        <p>
                                                          Run eight synthetic checks in an ephemeral,
                                                          network-denied Python 3.12 process.
                                                        </p>
                                                      </div>
                                                      <span className="state-badge pending">
                                                        <FlaskConical size={14} /> Synthetic only
                                                      </span>
                                                    </div>
                                                    {(identity?.subject_id ===
                                                      builderDomainReviewMutation.data?.data
                                                        .reviewed_by ||
                                                      identity?.subject_id ===
                                                        builderSecurityReviewMutation.data.data
                                                          .reviewed_by) &&
                                                      !builderLabValidationMutation.data && (
                                                        <div
                                                          className="workspace-message mcp-builder-security-sod"
                                                          role="status"
                                                        >
                                                          <UserX size={20} />
                                                          <div>
                                                            <h3>Independent lab operator required</h3>
                                                            <p>
                                                              Domain and security reviewers cannot
                                                              operate this validation. Continue with a
                                                              different authorized operator session.
                                                            </p>
                                                          </div>
                                                        </div>
                                                      )}
                                                    {identity?.subject_id !==
                                                      builderDomainReviewMutation.data?.data
                                                        .reviewed_by &&
                                                      identity?.subject_id !==
                                                        builderSecurityReviewMutation.data.data
                                                          .reviewed_by &&
                                                      !builderLabValidationMutation.data && (
                                                        <form
                                                          className="mcp-builder-lab-form"
                                                          onSubmit={(event) => {
                                                            event.preventDefault();
                                                            const project = builderMutation.data?.data;
                                                            const checkpoint =
                                                              builderDesignMutation.data?.data;
                                                            const generation =
                                                              builderGenerationMutation.data?.data;
                                                            const validation =
                                                              builderValidationMutation.data?.data;
                                                            const domainReview =
                                                              builderDomainReviewMutation.data?.data;
                                                            const securityReview =
                                                              builderSecurityReviewMutation.data?.data;
                                                            if (
                                                              !project ||
                                                              !checkpoint ||
                                                              !generation ||
                                                              !validation ||
                                                              !domainReview ||
                                                              !securityReview ||
                                                              !builderLabValidationAcknowledged ||
                                                              builderLabValidationMutation.isPending
                                                            ) {
                                                              return;
                                                            }
                                                            builderLabValidationMutation.mutate({
                                                              project,
                                                              checkpoint,
                                                              generation,
                                                              validation,
                                                              domainReview,
                                                              securityReview,
                                                            });
                                                          }}
                                                        >
                                                          <div className="mcp-builder-domain-contract">
                                                            <div>
                                                              <span>Lab profile</span>
                                                              <code>
                                                                atlas.lab-validation.python312.v1
                                                              </code>
                                                            </div>
                                                            <div>
                                                              <span>Runner contract</span>
                                                              <code>
                                                                mcp-builder-isolated-runner.v1
                                                              </code>
                                                            </div>
                                                            <div>
                                                              <span>Target access</span>
                                                              <strong>Denied</strong>
                                                            </div>
                                                          </div>
                                                          <label className="mcp-builder-check">
                                                            <input
                                                              type="checkbox"
                                                              checked={
                                                                builderLabValidationAcknowledged
                                                              }
                                                              onChange={(event) =>
                                                                setBuilderLabValidationAcknowledged(
                                                                  event.target.checked,
                                                                )
                                                              }
                                                            />
                                                            <span>
                                                              I am the independent lab operator. I
                                                              authorize only ephemeral, secret-free,
                                                              synthetic scaffold checks with no vendor
                                                              target or infrastructure access.
                                                            </span>
                                                          </label>
                                                          <button
                                                            className="run-check-button mcp-builder-submit"
                                                            type="submit"
                                                            disabled={
                                                              !builderLabValidationAcknowledged ||
                                                              builderLabValidationMutation.isPending
                                                            }
                                                          >
                                                            {builderLabValidationMutation.isPending ? (
                                                              <RefreshCw
                                                                className="spin"
                                                                size={16}
                                                              />
                                                            ) : (
                                                              <FlaskConical size={16} />
                                                            )}
                                                            Run isolated validation
                                                          </button>
                                                        </form>
                                                      )}
                                                    {builderLabValidationMutation.isError && (
                                                      <div
                                                        className="workspace-message error-state"
                                                        role="alert"
                                                      >
                                                        <AlertTriangle size={20} />
                                                        <div>
                                                          <h3>Lab validation unavailable</h3>
                                                          <p>
                                                            Exact evidence, operator separation, or
                                                            the isolated runner boundary was rejected.
                                                          </p>
                                                        </div>
                                                      </div>
                                                    )}
                                                    {builderLabValidationMutation.data?.data && (
                                                      <div className="mcp-builder-lab-result">
                                                        <div className="mcp-builder-generation-summary">
                                                          <div>
                                                            <p className="eyebrow">
                                                              IMMUTABLE LAB EVIDENCE
                                                            </p>
                                                            <strong>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .lab_validation_id
                                                              }
                                                            </strong>
                                                            <code>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .canonical_digest
                                                              }
                                                            </code>
                                                          </div>
                                                          <span
                                                            className={`state-badge ${
                                                              builderLabValidationMutation.data.data
                                                                .state === "passed"
                                                                ? "analyzed"
                                                                : "failed"
                                                            }`}
                                                          >
                                                            {builderLabValidationMutation.data.data
                                                              .state === "passed" ? (
                                                              <CheckCircle2 size={14} />
                                                            ) : (
                                                              <AlertTriangle size={14} />
                                                            )}
                                                            {
                                                              builderLabValidationMutation.data.data
                                                                .state
                                                            }
                                                          </span>
                                                        </div>
                                                        <div className="mcp-builder-facts">
                                                          <div>
                                                            <span>Passed</span>
                                                            <strong>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .passed_count
                                                              }
                                                            </strong>
                                                          </div>
                                                          <div>
                                                            <span>Failed</span>
                                                            <strong>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .failed_count
                                                              }
                                                            </strong>
                                                          </div>
                                                          <div>
                                                            <span>Runtime</span>
                                                            <code>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .runtime_version
                                                              }
                                                            </code>
                                                          </div>
                                                          <div>
                                                            <span>Duration</span>
                                                            <strong>
                                                              {
                                                                builderLabValidationMutation.data.data
                                                                  .duration_ms
                                                              }
                                                              ms
                                                            </strong>
                                                          </div>
                                                        </div>
                                                        <div className="mcp-builder-lab-checks">
                                                          {builderLabValidationMutation.data.data.checks.map(
                                                            (check) => (
                                                              <article key={check.code}>
                                                                <div>
                                                                  {check.state === "passed" ? (
                                                                    <CheckCircle2 size={17} />
                                                                  ) : (
                                                                    <AlertTriangle size={17} />
                                                                  )}
                                                                  <strong>
                                                                    {check.code
                                                                      .replace("lab.", "")
                                                                      .replaceAll("_", " ")}
                                                                  </strong>
                                                                </div>
                                                                <span>{check.state}</span>
                                                                <p>{check.summary}</p>
                                                                <code>
                                                                  {check.evidence_paths.join(", ")}
                                                                </code>
                                                              </article>
                                                            ),
                                                          )}
                                                        </div>
                                                        <div className="mcp-builder-limitations">
                                                          <strong>Lab-validation boundaries</strong>
                                                          <ul>
                                                            {builderLabValidationMutation.data.data.limitations.map(
                                                              (limitation) => (
                                                                <li key={limitation}>{limitation}</li>
                                                              ),
                                                            )}
                                                          </ul>
                                                        </div>
                                                        <div className="mcp-builder-boundary">
                                                          <LockKeyhole size={18} />
                                                          <p>
                                                            Package creation, signing, registration,
                                                            installation, vendor target access, runtime
                                                            trust, execution authority, and
                                                            infrastructure mutation remain false.
                                                          </p>
                                                        </div>
                                                      </div>
                                                    )}
                                                    {builderLabValidationMutation.data?.data.state ===
                                                      "passed" && (
                                                      <section
                                                        className="mcp-builder-candidate-handoff"
                                                        aria-label="Candidate package custody"
                                                      >
                                                        <div className="workspace-section-heading">
                                                          <div>
                                                            <p className="eyebrow">PACKAGE CUSTODY</p>
                                                            <h3>Create the quarantined candidate</h3>
                                                            <p>
                                                              Preserve the exact reviewed scaffold and
                                                              evidence lineage in a deterministic,
                                                              unsigned archive.
                                                            </p>
                                                          </div>
                                                          <span className="state-badge pending">
                                                            <Archive size={14} /> Quarantine only
                                                          </span>
                                                        </div>
                                                        {(identity?.subject_id ===
                                                          builderDomainReviewMutation.data?.data
                                                            .reviewed_by ||
                                                          identity?.subject_id ===
                                                            builderSecurityReviewMutation.data?.data
                                                              .reviewed_by ||
                                                          identity?.subject_id ===
                                                            builderLabValidationMutation.data.data
                                                              .operated_by) &&
                                                          !builderCandidateHandoffMutation.data && (
                                                            <div
                                                              className="workspace-message mcp-builder-security-sod"
                                                              role="status"
                                                            >
                                                              <UserX size={20} />
                                                              <div>
                                                                <h3>Independent package custodian required</h3>
                                                                <p>
                                                                  Reviewers and the lab operator cannot
                                                                  take custody. Continue with a different
                                                                  authorized custodian session.
                                                                </p>
                                                              </div>
                                                            </div>
                                                          )}
                                                        {identity?.subject_id !==
                                                          builderDomainReviewMutation.data?.data
                                                            .reviewed_by &&
                                                          identity?.subject_id !==
                                                            builderSecurityReviewMutation.data?.data
                                                              .reviewed_by &&
                                                          identity?.subject_id !==
                                                            builderLabValidationMutation.data.data
                                                              .operated_by &&
                                                          !builderCandidateHandoffMutation.data && (
                                                            <form
                                                              className="mcp-builder-lab-form"
                                                              onSubmit={(event) => {
                                                                event.preventDefault();
                                                                const project = builderMutation.data?.data;
                                                                const checkpoint =
                                                                  builderDesignMutation.data?.data;
                                                                const generation =
                                                                  builderGenerationMutation.data?.data;
                                                                const validation =
                                                                  builderValidationMutation.data?.data;
                                                                const domainReview =
                                                                  builderDomainReviewMutation.data?.data;
                                                                const securityReview =
                                                                  builderSecurityReviewMutation.data?.data;
                                                                const labValidation =
                                                                  builderLabValidationMutation.data?.data;
                                                                if (
                                                                  !project ||
                                                                  !checkpoint ||
                                                                  !generation ||
                                                                  !validation ||
                                                                  !domainReview ||
                                                                  !securityReview ||
                                                                  !labValidation ||
                                                                  !builderCandidateHandoffAcknowledged ||
                                                                  builderCandidateHandoffMutation.isPending
                                                                ) {
                                                                  return;
                                                                }
                                                                builderCandidateHandoffMutation.mutate({
                                                                  project,
                                                                  checkpoint,
                                                                  generation,
                                                                  validation,
                                                                  domainReview,
                                                                  securityReview,
                                                                  labValidation,
                                                                });
                                                              }}
                                                            >
                                                              <div className="mcp-builder-domain-contract">
                                                                <div>
                                                                  <span>Handoff profile</span>
                                                                  <code>
                                                                    atlas.candidate-handoff.python312.v1
                                                                  </code>
                                                                </div>
                                                                <div>
                                                                  <span>Package state</span>
                                                                  <strong>Quarantined</strong>
                                                                </div>
                                                                <div>
                                                                  <span>Signature</span>
                                                                  <strong>Unsigned</strong>
                                                                </div>
                                                              </div>
                                                              <label className="mcp-builder-check">
                                                                <input
                                                                  type="checkbox"
                                                                  checked={
                                                                    builderCandidateHandoffAcknowledged
                                                                  }
                                                                  onChange={(event) =>
                                                                    setBuilderCandidateHandoffAcknowledged(
                                                                      event.target.checked,
                                                                    )
                                                                  }
                                                                />
                                                                <span>
                                                                  I am the independent package custodian. I
                                                                  acknowledge that this creates only an
                                                                  unsigned quarantined archive and grants no
                                                                  registration, installation, runtime, or
                                                                  execution authority.
                                                                </span>
                                                              </label>
                                                              <button
                                                                className="run-check-button mcp-builder-submit"
                                                                type="submit"
                                                                disabled={
                                                                  !builderCandidateHandoffAcknowledged ||
                                                                  builderCandidateHandoffMutation.isPending
                                                                }
                                                              >
                                                                {builderCandidateHandoffMutation.isPending ? (
                                                                  <RefreshCw className="spin" size={16} />
                                                                ) : (
                                                                  <PackageCheck size={16} />
                                                                )}
                                                                Create candidate package
                                                              </button>
                                                            </form>
                                                          )}
                                                        {builderCandidateHandoffMutation.isError && (
                                                          <div
                                                            className="workspace-message error-state"
                                                            role="alert"
                                                          >
                                                            <AlertTriangle size={20} />
                                                            <div>
                                                              <h3>Candidate package unavailable</h3>
                                                              <p>
                                                                Custody separation, evidence lineage, or
                                                                archive integrity was rejected.
                                                              </p>
                                                            </div>
                                                          </div>
                                                        )}
                                                        {builderCandidateHandoffMutation.data?.data && (
                                                          <div className="mcp-builder-lab-result">
                                                            <div className="mcp-builder-generation-summary">
                                                              <div>
                                                                <p className="eyebrow">
                                                                  IMMUTABLE PACKAGE EVIDENCE
                                                                </p>
                                                                <strong>
                                                                  {
                                                                    builderCandidateHandoffMutation.data.data
                                                                      .handoff_id
                                                                  }
                                                                </strong>
                                                                <code>
                                                                  {
                                                                    builderCandidateHandoffMutation.data.data
                                                                      .package_digest
                                                                  }
                                                                </code>
                                                              </div>
                                                              <span className="state-badge pending">
                                                                <LockKeyhole size={14} /> candidate
                                                                quarantined
                                                              </span>
                                                            </div>
                                                            <div className="mcp-builder-facts">
                                                              <div>
                                                                <span>Signature</span>
                                                                <strong>Unsigned</strong>
                                                              </div>
                                                              <div>
                                                                <span>Files</span>
                                                                <strong>
                                                                  {
                                                                    builderCandidateHandoffMutation.data.data
                                                                      .generated_file_count
                                                                  }
                                                                </strong>
                                                              </div>
                                                              <div>
                                                                <span>Archive entries</span>
                                                                <strong>
                                                                  {
                                                                    builderCandidateHandoffMutation.data.data
                                                                      .package_entry_count
                                                                  }
                                                                </strong>
                                                              </div>
                                                              <div>
                                                                <span>Size</span>
                                                                <strong>
                                                                  {builderCandidateHandoffMutation.data.data.package_size_bytes.toLocaleString()} bytes
                                                                </strong>
                                                              </div>
                                                            </div>
                                                            <div className="mcp-builder-limitations">
                                                              <strong>Approved capabilities</strong>
                                                              <ul>
                                                                {builderCandidateHandoffMutation.data.data.capabilities.map(
                                                                  (capability) => (
                                                                    <li key={capability.candidate_id}>
                                                                      {capability.candidate_id} · {capability.capability_class} · {capability.required_permission}
                                                                    </li>
                                                                  ),
                                                                )}
                                                              </ul>
                                                            </div>
                                                            <div className="mcp-builder-limitations">
                                                              <strong>Candidate boundaries</strong>
                                                              <ul>
                                                                {builderCandidateHandoffMutation.data.data.limitations.map(
                                                                  (limitation) => (
                                                                    <li key={limitation}>{limitation}</li>
                                                                  ),
                                                                )}
                                                              </ul>
                                                            </div>
                                                            <button
                                                              className="run-check-button mcp-builder-submit"
                                                              type="button"
                                                              disabled={
                                                                builderCandidateArchiveMutation.isPending
                                                              }
                                                              onClick={() =>
                                                                builderCandidateArchiveMutation.mutate(
                                                                  builderCandidateHandoffMutation.data.data,
                                                                )
                                                              }
                                                            >
                                                              {builderCandidateArchiveMutation.isPending ? (
                                                                <RefreshCw className="spin" size={16} />
                                                              ) : (
                                                                <Download size={16} />
                                                              )}
                                                              Download verified archive
                                                            </button>
                                                            {builderCandidateArchiveMutation.isError && (
                                                              <div
                                                                className="workspace-message error-state"
                                                                role="alert"
                                                              >
                                                                <AlertTriangle size={20} />
                                                                <div>
                                                                  <h3>Archive integrity check failed</h3>
                                                                  <p>
                                                                    The archive was not downloaded because
                                                                    its evidence did not match.
                                                                  </p>
                                                                </div>
                                                              </div>
                                                            )}
                                                            {(identity?.subject_id ===
                                                              builderCandidateHandoffMutation.data
                                                                .data.custodied_by ||
                                                              identity?.subject_id ===
                                                                builderCandidateHandoffMutation.data
                                                                  .data.domain_reviewed_by ||
                                                              identity?.subject_id ===
                                                                builderCandidateHandoffMutation.data
                                                                  .data.security_reviewed_by ||
                                                              identity?.subject_id ===
                                                                builderCandidateHandoffMutation.data
                                                                  .data.lab_operated_by) &&
                                                              !builderPackageAcquisitionMutation.data && (
                                                                <div
                                                                  className="workspace-message mcp-builder-security-sod"
                                                                  role="status"
                                                                >
                                                                  <UserX size={20} />
                                                                  <div>
                                                                    <h3>
                                                                      Independent registry intake required
                                                                    </h3>
                                                                    <p>
                                                                      Builder custodians, reviewers, and the
                                                                      lab operator cannot acquire this package.
                                                                      Continue with a different authorized
                                                                      intake session.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                            {identity?.subject_id !==
                                                              builderCandidateHandoffMutation.data.data
                                                                .custodied_by &&
                                                              identity?.subject_id !==
                                                                builderCandidateHandoffMutation.data.data
                                                                  .domain_reviewed_by &&
                                                              identity?.subject_id !==
                                                                builderCandidateHandoffMutation.data.data
                                                                  .security_reviewed_by &&
                                                              identity?.subject_id !==
                                                                builderCandidateHandoffMutation.data.data
                                                                  .lab_operated_by &&
                                                              !builderPackageAcquisitionMutation.data && (
                                                              <div className="mcp-builder-candidate-handoff">
                                                                <div className="mcp-builder-generation-summary">
                                                                  <div>
                                                                    <p className="eyebrow">
                                                                      CONNECTOR QUARANTINE INTAKE
                                                                    </p>
                                                                    <h3>Transfer package custody</h3>
                                                                    <p>
                                                                      Preserve the exact archive in the
                                                                      separate connector quarantine. This is
                                                                      acquisition evidence, not registry
                                                                      validation or approval.
                                                                    </p>
                                                                  </div>
                                                                  <span className="state-badge pending">
                                                                    <Archive size={14} /> awaiting intake
                                                                  </span>
                                                                </div>
                                                                <label className="mcp-builder-check">
                                                                  <input
                                                                    type="checkbox"
                                                                    checked={
                                                                      builderPackageAcquisitionAcknowledged
                                                                    }
                                                                    onChange={(event) =>
                                                                      setBuilderPackageAcquisitionAcknowledged(
                                                                        event.target.checked,
                                                                      )
                                                                    }
                                                                  />
                                                                  I am the independent registry intake
                                                                  operator. I understand the package remains
                                                                  unsigned, unattested, and quarantined.
                                                                </label>
                                                                <button
                                                                  className="run-check-button mcp-builder-submit"
                                                                  type="button"
                                                                  disabled={
                                                                    !builderPackageAcquisitionAcknowledged ||
                                                                    builderPackageAcquisitionMutation.isPending
                                                                  }
                                                                  onClick={() =>
                                                                    builderPackageAcquisitionMutation.mutate(
                                                                      builderCandidateHandoffMutation.data.data,
                                                                    )
                                                                  }
                                                                >
                                                                  {builderPackageAcquisitionMutation.isPending ? (
                                                                    <RefreshCw className="spin" size={16} />
                                                                  ) : (
                                                                    <Archive size={16} />
                                                                  )}
                                                                  Acquire into connector quarantine
                                                                </button>
                                                              </div>
                                                              )}
                                                            {builderPackageAcquisitionMutation.isError && (
                                                              <div
                                                                className="workspace-message error-state"
                                                                role="alert"
                                                              >
                                                                <AlertTriangle size={20} />
                                                                <div>
                                                                  <h3>Package acquisition rejected</h3>
                                                                  <p>
                                                                    Custody separation, source integrity, or
                                                                    connector quarantine policy did not pass.
                                                                  </p>
                                                                </div>
                                                              </div>
                                                            )}
                                                            {builderPackageAcquisitionMutation.data?.data && (
                                                              <>
                                                              <div className="mcp-builder-acquisition-result">
                                                                <div className="mcp-builder-generation-summary">
                                                                  <div>
                                                                    <p className="eyebrow">
                                                                      IMMUTABLE ACQUISITION RECEIPT
                                                                    </p>
                                                                    <strong>
                                                                      {
                                                                        builderPackageAcquisitionMutation.data
                                                                          .data.acquisition_id
                                                                      }
                                                                    </strong>
                                                                    <code>
                                                                      {
                                                                        builderPackageAcquisitionMutation.data
                                                                          .data.package_digest
                                                                      }
                                                                    </code>
                                                                  </div>
                                                                  <span className="state-badge pending">
                                                                    <LockKeyhole size={14} /> quarantined
                                                                  </span>
                                                                </div>
                                                                <div className="mcp-builder-facts">
                                                                  <div>
                                                                    <span>Integrity</span>
                                                                    <strong>Verified</strong>
                                                                  </div>
                                                                  <div>
                                                                    <span>Signature</span>
                                                                    <strong>Unsigned</strong>
                                                                  </div>
                                                                  <div>
                                                                    <span>Publisher</span>
                                                                    <strong>Unattested</strong>
                                                                  </div>
                                                                  <div>
                                                                    <span>Registry validation</span>
                                                                    <strong>Not run</strong>
                                                                  </div>
                                                                </div>
                                                                <div className="mcp-builder-limitations">
                                                                  <strong>Acquisition boundaries</strong>
                                                                  <ul>
                                                                    {builderPackageAcquisitionMutation.data.data.limitations.map(
                                                                      (limitation) => (
                                                                        <li key={limitation}>{limitation}</li>
                                                                      ),
                                                                    )}
                                                                  </ul>
                                                                </div>
                                                                <div className="mcp-builder-boundary">
                                                                  <LockKeyhole size={18} />
                                                                  <p>
                                                                    No signing, attestation, validation,
                                                                    registration, approval, installation,
                                                                    enablement, runtime trust, execution, or
                                                                    infrastructure mutation authority was
                                                                    granted.
                                                                  </p>
                                                                </div>
                                                              </div>
                                                              {!builderPackageValidationSeparated &&
                                                                !builderPackageValidationMutation.data && (
                                                                  <div
                                                                    className="workspace-message mcp-builder-security-sod"
                                                                    role="status"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent package validator required
                                                                      </h3>
                                                                      <p>
                                                                        The acquisition operator and prior
                                                                        package custodians or reviewers cannot
                                                                        validate this intake. Continue with a
                                                                        different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderPackageValidationSeparated &&
                                                                !builderPackageValidationMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          GOVERNED VALIDATION INTAKE
                                                                        </p>
                                                                        <h3>Validate manifest and schemas</h3>
                                                                        <p>
                                                                          Inspect the exact quarantined archive
                                                                          and produce a bounded intake report.
                                                                        </p>
                                                                      </div>
                                                                      <span className="state-badge pending">
                                                                        <PackageCheck size={14} /> awaiting
                                                                        validation
                                                                      </span>
                                                                    </div>
                                                                    <label className="mcp-builder-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={
                                                                          builderPackageValidationAcknowledged
                                                                        }
                                                                        onChange={(event) =>
                                                                          setBuilderPackageValidationAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      I am the independent package validator. I
                                                                      understand this checks source, archive,
                                                                      manifest, and schema contracts only.
                                                                    </label>
                                                                    <button
                                                                      className="run-check-button mcp-builder-submit"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderPackageValidationAcknowledged ||
                                                                        builderPackageValidationMutation.isPending
                                                                      }
                                                                      onClick={() =>
                                                                        builderPackageValidationMutation.mutate(
                                                                          builderPackageAcquisitionMutation.data
                                                                            .data,
                                                                        )
                                                                      }
                                                                    >
                                                                      {builderPackageValidationMutation.isPending ? (
                                                                        <RefreshCw className="spin" size={16} />
                                                                      ) : (
                                                                        <PackageCheck size={16} />
                                                                      )}
                                                                      Run package intake validation
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderPackageValidationMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Package validation rejected</h3>
                                                                    <p>
                                                                      Source integrity, archive structure,
                                                                      separation of duties, or validation policy
                                                                      did not pass.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderPackageValidationMutation.data?.data && (
                                                                <section className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE VALIDATION REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderPackageValidationMutation.data
                                                                            .data.validation_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderPackageValidationMutation.data
                                                                            .data.canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderPackageValidationMutation.data.data
                                                                          .outcome === "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderPackageValidationMutation.data.data
                                                                        .outcome === "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderPackageValidationMutation.data.data
                                                                          .outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Source integrity</span>
                                                                      <strong>Accepted</strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Manifest</span>
                                                                      <strong>
                                                                        {builderPackageValidationMutation.data.data
                                                                          .manifest_digest
                                                                          ? "Recorded"
                                                                          : "Failed"}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Schemas</span>
                                                                      <strong>
                                                                        {
                                                                          builderPackageValidationMutation.data
                                                                            .data.schema_evidence.length
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Lifecycle</span>
                                                                      <strong>Validating</strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderPackageValidationMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
                                                                          {check.state === "passed" ? (
                                                                            <CheckCircle2 size={16} />
                                                                          ) : (
                                                                            <AlertTriangle size={16} />
                                                                          )}
                                                                          <div>
                                                                            <strong>{check.code}</strong>
                                                                            <p>{check.summary}</p>
                                                                            {check.evidence_paths.length > 0 && (
                                                                              <small>
                                                                                {check.evidence_paths.join(
                                                                                  " · ",
                                                                                )}
                                                                              </small>
                                                                            )}
                                                                          </div>
                                                                          <span>{check.state}</span>
                                                                        </article>
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Validation boundaries</strong>
                                                                    <ul>
                                                                      {builderPackageValidationMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                  <div className="mcp-builder-boundary">
                                                                    <LockKeyhole size={18} />
                                                                    <p>
                                                                      Dependency, vulnerability, malware,
                                                                      secret, license, code, contract, runner,
                                                                      and lab checks remain incomplete. No
                                                                      registration, installation, trust, or
                                                                      execution authority was granted.
                                                                    </p>
                                                                  </div>
                                                                </section>
                                                              )}
                                                              {builderPackageValidationMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderPackageInventorySeparated &&
                                                                !builderPackageInventoryMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>Independent inventory required</h3>
                                                                      <p>
                                                                        The validator and prior package actors
                                                                        cannot inventory this package. Continue
                                                                        with a different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderPackageValidationMutation.data?.data
                                                                .outcome === "passed" &&
                                                                builderPackageInventorySeparated &&
                                                                !builderPackageInventoryMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          SUPPLY-CHAIN INVENTORY
                                                                        </p>
                                                                        <h3>Inventory content and dependencies</h3>
                                                                        <p>
                                                                          Classify every archive entry and
                                                                          normalize declared dependencies without
                                                                          installing or executing the package.
                                                                        </p>
                                                                      </div>
                                                                      <span className="state-badge pending">
                                                                        <FileCheck2 size={14} /> awaiting inventory
                                                                      </span>
                                                                    </div>
                                                                    <label className="mcp-builder-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={
                                                                          builderPackageInventoryAcknowledged
                                                                        }
                                                                        onChange={(event) =>
                                                                          setBuilderPackageInventoryAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      I am the independent supply-chain inventory
                                                                      operator. I understand no package content
                                                                      will be installed, imported, or executed.
                                                                    </label>
                                                                    <button
                                                                      className="run-check-button mcp-builder-submit"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderPackageInventoryAcknowledged ||
                                                                        builderPackageInventoryMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const validation =
                                                                          builderPackageValidationMutation.data
                                                                            ?.data;
                                                                        if (validation) {
                                                                          builderPackageInventoryMutation.mutate(
                                                                            validation,
                                                                          );
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderPackageInventoryMutation.isPending ? (
                                                                        <RefreshCw className="spin" size={16} />
                                                                      ) : (
                                                                        <FileCheck2 size={16} />
                                                                      )}
                                                                      Create supply-chain inventory
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderPackageInventoryMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Package inventory rejected</h3>
                                                                    <p>
                                                                      Exact source evidence, package content,
                                                                      dependency metadata, or separation of
                                                                      duties did not pass.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderPackageInventoryMutation.data?.data && (
                                                                <section className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE SUPPLY-CHAIN INVENTORY
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderPackageInventoryMutation.data
                                                                            .data.inventory_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderPackageInventoryMutation.data
                                                                            .data.canonical_digest
                                                                        }
                                                                      </code>
                                                                      <small>
                                                                        Source validation: <code>
                                                                          {
                                                                            builderPackageInventoryMutation.data
                                                                              .data.source_validation_digest
                                                                          }
                                                                        </code>
                                                                      </small>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderPackageInventoryMutation.data.data
                                                                          .outcome === "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderPackageInventoryMutation.data.data
                                                                        .outcome === "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderPackageInventoryMutation.data.data
                                                                          .outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Package entries</span>
                                                                      <strong>
                                                                        {
                                                                          builderPackageInventoryMutation.data
                                                                            .data.files.length
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Build dependencies</span>
                                                                      <strong>
                                                                        {
                                                                          builderPackageInventoryMutation.data
                                                                            .data.build_dependency_count
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Runtime dependencies</span>
                                                                      <strong>
                                                                        {
                                                                          builderPackageInventoryMutation.data
                                                                            .data.runtime_dependency_count
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Dependency lock</span>
                                                                      <strong>Not present</strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Content classes</strong>
                                                                    <p>
                                                                      {Array.from(
                                                                        new Set(
                                                                          builderPackageInventoryMutation.data.data.files.map(
                                                                            (file) => file.content_class,
                                                                          ),
                                                                        ),
                                                                      ).join(", ")}
                                                                    </p>
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Declared dependencies</strong>
                                                                    {builderPackageInventoryMutation.data.data
                                                                      .dependencies.length > 0 ? (
                                                                      <ul>
                                                                        {builderPackageInventoryMutation.data.data.dependencies.map(
                                                                          (dependency) => (
                                                                            <li
                                                                              key={`${dependency.kind}:${dependency.name}`}
                                                                            >
                                                                              {dependency.kind}: {dependency.name}
                                                                              {dependency.version_constraint}
                                                                            </li>
                                                                          ),
                                                                        )}
                                                                      </ul>
                                                                    ) : (
                                                                      <p>No direct dependencies declared.</p>
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderPackageInventoryMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Inventory boundaries</strong>
                                                                    <ul>
                                                                      {builderPackageInventoryMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                  <div className="mcp-builder-boundary">
                                                                    <LockKeyhole size={18} />
                                                                    <p>
                                                                      Vulnerability, malware, secret, prohibited
                                                                      content, license, code, contract, runner,
                                                                      and lab checks remain incomplete. No trust,
                                                                      installation, execution, or deployment
                                                                      authority was granted.
                                                                    </p>
                                                                  </div>
                                                                  {builderContentPolicyScanMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderSchemaSemanticsSeparated &&
                                                                    !builderSchemaSemanticsMutation.data && (
                                                                      <div
                                                                        className="workspace-message warning-state"
                                                                        role="status"
                                                                      >
                                                                        <UserX size={20} />
                                                                        <div>
                                                                          <h3>
                                                                            Independent schema validator required
                                                                          </h3>
                                                                          <p>
                                                                            Sign in with an MFA identity that did
                                                                            not perform Builder, custody, intake,
                                                                            inventory, or content scanning.
                                                                          </p>
                                                                        </div>
                                                                      </div>
                                                                    )}
                                                                  {builderContentPolicyScanMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    builderSchemaSemanticsSeparated &&
                                                                    !builderSchemaSemanticsMutation.data && (
                                                                      <section className="mcp-builder-handoff-action">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            VALIDATION PIPELINE STEP 5
                                                                          </p>
                                                                          <strong>
                                                                            Validate schema semantics
                                                                          </strong>
                                                                          <p>
                                                                            Check closed, bounded configuration
                                                                            and capability contracts without
                                                                            resolving references or executing code.
                                                                          </p>
                                                                        </div>
                                                                        <label className="confirmation-row">
                                                                          <input
                                                                            type="checkbox"
                                                                            checked={
                                                                              builderSchemaSemanticsAcknowledged
                                                                            }
                                                                            onChange={(event) =>
                                                                              setBuilderSchemaSemanticsAcknowledged(
                                                                                event.target.checked,
                                                                              )
                                                                            }
                                                                          />
                                                                          I am the independent schema validator. I
                                                                          understand draft contracts may block
                                                                          promotion without changing the package.
                                                                        </label>
                                                                        <button
                                                                          className="run-check-button mcp-builder-submit"
                                                                          type="button"
                                                                          disabled={
                                                                            !builderSchemaSemanticsAcknowledged ||
                                                                            builderSchemaSemanticsMutation.isPending
                                                                          }
                                                                          onClick={() => {
                                                                            const scan =
                                                                              builderContentPolicyScanMutation.data
                                                                                ?.data;
                                                                            if (scan) {
                                                                              builderSchemaSemanticsMutation.mutate(
                                                                                scan,
                                                                              );
                                                                            }
                                                                          }}
                                                                        >
                                                                          {builderSchemaSemanticsMutation.isPending ? (
                                                                            <RefreshCw
                                                                              className="spin"
                                                                              size={16}
                                                                            />
                                                                          ) : (
                                                                            <FileCheck2 size={16} />
                                                                          )}
                                                                          Validate schema semantics
                                                                        </button>
                                                                      </section>
                                                                    )}
                                                                  {builderSchemaSemanticsMutation.isError && (
                                                                    <div
                                                                      className="workspace-message error-state"
                                                                      role="alert"
                                                                    >
                                                                      <AlertTriangle size={20} />
                                                                      <div>
                                                                        <h3>Schema validation unavailable</h3>
                                                                        <p>
                                                                          Exact lineage, package bytes,
                                                                          authorization, or separation of duties did
                                                                          not pass.
                                                                        </p>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderSchemaSemanticsMutation.data?.data && (
                                                                    <div className="mcp-builder-validation">
                                                                      <div className="section-heading">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            IMMUTABLE SCHEMA SEMANTICS REPORT
                                                                          </p>
                                                                          <strong>
                                                                            {
                                                                              builderSchemaSemanticsMutation.data
                                                                                .data.validation_id
                                                                            }
                                                                          </strong>
                                                                          <code>
                                                                            {
                                                                              builderSchemaSemanticsMutation.data
                                                                                .data.canonical_digest
                                                                            }
                                                                          </code>
                                                                        </div>
                                                                        <span
                                                                          className={`state-badge ${
                                                                            builderSchemaSemanticsMutation.data.data
                                                                              .outcome === "passed"
                                                                              ? "healthy"
                                                                              : "critical"
                                                                          }`}
                                                                        >
                                                                          {builderSchemaSemanticsMutation.data.data
                                                                            .outcome === "passed" ? (
                                                                            <CheckCircle2 size={14} />
                                                                          ) : (
                                                                            <AlertTriangle size={14} />
                                                                          )}
                                                                          {
                                                                            builderSchemaSemanticsMutation.data.data
                                                                              .outcome
                                                                          }
                                                                        </span>
                                                                      </div>
                                                                      <div className="mcp-builder-facts">
                                                                        <div>
                                                                          <span>Schemas</span>
                                                                          <strong>
                                                                            {
                                                                              builderSchemaSemanticsMutation.data
                                                                                .data.schemas.length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Findings</span>
                                                                          <strong>
                                                                            {
                                                                              builderSchemaSemanticsMutation.data
                                                                                .data.findings.length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Closed contracts</span>
                                                                          <strong>
                                                                            {
                                                                              builderSchemaSemanticsMutation.data.data.schemas.filter(
                                                                                (schema) => schema.closed_object,
                                                                              ).length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Promotion</span>
                                                                          <strong>
                                                                            {builderSchemaSemanticsMutation.data.data
                                                                              .promotion_blocked
                                                                              ? "Blocked"
                                                                              : "Not blocked"}
                                                                          </strong>
                                                                        </div>
                                                                      </div>
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderSchemaSemanticsMutation.data.data.schemas.map(
                                                                          (schema) => (
                                                                            <article
                                                                              key={schema.digest}
                                                                              data-state={
                                                                                schema.semantically_complete
                                                                                  ? "passed"
                                                                                  : "failed"
                                                                              }
                                                                            >
                                                                              {schema.semantically_complete ? (
                                                                                <CheckCircle2 size={16} />
                                                                              ) : (
                                                                                <AlertTriangle size={16} />
                                                                              )}
                                                                              <div>
                                                                                <strong>
                                                                                  {schema.relative_path}
                                                                                </strong>
                                                                                <p>
                                                                                  {schema.property_count} properties,
                                                                                  {" "}
                                                                                  {schema.required_count} required
                                                                                </p>
                                                                              </div>
                                                                              <span>{schema.purpose}</span>
                                                                            </article>
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      {builderSchemaSemanticsMutation.data.data
                                                                        .findings.length > 0 && (
                                                                        <div className="mcp-builder-validation-checks">
                                                                          {builderSchemaSemanticsMutation.data.data.findings.map(
                                                                            (finding) => (
                                                                              <article
                                                                                key={
                                                                                  finding.evidence_fingerprint
                                                                                }
                                                                                data-state="failed"
                                                                              >
                                                                                <AlertTriangle size={16} />
                                                                                <div>
                                                                                  <strong>
                                                                                    {finding.rule_code}
                                                                                  </strong>
                                                                                  <p>{finding.summary}</p>
                                                                                  <small>
                                                                                    {finding.relative_path}
                                                                                    {finding.json_pointer}
                                                                                  </small>
                                                                                </div>
                                                                                <span>{finding.kind}</span>
                                                                              </article>
                                                                            ),
                                                                          )}
                                                                        </div>
                                                                      )}
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderSchemaSemanticsMutation.data.data.checks.map(
                                                                          (check) => (
                                                                            <article
                                                                              key={check.code}
                                                                              data-state={check.state}
                                                                            >
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
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      <div className="mcp-builder-limitations">
                                                                        <strong>Schema boundaries</strong>
                                                                        <ul>
                                                                          {builderSchemaSemanticsMutation.data.data.limitations.map(
                                                                            (limitation) => (
                                                                              <li key={limitation}>
                                                                                {limitation}
                                                                              </li>
                                                                            ),
                                                                          )}
                                                                        </ul>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderSchemaSemanticsMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderAuthorityBehaviorSeparated &&
                                                                    !builderAuthorityBehaviorMutation.data && (
                                                                      <div
                                                                        className="workspace-message warning-state"
                                                                        role="status"
                                                                      >
                                                                        <UserX size={20} />
                                                                        <div>
                                                                          <h3>
                                                                            Independent behavior validator required
                                                                          </h3>
                                                                          <p>
                                                                            The schema validator and all earlier
                                                                            package actors remain separated from
                                                                            implementation behavior review.
                                                                          </p>
                                                                        </div>
                                                                      </div>
                                                                    )}
                                                                  {builderSchemaSemanticsMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    builderAuthorityBehaviorSeparated &&
                                                                    !builderAuthorityBehaviorMutation.data && (
                                                                      <section className="mcp-builder-handoff-action">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            VALIDATION PIPELINE STEP 6
                                                                          </p>
                                                                          <strong>
                                                                            Compare declared authority
                                                                          </strong>
                                                                          <p>
                                                                            Inspect bounded Python AST evidence
                                                                            without importing, compiling, or
                                                                            executing connector code.
                                                                          </p>
                                                                        </div>
                                                                        <label className="confirmation-row">
                                                                          <input
                                                                            type="checkbox"
                                                                            checked={
                                                                              builderAuthorityBehaviorAcknowledged
                                                                            }
                                                                            onChange={(event) =>
                                                                              setBuilderAuthorityBehaviorAcknowledged(
                                                                                event.target.checked,
                                                                              )
                                                                            }
                                                                          />
                                                                          I am the independent behavior validator. I
                                                                          understand static evidence is limited and
                                                                          grants no runtime authority.
                                                                        </label>
                                                                        <button
                                                                          className="run-check-button mcp-builder-submit"
                                                                          type="button"
                                                                          disabled={
                                                                            !builderAuthorityBehaviorAcknowledged ||
                                                                            builderAuthorityBehaviorMutation.isPending
                                                                          }
                                                                          onClick={() => {
                                                                            const report =
                                                                              builderSchemaSemanticsMutation.data
                                                                                ?.data;
                                                                            if (report) {
                                                                              builderAuthorityBehaviorMutation.mutate(
                                                                                report,
                                                                              );
                                                                            }
                                                                          }}
                                                                        >
                                                                          {builderAuthorityBehaviorMutation.isPending ? (
                                                                            <RefreshCw
                                                                              className="spin"
                                                                              size={16}
                                                                            />
                                                                          ) : (
                                                                            <ScanSearch size={16} />
                                                                          )}
                                                                          Compare authority and behavior
                                                                        </button>
                                                                      </section>
                                                                    )}
                                                                  {builderAuthorityBehaviorMutation.isError && (
                                                                    <div
                                                                      className="workspace-message error-state"
                                                                      role="alert"
                                                                    >
                                                                      <AlertTriangle size={20} />
                                                                      <div>
                                                                        <h3>Behavior validation unavailable</h3>
                                                                        <p>
                                                                          Exact lineage, package bytes,
                                                                          authorization, or bounded AST analysis did
                                                                          not pass.
                                                                        </p>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderAuthorityBehaviorMutation.data?.data && (
                                                                    <div className="mcp-builder-validation">
                                                                      <div className="section-heading">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            IMMUTABLE AUTHORITY BEHAVIOR REPORT
                                                                          </p>
                                                                          <strong>
                                                                            {
                                                                              builderAuthorityBehaviorMutation.data
                                                                                .data.validation_id
                                                                            }
                                                                          </strong>
                                                                          <code>
                                                                            {
                                                                              builderAuthorityBehaviorMutation.data
                                                                                .data.canonical_digest
                                                                            }
                                                                          </code>
                                                                        </div>
                                                                        <span
                                                                          className={`state-badge ${
                                                                            builderAuthorityBehaviorMutation.data
                                                                              .data.outcome === "passed"
                                                                              ? "healthy"
                                                                              : "critical"
                                                                          }`}
                                                                        >
                                                                          {builderAuthorityBehaviorMutation.data.data
                                                                            .outcome === "passed" ? (
                                                                            <CheckCircle2 size={14} />
                                                                          ) : (
                                                                            <AlertTriangle size={14} />
                                                                          )}
                                                                          {
                                                                            builderAuthorityBehaviorMutation.data
                                                                              .data.outcome
                                                                          }
                                                                        </span>
                                                                      </div>
                                                                      <div className="mcp-builder-facts">
                                                                        <div>
                                                                          <span>Capabilities</span>
                                                                          <strong>
                                                                            {
                                                                              builderAuthorityBehaviorMutation.data
                                                                                .data.capabilities.length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Findings</span>
                                                                          <strong>
                                                                            {
                                                                              builderAuthorityBehaviorMutation.data
                                                                                .data.findings.length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Resolved</span>
                                                                          <strong>
                                                                            {
                                                                              builderAuthorityBehaviorMutation.data.data.capabilities.filter(
                                                                                (capability) =>
                                                                                  capability.statically_resolved,
                                                                              ).length
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Promotion</span>
                                                                          <strong>
                                                                            {builderAuthorityBehaviorMutation.data
                                                                              .data.promotion_blocked
                                                                              ? "Blocked"
                                                                              : "Not blocked"}
                                                                          </strong>
                                                                        </div>
                                                                      </div>
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderAuthorityBehaviorMutation.data.data.capabilities.map(
                                                                          (capability) => (
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
                                                                              {capability.behavior_compatible &&
                                                                              capability.statically_resolved ? (
                                                                                <CheckCircle2 size={16} />
                                                                              ) : (
                                                                                <AlertTriangle size={16} />
                                                                              )}
                                                                              <div>
                                                                                <strong>
                                                                                  {
                                                                                    capability.capability_id
                                                                                  }
                                                                                </strong>
                                                                                <p>
                                                                                  {capability.observed_categories.join(
                                                                                    ", ",
                                                                                  )}
                                                                                </p>
                                                                                <small>
                                                                                  {
                                                                                    capability.required_permission
                                                                                  }
                                                                                </small>
                                                                              </div>
                                                                              <span>
                                                                                {
                                                                                  capability.declared_class
                                                                                }
                                                                              </span>
                                                                            </article>
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      {builderAuthorityBehaviorMutation.data.data
                                                                        .findings.length > 0 && (
                                                                        <div className="mcp-builder-validation-checks">
                                                                          {builderAuthorityBehaviorMutation.data.data.findings.map(
                                                                            (finding) => (
                                                                              <article
                                                                                key={
                                                                                  finding.evidence_fingerprint
                                                                                }
                                                                                data-state="failed"
                                                                              >
                                                                                <AlertTriangle size={16} />
                                                                                <div>
                                                                                  <strong>
                                                                                    {finding.rule_code}
                                                                                  </strong>
                                                                                  <p>{finding.summary}</p>
                                                                                  <small>
                                                                                    {finding.relative_path}
                                                                                    {finding.line_number > 0
                                                                                      ? `:${finding.line_number}`
                                                                                      : ""}
                                                                                  </small>
                                                                                </div>
                                                                                <span>
                                                                                  {finding.category}
                                                                                </span>
                                                                              </article>
                                                                            ),
                                                                          )}
                                                                        </div>
                                                                      )}
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderAuthorityBehaviorMutation.data.data.checks.map(
                                                                          (check) => (
                                                                            <article
                                                                              key={check.code}
                                                                              data-state={check.state}
                                                                            >
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
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      <div className="mcp-builder-limitations">
                                                                        <strong>Behavior boundaries</strong>
                                                                        <ul>
                                                                          {builderAuthorityBehaviorMutation.data.data.limitations.map(
                                                                            (limitation) => (
                                                                              <li key={limitation}>
                                                                                {limitation}
                                                                              </li>
                                                                            ),
                                                                          )}
                                                                        </ul>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderAuthorityBehaviorMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderStaticDependencySeparated &&
                                                                    !builderStaticDependencyMutation.data && (
                                                                      <div
                                                                        className="workspace-message warning-state"
                                                                        role="status"
                                                                      >
                                                                        <UserX size={20} />
                                                                        <div>
                                                                          <h3>
                                                                            Independent static analyst required
                                                                          </h3>
                                                                          <p>
                                                                            Prior package validators cannot analyze
                                                                            this stage. Continue with a different
                                                                            authorized session.
                                                                          </p>
                                                                        </div>
                                                                      </div>
                                                                    )}
                                                                  {builderAuthorityBehaviorMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    builderStaticDependencySeparated &&
                                                                    !builderStaticDependencyMutation.data && (
                                                                      <section className="mcp-builder-review-panel">
                                                                        <div className="section-heading">
                                                                          <div>
                                                                            <p className="eyebrow">
                                                                              STATIC AND DEPENDENCY ANALYSIS
                                                                            </p>
                                                                            <h3>
                                                                              Inspect source structure and dependency
                                                                              hygiene
                                                                            </h3>
                                                                            <p>
                                                                              Offline structural evidence only. No
                                                                              package code or dependency is loaded.
                                                                            </p>
                                                                          </div>
                                                                          <span className="state-badge neutral">
                                                                            <ScanSearch size={14} /> No execution
                                                                          </span>
                                                                        </div>
                                                                        <label className="mcp-builder-confirmation">
                                                                          <input
                                                                            type="checkbox"
                                                                            checked={
                                                                              builderStaticDependencyAcknowledged
                                                                            }
                                                                            onChange={(event) =>
                                                                              setBuilderStaticDependencyAcknowledged(
                                                                                event.target.checked,
                                                                              )
                                                                            }
                                                                          />
                                                                          I am the independent static analyst. I
                                                                          understand this does not perform
                                                                          vulnerability, malware, license, build, or
                                                                          runtime validation.
                                                                        </label>
                                                                        <button
                                                                          className="run-check-button mcp-builder-submit"
                                                                          type="button"
                                                                          disabled={
                                                                            !builderStaticDependencyAcknowledged ||
                                                                            builderStaticDependencyMutation.isPending
                                                                          }
                                                                          onClick={() => {
                                                                            const report =
                                                                              builderAuthorityBehaviorMutation.data
                                                                                ?.data;
                                                                            if (report) {
                                                                              builderStaticDependencyMutation.mutate(
                                                                                report,
                                                                              );
                                                                            }
                                                                          }}
                                                                        >
                                                                          {builderStaticDependencyMutation.isPending ? (
                                                                            <RefreshCw
                                                                              className="spin"
                                                                              size={16}
                                                                            />
                                                                          ) : (
                                                                            <ScanSearch size={16} />
                                                                          )}
                                                                          Analyze source and dependencies
                                                                        </button>
                                                                      </section>
                                                                    )}
                                                                  {builderStaticDependencyMutation.isError && (
                                                                    <div
                                                                      className="workspace-message error-state"
                                                                      role="alert"
                                                                    >
                                                                      <AlertTriangle size={20} />
                                                                      <div>
                                                                        <h3>Static analysis unavailable</h3>
                                                                        <p>
                                                                          Exact lineage, source structure, or
                                                                          dependency hygiene did not pass.
                                                                        </p>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderStaticDependencyMutation.data?.data && (
                                                                    <div className="mcp-builder-validation">
                                                                      <div className="section-heading">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            IMMUTABLE STATIC DEPENDENCY REPORT
                                                                          </p>
                                                                          <strong>
                                                                            {
                                                                              builderStaticDependencyMutation.data
                                                                                .data.analysis_id
                                                                            }
                                                                          </strong>
                                                                          <code>
                                                                            {
                                                                              builderStaticDependencyMutation.data
                                                                                .data.canonical_digest
                                                                            }
                                                                          </code>
                                                                        </div>
                                                                        <span
                                                                          className={`state-badge ${
                                                                            builderStaticDependencyMutation.data.data
                                                                              .outcome === "passed"
                                                                              ? "healthy"
                                                                              : "critical"
                                                                          }`}
                                                                        >
                                                                          {builderStaticDependencyMutation.data.data
                                                                            .outcome === "passed" ? (
                                                                            <CheckCircle2 size={14} />
                                                                          ) : (
                                                                            <AlertTriangle size={14} />
                                                                          )}
                                                                          {
                                                                            builderStaticDependencyMutation.data.data
                                                                              .outcome
                                                                          }
                                                                        </span>
                                                                      </div>
                                                                      <div className="mcp-builder-facts">
                                                                        <div>
                                                                          <span>Source files</span>
                                                                          <strong>
                                                                            {
                                                                              builderStaticDependencyMutation.data.data
                                                                                .source_summary.source_file_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Imports</span>
                                                                          <strong>
                                                                            {
                                                                              builderStaticDependencyMutation.data.data
                                                                                .source_summary.import_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Runtime dependencies</span>
                                                                          <strong>
                                                                            {
                                                                              builderStaticDependencyMutation.data.data
                                                                                .dependency_summary
                                                                                .runtime_dependency_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Promotion</span>
                                                                          <strong>
                                                                            {builderStaticDependencyMutation.data.data
                                                                              .promotion_blocked
                                                                              ? "Blocked"
                                                                              : "Not blocked"}
                                                                          </strong>
                                                                        </div>
                                                                      </div>
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderStaticDependencyMutation.data.data.checks.map(
                                                                          (check) => (
                                                                            <article
                                                                              key={check.code}
                                                                              data-state={check.state}
                                                                            >
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
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      {builderStaticDependencyMutation.data.data
                                                                        .findings.length > 0 && (
                                                                        <div className="mcp-builder-validation-checks">
                                                                          {builderStaticDependencyMutation.data.data.findings.map(
                                                                            (finding) => (
                                                                              <article
                                                                                key={
                                                                                  finding.evidence_fingerprint
                                                                                }
                                                                                data-state="failed"
                                                                              >
                                                                                <AlertTriangle size={16} />
                                                                                <div>
                                                                                  <strong>
                                                                                    {finding.rule_code}
                                                                                  </strong>
                                                                                  <p>{finding.summary}</p>
                                                                                  <code>
                                                                                    {finding.relative_path}:
                                                                                    {finding.line_number}
                                                                                  </code>
                                                                                </div>
                                                                                <span>
                                                                                  {finding.category}
                                                                                </span>
                                                                              </article>
                                                                            ),
                                                                          )}
                                                                        </div>
                                                                      )}
                                                                      <div className="mcp-builder-limitations">
                                                                        <strong>Static analysis boundaries</strong>
                                                                        <ul>
                                                                          {builderStaticDependencyMutation.data.data.limitations.map(
                                                                            (limitation) => (
                                                                              <li key={limitation}>
                                                                                {limitation}
                                                                              </li>
                                                                            ),
                                                                          )}
                                                                        </ul>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderStaticDependencyMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderVulnerabilitySeparated &&
                                                                    !builderVulnerabilityMutation.data && (
                                                                      <div
                                                                        className="workspace-message warning-state"
                                                                        role="status"
                                                                      >
                                                                        <UserX size={20} />
                                                                        <div>
                                                                          <h3>
                                                                            Independent vulnerability analyst
                                                                            required
                                                                          </h3>
                                                                          <p>
                                                                            Prior package and static-analysis actors
                                                                            cannot perform this stage. Continue with
                                                                            a different authorized session.
                                                                          </p>
                                                                        </div>
                                                                      </div>
                                                                    )}
                                                                  {builderStaticDependencyMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    builderVulnerabilitySeparated &&
                                                                    !builderVulnerabilityMutation.data && (
                                                                      <section className="mcp-builder-review-panel">
                                                                        <div className="section-heading">
                                                                          <div>
                                                                            <p className="eyebrow">
                                                                              DEPENDENCY VULNERABILITY ANALYSIS
                                                                            </p>
                                                                            <h3>
                                                                              Compare represented dependencies to
                                                                              trusted advisories
                                                                            </h3>
                                                                            <p>
                                                                              Offline evidence against one immutable,
                                                                              signed, and platform-selected snapshot.
                                                                            </p>
                                                                          </div>
                                                                          <span className="state-badge neutral">
                                                                            <ShieldCheck size={14} /> No network
                                                                          </span>
                                                                        </div>
                                                                        <label className="mcp-builder-confirmation">
                                                                          <input
                                                                            type="checkbox"
                                                                            checked={
                                                                              builderVulnerabilityAcknowledged
                                                                            }
                                                                            onChange={(event) =>
                                                                              setBuilderVulnerabilityAcknowledged(
                                                                                event.target.checked,
                                                                              )
                                                                            }
                                                                          />
                                                                          I am the independent vulnerability analyst.
                                                                          I understand this report is time-bound and
                                                                          does not perform malware, license, build, or
                                                                          runtime validation.
                                                                        </label>
                                                                        <button
                                                                          className="run-check-button mcp-builder-submit"
                                                                          type="button"
                                                                          disabled={
                                                                            !builderVulnerabilityAcknowledged ||
                                                                            builderVulnerabilityMutation.isPending
                                                                          }
                                                                          onClick={() => {
                                                                            const report =
                                                                              builderStaticDependencyMutation.data
                                                                                ?.data;
                                                                            if (report) {
                                                                              builderVulnerabilityMutation.mutate(
                                                                                report,
                                                                              );
                                                                            }
                                                                          }}
                                                                        >
                                                                          {builderVulnerabilityMutation.isPending ? (
                                                                            <RefreshCw
                                                                              className="spin"
                                                                              size={16}
                                                                            />
                                                                          ) : (
                                                                            <ShieldCheck size={16} />
                                                                          )}
                                                                          Analyze known vulnerabilities
                                                                        </button>
                                                                      </section>
                                                                    )}
                                                                  {builderVulnerabilityMutation.isError && (
                                                                    <div
                                                                      className="workspace-message error-state"
                                                                      role="alert"
                                                                    >
                                                                      <AlertTriangle size={20} />
                                                                      <div>
                                                                        <h3>Vulnerability analysis unavailable</h3>
                                                                        <p>
                                                                          Exact lineage, advisory trust, freshness,
                                                                          coverage, or subject reconciliation did not
                                                                          pass.
                                                                        </p>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderVulnerabilityMutation.data?.data && (
                                                                    <div className="mcp-builder-validation">
                                                                      <div className="section-heading">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            IMMUTABLE VULNERABILITY REPORT
                                                                          </p>
                                                                          <strong>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .analysis_id
                                                                            }
                                                                          </strong>
                                                                          <code>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .canonical_digest
                                                                            }
                                                                          </code>
                                                                        </div>
                                                                        <span
                                                                          className={`state-badge ${
                                                                            builderVulnerabilityMutation.data.data
                                                                              .outcome === "passed"
                                                                              ? "healthy"
                                                                              : "critical"
                                                                          }`}
                                                                        >
                                                                          {builderVulnerabilityMutation.data.data
                                                                            .outcome === "passed" ? (
                                                                            <CheckCircle2 size={14} />
                                                                          ) : (
                                                                            <AlertTriangle size={14} />
                                                                          )}
                                                                          {
                                                                            builderVulnerabilityMutation.data.data
                                                                              .outcome
                                                                          }
                                                                        </span>
                                                                      </div>
                                                                      <div className="mcp-builder-facts">
                                                                        <div>
                                                                          <span>Advisory snapshot</span>
                                                                          <strong>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .advisory_snapshot.snapshot_version
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Dataset status</span>
                                                                          <strong>
                                                                            {builderVulnerabilityMutation.data.data
                                                                              .advisory_snapshot.fresh &&
                                                                            builderVulnerabilityMutation.data.data
                                                                              .advisory_snapshot.coverage_complete
                                                                              ? "Current and complete"
                                                                              : "Blocking gap"}
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Scanned subjects</span>
                                                                          <strong>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .subject_summary.scanned_subject_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Known matches</span>
                                                                          <strong>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .subject_summary.advisory_match_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Critical / high</span>
                                                                          <strong>
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .subject_summary.critical_count
                                                                            }
                                                                            {" / "}
                                                                            {
                                                                              builderVulnerabilityMutation.data.data
                                                                                .subject_summary.high_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Promotion</span>
                                                                          <strong>
                                                                            {builderVulnerabilityMutation.data.data
                                                                              .promotion_blocked
                                                                              ? "Blocked"
                                                                              : "Not blocked"}
                                                                          </strong>
                                                                        </div>
                                                                      </div>
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderVulnerabilityMutation.data.data.checks.map(
                                                                          (check) => (
                                                                            <article
                                                                              key={check.code}
                                                                              data-state={check.state}
                                                                            >
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
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      {builderVulnerabilityMutation.data.data.findings
                                                                        .length > 0 && (
                                                                        <div className="mcp-builder-validation-checks">
                                                                          {builderVulnerabilityMutation.data.data.findings.map(
                                                                            (finding) => (
                                                                              <article
                                                                                key={`${finding.advisory_id}:${finding.subject_fingerprint}`}
                                                                                data-state="failed"
                                                                              >
                                                                                <AlertTriangle size={16} />
                                                                                <div>
                                                                                  <strong>
                                                                                    {
                                                                                      finding.advisory_id
                                                                                    }
                                                                                  </strong>
                                                                                  <p>{finding.summary}</p>
                                                                                  <small>
                                                                                    {
                                                                                      finding.dependency_scope
                                                                                    }
                                                                                  </small>
                                                                                </div>
                                                                                <span>
                                                                                  {finding.severity}
                                                                                </span>
                                                                              </article>
                                                                            ),
                                                                          )}
                                                                        </div>
                                                                      )}
                                                                      <div className="mcp-builder-limitations">
                                                                        <strong>Advisory boundaries</strong>
                                                                        <ul>
                                                                          {builderVulnerabilityMutation.data.data.limitations.map(
                                                                            (limitation) => (
                                                                              <li key={limitation}>
                                                                                {limitation}
                                                                              </li>
                                                                            ),
                                                                          )}
                                                                        </ul>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderVulnerabilityMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderVulnerabilityMutation.data.data
                                                                      .promotion_blocked &&
                                                                    !builderMalwareSeparated &&
                                                                    !builderMalwareMutation.data && (
                                                                      <div
                                                                        className="workspace-message warning-state"
                                                                        role="status"
                                                                      >
                                                                        <UserX size={20} />
                                                                        <div>
                                                                          <h3>
                                                                            Independent malware analyst required
                                                                          </h3>
                                                                          <p>
                                                                            Every prior package-analysis actor is
                                                                            excluded. Continue with a different
                                                                            authorized session.
                                                                          </p>
                                                                        </div>
                                                                      </div>
                                                                    )}
                                                                  {builderVulnerabilityMutation.data?.data
                                                                    .outcome === "passed" &&
                                                                    !builderVulnerabilityMutation.data.data
                                                                      .promotion_blocked &&
                                                                    builderMalwareSeparated &&
                                                                    !builderMalwareMutation.data && (
                                                                      <section className="mcp-builder-review-panel">
                                                                        <div className="section-heading">
                                                                          <div>
                                                                            <p className="eyebrow">
                                                                              KNOWN MALWARE ANALYSIS
                                                                            </p>
                                                                            <h3>
                                                                              Scan the exact package and inventory
                                                                            </h3>
                                                                            <p>
                                                                              Offline evidence against an immutable,
                                                                              signed, platform-selected definition
                                                                              snapshot.
                                                                            </p>
                                                                          </div>
                                                                          <span className="state-badge neutral">
                                                                            <ShieldCheck size={14} /> No network
                                                                          </span>
                                                                        </div>
                                                                        <label className="mcp-builder-confirmation">
                                                                          <input
                                                                            type="checkbox"
                                                                            checked={builderMalwareAcknowledged}
                                                                            onChange={(event) =>
                                                                              setBuilderMalwareAcknowledged(
                                                                                event.target.checked,
                                                                              )
                                                                            }
                                                                          />
                                                                          I am the independent malware analyst. I
                                                                          understand this is a limited known-indicator
                                                                          gate, not a guarantee that the package is
                                                                          benign.
                                                                        </label>
                                                                        <button
                                                                          className="run-check-button mcp-builder-submit"
                                                                          type="button"
                                                                          disabled={
                                                                            !builderMalwareAcknowledged ||
                                                                            builderMalwareMutation.isPending
                                                                          }
                                                                          onClick={() => {
                                                                            const report =
                                                                              builderVulnerabilityMutation.data
                                                                                ?.data;
                                                                            if (report) {
                                                                              builderMalwareMutation.mutate(report);
                                                                            }
                                                                          }}
                                                                        >
                                                                          {builderMalwareMutation.isPending ? (
                                                                            <RefreshCw
                                                                              className="spin"
                                                                              size={16}
                                                                            />
                                                                          ) : (
                                                                            <ShieldCheck size={16} />
                                                                          )}
                                                                          Scan known malware indicators
                                                                        </button>
                                                                      </section>
                                                                    )}
                                                                  {builderMalwareMutation.isError && (
                                                                    <div
                                                                      className="workspace-message error-state"
                                                                      role="alert"
                                                                    >
                                                                      <AlertTriangle size={20} />
                                                                      <div>
                                                                        <h3>Malware analysis unavailable</h3>
                                                                        <p>
                                                                          Exact lineage, definition trust, freshness,
                                                                          coverage, or archive reconciliation did not
                                                                          pass.
                                                                        </p>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                  {builderMalwareMutation.data?.data && (
                                                                    <div className="mcp-builder-validation">
                                                                      <div className="section-heading">
                                                                        <div>
                                                                          <p className="eyebrow">
                                                                            IMMUTABLE MALWARE REPORT
                                                                          </p>
                                                                          <strong>
                                                                            {
                                                                              builderMalwareMutation.data.data
                                                                                .analysis_id
                                                                            }
                                                                          </strong>
                                                                          <code>
                                                                            {
                                                                              builderMalwareMutation.data.data
                                                                                .canonical_digest
                                                                            }
                                                                          </code>
                                                                        </div>
                                                                        <span
                                                                          className={`state-badge ${
                                                                            builderMalwareMutation.data.data
                                                                              .outcome === "passed"
                                                                              ? "healthy"
                                                                              : "critical"
                                                                          }`}
                                                                        >
                                                                          {builderMalwareMutation.data.data.outcome ===
                                                                          "passed" ? (
                                                                            <CheckCircle2 size={14} />
                                                                          ) : (
                                                                            <AlertTriangle size={14} />
                                                                          )}
                                                                          {
                                                                            builderMalwareMutation.data.data.outcome
                                                                          }
                                                                        </span>
                                                                      </div>
                                                                      <div className="mcp-builder-facts">
                                                                        <div>
                                                                          <span>Definition snapshot</span>
                                                                          <strong>
                                                                            {
                                                                              builderMalwareMutation.data.data
                                                                                .definition_snapshot.snapshot_version
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Coverage</span>
                                                                          <strong>
                                                                            {builderMalwareMutation.data.data
                                                                              .definition_snapshot.fresh &&
                                                                            builderMalwareMutation.data.data
                                                                              .definition_snapshot
                                                                              .package_coverage_complete &&
                                                                            builderMalwareMutation.data.data
                                                                              .definition_snapshot
                                                                              .file_coverage_complete &&
                                                                            builderMalwareMutation.data.data
                                                                              .definition_snapshot
                                                                              .stream_coverage_complete
                                                                              ? "Current and complete"
                                                                              : "Blocking gap"}
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Scanned subjects</span>
                                                                          <strong>
                                                                            {
                                                                              builderMalwareMutation.data.data
                                                                                .subject_summary.scanned_subject_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Scanned bytes</span>
                                                                          <strong>
                                                                            {builderMalwareMutation.data.data.subject_summary.scanned_bytes.toLocaleString()}
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Known matches</span>
                                                                          <strong>
                                                                            {
                                                                              builderMalwareMutation.data.data
                                                                                .subject_summary
                                                                                .definition_match_count
                                                                            }
                                                                          </strong>
                                                                        </div>
                                                                        <div>
                                                                          <span>Promotion</span>
                                                                          <strong>
                                                                            {builderMalwareMutation.data.data
                                                                              .promotion_blocked
                                                                              ? "Blocked"
                                                                              : "Not blocked"}
                                                                          </strong>
                                                                        </div>
                                                                      </div>
                                                                      <div className="mcp-builder-validation-checks">
                                                                        {builderMalwareMutation.data.data.checks.map(
                                                                          (check) => (
                                                                            <article
                                                                              key={check.code}
                                                                              data-state={check.state}
                                                                            >
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
                                                                          ),
                                                                        )}
                                                                      </div>
                                                                      {builderMalwareMutation.data.data.findings
                                                                        .length > 0 && (
                                                                        <div className="mcp-builder-validation-checks">
                                                                          {builderMalwareMutation.data.data.findings.map(
                                                                            (finding) => (
                                                                              <article
                                                                                key={`${finding.rule_id}:${finding.subject_fingerprint}`}
                                                                                data-state="failed"
                                                                              >
                                                                                <AlertTriangle size={16} />
                                                                                <div>
                                                                                  <strong>
                                                                                    {finding.rule_id}
                                                                                  </strong>
                                                                                  <p>{finding.summary}</p>
                                                                                  <small>
                                                                                    {finding.subject_scope}
                                                                                  </small>
                                                                                </div>
                                                                                <span>
                                                                                  {finding.severity}
                                                                                </span>
                                                                              </article>
                                                                            ),
                                                                          )}
                                                                        </div>
                                                                      )}
                                                                      <div className="mcp-builder-limitations">
                                                                        <strong>Malware scan boundaries</strong>
                                                                        <ul>
                                                                          {builderMalwareMutation.data.data.limitations.map(
                                                                            (limitation) => (
                                                                              <li key={limitation}>
                                                                                {limitation}
                                                                              </li>
                                                                            ),
                                                                          )}
                                                                        </ul>
                                                                      </div>
                                                                    </div>
                                                                  )}
                                                                </section>
                                                              )}
                                                              {builderMalwareMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderMalwareMutation.data.data
                                                                  .promotion_blocked &&
                                                                !builderLicenseSeparated &&
                                                                !builderLicenseMutation.data && (
                                                                  <div
                                                                    className="workspace-message warning-state"
                                                                    role="status"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent license analyst required
                                                                      </h3>
                                                                      <p>
                                                                        Every prior package-analysis actor is
                                                                        excluded. Continue with a different
                                                                        authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderMalwareMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderMalwareMutation.data.data
                                                                  .promotion_blocked &&
                                                                builderLicenseSeparated &&
                                                                !builderLicenseMutation.data && (
                                                                  <section className="mcp-builder-review-panel">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          LICENSE POLICY ANALYSIS
                                                                        </p>
                                                                        <h3>
                                                                          Compare represented licenses to policy
                                                                        </h3>
                                                                        <p>
                                                                          Evaluate opaque package, source, and
                                                                          dependency subjects against the trusted
                                                                          internal policy snapshot.
                                                                        </p>
                                                                      </div>
                                                                      <span className="state-badge neutral">
                                                                        <Scale size={14} /> Decision support
                                                                      </span>
                                                                    </div>
                                                                    <label className="mcp-builder-confirmation">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={builderLicenseAcknowledged}
                                                                        onChange={(event) =>
                                                                          setBuilderLicenseAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      I am the independent license analyst. I
                                                                      understand this policy comparison is not
                                                                      legal advice and grants no redistribution or
                                                                      runtime authority.
                                                                    </label>
                                                                    <button
                                                                      className="run-check-button mcp-builder-submit"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderLicenseAcknowledged ||
                                                                        builderLicenseMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const report =
                                                                          builderMalwareMutation.data?.data;
                                                                        if (report) {
                                                                          builderLicenseMutation.mutate(report);
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderLicenseMutation.isPending ? (
                                                                        <RefreshCw className="spin" size={16} />
                                                                      ) : (
                                                                        <Scale size={16} />
                                                                      )}
                                                                      Analyze license policy
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderLicenseMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>License analysis unavailable</h3>
                                                                    <p>
                                                                      Exact lineage, policy trust, coverage, or
                                                                      package metadata reconciliation did not
                                                                      pass.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderLicenseMutation.data?.data && (
                                                                <div className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE LICENSE REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderLicenseMutation.data.data
                                                                            .analysis_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderLicenseMutation.data.data
                                                                            .canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderLicenseMutation.data.data.outcome ===
                                                                        "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderLicenseMutation.data.data.outcome ===
                                                                      "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderLicenseMutation.data.data.outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Policy snapshot</span>
                                                                      <strong>
                                                                        {
                                                                          builderLicenseMutation.data.data
                                                                            .policy_snapshot.snapshot_version
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Scanned subjects</span>
                                                                      <strong>
                                                                        {builderLicenseMutation.data.data.subject_summary.scanned_subject_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Permitted</span>
                                                                      <strong>
                                                                        {builderLicenseMutation.data.data.subject_summary.permitted_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Blocking subjects</span>
                                                                      <strong>
                                                                        {(
                                                                          builderLicenseMutation.data.data
                                                                            .subject_summary.review_required_count +
                                                                          builderLicenseMutation.data.data
                                                                            .subject_summary.prohibited_count +
                                                                          builderLicenseMutation.data.data
                                                                            .subject_summary.unknown_count
                                                                        ).toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderLicenseMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  {builderLicenseMutation.data.data.findings.length >
                                                                    0 && (
                                                                    <div className="mcp-builder-findings">
                                                                      {builderLicenseMutation.data.data.findings.map(
                                                                        (finding) => (
                                                                          <article
                                                                            key={`${finding.rule_id}-${finding.subject_fingerprint}`}
                                                                            data-state="failed"
                                                                          >
                                                                            <AlertTriangle size={16} />
                                                                            <div>
                                                                              <strong>
                                                                                {finding.rule_id}
                                                                              </strong>
                                                                              <p>{finding.summary}</p>
                                                                              <small>
                                                                                {finding.subject_scope} ·{" "}
                                                                                {finding.disposition}
                                                                              </small>
                                                                            </div>
                                                                            <span>
                                                                              {finding.severity}
                                                                            </span>
                                                                          </article>
                                                                        ),
                                                                      )}
                                                                    </div>
                                                                  )}
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>License policy boundaries</strong>
                                                                    <ul>
                                                                      {builderLicenseMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderLicenseMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderContractSeparated &&
                                                                !builderContractMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent contract validator required
                                                                      </h3>
                                                                      <p>
                                                                        License and prior package actors cannot
                                                                        validate this contract. Continue with a
                                                                        different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderLicenseMutation.data?.data
                                                                .outcome === "passed" &&
                                                                builderContractSeparated &&
                                                                !builderContractMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          STATIC CONTRACT VALIDATION
                                                                        </p>
                                                                        <h3>
                                                                          Validate package contract bindings
                                                                        </h3>
                                                                        <p>
                                                                          Parse the exact manifest, schemas,
                                                                          handlers, tests, and synthetic fixtures
                                                                          without importing or executing package
                                                                          code.
                                                                        </p>
                                                                      </div>
                                                                      <FileCheck2 size={24} />
                                                                    </div>
                                                                    <label className="approval-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={builderContractAcknowledged}
                                                                        onChange={(event) =>
                                                                          setBuilderContractAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      <span>
                                                                        I am the independent contract validator.
                                                                        This stage proves static consistency only
                                                                        and grants no execution authority.
                                                                      </span>
                                                                    </label>
                                                                    <button
                                                                      className="primary-button"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderContractAcknowledged ||
                                                                        builderContractMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const report =
                                                                          builderLicenseMutation.data?.data;
                                                                        if (report) {
                                                                          builderContractMutation.mutate(report);
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderContractMutation.isPending ? (
                                                                        <RefreshCw
                                                                          className="spin"
                                                                          size={16}
                                                                        />
                                                                      ) : (
                                                                        <FileCheck2 size={16} />
                                                                      )}
                                                                      Validate contracts
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderContractMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Contract validation unavailable</h3>
                                                                    <p>
                                                                      Exact lineage, archive integrity, or a
                                                                      required contract family did not reconcile.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderContractMutation.data?.data && (
                                                                <div className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE CONTRACT REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderContractMutation.data.data
                                                                            .validation_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderContractMutation.data.data
                                                                            .canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderContractMutation.data.data
                                                                          .outcome === "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderContractMutation.data.data.outcome ===
                                                                      "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderContractMutation.data.data.outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Capabilities</span>
                                                                      <strong>
                                                                        {builderContractMutation.data.data.coverage.capability_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Covered</span>
                                                                      <strong>
                                                                        {builderContractMutation.data.data.coverage.covered_capability_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Contract tests</span>
                                                                      <strong>
                                                                        {builderContractMutation.data.data.coverage.contract_test_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Orphan artifacts</span>
                                                                      <strong>
                                                                        {builderContractMutation.data.data.coverage.orphan_artifact_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderContractMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  {builderContractMutation.data.data.findings.length >
                                                                    0 && (
                                                                    <div className="mcp-builder-findings">
                                                                      {builderContractMutation.data.data.findings.map(
                                                                        (finding) => (
                                                                          <article
                                                                            key={`${finding.rule_id}-${finding.subject_fingerprint}`}
                                                                            data-state="failed"
                                                                          >
                                                                            <AlertTriangle size={16} />
                                                                            <div>
                                                                              <strong>
                                                                                {finding.rule_id}
                                                                              </strong>
                                                                              <p>{finding.summary}</p>
                                                                              <small>
                                                                                {
                                                                                  finding.artifact_scope
                                                                                }
                                                                              </small>
                                                                            </div>
                                                                            <span>
                                                                              {finding.severity}
                                                                            </span>
                                                                          </article>
                                                                        ),
                                                                      )}
                                                                    </div>
                                                                  )}
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Contract boundaries</strong>
                                                                    <ul>
                                                                      {builderContractMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderContractMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderRunnerSeparated &&
                                                                !builderRunnerMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent runner validator required
                                                                      </h3>
                                                                      <p>
                                                                        Contract and prior package actors cannot
                                                                        run this package. Continue with a
                                                                        different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderContractMutation.data?.data
                                                                .outcome === "passed" &&
                                                                builderRunnerSeparated &&
                                                                !builderRunnerMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          ISOLATED RUNNER
                                                                        </p>
                                                                        <h3>
                                                                          Exercise disconnected synthetic behavior
                                                                        </h3>
                                                                        <p>
                                                                          Invoke every accepted capability with the
                                                                          platform harness. Package tests, network,
                                                                          credentials, targets, and models remain
                                                                          unavailable.
                                                                        </p>
                                                                      </div>
                                                                      <FlaskConical size={24} />
                                                                    </div>
                                                                    <label className="approval-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={builderRunnerAcknowledged}
                                                                        onChange={(event) =>
                                                                          setBuilderRunnerAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      <span>
                                                                        I am the independent runner validator. This
                                                                        executes only the fixed disconnected
                                                                        synthetic harness and grants no runtime
                                                                        authority.
                                                                      </span>
                                                                    </label>
                                                                    <button
                                                                      className="primary-button"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderRunnerAcknowledged ||
                                                                        builderRunnerMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const report =
                                                                          builderContractMutation.data?.data;
                                                                        if (report) {
                                                                          builderRunnerMutation.mutate(report);
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderRunnerMutation.isPending ? (
                                                                        <RefreshCw
                                                                          className="spin"
                                                                          size={16}
                                                                        />
                                                                      ) : (
                                                                        <Play size={16} />
                                                                      )}
                                                                      Run isolated validation
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderRunnerMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Runner validation unavailable</h3>
                                                                    <p>
                                                                      Exact lineage, archive integrity, process
                                                                      isolation, synthetic behavior, or cleanup did
                                                                      not reconcile.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderRunnerMutation.data?.data && (
                                                                <div className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE RUNNER REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderRunnerMutation.data.data
                                                                            .validation_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderRunnerMutation.data.data
                                                                            .canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderRunnerMutation.data.data.outcome ===
                                                                        "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderRunnerMutation.data.data.outcome ===
                                                                      "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderRunnerMutation.data.data.outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Capabilities</span>
                                                                      <strong>
                                                                        {builderRunnerMutation.data.data.capability_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Invoked</span>
                                                                      <strong>
                                                                        {builderRunnerMutation.data.data.invoked_capability_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Fail closed</span>
                                                                      <strong>
                                                                        {builderRunnerMutation.data.data.fail_closed_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Bounded results</span>
                                                                      <strong>
                                                                        {builderRunnerMutation.data.data.bounded_literal_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Runtime</span>
                                                                      <strong>
                                                                        {
                                                                          builderRunnerMutation.data.data
                                                                            .runtime_version
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Workspace</span>
                                                                      <strong>
                                                                        {builderRunnerMutation.data.data
                                                                          .workspace_removed
                                                                          ? "Removed"
                                                                          : "Unresolved"}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderRunnerMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Runner boundaries</strong>
                                                                    <ul>
                                                                      {builderRunnerMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderRunnerMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderLabSelfTestSeparated &&
                                                                !builderLabSelfTestMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent lab operator required
                                                                      </h3>
                                                                      <p>
                                                                        Runner and prior package actors cannot
                                                                        perform this lab self-test. Continue with a
                                                                        different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderRunnerMutation.data?.data
                                                                .outcome === "passed" &&
                                                                builderLabSelfTestSeparated &&
                                                                !builderLabSelfTestMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          READ-ONLY LAB SELF-TEST
                                                                        </p>
                                                                        <h3>
                                                                          Validate the approved non-production plan
                                                                        </h3>
                                                                        <p>
                                                                          The platform resolves target, trust, and
                                                                          short-lived access from the approved plan.
                                                                          No write capability is available.
                                                                        </p>
                                                                      </div>
                                                                      <FlaskConical size={24} />
                                                                    </div>
                                                                    <div className="mcp-builder-review-fields">
                                                                      <label>
                                                                        <span>Approved lab plan ID</span>
                                                                        <input
                                                                          value={builderLabPlanId}
                                                                          onChange={(event) =>
                                                                            setBuilderLabPlanId(event.target.value)
                                                                          }
                                                                          autoComplete="off"
                                                                        />
                                                                      </label>
                                                                      <label>
                                                                        <span>Approved plan digest</span>
                                                                        <input
                                                                          value={builderLabPlanDigest}
                                                                          onChange={(event) =>
                                                                            setBuilderLabPlanDigest(event.target.value)
                                                                          }
                                                                          autoComplete="off"
                                                                          spellCheck={false}
                                                                        />
                                                                      </label>
                                                                    </div>
                                                                    <label className="approval-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={builderLabSelfTestAcknowledged}
                                                                        onChange={(event) =>
                                                                          setBuilderLabSelfTestAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      <span>
                                                                        I am the independent lab operator. This run
                                                                        is restricted to the approved non-production
                                                                        target and read-only C0/C1 capabilities.
                                                                      </span>
                                                                    </label>
                                                                    <button
                                                                      className="primary-button"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderLabSelfTestAcknowledged ||
                                                                        !/^[a-z][a-z0-9_.:-]{2,127}$/.test(
                                                                          builderLabPlanId,
                                                                        ) ||
                                                                        !/^[a-f0-9]{64}$/.test(
                                                                          builderLabPlanDigest,
                                                                        ) ||
                                                                        builderLabSelfTestMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const source =
                                                                          builderRunnerMutation.data?.data;
                                                                        if (source) {
                                                                          builderLabSelfTestMutation.mutate({
                                                                            source,
                                                                            labPlanId: builderLabPlanId,
                                                                            labPlanDigest: builderLabPlanDigest,
                                                                          });
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderLabSelfTestMutation.isPending ? (
                                                                        <RefreshCw
                                                                          className="spin"
                                                                          size={16}
                                                                        />
                                                                      ) : (
                                                                        <FlaskConical size={16} />
                                                                      )}
                                                                      Run lab self-test
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderLabSelfTestMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Lab self-test unavailable</h3>
                                                                    <p>
                                                                      Exact lineage, plan approval, lease, read-only
                                                                      policy, target identity, or cleanup did not
                                                                      reconcile.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderLabSelfTestMutation.data?.data && (
                                                                <div className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE LAB REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderLabSelfTestMutation.data.data
                                                                            .self_test_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderLabSelfTestMutation.data.data
                                                                            .canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderLabSelfTestMutation.data.data
                                                                          .outcome === "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderLabSelfTestMutation.data.data
                                                                        .outcome === "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderLabSelfTestMutation.data.data
                                                                          .outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Target</span>
                                                                      <strong>
                                                                        {
                                                                          builderLabSelfTestMutation.data.data
                                                                            .target_alias
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Product</span>
                                                                      <strong>
                                                                        {
                                                                          builderLabSelfTestMutation.data.data
                                                                            .product_family
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Version</span>
                                                                      <strong>
                                                                        {
                                                                          builderLabSelfTestMutation.data.data
                                                                            .observed_product_version
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Coverage</span>
                                                                      <strong>
                                                                        {`${builderLabSelfTestMutation.data.data.tested_capability_count}/${builderLabSelfTestMutation.data.data.capability_count}`}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Requests</span>
                                                                      <strong>
                                                                        {builderLabSelfTestMutation.data.data.request_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Access</span>
                                                                      <strong>
                                                                        {builderLabSelfTestMutation.data.data
                                                                          .credentials_revoked
                                                                          ? "Revoked"
                                                                          : "Unresolved"}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderLabSelfTestMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Lab boundaries</strong>
                                                                    <ul>
                                                                      {builderLabSelfTestMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderLabSelfTestMutation.data?.data.outcome ===
                                                                "passed" &&
                                                                !builderFinalValidationSeparated &&
                                                                !builderFinalValidationMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent final validator required
                                                                      </h3>
                                                                      <p>
                                                                        No prior package, runner, lab, policy, or
                                                                        custody actor can perform final validation.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderLabSelfTestMutation.data?.data.outcome ===
                                                                "passed" &&
                                                                builderFinalValidationSeparated &&
                                                                !builderFinalValidationMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">
                                                                          GOVERNED FINAL VALIDATION
                                                                        </p>
                                                                        <h3>
                                                                          Reconcile the complete evidence chain
                                                                        </h3>
                                                                        <p>
                                                                          The signed policy evaluates exact lineage,
                                                                          coverage, freshness, limitations, and risk.
                                                                          This step cannot approve or operate a
                                                                          connector.
                                                                        </p>
                                                                      </div>
                                                                      <ShieldCheck size={24} />
                                                                    </div>
                                                                    <div className="mcp-builder-review-fields">
                                                                      <label>
                                                                        <span>Final-validation policy ID</span>
                                                                        <input
                                                                          value={builderFinalPolicyId}
                                                                          onChange={(event) =>
                                                                            setBuilderFinalPolicyId(event.target.value)
                                                                          }
                                                                          autoComplete="off"
                                                                        />
                                                                      </label>
                                                                      <label>
                                                                        <span>Signed policy digest</span>
                                                                        <input
                                                                          value={builderFinalPolicyDigest}
                                                                          onChange={(event) =>
                                                                            setBuilderFinalPolicyDigest(
                                                                              event.target.value,
                                                                            )
                                                                          }
                                                                          autoComplete="off"
                                                                          spellCheck={false}
                                                                        />
                                                                      </label>
                                                                    </div>
                                                                    <label className="approval-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={builderFinalValidationAcknowledged}
                                                                        onChange={(event) =>
                                                                          setBuilderFinalValidationAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      <span>
                                                                        I am the independent final validator. I
                                                                        understand this creates evidence only and
                                                                        does not approve, sign, install, enable, or
                                                                        execute the connector.
                                                                      </span>
                                                                    </label>
                                                                    <button
                                                                      className="primary-button"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderFinalValidationAcknowledged ||
                                                                        !/^[a-z][a-z0-9_.:-]{2,127}$/.test(
                                                                          builderFinalPolicyId,
                                                                        ) ||
                                                                        !/^[a-f0-9]{64}$/.test(
                                                                          builderFinalPolicyDigest,
                                                                        ) ||
                                                                        builderFinalValidationMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const source =
                                                                          builderLabSelfTestMutation.data?.data;
                                                                        if (source) {
                                                                          builderFinalValidationMutation.mutate({
                                                                            source,
                                                                            policyId: builderFinalPolicyId,
                                                                            policyDigest: builderFinalPolicyDigest,
                                                                          });
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderFinalValidationMutation.isPending ? (
                                                                        <RefreshCw
                                                                          className="spin"
                                                                          size={16}
                                                                        />
                                                                      ) : (
                                                                        <ShieldCheck size={16} />
                                                                      )}
                                                                      Run final validation
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderFinalValidationMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Final validation unavailable</h3>
                                                                    <p>
                                                                      Exact lineage, actor separation, signed policy,
                                                                      evidence freshness, coverage, or risk did not
                                                                      reconcile.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderFinalValidationMutation.data?.data && (
                                                                <div className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE FINAL REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderFinalValidationMutation.data.data
                                                                            .validation_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderFinalValidationMutation.data.data
                                                                            .canonical_digest
                                                                        }
                                                                      </code>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderFinalValidationMutation.data.data
                                                                          .eligible_for_human_approval
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderFinalValidationMutation.data.data
                                                                        .eligible_for_human_approval ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderFinalValidationMutation.data.data
                                                                          .outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Policy</span>
                                                                      <strong>
                                                                        {
                                                                          builderFinalValidationMutation.data.data
                                                                            .policy_version
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Stages</span>
                                                                      <strong>
                                                                        {`${builderFinalValidationMutation.data.data.passed_stage_count}/${builderFinalValidationMutation.data.data.stage_count}`}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Coverage</span>
                                                                      <strong>
                                                                        {`${builderFinalValidationMutation.data.data.tested_capability_count}/${builderFinalValidationMutation.data.data.capability_count}`}
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Blocking risks</span>
                                                                      <strong>
                                                                        {builderFinalValidationMutation.data.data.blocking_risk_count.toLocaleString()}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderFinalValidationMutation.data.data.stage_evidence.map(
                                                                      (stage) => (
                                                                        <article
                                                                          key={stage.stage_code}
                                                                          data-state={
                                                                            stage.promotion_blocked
                                                                              ? "failed"
                                                                              : "passed"
                                                                          }
                                                                        >
                                                                          {stage.promotion_blocked ? (
                                                                            <AlertTriangle size={16} />
                                                                          ) : (
                                                                            <CheckCircle2 size={16} />
                                                                          )}
                                                                          <div>
                                                                            <strong>
                                                                              {stage.stage_code}
                                                                            </strong>
                                                                            <p>{stage.evidence_id}</p>
                                                                          </div>
                                                                          <span>{stage.outcome}</span>
                                                                        </article>
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  {builderFinalValidationMutation.data.data.risks
                                                                    .length > 0 && (
                                                                    <div className="mcp-builder-limitations">
                                                                      <strong>Risk summary</strong>
                                                                      <ul>
                                                                        {builderFinalValidationMutation.data.data.risks.map(
                                                                          (risk) => (
                                                                            <li key={risk.code}>
                                                                              {risk.code}: {risk.next_step}
                                                                            </li>
                                                                          ),
                                                                        )}
                                                                      </ul>
                                                                    </div>
                                                                  )}
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Final-validation boundaries</strong>
                                                                    <ul>
                                                                      {builderFinalValidationMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderFinalValidationMutation.data?.data &&
                                                                identity && (
                                                                  <PackageApprovalPanel
                                                                    key={
                                                                      builderFinalValidationMutation.data.data
                                                                        .validation_id
                                                                    }
                                                                    source={
                                                                      builderFinalValidationMutation.data.data
                                                                    }
                                                                    subjectId={identity.subject_id}
                                                                  />
                                                                )}
                                                              {builderPackageInventoryMutation.data?.data
                                                                .outcome === "passed" &&
                                                                !builderContentPolicyScanSeparated &&
                                                                !builderContentPolicyScanMutation.data && (
                                                                  <div
                                                                    className="workspace-message error-state"
                                                                    role="alert"
                                                                  >
                                                                    <UserX size={20} />
                                                                    <div>
                                                                      <h3>
                                                                        Independent content-policy scan required
                                                                      </h3>
                                                                      <p>
                                                                        Inventory and prior package actors cannot
                                                                        scan this content. Continue with a
                                                                        different authorized session.
                                                                      </p>
                                                                    </div>
                                                                  </div>
                                                                )}
                                                              {builderPackageInventoryMutation.data?.data
                                                                .outcome === "passed" &&
                                                                builderContentPolicyScanSeparated &&
                                                                !builderContentPolicyScanMutation.data && (
                                                                  <section className="mcp-builder-validation">
                                                                    <div className="section-heading">
                                                                      <div>
                                                                        <p className="eyebrow">CONTENT POLICY</p>
                                                                        <h3>
                                                                          Scan secrets and prohibited content
                                                                        </h3>
                                                                        <p>
                                                                          Inspect the exact inventory offline.
                                                                          Matched values and source snippets are
                                                                          never returned or retained.
                                                                        </p>
                                                                      </div>
                                                                      <span className="state-badge pending">
                                                                        <ShieldCheck size={14} /> awaiting scan
                                                                      </span>
                                                                    </div>
                                                                    <label className="mcp-builder-check">
                                                                      <input
                                                                        type="checkbox"
                                                                        checked={
                                                                          builderContentPolicyScanAcknowledged
                                                                        }
                                                                        onChange={(event) =>
                                                                          setBuilderContentPolicyScanAcknowledged(
                                                                            event.target.checked,
                                                                          )
                                                                        }
                                                                      />
                                                                      I am the independent content-policy
                                                                      operator. I understand untrusted package
                                                                      text will be inspected without execution.
                                                                    </label>
                                                                    <button
                                                                      className="run-check-button mcp-builder-submit"
                                                                      type="button"
                                                                      disabled={
                                                                        !builderContentPolicyScanAcknowledged ||
                                                                        builderContentPolicyScanMutation.isPending
                                                                      }
                                                                      onClick={() => {
                                                                        const inventory =
                                                                          builderPackageInventoryMutation.data
                                                                            ?.data;
                                                                        if (inventory) {
                                                                          builderContentPolicyScanMutation.mutate(
                                                                            inventory,
                                                                          );
                                                                        }
                                                                      }}
                                                                    >
                                                                      {builderContentPolicyScanMutation.isPending ? (
                                                                        <RefreshCw className="spin" size={16} />
                                                                      ) : (
                                                                        <ShieldCheck size={16} />
                                                                      )}
                                                                      Run content-policy scan
                                                                    </button>
                                                                  </section>
                                                                )}
                                                              {builderContentPolicyScanMutation.isError && (
                                                                <div
                                                                  className="workspace-message error-state"
                                                                  role="alert"
                                                                >
                                                                  <AlertTriangle size={20} />
                                                                  <div>
                                                                    <h3>Content-policy scan unavailable</h3>
                                                                    <p>
                                                                      Exact inventory, package bytes,
                                                                      authorization, or separation of duties did
                                                                      not pass.
                                                                    </p>
                                                                  </div>
                                                                </div>
                                                              )}
                                                              {builderContentPolicyScanMutation.data?.data && (
                                                                <section className="mcp-builder-validation">
                                                                  <div className="section-heading">
                                                                    <div>
                                                                      <p className="eyebrow">
                                                                        IMMUTABLE CONTENT-POLICY REPORT
                                                                      </p>
                                                                      <strong>
                                                                        {
                                                                          builderContentPolicyScanMutation.data
                                                                            .data.scan_id
                                                                        }
                                                                      </strong>
                                                                      <code>
                                                                        {
                                                                          builderContentPolicyScanMutation.data
                                                                            .data.canonical_digest
                                                                        }
                                                                      </code>
                                                                      <small>
                                                                        Source inventory: <code>
                                                                          {
                                                                            builderContentPolicyScanMutation.data
                                                                              .data.source_inventory_digest
                                                                          }
                                                                        </code>
                                                                      </small>
                                                                    </div>
                                                                    <span
                                                                      className={`state-badge ${
                                                                        builderContentPolicyScanMutation.data.data
                                                                          .outcome === "passed"
                                                                          ? "healthy"
                                                                          : "critical"
                                                                      }`}
                                                                    >
                                                                      {builderContentPolicyScanMutation.data.data
                                                                        .outcome === "passed" ? (
                                                                        <CheckCircle2 size={14} />
                                                                      ) : (
                                                                        <AlertTriangle size={14} />
                                                                      )}
                                                                      {
                                                                        builderContentPolicyScanMutation.data.data
                                                                          .outcome
                                                                      }
                                                                    </span>
                                                                  </div>
                                                                  <div className="mcp-builder-facts">
                                                                    <div>
                                                                      <span>Scanned files</span>
                                                                      <strong>
                                                                        {
                                                                          builderContentPolicyScanMutation.data
                                                                            .data.scanned_file_count
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Safe findings</span>
                                                                      <strong>
                                                                        {
                                                                          builderContentPolicyScanMutation.data
                                                                            .data.findings.length
                                                                        }
                                                                      </strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Secret scan</span>
                                                                      <strong>Complete</strong>
                                                                    </div>
                                                                    <div>
                                                                      <span>Promotion</span>
                                                                      <strong>
                                                                        {builderContentPolicyScanMutation.data.data
                                                                          .promotion_blocked
                                                                          ? "Blocked"
                                                                          : "Not blocked"}
                                                                      </strong>
                                                                    </div>
                                                                  </div>
                                                                  {builderContentPolicyScanMutation.data.data
                                                                    .findings.length > 0 && (
                                                                    <div className="mcp-builder-validation-checks">
                                                                      {builderContentPolicyScanMutation.data.data.findings.map(
                                                                        (finding) => (
                                                                          <article
                                                                            key={
                                                                              finding.evidence_fingerprint
                                                                            }
                                                                            data-state="failed"
                                                                          >
                                                                            <AlertTriangle size={16} />
                                                                            <div>
                                                                              <strong>
                                                                                {finding.rule_code}
                                                                              </strong>
                                                                              <p>{finding.summary}</p>
                                                                              <small>
                                                                                {finding.relative_path}
                                                                                {finding.line_number
                                                                                  ? ` · line ${finding.line_number}`
                                                                                  : ""}
                                                                              </small>
                                                                            </div>
                                                                            <span>{finding.kind}</span>
                                                                          </article>
                                                                        ),
                                                                      )}
                                                                    </div>
                                                                  )}
                                                                  <div className="mcp-builder-validation-checks">
                                                                    {builderContentPolicyScanMutation.data.data.checks.map(
                                                                      (check) => (
                                                                        <article
                                                                          key={check.code}
                                                                          data-state={check.state}
                                                                        >
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
                                                                      ),
                                                                    )}
                                                                  </div>
                                                                  <div className="mcp-builder-limitations">
                                                                    <strong>Content-policy boundaries</strong>
                                                                    <ul>
                                                                      {builderContentPolicyScanMutation.data.data.limitations.map(
                                                                        (limitation) => (
                                                                          <li key={limitation}>{limitation}</li>
                                                                        ),
                                                                      )}
                                                                    </ul>
                                                                  </div>
                                                                  <div className="mcp-builder-boundary">
                                                                    <LockKeyhole size={18} />
                                                                    <p>
                                                                      No raw match is disclosed. Vulnerability,
                                                                      malware, license, code, contract, runner,
                                                                      and lab checks remain incomplete. No
                                                                      rejection, trust, execution, or deployment
                                                                      authority was granted.
                                                                    </p>
                                                                  </div>
                                                                </section>
                                                              )}
                                                              </>
                                                            )}
                                                            <div className="mcp-builder-boundary">
                                                              <LockKeyhole size={18} />
                                                              <p>
                                                                Signing, publisher attestation, registry
                                                                validation, registration, installation,
                                                                enablement, target configuration, credentials,
                                                                runtime trust, deployment approval, execution,
                                                                and infrastructure mutation remain false.
                                                              </p>
                                                            </div>
                                                          </div>
                                                        )}
                                                      </section>
                                                    )}
                                                  </section>
                                                )}
                                              </section>
                                            )}
                                          </div>
                                        )}
                                      </section>
                                    )}
                                  </div>
                                )}
                              </section>
                            </div>
                          )}
                        </section>
                      )}
                    </section>
                  </div>
                )}
              </section>
            </div>
            )}

            <div
              className="operations-workspace"
              hidden={activeNavigation !== "Health"}
            >
              <HealthWorkspaceNavigation
                activeView={activeHealthView}
                onNavigate={onNavigateHealthView}
              />
              {!identityQuery.isLoading && !identity && (
                <div className="workspace-message error-state">
                  <ShieldCheck size={22} />
                  <div>
                    <h2>Authentication required</h2>
                    <p>Storage health data is hidden until an authorized identity is available.</p>
                  </div>
                </div>
              )}

              {(identityQuery.isLoading || storageQuery.isLoading) && (
                <div className="workspace-message">
                  <Clock3 size={22} />
                  <div>
                    <h2>Loading governed storage context</h2>
                    <p>Authorization and evidence scope are being evaluated.</p>
                  </div>
                </div>
              )}

              {storageQuery.isError && (
                <div className="workspace-message error-state">
                  <AlertTriangle size={22} />
                  <div>
                    <h2>Storage overview unavailable</h2>
                    <p>No infrastructure state is inferred when authorized evidence cannot be read.</p>
                  </div>
                </div>
              )}

              {activeNavigation === "Health" && activeHealthView === "overview" && identity && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey="inventory-device-registry"
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading device registry</h2>
                          <p>Preparing authorized infrastructure lifecycle records.</p>
                        </div>
                      </div>
                    }
                  >
                    <InventoryDeviceRegistryWorkspace
                      environmentId={identity.scope.environment_id}
                      governedSessionAvailable={
                        identity.credential_kind === "browser_session"
                      }
                      onRequestEnterpriseLogin={() => setEnterpriseLoginRequested(true)}
                      organizationId={identity.scope.organization_id}
                      siteId={identity.scope.site_id}
                    />
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeNavigation === "Health" && activeHealthView === "overview" && overview && (
                <WorkspaceLoadBoundary compact resetKey={overview.snapshot_id} workspace="Health">
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Health inventory</h2>
                          <p>Preparing authorized inventory and evidence presentation.</p>
                        </div>
                      </div>
                    }
                  >
                    <HealthInventoryEvidenceWorkspace
                      impact={impact}
                      impactError={impactQuery.isError}
                      impactLoading={impactQuery.isLoading}
                      onSelectAsset={(assetId) => {
                        setSelectedAssetId(assetId);
                        investigationMutation.reset();
                        rcaMutation.reset();
                        recommendationMutation.reset();
                        clearTechnicalReportSelection();
                      }}
                      overview={overview}
                      selectedAsset={selectedAsset}
                      selectedEvidence={selectedEvidence}
                    />
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeHealthView === "governance" && identity && (
                <section className="workspace-section review-inbox-section">
                  <div className="section-heading review-inbox-heading">
                    <div>
                      <p className="eyebrow">HUMAN REVIEW INBOX</p>
                      <h2>Assigned upgrade reviews</h2>
                      <p>Exact evidence awaiting this identity's current accountable stage.</p>
                    </div>
                    <span className="state-badge pending">
                      <UserCheck size={14} /> {humanReviewInbox?.items.length ?? 0} assigned
                    </span>
                  </div>

                  {humanReviewInboxQuery.isLoading && (
                    <div className="review-inbox-status">
                      <Clock3 size={17} /> Evaluating role and scope
                    </div>
                  )}
                  {humanReviewInboxQuery.isError && (
                    <div className="review-inbox-status error-state" role="alert">
                      <AlertTriangle size={17} /> Assigned reviews are unavailable.
                    </div>
                  )}
                  {humanReviewInbox && humanReviewInbox.items.length === 0 && (
                    <div className="review-inbox-empty">
                      <ShieldCheck size={18} />
                      <div>
                        <strong>No actionable review is assigned</strong>
                        <p>Waiting, completed, ineligible, and out-of-scope requests stay hidden.</p>
                      </div>
                    </div>
                  )}
                  {humanReviewInbox && humanReviewInbox.items.length > 0 && (
                    <div className="review-inbox-list" aria-label="Assigned human reviews">
                      {humanReviewInbox.items.map((item) => {
                        const currentStage = item.stages.find((stage) => stage.state === "pending");
                        return (
                          <article key={item.review_id}>
                            <div className="review-inbox-item-main">
                              <span className="review-sequence">{currentStage?.sequence ?? "-"}</span>
                              <div>
                                <strong>
                                  {currentStage?.required_role_id
                                    .replace("role.", "")
                                    .replaceAll("-", " ") ?? "Review unavailable"}
                                </strong>
                                <code>{item.review_id}</code>
                              </div>
                            </div>
                            <div className="review-inbox-item-meta">
                              <span>{item.risk_class.replace("risk.", "")}</span>
                              <span>{formatTimestamp(item.expires_at)}</span>
                            </div>
                            <button
                              className="run-check-button"
                              type="button"
                              onClick={() => {
                                setSelectedInboxReviewId(item.review_id);
                                setReviewDecisionResult(null);
                              }}
                            >
                              <UserCheck size={16} /> Review request
                            </button>
                          </article>
                        );
                      })}
                    </div>
                  )}

                  {selectedInboxReview && selectedInboxStage && (
                    <form
                      className="review-decision-workspace"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (
                          reviewDecisionRationale.trim().length >= 5 &&
                          reviewDecisionAcknowledged &&
                          !reviewDecisionMutation.isPending
                        ) {
                          reviewDecisionMutation.mutate({
                            review: selectedInboxReview,
                            stageId: selectedInboxStage.stage_id,
                            outcome: reviewDecisionOutcome,
                            rationale: reviewDecisionRationale.trim(),
                            acknowledgedNoAuthority: reviewDecisionAcknowledged,
                          });
                        }
                      }}
                    >
                      <div className="review-workspace-heading">
                        <div>
                          <p className="eyebrow">CURRENT DECISION</p>
                          <h3>
                            {selectedInboxStage.required_role_id
                              .replace("role.", "")
                              .replaceAll("-", " ")}
                          </h3>
                          <code>{selectedInboxReview.packet_id}</code>
                        </div>
                        <button
                          className="icon-button"
                          type="button"
                          aria-label="Close review workspace"
                          onClick={() => setSelectedInboxReviewId(null)}
                        >
                          <X size={17} />
                        </button>
                      </div>

                      <div className="review-fact-grid" aria-label="Human review facts">
                        <div><span>Requester</span><strong>{selectedInboxReview.requester_id}</strong></div>
                        <div><span>Window</span><strong>{formatTimestamp(selectedInboxReview.proposed_window_start)}</strong></div>
                        <div><span>Affected services</span><strong>{selectedInboxReview.impacted_service_ids.length}</strong></div>
                        <div><span>Evidence digests</span><strong>{selectedInboxReview.evidence_digests.length}</strong></div>
                      </div>

                      <div className="review-impact-summary">
                        <strong>{selectedInboxReview.change_class.replace("change.", "")}</strong>
                        <p>{selectedInboxReview.justification}</p>
                        <span>{selectedInboxReview.impacted_service_ids.join(" · ")}</span>
                      </div>

                      <div className="human-review-stages">
                        {selectedInboxReview.stages.map((stage) => (
                          <div key={stage.stage_id}>
                            <span>{stage.sequence}</span>
                            <div>
                              <strong>{stage.required_role_id.replace("role.", "").replaceAll("-", " ")}</strong>
                              <code>{stage.stage_id}</code>
                            </div>
                            <small>{stage.state}</small>
                          </div>
                        ))}
                      </div>

                      <fieldset className="review-outcome-control">
                        <legend>Decision</legend>
                        {([
                          ["approve", "Approve", CheckCircle2],
                          ["reject", "Reject", UserX],
                          ["needs_evidence", "Needs evidence", Search],
                          ["defer", "Defer", Clock3],
                        ] as const).map(([value, label, Icon]) => (
                          <button
                            key={value}
                            type="button"
                            aria-pressed={reviewDecisionOutcome === value}
                            className={reviewDecisionOutcome === value ? "selected" : ""}
                            onClick={() => setReviewDecisionOutcome(value)}
                          >
                            <Icon size={15} /> {label}
                          </button>
                        ))}
                      </fieldset>

                      <label className="review-rationale-field">
                        <span>Decision rationale</span>
                        <textarea
                          value={reviewDecisionRationale}
                          minLength={5}
                          maxLength={1000}
                          rows={3}
                          required
                          onChange={(event) => setReviewDecisionRationale(event.target.value)}
                        />
                      </label>
                      <label className="review-boundary-check">
                        <input
                          type="checkbox"
                          checked={reviewDecisionAcknowledged}
                          onChange={(event) => setReviewDecisionAcknowledged(event.target.checked)}
                        />
                        <span>
                          This decision records human review only. It does not approve execution,
                          dispatch to ITSM, issue a handoff, or change infrastructure.
                        </span>
                      </label>
                      <div className="review-decision-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => setSelectedInboxReviewId(null)}
                        >
                          Cancel
                        </button>
                        <button
                          className="run-check-button"
                          type="submit"
                          disabled={
                            reviewDecisionRationale.trim().length < 5 ||
                            !reviewDecisionAcknowledged ||
                            reviewDecisionMutation.isPending
                          }
                        >
                          <UserCheck size={16} />
                          {reviewDecisionMutation.isPending ? "Recording" : "Record decision"}
                        </button>
                      </div>
                    </form>
                  )}

                  {reviewDecisionMutation.isError && (
                    <div className="review-inbox-status error-state" role="alert">
                      <AlertTriangle size={17} /> The decision was not recorded.
                    </div>
                  )}
                  {reviewDecisionResult && (
                    <div className="review-decision-result">
                      <CheckCircle2 size={17} />
                      <div>
                        <strong>Decision recorded</strong>
                        <p>
                          Review is now {reviewDecisionResult.state.replaceAll("_", " ")}; execution
                          authorization remains No.
                        </p>
                      </div>
                    </div>
                  )}
                  {reviewDecisionResult?.state === "completed" && !completionReceipt && (
                    <div className="completion-receipt-create">
                      <div className="completion-receipt-heading">
                        <FileCheck2 size={18} />
                        <div>
                          <strong>Create completion receipt</strong>
                          <p>Preserve the exact four-person review as non-executable evidence.</p>
                        </div>
                      </div>
                      <label className="review-boundary-check completion-receipt-check">
                        <input
                          type="checkbox"
                          checked={completionReceiptAcknowledged}
                          onChange={(event) =>
                            setCompletionReceiptAcknowledged(event.target.checked)
                          }
                        />
                        <span>
                          This receipt proves human review completion only. It grants no approval,
                          handoff, workflow, or infrastructure execution authority.
                        </span>
                      </label>
                      <button
                        className="run-check-button completion-receipt-button"
                        type="button"
                        disabled={
                          !completionReceiptAcknowledged || completionReceiptMutation.isPending
                        }
                        onClick={() =>
                          completionReceiptMutation.mutate({
                            review: reviewDecisionResult,
                            acknowledgedEvidenceOnly: completionReceiptAcknowledged,
                          })
                        }
                      >
                        <FileCheck2 size={16} />
                        {completionReceiptMutation.isPending ? "Creating" : "Create receipt"}
                      </button>
                    </div>
                  )}
                  {completionReceiptMutation.isError && (
                    <div className="review-inbox-status error-state" role="alert">
                      <AlertTriangle size={17} /> The completion receipt was not created.
                    </div>
                  )}
                  {completionReceipt && (
                    <article className="completion-receipt-result" aria-label="Completion receipt">
                      <div className="completion-receipt-heading">
                        <FileCheck2 size={18} />
                        <div>
                          <strong>Human-review completion receipt</strong>
                          <code>{completionReceipt.receipt_id}</code>
                        </div>
                      </div>
                      <dl>
                        <div>
                          <dt>Review</dt>
                          <dd>{completionReceipt.review_id}</dd>
                        </div>
                        <div>
                          <dt>Human stages</dt>
                          <dd>{completionReceipt.stages.length} approved</dd>
                        </div>
                        <div>
                          <dt>Evidence digests</dt>
                          <dd>{completionReceipt.evidence_digests.length}</dd>
                        </div>
                        <div>
                          <dt>Execution authority</dt>
                          <dd>No</dd>
                        </div>
                      </dl>
                      <p>
                        Evidence only. Approval, ITSM dispatch, handoff, workflow execution, and
                        infrastructure mutation remain No.
                      </p>
                    </article>
                  )}
                  <div className="safety-notice review-inbox-boundary">
                    <ShieldCheck size={16} />
                    <span>
                      Human review is evidence-bound decision support. No review action executes a
                      workflow or infrastructure change.
                    </span>
                  </div>
                </section>
              )}

              {activeHealthView === "governance" && auditExport && auditHealth && (
                <section className="workspace-section audit-export-section">
                  <div className="section-heading audit-export-heading">
                    <div>
                      <p className="eyebrow">AUDIT GOVERNANCE</p>
                      <h2>Enterprise audit delivery</h2>
                      <p>Bounded, secret-free evidence from the authoritative Atlas audit stream.</p>
                    </div>
                    <span className={`security-export-state ${auditHealth.state}`}>
                      <ShieldCheck size={14} /> {auditHealth.state}
                    </span>
                  </div>

                  <div className="audit-export-toolbar">
                    <label>
                      <span>Search bounded events</span>
                      <div className="audit-search-input">
                        <Search size={15} />
                        <input
                          aria-label="Search audit events"
                          value={auditSearch}
                          maxLength={80}
                          placeholder="Event, result, subject, correlation"
                          onChange={(event) => setAuditSearch(event.target.value)}
                        />
                      </div>
                    </label>
                    <label>
                      <span>Outcome</span>
                      <select
                        aria-label="Filter audit outcome"
                        value={auditOutcome}
                        onChange={(event) => setAuditOutcome(event.target.value)}
                      >
                        <option value="">All outcomes</option>
                        <option value="allowed">Allowed</option>
                        <option value="denied">Denied</option>
                        <option value="succeeded">Succeeded</option>
                        <option value="failed">Failed</option>
                      </select>
                    </label>
                    <button
                      className="run-check-button audit-retry-button"
                      type="button"
                      disabled={
                        retryAuditExportMutation.isPending || auditHealth.queue_depth === 0
                      }
                      onClick={() => retryAuditExportMutation.mutate()}
                    >
                      <RefreshCw
                        className={retryAuditExportMutation.isPending ? "spin" : undefined}
                        size={16}
                      />
                      Retry queued delivery
                    </button>
                  </div>

                  <div className="audit-health-grid" aria-label="Audit delivery health">
                    <div>
                      <span>Bounded page</span>
                      <strong>{auditExport.page.events.length}</strong>
                      <small>Maximum {auditExport.page.limit} events</small>
                    </div>
                    <div>
                      <span>Queued</span>
                      <strong>{auditHealth.queue_depth}</strong>
                      <small>{auditHealth.retrying_count} retrying</small>
                    </div>
                    <div>
                      <span>Transport handoffs</span>
                      <strong>{auditHealth.delivered_count}</strong>
                      <small>SIEM receipt not inferred</small>
                    </div>
                    <div>
                      <span>Dead-letter</span>
                      <strong>{auditHealth.dead_letter_count}</strong>
                      <small>Visible for governed follow-up</small>
                    </div>
                  </div>

                  <div className="audit-export-grid">
                    <div className="audit-events-panel">
                      <div className="audit-panel-heading">
                        <h3>Authorized events</h3>
                        <span>{auditExport.page.has_more ? "More available" : "Bounded result"}</span>
                      </div>
                      {auditExport.page.events.length === 0 ? (
                        <p className="audit-empty">No matching audit events in this exact scope.</p>
                      ) : (
                        <div className="audit-event-list">
                          {auditExport.page.events.map((event) => (
                            <article className="audit-event" key={`${event.sequence}-${event.event_id}`}>
                              <div className="audit-event-title">
                                <strong>{event.event_type}</strong>
                                <span className={`audit-outcome ${event.outcome}`}>
                                  {event.outcome}
                                </span>
                              </div>
                              <p>{event.result_code}</p>
                              <dl>
                                <div>
                                  <dt>Actor</dt>
                                  <dd>{event.subject_id ?? "Unknown subject"}</dd>
                                </div>
                                <div>
                                  <dt>Occurred</dt>
                                  <dd>{formatTimestamp(event.occurred_at)}</dd>
                                </div>
                                <div>
                                  <dt>Correlation</dt>
                                  <dd>{event.correlation_id}</dd>
                                </div>
                                <div>
                                  <dt>Permission</dt>
                                  <dd>{event.permission_id ?? "Not applicable"}</dd>
                                </div>
                              </dl>
                              <code>{event.event_id}</code>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="audit-delivery-panel">
                      <div className="audit-panel-heading">
                        <h3>Recent delivery state</h3>
                        <span>At least once</span>
                      </div>
                      {auditExport.recent_deliveries.length === 0 ? (
                        <p className="audit-empty">No delivery attempts are visible yet.</p>
                      ) : (
                        <div className="audit-delivery-list">
                          {auditExport.recent_deliveries.slice(0, 8).map((delivery) => (
                            <article className="audit-delivery" key={delivery.delivery_id}>
                              <div>
                                <strong>{delivery.state.replaceAll("_", " ")}</strong>
                                <span>{delivery.attempts} attempt(s)</span>
                              </div>
                              <code>{delivery.event_id}</code>
                              <small>{formatTimestamp(delivery.updated_at)}</small>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {retryAuditExportMutation.data && (
                    <div className="security-export-result" role="status">
                      <CheckCircle2 size={16} />
                      Retry completed: {retryAuditExportMutation.data.data.delivered} transport
                      handoff(s), {retryAuditExportMutation.data.data.retrying} still retrying.
                    </div>
                  )}
                  {retryAuditExportMutation.isError && (
                    <div className="security-export-result error-state" role="alert">
                      <AlertTriangle size={16} /> Delivery remains queued or unavailable.
                    </div>
                  )}
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>{auditExport.safety_notice}</span>
                  </div>
                </section>
              )}

              {activeNavigation === "Health" &&
                activeHealthView === "deployments" &&
                releasePreflight && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey={releasePreflight.report_id}
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Release Preflight</h2>
                          <p>Preparing authorized immutable release evidence.</p>
                        </div>
                      </div>
                    }
                  >
                    <ReleasePreflightWorkspace
                      mode={releaseMode}
                      onModeChange={setReleaseMode}
                      onProfileChange={setReleaseProfile}
                      preflight={releasePreflight}
                      profile={releaseProfile}
                    />
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeNavigation === "Health" &&
                activeHealthView === "deployments" &&
                deploymentConfiguration && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey={deploymentConfiguration.preview_id}
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Deployment Configuration</h2>
                          <p>Preparing authorized redacted configuration evidence.</p>
                        </div>
                      </div>
                    }
                  >
                    <DeploymentConfigurationWorkspace preview={deploymentConfiguration} />
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeNavigation === "Health" &&
                activeHealthView === "deployments" &&
                bootstrapPlan && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey={bootstrapPlan.plan_id}
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Bootstrap Plan</h2>
                          <p>Preparing authorized ordered phase evidence.</p>
                        </div>
                      </div>
                    }
                  >
                    <BootstrapPlanWorkspace plan={bootstrapPlan} />
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeNavigation === "Health" &&
                activeHealthView === "deployments" &&
                bootstrapState && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey={
                    bootstrapState.run
                      ? `${bootstrapState.run.run_id}:${bootstrapState.run.version}`
                      : `empty:${bootstrapState.durable}:${bootstrapState.lease_available}`
                  }
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Bootstrap Checkpoints</h2>
                          <p>Preparing authorized resume and lease evidence.</p>
                        </div>
                      </div>
                    }
                  >
                    <section className="workspace-section bootstrap-state-section">
                      <BootstrapCheckpointWorkspace
                        formatTimestamp={formatTimestamp}
                        state={bootstrapState}
                      />
                      {bootstrapState.run && (
                    <>
                      {bootstrapPlan && releasePreflight && identity && (
                        <BootstrapArtifactAcquisitionWorkspace
                          formatTimestamp={formatTimestamp}
                          plan={bootstrapPlan}
                          preflight={releasePreflight}
                          scope={identity.scope}
                          state={bootstrapState}
                        />
                      )}
                      {deploymentConfiguration && identity && (
                        <BootstrapConfigurationRenderingWorkspace
                          configuration={deploymentConfiguration}
                          formatTimestamp={formatTimestamp}
                          scope={identity.scope}
                          state={bootstrapState}
                        />
                      )}
                      {deploymentConfiguration && bootstrapTrustPlan && identity && (
                        <BootstrapTrustProvisioningWorkspace
                          configuration={deploymentConfiguration}
                          scope={identity.scope}
                          state={bootstrapState}
                          trustPlan={bootstrapTrustPlan}
                        />
                      )}
                      {deploymentConfiguration &&
                        bootstrapTrustPlan &&
                        bootstrapDataPlan &&
                        identity && (
                          <BootstrapDataInitializationWorkspace
                            configuration={deploymentConfiguration}
                            dataPlan={bootstrapDataPlan}
                            scope={identity.scope}
                            state={bootstrapState}
                            trustPlan={bootstrapTrustPlan}
                          />
                        )}
                      {deploymentConfiguration &&
                        bootstrapTrustPlan &&
                        bootstrapDataPlan &&
                        bootstrapServicePlan &&
                        identity && (
                          <BootstrapServiceDeploymentWorkspace
                            configuration={deploymentConfiguration}
                            dataPlan={bootstrapDataPlan}
                            scope={identity.scope}
                            servicePlan={bootstrapServicePlan}
                            state={bootstrapState}
                            trustPlan={bootstrapTrustPlan}
                          />
                        )}
                      {deploymentConfiguration &&
                        bootstrapTrustPlan &&
                        bootstrapDataPlan &&
                        bootstrapServicePlan &&
                        bootstrapIdentityPlan &&
                        identity && (
                          <BootstrapIdentityHandoffWorkspace
                            configuration={deploymentConfiguration}
                            dataPlan={bootstrapDataPlan}
                            identityPlan={bootstrapIdentityPlan}
                            scope={identity.scope}
                            servicePlan={bootstrapServicePlan}
                            state={bootstrapState}
                            trustPlan={bootstrapTrustPlan}
                          />
                        )}
                      {integrationPhaseAvailable &&
                        bootstrapIntegrationPlan &&
                        !integrationValidationPending && (
                          <div className="data-initialization-action integration-validation-action">
                            <div>
                              <strong>Validate model gateway and core integrations</strong>
                              <p>
                                Reviews one local OpenAI-compatible model contract and {" "}
                                {bootstrapIntegrationPlan.integrations.length} inactive integration
                                registrations through {bootstrapIntegrationPlan.checks.length} {" "}
                                synthetic checks. No endpoint is called or activated.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                setIntegrationValidationResult(null);
                                setIntegrationValidationPending(true);
                              }}
                            >
                              <Network size={14} /> Review integrations
                            </button>
                          </div>
                        )}
                      {integrationValidationPending &&
                        integrationPhaseAvailable &&
                        bootstrapIntegrationPlan && (
                          <div
                            className="data-initialization-confirmation integration-validation-confirmation"
                            role="dialog"
                          >
                            <div>
                              <strong>Confirm synthetic integration validation</strong>
                              <p>
                                Target {bootstrapIntegrationPlan.target_id} is {" "}
                                {bootstrapIntegrationPlan.target_state}. This publishes one
                                Atlas-owned validation document without resolving credentials or
                                contacting any integration.
                              </p>
                            </div>
                            <div className="identity-plan-summary integration-plan-summary">
                              <div>
                                <span>Model contract</span>
                                <code>{bootstrapIntegrationPlan.model_endpoint.model_id}</code>
                                <small>
                                  {bootstrapIntegrationPlan.model_endpoint.context_limit.toLocaleString()}
                                  -token context
                                </small>
                              </div>
                              <div>
                                <span>Core integrations</span>
                                <strong>{bootstrapIntegrationPlan.integrations.length}</strong>
                                <small>All inactive</small>
                              </div>
                              <div>
                                <span>Mandatory checks</span>
                                <strong>{bootstrapIntegrationPlan.checks.length}</strong>
                                <small>All synthetic passes</small>
                              </div>
                              <div>
                                <span>External operations</span>
                                <strong>0</strong>
                                <small>No network or secret access</small>
                              </div>
                            </div>
                            <div className="identity-mapping-list integration-registration-list">
                              {bootstrapIntegrationPlan.integrations.map((integration) => (
                                <div key={integration.integration_id}>
                                  <div>
                                    <code>{integration.integration_id}</code>
                                    <small>{integration.integration_type}</small>
                                  </div>
                                  <strong>{integration.activation_state}</strong>
                                </div>
                              ))}
                            </div>
                            <label>
                              Integration-validation justification
                              <input
                                value={integrationValidationJustification}
                                maxLength={500}
                                onChange={(event) =>
                                  setIntegrationValidationJustification(event.target.value)
                                }
                                placeholder="Record the reviewed reason for synthetic validation"
                              />
                            </label>
                            {integrationValidationMutation.isError && (
                              <div className="impact-message impact-error" role="alert">
                                <AlertTriangle size={16} /> Integration state was not validated.
                                Refresh the governed state and exact plan before retrying.
                              </div>
                            )}
                            <div className="data-initialization-confirm-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  setIntegrationValidationPending(false);
                                  setIntegrationValidationJustification("");
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                className="data-initialization-confirm"
                                type="button"
                                disabled={
                                  integrationValidationJustification.trim().length < 12 ||
                                  integrationValidationMutation.isPending
                                }
                                onClick={() => integrationValidationMutation.mutate()}
                              >
                                <Network size={14} /> Confirm integrations
                              </button>
                            </div>
                          </div>
                        )}
                      {integrationExecution && (
                        <div
                          className={`data-initialization-result integration-validation-result ${integrationExecution.state}`}
                        >
                          <div className="data-initialization-result-heading">
                            {integrationExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>
                                Integration validation {integrationExecution.state}
                              </strong>
                              <code>{integrationExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${integrationExecution.state}`}>
                              {integrationExecution.state}
                            </span>
                          </div>
                          <div className="data-initialization-summary">
                            <div>
                              <span>Model checks</span>
                              <strong>{integrationExecution.model_check_count}</strong>
                            </div>
                            <div>
                              <span>Integration checks</span>
                              <strong>{integrationExecution.integration_check_count}</strong>
                            </div>
                            <div>
                              <span>Mandatory passes</span>
                              <strong>{integrationExecution.mandatory_pass_count}</strong>
                            </div>
                            <div>
                              <span>External operations</span>
                              <strong>
                                {integrationExecution.activation_count +
                                  integrationExecution.network_request_count +
                                  integrationExecution.secret_resolution_count}
                              </strong>
                            </div>
                          </div>
                          {integrationExecution.evidence.map((item) => (
                            <div className="service-state-evidence" key={item.evidence_id}>
                              <div>
                                <code>{item.evidence_id}</code>
                                <span>{item.disposition}</span>
                              </div>
                              <code>{item.sha256.slice(0, 20)}...</code>
                            </div>
                          ))}
                          {integrationExecution.state === "failed" && (
                            <p className="data-recovery-note">
                              No partial integration state was published. Correct the bounded failure
                              and retry under the active lease.
                            </p>
                          )}
                        </div>
                      )}
                      {verificationPhaseAvailable &&
                        bootstrapVerificationPlan &&
                        !verificationPending && (
                          <div className="data-initialization-action verification-action">
                            <div>
                              <strong>Verify the complete bootstrap evidence</strong>
                              <p>
                                Reconciles {bootstrapVerificationPlan.checks.length} versioned
                                checks across ingress, identity, audit, data, model, knowledge,
                                workflow, connector, recovery, and security boundaries.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                setVerificationResult(null);
                                setVerificationPending(true);
                              }}
                            >
                              <ShieldCheck size={14} /> Review verification
                            </button>
                          </div>
                        )}
                      {verificationPending &&
                        verificationPhaseAvailable &&
                        bootstrapVerificationPlan && (
                          <div className="data-initialization-confirmation verification-confirmation" role="dialog">
                            <div>
                              <strong>Confirm end-to-end verification</strong>
                              <p>
                                Target {bootstrapVerificationPlan.target_id} is {" "}
                                {bootstrapVerificationPlan.target_state}. This publishes one
                                sanitized Atlas report and performs no external operation.
                              </p>
                            </div>
                            <div className="identity-plan-summary verification-plan-summary">
                              <div>
                                <span>Suite</span>
                                <code>{bootstrapVerificationPlan.suite_version}</code>
                                <small>Source revision {bootstrapVerificationPlan.source_run_version}</small>
                              </div>
                              <div>
                                <span>Mandatory passes</span>
                                <strong>
                                  {bootstrapVerificationPlan.checks.filter((item) => item.mandatory).length}
                                </strong>
                                <small>No skipped mandatory check</small>
                              </div>
                              <div>
                                <span>Not applicable</span>
                                <strong>
                                  {bootstrapVerificationPlan.checks.filter(
                                    (item) => item.state === "not_applicable",
                                  ).length}
                                </strong>
                                <small>Unselected external services</small>
                              </div>
                              <div>
                                <span>External operations</span>
                                <strong>0</strong>
                                <small>Evidence reconciliation only</small>
                              </div>
                            </div>
                            <div className="identity-mapping-list verification-check-list">
                              {bootstrapVerificationPlan.checks.map((check) => (
                                <div key={check.check_id}>
                                  <div>
                                    <code>{check.check_id}</code>
                                    <small>{check.category_id}</small>
                                  </div>
                                  <strong>{check.state.replaceAll("_", " ")}</strong>
                                </div>
                              ))}
                            </div>
                            <label>
                              Verification justification
                              <input
                                value={verificationJustification}
                                maxLength={500}
                                onChange={(event) => setVerificationJustification(event.target.value)}
                                placeholder="Record the reviewed reason for verification"
                              />
                            </label>
                            {verificationMutation.isError && (
                              <div className="impact-message impact-error" role="alert">
                                <AlertTriangle size={16} /> Verification was not completed. Refresh
                                the exact governed state before retrying.
                              </div>
                            )}
                            <div className="data-initialization-confirm-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  setVerificationPending(false);
                                  setVerificationJustification("");
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                className="data-initialization-confirm"
                                type="button"
                                disabled={
                                  verificationJustification.trim().length < 12 ||
                                  verificationMutation.isPending
                                }
                                onClick={() => verificationMutation.mutate()}
                              >
                                <ShieldCheck size={14} /> Confirm verification
                              </button>
                            </div>
                          </div>
                        )}
                      {verificationExecution && (
                        <div
                          className={`data-initialization-result verification-result ${verificationExecution.state}`}
                        >
                          <div className="data-initialization-result-heading">
                            {verificationExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>End-to-end verification {verificationExecution.state}</strong>
                              <code>{verificationExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${verificationExecution.state}`}>
                              {verificationExecution.state}
                            </span>
                          </div>
                          <div className="data-initialization-summary">
                            <div>
                              <span>Passed</span>
                              <strong>{verificationExecution.passed_count}</strong>
                            </div>
                            <div>
                              <span>Failed / skipped</span>
                              <strong>
                                {verificationExecution.failed_count + verificationExecution.skipped_count}
                              </strong>
                            </div>
                            <div>
                              <span>Not applicable</span>
                              <strong>{verificationExecution.not_applicable_count}</strong>
                            </div>
                            <div>
                              <span>External operations</span>
                              <strong>{verificationExecution.external_operation_count}</strong>
                            </div>
                          </div>
                          {verificationExecution.evidence.map((item) => (
                            <div className="service-state-evidence" key={item.evidence_id}>
                              <div>
                                <code>{item.evidence_id}</code>
                                <span>{item.disposition}</span>
                              </div>
                              <code>{item.sha256.slice(0, 20)}...</code>
                            </div>
                          ))}
                          {verificationExecution.state === "failed" && (
                            <p className="data-recovery-note">
                              No successful verification checkpoint was recorded. Resolve every
                              mandatory finding before operational handoff.
                            </p>
                          )}
                        </div>
                      )}
                      {handoffPhaseAvailable && bootstrapHandoffPlan && !handoffPending && (
                        <div className="data-initialization-action handoff-action">
                          <div>
                            <strong>Prepare operational handoff</strong>
                            <p>
                              Developer and Linux lab evidence is complete. Production acceptance
                              remains explicitly unclaimed.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setHandoffResult(null);
                              setHandoffPending(true);
                            }}
                          >
                            <FileText size={14} /> Review handoff
                          </button>
                        </div>
                      )}
                      {handoffPending && handoffPhaseAvailable && bootstrapHandoffPlan && (
                        <div
                          className="data-initialization-confirmation handoff-confirmation"
                          role="dialog"
                        >
                          <div>
                            <strong>Confirm operational handoff</strong>
                            <p>
                              Target {bootstrapHandoffPlan.target_id} is {" "}
                              {bootstrapHandoffPlan.target_state}. The report remains local and
                              contains no production approval.
                            </p>
                          </div>
                          <div className="identity-plan-summary handoff-plan-summary">
                            <div>
                              <span>Readiness</span>
                              <code>{bootstrapHandoffPlan.readiness_class}</code>
                              <small>Developer and Linux lab only</small>
                            </div>
                            <div>
                              <span>Known limitations</span>
                              <strong>{bootstrapHandoffPlan.known_limitation_ids.length}</strong>
                              <small>Recorded in the handoff evidence</small>
                            </div>
                            <div>
                              <span>Pending actions</span>
                              <strong>{bootstrapHandoffPlan.pending_action_ids.length}</strong>
                              <small>Required before production review</small>
                            </div>
                            <div>
                              <span>Production claims</span>
                              <strong>0</strong>
                              <small>All seven claims remain false</small>
                            </div>
                          </div>
                          <div className="identity-mapping-list handoff-limitation-list">
                            {bootstrapHandoffPlan.known_limitation_ids.map((limitation) => (
                              <div key={limitation}>
                                <div>
                                  <code>{limitation}</code>
                                  <small>Bounded handoff limitation</small>
                                </div>
                                <strong>recorded</strong>
                              </div>
                            ))}
                          </div>
                          <label>
                            Handoff justification
                            <input
                              value={handoffJustification}
                              maxLength={500}
                              onChange={(event) => setHandoffJustification(event.target.value)}
                              placeholder="Record the reviewed handoff purpose"
                            />
                          </label>
                          {handoffMutation.isError && (
                            <div className="impact-message impact-error" role="alert">
                              <AlertTriangle size={16} /> Handoff was not completed. Refresh the
                              governed evidence before retrying.
                            </div>
                          )}
                          <div className="data-initialization-confirm-actions">
                            <button
                              type="button"
                              onClick={() => {
                                setHandoffPending(false);
                                setHandoffJustification("");
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              className="data-initialization-confirm"
                              type="button"
                              disabled={
                                handoffJustification.trim().length < 12 ||
                                handoffMutation.isPending
                              }
                              onClick={() => handoffMutation.mutate()}
                            >
                              <FileText size={14} /> Confirm handoff
                            </button>
                          </div>
                        </div>
                      )}
                      {handoffExecution && (
                        <div
                          className={`data-initialization-result handoff-result ${handoffExecution.state}`}
                        >
                          <div className="data-initialization-result-heading">
                            {handoffExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>Operational handoff {handoffExecution.state}</strong>
                              <code>{handoffExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${handoffExecution.state}`}>
                              {handoffExecution.state}
                            </span>
                          </div>
                          <div className="data-initialization-summary">
                            <div>
                              <span>Readiness</span>
                              <strong>Lab complete</strong>
                            </div>
                            <div>
                              <span>Limitations</span>
                              <strong>{handoffExecution.known_limitation_count}</strong>
                            </div>
                            <div>
                              <span>Missing production evidence</span>
                              <strong>{handoffExecution.missing_production_evidence_count}</strong>
                            </div>
                            <div>
                              <span>External operations</span>
                              <strong>{handoffExecution.external_operation_count}</strong>
                            </div>
                          </div>
                          {handoffExecution.evidence.map((item) => (
                            <div className="service-state-evidence" key={item.evidence_id}>
                              <div>
                                <code>{item.evidence_id}</code>
                                <span>{item.disposition}</span>
                              </div>
                              <code>{item.sha256.slice(0, 20)}...</code>
                            </div>
                          ))}
                          {handoffExecution.state === "completed" && (
                            <p className="data-recovery-note">
                              Bootstrap evidence is complete for the developer and Linux lab
                              profile. Production readiness remains false.
                            </p>
                          )}
                        </div>
                      )}
                      {bootstrapState.run.state === "completed" &&
                        bootstrapState.run.operational_handoff?.state === "completed" && (
                          <section className="support-bundle-section">
                            <div className="support-bundle-heading">
                              <div>
                                <span className="eyebrow">Local support evidence</span>
                                <h3>Governed support bundle</h3>
                              </div>
                              <span className="state-badge completed">C2 local export</span>
                            </div>
                            <div className="support-bundle-controls">
                              <label>
                                Evidence window
                                <select
                                  aria-label="Support evidence window"
                                  value={supportLookbackHours}
                                  onChange={(event) => {
                                    setSupportResult(null);
                                    setSupportPending(false);
                                    setSupportLookbackHours(Number(event.target.value));
                                  }}
                                >
                                  <option value={12}>12 hours</option>
                                  <option value={24}>24 hours</option>
                                  <option value={72}>72 hours</option>
                                  <option value={168}>7 days</option>
                                </select>
                              </label>
                              <fieldset>
                                <legend>Bundle components</legend>
                                {SUPPORT_BUNDLE_COMPONENTS.map((componentId) => {
                                  const required =
                                    componentId === "support.release-manifest" ||
                                    componentId === "support.bootstrap-summary";
                                  return (
                                    <label key={componentId}>
                                      <input
                                        type="checkbox"
                                        checked={supportComponentIds.includes(componentId)}
                                        disabled={required}
                                        onChange={(event) => {
                                          setSupportResult(null);
                                          setSupportPending(false);
                                          setSupportComponentIds((current) =>
                                            event.target.checked
                                              ? [...current, componentId]
                                              : current.filter((item) => item !== componentId),
                                          );
                                        }}
                                      />
                                      <span>{componentId.replace("support.", "").replaceAll("-", " ")}</span>
                                      {required && <small>Required</small>}
                                    </label>
                                  );
                                })}
                              </fieldset>
                            </div>
                            {supportBundlePreviewQuery.isLoading && (
                              <div className="inline-state">
                                <RefreshCw className="spin" size={16} /> Building bounded preview
                              </div>
                            )}
                            {supportBundlePreviewQuery.isError && (
                              <div className="inline-error">
                                <AlertTriangle size={16} /> Support preview is unavailable for this
                                evidence selection.
                              </div>
                            )}
                            {supportBundlePreview && !supportPending && !supportResult && (
                              <div className="data-initialization-action support-bundle-action">
                                <div>
                                  <strong>Preview passed all export gates</strong>
                                  <p>
                                    {supportBundlePreview.included_count} included, {" "}
                                    {supportBundlePreview.excluded_count} excluded, {" "}
                                    {supportBundlePreview.redaction_check_count} redaction checks.
                                  </p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSupportResult(null);
                                    setSupportPending(true);
                                  }}
                                >
                                  <Archive size={14} /> Review export
                                </button>
                              </div>
                            )}
                            {supportPending && supportBundlePreview && (
                              <div
                                className="data-initialization-confirmation support-bundle-confirmation"
                                role="dialog"
                              >
                                <div>
                                  <strong>Confirm local support bundle</strong>
                                  <p>
                                    Archive {supportBundlePreview.target_state}; no external transfer
                                    or arbitrary host-file collection is authorized.
                                  </p>
                                </div>
                                <div className="identity-plan-summary support-bundle-summary">
                                  <div>
                                    <span>Archive</span>
                                    <strong>{supportBundlePreview.archive_size_bytes} bytes</strong>
                                    <small>{supportBundlePreview.archive_sha256.slice(0, 20)}...</small>
                                  </div>
                                  <div>
                                    <span>Content budget</span>
                                    <strong>{supportBundlePreview.content_bytes} bytes</strong>
                                    <small>of {supportBundlePreview.max_content_bytes}</small>
                                  </div>
                                  <div>
                                    <span>Classification</span>
                                    <strong>Internal</strong>
                                    <small>Typed Atlas evidence only</small>
                                  </div>
                                  <div>
                                    <span>Transfer</span>
                                    <strong>Local only</strong>
                                    <small>External operation false</small>
                                  </div>
                                </div>
                                <div className="identity-mapping-list support-entry-list">
                                  {supportBundlePreview.entries.map((entry) => (
                                    <div key={entry.entry_id}>
                                      <div>
                                        <code>{entry.entry_id}</code>
                                        <small>{entry.file_name}</small>
                                      </div>
                                      <strong>{entry.disposition}</strong>
                                    </div>
                                  ))}
                                </div>
                                <label>
                                  Support-export justification
                                  <input
                                    value={supportJustification}
                                    maxLength={500}
                                    onChange={(event) =>
                                      setSupportJustification(event.target.value)
                                    }
                                    placeholder="Record the reviewed diagnostic purpose"
                                  />
                                </label>
                                {supportBundleMutation.isError && (
                                  <div className="inline-error">
                                    <AlertTriangle size={16} /> The support bundle was not created.
                                  </div>
                                )}
                                <div className="data-initialization-confirm-actions">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSupportPending(false);
                                      setSupportJustification("");
                                    }}
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    className="data-initialization-confirm"
                                    type="button"
                                    disabled={
                                      supportJustification.trim().length < 12 ||
                                      supportBundleMutation.isPending
                                    }
                                    onClick={() => supportBundleMutation.mutate()}
                                  >
                                    <Archive size={14} /> Confirm local export
                                  </button>
                                </div>
                              </div>
                            )}
                            {supportResult && (
                              <div className="data-initialization-result completed support-bundle-result">
                                <div className="data-initialization-result-heading">
                                  <CheckCircle2 size={18} />
                                  <div>
                                    <strong>Support bundle completed</strong>
                                    <code>{supportResult.export_id}</code>
                                  </div>
                                  <span className="state-badge completed">local only</span>
                                </div>
                                <div className="data-initialization-summary">
                                  <div>
                                    <span>Entries</span>
                                    <strong>{supportResult.included_count}</strong>
                                  </div>
                                  <div>
                                    <span>Archive bytes</span>
                                    <strong>{supportResult.archive_size_bytes}</strong>
                                  </div>
                                  <div>
                                    <span>Reuse</span>
                                    <strong>{supportResult.reused ? "Exact bytes" : "Published"}</strong>
                                  </div>
                                  <div>
                                    <span>External transfer</span>
                                    <strong>No</strong>
                                  </div>
                                </div>
                                <div className="service-state-evidence">
                                  <div>
                                    <code>{supportResult.archive_name}</code>
                                    <span>Integrity verified</span>
                                  </div>
                                  <code>{supportResult.archive_sha256.slice(0, 20)}...</code>
                                </div>
                                <p className="data-recovery-note">
                                  Retain only through {formatTimestamp(supportResult.expires_at)}.
                                  Support-system upload remains outside this operation.
                                </p>
                              </div>
                            )}
                          </section>
                        )}
                      {bootstrapState.run.state === "completed" &&
                        bootstrapState.run.operational_handoff?.state === "completed" && (
                          <section className="support-bundle-section recovery-section">
                            <div className="support-bundle-heading">
                              <div>
                                <span className="eyebrow">Recovery evidence</span>
                                <h3>Logical backup and restore validation</h3>
                              </div>
                              <span className="state-badge completed">C2 local backup</span>
                            </div>
                            <div className="support-bundle-controls recovery-controls">
                              <fieldset>
                                <legend>Logical components</legend>
                                {LOGICAL_BACKUP_COMPONENTS.map((componentId) => {
                                  const optional = componentId === "backup.identity-handoff" ||
                                    componentId === "backup.integration-validation";
                                  return (
                                    <label key={componentId}>
                                      <input
                                        type="checkbox"
                                        checked={backupComponentIds.includes(componentId)}
                                        disabled={!optional}
                                        onChange={(event) => {
                                          setBackupResult(null);
                                          setRestoreValidation(null);
                                          setBackupPending(false);
                                          setUpgradePending(false);
                                          setUpgradeJustification("");
                                          setUpgradeSimulation(null);
                                          setBackupComponentIds((current) =>
                                            event.target.checked
                                              ? [...current, componentId]
                                              : current.filter((item) => item !== componentId),
                                          );
                                        }}
                                      />
                                      <span>{componentId.replace("backup.", "").replaceAll("-", " ")}</span>
                                      {!optional && <small>Required</small>}
                                    </label>
                                  );
                                })}
                              </fieldset>
                            </div>
                            {backupPreviewQuery.isLoading && (
                              <div className="inline-state">
                                <RefreshCw className="spin" size={16} /> Building logical backup preview
                              </div>
                            )}
                            {backupPreviewQuery.isError && (
                              <div className="inline-error">
                                <AlertTriangle size={16} /> Backup preview is unavailable for this source.
                              </div>
                            )}
                            {backupPreview && !backupPending && !backupResult && (
                              <div className="data-initialization-action support-bundle-action">
                                <div>
                                  <strong>Backup preview passed</strong>
                                  <p>
                                    {backupPreview.entries.length} typed entries, {backupPreview.content_bytes}
                                    {" "}bytes; no secret or external transfer is authorized.
                                  </p>
                                </div>
                                <button type="button" onClick={() => setBackupPending(true)}>
                                  <Database size={14} /> Review backup
                                </button>
                              </div>
                            )}
                            {backupPending && backupPreview && (
                              <div className="data-initialization-confirmation support-bundle-confirmation"
                                role="dialog">
                                <div>
                                  <strong>Confirm local logical backup</strong>
                                  <p>
                                    Archive {backupPreview.target_state}; this stores only the reviewed
                                    Atlas-owned logical projection. It is not a production database backup.
                                  </p>
                                </div>
                                <div className="identity-plan-summary support-bundle-summary">
                                  <div><span>Entries</span><strong>{backupPreview.entries.length}</strong>
                                    <small>Strict versioned JSON</small></div>
                                  <div><span>Archive</span><strong>{backupPreview.archive_size_bytes} bytes</strong>
                                    <small>{backupPreview.archive_sha256.slice(0, 20)}...</small></div>
                                  <div><span>Classification</span><strong>Internal</strong>
                                    <small>No secret values</small></div>
                                  <div><span>Transfer</span><strong>Local only</strong>
                                    <small>External operation false</small></div>
                                </div>
                                <div className="identity-mapping-list support-entry-list">
                                  {backupPreview.entries.map((entry) => (
                                    <div key={entry.entry_id}>
                                      <div><code>{entry.entry_id}</code><small>{entry.file_name}</small></div>
                                      <strong>{entry.mandatory ? "required" : "selected"}</strong>
                                    </div>
                                  ))}
                                </div>
                                <label>
                                  Backup justification
                                  <input value={backupJustification} maxLength={500}
                                    onChange={(event) => setBackupJustification(event.target.value)}
                                    placeholder="Record the reviewed recovery evidence purpose" />
                                </label>
                                {backupMutation.isError && (
                                  <div className="inline-error"><AlertTriangle size={16} /> Backup was not created.</div>
                                )}
                                <div className="data-initialization-confirm-actions">
                                  <button type="button" onClick={() => {
                                    setBackupPending(false); setBackupJustification("");
                                  }}>Cancel</button>
                                  <button className="data-initialization-confirm" type="button"
                                    disabled={backupJustification.trim().length < 12 || backupMutation.isPending}
                                    onClick={() => backupMutation.mutate()}>
                                    <Database size={14} /> Confirm local backup
                                  </button>
                                </div>
                              </div>
                            )}
                            {backupResult && (
                              <div className="data-initialization-result completed support-bundle-result">
                                <div className="data-initialization-result-heading">
                                  <CheckCircle2 size={18} />
                                  <div><strong>Logical backup completed</strong><code>{backupResult.backup_id}</code></div>
                                  <span className="state-badge completed">local only</span>
                                </div>
                                <div className="data-initialization-summary">
                                  <div><span>Entries</span><strong>{backupResult.entry_count}</strong></div>
                                  <div><span>Archive bytes</span><strong>{backupResult.archive_size_bytes}</strong></div>
                                  <div><span>Reuse</span><strong>{backupResult.reused ? "Exact bytes" : "Published"}</strong></div>
                                  <div><span>Active restore</span><strong>No</strong></div>
                                </div>
                                <div className="service-state-evidence">
                                  <div><code>{backupResult.archive_name}</code><span>Integrity verified</span></div>
                                  <code>{backupResult.archive_sha256.slice(0, 20)}...</code>
                                </div>
                                {!restoreValidation && (
                                  <div className="data-initialization-action recovery-validation-action">
                                    <div><strong>Validate isolated restore</strong>
                                      <p>Reconstruct the projection in ephemeral memory without writing active state.</p>
                                    </div>
                                    <button type="button" disabled={restoreValidationMutation.isPending}
                                      onClick={() => restoreValidationMutation.mutate()}>
                                      <FlaskConical size={14} /> Validate restore
                                    </button>
                                  </div>
                                )}
                                {restoreValidationMutation.isError && (
                                  <div className="inline-error"><AlertTriangle size={16} /> Restore validation failed closed.</div>
                                )}
                                {restoreValidation && (
                                  <div className="recovery-validation-result">
                                    <CheckCircle2 size={18} />
                                    <div><strong>Isolated restore validation passed</strong>
                                      <p>{restoreValidation.check_ids.length} checks; no active repository write or operational recovery.</p>
                                      <code>{restoreValidation.validation_digest.slice(0, 20)}...</code>
                                    </div>
                                  </div>
                                )}
                                <p className="data-recovery-note">
                                  Retain only through {formatTimestamp(backupResult.expires_at)}.
                                  Production RPO, RTO, secret recovery, HA, and DR remain unvalidated.
                                </p>
                              </div>
                            )}
                            {restoreValidation && upgradeReadinessQuery.isLoading && (
                              <div className="inline-state">
                                <RefreshCw className="spin" size={16} /> Evaluating upgrade readiness
                              </div>
                            )}
                            {restoreValidation && upgradeReadinessQuery.isError && (
                              <div className="inline-error">
                                <AlertTriangle size={16} /> Upgrade readiness failed closed for this
                                evidence set.
                              </div>
                            )}
                            {upgradeReadiness && !upgradePending && !upgradeSimulation && (
                              <div className="upgrade-readiness-panel">
                                <div className="data-initialization-result-heading">
                                  <GitBranch size={18} />
                                  <div>
                                    <strong>Upgrade readiness passed</strong>
                                    <code>{upgradeReadiness.plan_id}</code>
                                  </div>
                                  <span className="state-badge completed">C1 preview</span>
                                </div>
                                <div className="data-initialization-summary">
                                  <div>
                                    <span>Readiness gates</span>
                                    <strong>
                                      {upgradeReadiness.readiness_checks.filter((item) => item.passed).length}/
                                      {upgradeReadiness.readiness_checks.length}
                                    </strong>
                                  </div>
                                  <div>
                                    <span>Release path</span>
                                    <strong>
                                      {upgradeReadiness.source_release_version} to {upgradeReadiness.target_release_version}
                                    </strong>
                                  </div>
                                  <div>
                                    <span>Downtime range</span>
                                    <strong>
                                      {upgradeReadiness.estimated_downtime_min_minutes}-
                                      {upgradeReadiness.estimated_downtime_max_minutes} min
                                    </strong>
                                  </div>
                                  <div>
                                    <span>Rollback window</span>
                                    <strong>{upgradeReadiness.rollback_window_minutes} min</strong>
                                  </div>
                                </div>
                                <div className="data-initialization-action upgrade-review-action">
                                  <div>
                                    <strong>Isolated abort and rollback model</strong>
                                    <p>
                                      {upgradeReadiness.migration_steps.length} reversible migrations;
                                      production authorization remains disabled.
                                    </p>
                                  </div>
                                  <button type="button" onClick={() => setUpgradePending(true)}>
                                    <FlaskConical size={14} /> Review simulation
                                  </button>
                                </div>
                              </div>
                            )}
                            {upgradePending && upgradeReadiness && (
                              <div className="data-initialization-confirmation upgrade-confirmation"
                                role="dialog">
                                <div>
                                  <strong>Confirm isolated upgrade rollback simulation</strong>
                                  <p>
                                    This models the reviewed release path, injects an abort, and
                                    evaluates rollback without acquiring artifacts or changing services.
                                  </p>
                                </div>
                                <div className="identity-plan-summary upgrade-plan-summary">
                                  <div><span>Source</span><strong>{upgradeReadiness.source_release_version}</strong>
                                    <small>{upgradeReadiness.source_schema_version}</small></div>
                                  <div><span>Target</span><strong>{upgradeReadiness.target_release_version}</strong>
                                    <small>{upgradeReadiness.target_schema_version}</small></div>
                                  <div><span>Services</span><strong>{upgradeReadiness.service_dependency_ids.length}</strong>
                                    <small>No restart authorized</small></div>
                                  <div><span>Execution</span><strong>Isolated only</strong>
                                    <small>Active state false</small></div>
                                </div>
                                <div className="identity-mapping-list upgrade-migration-list">
                                  {upgradeReadiness.migration_steps.map((step) => (
                                    <div key={step.step_id}>
                                      <div><code>{step.step_id}</code>
                                        <small>{step.migration_kind.replaceAll("_", " ")} · {step.estimated_minutes} min</small></div>
                                      <strong>{step.reversible ? "reversible" : "forward only"}</strong>
                                    </div>
                                  ))}
                                </div>
                                <div className="upgrade-policy-columns">
                                  <div><strong>Abort criteria</strong>
                                    {upgradeReadiness.abort_criterion_ids.map((item) => <code key={item}>{item}</code>)}</div>
                                  <div><strong>Rollback sequence</strong>
                                    {upgradeReadiness.rollback_step_ids.map((item) => <code key={item}>{item}</code>)}</div>
                                </div>
                                <label>
                                  Upgrade simulation justification
                                  <input value={upgradeJustification} maxLength={500}
                                    onChange={(event) => setUpgradeJustification(event.target.value)}
                                    placeholder="Record why this isolated rollback path is being reviewed" />
                                </label>
                                {upgradeSimulationMutation.isError && (
                                  <div className="inline-error">
                                    <AlertTriangle size={16} /> Upgrade simulation failed closed.
                                  </div>
                                )}
                                <div className="data-initialization-confirm-actions">
                                  <button type="button" onClick={() => {
                                    setUpgradePending(false); setUpgradeJustification("");
                                  }}>Cancel</button>
                                  <button className="data-initialization-confirm" type="button"
                                    disabled={upgradeJustification.trim().length < 12 ||
                                      upgradeSimulationMutation.isPending}
                                    onClick={() => upgradeSimulationMutation.mutate()}>
                                    <FlaskConical size={14} /> Confirm isolated simulation
                                  </button>
                                </div>
                              </div>
                            )}
                            {upgradeSimulation && (
                              <div className="upgrade-simulation-result">
                                <div className="data-initialization-result-heading">
                                  <CheckCircle2 size={18} />
                                  <div><strong>Upgrade rollback simulation passed</strong>
                                    <code>{upgradeSimulation.simulation_id}</code></div>
                                  <span className="state-badge completed">isolated</span>
                                </div>
                                <div className="data-initialization-summary">
                                  <div><span>Timeline</span><strong>{upgradeSimulation.steps.length} steps</strong></div>
                                  <div><span>Modeled downtime</span><strong>{upgradeSimulation.estimated_downtime_minutes} min</strong></div>
                                  <div><span>Production authorization</span><strong>No</strong></div>
                                  <div><span>Active execution</span><strong>No</strong></div>
                                </div>
                                <div className="upgrade-timeline">
                                  {upgradeSimulation.steps.map((step) => (
                                    <div key={step.step_id}>
                                      <span>{step.sequence}</span>
                                      <div><code>{step.step_id}</code><small>{step.result_code}</small></div>
                                      <strong>{step.simulated_minutes} min</strong>
                                    </div>
                                  ))}
                                </div>
                                <div className="recovery-validation-result">
                                  <ShieldCheck size={18} />
                                  <div><strong>Abort injected; rollback applicable</strong>
                                    <p>
                                      {upgradeSimulation.post_verification_check_ids.length} source-release
                                      checks modeled with no network request or infrastructure mutation.
                                    </p>
                                    <code>{upgradeSimulation.simulation_digest.slice(0, 20)}...</code>
                                  </div>
                                </div>
                                {!changeReviewPacket && (
                                  <div className="data-initialization-action upgrade-review-action">
                                    <div>
                                      <strong>Prepare change review packet</strong>
                                      <p>
                                        Reconcile this exact plan and simulation into a local,
                                        non-authorizing ITSM draft.
                                      </p>
                                    </div>
                                    <button
                                      type="button"
                                      disabled={changeReviewPreviewMutation.isPending}
                                      onClick={() => changeReviewPreviewMutation.mutate()}
                                    >
                                      <FileText size={14} /> Review change packet
                                    </button>
                                  </div>
                                )}
                                {changeReviewPreviewMutation.isError && (
                                  <div className="inline-error">
                                    <AlertTriangle size={16} /> Change evidence failed closed.
                                  </div>
                                )}
                              </div>
                            )}
                            {changeReviewPending && changeReviewPreview && (
                              <div
                                className="data-initialization-confirmation change-review-confirmation"
                                role="dialog"
                                aria-label="Confirm upgrade change review packet"
                              >
                                <div>
                                  <strong>Confirm upgrade change review packet</strong>
                                  <p>
                                    This records evidence for human review. It grants no approval,
                                    dispatch, notification, workflow, or execution authority.
                                  </p>
                                </div>
                                <div className="identity-plan-summary upgrade-plan-summary">
                                  <div>
                                    <span>Classification</span>
                                    <strong>Medium risk</strong>
                                    <small>Reviewed standard change</small>
                                  </div>
                                  <div>
                                    <span>Services</span>
                                    <strong>{changeReviewPreview.impacted_service_ids.length}</strong>
                                    <small>{changeReviewPreview.impacted_service_ids.join(", ")}</small>
                                  </div>
                                  <div>
                                    <span>Interruption</span>
                                    <strong>
                                      {changeReviewPreview.estimated_downtime_min_minutes}-
                                      {changeReviewPreview.estimated_downtime_max_minutes} min
                                    </strong>
                                    <small>Estimate only</small>
                                  </div>
                                  <div>
                                    <span>Evidence</span>
                                    <strong>{changeReviewPreview.evidence_digests.length} digests</strong>
                                    <small>Exact plan and simulation</small>
                                  </div>
                                </div>
                                <div className="upgrade-policy-columns">
                                  <div>
                                    <strong>Residual risks</strong>
                                    {changeReviewPreview.residual_risk_ids.map((item) => (
                                      <code key={item}>{item}</code>
                                    ))}
                                  </div>
                                  <div>
                                    <strong>Required owners</strong>
                                    {changeReviewPreview.owner_role_ids.map((item) => (
                                      <code key={item}>{item}</code>
                                    ))}
                                  </div>
                                </div>
                                <div className="change-review-window">
                                  <label>
                                    Proposed UTC-aware start
                                    <input
                                      type="datetime-local"
                                      value={changeReviewWindowStart}
                                      onChange={(event) =>
                                        setChangeReviewWindowStart(event.target.value)
                                      }
                                    />
                                  </label>
                                  <label>
                                    Proposed UTC-aware end
                                    <input
                                      type="datetime-local"
                                      value={changeReviewWindowEnd}
                                      onChange={(event) =>
                                        setChangeReviewWindowEnd(event.target.value)
                                      }
                                    />
                                  </label>
                                </div>
                                <label>
                                  Change review justification
                                  <input
                                    value={changeReviewJustification}
                                    maxLength={500}
                                    onChange={(event) =>
                                      setChangeReviewJustification(event.target.value)
                                    }
                                    placeholder="Record why this packet is being prepared for review"
                                  />
                                </label>
                                <label className="change-review-acknowledgement">
                                  <input
                                    type="checkbox"
                                    checked={changeReviewAcknowledged}
                                    onChange={(event) =>
                                      setChangeReviewAcknowledged(event.target.checked)
                                    }
                                  />
                                  <span>
                                    I acknowledge this packet does not approve or execute the change.
                                  </span>
                                </label>
                                {changeReviewPacketMutation.isError && (
                                  <div className="inline-error">
                                    <AlertTriangle size={16} /> Change packet creation failed closed.
                                  </div>
                                )}
                                <div className="data-initialization-confirm-actions">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setChangeReviewPending(false);
                                      setChangeReviewJustification("");
                                      setChangeReviewAcknowledged(false);
                                    }}
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    className="data-initialization-confirm"
                                    type="button"
                                    disabled={
                                      changeReviewJustification.trim().length < 12 ||
                                      !changeReviewWindowStart ||
                                      !changeReviewWindowEnd ||
                                      !changeReviewAcknowledged ||
                                      changeReviewPacketMutation.isPending
                                    }
                                    onClick={() => changeReviewPacketMutation.mutate()}
                                  >
                                    <FileText size={14} /> Create review packet
                                  </button>
                                </div>
                              </div>
                            )}
                            {changeReviewPacket && (
                              <div className="change-review-result">
                                <div className="data-initialization-result-heading">
                                  <CheckCircle2 size={18} />
                                  <div>
                                    <strong>Upgrade change review packet created</strong>
                                    <code>{changeReviewPacket.packet_id}</code>
                                  </div>
                                  <span className="state-badge completed">local draft</span>
                                </div>
                                <div className="data-initialization-summary">
                                  <div>
                                    <span>Approval granted</span>
                                    <strong>No</strong>
                                  </div>
                                  <div>
                                    <span>ITSM dispatched</span>
                                    <strong>No</strong>
                                  </div>
                                  <div>
                                    <span>Execution authorized</span>
                                    <strong>No</strong>
                                  </div>
                                  <div>
                                    <span>Evidence retained</span>
                                    <strong>{changeReviewPacket.evidence_digests.length}</strong>
                                  </div>
                                </div>
                                <div className="recovery-validation-result">
                                  <ShieldCheck size={18} />
                                  <div>
                                    <strong>{changeReviewPacket.itsm_draft_title}</strong>
                                    <p>
                                      Immutable local review record; human CAB and service-owner
                                      decisions remain outstanding.
                                    </p>
                                    <code>{changeReviewPacket.packet_digest.slice(0, 20)}...</code>
                                  </div>
                                </div>
                                {!humanReview && !humanReviewPending && (
                                  <div className="data-initialization-action upgrade-review-action">
                                    <div>
                                      <strong>Route to separated human review</strong>
                                      <p>
                                        Create four ordered local review stages bound to this exact
                                        packet. No external approval or execution authority is issued.
                                      </p>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setHumanReviewJustification("");
                                        setHumanReviewAcknowledged(false);
                                        setHumanReviewPending(true);
                                      }}
                                    >
                                      <UserCheck size={14} /> Review routing
                                    </button>
                                  </div>
                                )}
                                {humanReviewPending && (
                                  <div
                                    className="data-initialization-confirmation human-review-confirmation"
                                    role="dialog"
                                    aria-label="Confirm separated human review"
                                  >
                                    <div>
                                      <strong>Confirm separated human review</strong>
                                      <p>
                                        The requester cannot decide any stage. Four distinct eligible
                                        humans must review the unchanged packet in order.
                                      </p>
                                    </div>
                                    <div className="human-review-stage-preview">
                                      {changeReviewPacket.owner_role_ids.map((roleId, index) => (
                                        <div key={roleId}>
                                          <span>{index + 1}</span>
                                          <div>
                                            <strong>{roleId.replaceAll(".", " ")}</strong>
                                            <small>One distinct human · exact packet digest</small>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                    <label>
                                      Review routing justification
                                      <input
                                        value={humanReviewJustification}
                                        maxLength={500}
                                        onChange={(event) =>
                                          setHumanReviewJustification(event.target.value)
                                        }
                                        placeholder="Record why these accountable reviews are required"
                                      />
                                    </label>
                                    <label className="change-review-acknowledgement">
                                      <input
                                        type="checkbox"
                                        checked={humanReviewAcknowledged}
                                        onChange={(event) =>
                                          setHumanReviewAcknowledged(event.target.checked)
                                        }
                                      />
                                      <span>
                                        I acknowledge review completion will not authorize execution.
                                      </span>
                                    </label>
                                    {humanReviewMutation.isError && (
                                      <div className="inline-error">
                                        <AlertTriangle size={16} /> Human review creation failed closed.
                                      </div>
                                    )}
                                    <div className="data-initialization-confirm-actions">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setHumanReviewPending(false);
                                          setHumanReviewJustification("");
                                          setHumanReviewAcknowledged(false);
                                        }}
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        className="data-initialization-confirm"
                                        type="button"
                                        disabled={
                                          humanReviewJustification.trim().length < 12 ||
                                          !humanReviewAcknowledged ||
                                          humanReviewMutation.isPending
                                        }
                                        onClick={() => humanReviewMutation.mutate()}
                                      >
                                        <UserCheck size={14} /> Create review stages
                                      </button>
                                    </div>
                                  </div>
                                )}
                                {humanReview && (
                                  <div className="human-review-result">
                                    <div className="human-review-heading">
                                      <UserCheck size={18} />
                                      <div>
                                        <strong>Separated human review created</strong>
                                        <code>{humanReview.review_id}</code>
                                      </div>
                                      <span className="state-badge pending">{humanReview.state}</span>
                                    </div>
                                    <div className="human-review-stages">
                                      {humanReview.stages.map((stage) => (
                                        <div key={stage.stage_id} data-state={stage.state}>
                                          <span>{stage.sequence}</span>
                                          <div>
                                            <strong>{stage.required_role_id.replaceAll(".", " ")}</strong>
                                            <code>{stage.stage_id}</code>
                                          </div>
                                          <small>{stage.state.replaceAll("_", " ")}</small>
                                        </div>
                                      ))}
                                    </div>
                                    <div className="human-review-boundary">
                                      <LockKeyhole size={17} />
                                      <div>
                                        <strong>Requester is ineligible to self-review</strong>
                                        <p>
                                          Approval, ITSM dispatch, handoff, workflow, and execution
                                          authorization remain No. Packet changes invalidate review.
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </section>
                        )}
                    </>
                  )}
                  {bootstrapPlan && deploymentConfiguration && identity && (
                    <BootstrapLeaseWorkspace
                      configuration={deploymentConfiguration}
                      plan={bootstrapPlan}
                      scope={identity.scope}
                      state={bootstrapState}
                    />
                  )}
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>
                      A confirmed acquisition may change only the governed Atlas artifact store. No
                      configuration, service, rollback, connector, or infrastructure operation is
                      authorized.
                    </span>
                  </div>
                    </section>
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {activeNavigation === "Health" &&
                activeHealthView === "deployments" &&
                bootstrapInvalidation && (
                <WorkspaceLoadBoundary
                  compact
                  resetKey={bootstrapInvalidation.preview_id}
                  workspace="Health"
                >
                  <Suspense
                    fallback={
                      <div className="workspace-message" aria-live="polite" aria-busy="true">
                        <Clock3 size={22} />
                        <div>
                          <h2>Loading Bootstrap Invalidation</h2>
                          <p>Preparing authorized checkpoint drift evidence.</p>
                        </div>
                      </div>
                    }
                  >
                    <section className="workspace-section bootstrap-invalidation-section">
                      <BootstrapInvalidationWorkspace preview={bootstrapInvalidation} />
                      {bootstrapInvalidation.state !== "empty" && (
                        <>
                      {bootstrapInvalidation.state === "drifted" &&
                        bootstrapState?.run &&
                        bootstrapState.lease_held_by_current_actor &&
                        bootstrapInvalidation.source_run_version === bootstrapState.run.version &&
                        !bootstrapRebasePending && (
                          <div className="bootstrap-rebase-action">
                            <div>
                              <strong>Apply the reviewed checkpoint boundary</strong>
                              <p>
                                This updates Atlas coordination metadata only. It does not run any
                                deployment phase.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                setBootstrapRebaseResult(null);
                                setBootstrapRebasePending(true);
                              }}
                            >
                              <RefreshCw size={14} /> Review plan update
                            </button>
                          </div>
                        )}
                      {bootstrapRebasePending && bootstrapState?.run && (
                        <div className="bootstrap-rebase-confirmation" role="dialog">
                          <div>
                            <strong>Confirm checkpoint metadata update</strong>
                            <p>
                              Revision {bootstrapState.run.version} will move to the candidate plan.
                              Only checkpoints before {" "}
                              {bootstrapInvalidation.earliest_affected_phase_id} remain reusable.
                            </p>
                          </div>
                          <label>
                            Review justification
                            <input
                              value={bootstrapRebaseJustification}
                              maxLength={500}
                              onChange={(event) =>
                                setBootstrapRebaseJustification(event.target.value)
                              }
                              placeholder="Record the reviewed reason for this plan update"
                            />
                          </label>
                          {bootstrapRebaseMutation.isError && (
                            <div className="impact-message impact-error">
                              <AlertTriangle size={16} /> The checkpoint update was not completed.
                            </div>
                          )}
                          <div className="bootstrap-rebase-confirm-actions">
                            <button
                              type="button"
                              onClick={() => {
                                setBootstrapRebasePending(false);
                                setBootstrapRebaseJustification("");
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              className="bootstrap-rebase-confirm"
                              type="button"
                              disabled={
                                bootstrapRebaseJustification.trim().length < 12 ||
                                bootstrapRebaseMutation.isPending
                              }
                              onClick={() => bootstrapRebaseMutation.mutate()}
                            >
                              <RefreshCw size={14} /> Confirm checkpoint update
                            </button>
                          </div>
                        </div>
                      )}
                      {bootstrapRebaseResult && (
                        <div className="bootstrap-rebase-result" role="status">
                          <CheckCircle2 size={18} />
                          <div>
                            <strong>
                              Plan metadata updated to revision {bootstrapRebaseResult.run.version}
                            </strong>
                            <p>
                              Preserved: {" "}
                              {bootstrapRebaseResult.preserved_checkpoint_phase_ids.join(", ") ||
                                "None"}
                              . Invalidated: {" "}
                              {bootstrapRebaseResult.invalidated_checkpoint_phase_ids.join(", ") ||
                                "None"}
                              .
                            </p>
                          </div>
                        </div>
                      )}
                        </>
                      )}
                      <div className="safety-notice">
                        <ShieldCheck size={16} />
                        <span>
                          Preview is read-only. A confirmed plan update changes checkpoint metadata
                          only; no lease, file, phase, rollback, or infrastructure operation is
                          authorized.
                        </span>
                      </div>
                    </section>
                  </Suspense>
                </WorkspaceLoadBoundary>
              )}

              {overview && (
                <>
                  {activeHealthView === "governance" &&
                    identity &&
                    identity.authentication.method !== "development" && (
                    <section className="workspace-section session-section">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">SESSION SECURITY</p>
                          <h2>Browser sessions</h2>
                        </div>
                        <span className="session-count">
                          {sessions?.length ?? 0}{sessionInventory?.truncated ? "+" : ""} visible
                        </span>
                      </div>
                      {sessionsQuery.isLoading && (
                        <div className="impact-message">
                          <Clock3 size={18} /> Reading authorized session inventory
                        </div>
                      )}
                      {sessionsQuery.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> Session inventory is unavailable.
                        </div>
                      )}
                      {revokeSessionMutation.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> Session revocation was not completed.
                        </div>
                      )}
                      {sessions?.length === 0 && (
                        <div className="impact-message">No browser sessions are visible.</div>
                      )}
                      {sessions && sessions.length > 0 && (
                        <div className="session-list">
                          {sessions.map((session) => (
                            <div className="session-row" key={session.session_id}>
                              <div className="session-icon"><Monitor size={17} /></div>
                              <div className="session-detail">
                                <strong>{session.current ? "Current session" : "Browser session"}</strong>
                                <span>Last active {formatTimestamp(session.last_seen_at)}</span>
                              </div>
                              <div className="session-expiry">
                                <span>Expires</span>
                                <strong>{formatTimestamp(session.idle_expires_at)}</strong>
                              </div>
                              <span className={`state-badge ${session.state}`}>{session.state}</span>
                              {session.state === "active" && (
                                <button
                                  className="icon-button session-revoke"
                                  type="button"
                                  aria-label={
                                    session.current ? "Revoke current session" : "Revoke browser session"
                                  }
                                  title="Revoke session"
                                  disabled={revokeSessionMutation.isPending}
                                  onClick={() => revokeSessionMutation.mutate(session.session_id)}
                                >
                                  <Trash2 size={17} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {activeHealthView === "governance" &&
                    identity &&
                    identity.authentication.method !== "development" && (
                    <section className="workspace-section api-credential-section">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">API ACCESS</p>
                          <h2>Personal read-only tokens</h2>
                        </div>
                        <span className="session-count">
                          {apiCredentials?.filter((item) => item.state === "active").length ?? 0}
                          {apiCredentialInventory?.truncated ? "+" : ""} active
                        </span>
                      </div>

                      {apiCredentialsQuery.isLoading && (
                        <div className="impact-message">
                          <Clock3 size={18} /> Reading authorized API access
                        </div>
                      )}
                      {apiCredentialsQuery.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> API access is unavailable.
                        </div>
                      )}

                      {issuedApiToken && (
                        <div className="issued-token" role="status">
                          <div className="issued-token-heading">
                            <div>
                              <span>NEW TOKEN</span>
                              <strong>Available once</strong>
                            </div>
                            <button
                              className="icon-button"
                              type="button"
                              aria-label="Dismiss API token"
                              title="Dismiss token"
                              onClick={() => setIssuedApiToken(null)}
                            >
                              <X size={17} />
                            </button>
                          </div>
                          <div className="issued-token-value">
                            <code>{issuedApiToken}</code>
                            <button
                              className="icon-button"
                              type="button"
                              aria-label="Copy API token"
                              title="Copy token"
                              onClick={() => void navigator.clipboard.writeText(issuedApiToken)}
                            >
                              <Copy size={17} />
                            </button>
                          </div>
                        </div>
                      )}

                      {apiCredentialInventory && (
                        <form
                          className="api-credential-form"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (
                              apiCredentialName.trim() &&
                              apiCredentialPurpose.trim() &&
                              selectedApiGrants.length > 0 &&
                              !createApiCredentialMutation.isPending
                            ) {
                              createApiCredentialMutation.mutate();
                            }
                          }}
                        >
                          <div className="api-credential-fields">
                            <label>
                              <span>Name</span>
                              <input
                                value={apiCredentialName}
                                onChange={(event) => setApiCredentialName(event.target.value)}
                                maxLength={80}
                                required
                              />
                            </label>
                            <label>
                              <span>Purpose</span>
                              <input
                                value={apiCredentialPurpose}
                                onChange={(event) => setApiCredentialPurpose(event.target.value)}
                                maxLength={240}
                                required
                              />
                            </label>
                            <label>
                              <span>Lifetime</span>
                              <select
                                value={apiCredentialLifetime}
                                onChange={(event) =>
                                  setApiCredentialLifetime(Number(event.target.value))
                                }
                              >
                                <option value={5}>5 minutes</option>
                                <option value={15}>15 minutes</option>
                                <option value={30}>30 minutes</option>
                                <option value={60}>60 minutes</option>
                              </select>
                            </label>
                          </div>
                          <fieldset className="api-grant-options">
                            <legend>Read access</legend>
                            {availableApiGrants.map((grant) => (
                              <label key={grant.permission_id}>
                                <input
                                  type="checkbox"
                                  checked={selectedApiGrants.includes(grant.permission_id)}
                                  onChange={(event) =>
                                    setSelectedApiGrants((current) =>
                                      event.target.checked
                                        ? [...current, grant.permission_id]
                                        : current.filter((item) => item !== grant.permission_id),
                                    )
                                  }
                                />
                                <span>{apiGrantLabel(grant.permission_id)}</span>
                              </label>
                            ))}
                          </fieldset>
                          <div className="api-credential-submit">
                            <span>Read-only · expires automatically</span>
                            <button
                              className="run-check-button"
                              type="submit"
                              disabled={
                                createApiCredentialMutation.isPending ||
                                !apiCredentialName.trim() ||
                                !apiCredentialPurpose.trim() ||
                                selectedApiGrants.length === 0
                              }
                            >
                              {createApiCredentialMutation.isPending ? (
                                <RefreshCw className="spin" size={16} />
                              ) : (
                                <KeyRound size={16} />
                              )}
                              Create token
                            </button>
                          </div>
                        </form>
                      )}

                      {(createApiCredentialMutation.isError ||
                        revokeApiCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> API access change was not completed.
                        </div>
                      )}

                      {apiCredentials?.length === 0 && (
                        <div className="impact-message">No personal API tokens are visible.</div>
                      )}
                      {apiCredentials && apiCredentials.length > 0 && (
                        <div className="api-credential-list">
                          {apiCredentials.map((credential) => (
                            <div className="api-credential-row" key={credential.credential_id}>
                              <div className="session-icon"><KeyRound size={17} /></div>
                              <div className="api-credential-detail">
                                <strong>{credential.display_name}</strong>
                                <span>{credential.purpose}</span>
                                <small>
                                  {credential.grants.map((grant) =>
                                    apiGrantLabel(grant.permission_id),
                                  ).join(" · ")}
                                </small>
                              </div>
                              <div className="session-expiry">
                                <span>Expires</span>
                                <strong>{formatTimestamp(credential.expires_at)}</strong>
                              </div>
                              <span className={`state-badge ${credential.state}`}>
                                {credential.state}
                              </span>
                              {credential.state === "active" && (
                                <button
                                  className="icon-button session-revoke"
                                  type="button"
                                  aria-label={`Revoke ${credential.display_name}`}
                                  title="Revoke token"
                                  disabled={revokeApiCredentialMutation.isPending}
                                  onClick={() =>
                                    revokeApiCredentialMutation.mutate(
                                      credential.credential_id,
                                    )
                                  }
                                >
                                  <Trash2 size={17} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {activeHealthView === "governance" && identity && (
                    <WorkspaceLoadBoundary
                      compact
                      resetKey={identity.subject_id}
                      workspace="Health"
                    >
                      <Suspense
                        fallback={
                          <div className="workspace-message" aria-live="polite" aria-busy="true">
                            <Clock3 size={22} />
                            <div>
                              <h2>Loading ITSM integration readiness</h2>
                              <p>Preparing authorized configuration and blocker inventory.</p>
                            </div>
                          </div>
                        }
                      >
                        <ItsmIntegrationReadinessWorkspace
                          governedSessionAvailable={
                            identity.credential_kind === "browser_session"
                          }
                          onRequestEnterpriseLogin={() => setEnterpriseLoginRequested(true)}
                        />
                      </Suspense>
                    </WorkspaceLoadBoundary>
                  )}

                  {activeHealthView === "governance" && identityGovernance && (
                    <section className="workspace-section identity-governance-section">
                      <div className="section-heading governance-heading">
                        <div>
                          <p className="eyebrow">IDENTITY GOVERNANCE</p>
                          <h2>Administrative access review</h2>
                        </div>
                        <span className="session-count">
                          {identityGovernance.subjects.length} identities {" · "}
                          {identityGovernance.sessions.length +
                            identityGovernance.api_credentials.length}
                          {identityGovernance.truncated ? "+" : ""} active
                        </span>
                      </div>

                      <div className="governance-toolbar">
                        <label>
                          <span>Search identities and credentials</span>
                          <div className="governance-input">
                            <Search size={15} />
                            <input
                              aria-label="Search identity governance"
                              value={governanceSearch}
                              maxLength={128}
                              placeholder="Subject, provider, session, or token name"
                              onChange={(event) => setGovernanceSearch(event.target.value)}
                            />
                          </div>
                        </label>
                        <label>
                          <span>Governance reason</span>
                          <input
                            aria-label="Identity governance revocation reason"
                            value={governanceReason}
                            maxLength={240}
                            placeholder="Required for revocation or identity disablement"
                            onChange={(event) => setGovernanceReason(event.target.value)}
                          />
                        </label>
                      </div>

                      {(disableGovernedIdentityMutation.isError ||
                        revokeGovernedSessionMutation.isError ||
                        revokeGovernedApiCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> The administrative identity change was not
                          completed; prior access state remains authoritative.
                        </div>
                      )}

                      <div className="governance-panel governance-subject-panel">
                        <div className="governance-panel-heading">
                          <div>
                            <UserCheck size={17} />
                            <h3>Enterprise identities</h3>
                          </div>
                          <span>{identityGovernance.subjects.length}</span>
                        </div>
                        {identityGovernance.subjects.length === 0 && (
                          <div className="governance-empty">No matching enterprise identities.</div>
                        )}
                        <div className="governance-subject-records">
                          {identityGovernance.subjects.map((governedSubject) => {
                            const confirming =
                              pendingDisableSubjectId === governedSubject.subject_id;
                            return (
                              <article
                                className="governance-record governance-subject-record"
                                key={governedSubject.subject_id}
                              >
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{governedSubject.display_name}</strong>
                                    <span>{governedSubject.subject_id}</span>
                                  </div>
                                  <span className={`state-badge ${governedSubject.state}`}>
                                    {governedSubject.state}
                                  </span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{governedSubject.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Browser sessions</dt>
                                    <dd>{governedSubject.active_session_count} active</dd>
                                  </div>
                                  <div>
                                    <dt>Personal tokens</dt>
                                    <dd>{governedSubject.active_api_credential_count} active</dd>
                                  </div>
                                  <div>
                                    <dt>Observed</dt>
                                    <dd>{formatTimestamp(governedSubject.observed_at)}</dd>
                                  </div>
                                </dl>
                                {governedSubject.disabled_at && (
                                  <p>
                                    Disabled {formatTimestamp(governedSubject.disabled_at)}. New
                                    authentication and personal-token issuance remain blocked.
                                  </p>
                                )}
                                {confirming && governedSubject.state === "active" && (
                                  <div className="governance-disable-confirmation" role="dialog">
                                    <div>
                                      <strong>Confirm identity disablement</strong>
                                      <p>
                                        This disables {governedSubject.display_name} and atomically
                                        revokes {governedSubject.active_session_count} browser
                                        session(s) and {" "}
                                        {governedSubject.active_api_credential_count} personal
                                        token(s). Re-enable is not part of this slice.
                                      </p>
                                    </div>
                                    <div className="governance-confirm-actions">
                                      <button
                                        type="button"
                                        onClick={() => setPendingDisableSubjectId(null)}
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        className="governance-disable-confirm"
                                        type="button"
                                        disabled={
                                          !governanceReason.trim() ||
                                          disableGovernedIdentityMutation.isPending
                                        }
                                        onClick={() =>
                                          disableGovernedIdentityMutation.mutate({
                                            subjectId: governedSubject.subject_id,
                                            expectedVersion: governedSubject.version,
                                            reason: governanceReason.trim(),
                                            idempotencyKey: governanceIdempotencyKey(
                                              "identity",
                                              governedSubject.version,
                                            ),
                                          })
                                        }
                                      >
                                        <UserX size={14} /> Confirm disablement
                                      </button>
                                    </div>
                                  </div>
                                )}
                                <div className="governance-record-footer">
                                  <code>
                                    {governedSubject.authentication_method} · v
                                    {governedSubject.version}
                                  </code>
                                  {governedSubject.state === "active" && !confirming && (
                                    <button
                                      className="governance-revoke"
                                      type="button"
                                      disabled={disableGovernedIdentityMutation.isPending}
                                      onClick={() =>
                                        setPendingDisableSubjectId(governedSubject.subject_id)
                                      }
                                    >
                                      <UserX size={14} /> Disable identity
                                    </button>
                                  )}
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      </div>

                      <div className="governance-grid">
                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <Monitor size={17} />
                              <h3>Browser sessions</h3>
                            </div>
                            <span>{identityGovernance.sessions.length}</span>
                          </div>
                          {identityGovernance.sessions.length === 0 && (
                            <div className="governance-empty">No matching sessions.</div>
                          )}
                          <div className="governance-records">
                            {identityGovernance.sessions.map((session) => (
                              <article className="governance-record" key={session.session_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{session.subject_display_name}</strong>
                                    <span>{session.subject_id}</span>
                                  </div>
                                  <span className="state-badge active">active</span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{session.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Last active</dt>
                                    <dd>{formatTimestamp(session.last_seen_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Idle expiry</dt>
                                    <dd>{formatTimestamp(session.idle_expires_at)}</dd>
                                  </div>
                                </dl>
                                <div className="governance-record-footer">
                                  <code>{session.session_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={
                                      !governanceReason.trim() ||
                                      revokeGovernedSessionMutation.isPending
                                    }
                                    onClick={() =>
                                      revokeGovernedSessionMutation.mutate({
                                        sessionId: session.session_id,
                                        expectedVersion: session.version,
                                        reason: governanceReason.trim(),
                                        idempotencyKey: governanceIdempotencyKey(
                                          "session",
                                          session.version,
                                        ),
                                      })
                                    }
                                  >
                                    <Trash2 size={14} /> Revoke session
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <KeyRound size={17} />
                              <h3>Personal API tokens</h3>
                            </div>
                            <span>{identityGovernance.api_credentials.length}</span>
                          </div>
                          {identityGovernance.api_credentials.length === 0 && (
                            <div className="governance-empty">No matching personal tokens.</div>
                          )}
                          <div className="governance-records">
                            {identityGovernance.api_credentials.map((credential) => (
                              <article
                                className="governance-record"
                                key={credential.credential_id}
                              >
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{credential.display_name}</strong>
                                    <span>
                                      {credential.subject_display_name} {" · "}
                                      {credential.subject_id}
                                    </span>
                                  </div>
                                  <span className="state-badge active">active</span>
                                </div>
                                <p>{credential.purpose}</p>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{credential.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Grant</dt>
                                    <dd>
                                      {credential.grants
                                        .map((grant) => apiGrantLabel(grant.permission_id))
                                        .join(" · ")}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt>Expires</dt>
                                    <dd>{formatTimestamp(credential.expires_at)}</dd>
                                  </div>
                                </dl>
                                <div className="governance-record-footer">
                                  <code>{credential.credential_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={
                                      !governanceReason.trim() ||
                                      revokeGovernedApiCredentialMutation.isPending
                                    }
                                    onClick={() =>
                                      revokeGovernedApiCredentialMutation.mutate({
                                        credentialId: credential.credential_id,
                                        expectedVersion: credential.version,
                                        reason: governanceReason.trim(),
                                        idempotencyKey: governanceIdempotencyKey(
                                          "token",
                                          credential.version,
                                        ),
                                      })
                                    }
                                  >
                                    <Trash2 size={14} /> Revoke token
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>
                      </div>
                    </section>
                  )}

                  {activeHealthView === "governance" && workloadInventory && (
                    <section className="workspace-section workload-identity-section">
                      <div className="section-heading governance-heading">
                        <div>
                          <p className="eyebrow">WORKLOAD TRUST</p>
                          <h2>Platform workload identities</h2>
                          <p>
                            Short-lived service credentials with exact audience and environment
                            boundaries.
                          </p>
                        </div>
                        <span className="session-count">
                          {workloadInventory.identities.length} identities {" · "}
                          {workloadInventory.credentials.length}
                          {workloadInventory.truncated ? "+" : ""} credentials
                        </span>
                      </div>

                      <div className="governance-toolbar workload-toolbar">
                        <label>
                          <span>Search workload identities</span>
                          <div className="governance-input">
                            <Search size={15} />
                            <input
                              aria-label="Search workload identities"
                              value={workloadSearch}
                              maxLength={128}
                              placeholder="Service, instance, owner, or audience"
                              onChange={(event) => setWorkloadSearch(event.target.value)}
                            />
                          </div>
                        </label>
                        <label>
                          <span>Governance reason</span>
                          <input
                            aria-label="Workload identity governance reason"
                            value={workloadReason}
                            maxLength={240}
                            placeholder="Required for create, rotate, or revoke"
                            onChange={(event) => setWorkloadReason(event.target.value)}
                          />
                        </label>
                      </div>

                      {(createWorkloadIdentityMutation.isError ||
                        rotateWorkloadCredentialMutation.isError ||
                        revokeWorkloadCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> The workload identity change was not
                          completed; prior trust state remains authoritative.
                        </div>
                      )}

                      {issuedWorkloadToken && (
                        <div className="workload-token-once" role="status">
                          <div>
                            <KeyRound size={18} />
                            <div>
                              <strong>Credential shown once</strong>
                              <p>Store it in the approved secret manager before dismissing.</p>
                            </div>
                          </div>
                          <code>{issuedWorkloadToken}</code>
                          <div className="workload-token-actions">
                            <button
                              type="button"
                              title="Copy credential"
                              aria-label="Copy workload credential"
                              onClick={() => void navigator.clipboard?.writeText(issuedWorkloadToken)}
                            >
                              <Copy size={15} />
                            </button>
                            <button type="button" onClick={() => setIssuedWorkloadToken(null)}>
                              Dismiss
                            </button>
                          </div>
                        </div>
                      )}

                      <form
                        className="workload-create-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          setPendingWorkloadAction({ kind: "create" });
                        }}
                      >
                        <div className="governance-panel-heading">
                          <div>
                            <Server size={17} />
                            <h3>Register workload identity</h3>
                          </div>
                          <span>C2 governed</span>
                        </div>
                        <div className="workload-form-grid">
                          <label>
                            <span>Identity ID</span>
                            <input
                              aria-label="Workload identity ID"
                              value={workloadIdentityId}
                              onChange={(event) => setWorkloadIdentityId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Display name</span>
                            <input
                              aria-label="Workload display name"
                              value={workloadDisplayName}
                              onChange={(event) => setWorkloadDisplayName(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Service</span>
                            <input
                              aria-label="Workload service ID"
                              value={workloadServiceId}
                              onChange={(event) => setWorkloadServiceId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Instance</span>
                            <input
                              aria-label="Workload instance ID"
                              value={workloadInstanceId}
                              onChange={(event) => setWorkloadInstanceId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Owner</span>
                            <input
                              aria-label="Workload owner subject ID"
                              value={workloadOwnerId}
                              onChange={(event) => setWorkloadOwnerId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Audience</span>
                            <input
                              aria-label="Workload audience"
                              value={workloadAudience}
                              onChange={(event) => setWorkloadAudience(event.target.value)}
                            />
                          </label>
                          <label className="workload-form-wide">
                            <span>Secret reference</span>
                            <input
                              aria-label="Workload secret reference"
                              value={workloadSecretReference}
                              onChange={(event) => setWorkloadSecretReference(event.target.value)}
                            />
                          </label>
                          <label className="workload-form-wide">
                            <span>Purpose</span>
                            <input
                              aria-label="Workload purpose"
                              value={workloadPurpose}
                              onChange={(event) => setWorkloadPurpose(event.target.value)}
                            />
                          </label>
                        </div>
                        <button
                          className="governance-revoke workload-create-button"
                          type="submit"
                          disabled={
                            !workloadReason.trim() ||
                            !workloadIdentityId.trim() ||
                            createWorkloadIdentityMutation.isPending
                          }
                        >
                          <KeyRound size={14} /> Review creation
                        </button>
                      </form>

                      {pendingWorkloadAction?.kind === "create" && (
                        <div className="governance-disable-confirmation" role="dialog">
                          <div>
                            <strong>Confirm workload identity creation</strong>
                            <p>
                              Creates {workloadIdentityId} with one 10-minute credential for {" "}
                              {workloadAudience}. It receives no human role and no execution
                              authority.
                            </p>
                          </div>
                          <div className="governance-confirm-actions">
                            <button type="button" onClick={() => setPendingWorkloadAction(null)}>
                              Cancel
                            </button>
                            <button
                              className="governance-disable-confirm"
                              type="button"
                              onClick={() =>
                                createWorkloadIdentityMutation.mutate({
                                  identityId: workloadIdentityId.trim(),
                                  displayName: workloadDisplayName.trim(),
                                  serviceId: workloadServiceId.trim(),
                                  instanceId: workloadInstanceId.trim(),
                                  ownerSubjectId: workloadOwnerId.trim(),
                                  purpose: workloadPurpose.trim(),
                                  audience: workloadAudience.trim(),
                                  secretReferenceId: workloadSecretReference.trim(),
                                  lifetimeMinutes: 10,
                                  reason: workloadReason.trim(),
                                  idempotencyKey: governanceIdempotencyKey(
                                    "workload-create",
                                    1,
                                  ),
                                })
                              }
                            >
                              <ShieldCheck size={14} /> Confirm creation
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="governance-grid workload-grid">
                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <Server size={17} />
                              <h3>Service identities</h3>
                            </div>
                            <span>{workloadInventory.identities.length}</span>
                          </div>
                          {workloadInventory.identities.length === 0 && (
                            <div className="governance-empty">No matching workload identities.</div>
                          )}
                          <div className="governance-records">
                            {workloadInventory.identities.map((workload) => (
                              <article className="governance-record" key={workload.identity_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{workload.display_name}</strong>
                                    <span>{workload.identity_id}</span>
                                  </div>
                                  <span className={`state-badge ${workload.state}`}>
                                    {workload.state}
                                  </span>
                                </div>
                                <p>{workload.purpose}</p>
                                <dl>
                                  <div>
                                    <dt>Service / instance</dt>
                                    <dd>{workload.service_id} / {workload.instance_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Owner</dt>
                                    <dd>{workload.owner_subject_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Audience</dt>
                                    <dd>{workload.audiences.join(" · ")}</dd>
                                  </div>
                                </dl>
                                {pendingWorkloadAction?.kind === "rotate" &&
                                  pendingWorkloadAction.identityId === workload.identity_id && (
                                    <div className="governance-disable-confirmation" role="dialog">
                                      <div>
                                        <strong>Confirm credential rotation</strong>
                                        <p>
                                          Issues a new 10-minute credential. Existing active
                                          credentials retire after a two-minute overlap.
                                        </p>
                                      </div>
                                      <div className="governance-confirm-actions">
                                        <button
                                          type="button"
                                          onClick={() => setPendingWorkloadAction(null)}
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          className="governance-disable-confirm"
                                          type="button"
                                          onClick={() =>
                                            rotateWorkloadCredentialMutation.mutate({
                                              identityId: workload.identity_id,
                                              expectedVersion: workload.version,
                                              lifetimeMinutes: 10,
                                              overlapMinutes: 2,
                                              reason: workloadReason.trim(),
                                              idempotencyKey: governanceIdempotencyKey(
                                                "workload-rotate",
                                                workload.version,
                                              ),
                                            })
                                          }
                                        >
                                          <RefreshCw size={14} /> Confirm rotation
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                <div className="governance-record-footer">
                                  <code>v{workload.version} · {workload.environment_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={!workloadReason.trim()}
                                    onClick={() =>
                                      setPendingWorkloadAction({
                                        kind: "rotate",
                                        identityId: workload.identity_id,
                                        version: workload.version,
                                      })
                                    }
                                  >
                                    <RefreshCw size={14} /> Rotate credential
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <KeyRound size={17} />
                              <h3>Credential health</h3>
                            </div>
                            <span>{workloadInventory.credentials.length}</span>
                          </div>
                          {workloadInventory.credentials.length === 0 && (
                            <div className="governance-empty">No workload credentials issued.</div>
                          )}
                          <div className="governance-records">
                            {workloadInventory.credentials.map((credential) => (
                              <article className="governance-record" key={credential.credential_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{credential.identity_id}</strong>
                                    <span>{credential.credential_id}</span>
                                  </div>
                                  <span className={`state-badge ${credential.state}`}>
                                    {credential.state}
                                  </span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Audience</dt>
                                    <dd>{credential.audiences.join(" · ")}</dd>
                                  </div>
                                  <div>
                                    <dt>Expires</dt>
                                    <dd>{formatTimestamp(credential.expires_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Signing key</dt>
                                    <dd>version {credential.key_version}</dd>
                                  </div>
                                </dl>
                                {pendingWorkloadAction?.kind === "revoke" &&
                                  pendingWorkloadAction.credentialId ===
                                    credential.credential_id && (
                                    <div className="governance-disable-confirmation" role="dialog">
                                      <div>
                                        <strong>Confirm immediate revocation</strong>
                                        <p>
                                          This credential stops authenticating immediately. The
                                          workload must already have replacement trust.
                                        </p>
                                      </div>
                                      <div className="governance-confirm-actions">
                                        <button
                                          type="button"
                                          onClick={() => setPendingWorkloadAction(null)}
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          className="governance-disable-confirm"
                                          type="button"
                                          onClick={() =>
                                            revokeWorkloadCredentialMutation.mutate({
                                              credentialId: credential.credential_id,
                                              expectedVersion: credential.version,
                                              reason: workloadReason.trim(),
                                              idempotencyKey: governanceIdempotencyKey(
                                                "workload-revoke",
                                                credential.version,
                                              ),
                                            })
                                          }
                                        >
                                          <Trash2 size={14} /> Confirm revocation
                                        </button>
                                      </div>
                                    </div>
                                  )}
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
                              clearTechnicalReportSelection();
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
                              clearTechnicalReportSelection();
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
                          canReviewItsmHandoff={canReviewItsmHandoff}
                          canSubmitApproval={Boolean(recommendation?.preferred_option_id)}
                          itsmHandoffReview={itsmHandoffReview}
                          itsmHandoffReviewAcknowledged={itsmReviewAcknowledged}
                          itsmHandoffReviewError={
                            itsmHandoffReviewQuery.isError ||
                            itsmHandoffReviewMutation.isError
                          }
                          itsmHandoffReviewPending={
                            itsmHandoffReviewQuery.isLoading ||
                            itsmHandoffReviewMutation.isPending
                          }
                          itsmHandoffReviewRationale={itsmReviewRationale}
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
                          onItsmHandoffReviewAcknowledgedChange={
                            setItsmReviewAcknowledged
                          }
                          onItsmHandoffReviewRationaleChange={setItsmReviewRationale}
                          onDecideItsmHandoffReview={(outcome) => {
                            if (
                              technicalReport &&
                              itsmReviewAcknowledged &&
                              itsmReviewRationale.trim().length >= 5
                            ) {
                              itsmHandoffReviewMutation.mutate({
                                report: technicalReport,
                                outcome,
                                rationale: itsmReviewRationale.trim(),
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
                          reportError={reportMutation.isError || technicalReportQuery.isError}
                          reportPending={reportMutation.isPending || technicalReportQuery.isLoading}
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
                    clearTechnicalReportSelection();
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
                  <span>Authorized evidence · 24-hour UTC window · decision support only</span>
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
