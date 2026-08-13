from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ASSEMBLED_STATE = "protected_model_context_assembled"
INSUFFICIENT_STATE = "protected_model_context_insufficient"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "protected model-context identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class ProtectedModelContextPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_retrieval_schema: str
    required_retrieval_state: str
    required_assembler_id: str
    required_assembler_attestor_id: str
    required_receipt_schema: str
    protected_vault_id: str
    task_class: str
    output_schema_version: str
    context_profile_digest: str
    safety_profile_digest: str
    budgeting_profile_digest: str
    destination_profile_digest: str
    browser_binding_key_digest: str
    maximum_authentication_age_minutes: int
    maximum_objective_characters: int
    maximum_context_characters: int
    maximum_estimated_tokens: int
    maximum_evidence_items: int
    retention_minutes: int
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_retrieval_schema,
            self.required_retrieval_state,
            self.required_assembler_id,
            self.required_assembler_attestor_id,
            self.required_receipt_schema,
            self.protected_vault_id,
            self.task_class,
            self.output_schema_version,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 64 <= self.maximum_objective_characters <= 4_000
            or not 1_000 <= self.maximum_context_characters <= 100_000
            or not 256 <= self.maximum_estimated_tokens <= 25_000
            or not 1 <= self.maximum_evidence_items <= 20
            or not 1 <= self.retention_minutes <= 1_440
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.context_profile_digest,
                self.safety_profile_digest,
                self.budgeting_profile_digest,
                self.destination_profile_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected model-context policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextInstruction:
    context_id: str
    retrieval_id: str
    retrieval_digest: str
    retrieval_receipt_digest: str
    evidence_package_digest: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    consumer_subject_digest: str
    authorization_context_digest: str
    browser_session_binding_digest: str
    objective: str
    objective_digest: str
    purpose: str
    policy_id: str
    policy_digest: str
    task_class: str
    output_schema_version: str
    context_profile_digest: str
    safety_profile_digest: str
    budgeting_profile_digest: str
    destination_profile_digest: str
    maximum_context_characters: int
    maximum_estimated_tokens: int
    maximum_evidence_items: int
    protected_vault_id: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.context_id,
            self.retrieval_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.policy_id,
            self.task_class,
            self.output_schema_version,
            self.protected_vault_id,
        )
        if (
            not 3 <= len(self.objective.strip()) <= 4_000
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or not 1_000 <= self.maximum_context_characters <= 100_000
            or not 256 <= self.maximum_estimated_tokens <= 25_000
            or not 1 <= self.maximum_evidence_items <= 20
            or self.requested_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.requested_at < self.expires_at
            or not _digests(
                self.retrieval_digest,
                self.retrieval_receipt_digest,
                self.evidence_package_digest,
                self.consumer_subject_digest,
                self.authorization_context_digest,
                self.browser_session_binding_digest,
                self.objective_digest,
                self.policy_digest,
                self.context_profile_digest,
                self.safety_profile_digest,
                self.budgeting_profile_digest,
                self.destination_profile_digest,
            )
        ):
            raise ValueError("Protected model-context instruction is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextEvidenceUnit:
    evidence_reference_id: str
    citation_binding_digest: str
    content: str
    safety_state: str

    def __post_init__(self) -> None:
        _ids(self.evidence_reference_id, self.safety_state)
        if not self.content.strip() or not _digests(self.citation_binding_digest):
            raise ValueError("Protected model-context evidence unit is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextPackage:
    context_id: str
    task_class: str
    output_schema_version: str
    platform_safety_layer: str
    task_contract_layer: str
    untrusted_objective: str
    evidence_units: tuple[ProtectedModelContextEvidenceUnit, ...]
    output_contract_layer: str
    character_count: int
    estimated_token_count: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(self.context_id, self.task_class, self.output_schema_version)
        content = (
            self.platform_safety_layer,
            self.task_contract_layer,
            self.untrusted_objective,
            self.output_contract_layer,
        )
        if (
            not all(item.strip() for item in content)
            or self.character_count < sum(len(item) for item in content)
            or self.estimated_token_count != (self.character_count + 3) // 4
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.generated_at < self.expires_at
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected model-context package is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextReceipt:
    context_id: str
    schema_version: str
    version: int
    assembler_id: str
    attested_by: str
    retrieval_id: str
    retrieval_digest: str
    consumer_subject_digest: str
    authorization_context_digest: str
    objective_digest: str
    context_package_digest: str
    protected_artifact_reference: str
    protected_artifact_digest: str
    evidence_set_digest: str
    citation_set_digest: str
    safety_validation_digest: str
    budget_allocation_digest: str
    destination_profile_digest: str
    included_evidence_count: int
    character_count: int
    estimated_token_count: int
    outcome: str
    assembled_at: datetime
    expires_at: datetime
    instructions_isolated: bool
    citations_bound: bool
    budget_verified: bool
    protected_vault_write_verified: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.context_id,
            self.schema_version,
            self.assembler_id,
            self.attested_by,
            self.retrieval_id,
            self.protected_artifact_reference,
            self.outcome,
        )
        if (
            self.version != 1
            or not 0 <= self.included_evidence_count <= 20
            or self.character_count <= 0
            or self.estimated_token_count <= 0
            or self.outcome
            not in {"context-outcome.assembled", "context-outcome.insufficient-evidence"}
            or self.assembled_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.assembled_at < self.expires_at
            or not all(
                (
                    self.instructions_isolated,
                    self.citations_bound,
                    self.budget_verified,
                    self.protected_vault_write_verified,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.retrieval_digest,
                self.consumer_subject_digest,
                self.authorization_context_digest,
                self.objective_digest,
                self.context_package_digest,
                self.protected_artifact_digest,
                self.evidence_set_digest,
                self.citation_set_digest,
                self.safety_validation_digest,
                self.budget_allocation_digest,
                self.destination_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected model-context receipt is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextClaim:
    claim_id: str
    schema_version: str
    version: int
    context_id: str
    retrieval_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    objective_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.context_id,
            self.retrieval_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.objective_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected model-context claim is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextRecord:
    context_id: str
    schema_version: str
    version: int
    claim_id: str
    retrieval_id: str
    retrieval_digest: str
    publication_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    context_policy_id: str
    context_policy_digest: str
    context_policy_version: str
    assembler_id: str
    assembly_receipt_digest: str
    objective_digest: str
    authorization_context_digest: str
    context_package_digest: str
    protected_artifact_reference: str
    protected_artifact_digest: str
    evidence_set_digest: str
    citation_set_digest: str
    safety_validation_digest: str
    budget_allocation_digest: str
    destination_profile_digest: str
    task_class: str
    output_schema_version: str
    included_evidence_count: int
    character_count: int
    estimated_token_count: int
    maximum_context_characters: int
    maximum_estimated_tokens: int
    outcome: str
    assembled_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool = True
    model_context_available: bool = True
    model_invoked: bool = False
    answer_generated: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.context_id,
            self.schema_version,
            self.claim_id,
            self.retrieval_id,
            self.publication_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.context_policy_id,
            self.context_policy_version,
            self.assembler_id,
            self.task_class,
            self.output_schema_version,
            self.outcome,
            self.instance_state,
        )
        later = (
            self.model_invoked,
            self.answer_generated,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        assembled = self.outcome == "context-outcome.assembled"
        if (
            self.version != 1
            or self.instance_state != (ASSEMBLED_STATE if assembled else INSUFFICIENT_STATE)
            or not self.knowledge_retrieved
            or self.model_context_available is not assembled
            or any(later)
            or not 0 <= self.included_evidence_count <= 20
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or not 0 < self.character_count <= self.maximum_context_characters
            or not 0 < self.estimated_token_count <= self.maximum_estimated_tokens
            or self.assembled_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.assembled_at < self.expires_at
            or not _digests(
                self.retrieval_digest,
                self.consumer_subject_digest,
                self.browser_session_binding_digest,
                self.context_policy_digest,
                self.assembly_receipt_digest,
                self.objective_digest,
                self.authorization_context_digest,
                self.context_package_digest,
                self.protected_artifact_digest,
                self.evidence_set_digest,
                self.citation_set_digest,
                self.safety_validation_digest,
                self.budget_allocation_digest,
                self.destination_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected model-context record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedModelContextManifest:
    context_id: str
    retrieval_id: str
    task_class: str
    output_schema_version: str
    classification: str
    included_evidence_count: int
    character_count: int
    estimated_token_count: int
    maximum_context_characters: int
    maximum_estimated_tokens: int
    outcome: str
    evidence_set_digest: str
    citation_set_digest: str
    safety_validation_digest: str
    context_package_digest: str
    assembled_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedModelContextResult:
    record: ProtectedModelContextRecord
    manifest: ProtectedModelContextManifest
