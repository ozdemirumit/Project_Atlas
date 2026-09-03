# Project Atlas Architecture Decision Records

Architecture Decision Records capture significant implementation choices made under the approved Project Atlas documentation baseline.

## Lifecycle

- `Proposed`: under evaluation and not implementation authority.
- `Accepted`: approved for implementation.
- `Superseded`: replaced by a later ADR that links back to the prior decision.
- `Deprecated`: retained for history but no longer applicable.

ADR numbers are permanent and never reused. Material changes require a new ADR rather than silent editing of an accepted decision.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [ADR-001](ADR-001_Initial_Application_Stack.md) | Initial application stack | Accepted |
| [ADR-002](ADR-002_Development_and_Delivery_Toolchain.md) | Development and delivery toolchain | Accepted |
| [ADR-003](ADR-003_Development_Identity.md) | Development identity boundary | Accepted |
| [ADR-004](ADR-004_MCP_Builder_Python_Generation_Profile.md) | MCP Builder Python generation profile | Accepted |
| [ADR-005](ADR-005_MCP_Builder_Static_Validation_Profile.md) | MCP Builder static validation profile | Accepted |
| [ADR-006](ADR-006_MCP_Builder_Domain_Review_Contract.md) | MCP Builder domain review contract | Accepted |
| [ADR-007](ADR-007_MCP_Builder_Security_Review_Contract.md) | MCP Builder security review contract | Accepted |
| [ADR-008](ADR-008_MCP_Builder_Isolated_Lab_Validation_Contract.md) | MCP Builder isolated lab validation contract | Accepted |
| [ADR-009](ADR-009_MCP_Builder_Candidate_Package_Handoff_Contract.md) | MCP Builder candidate package handoff contract | Accepted |
| [ADR-010](ADR-010_MCP_Builder_Package_Acquisition_Contract.md) | MCP Builder package acquisition contract | Accepted |
| [ADR-011](ADR-011_Connector_Package_Validation_Intake_Contract.md) | Connector package validation intake contract | Accepted |
| [ADR-012](ADR-012_Connector_Package_Content_Dependency_Inventory_Contract.md) | Connector package content and dependency inventory contract | Accepted |
| [ADR-013](ADR-013_Connector_Package_Secret_Prohibited_Content_Scan_Contract.md) | Connector package secret and prohibited-content scan contract | Accepted |
| [ADR-014](ADR-014_Connector_Configuration_Capability_Schema_Semantics_Contract.md) | Connector configuration and capability schema semantics contract | Accepted |
| [ADR-015](ADR-015_Connector_Declared_Authority_Implementation_Behavior_Contract.md) | Connector declared authority and implementation behavior contract | Accepted |
| [ADR-016](ADR-016_Connector_Static_Code_Dependency_Hygiene_Contract.md) | Connector static code and dependency hygiene contract | Accepted |
| [ADR-017](ADR-017_Connector_Dependency_Vulnerability_Analysis_Contract.md) | Connector dependency vulnerability analysis contract | Accepted |
| [ADR-018](ADR-018_Connector_Package_Malware_Analysis_Contract.md) | Connector package malware analysis contract | Accepted |
| [ADR-019](ADR-019_Connector_Package_License_Analysis_Contract.md) | Connector package license analysis contract | Accepted |
| [ADR-020](ADR-020_Connector_Contract_Validation_Contract.md) | Connector contract validation contract | Accepted |
| [ADR-021](ADR-021_Connector_Isolated_Runner_Validation_Contract.md) | Connector isolated runner validation contract | Accepted |
| [ADR-022](ADR-022_Connector_Isolated_Lab_Self_Test_Contract.md) | Connector isolated lab self-test contract | Accepted |
| [ADR-023](ADR-023_Connector_Final_Validation_Contract.md) | Connector final validation contract | Accepted |
| [ADR-024](ADR-024_Connector_Package_Human_Approval_Contract.md) | Connector package human approval contract | Accepted |
| [ADR-025](ADR-025_Connector_Publisher_Attestation_Contract.md) | Connector publisher attestation contract | Accepted |
| [ADR-026](ADR-026_Connector_Package_Signing_Contract.md) | Connector package signing contract | Accepted |
| [ADR-027](ADR-027_Connector_Internal_Registry_Publication_Contract.md) | Connector internal registry publication contract | Accepted |
| [ADR-028](ADR-028_Connector_Package_Registration_Contract.md) | Connector package registration contract | Accepted |
| [ADR-029](ADR-029_Connector_Package_Installation_Contract.md) | Connector package installation contract | Accepted |
| [ADR-030](ADR-030_Connector_Instance_Creation_Contract.md) | Connector instance creation contract | Accepted |
| [ADR-031](ADR-031_Connector_Target_Configuration_Binding_Contract.md) | Connector target and configuration binding contract | Accepted |
| [ADR-032](ADR-032_Connector_Credential_Reference_Assignment_Contract.md) | Connector credential-reference assignment contract | Accepted |
| [ADR-033](ADR-033_Connector_Configuration_Connectivity_Validation_Contract.md) | Connector configuration and connectivity validation contract | Accepted |
| [ADR-034](ADR-034_Connector_Capability_Governance_Enablement_Contract.md) | Connector capability governance and enablement contract | Accepted |
| [ADR-035](ADR-035_Connector_Runtime_Trust_Grant_Contract.md) | Connector runtime trust grant contract | Accepted |
| [ADR-036](ADR-036_Connector_Secret_Brokerage_Authorization_Contract.md) | Connector secret brokerage authorization contract | Accepted |
| [ADR-037](ADR-037_Connector_Runtime_Activation_and_Health_Evidence_Contract.md) | Connector runtime activation and health evidence contract | Accepted |
| [ADR-038](ADR-038_Connector_Target_Session_and_Connectivity_Evidence_Contract.md) | Connector target session and connectivity evidence contract | Accepted |
| [ADR-039](ADR-039_Connector_Capability_Invocation_Authorization_Contract.md) | Connector capability invocation authorization contract | Accepted |
| [ADR-040](ADR-040_Bounded_Connector_Capability_Invocation_Contract.md) | Bounded connector capability invocation contract | Accepted |
| [ADR-041](ADR-041_Governed_Connector_Invocation_Evidence_Ingestion_Contract.md) | Governed connector invocation evidence ingestion contract | Accepted |
| [ADR-042](ADR-042_Governed_Operational_Evidence_Knowledge_Draft_Curation_Contract.md) | Governed operational evidence knowledge-draft curation contract | Accepted |
| [ADR-043](ADR-043_Governed_Operational_Knowledge_Draft_Review_Request_Contract.md) | Governed operational knowledge draft review request contract | Accepted |
| [ADR-044](ADR-044_Governed_Operational_Knowledge_Reviewer_Assignment_Contract.md) | Governed operational knowledge reviewer assignment contract | Accepted |
| [ADR-045](ADR-045_Governed_Operational_Knowledge_Protected_Inspection_Lease_Contract.md) | Governed operational knowledge protected inspection lease contract | Accepted |
| [ADR-046](ADR-046_Governed_Operational_Knowledge_Protected_Content_Presentation_Contract.md) | Governed operational knowledge protected content presentation contract | Accepted |
| [ADR-047](ADR-047_Governed_Operational_Knowledge_Review_Finding_Contract.md) | Governed operational knowledge review finding contract | Accepted |
| [ADR-048](ADR-048_Governed_Operational_Knowledge_Protected_Finding_Presentation_Contract.md) | Governed operational knowledge protected finding presentation contract | Accepted |
| [ADR-049](ADR-049_Governed_Operational_Knowledge_Track_Review_Decision_Contract.md) | Governed operational knowledge track review decision contract | Accepted |
| [ADR-050](ADR-050_Governed_Operational_Knowledge_Correction_and_Resubmission_Contract.md) | Governed operational knowledge correction and resubmission contract | Accepted |
| [ADR-051](ADR-051_Governed_Operational_Knowledge_Final_Resolution_Contract.md) | Governed operational knowledge final resolution contract | Accepted |
| [ADR-052](ADR-052_Governed_Operational_Knowledge_Publication_Preparation_Contract.md) | Governed operational knowledge publication preparation contract | Accepted |
| [ADR-053](ADR-053_Governed_Protected_Knowledge_Source_Materialization_Contract.md) | Governed protected knowledge source materialization contract | Accepted |
| [ADR-054](ADR-054_Governed_Deterministic_Protected_Knowledge_Chunking_Contract.md) | Governed deterministic protected knowledge chunking contract | Accepted |
| [ADR-055](ADR-055_Governed_Protected_Knowledge_Embedding_Generation_Contract.md) | Governed protected knowledge embedding generation contract | Accepted |
| [ADR-056](ADR-056_Governed_Protected_Knowledge_Retrieval_Index_Staging_and_Validation_Contract.md) | Governed protected knowledge retrieval index staging and validation contract | Accepted |
| [ADR-057](ADR-057_Governed_Protected_Knowledge_Retrieval_Index_Publication_Contract.md) | Governed protected knowledge retrieval index publication contract | Accepted |
| [ADR-058](ADR-058_Governed_Protected_Knowledge_Retrieval_Contract.md) | Governed protected knowledge retrieval contract | Accepted |
| [ADR-059](ADR-059_Governed_Protected_Model_Context_Assembly_Contract.md) | Governed protected model-context assembly contract | Accepted |
| [ADR-060](ADR-060_Governed_Protected_Model_Invocation_Contract.md) | Governed protected model invocation contract | Accepted |
| [ADR-061](ADR-061_Governed_Protected_Model_Draft_Adjudication_Contract.md) | Governed protected model draft adjudication contract | Accepted |
| [ADR-062](ADR-062_Governed_Protected_Answer_Presentation_Contract.md) | Governed protected answer presentation contract | Accepted |
| [ADR-063](ADR-063_Governed_Grounded_Recommendation_Candidate_Generation_Contract.md) | Governed grounded recommendation candidate generation contract | Accepted |
| [ADR-064](ADR-064_Governed_Protected_Candidate_Service_Impact_Enrichment_Contract.md) | Governed protected candidate service-impact enrichment contract | Accepted |
| [ADR-065](ADR-065_Governed_Protected_Candidate_Risk_Interruption_Duration_Recovery_Completion_Contract.md) | Governed protected candidate risk, interruption, duration, and recovery completion contract | Accepted |
| [ADR-066](ADR-066_Governed_Deterministic_Protected_Recommendation_Adjudication_Contract.md) | Governed deterministic protected recommendation adjudication contract | Accepted |
| [ADR-067](ADR-067_Governed_Protected_Recommendation_Presentation_Contract.md) | Governed protected recommendation presentation contract | Accepted |
| [ADR-068](ADR-068_Governed_Recommendation_Domain_Promotion_Contract.md) | Governed recommendation domain promotion contract | Accepted |
| [ADR-069](ADR-069_Governed_Recommendation_Review_Readiness_Contract.md) | Governed recommendation review readiness contract | Accepted |
| [ADR-070](ADR-070_Governed_Recommendation_Human_Review_Request_Contract.md) | Governed recommendation human review request contract | Accepted |
| [ADR-071](ADR-071_Governed_Recommendation_Reviewer_Assignment_Contract.md) | Governed recommendation reviewer assignment contract | Accepted |
| [ADR-072](ADR-072_Governed_Recommendation_Protected_Inspection_Lease_Contract.md) | Governed recommendation protected inspection lease contract | Accepted |
| [ADR-073](ADR-073_Governed_Recommendation_Protected_Content_Presentation_Contract.md) | Governed recommendation protected content presentation contract | Accepted |
| [ADR-074](ADR-074_Governed_Recommendation_Human_Review_Finding_Contract.md) | Governed recommendation human review finding contract | Accepted |
| [ADR-075](ADR-075_Governed_Recommendation_Protected_Finding_Presentation_Contract.md) | Governed recommendation protected finding presentation contract | Accepted |
| [ADR-076](ADR-076_Governed_Recommendation_Track_Review_Decision_Contract.md) | Governed recommendation track review decision contract | Accepted |
| [ADR-077](ADR-077_Governed_Recommendation_Correction_and_Resubmission_Contract.md) | Governed recommendation correction and resubmission contract | Accepted |
| [ADR-078](ADR-078_Governed_Final_Recommendation_Disposition_Contract.md) | Governed final recommendation disposition contract | Accepted |
| [ADR-079](ADR-079_Operational_Workspace_Information_Architecture_Contract.md) | Operational workspace information architecture contract | Accepted |
| [ADR-080](ADR-080_Health_Workspace_Loading_Boundary_and_Route_Code_Splitting_Contract.md) | Health workspace loading boundary and route code splitting contract | Accepted |
| [ADR-081](ADR-081_Health_Inventory_and_Evidence_Workspace_Extraction_Contract.md) | Health inventory and evidence workspace extraction contract | Accepted |
| [ADR-082](ADR-082_Health_Decision_Support_Presentation_Extraction_Contract.md) | Health decision-support presentation extraction contract | Accepted |
| [ADR-083](ADR-083_Health_Governance_Report_Presentation_Extraction_Contract.md) | Health governance and report presentation extraction contract | Accepted |
| [ADR-084](ADR-084_Health_Scheduled_Checks_Presentation_Extraction_Contract.md) | Health scheduled checks presentation extraction contract | Accepted |
| [ADR-085](ADR-085_Security_Export_Presentation_Extraction_Contract.md) | Security export presentation extraction contract | Accepted |
| [ADR-086](ADR-086_Release_Preflight_Presentation_Extraction_Contract.md) | Release preflight presentation extraction contract | Accepted |
| [ADR-087](ADR-087_Deployment_Configuration_Presentation_Extraction_Contract.md) | Deployment configuration presentation extraction contract | Accepted |
| [ADR-088](ADR-088_Bootstrap_Plan_Presentation_Extraction_Contract.md) | Bootstrap plan presentation extraction contract | Accepted |
| [ADR-089](ADR-089_Bootstrap_Checkpoint_Presentation_Extraction_Contract.md) | Bootstrap checkpoint presentation extraction contract | Accepted |
| [ADR-090](ADR-090_Bootstrap_Invalidation_Presentation_Extraction_Contract.md) | Bootstrap invalidation presentation extraction contract | Accepted |
| [ADR-091](ADR-091_Bootstrap_Lease_Workflow_Ownership_Contract.md) | Bootstrap lease workflow ownership contract | Accepted |
| [ADR-092](ADR-092_Bootstrap_Artifact_Acquisition_Workflow_Ownership_Contract.md) | Bootstrap artifact acquisition workflow ownership contract | Accepted |
| [ADR-093](ADR-093_Health_Workspace_Task_View_Contract.md) | Health workspace task view contract | Accepted |
| [ADR-094](ADR-094_Bootstrap_Configuration_Rendering_Workflow_Ownership_Contract.md) | Bootstrap configuration rendering workflow ownership contract | Accepted |
| [ADR-095](ADR-095_Bootstrap_Trust_Provisioning_Workflow_Ownership_Contract.md) | Bootstrap trust provisioning workflow ownership contract | Accepted |
| [ADR-096](ADR-096_Bootstrap_Data_Initialization_Workflow_Ownership_Contract.md) | Bootstrap data initialization workflow ownership contract | Accepted |
| [ADR-097](ADR-097_Bootstrap_Service_Deployment_Workflow_Ownership_Contract.md) | Bootstrap service deployment workflow ownership contract | Accepted |
| [ADR-098](ADR-098_Bootstrap_Identity_Handoff_Workflow_Ownership_Contract.md) | Bootstrap identity handoff workflow ownership contract | Accepted |
| [ADR-099](ADR-099_Inventory_Device_Registry_Management_Contract.md) | Inventory device registry management contract | Accepted |
| [ADR-100](ADR-100_Installed_MCP_Lifecycle_Management_Contract.md) | Installed MCP lifecycle management contract | Accepted |
| [ADR-101](ADR-101_Capability_Aware_Workspace_Navigation.md) | Capability-aware workspace navigation | Accepted |
| [ADR-102](ADR-102_Connector_Upgrade_Readiness_Contract.md) | Connector upgrade readiness contract | Accepted |
| [ADR-103](ADR-103_Connector_Upgrade_Plan_Contract.md) | Connector upgrade plan contract | Accepted |
| [ADR-104](ADR-104_Connector_Upgrade_Approval_Request.md) | Connector upgrade approval request | Accepted |
| [ADR-105](ADR-105_Connector_Upgrade_Approval_Decision.md) | Connector upgrade approval decision | Accepted |
| [ADR-106](ADR-106_Connector_Upgrade_Approval_Revalidation.md) | Connector upgrade approval revalidation | Accepted |
| [ADR-107](ADR-107_Connector_Upgrade_Handoff_Readiness_Assessment.md) | Connector upgrade handoff readiness assessment | Accepted |
| [ADR-108](ADR-108_Connector_Upgrade_Handoff_Evidence_Applicability.md) | Connector upgrade handoff evidence applicability | Accepted |
| [ADR-109](ADR-109_Connector_Upgrade_Change_Context_Draft.md) | Connector upgrade change-context draft | Accepted |
| [ADR-110](ADR-110_Connector_Upgrade_Audit_Readiness_Evidence.md) | Connector upgrade audit readiness evidence | Accepted |
| [ADR-111](ADR-111_Connector_Upgrade_Authoritative_ITSM_Change_Evidence.md) | Connector upgrade authoritative ITSM change evidence | Accepted |
| [ADR-112](ADR-112_Connector_Upgrade_Maintenance_Window_Evidence.md) | Connector upgrade maintenance-window evidence | Accepted |
| [ADR-113](ADR-113_Connector_Upgrade_Non_Executable_Evidence_Receipt.md) | Connector upgrade non-executable evidence receipt | Accepted |
| [ADR-114](ADR-114_Connector_Upgrade_Evidence_Receipt_Verification.md) | Connector upgrade evidence receipt verification | Accepted |
| [ADR-115](ADR-115_Connector_Upgrade_Evidence_Receipt_Authenticity.md) | Connector upgrade evidence receipt authenticity | Accepted |
| [ADR-116](ADR-116_Connector_Upgrade_Signing_Key_Trust_Inventory.md) | Connector upgrade signing-key trust inventory | Accepted |
| [ADR-117](ADR-117_Connector_Upgrade_Signing_Provider_Conformance_Assessment.md) | Connector upgrade signing-provider conformance assessment | Accepted |
| [ADR-118](ADR-118_Connector_Upgrade_Signing_Provider_Onboarding_Readiness.md) | Connector upgrade signing-provider onboarding readiness | Accepted |
| [ADR-119](ADR-119_Connector_Upgrade_Signing_Provider_Onboarding_Policy_Governance.md) | Connector upgrade signing-provider onboarding policy governance | Accepted |
| [ADR-120](ADR-120_Connector_Upgrade_Signing_Provider_Onboarding_Policy_Authenticity.md) | Connector upgrade signing-provider onboarding policy authenticity | Accepted |
| [ADR-121](ADR-121_Connector_Upgrade_Onboarding_Policy_Provenance_Diagnostics.md) | Connector upgrade onboarding-policy provenance diagnostics | Accepted |
| [ADR-122](ADR-122_Connector_Upgrade_Onboarding_Policy_Provenance_Remediation_Guidance.md) | Connector upgrade onboarding-policy provenance remediation guidance | Accepted |
| [ADR-123](ADR-123_Inventory_and_MCP_Lifecycle_Action_Discoverability.md) | Inventory and MCP lifecycle action discoverability | Accepted |
| [ADR-124](ADR-124_Governed_ITSM_Handoff_Human_Review.md) | Governed ITSM handoff human review | Accepted |
| [ADR-125](ADR-125_Durable_Technical_Reports_and_Restart_Revalidation.md) | Durable technical reports and restart revalidation | Accepted |
| [ADR-126](ADR-126_Provider_Neutral_ITSM_Adapter_Readiness.md) | Provider-neutral ITSM adapter readiness | Accepted |
| [ADR-127](ADR-127_Provider_Neutral_ITSM_Sandbox_Conformance_Assessment.md) | Provider-neutral ITSM sandbox conformance assessment | Accepted |
| [ADR-128](ADR-128_Provider_Neutral_ITSM_Sandbox_Adapter_Onboarding_Readiness.md) | Provider-neutral ITSM sandbox adapter onboarding readiness | Accepted |
| [ADR-129](ADR-129_Provider_Neutral_ITSM_Sandbox_Onboarding_Policy_Governance.md) | Provider-neutral ITSM sandbox onboarding policy governance | Accepted |
| [ADR-130](ADR-130_Provider_Neutral_ITSM_Onboarding_Policy_Provenance_Authenticity.md) | Provider-neutral ITSM onboarding policy provenance and authenticity | Accepted |
| [ADR-131](ADR-131_Durable_Chat_Centered_Operations_Workspace.md) | Durable chat-centered operations workspace | Accepted |
| [ADR-132](ADR-132_Active_Directory_Authentication_Only_Boundary.md) | Active Directory authentication-only boundary | Accepted |
| [ADR-133](ADR-133_Optional_Policy_Based_Step_Up_Authentication.md) | Optional policy-based step-up authentication | Accepted |
| [ADR-134](ADR-134_Versioned_Workflow_Definition_and_Non_Executable_Run_Plan.md) | Versioned workflow definition and non-executable run plan | Accepted |
| [ADR-135](ADR-135_Durable_Workflow_Cancellation_State_and_Immutable_Transition_History.md) | Durable workflow cancellation state and immutable transition history | Accepted |
| [ADR-136](ADR-136_Fenced_Workflow_Orchestration_Lease_Without_Execution_Authority.md) | Fenced workflow orchestration lease without execution authority | Accepted |
| [ADR-137](ADR-137_Durable_Workflow_Run_Materialization_Without_Dispatch_Authority.md) | Durable workflow run materialization without dispatch authority | Accepted |
| [ADR-138](ADR-138_Durable_Workflow_Step_Attempt_Materialization_Without_Dispatch_Authority.md) | Durable workflow step attempt materialization without dispatch authority | Accepted |
| [ADR-139](ADR-139_Durable_Workflow_Dispatch_Intent_Staging_Without_Publication_Authority.md) | Durable workflow dispatch intent staging without publication authority | Accepted |
| [ADR-140](ADR-140_Transactional_Workflow_Dispatch_Outbox_Admission_Without_Publication_Authority.md) | Transactional workflow dispatch outbox admission without publication authority | Accepted |
| [ADR-141](ADR-141_Fenced_Workflow_Outbox_Publication_Lease_Without_Publication_Authority.md) | Fenced workflow outbox publication lease without publication authority | Accepted |
| [ADR-142](ADR-142_Canonical_Workflow_Dispatch_Event_Envelope_Without_Transport_Authority.md) | Canonical workflow dispatch event envelope without transport authority | Accepted |
| [ADR-143](ADR-143_Policy_Governed_Workflow_Event_Transport_Admission_Without_Publication_Authority.md) | Policy-governed workflow event transport admission without publication authority | Accepted |
| [ADR-144](ADR-144_Deterministic_Workflow_Event_Byte_Artifact_Materialization_Without_Transport_Selection.md) | Deterministic workflow event byte artifact materialization without transport selection | Accepted |
| [ADR-145](ADR-145_Immutable_Workflow_Logical_Publication_Channel_Binding_Without_Physical_Transport_Selection.md) | Immutable workflow logical publication channel binding without physical transport selection | Accepted |
| [ADR-146](ADR-146_Immutable_Deployment_Transport_Capability_Profile_Snapshot_Without_Route_Binding.md) | Immutable deployment transport capability profile snapshot without route binding | Accepted |
| [ADR-147](ADR-147_Immutable_Workflow_Transport_Compatibility_Admission_Without_Route_Binding.md) | Immutable workflow transport compatibility admission without route binding | Accepted |
| [ADR-148](ADR-148_Immutable_Deployment_Physical_Transport_Route_Snapshot_Without_Workflow_Binding.md) | Immutable deployment physical transport route snapshot without workflow binding | Accepted |
| [ADR-149](ADR-149_Immutable_Workflow_Physical_Transport_Route_Binding_Without_Runtime_Authority.md) | Immutable workflow physical transport route binding without runtime authority | Accepted |
| [ADR-150](ADR-150_Immutable_Workflow_Physical_Transport_Route_Freshness_and_Non_Supersession_Admission_Without_Endpoint_Resolution_Authority.md) | Immutable workflow physical transport route freshness and non-supersession admission without endpoint resolution authority | Accepted |
| [ADR-151](ADR-151_Bounded_Single_Use_Workflow_Physical_Transport_Endpoint_Resolution_Authorization_Lease_Without_Endpoint_Materialization.md) | Bounded single-use workflow physical transport endpoint-resolution authorization lease without endpoint materialization | Accepted |
| [ADR-152](ADR-152_Atomic_Single_Use_Workflow_Endpoint_Resolution_Lease_Consumption_and_Protected_Endpoint_Materialization.md) | Atomic single-use workflow endpoint-resolution lease consumption and protected endpoint materialization | Accepted |
| [ADR-153](ADR-153_Immutable_Deployment_Physical_Transport_Credential_Assignment_Snapshot_Without_Workflow_Binding.md) | Immutable deployment physical transport credential-assignment snapshot without workflow binding | Accepted |
| [ADR-154](ADR-154_Immutable_Workflow_Physical_Transport_Credential_Assignment_Binding_Without_Access_Authority.md) | Immutable workflow physical transport credential-assignment binding without access authority | Accepted |
| [ADR-155](ADR-155_Immutable_Workflow_Physical_Transport_Credential_Assignment_Freshness_Admission_Without_Access_Authority.md) | Immutable workflow physical transport credential-assignment freshness admission without access authority | Accepted |
| [ADR-156](ADR-156_Bounded_Single_Use_Workflow_Physical_Transport_Credential_Access_Authorization_Lease_Without_Secret_Resolution_or_Delivery.md) | Bounded single-use workflow physical-transport credential-access authorization lease without secret resolution or delivery | Accepted |
| [ADR-157](ADR-157_Atomic_Single_Use_Workflow_Credential_Access_Lease_Consumption_and_Protected_Credential_Materialization.md) | Atomic single-use workflow credential-access lease consumption and protected credential materialization | Accepted |
| [ADR-158](ADR-158_Immutable_Workflow_Protected_Transport_Target_Context_Binding_Without_Artifact_Access.md) | Immutable workflow protected transport target-context binding without artifact access | Accepted |
| [ADR-159](ADR-159_Target_Context_Access_Authorization_Lease.md) | Bounded single-use workflow protected transport target-context access authorization lease without artifact opening or runtime authority | Accepted |
| [ADR-160](ADR-160_Target_Context_Artifact_Opening.md) | Atomic single-use target-context access lease consumption and paired protected artifact opening without delivery or runtime authority | Accepted |
| [ADR-161](ADR-161_Immutable_Target_Context_Capsule_Consumer_Binding.md) | Immutable target-context capsule consumer binding without handoff or runtime authority | Accepted |
| [ADR-162](ADR-162_Bounded_Single_Use_Target_Context_Capsule_Handoff_Authorization_Lease.md) | Bounded single-use protected target-context capsule handoff authorization lease | Accepted |
| [ADR-163](ADR-163_Atomic_Target_Context_Capsule_Handoff_Lease_Consumption.md) | Atomic single-use target-context capsule handoff lease consumption | Accepted |
| [ADR-164](ADR-164_Bounded_Single_Use_Target_Context_Capsule_Opening_Authorization_Lease.md) | Bounded single-use consumer-side target-context capsule opening authorization lease | Accepted |
| [ADR-165](ADR-165_Atomic_Target_Context_Capsule_Opening_Lease_Consumption.md) | Atomic single-use consumer-side target-context capsule opening lease consumption | Accepted |
| [ADR-166](ADR-166_Bounded_Single_Use_Protected_Resident_Context_Access_Authorization_Lease.md) | Bounded single-use protected resident-context access authorization lease | Accepted |
| [ADR-167](ADR-167_Atomic_Protected_Resident_Context_Access_Lease_Consumption.md) | Atomic protected resident-context access lease consumption and non-bearer runtime-handle materialization | Accepted |
| [ADR-168](ADR-168_Bounded_Single_Use_Protected_Runtime_Context_Injection_Authorization_Lease.md) | Bounded single-use protected runtime-context injection authorization lease | Accepted |
| [ADR-169](ADR-169_Atomic_Protected_Runtime_Context_Injection_Lease_Consumption.md) | Atomic protected runtime-context injection lease consumption and inert protected-slot injection | Accepted |
| [ADR-170](ADR-170_Bounded_Single_Use_Protected_Runtime_Context_Use_Authorization_Lease.md) | Bounded single-use protected runtime-context use authorization lease | Accepted |
| [ADR-171](ADR-171_Atomic_Protected_Runtime_Context_Use_Authorization_Lease_Consumption.md) | Atomic protected runtime-context use-authorization lease consumption without runtime-context use | Accepted |
| [ADR-172](ADR-172_Single_Use_Protected_Runtime_Context_Adoption.md) | Single-use protected runtime-context adoption after terminal authorization consumption | Accepted |
| [ADR-173](ADR-173_Bounded_Single_Use_Protected_Runtime_Start_Authorization_Lease.md) | Bounded single-use protected runtime-start authorization lease | Accepted |
| [ADR-174](ADR-174_Atomic_Protected_Runtime_Start_Consumption.md) | Atomic protected runtime-start lease consumption and single start attempt | Accepted |
| [ADR-175](ADR-175_Bounded_Single_Use_Protected_Runtime_Readiness_Authorization_Lease.md) | Bounded single-use protected runtime-readiness authorization lease | Accepted |
| [ADR-176](ADR-176_Atomic_Protected_Runtime_Readiness_Consumption.md) | Atomic protected runtime-readiness lease consumption and single assessment attempt | Accepted |
| [ADR-177](ADR-177_Bounded_Single_Use_Protected_Runtime_Process_Creation_Authorization_Lease.md) | Bounded single-use protected runtime process-creation authorization lease | Accepted |
| [ADR-178](ADR-178_Atomic_Protected_Runtime_Process_Creation_Consumption.md) | Atomic protected runtime process-creation consumption and single suspended-process attempt | Accepted |
| [ADR-179](ADR-179_Bounded_Single_Use_Protected_Runtime_Process_Scheduling_Authorization_Lease.md) | Bounded single-use protected runtime process-scheduling authorization lease | Accepted |
| [ADR-180](ADR-180_Atomic_Protected_Runtime_Process_Scheduling_Consumption.md) | Atomic protected runtime process-scheduling consumption | Accepted |
| [ADR-181](ADR-181_Bounded_Single_Use_Protected_Runtime_Process_Resume_Authorization_Lease.md) | Bounded single-use protected runtime process-resume authorization lease | Accepted |
| [ADR-182](ADR-182_Advisory_Only_Terminal_Execution_Boundary.md) | Advisory-only terminal execution boundary | Accepted |
| [ADR-183](ADR-183_Vector_Store_and_Embedding_Model_Selection.md) | Vector store and embedding model selection | Accepted |
| [ADR-184](ADR-184_Compact_Document_Sourced_Knowledge_Governance_Chain.md) | Compact document-sourced knowledge governance chain | Accepted |
