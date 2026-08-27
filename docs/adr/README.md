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
| [ADR-131](ADR-131_Durable_Chat_Centered_Operations_Workspace.md) | Durable chat-centered operations workspace | Accepted |
| [ADR-132](ADR-132_Active_Directory_Authentication_Only_Boundary.md) | Active Directory authentication-only boundary | Accepted |
| [ADR-133](ADR-133_Optional_Policy_Based_Step_Up_Authentication.md) | Optional policy-based step-up authentication | Accepted |
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
