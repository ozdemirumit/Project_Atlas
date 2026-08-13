from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel


def _ids(*values: str) -> bool:
    return all(3 <= len(value.strip()) <= 256 for value in values)


def _digests(*values: str) -> bool:
    return all(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in values
    )


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    endpoint_profile_id: str
    endpoint_profile_digest: str
    endpoint_owner_id: str
    endpoint_evaluator_id: str
    required_gateway_id: str
    required_gateway_attestor_id: str
    required_receipt_schema: str
    protected_result_vault_id: str
    model_id: str
    provider_type: str
    task_class: str
    output_schema_version: str
    destination_profile_digest: str
    classification_ceiling: str
    network_boundary_digest: str
    secret_reference_digest: str
    browser_binding_key_digest: str
    maximum_authentication_age_minutes: int
    maximum_context_characters: int
    maximum_context_tokens: int
    maximum_output_tokens: int
    timeout_seconds: int
    retention_minutes: int
    accepted_finish_reasons: tuple[str, ...]
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    endpoint_active: bool
    evaluation_approved: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.policy_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.endpoint_profile_id,
                self.model_id,
                self.task_class,
                self.output_schema_version,
            )
            or self.provider_type != "openai_compatible"
            or not _digests(
                self.endpoint_profile_digest,
                self.destination_profile_digest,
                self.network_boundary_digest,
                self.secret_reference_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1_000 <= self.maximum_context_characters <= 1_000_000
            or not 250 <= self.maximum_context_tokens <= 250_000
            or not 1 <= self.maximum_output_tokens <= 8_192
            or not 1 <= self.timeout_seconds <= 120
            or not 1 <= self.retention_minutes <= 1_440
            or not self.accepted_finish_reasons
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not all((self.signature_verified, self.endpoint_active, self.evaluation_approved))
        ):
            raise ValueError("Protected model-invocation policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationInstruction:
    invocation_id: str
    context_id: str
    context_digest: str
    context_package_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    authorization_context_digest: str
    invocation_authorization_digest: str
    endpoint_profile_id: str
    endpoint_profile_digest: str
    model_id: str
    task_class: str
    output_schema_version: str
    maximum_output_tokens: int
    timeout_seconds: int
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedModelResponseDraft:
    invocation_id: str
    summary: str
    citation_references: tuple[str, ...]
    unknowns: tuple[str, ...]
    endpoint_profile_id: str
    model_id: str
    finish_reason: str
    response_schema_version: str
    input_tokens: int
    output_tokens: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationReceipt:
    invocation_id: str
    schema_version: str
    version: int
    gateway_id: str
    attested_by: str
    context_id: str
    context_digest: str
    context_package_digest: str
    authorization_context_digest: str
    endpoint_profile_id: str
    endpoint_profile_digest: str
    model_id: str
    response_schema_version: str
    protected_draft_reference: str
    protected_draft_digest: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    outcome: str
    invoked_at: datetime
    expires_at: datetime
    tools_disabled: bool
    streaming_disabled: bool
    schema_verified: bool
    citations_verified: bool
    output_safety_verified: bool
    protected_vault_write_verified: bool
    signature_verified: bool
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationClaim:
    claim_id: str
    schema_version: str
    version: int
    invocation_id: str
    context_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationRecord:
    invocation_id: str
    schema_version: str
    version: int
    claim_id: str
    context_id: str
    context_digest: str
    context_package_digest: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    gateway_id: str
    invocation_receipt_digest: str
    invocation_authorization_digest: str
    endpoint_profile_id: str
    endpoint_profile_digest: str
    model_id: str
    task_class: str
    response_schema_version: str
    protected_draft_reference: str
    protected_draft_digest: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    input_tokens: int
    output_tokens: int
    maximum_output_tokens: int
    finish_reason: str
    outcome: str
    invoked_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool = True
    model_context_available: bool = True
    model_invoked: bool = True
    protected_draft_available: bool = True
    answer_generated: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        later = (
            self.answer_generated,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        if (
            self.version != 1
            or self.instance_state != "protected_model_invoked"
            or self.outcome != "invocation-outcome.completed"
            or not all(
                (
                    self.knowledge_retrieved,
                    self.model_context_available,
                    self.model_invoked,
                    self.protected_draft_available,
                )
            )
            or any(later)
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or self.input_tokens < 0
            or not 0 < self.output_tokens <= self.maximum_output_tokens
            or self.invoked_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.invoked_at < self.expires_at
        ):
            raise ValueError("Protected model-invocation record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationManifest:
    invocation_id: str
    context_id: str
    endpoint_profile_id: str
    model_id: str
    task_class: str
    response_schema_version: str
    citation_count: int
    unknown_count: int
    input_tokens: int
    output_tokens: int
    maximum_output_tokens: int
    finish_reason: str
    outcome: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    invoked_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedModelInvocationResult:
    record: ProtectedModelInvocationRecord
    manifest: ProtectedModelInvocationManifest
