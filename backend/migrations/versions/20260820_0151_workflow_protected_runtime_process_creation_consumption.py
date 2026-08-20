"""Add atomic protected runtime process-creation consumption evidence.

Revision ID: 20260820_0151
Revises: 20260818_0150
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0151"
down_revision: str | None = "20260818_0150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_runtime_process_creation_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_process_creation_consumption_claims"
ATTEMPT_TABLE = "workflow_event_runtime_process_creation_attempts"
RESULT_TABLE = "workflow_event_runtime_process_creation_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtproc_cons_mutation"
FINAL_VALIDATION_FUNCTION = "validate_wf_rtproc_cons_commit"

LEASE_PROJECTION_COLUMNS = (
    "authorization_lease_id",
    "canonical_digest",
    "claim_id",
    "claim_digest",
    "readiness_result_id",
    "readiness_result_digest",
    "readiness_consumption_id",
    "readiness_attempt_id",
    "readiness_attempt_digest",
    "readiness_claim_id",
    "readiness_claim_digest",
    "destination_deployment_id",
    "destination_generation",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_slot_generation",
    "runtime_envelope_id",
    "runtime_envelope_commitment",
    "runtime_envelope_generation",
    "process_creation_profile_id",
    "process_creation_profile_version",
    "process_creation_profile_digest",
    "coordination_state",
    "runtime_start_attempt_pending",
    "runtime_start_attempt_terminal",
    "runtime_started",
    "runtime_resumed",
    "process_created",
    "process_scheduled",
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtproc_auth_lease_consume",
        LEASE_TABLE,
        list(LEASE_PROJECTION_COLUMNS),
    )
    op.execute(
        sa.text(r"""
