"""Add bounded protected runtime-readiness authorization leases.

Revision ID: 20260817_0148
Revises: 20260817_0147
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0148"
down_revision: str | None = "20260817_0147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

START_LEASE_TABLE = "workflow_event_runtime_start_auth_leases"
START_CLAIM_TABLE = "workflow_event_runtime_start_auth_claims"
START_CONSUMPTION_CLAIM_TABLE = "workflow_event_runtime_start_consumption_claims"
START_ATTEMPT_TABLE = "workflow_event_runtime_start_consumption_attempts"
START_RESULT_TABLE = "workflow_event_runtime_start_consumption_results"
START_COORDINATION_TABLE = "workflow_event_runtime_start_coordination_heads"
USE_RESULT_TABLE = "workflow_protected_runtime_context_use_results"
LEASE_TABLE = "workflow_event_runtime_readiness_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_readiness_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtready_auth_mutation"
COORDINATION_SCOPE_FUNCTION = "hydrate_wf_rtstart_coord_scope"

SCOPE_COLUMNS = ("organization_id", "environment_id", "site_id")

SCOPED_SOURCE_UNIQUES = (
    (
        "uq_wf_rtready_src_start_result_lineage",
        START_RESULT_TABLE,
        ("result_id", "canonical_digest", "claim_id", "attempt_id", "authorization_lease_id"),
    ),
    (
        "uq_wf_rtready_src_start_result_outcome",
        START_RESULT_TABLE,
        (
            "result_id",
            "canonical_digest",
            "state",
            "outcome_known",
            "runtime_started",
            "starter_receipt_digest",
            "completed_at",
            "recorded_at",
        ),
    ),
    (
        "uq_wf_rtready_src_start_attempt",
        START_ATTEMPT_TABLE,
        (
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "destination_deployment_id",
            "destination_generation",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "runtime_start_profile_id",
            "runtime_start_profile_version",
            "runtime_start_profile_digest",
            "protected_operation_reference",
            "instruction_digest",
            "started_at",
            "invocation_deadline",
        ),
    ),
    (
        "uq_wf_rtready_src_start_claim",
        START_CONSUMPTION_CLAIM_TABLE,
        ("claim_id", "canonical_digest", "consumption_id", "attempt_id", "authorization_lease_id"),
    ),
    (
        "uq_wf_rtready_src_start_lease",
        START_LEASE_TABLE,
        (
            "authorization_lease_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "use_result_id",
            "use_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "runtime_start_profile_id",
            "runtime_start_profile_version",
            "runtime_start_profile_digest",
        ),
    ),
    (
        "uq_wf_rtready_src_start_auth_claim",
        START_CLAIM_TABLE,
        ("claim_id", "canonical_digest", "authorization_lease_id"),
    ),
    (
        "uq_wf_rtready_src_started_head",
        START_COORDINATION_TABLE,
        (
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "use_result_id",
            "use_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            "state",
            "active_authorization_lease_id",
            "consumption_claim_id",
            "runtime_start_attempt_id",
            "runtime_start_result_id",
            "runtime_start_result_digest",
            "runtime_start_attempt_pending",
            "runtime_start_attempt_terminal",
            "runtime_started",
            "runtime_resumed",
            "process_created",
            "process_scheduled",
        ),
    ),
)

POLICY_DIGEST = "4d797b56dd215b9ab74974fb841e50c554c7ecf7aa76380e697fe1a2ebd360c5"
SOURCE_POLICY_DIGEST = "75ed8efd455acee45b3df68e65890de39f705ff1849c2eed02818fb8ab39be80"
RUNTIME_START_PROFILE_DIGEST = "233c49d3d7cb7d80655d2d2456431f38efecec49ad4c79d2100323754e829995"
READINESS_PROFILE_DIGEST = "830c47f035804b954d29813b226fe9ed2199d2b3b25f2a5694e5ca2d0fe219a3"


def _identity_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("source_policy_id", sa.String(128), nullable=False),
        sa.Column("source_policy_version", sa.String(64), nullable=False),
        sa.Column("source_policy_digest", sa.String(64), nullable=False),
    )


def _source_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("start_result_id", sa.String(128), nullable=False),
        sa.Column("start_result_digest", sa.String(64), nullable=False),
        sa.Column("start_consumption_id", sa.String(128), nullable=False),
        sa.Column("start_attempt_id", sa.String(128), nullable=False),
        sa.Column("start_attempt_digest", sa.String(64), nullable=False),
        sa.Column("start_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("start_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("runtime_start_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("runtime_start_authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("use_result_id", sa.String(128), nullable=False),
        sa.Column("use_result_digest", sa.String(64), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_envelope_id", sa.String(128), nullable=False),
        sa.Column("runtime_envelope_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_envelope_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_start_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_start_profile_digest", sa.String(64), nullable=False),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("start_instruction_digest", sa.String(64), nullable=False),
        sa.Column("start_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starter_receipt_digest", sa.String(64), nullable=False),
        sa.Column("start_result_state", sa.String(64), nullable=False),
        sa.Column("start_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("runtime_started", sa.Boolean(), nullable=False),
        sa.Column("coordination_state", sa.String(64), nullable=False),
        sa.Column("runtime_start_attempt_pending", sa.Boolean(), nullable=False),
        sa.Column("runtime_start_attempt_terminal", sa.Boolean(), nullable=False),
        sa.Column("runtime_resumed", sa.Boolean(), nullable=False),
        sa.Column("process_created", sa.Boolean(), nullable=False),
        sa.Column("process_scheduled", sa.Boolean(), nullable=False),
    )


def _authority_names() -> tuple[str, ...]:
    return (
        "endpoint_resolution_authorized",
        "route_selection_authorized",
        "route_binding_authorized",
        "credential_selection_authorized",
        "credential_assignment_binding_authorized",
        "credential_access_authorized",
        "credential_brokerage_authorized",
        "credential_resolution_authorized",
        "protected_artifact_access_authorized",
        "credential_delivery_authorized",
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "target_context_capsule_handoff_authorized",
        "target_context_capsule_opening_authorized",
        "protected_resident_context_access_authority_granted",
        "protected_runtime_context_injection_authority_granted",
        "runtime_use_authorized",
        "runtime_start_authorized",
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "protected_runtime_context_use_authority_granted",
        "protected_runtime_start_authority_granted",
        "protected_runtime_readiness_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_prior_authority() -> str:
    return " AND ".join(
        f"NOT {name}"
        for name in _authority_names()
        if name != "protected_runtime_readiness_authority_granted"
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = "
        "'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = "
        "'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = "
        "'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-readiness-evaluation' "
        "AND policy_id = 'policy.workflow-protected-runtime-readiness-authorization' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-start' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "start_result_state = 'runtime_started_in_protected_boundary' "
        "AND start_outcome_known AND runtime_started "
        "AND start_started_at <= start_completed_at "
        "AND start_completed_at <= start_result_recorded_at "
        "AND start_completed_at < start_invocation_deadline "
        "AND coordination_state = 'start_attempt_terminal' "
        "AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal "
        "AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled "
        "AND runtime_slot_generation = runtime_envelope_generation "
        "AND runtime_slot_generation >= 2 "
        "AND destination_generation >= 1 "
        "AND length(start_result_digest) = 64 "
        "AND length(start_attempt_digest) = 64 "
        "AND length(start_consumption_claim_digest) = 64 "
        "AND length(runtime_start_authorization_lease_digest) = 64 "
        "AND length(runtime_start_authorization_claim_digest) = 64 "
        "AND length(use_result_digest) = 64 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND length(runtime_envelope_commitment) = 64 "
        "AND length(start_instruction_digest) = 64 "
        "AND length(starter_receipt_digest) = 64 "
        "AND runtime_start_profile_id = 'profile.workflow-protected-runtime-start' "
        "AND runtime_start_profile_version = '1.0' "
        f"AND runtime_start_profile_digest = '{RUNTIME_START_PROFILE_DIGEST}'"
    )


def _source_constraints(*, prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "start_result_id",
                "start_result_digest",
                "start_consumption_claim_id",
                "start_attempt_id",
                "runtime_start_authorization_lease_id",
            ],
            [
                *(f"{START_RESULT_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_RESULT_TABLE}.result_id",
                f"{START_RESULT_TABLE}.canonical_digest",
                f"{START_RESULT_TABLE}.claim_id",
                f"{START_RESULT_TABLE}.attempt_id",
                f"{START_RESULT_TABLE}.authorization_lease_id",
            ],
            name=f"fk_wf_rtready_{prefix}_start_result",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "start_result_id",
                "start_result_digest",
                "start_result_state",
                "start_outcome_known",
                "runtime_started",
                "starter_receipt_digest",
                "start_completed_at",
                "start_result_recorded_at",
            ],
            [
                *(f"{START_RESULT_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_RESULT_TABLE}.result_id",
                f"{START_RESULT_TABLE}.canonical_digest",
                f"{START_RESULT_TABLE}.state",
                f"{START_RESULT_TABLE}.outcome_known",
                f"{START_RESULT_TABLE}.runtime_started",
                f"{START_RESULT_TABLE}.starter_receipt_digest",
                f"{START_RESULT_TABLE}.completed_at",
                f"{START_RESULT_TABLE}.recorded_at",
            ],
            name=f"fk_wf_rtready_{prefix}_start_outcome",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "start_attempt_id",
                "start_attempt_digest",
                "start_consumption_claim_id",
                "start_consumption_claim_digest",
                "start_consumption_id",
                "runtime_start_authorization_lease_id",
                "runtime_start_authorization_lease_digest",
                "destination_deployment_id",
                "destination_generation",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "runtime_start_profile_id",
                "runtime_start_profile_version",
                "runtime_start_profile_digest",
                "protected_operation_reference",
                "start_instruction_digest",
                "start_started_at",
                "start_invocation_deadline",
            ],
            [
                *(f"{START_ATTEMPT_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_ATTEMPT_TABLE}.attempt_id",
                f"{START_ATTEMPT_TABLE}.canonical_digest",
                f"{START_ATTEMPT_TABLE}.claim_id",
                f"{START_ATTEMPT_TABLE}.claim_digest",
                f"{START_ATTEMPT_TABLE}.consumption_id",
                f"{START_ATTEMPT_TABLE}.authorization_lease_id",
                f"{START_ATTEMPT_TABLE}.authorization_lease_digest",
                f"{START_ATTEMPT_TABLE}.destination_deployment_id",
                f"{START_ATTEMPT_TABLE}.destination_generation",
                f"{START_ATTEMPT_TABLE}.runtime_envelope_commitment",
                f"{START_ATTEMPT_TABLE}.runtime_envelope_generation",
                f"{START_ATTEMPT_TABLE}.runtime_start_profile_id",
                f"{START_ATTEMPT_TABLE}.runtime_start_profile_version",
                f"{START_ATTEMPT_TABLE}.runtime_start_profile_digest",
                f"{START_ATTEMPT_TABLE}.protected_operation_reference",
                f"{START_ATTEMPT_TABLE}.instruction_digest",
                f"{START_ATTEMPT_TABLE}.started_at",
                f"{START_ATTEMPT_TABLE}.invocation_deadline",
            ],
            name=f"fk_wf_rtready_{prefix}_start_attempt",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "start_consumption_claim_id",
                "start_consumption_claim_digest",
                "start_consumption_id",
                "start_attempt_id",
                "runtime_start_authorization_lease_id",
            ],
            [
                *(f"{START_CONSUMPTION_CLAIM_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_CONSUMPTION_CLAIM_TABLE}.claim_id",
                f"{START_CONSUMPTION_CLAIM_TABLE}.canonical_digest",
                f"{START_CONSUMPTION_CLAIM_TABLE}.consumption_id",
                f"{START_CONSUMPTION_CLAIM_TABLE}.attempt_id",
                f"{START_CONSUMPTION_CLAIM_TABLE}.authorization_lease_id",
            ],
            name=f"fk_wf_rtready_{prefix}_start_claim",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "runtime_start_authorization_lease_id",
                "runtime_start_authorization_lease_digest",
                "runtime_start_authorization_claim_id",
                "runtime_start_authorization_claim_digest",
                "use_result_id",
                "use_result_digest",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_generation",
                "runtime_envelope_id",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "runtime_start_profile_id",
                "runtime_start_profile_version",
                "runtime_start_profile_digest",
            ],
            [
                *(f"{START_LEASE_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_LEASE_TABLE}.authorization_lease_id",
                f"{START_LEASE_TABLE}.canonical_digest",
                f"{START_LEASE_TABLE}.claim_id",
                f"{START_LEASE_TABLE}.claim_digest",
                f"{START_LEASE_TABLE}.use_result_id",
                f"{START_LEASE_TABLE}.use_result_digest",
                f"{START_LEASE_TABLE}.destination_deployment_id",
                f"{START_LEASE_TABLE}.destination_generation",
                f"{START_LEASE_TABLE}.destination_fencing_token_digest",
                f"{START_LEASE_TABLE}.runtime_slot_commitment",
                f"{START_LEASE_TABLE}.runtime_slot_post_generation",
                f"{START_LEASE_TABLE}.runtime_envelope_id",
                f"{START_LEASE_TABLE}.runtime_envelope_commitment",
                f"{START_LEASE_TABLE}.runtime_envelope_generation",
                f"{START_LEASE_TABLE}.runtime_start_profile_id",
                f"{START_LEASE_TABLE}.runtime_start_profile_version",
                f"{START_LEASE_TABLE}.runtime_start_profile_digest",
            ],
            name=f"fk_wf_rtready_{prefix}_start_lease",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "runtime_start_authorization_claim_id",
                "runtime_start_authorization_claim_digest",
                "runtime_start_authorization_lease_id",
            ],
            [
                *(f"{START_CLAIM_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_CLAIM_TABLE}.claim_id",
                f"{START_CLAIM_TABLE}.canonical_digest",
                f"{START_CLAIM_TABLE}.authorization_lease_id",
            ],
            name=f"fk_wf_rtready_{prefix}_start_auth_claim",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "runtime_envelope_id",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "use_result_id",
                "use_result_digest",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_generation",
                "coordination_state",
                "runtime_start_authorization_lease_id",
                "start_consumption_claim_id",
                "start_attempt_id",
                "start_result_id",
                "start_result_digest",
                "runtime_start_attempt_pending",
                "runtime_start_attempt_terminal",
                "runtime_started",
                "runtime_resumed",
                "process_created",
                "process_scheduled",
            ],
            [
                *(f"{START_COORDINATION_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{START_COORDINATION_TABLE}.runtime_envelope_id",
                f"{START_COORDINATION_TABLE}.runtime_envelope_commitment",
                f"{START_COORDINATION_TABLE}.runtime_envelope_generation",
                f"{START_COORDINATION_TABLE}.use_result_id",
                f"{START_COORDINATION_TABLE}.use_result_digest",
                f"{START_COORDINATION_TABLE}.destination_deployment_id",
                f"{START_COORDINATION_TABLE}.destination_generation",
                f"{START_COORDINATION_TABLE}.destination_fencing_token_digest",
                f"{START_COORDINATION_TABLE}.runtime_slot_commitment",
                f"{START_COORDINATION_TABLE}.runtime_slot_post_generation",
                f"{START_COORDINATION_TABLE}.state",
                f"{START_COORDINATION_TABLE}.active_authorization_lease_id",
                f"{START_COORDINATION_TABLE}.consumption_claim_id",
                f"{START_COORDINATION_TABLE}.runtime_start_attempt_id",
                f"{START_COORDINATION_TABLE}.runtime_start_result_id",
                f"{START_COORDINATION_TABLE}.runtime_start_result_digest",
                f"{START_COORDINATION_TABLE}.runtime_start_attempt_pending",
                f"{START_COORDINATION_TABLE}.runtime_start_attempt_terminal",
                f"{START_COORDINATION_TABLE}.runtime_started",
                f"{START_COORDINATION_TABLE}.runtime_resumed",
                f"{START_COORDINATION_TABLE}.process_created",
                f"{START_COORDINATION_TABLE}.process_scheduled",
            ],
            name=f"fk_wf_rtready_{prefix}_started_head",
        ),
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtready_src_use_result_scope",
        USE_RESULT_TABLE,
        [*SCOPE_COLUMNS, "result_id", "canonical_digest"],
    )
    for column_name in SCOPE_COLUMNS:
        op.add_column(
            START_COORDINATION_TABLE,
            sa.Column(column_name, sa.String(128), nullable=True),
        )
    op.execute(
        sa.text(f"""
        UPDATE {START_COORDINATION_TABLE} AS coordination
        SET organization_id = source.organization_id,
            environment_id = source.environment_id,
            site_id = source.site_id
        FROM {USE_RESULT_TABLE} AS source
        WHERE source.result_id = coordination.use_result_id
          AND source.canonical_digest = coordination.use_result_digest
    """)
    )
    for column_name in SCOPE_COLUMNS:
        op.alter_column(
            START_COORDINATION_TABLE,
            column_name,
            existing_type=sa.String(128),
            nullable=False,
        )
    op.create_foreign_key(
        "fk_wf_rtstart_coord_ready_scope",
        START_COORDINATION_TABLE,
        USE_RESULT_TABLE,
        [*SCOPE_COLUMNS, "use_result_id", "use_result_digest"],
        [*SCOPE_COLUMNS, "result_id", "canonical_digest"],
    )
    op.execute(
        sa.text(f"""
        CREATE FUNCTION {COORDINATION_SCOPE_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            authoritative_organization_id varchar(128);
            authoritative_environment_id varchar(128);
            authoritative_site_id varchar(128);
        BEGIN
            SELECT organization_id, environment_id, site_id
              INTO STRICT authoritative_organization_id,
                          authoritative_environment_id,
                          authoritative_site_id
              FROM {USE_RESULT_TABLE}
             WHERE result_id = NEW.use_result_id
               AND canonical_digest = NEW.use_result_digest;

            IF (NEW.organization_id IS NOT NULL
                    AND NEW.organization_id <> authoritative_organization_id)
               OR (NEW.environment_id IS NOT NULL
                    AND NEW.environment_id <> authoritative_environment_id)
               OR (NEW.site_id IS NOT NULL
                    AND NEW.site_id <> authoritative_site_id) THEN
                RAISE EXCEPTION 'runtime-start coordination scope does not match use result'
                    USING ERRCODE = '23503';
            END IF;

            NEW.organization_id := authoritative_organization_id;
            NEW.environment_id := authoritative_environment_id;
            NEW.site_id := authoritative_site_id;
            RETURN NEW;
        EXCEPTION WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'runtime-start coordination use result is unavailable'
                USING ERRCODE = '23503';
        END;
        $$
    """)
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER trg_wf_rtstart_coord_ready_scope "
            f"BEFORE INSERT OR UPDATE OF organization_id, environment_id, site_id, "
            f"use_result_id, use_result_digest ON {START_COORDINATION_TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION {COORDINATION_SCOPE_FUNCTION}()"
        )
    )
    for name, table, columns in SCOPED_SOURCE_UNIQUES:
        op.create_unique_constraint(name, table, [*SCOPE_COLUMNS, *columns])

    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("readiness_attestation_id", sa.String(128), nullable=False),
        sa.Column("readiness_attestation_digest", sa.String(64), nullable=False),
        sa.Column("readiness_attestation_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("runtime_envelope_eligible_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_profile_id", sa.String(128), nullable=False),
        sa.Column("readiness_profile_version", sa.String(64), nullable=False),
        sa.Column("readiness_profile_digest", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("readiness_attestation_payload", postgresql.JSONB(), nullable=False),
        *_source_constraints(prefix="lease"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtready_auth_lease_claim"),
        sa.UniqueConstraint("start_result_id", name="uq_wf_rtready_auth_lease_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            name="uq_wf_rtready_auth_lease_slot",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtready_auth_lease_digest"),
        sa.UniqueConstraint(
            *SCOPE_COLUMNS,
            "authorization_lease_id",
            "start_result_id",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            name="uq_wf_rtready_auth_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtready_auth_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtready_auth_lease_source"),
        sa.CheckConstraint(
            "start_result_recorded_at <= readiness_attestation_observed_at "
            "AND readiness_attestation_observed_at <= issued_at "
            "AND readiness_attestation_observed_at < readiness_attestation_valid_until "
            "AND readiness_attestation_valid_until "
            "<= readiness_attestation_observed_at + INTERVAL '1 second' "
            "AND issued_at < valid_until AND valid_until = effective_until "
            "AND effective_until <= readiness_attestation_valid_until "
            "AND effective_until <= runtime_envelope_eligible_until "
            "AND valid_until <= issued_at + INTERVAL '1 second'",
            name="ck_wf_rtready_auth_lease_window",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND state = 'authorized_unconsumed'",
            name="ck_wf_rtready_auth_lease_semantics",
        ),
        sa.CheckConstraint(
            "readiness_profile_id = 'profile.workflow-protected-runtime-readiness' "
            "AND readiness_profile_version = '1.0' "
            f"AND readiness_profile_digest = '{READINESS_PROFILE_DIGEST}'",
            name="ck_wf_rtready_auth_lease_profile",
        ),
        sa.CheckConstraint(
            _zero_prior_authority() + " AND protected_runtime_readiness_authority_granted",
            name="ck_wf_rtready_auth_lease_authority",
        ),
        sa.CheckConstraint(
            "length(readiness_attestation_digest) = 64 "
            "AND jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(readiness_attestation_payload) = 'object' "
            "AND readiness_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtready_auth_lease_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtready_auth_lease_scope",
        LEASE_TABLE,
        ["organization_id", "environment_id", "site_id", "issued_at"],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        *_source_constraints(prefix="claim"),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "authorization_lease_id",
                "start_result_id",
                "runtime_slot_commitment",
                "runtime_slot_generation",
            ],
            [
                *(f"{LEASE_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.start_result_id",
                f"{LEASE_TABLE}.runtime_slot_commitment",
                f"{LEASE_TABLE}.runtime_slot_generation",
            ],
            name="fk_wf_rtready_auth_claim_lease",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtready_auth_claim_lease"),
        sa.UniqueConstraint("start_result_id", name="uq_wf_rtready_auth_claim_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            name="uq_wf_rtready_auth_claim_slot",
        ),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_rtready_auth_scope_idem",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtready_auth_claim_digest"),
        sa.UniqueConstraint(
            *SCOPE_COLUMNS,
            "claim_id",
            "canonical_digest",
            "authorization_lease_id",
            name="uq_wf_rtready_auth_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtready_auth_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtready_auth_claim_source"),
        sa.CheckConstraint(
            "start_result_recorded_at <= claimed_at",
            name="ck_wf_rtready_auth_claim_window",
        ),
        sa.CheckConstraint(
            _zero_prior_authority() + " AND NOT protected_runtime_readiness_authority_granted",
            name="ck_wf_rtready_auth_claim_authority",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64 "
            "AND length(idempotency_scope_id) = 64 "
            "AND length(idempotency_digest) = 64 "
            "AND length(authorization_audit_digest) = 64 "
            "AND jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtready_auth_claim_audit",
        ),
    )
    op.create_index(
        "ix_wf_rtready_auth_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )
    op.create_foreign_key(
        "fk_wf_rtready_auth_lease_claim",
        LEASE_TABLE,
        CLAIM_TABLE,
        [*SCOPE_COLUMNS, "claim_id", "claim_digest", "authorization_lease_id"],
        [*SCOPE_COLUMNS, "claim_id", "canonical_digest", "authorization_lease_id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'protected runtime-readiness authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rtready_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_rtready_auth_claim_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rtready_auth_lease_no_truncate"),
        (CLAIM_TABLE, "trg_wf_rtready_auth_claim_no_truncate"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE TRUNCATE ON {table} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {LEASE_TABLE} LIMIT 1)
               OR EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: protected runtime-readiness authorization evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_constraint("fk_wf_rtready_auth_lease_claim", LEASE_TABLE, type_="foreignkey")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    for name, table, _columns in reversed(SCOPED_SOURCE_UNIQUES):
        op.drop_constraint(name, table, type_="unique")
    op.execute(
        sa.text(
            f"DROP TRIGGER IF EXISTS trg_wf_rtstart_coord_ready_scope ON {START_COORDINATION_TABLE}"
        )
    )
    op.drop_constraint(
        "fk_wf_rtstart_coord_ready_scope",
        START_COORDINATION_TABLE,
        type_="foreignkey",
    )
    for column_name in reversed(SCOPE_COLUMNS):
        op.drop_column(START_COORDINATION_TABLE, column_name)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {COORDINATION_SCOPE_FUNCTION}()"))
    op.drop_constraint("uq_wf_rtready_src_use_result_scope", USE_RESULT_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
