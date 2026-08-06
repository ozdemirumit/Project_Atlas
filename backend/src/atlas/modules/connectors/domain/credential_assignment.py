from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DISABLED_CREDENTIALS_ASSIGNED = "disabled_credentials_assigned"


@dataclass(frozen=True, slots=True)
class ConnectorCredentialProfileSnapshot:
    profile_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    target_profile_id: str
    target_id: str
    target_type: str
    target_product: str
    secret_reference_id: str
    secret_store_profile_id: str
    credential_class: str
    authentication_method: str
    vendor_role: str
    privilege_class: str
    allowed_connector_ids: tuple[str, ...]
    allowed_release_versions: tuple[str, ...]
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.target_profile_id,
            self.target_id,
            self.target_type,
            self.secret_reference_id,
            self.secret_store_profile_id,
            self.credential_class,
            self.authentication_method,
            self.vendor_role,
            self.privilege_class,
            *self.allowed_connector_ids,
            *self.allowed_release_versions,
            self.rotation_state,
            self.revocation_state,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector credential profile identifier")
        if (
            self.version != 1
            or not self.allowed_connector_ids
            or not self.allowed_release_versions
            or not 1 <= len(self.target_product.strip()) <= 200
            or self.rotation_state != "rotation.current"
            or self.revocation_state != "revocation.active"
            or not self.signature_verified
            or any(
                item.tzinfo is None
                for item in (self.next_rotation_at, self.issued_at, self.expires_at)
            )
            or not self.issued_at < self.next_rotation_at < self.expires_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector credential profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorCredentialAssignmentPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_target_binding_schema: str
    required_credential_profile_schema: str
    maximum_target_binding_age_hours: int
    maximum_credential_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_credential_profile_signer_id: str
    allowed_secret_store_profile_ids: tuple[str, ...]
    allowed_credential_classes: tuple[str, ...]
    allowed_authentication_methods: tuple[str, ...]
    allowed_privilege_classes: tuple[str, ...]
    required_rotation_state: str
    required_revocation_state: str
    minimum_rotation_window_hours: int
    required_effective_state: str
    assignment_record_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_target_binding_schema,
            self.required_credential_profile_schema,
            self.required_credential_profile_signer_id,
            *self.allowed_secret_store_profile_ids,
            *self.allowed_credential_classes,
            *self.allowed_authentication_methods,
            *self.allowed_privilege_classes,
            self.required_rotation_state,
            self.required_revocation_state,
            self.required_effective_state,
            self.assignment_record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "credential assignment policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_target_binding_age_hours <= 87600
            or not 1 <= self.maximum_credential_profile_age_hours <= 87600
            or not 1 <= self.minimum_rotation_window_hours <= 8760
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or not self.allowed_secret_store_profile_ids
            or not self.allowed_credential_classes
            or not self.allowed_authentication_methods
            or not self.allowed_privilege_classes
            or self.required_effective_state != DISABLED_CREDENTIALS_ASSIGNED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Credential assignment policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorCredentialAssignmentRecord:
    assignment_id: str
    schema_version: str
    version: int
    source_target_binding_id: str
    source_target_binding_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    owner_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_type: str
    target_product: str
    credential_profile_id: str
    credential_profile_digest: str
    credential_class: str
    authentication_method: str
    vendor_role: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    credential_policy_id: str
    credential_policy_digest: str
    credential_policy_version: str
    assignment_version: int
    instance_state: str
    assigned_by: str
    purpose: str
    assigned_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_installed: bool = True
    instance_created: bool = True
    target_configured: bool = True
    eligible_for_credential_governance: bool = True
    credential_references_assigned: bool = True
    eligible_for_configuration_validation: bool = True
    promotion_blocked: bool = False
    credentials_resolved: bool = False
    connector_enabled: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.assignment_id,
            self.schema_version,
            self.source_target_binding_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.owner_id,
            self.target_profile_id,
            self.site_id,
            self.target_type,
            self.credential_profile_id,
            self.credential_class,
            self.authentication_method,
            self.vendor_role,
            self.privilege_class,
            self.rotation_state,
            self.revocation_state,
            self.credential_policy_id,
            self.credential_policy_version,
            self.instance_state,
            self.assigned_by,
        ):
            validate_stable_identifier(value, "credential assignment record identifier")
        if (
            self.version != 1
            or self.assignment_version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_target_binding_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.credential_profile_digest,
                    self.credential_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 3 <= len(self.display_name.strip()) <= 200
            or not 1 <= len(self.target_product.strip()) <= 200
            or self.instance_state != DISABLED_CREDENTIALS_ASSIGNED
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or any(item.tzinfo is None for item in (self.next_rotation_at, self.assigned_at))
            or not all(
                (
                    self.package_installed,
                    self.instance_created,
                    self.target_configured,
                    self.eligible_for_credential_governance,
                    self.credential_references_assigned,
                    self.eligible_for_configuration_validation,
                )
            )
            or self.promotion_blocked
            or any(
                (
                    self.credentials_resolved,
                    self.connector_enabled,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Credential assignment violates the authority boundary")