CREATE TABLE workflow_event_runtime_process_creation_consumption_claims (
	claim_id VARCHAR(128) NOT NULL,
	consumption_id VARCHAR(128) NOT NULL,
	attempt_id VARCHAR(128) NOT NULL,
	idempotency_scope_id VARCHAR(64) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	idempotency_digest VARCHAR(64) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	irreversible_consumption_acknowledged BOOLEAN NOT NULL,
	uncertainty_no_retry_acknowledged BOOLEAN NOT NULL,
	claimed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	canonical_digest VARCHAR(64) NOT NULL,
	payload JSONB NOT NULL,
	authorization_lease_id VARCHAR(128) NOT NULL,
	authorization_lease_digest VARCHAR(64) NOT NULL,
	authorization_claim_id VARCHAR(128) NOT NULL,
	authorization_claim_digest VARCHAR(64) NOT NULL,
	process_creation_profile_id VARCHAR(128) NOT NULL,
	process_creation_profile_version VARCHAR(64) NOT NULL,
	process_creation_profile_digest VARCHAR(64) NOT NULL,
	readiness_result_id VARCHAR(128) NOT NULL,
	readiness_result_digest VARCHAR(64) NOT NULL,
	readiness_consumption_id VARCHAR(128) NOT NULL,
	readiness_attempt_id VARCHAR(128) NOT NULL,
	readiness_attempt_digest VARCHAR(64) NOT NULL,
	readiness_claim_id VARCHAR(128) NOT NULL,
	readiness_claim_digest VARCHAR(64) NOT NULL,
	readiness_authorization_lease_id VARCHAR(128) NOT NULL,
	readiness_authorization_lease_digest VARCHAR(64) NOT NULL,
	readiness_authorization_claim_id VARCHAR(128) NOT NULL,
	readiness_authorization_claim_digest VARCHAR(64) NOT NULL,
	readiness_profile_id VARCHAR(128) NOT NULL,
	readiness_profile_version VARCHAR(64) NOT NULL,
	readiness_profile_digest VARCHAR(64) NOT NULL,
	readiness_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_state VARCHAR(64) NOT NULL,
	readiness_failure_class VARCHAR(64),
	readiness_outcome_known BOOLEAN NOT NULL,
	readiness_assessment_performed BOOLEAN NOT NULL,
	runtime_ready BOOLEAN NOT NULL,
	assessor_receipt_digest VARCHAR(64) NOT NULL,
	readiness_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_id VARCHAR(128) NOT NULL,
	start_result_digest VARCHAR(64) NOT NULL,
	start_consumption_id VARCHAR(128) NOT NULL,
	start_attempt_id VARCHAR(128) NOT NULL,
	start_attempt_digest VARCHAR(64) NOT NULL,
	start_consumption_claim_id VARCHAR(128) NOT NULL,
	start_consumption_claim_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_lease_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_lease_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_claim_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_claim_digest VARCHAR(64) NOT NULL,
	use_result_id VARCHAR(128) NOT NULL,
	use_result_digest VARCHAR(64) NOT NULL,
	destination_deployment_id VARCHAR(128) NOT NULL,
	destination_generation INTEGER NOT NULL,
	destination_fencing_token_digest VARCHAR(64) NOT NULL,
	runtime_slot_commitment VARCHAR(64) NOT NULL,
	runtime_slot_generation INTEGER NOT NULL,
	runtime_envelope_id VARCHAR(128) NOT NULL,
	runtime_envelope_commitment VARCHAR(64) NOT NULL,
	runtime_envelope_generation INTEGER NOT NULL,
	runtime_start_profile_id VARCHAR(128) NOT NULL,
	runtime_start_profile_version VARCHAR(64) NOT NULL,
	runtime_start_profile_digest VARCHAR(64) NOT NULL,
	protected_operation_reference VARCHAR(128) NOT NULL,
	start_instruction_digest VARCHAR(64) NOT NULL,
	start_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	start_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	starter_receipt_digest VARCHAR(64) NOT NULL,
	start_result_state VARCHAR(64) NOT NULL,
	start_outcome_known BOOLEAN NOT NULL,
	runtime_started BOOLEAN NOT NULL,
	coordination_state VARCHAR(64) NOT NULL,
	runtime_start_attempt_pending BOOLEAN NOT NULL,
	runtime_start_attempt_terminal BOOLEAN NOT NULL,
	runtime_resumed BOOLEAN NOT NULL,
	process_created BOOLEAN NOT NULL,
	process_scheduled BOOLEAN NOT NULL,
	organization_id VARCHAR(128) NOT NULL,
	environment_id VARCHAR(128) NOT NULL,
	site_id VARCHAR(128) NOT NULL,
	consumer_subject_id VARCHAR(240) NOT NULL,
	consumer_audience VARCHAR(240) NOT NULL,
	consumer_contract_id VARCHAR(128) NOT NULL,
	consumer_contract_version VARCHAR(64) NOT NULL,
	purpose_id VARCHAR(128) NOT NULL,
	policy_id VARCHAR(128) NOT NULL,
	policy_version VARCHAR(64) NOT NULL,
	policy_digest VARCHAR(64) NOT NULL,
	source_policy_id VARCHAR(128) NOT NULL,
	source_policy_version VARCHAR(64) NOT NULL,
	source_policy_digest VARCHAR(64) NOT NULL,
	protected_runtime_process_creation_authority_granted BOOLEAN NOT NULL,
	protected_runtime_readiness_authority_granted BOOLEAN NOT NULL,
	protected_runtime_start_authority_granted BOOLEAN NOT NULL,
	endpoint_resolution_authorized BOOLEAN NOT NULL,
	route_selection_authorized BOOLEAN NOT NULL,
	route_binding_authorized BOOLEAN NOT NULL,
	credential_selection_authorized BOOLEAN NOT NULL,
	credential_assignment_binding_authorized BOOLEAN NOT NULL,
	credential_access_authorized BOOLEAN NOT NULL,
	credential_brokerage_authorized BOOLEAN NOT NULL,
	credential_resolution_authorized BOOLEAN NOT NULL,
	protected_artifact_access_authorized BOOLEAN NOT NULL,
	credential_delivery_authorized BOOLEAN NOT NULL,
	network_access_authorized BOOLEAN NOT NULL,
	readiness_probe_authorized BOOLEAN NOT NULL,
	publication_authorized BOOLEAN NOT NULL,
	delivery_authorized BOOLEAN NOT NULL,
	dispatch_authorized BOOLEAN NOT NULL,
	execution_authorized BOOLEAN NOT NULL,
	infrastructure_mutation_authorized BOOLEAN NOT NULL,
	target_context_capsule_handoff_authorized BOOLEAN NOT NULL,
	target_context_capsule_opening_authorized BOOLEAN NOT NULL,
	protected_resident_context_access_authority_granted BOOLEAN NOT NULL,
	protected_runtime_context_injection_authority_granted BOOLEAN NOT NULL,
	runtime_use_authorized BOOLEAN NOT NULL,
	runtime_start_authorized BOOLEAN NOT NULL,
	runtime_resume_authorized BOOLEAN NOT NULL,
	connector_activity_authorized BOOLEAN NOT NULL,
	protected_runtime_context_use_authority_granted BOOLEAN NOT NULL,
	PRIMARY KEY (claim_id),
	CONSTRAINT fk_wf_rtproc_cons_claim_lease FOREIGN KEY(authorization_lease_id, authorization_lease_digest, authorization_claim_id, authorization_claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled) REFERENCES workflow_event_runtime_process_creation_auth_leases (authorization_lease_id, canonical_digest, claim_id, claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled),
	CONSTRAINT fk_wf_rtproc_cons_claim_auth_claim FOREIGN KEY(organization_id, environment_id, site_id, authorization_claim_id, authorization_claim_digest, authorization_lease_id) REFERENCES workflow_event_runtime_process_creation_auth_claims (organization_id, environment_id, site_id, claim_id, canonical_digest, authorization_lease_id),
	CONSTRAINT uq_wf_rtproc_cons_claim_lease UNIQUE (authorization_lease_id),
	CONSTRAINT uq_wf_rtproc_cons_claim_consumption UNIQUE (consumption_id),
	CONSTRAINT uq_wf_rtproc_cons_claim_attempt UNIQUE (attempt_id),
	CONSTRAINT uq_wf_rtproc_cons_claim_digest UNIQUE (canonical_digest),
	CONSTRAINT uq_wf_rtproc_cons_claim_tenant_idem UNIQUE (organization_id, environment_id, site_id, consumer_subject_id, consumer_audience, idempotency_digest),
	CONSTRAINT uq_wf_rtproc_cons_claim_lineage UNIQUE (claim_id, canonical_digest, consumption_id, attempt_id, authorization_lease_id),
	CONSTRAINT ck_wf_rtproc_cons_claim_contract CHECK (consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_version = '1.0' AND purpose_id = 'purpose.workflow-protected-runtime-create-sealed-suspended-process' AND policy_id = 'policy.workflow-protected-runtime-process-creation-consumption' AND policy_version = '1.0' AND policy_digest = '4e9692080e0236eb64a69708499e382bcf3a373aa49b1b42ece990e6c5d6b572' AND source_policy_id = 'policy.workflow-protected-runtime-process-creation-authorization' AND source_policy_version = '1.0' AND source_policy_digest = '864620a2296233207d3ff1bde932725f65df1c102bddbdca304f9bcfe7e0cc96'),
	CONSTRAINT ck_wf_rtproc_cons_claim_source CHECK (readiness_result_state = 'runtime_ready_in_protected_boundary' AND readiness_outcome_known AND readiness_assessment_performed AND runtime_ready AND readiness_failure_class IS NULL AND readiness_completed_at IS NOT NULL AND assessor_receipt_digest IS NOT NULL AND readiness_started_at <= readiness_completed_at AND readiness_completed_at <= readiness_result_recorded_at AND readiness_completed_at < readiness_invocation_deadline AND coordination_state = 'start_attempt_terminal' AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal AND runtime_started AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled AND runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2),
	CONSTRAINT ck_wf_rtproc_cons_claim_semantics CHECK (irreversible_consumption_acknowledged AND uncertainty_no_retry_acknowledged AND runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2 AND process_creation_profile_id = 'profile.workflow-protected-runtime-process-creation-request' AND process_creation_profile_version = '1.0' AND process_creation_profile_digest = 'b08432f01dd864b34157e2522fc591606487a6d0968d2f39dd88a5672aa0ba1b' AND length(idempotency_scope_id) = 64 AND length(idempotency_digest) = 64 AND length(request_fingerprint) = 64 AND NOT endpoint_resolution_authorized AND NOT route_selection_authorized AND NOT route_binding_authorized AND NOT credential_selection_authorized AND NOT credential_assignment_binding_authorized AND NOT credential_access_authorized AND NOT credential_brokerage_authorized AND NOT credential_resolution_authorized AND NOT protected_artifact_access_authorized AND NOT credential_delivery_authorized AND NOT network_access_authorized AND NOT readiness_probe_authorized AND NOT publication_authorized AND NOT delivery_authorized AND NOT dispatch_authorized AND NOT execution_authorized AND NOT infrastructure_mutation_authorized AND NOT target_context_capsule_handoff_authorized AND NOT target_context_capsule_opening_authorized AND NOT protected_resident_context_access_authority_granted AND NOT protected_runtime_context_injection_authority_granted AND NOT runtime_use_authorized AND NOT runtime_start_authorized AND NOT runtime_resume_authorized AND NOT connector_activity_authorized AND NOT protected_runtime_context_use_authority_granted AND NOT protected_runtime_start_authority_granted AND NOT protected_runtime_readiness_authority_granted AND NOT protected_runtime_process_creation_authority_granted),
	CONSTRAINT ck_wf_rtproc_cons_claim_payload CHECK (jsonb_typeof(payload) = 'object')
)

""")
    )
    op.execute(
        sa.text(r"""
CREATE TABLE workflow_event_runtime_process_creation_attempts (
	attempt_id VARCHAR(128) NOT NULL,
	consumption_id VARCHAR(128) NOT NULL,
	claim_id VARCHAR(128) NOT NULL,
	claim_digest VARCHAR(64) NOT NULL,
	expected_process_count_pre INTEGER NOT NULL,
	expected_process_count_post INTEGER NOT NULL,
	primitive_id VARCHAR(128) NOT NULL,
	primitive_version VARCHAR(64) NOT NULL,
	primitive_digest VARCHAR(64) NOT NULL,
	creator_contract_id VARCHAR(128) NOT NULL,
	creator_contract_version VARCHAR(64) NOT NULL,
	creator_id VARCHAR(128) NOT NULL,
	creator_version VARCHAR(64) NOT NULL,
	receipt_verification_signing_key_id VARCHAR(128) NOT NULL,
	request_nonce_digest VARCHAR(64) NOT NULL,
	claimed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	state VARCHAR(64) NOT NULL,
	instruction_digest VARCHAR(64) NOT NULL,
	instruction_signing_key_id VARCHAR(128) NOT NULL,
	instruction_signature_algorithm VARCHAR(64) NOT NULL,
	signed_instruction_envelope_digest VARCHAR(64) NOT NULL,
	canonical_digest VARCHAR(64) NOT NULL,
	payload JSONB NOT NULL,
	signed_instruction_envelope_payload JSONB NOT NULL,
	authorization_lease_id VARCHAR(128) NOT NULL,
	authorization_lease_digest VARCHAR(64) NOT NULL,
	authorization_claim_id VARCHAR(128) NOT NULL,
	authorization_claim_digest VARCHAR(64) NOT NULL,
	process_creation_profile_id VARCHAR(128) NOT NULL,
	process_creation_profile_version VARCHAR(64) NOT NULL,
	process_creation_profile_digest VARCHAR(64) NOT NULL,
	readiness_result_id VARCHAR(128) NOT NULL,
	readiness_result_digest VARCHAR(64) NOT NULL,
	readiness_consumption_id VARCHAR(128) NOT NULL,
	readiness_attempt_id VARCHAR(128) NOT NULL,
	readiness_attempt_digest VARCHAR(64) NOT NULL,
	readiness_claim_id VARCHAR(128) NOT NULL,
	readiness_claim_digest VARCHAR(64) NOT NULL,
	readiness_authorization_lease_id VARCHAR(128) NOT NULL,
	readiness_authorization_lease_digest VARCHAR(64) NOT NULL,
	readiness_authorization_claim_id VARCHAR(128) NOT NULL,
	readiness_authorization_claim_digest VARCHAR(64) NOT NULL,
	readiness_profile_id VARCHAR(128) NOT NULL,
	readiness_profile_version VARCHAR(64) NOT NULL,
	readiness_profile_digest VARCHAR(64) NOT NULL,
	readiness_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_state VARCHAR(64) NOT NULL,
	readiness_failure_class VARCHAR(64),
	readiness_outcome_known BOOLEAN NOT NULL,
	readiness_assessment_performed BOOLEAN NOT NULL,
	runtime_ready BOOLEAN NOT NULL,
	assessor_receipt_digest VARCHAR(64) NOT NULL,
	readiness_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_id VARCHAR(128) NOT NULL,
	start_result_digest VARCHAR(64) NOT NULL,
	start_consumption_id VARCHAR(128) NOT NULL,
	start_attempt_id VARCHAR(128) NOT NULL,
	start_attempt_digest VARCHAR(64) NOT NULL,
	start_consumption_claim_id VARCHAR(128) NOT NULL,
	start_consumption_claim_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_lease_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_lease_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_claim_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_claim_digest VARCHAR(64) NOT NULL,
	use_result_id VARCHAR(128) NOT NULL,
	use_result_digest VARCHAR(64) NOT NULL,
	destination_deployment_id VARCHAR(128) NOT NULL,
	destination_generation INTEGER NOT NULL,
	destination_fencing_token_digest VARCHAR(64) NOT NULL,
	runtime_slot_commitment VARCHAR(64) NOT NULL,
	runtime_slot_generation INTEGER NOT NULL,
	runtime_envelope_id VARCHAR(128) NOT NULL,
	runtime_envelope_commitment VARCHAR(64) NOT NULL,
	runtime_envelope_generation INTEGER NOT NULL,
	runtime_start_profile_id VARCHAR(128) NOT NULL,
	runtime_start_profile_version VARCHAR(64) NOT NULL,
	runtime_start_profile_digest VARCHAR(64) NOT NULL,
	protected_operation_reference VARCHAR(128) NOT NULL,
	start_instruction_digest VARCHAR(64) NOT NULL,
	start_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	start_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	starter_receipt_digest VARCHAR(64) NOT NULL,
	start_result_state VARCHAR(64) NOT NULL,
	start_outcome_known BOOLEAN NOT NULL,
	runtime_started BOOLEAN NOT NULL,
	coordination_state VARCHAR(64) NOT NULL,
	runtime_start_attempt_pending BOOLEAN NOT NULL,
	runtime_start_attempt_terminal BOOLEAN NOT NULL,
	runtime_resumed BOOLEAN NOT NULL,
	process_created BOOLEAN NOT NULL,
	process_scheduled BOOLEAN NOT NULL,
	organization_id VARCHAR(128) NOT NULL,
	environment_id VARCHAR(128) NOT NULL,
	site_id VARCHAR(128) NOT NULL,
	consumer_subject_id VARCHAR(240) NOT NULL,
	consumer_audience VARCHAR(240) NOT NULL,
	consumer_contract_id VARCHAR(128) NOT NULL,
	consumer_contract_version VARCHAR(64) NOT NULL,
	purpose_id VARCHAR(128) NOT NULL,
	policy_id VARCHAR(128) NOT NULL,
	policy_version VARCHAR(64) NOT NULL,
	policy_digest VARCHAR(64) NOT NULL,
	source_policy_id VARCHAR(128) NOT NULL,
	source_policy_version VARCHAR(64) NOT NULL,
	source_policy_digest VARCHAR(64) NOT NULL,
	protected_runtime_process_creation_authority_granted BOOLEAN NOT NULL,
	protected_runtime_readiness_authority_granted BOOLEAN NOT NULL,
	protected_runtime_start_authority_granted BOOLEAN NOT NULL,
	endpoint_resolution_authorized BOOLEAN NOT NULL,
	route_selection_authorized BOOLEAN NOT NULL,
	route_binding_authorized BOOLEAN NOT NULL,
	credential_selection_authorized BOOLEAN NOT NULL,
	credential_assignment_binding_authorized BOOLEAN NOT NULL,
	credential_access_authorized BOOLEAN NOT NULL,
	credential_brokerage_authorized BOOLEAN NOT NULL,
	credential_resolution_authorized BOOLEAN NOT NULL,
	protected_artifact_access_authorized BOOLEAN NOT NULL,
	credential_delivery_authorized BOOLEAN NOT NULL,
	network_access_authorized BOOLEAN NOT NULL,
	readiness_probe_authorized BOOLEAN NOT NULL,
	publication_authorized BOOLEAN NOT NULL,
	delivery_authorized BOOLEAN NOT NULL,
	dispatch_authorized BOOLEAN NOT NULL,
	execution_authorized BOOLEAN NOT NULL,
	infrastructure_mutation_authorized BOOLEAN NOT NULL,
	target_context_capsule_handoff_authorized BOOLEAN NOT NULL,
	target_context_capsule_opening_authorized BOOLEAN NOT NULL,
	protected_resident_context_access_authority_granted BOOLEAN NOT NULL,
	protected_runtime_context_injection_authority_granted BOOLEAN NOT NULL,
	runtime_use_authorized BOOLEAN NOT NULL,
	runtime_start_authorized BOOLEAN NOT NULL,
	runtime_resume_authorized BOOLEAN NOT NULL,
	connector_activity_authorized BOOLEAN NOT NULL,
	protected_runtime_context_use_authority_granted BOOLEAN NOT NULL,
	PRIMARY KEY (attempt_id),
	CONSTRAINT fk_wf_rtproc_cons_attempt_lease FOREIGN KEY(authorization_lease_id, authorization_lease_digest, authorization_claim_id, authorization_claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled) REFERENCES workflow_event_runtime_process_creation_auth_leases (authorization_lease_id, canonical_digest, claim_id, claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled),
	CONSTRAINT fk_wf_rtproc_cons_attempt_auth_claim FOREIGN KEY(organization_id, environment_id, site_id, authorization_claim_id, authorization_claim_digest, authorization_lease_id) REFERENCES workflow_event_runtime_process_creation_auth_claims (organization_id, environment_id, site_id, claim_id, canonical_digest, authorization_lease_id),
	CONSTRAINT fk_wf_rtproc_cons_attempt_claim FOREIGN KEY(claim_id, claim_digest, consumption_id, attempt_id, authorization_lease_id) REFERENCES workflow_event_runtime_process_creation_consumption_claims (claim_id, canonical_digest, consumption_id, attempt_id, authorization_lease_id),
	CONSTRAINT uq_wf_rtproc_cons_attempt_claim UNIQUE (claim_id),
	CONSTRAINT uq_wf_rtproc_cons_attempt_consumption UNIQUE (consumption_id),
	CONSTRAINT uq_wf_rtproc_cons_attempt_lease UNIQUE (authorization_lease_id),
	CONSTRAINT uq_wf_rtproc_cons_attempt_instruction UNIQUE (instruction_digest),
	CONSTRAINT uq_wf_rtproc_cons_attempt_digest UNIQUE (canonical_digest),
	CONSTRAINT uq_wf_rtproc_cons_attempt_result UNIQUE (attempt_id, canonical_digest, claim_id, claim_digest, consumption_id, authorization_lease_id, authorization_lease_digest, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, primitive_id, primitive_version, primitive_digest, protected_operation_reference, instruction_digest, started_at, invocation_deadline),
	CONSTRAINT ck_wf_rtproc_cons_attempt_contract CHECK (consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_version = '1.0' AND purpose_id = 'purpose.workflow-protected-runtime-create-sealed-suspended-process' AND policy_id = 'policy.workflow-protected-runtime-process-creation-consumption' AND policy_version = '1.0' AND policy_digest = '4e9692080e0236eb64a69708499e382bcf3a373aa49b1b42ece990e6c5d6b572' AND source_policy_id = 'policy.workflow-protected-runtime-process-creation-authorization' AND source_policy_version = '1.0' AND source_policy_digest = '864620a2296233207d3ff1bde932725f65df1c102bddbdca304f9bcfe7e0cc96'),
	CONSTRAINT ck_wf_rtproc_cons_attempt_source CHECK (readiness_result_state = 'runtime_ready_in_protected_boundary' AND readiness_outcome_known AND readiness_assessment_performed AND runtime_ready AND readiness_failure_class IS NULL AND readiness_completed_at IS NOT NULL AND assessor_receipt_digest IS NOT NULL AND readiness_started_at <= readiness_completed_at AND readiness_completed_at <= readiness_result_recorded_at AND readiness_completed_at < readiness_invocation_deadline AND coordination_state = 'start_attempt_terminal' AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal AND runtime_started AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled AND runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2),
	CONSTRAINT ck_wf_rtproc_cons_attempt_state CHECK (state = 'process_creation_attempt_started' AND claimed_at <= started_at AND started_at < invocation_deadline AND expected_process_count_pre = 0 AND expected_process_count_post = 1),
	CONSTRAINT ck_wf_rtproc_cons_attempt_instruction CHECK (primitive_id = 'primitive.workflow-protected-runtime-create-sealed-suspended-process' AND primitive_version = '1.0' AND primitive_digest = '96adb884eeb1554fa4ae7858b728f3db1c204784b2af879e8bfcc37356874222' AND creator_contract_id = 'contract.workflow-protected-runtime-sealed-process-creator' AND creator_contract_version = '1.0' AND creator_id = 'creator.workflow-protected-runtime-sealed-process' AND creator_version = '1.0' AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-process-creation-receipt.v1' AND instruction_signing_key_id = 'key.workflow-protected-runtime-process-creation-instruction.v1' AND instruction_signature_algorithm = 'hmac-sha256' AND length(instruction_digest) = 64 AND length(signed_instruction_envelope_digest) = 64 AND length(request_nonce_digest) = 64 AND NOT endpoint_resolution_authorized AND NOT route_selection_authorized AND NOT route_binding_authorized AND NOT credential_selection_authorized AND NOT credential_assignment_binding_authorized AND NOT credential_access_authorized AND NOT credential_brokerage_authorized AND NOT credential_resolution_authorized AND NOT protected_artifact_access_authorized AND NOT credential_delivery_authorized AND NOT network_access_authorized AND NOT readiness_probe_authorized AND NOT publication_authorized AND NOT delivery_authorized AND NOT dispatch_authorized AND NOT execution_authorized AND NOT infrastructure_mutation_authorized AND NOT target_context_capsule_handoff_authorized AND NOT target_context_capsule_opening_authorized AND NOT protected_resident_context_access_authority_granted AND NOT protected_runtime_context_injection_authority_granted AND NOT runtime_use_authorized AND NOT runtime_start_authorized AND NOT runtime_resume_authorized AND NOT connector_activity_authorized AND NOT protected_runtime_context_use_authority_granted AND NOT protected_runtime_start_authority_granted AND NOT protected_runtime_readiness_authority_granted AND NOT protected_runtime_process_creation_authority_granted),
	CONSTRAINT ck_wf_rtproc_cons_attempt_payload CHECK (jsonb_typeof(payload) = 'object' AND jsonb_typeof(signed_instruction_envelope_payload) = 'object' AND signed_instruction_envelope_payload <> '{}'::jsonb)
)

""")
    )
    op.execute(
        sa.text(r"""
CREATE TABLE workflow_event_runtime_process_creation_results (
	result_id VARCHAR(128) NOT NULL,
	consumption_id VARCHAR(128) NOT NULL,
	attempt_id VARCHAR(128) NOT NULL,
	attempt_digest VARCHAR(64) NOT NULL,
	claim_id VARCHAR(128) NOT NULL,
	claim_digest VARCHAR(64) NOT NULL,
	primitive_id VARCHAR(128) NOT NULL,
	primitive_version VARCHAR(64) NOT NULL,
	primitive_digest VARCHAR(64) NOT NULL,
	instruction_digest VARCHAR(64) NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	state VARCHAR(64) NOT NULL,
	failure_class VARCHAR(64),
	outcome_known BOOLEAN NOT NULL,
	result_process_created BOOLEAN,
	process_sealed BOOLEAN,
	process_suspended BOOLEAN,
	result_process_scheduled BOOLEAN NOT NULL,
	result_process_resumed BOOLEAN NOT NULL,
	result_process_dispatched BOOLEAN NOT NULL,
	result_process_executed BOOLEAN NOT NULL,
	receipt_digest VARCHAR(64),
	completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	canonical_digest VARCHAR(64) NOT NULL,
	payload JSONB NOT NULL,
	receipt_payload JSONB,
	authorization_lease_id VARCHAR(128) NOT NULL,
	authorization_lease_digest VARCHAR(64) NOT NULL,
	authorization_claim_id VARCHAR(128) NOT NULL,
	authorization_claim_digest VARCHAR(64) NOT NULL,
	process_creation_profile_id VARCHAR(128) NOT NULL,
	process_creation_profile_version VARCHAR(64) NOT NULL,
	process_creation_profile_digest VARCHAR(64) NOT NULL,
	readiness_result_id VARCHAR(128) NOT NULL,
	readiness_result_digest VARCHAR(64) NOT NULL,
	readiness_consumption_id VARCHAR(128) NOT NULL,
	readiness_attempt_id VARCHAR(128) NOT NULL,
	readiness_attempt_digest VARCHAR(64) NOT NULL,
	readiness_claim_id VARCHAR(128) NOT NULL,
	readiness_claim_digest VARCHAR(64) NOT NULL,
	readiness_authorization_lease_id VARCHAR(128) NOT NULL,
	readiness_authorization_lease_digest VARCHAR(64) NOT NULL,
	readiness_authorization_claim_id VARCHAR(128) NOT NULL,
	readiness_authorization_claim_digest VARCHAR(64) NOT NULL,
	readiness_profile_id VARCHAR(128) NOT NULL,
	readiness_profile_version VARCHAR(64) NOT NULL,
	readiness_profile_digest VARCHAR(64) NOT NULL,
	readiness_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_state VARCHAR(64) NOT NULL,
	readiness_failure_class VARCHAR(64),
	readiness_outcome_known BOOLEAN NOT NULL,
	readiness_assessment_performed BOOLEAN NOT NULL,
	runtime_ready BOOLEAN NOT NULL,
	assessor_receipt_digest VARCHAR(64) NOT NULL,
	readiness_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	readiness_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_id VARCHAR(128) NOT NULL,
	start_result_digest VARCHAR(64) NOT NULL,
	start_consumption_id VARCHAR(128) NOT NULL,
	start_attempt_id VARCHAR(128) NOT NULL,
	start_attempt_digest VARCHAR(64) NOT NULL,
	start_consumption_claim_id VARCHAR(128) NOT NULL,
	start_consumption_claim_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_lease_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_lease_digest VARCHAR(64) NOT NULL,
	runtime_start_authorization_claim_id VARCHAR(128) NOT NULL,
	runtime_start_authorization_claim_digest VARCHAR(64) NOT NULL,
	use_result_id VARCHAR(128) NOT NULL,
	use_result_digest VARCHAR(64) NOT NULL,
	destination_deployment_id VARCHAR(128) NOT NULL,
	destination_generation INTEGER NOT NULL,
	destination_fencing_token_digest VARCHAR(64) NOT NULL,
	runtime_slot_commitment VARCHAR(64) NOT NULL,
	runtime_slot_generation INTEGER NOT NULL,
	runtime_envelope_id VARCHAR(128) NOT NULL,
	runtime_envelope_commitment VARCHAR(64) NOT NULL,
	runtime_envelope_generation INTEGER NOT NULL,
	runtime_start_profile_id VARCHAR(128) NOT NULL,
	runtime_start_profile_version VARCHAR(64) NOT NULL,
	runtime_start_profile_digest VARCHAR(64) NOT NULL,
	protected_operation_reference VARCHAR(128) NOT NULL,
	start_instruction_digest VARCHAR(64) NOT NULL,
	start_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_invocation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	start_completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	start_result_recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	starter_receipt_digest VARCHAR(64) NOT NULL,
	start_result_state VARCHAR(64) NOT NULL,
	start_outcome_known BOOLEAN NOT NULL,
	runtime_started BOOLEAN NOT NULL,
	coordination_state VARCHAR(64) NOT NULL,
	runtime_start_attempt_pending BOOLEAN NOT NULL,
	runtime_start_attempt_terminal BOOLEAN NOT NULL,
	runtime_resumed BOOLEAN NOT NULL,
	process_created BOOLEAN NOT NULL,
	process_scheduled BOOLEAN NOT NULL,
	organization_id VARCHAR(128) NOT NULL,
	environment_id VARCHAR(128) NOT NULL,
	site_id VARCHAR(128) NOT NULL,
	consumer_subject_id VARCHAR(240) NOT NULL,
	consumer_audience VARCHAR(240) NOT NULL,
	consumer_contract_id VARCHAR(128) NOT NULL,
	consumer_contract_version VARCHAR(64) NOT NULL,
	purpose_id VARCHAR(128) NOT NULL,
	policy_id VARCHAR(128) NOT NULL,
	policy_version VARCHAR(64) NOT NULL,
	policy_digest VARCHAR(64) NOT NULL,
	source_policy_id VARCHAR(128) NOT NULL,
	source_policy_version VARCHAR(64) NOT NULL,
	source_policy_digest VARCHAR(64) NOT NULL,
	protected_runtime_process_creation_authority_granted BOOLEAN NOT NULL,
	protected_runtime_readiness_authority_granted BOOLEAN NOT NULL,
	protected_runtime_start_authority_granted BOOLEAN NOT NULL,
	endpoint_resolution_authorized BOOLEAN NOT NULL,
	route_selection_authorized BOOLEAN NOT NULL,
	route_binding_authorized BOOLEAN NOT NULL,
	credential_selection_authorized BOOLEAN NOT NULL,
	credential_assignment_binding_authorized BOOLEAN NOT NULL,
	credential_access_authorized BOOLEAN NOT NULL,
	credential_brokerage_authorized BOOLEAN NOT NULL,
	credential_resolution_authorized BOOLEAN NOT NULL,
	protected_artifact_access_authorized BOOLEAN NOT NULL,
	credential_delivery_authorized BOOLEAN NOT NULL,
	network_access_authorized BOOLEAN NOT NULL,
	readiness_probe_authorized BOOLEAN NOT NULL,
	publication_authorized BOOLEAN NOT NULL,
	delivery_authorized BOOLEAN NOT NULL,
	dispatch_authorized BOOLEAN NOT NULL,
	execution_authorized BOOLEAN NOT NULL,
	infrastructure_mutation_authorized BOOLEAN NOT NULL,
	target_context_capsule_handoff_authorized BOOLEAN NOT NULL,
	target_context_capsule_opening_authorized BOOLEAN NOT NULL,
	protected_resident_context_access_authority_granted BOOLEAN NOT NULL,
	protected_runtime_context_injection_authority_granted BOOLEAN NOT NULL,
	runtime_use_authorized BOOLEAN NOT NULL,
	runtime_start_authorized BOOLEAN NOT NULL,
	runtime_resume_authorized BOOLEAN NOT NULL,
	connector_activity_authorized BOOLEAN NOT NULL,
	protected_runtime_context_use_authority_granted BOOLEAN NOT NULL,
	PRIMARY KEY (result_id),
	CONSTRAINT fk_wf_rtproc_cons_result_lease FOREIGN KEY(authorization_lease_id, authorization_lease_digest, authorization_claim_id, authorization_claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled) REFERENCES workflow_event_runtime_process_creation_auth_leases (authorization_lease_id, canonical_digest, claim_id, claim_digest, readiness_result_id, readiness_result_digest, readiness_consumption_id, readiness_attempt_id, readiness_attempt_digest, readiness_claim_id, readiness_claim_digest, destination_deployment_id, destination_generation, destination_fencing_token_digest, runtime_slot_commitment, runtime_slot_generation, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, coordination_state, runtime_start_attempt_pending, runtime_start_attempt_terminal, runtime_started, runtime_resumed, process_created, process_scheduled),
	CONSTRAINT fk_wf_rtproc_cons_result_auth_claim FOREIGN KEY(organization_id, environment_id, site_id, authorization_claim_id, authorization_claim_digest, authorization_lease_id) REFERENCES workflow_event_runtime_process_creation_auth_claims (organization_id, environment_id, site_id, claim_id, canonical_digest, authorization_lease_id),
	CONSTRAINT fk_wf_rtproc_cons_result_attempt FOREIGN KEY(attempt_id, attempt_digest, claim_id, claim_digest, consumption_id, authorization_lease_id, authorization_lease_digest, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, primitive_id, primitive_version, primitive_digest, protected_operation_reference, instruction_digest, started_at, invocation_deadline) REFERENCES workflow_event_runtime_process_creation_attempts (attempt_id, canonical_digest, claim_id, claim_digest, consumption_id, authorization_lease_id, authorization_lease_digest, runtime_envelope_id, runtime_envelope_commitment, runtime_envelope_generation, process_creation_profile_id, process_creation_profile_version, process_creation_profile_digest, primitive_id, primitive_version, primitive_digest, protected_operation_reference, instruction_digest, started_at, invocation_deadline),
	CONSTRAINT uq_wf_rtproc_cons_result_attempt UNIQUE (attempt_id),
	CONSTRAINT uq_wf_rtproc_cons_result_claim UNIQUE (claim_id),
	CONSTRAINT uq_wf_rtproc_cons_result_consumption UNIQUE (consumption_id),
	CONSTRAINT uq_wf_rtproc_cons_result_lease UNIQUE (authorization_lease_id),
	CONSTRAINT uq_wf_rtproc_cons_result_digest UNIQUE (canonical_digest),
	CONSTRAINT ck_wf_rtproc_cons_result_contract CHECK (consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' AND consumer_contract_version = '1.0' AND purpose_id = 'purpose.workflow-protected-runtime-create-sealed-suspended-process' AND policy_id = 'policy.workflow-protected-runtime-process-creation-consumption' AND policy_version = '1.0' AND policy_digest = '4e9692080e0236eb64a69708499e382bcf3a373aa49b1b42ece990e6c5d6b572' AND source_policy_id = 'policy.workflow-protected-runtime-process-creation-authorization' AND source_policy_version = '1.0' AND source_policy_digest = '864620a2296233207d3ff1bde932725f65df1c102bddbdca304f9bcfe7e0cc96'),
	CONSTRAINT ck_wf_rtproc_cons_result_source CHECK (readiness_result_state = 'runtime_ready_in_protected_boundary' AND readiness_outcome_known AND readiness_assessment_performed AND runtime_ready AND readiness_failure_class IS NULL AND readiness_completed_at IS NOT NULL AND assessor_receipt_digest IS NOT NULL AND readiness_started_at <= readiness_completed_at AND readiness_completed_at <= readiness_result_recorded_at AND readiness_completed_at < readiness_invocation_deadline AND coordination_state = 'start_attempt_terminal' AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal AND runtime_started AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled AND runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2),
	CONSTRAINT ck_wf_rtproc_cons_result_outcome CHECK (recorded_at >= completed_at AND completed_at >= started_at AND ((state = 'process_created_suspended_in_protected_boundary' AND failure_class IS NULL AND outcome_known AND result_process_created AND process_sealed AND process_suspended AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR (state = 'process_creation_rejected_without_creation' AND failure_class = 'protected_creator_rejected_without_creation' AND outcome_known AND NOT result_process_created AND NOT process_sealed AND NOT process_suspended AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR (state = 'process_creation_failed_without_creation' AND failure_class = 'protected_creator_failed_without_creation' AND outcome_known AND NOT result_process_created AND NOT process_sealed AND NOT process_suspended AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR (state = 'process_creation_outcome_uncertain' AND failure_class = 'process_creation_outcome_uncertain' AND NOT outcome_known AND result_process_created IS NULL AND process_sealed IS NULL AND process_suspended IS NULL AND receipt_digest IS NULL)) AND NOT result_process_scheduled AND NOT result_process_resumed AND NOT result_process_dispatched AND NOT result_process_executed),
	CONSTRAINT ck_wf_rtproc_cons_result_semantics CHECK (runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2 AND NOT endpoint_resolution_authorized AND NOT route_selection_authorized AND NOT route_binding_authorized AND NOT credential_selection_authorized AND NOT credential_assignment_binding_authorized AND NOT credential_access_authorized AND NOT credential_brokerage_authorized AND NOT credential_resolution_authorized AND NOT protected_artifact_access_authorized AND NOT credential_delivery_authorized AND NOT network_access_authorized AND NOT readiness_probe_authorized AND NOT publication_authorized AND NOT delivery_authorized AND NOT dispatch_authorized AND NOT execution_authorized AND NOT infrastructure_mutation_authorized AND NOT target_context_capsule_handoff_authorized AND NOT target_context_capsule_opening_authorized AND NOT protected_resident_context_access_authority_granted AND NOT protected_runtime_context_injection_authority_granted AND NOT runtime_use_authorized AND NOT runtime_start_authorized AND NOT runtime_resume_authorized AND NOT connector_activity_authorized AND NOT protected_runtime_context_use_authority_granted AND NOT protected_runtime_start_authority_granted AND NOT protected_runtime_readiness_authority_granted AND NOT protected_runtime_process_creation_authority_granted),
	CONSTRAINT ck_wf_rtproc_cons_result_payload CHECK (jsonb_typeof(payload) = 'object' AND (receipt_payload IS NULL OR jsonb_typeof(receipt_payload) = 'object'))
)

""")
    )
    op.create_index(
        "ix_wf_rtproc_cons_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )
    op.create_index(
        "ix_wf_rtproc_cons_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )
    op.create_index(
        "ix_wf_rtproc_cons_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {FINAL_VALIDATION_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE
                lease_issued_at timestamptz;
                lease_valid_until timestamptz;
                lease_effective_until timestamptz;
                lease_state text;
                lease_single_use boolean;
                lease_renewable boolean;
                lease_transferable boolean;
                lease_bearer boolean;
                lease_authority boolean;
                attempt_started_at timestamptz;
                attempt_deadline timestamptz;
            BEGIN
                SELECT issued_at, valid_until, effective_until, state, single_use,
                       renewable, transferable, lease_is_bearer_capability,
                       protected_runtime_process_creation_authority_granted
                  INTO lease_issued_at, lease_valid_until, lease_effective_until,
                       lease_state, lease_single_use, lease_renewable,
                       lease_transferable, lease_bearer, lease_authority
                  FROM {LEASE_TABLE}
                 WHERE authorization_lease_id = NEW.authorization_lease_id
                   AND canonical_digest = NEW.authorization_lease_digest
                   AND claim_id = NEW.authorization_claim_id
                   AND claim_digest = NEW.authorization_claim_digest
                 FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION
                        'protected process-creation authorization lineage is missing'
                        USING ERRCODE = '23503';
                END IF;
                SELECT started_at, invocation_deadline
                  INTO attempt_started_at, attempt_deadline
                  FROM {ATTEMPT_TABLE}
                 WHERE claim_id = NEW.claim_id
                   AND attempt_id = NEW.attempt_id
                   AND authorization_lease_id = NEW.authorization_lease_id;
                IF NOT FOUND THEN
                    RAISE EXCEPTION
                        'process-creation claim and attempt must commit atomically'
                        USING ERRCODE = '23514';
                END IF;
                IF lease_state <> 'authorized_unconsumed'
                   OR NOT lease_single_use OR lease_renewable OR lease_transferable
                   OR lease_bearer OR NOT lease_authority
                   OR NEW.claimed_at < lease_issued_at
                   OR attempt_started_at < NEW.claimed_at
                   OR attempt_deadline > lease_valid_until
                   OR attempt_deadline > lease_effective_until
                   OR clock_timestamp() >= lease_valid_until
                   OR clock_timestamp() >= lease_effective_until
                   OR clock_timestamp() + INTERVAL '100 milliseconds' > attempt_deadline THEN
                    RAISE EXCEPTION
                        'protected process-creation lease window is no longer valid'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_wf_rtproc_cons_final_window "
            f"AFTER INSERT ON {CLAIM_TABLE} DEFERRABLE INITIALLY DEFERRED "
            f"FOR EACH ROW EXECUTE FUNCTION {FINAL_VALIDATION_FUNCTION}()"
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION
                    'protected runtime process-creation consumption evidence is append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtproc_cons_claim_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rtproc_cons_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rtproc_cons_result_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtproc_cons_claim_no_truncate"),
        (ATTEMPT_TABLE, "trg_wf_rtproc_cons_attempt_no_truncate"),
        (RESULT_TABLE, "trg_wf_rtproc_cons_result_no_truncate"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE TRUNCATE ON {table} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1)
                   OR EXISTS (SELECT 1 FROM {ATTEMPT_TABLE} LIMIT 1)
                   OR EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1) THEN
                    RAISE EXCEPTION
                        'refusing guarded downgrade: protected runtime process-creation consumption evidence exists'
                        USING ERRCODE = '55000';
                END IF;
            END $$;
            """
        )
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {FINAL_VALIDATION_FUNCTION}()"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
    op.drop_constraint("uq_wf_rtproc_auth_lease_consume", LEASE_TABLE, type_="unique")
