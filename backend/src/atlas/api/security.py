from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, Request

from atlas import __version__
from atlas.api.errors import AtlasError
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    AI_GROUNDED_QUERY_CREATE,
    AI_PROTECTED_ANSWER_PRESENTATION_CREATE,
    AI_PROTECTED_ANSWER_PRESENTATION_READ,
    AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
    AI_PROTECTED_CANDIDATE_IMPACT_READ,
    AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
    AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
    AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
    AI_PROTECTED_DRAFT_ADJUDICATION_READ,
    AI_PROTECTED_MODEL_CONTEXT_CREATE,
    AI_PROTECTED_MODEL_CONTEXT_READ,
    AI_PROTECTED_MODEL_INVOCATION_CREATE,
    AI_PROTECTED_MODEL_INVOCATION_READ,
    AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
    AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
    AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
    AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
    API_CREDENTIAL_ADMIN_REVOKE,
    API_CREDENTIAL_SELF_CREATE,
    API_CREDENTIAL_SELF_READ,
    API_CREDENTIAL_SELF_REVOKE,
    APPROVAL_REQUEST_CREATE,
    APPROVAL_REQUEST_DECIDE,
    APPROVAL_REQUEST_READ,
    AUDIT_EXPORT,
    AUDIT_READ,
    BACKUP_LOGICAL_CREATE,
    BACKUP_LOGICAL_PREVIEW,
    BACKUP_LOGICAL_RESTORE_VALIDATE,
    BOOTSTRAP_INVALIDATION_PREVIEW,
    BOOTSTRAP_PLAN_READ,
    BOOTSTRAP_STATE_MANAGE,
    BOOTSTRAP_STATE_READ,
    CONNECTOR_BOUNDED_INVOCATION_CREATE,
    CONNECTOR_BOUNDED_INVOCATION_READ,
    CONNECTOR_CAPABILITY_ENABLEMENT_CREATE,
    CONNECTOR_CAPABILITY_ENABLEMENT_READ,
    CONNECTOR_CONFIGURATION_VALIDATION_CREATE,
    CONNECTOR_CONFIGURATION_VALIDATION_READ,
    CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE,
    CONNECTOR_CREDENTIAL_ASSIGNMENT_READ,
    CONNECTOR_INSTANCE_CREATE,
    CONNECTOR_INSTANCE_READ,
    CONNECTOR_INSTANCE_RETIRE,
    CONNECTOR_INVOCATION_AUTHORIZATION_CREATE,
    CONNECTOR_INVOCATION_AUTHORIZATION_READ,
    CONNECTOR_INVOCATION_EVIDENCE_CREATE,
    CONNECTOR_INVOCATION_EVIDENCE_READ,
    CONNECTOR_PACKAGE_ACQUIRE,
    CONNECTOR_PACKAGE_ACQUISITION_READ,
    CONNECTOR_PACKAGE_APPROVAL_CREATE,
    CONNECTOR_PACKAGE_APPROVAL_DECIDE,
    CONNECTOR_PACKAGE_APPROVAL_READ,
    CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_READ,
    CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_CREATE,
    CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_READ,
    CONNECTOR_PACKAGE_CONTRACT_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_CONTRACT_VALIDATION_READ,
    CONNECTOR_PACKAGE_FINAL_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_FINAL_VALIDATION_READ,
    CONNECTOR_PACKAGE_INSTALLATION_CREATE,
    CONNECTOR_PACKAGE_INSTALLATION_READ,
    CONNECTOR_PACKAGE_LAB_SELF_TEST_CREATE,
    CONNECTOR_PACKAGE_LAB_SELF_TEST_READ,
    CONNECTOR_PACKAGE_LICENSE_ANALYSIS_CREATE,
    CONNECTOR_PACKAGE_LICENSE_ANALYSIS_READ,
    CONNECTOR_PACKAGE_MALWARE_ANALYSIS_CREATE,
    CONNECTOR_PACKAGE_MALWARE_ANALYSIS_READ,
    CONNECTOR_PACKAGE_REGISTRATION_CREATE,
    CONNECTOR_PACKAGE_REGISTRATION_READ,
    CONNECTOR_PACKAGE_RUNNER_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_RUNNER_VALIDATION_READ,
    CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_READ,
    CONNECTOR_PACKAGE_SIGNING_CREATE,
    CONNECTOR_PACKAGE_SIGNING_READ,
    CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_CREATE,
    CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_READ,
    CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_CREATE,
    CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_READ,
    CONNECTOR_PACKAGE_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_VALIDATION_READ,
    CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_CREATE,
    CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_READ,
    CONNECTOR_PUBLISHER_ATTESTATION_CREATE,
    CONNECTOR_PUBLISHER_ATTESTATION_READ,
    CONNECTOR_REGISTRY_PUBLICATION_CREATE,
    CONNECTOR_REGISTRY_PUBLICATION_READ,
    CONNECTOR_RUNTIME_ACTIVATION_CREATE,
    CONNECTOR_RUNTIME_ACTIVATION_READ,
    CONNECTOR_RUNTIME_TRUST_CREATE,
    CONNECTOR_RUNTIME_TRUST_READ,
    CONNECTOR_SECRET_BROKERAGE_CREATE,
    CONNECTOR_SECRET_BROKERAGE_READ,
    CONNECTOR_TARGET_CONFIGURATION_CREATE,
    CONNECTOR_TARGET_CONFIGURATION_READ,
    CONNECTOR_TARGET_SESSION_CREATE,
    CONNECTOR_TARGET_SESSION_READ,
    CONNECTOR_UPGRADE_APPROVAL_CREATE,
    CONNECTOR_UPGRADE_APPROVAL_DECIDE,
    CONNECTOR_UPGRADE_APPROVAL_READ,
    CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_CREATE,
    CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_READ,
    CONNECTOR_UPGRADE_CHANGE_CONTEXT_CREATE,
    CONNECTOR_UPGRADE_CHANGE_CONTEXT_READ,
    CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_CREATE,
    CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_VERIFY,
    CONNECTOR_UPGRADE_HANDOFF_READINESS_READ,
    CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_CREATE,
    CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_VERIFY,
    CONNECTOR_UPGRADE_SIGNING_KEY_TRUST_INVENTORY_READ,
    CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_CREATE,
    CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_READ,
    CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_POLICY_PROVENANCE_DIAGNOSTIC_READ,
    CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_READINESS_READ,
    CONVERSATION_CREATE,
    CONVERSATION_READ,
    CONVERSATION_TURN_APPEND,
    DEPLOYMENT_CONFIGURATION_PREVIEW,
    GRAPH_STORAGE_IMPACT_READ,
    HEALTH_CHECK_OVERVIEW_READ,
    HEALTH_CHECK_RUN_CREATE,
    IDENTITY_GOVERNANCE_READ,
    IDENTITY_SELF_READ,
    IDENTITY_SUBJECT_ADMIN_DISABLE,
    INVENTORY_DEVICE_CREATE,
    INVENTORY_DEVICE_READ,
    INVENTORY_DEVICE_RETIRE,
    INVESTIGATION_CREATE,
    ITSM_HANDOFF_REVIEW_DECIDE,
    ITSM_HANDOFF_REVIEW_READ,
    ITSM_INTEGRATION_CREATE,
    ITSM_INTEGRATION_READ,
    ITSM_INTEGRATION_RETIRE,
    ITSM_SANDBOX_CONFORMANCE_CREATE,
    ITSM_SANDBOX_CONFORMANCE_READ,
    ITSM_SANDBOX_ONBOARDING_READ,
    KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
    KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
    KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
    KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
    KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
    KNOWLEDGE_EMBEDDING_GENERATION_READ,
    KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
    KNOWLEDGE_EVIDENCE_DRAFT_READ,
    KNOWLEDGE_FINAL_RESOLUTION_CREATE,
    KNOWLEDGE_FINAL_RESOLUTION_READ,
    KNOWLEDGE_FINDING_PRESENTATION_CREATE,
    KNOWLEDGE_FINDING_PRESENTATION_READ,
    KNOWLEDGE_INDEX_STAGING_CREATE,
    KNOWLEDGE_INDEX_STAGING_READ,
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
    KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
    KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
    KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
    KNOWLEDGE_PUBLICATION_PREPARATION_READ,
    KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
    KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
    KNOWLEDGE_REVIEW_FINDING_CREATE,
    KNOWLEDGE_REVIEW_FINDING_READ,
    KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
    KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
    KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
    KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
    KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
    KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
    MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
    MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
    MCP_BUILDER_CANDIDATE_HANDOFF_READ,
    MCP_BUILDER_DESIGN_CREATE,
    MCP_BUILDER_DESIGN_READ,
    MCP_BUILDER_DOMAIN_REVIEW_CREATE,
    MCP_BUILDER_DOMAIN_REVIEW_READ,
    MCP_BUILDER_GENERATION_CREATE,
    MCP_BUILDER_GENERATION_READ,
    MCP_BUILDER_LAB_VALIDATION_CREATE,
    MCP_BUILDER_LAB_VALIDATION_READ,
    MCP_BUILDER_PROJECT_CREATE,
    MCP_BUILDER_PROJECT_READ,
    MCP_BUILDER_SECURITY_REVIEW_CREATE,
    MCP_BUILDER_SECURITY_REVIEW_READ,
    MCP_BUILDER_VALIDATION_CREATE,
    MCP_BUILDER_VALIDATION_READ,
    RCA_CREATE,
    RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
    RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
    RECOMMENDATION_CREATE,
    RECOMMENDATION_FINAL_DISPOSITION_CREATE,
    RECOMMENDATION_FINAL_DISPOSITION_READ,
    RECOMMENDATION_FINDING_PRESENTATION_CREATE,
    RECOMMENDATION_FINDING_PRESENTATION_READ,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    RECOMMENDATION_PROMOTION_CREATE,
    RECOMMENDATION_PROMOTION_READ,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    RECOMMENDATION_READINESS_CREATE,
    RECOMMENDATION_READINESS_READ,
    RECOMMENDATION_REVIEW_REQUEST_CREATE,
    RECOMMENDATION_REVIEW_REQUEST_READ,
    RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
    RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
    RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
    RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
    RELEASE_PREFLIGHT_READ,
    REPORT_CREATE,
    REPORT_READ,
    SECURITY_EXPORT_OVERVIEW_READ,
    SECURITY_EXPORT_TEST_CREATE,
    SESSION_ADMIN_REVOKE,
    SESSION_SELF_READ,
    SESSION_SELF_REVOKE,
    STORAGE_OVERVIEW_READ,
    SUPPORT_BUNDLE_EXPORT,
    SUPPORT_BUNDLE_PREVIEW,
    UPGRADE_CHANGE_REVIEW_CREATE,
    UPGRADE_CHANGE_REVIEW_PREVIEW,
    UPGRADE_COMPLETION_RECEIPT_CREATE,
    UPGRADE_COMPLETION_RECEIPT_READ,
    UPGRADE_HUMAN_REVIEW_CREATE,
    UPGRADE_HUMAN_REVIEW_DECIDE,
    UPGRADE_HUMAN_REVIEW_READ,
    UPGRADE_READINESS_PREVIEW,
    UPGRADE_ROLLBACK_SIMULATE,
    WORKFLOW_DEFINITION_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_CONSUMER_BINDING_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_READ,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_READ,
    WORKFLOW_PLAN_CANCEL,
    WORKFLOW_PLAN_CREATE,
    WORKFLOW_PLAN_READ,
    WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_READ,
    WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_READ,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_AUTHORIZATION_READ,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_CONSUMPTION_READ,
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_READ,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_READ,
    WORKFLOW_TRANSPORT_PROFILE_READ,
    WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_READ,
    WORKLOAD_IDENTITY_ADMIN_CREATE,
    WORKLOAD_IDENTITY_ADMIN_REVOKE,
    WORKLOAD_IDENTITY_ADMIN_ROTATE,
    WORKLOAD_IDENTITY_GOVERNANCE_READ,
    ai_grounded_query_scope,
    ai_protected_answer_presentation_scope,
    ai_protected_candidate_impact_scope,
    ai_protected_candidate_risk_recovery_scope,
    ai_protected_draft_adjudication_scope,
    ai_protected_model_context_scope,
    ai_protected_model_invocation_scope,
    ai_protected_recommendation_adjudication_scope,
    ai_protected_recommendation_candidate_scope,
    ai_protected_recommendation_presentation_scope,
    api_credential_self_scope,
    approval_scope,
    audit_export_scope,
    bootstrap_invalidation_scope,
    bootstrap_plan_scope,
    bootstrap_state_scope,
    connector_bounded_invocation_scope,
    connector_capability_enablement_scope,
    connector_configuration_validation_scope,
    connector_credential_assignment_scope,
    connector_instance_scope,
    connector_invocation_authorization_scope,
    connector_invocation_evidence_scope,
    connector_package_acquisition_scope,
    connector_package_approval_scope,
    connector_package_authority_behavior_validation_scope,
    connector_package_content_policy_scan_scope,
    connector_package_contract_validation_scope,
    connector_package_final_validation_scope,
    connector_package_installation_scope,
    connector_package_lab_self_test_scope,
    connector_package_license_analysis_scope,
    connector_package_malware_analysis_scope,
    connector_package_registration_scope,
    connector_package_runner_validation_scope,
    connector_package_schema_semantics_validation_scope,
    connector_package_signing_scope,
    connector_package_static_dependency_analysis_scope,
    connector_package_supply_chain_inventory_scope,
    connector_package_validation_scope,
    connector_package_vulnerability_analysis_scope,
    connector_publisher_attestation_scope,
    connector_registry_publication_scope,
    connector_runtime_activation_scope,
    connector_runtime_trust_scope,
    connector_secret_brokerage_scope,
    connector_target_configuration_scope,
    connector_target_session_scope,
    conversation_scope,
    current_identity_scope,
    deployment_configuration_scope,
    graph_storage_impact_scope,
    health_check_scope,
    identity_governance_scope,
    inventory_device_scope,
    investigation_scope,
    itsm_handoff_review_scope,
    itsm_integration_scope,
    logical_backup_scope,
    mcp_builder_scope,
    operational_evidence_knowledge_draft_scope,
    operational_knowledge_correction_scope,
    operational_knowledge_deterministic_chunking_scope,
    operational_knowledge_embedding_generation_scope,
    operational_knowledge_final_resolution_scope,
    operational_knowledge_finding_presentation_scope,
    operational_knowledge_index_staging_scope,
    operational_knowledge_protected_content_scope,
    operational_knowledge_protected_inspection_scope,
    operational_knowledge_protected_retrieval_scope,
    operational_knowledge_publication_preparation_scope,
    operational_knowledge_retrieval_publication_scope,
    operational_knowledge_review_finding_scope,
    operational_knowledge_review_request_scope,
    operational_knowledge_reviewer_assignment_scope,
    operational_knowledge_source_materialization_scope,
    operational_knowledge_track_review_decision_scope,
    rca_scope,
    recommendation_correction_resubmission_scope,
    recommendation_final_disposition_scope,
    recommendation_finding_presentation_scope,
    recommendation_human_review_finding_scope,
    recommendation_promotion_scope,
    recommendation_protected_content_scope,
    recommendation_protected_inspection_scope,
    recommendation_readiness_scope,
    recommendation_review_request_scope,
    recommendation_reviewer_assignment_scope,
    recommendation_scope,
    recommendation_track_review_decision_scope,
    release_preflight_scope,
    report_scope,
    security_export_scope,
    session_self_scope,
    storage_overview_scope,
    support_bundle_scope,
    upgrade_change_review_scope,
    upgrade_completion_receipt_scope,
    upgrade_human_review_scope,
    upgrade_simulation_scope,
    workflow_physical_transport_credential_access_authorization_lease_scope,
    workflow_physical_transport_credential_assignment_binding_scope,
    workflow_physical_transport_credential_assignment_freshness_admission_scope,
    workflow_physical_transport_credential_materialization_scope,
    workflow_physical_transport_endpoint_materialization_scope,
    workflow_physical_transport_endpoint_resolution_authorization_lease_scope,
    workflow_physical_transport_route_binding_scope,
    workflow_physical_transport_route_freshness_admission_scope,
    workflow_physical_transport_target_context_access_authorization_lease_scope,
    workflow_physical_transport_target_context_artifact_opening_scope,
    workflow_physical_transport_target_context_binding_scope,
    workflow_physical_transport_target_context_capsule_consumer_binding_scope,
    workflow_physical_transport_target_context_capsule_handoff_authorization_lease_scope,
    workflow_physical_transport_target_context_capsule_handoff_scope,
    workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope,
    workflow_physical_transport_target_context_capsule_opening_scope,
    workflow_protected_runtime_context_injection_authorization_scope,
    workflow_protected_runtime_context_injection_consumption_scope,
    workflow_scope,
    workflow_transport_compatibility_admission_scope,
    workflow_transport_credential_assignment_snapshot_scope,
    workflow_transport_profile_scope,
    workflow_transport_route_snapshot_scope,
    workload_identity_governance_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    ResourceScope,
)
from atlas.modules.identity.application.api_credentials import (
    ApiCredentialOperationsError,
    ApiCredentialService,
)
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionOperationsError, SessionService
from atlas.modules.identity.application.workload_identities import (
    WorkloadIdentityError,
    WorkloadIdentityService,
)
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.sessions import CredentialKind
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
    WORKFLOW_WORKER_AUDIENCE,
)


def workflow_protected_resident_context_access_authorization_scope(
    organization_id: str, environment: str
) -> ResourceScope:
    return workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope(
        organization_id, environment
    )


def workflow_protected_resident_context_access_consumption_scope(
    organization_id: str, environment: str
) -> ResourceScope:
    return workflow_protected_resident_context_access_authorization_scope(
        organization_id, environment
    )


def _presented_authorization(request: Request) -> tuple[str | None, str | None]:
    value = request.headers.get("Authorization")
    if value is None:
        return None, None
    parts = value.split(" ", maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "invalid", None
    return parts[0].lower(), parts[1]


async def authenticated_subject(request: Request) -> AuthenticatedSubject:
    scheme, credential = _presented_authorization(request)
    settings = request.app.state.settings
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token is not None and scheme is not None:
        raise AtlasError(
            status=400,
            code="ambiguous_authentication",
            title="Ambiguous authentication",
            detail="Use exactly one supported authentication mechanism.",
        )
    if session_token is not None:
        session_service: SessionService = request.app.state.session_service
        try:
            context = await session_service.authenticate(
                session_token,
                csrf_token=request.headers.get(settings.csrf_header_name),
                unsafe_request=request.method not in {"GET", "HEAD", "OPTIONS"},
                correlation_id=str(request.state.correlation_id),
            )
        except SessionOperationsError as exc:
            raise AtlasError(
                status=403,
                code=exc.code,
                title="Session validation failed",
                detail="The browser session could not authorize this request.",
            ) from exc
        if context is None:
            raise AtlasError(
                status=401,
                code="authentication_required",
                title="Authentication required",
                detail="A valid authenticated identity is required for this operation.",
            )
        request.state.authenticated_subject = context.subject
        request.state.authenticated_session_id = context.session_id
        request.state.authenticated_credential_kind = CredentialKind.BROWSER_SESSION
        return context.subject
    if scheme == "bearer" and credential is not None:
        api_credential_service: ApiCredentialService = request.app.state.api_credential_service
        try:
            api_context = await api_credential_service.authenticate(
                credential,
                unsafe_request=request.method not in {"GET", "HEAD", "OPTIONS"},
                correlation_id=str(request.state.correlation_id),
            )
        except ApiCredentialOperationsError as exc:
            raise AtlasError(
                status=403,
                code=exc.code,
                title="API credential denied",
                detail="The API credential cannot authorize this request.",
            ) from exc
        if api_context is None:
            raise AtlasError(
                status=401,
                code="authentication_required",
                title="Authentication required",
                detail="A valid authenticated identity is required for this operation.",
            )
        request.state.authenticated_subject = api_context.subject
        request.state.authenticated_api_credential_id = api_context.credential_id
        request.state.authenticated_credential_kind = CredentialKind.API_TOKEN
        return api_context.subject
    service: IdentityService = request.app.state.identity_service
    subject = await service.authenticate(
        AuthenticationInput(
            correlation_id=str(request.state.correlation_id),
            authorization_scheme=scheme,
            credential=credential,
        )
    )
    if subject is None:
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A valid authenticated identity is required for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def browser_session_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is not CredentialKind.BROWSER_SESSION
    ):
        raise AtlasError(
            status=403,
            code="browser_session_required",
            title="Browser session required",
            detail="Use a CSRF-protected browser session for credential management.",
        )
    return subject


async def workflow_worker_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate the dedicated workflow worker without human-session semantics."""
    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_WORKER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_WORKER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_outbox_publisher_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate the dedicated outbox publisher without human-session semantics."""
    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_transport_profile_registry_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the deployment-owned transport profile registry workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_transport_compatibility_admitter_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the workflow transport compatibility admitter workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_transport_route_registry_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the deployment-owned transport route registry workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_transport_credential_assignment_registry_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the deployment credential-assignment registry workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_route_binder_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the workflow physical transport route binder workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_credential_assignment_binder_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate the one workload audience mapped to binding permission."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    request.state.authorization_permission_id = (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND
    )
    return subject


async def authorize_workflow_physical_transport_credential_assignment_binding_bind(
    request: Request,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_credential_assignment_binder_subject),
    ],
) -> AuthenticatedSubject:
    if getattr(request.state, "authorization_permission_id", None) != (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND
    ):
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current workload is not authorized for this operation.",
        )
    return subject


async def workflow_physical_transport_credential_assignment_freshness_admitter_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the credential-assignment freshness admitter workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience
        == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=(
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE
            ),
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id
        != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_credential_accessor_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the exact credential-access workload and audience."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_target_context_accessor_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the exact protected target-context accessor workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_target_context_capsule_binder_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the exact protected target-context capsule binder workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id != WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_protected_transport_target_context_capsule_consumer_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the exact protected target-context capsule consumer workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id != WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_target_context_binder_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the exact target-context binder workload and audience."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
        or subject.subject_id != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_route_freshness_admitter_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the workflow physical route freshness admitter workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def workflow_physical_transport_endpoint_resolver_subject(
    request: Request,
    authorization: Annotated[
        str | None, Header(alias="Authorization", min_length=1, max_length=8192)
    ] = None,
    audience: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Audience",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
    environment_id: Annotated[
        str | None,
        Header(
            alias="X-Atlas-Environment",
            min_length=3,
            max_length=127,
            pattern=r"^[a-z][a-z0-9_.:-]{2,126}$",
        ),
    ] = None,
) -> AuthenticatedSubject:
    """Authenticate only the physical transport endpoint resolver workload."""

    expected_environment = f"environment.{request.app.state.settings.environment}"
    scheme, separator, token = (authorization or "").partition(" ")
    valid_envelope = (
        separator == " "
        and scheme.lower() == "workload"
        and bool(token)
        and audience == WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE
        and environment_id == expected_environment
    )
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token if valid_envelope else "",
            audience=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
            environment_id=expected_environment,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        ) from exc
    if (
        subject.kind is not SubjectKind.SERVICE
        or subject.authentication_method is not AuthenticationMethod.WORKLOAD_TOKEN
    ):
        raise AtlasError(
            status=401,
            code="workload_authentication_failed",
            title="Workload authentication failed",
            detail="The workload credential is invalid or unavailable for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def inventory_device_mutation_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a CSRF-protected browser session for inventory lifecycle management.",
    )


async def itsm_integration_mutation_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a CSRF-protected browser session for ITSM configuration lifecycle management.",
    )


async def workflow_plan_creation_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        subject.kind is SubjectKind.HUMAN
        and getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a CSRF-protected human browser session to create a workflow plan.",
    )


async def workflow_plan_cancellation_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        subject.kind is SubjectKind.HUMAN
        and getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a CSRF-protected human browser session to cancel a workflow plan.",
    )


async def connector_signing_trust_read_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    settings = request.app.state.settings
    if (
        settings.environment == "development"
        and settings.development_identity_enabled
        and subject.authentication_method is AuthenticationMethod.DEVELOPMENT
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a browser session to read connector signing trust metadata.",
    )


async def connector_signing_conformance_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is CredentialKind.BROWSER_SESSION
    ):
        return subject
    settings = request.app.state.settings
    if (
        settings.environment == "development"
        and settings.development_identity_enabled
        and subject.authentication_method is AuthenticationMethod.DEVELOPMENT
    ):
        return subject
    raise AtlasError(
        status=403,
        code="browser_session_required",
        title="Browser session required",
        detail="Use a CSRF-protected browser session for signing-provider diagnostics.",
    )


async def authorize_identity_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=IDENTITY_SELF_READ,
            resource_type="resource.identity.context",
            scope=current_identity_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_session_self(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.session",
            scope=session_self_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_session_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_session_self(
        request,
        subject,
        permission_id=SESSION_SELF_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_session_self_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_session_self(
        request,
        subject,
        permission_id=SESSION_SELF_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_api_credential_self(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.api-credential",
            scope=api_credential_self_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="API credential management is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_api_credential_self_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_api_credential_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_api_credential_self_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_identity_governance(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
    target_subject_id: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
    target_metadata: tuple[tuple[str, str], ...] = (),
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.governance",
            scope=identity_governance_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            target_subject_id=target_subject_id,
            reason=reason,
            idempotency_key=idempotency_key,
            target_metadata=target_metadata,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Identity governance is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_identity_governance_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=IDENTITY_GOVERNANCE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_session_admin_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    session_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "browser_session", session_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=SESSION_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def authorize_api_credential_admin_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    credential_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "personal_api_credential", credential_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=API_CREDENTIAL_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def authorize_identity_subject_admin_disable(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    subject_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "identity_subject", subject_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=IDENTITY_SUBJECT_ADMIN_DISABLE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def _governance_mutation_audit_fields(request: Request) -> tuple[str | None, str | None]:
    try:
        body = await request.json()
    except ValueError:
        body = None
    raw_reason = body.get("reason") if isinstance(body, dict) else None
    reason = raw_reason.strip() if isinstance(raw_reason, str) else None
    if reason is not None and (
        not reason or len(reason) > 240 or any(ord(character) < 32 for character in reason)
    ):
        reason = None
    raw_idempotency_key = request.headers.get("Idempotency-Key")
    idempotency_key = (
        raw_idempotency_key
        if raw_idempotency_key is not None and len(raw_idempotency_key) <= 128
        else None
    )
    return reason, idempotency_key


async def _authorize_workload_identity(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
    target_subject_id: str | None = None,
    target_metadata: tuple[tuple[str, str], ...] = (),
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.workload",
            scope=workload_identity_governance_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            target_subject_id=target_subject_id,
            reason=reason,
            idempotency_key=idempotency_key,
            target_metadata=target_metadata,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Workload identity governance is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workload_identity_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_GOVERNANCE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_workload_identity_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_workload_identity_rotate(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    identity_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.workload_identity_service.target_audit_fields(
        "workload_identity", identity_id
    )
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_ROTATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        target_metadata=target_metadata,
    )


async def authorize_workload_identity_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    credential_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.workload_identity_service.target_audit_fields(
        "workload_credential", credential_id
    )
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        target_metadata=target_metadata,
    )


async def authorize_storage_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=STORAGE_OVERVIEW_READ,
            resource_type="resource.storage.overview",
            scope=storage_overview_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_inventory_device(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    reason: str | None = None
    idempotency_key: str | None = None
    if capability_class is CapabilityClass.C2_DIAGNOSTIC:
        reason, idempotency_key = await _governance_mutation_audit_fields(request)
        if reason is None and permission_id == INVENTORY_DEVICE_CREATE:
            try:
                body = await request.json()
            except ValueError:
                body = None
            raw_purpose = body.get("purpose") if isinstance(body, dict) else None
            if isinstance(raw_purpose, str):
                candidate = raw_purpose.strip()
                if 20 <= len(candidate) <= 240 and not any(
                    ord(character) < 32 for character in candidate
                ):
                    reason = candidate
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.inventory.device",
            scope=inventory_device_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            reason=reason,
            idempotency_key=idempotency_key,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_inventory_device_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_inventory_device(
        request,
        subject,
        permission_id=INVENTORY_DEVICE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_inventory_device_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
) -> AuthorizationDecision:
    return await _authorize_inventory_device(
        request,
        subject,
        permission_id=INVENTORY_DEVICE_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_inventory_device_retire(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
) -> AuthorizationDecision:
    return await _authorize_inventory_device(
        request,
        subject,
        permission_id=INVENTORY_DEVICE_RETIRE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_itsm_integration(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    reason: str | None = None
    idempotency_key: str | None = None
    if capability_class is CapabilityClass.C2_DIAGNOSTIC:
        reason, idempotency_key = await _governance_mutation_audit_fields(request)
        if reason is None and permission_id == ITSM_INTEGRATION_CREATE:
            try:
                body = await request.json()
            except ValueError:
                body = None
            raw_purpose = body.get("purpose") if isinstance(body, dict) else None
            if isinstance(raw_purpose, str):
                candidate = raw_purpose.strip()
                if 20 <= len(candidate) <= 240 and not any(
                    ord(character) < 32 for character in candidate
                ):
                    reason = candidate
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.itsm.integration",
            scope=itsm_integration_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            reason=reason,
            idempotency_key=idempotency_key,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_itsm_integration_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_INTEGRATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_itsm_integration_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_INTEGRATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_itsm_integration_retire(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_INTEGRATION_RETIRE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_itsm_sandbox_conformance_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_SANDBOX_CONFORMANCE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_itsm_sandbox_conformance_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_SANDBOX_CONFORMANCE_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_itsm_sandbox_onboarding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_integration(
        request,
        subject,
        permission_id=ITSM_SANDBOX_ONBOARDING_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_release_preflight_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RELEASE_PREFLIGHT_READ,
            resource_type="resource.platform.release-preflight",
            scope=release_preflight_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_deployment_configuration_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=DEPLOYMENT_CONFIGURATION_PREVIEW,
            resource_type="resource.platform.deployment-configuration",
            scope=deployment_configuration_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_bootstrap_plan_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=BOOTSTRAP_PLAN_READ,
            resource_type="resource.platform.bootstrap-plan",
            scope=bootstrap_plan_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_bootstrap_invalidation_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=BOOTSTRAP_INVALIDATION_PREVIEW,
            resource_type="resource.platform.bootstrap-invalidation",
            scope=bootstrap_invalidation_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Bootstrap invalidation preview is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_support_bundle_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_support_bundle(
        request,
        subject,
        permission_id=SUPPORT_BUNDLE_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_support_bundle_export(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_support_bundle(
        request,
        subject,
        permission_id=SUPPORT_BUNDLE_EXPORT,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_support_bundle(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.support.bundle",
            scope=support_bundle_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Support bundle access is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_backup_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_backup_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_restore_validation(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_RESTORE_VALIDATE,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_logical_backup(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.backup.logical",
            scope=logical_backup_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Logical backup or restore validation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_readiness(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_simulation(
        request,
        subject,
        permission_id=UPGRADE_READINESS_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_simulation(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_simulation(
        request,
        subject,
        permission_id=UPGRADE_ROLLBACK_SIMULATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_upgrade_simulation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-simulation",
            scope=upgrade_simulation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade readiness or isolated rollback simulation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_change_review_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_change_review(
        request,
        subject,
        permission_id=UPGRADE_CHANGE_REVIEW_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_change_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_change_review(
        request,
        subject,
        permission_id=UPGRADE_CHANGE_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_upgrade_change_review(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-change-review",
            scope=upgrade_change_review_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade change review is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_human_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_human_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_human_review_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_completion_receipt_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_completion_receipt(
        request,
        subject,
        permission_id=UPGRADE_COMPLETION_RECEIPT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_completion_receipt_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_completion_receipt(
        request,
        subject,
        permission_id=UPGRADE_COMPLETION_RECEIPT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_upgrade_completion_receipt(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-human-review-receipt",
            scope=upgrade_completion_receipt_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Human review completion receipt is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_upgrade_human_review(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-change-human-review",
            scope=upgrade_human_review_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade human review is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_bootstrap_state(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.bootstrap-state",
            scope=bootstrap_state_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Bootstrap coordination is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_bootstrap_state_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_bootstrap_state(
        request,
        subject,
        permission_id=BOOTSTRAP_STATE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_bootstrap_state_manage(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_bootstrap_state(
        request,
        subject,
        permission_id=BOOTSTRAP_STATE_MANAGE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_ai_grounded_query(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=AI_GROUNDED_QUERY_CREATE,
            resource_type="resource.ai.grounded-query",
            scope=ai_grounded_query_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_conversation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.conversation",
            scope=conversation_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_conversation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_conversation(request, subject, permission_id=CONVERSATION_READ)


async def authorize_conversation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_conversation(request, subject, permission_id=CONVERSATION_CREATE)


async def authorize_conversation_turn_append(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_conversation(
        request,
        subject,
        permission_id=CONVERSATION_TURN_APPEND,
    )


async def authorize_graph_storage_impact_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=GRAPH_STORAGE_IMPACT_READ,
            resource_type="resource.graph.storage-impact",
            scope=graph_storage_impact_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_health_check(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.health-check",
            scope=health_check_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_health_check_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_health_check(request, subject, permission_id=HEALTH_CHECK_OVERVIEW_READ)


async def authorize_health_check_run_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_health_check(request, subject, permission_id=HEALTH_CHECK_RUN_CREATE)


async def _authorize_workflow(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.workflow",
            scope=workflow_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_definition_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_workflow(
        request,
        subject,
        permission_id=WORKFLOW_DEFINITION_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_workflow_plan_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_plan_creation_subject)],
) -> AuthorizationDecision:
    return await _authorize_workflow(
        request,
        subject,
        permission_id=WORKFLOW_PLAN_CREATE,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_workflow_plan_cancel(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_plan_cancellation_subject)],
) -> AuthorizationDecision:
    return await _authorize_workflow(
        request,
        subject,
        permission_id=WORKFLOW_PLAN_CANCEL,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_workflow_plan_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_workflow(
        request,
        subject,
        permission_id=WORKFLOW_PLAN_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_workflow_transport_profile_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_TRANSPORT_PROFILE_READ,
            resource_type="resource.workflow.transport-profile-snapshot",
            scope=workflow_transport_profile_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_transport_compatibility_admission_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_TRANSPORT_COMPATIBILITY_ADMISSION_READ,
            resource_type="resource.workflow.transport-compatibility-admission",
            scope=workflow_transport_compatibility_admission_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_transport_route_snapshot_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_TRANSPORT_ROUTE_SNAPSHOT_READ,
            resource_type="resource.workflow.transport-route-snapshot",
            scope=workflow_transport_route_snapshot_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_transport_credential_assignment_snapshot_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_SNAPSHOT_READ,
            resource_type="resource.workflow.transport-credential-assignment-snapshot",
            scope=workflow_transport_credential_assignment_snapshot_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_route_binding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDING_READ,
            resource_type="resource.workflow.physical-transport-route-binding",
            scope=workflow_physical_transport_route_binding_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_credential_assignment_binding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ,
            resource_type=("resource.workflow.physical-transport-credential-assignment-binding"),
            scope=workflow_physical_transport_credential_assignment_binding_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_credential_assignment_freshness_admission_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMISSION_READ
            ),
            resource_type=(
                "resource.workflow.physical-transport-credential-assignment-freshness-admission"
            ),
            scope=(
                workflow_physical_transport_credential_assignment_freshness_admission_scope(
                    subject.organization_id,
                    settings.environment,
                )
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_credential_access_authorization_lease_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESS_AUTHORIZATION_LEASE_READ),
            resource_type=(
                "resource.workflow.physical-transport-credential-access-authorization-lease"
            ),
            scope=workflow_physical_transport_credential_access_authorization_lease_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_route_freshness_admission_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMISSION_READ,
            resource_type="resource.workflow.physical-transport-route-freshness-admission",
            scope=workflow_physical_transport_route_freshness_admission_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_endpoint_resolution_authorization_lease_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLUTION_AUTHORIZATION_LEASE_READ
            ),
            resource_type=(
                "resource.workflow.physical-transport-endpoint-resolution-authorization-lease"
            ),
            scope=(
                workflow_physical_transport_endpoint_resolution_authorization_lease_scope(
                    subject.organization_id,
                    settings.environment,
                )
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_endpoint_materialization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_MATERIALIZATION_READ,
            resource_type=("resource.workflow.physical-transport-endpoint-materialization"),
            scope=workflow_physical_transport_endpoint_materialization_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_credential_materialization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_MATERIALIZATION_READ,
            resource_type="resource.workflow.physical-transport-credential-materialization",
            scope=workflow_physical_transport_credential_materialization_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_target_context_access_authorization_lease_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESS_AUTHORIZATION_LEASE_READ
            ),
            resource_type=(
                "resource.workflow.physical-transport-target-context-access-authorization-lease"
            ),
            scope=(
                workflow_physical_transport_target_context_access_authorization_lease_scope(
                    subject.organization_id,
                    settings.environment,
                )
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_target_context_artifact_opening_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ARTIFACT_OPENING_READ,
            resource_type=("resource.workflow.physical-transport-target-context-artifact-opening"),
            scope=workflow_physical_transport_target_context_artifact_opening_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_target_context_capsule_consumer_binding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_CONSUMER_BINDING_READ
            ),
            resource_type=(
                "resource.workflow.physical-transport-target-context-capsule-consumer-binding"
            ),
            scope=workflow_physical_transport_target_context_capsule_consumer_binding_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_target_context_capsule_handoff_authorization_lease_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_AUTHORIZATION_LEASE_READ
            ),
            resource_type=(
                "resource.workflow."
                "physical-transport-target-context-capsule-handoff-authorization-lease"
            ),
            scope=(
                workflow_physical_transport_target_context_capsule_handoff_authorization_lease_scope(
                    subject.organization_id,
                    settings.environment,
                )
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_target_context_capsule_handoff_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_HANDOFF_READ),
            resource_type=("resource.workflow.physical-transport-target-context-capsule-handoff"),
            scope=workflow_physical_transport_target_context_capsule_handoff_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_target_context_capsule_opening_authorization_lease_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=(
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_AUTHORIZATION_LEASE_READ
            ),
            resource_type=(
                "resource.workflow."
                "physical-transport-target-context-capsule-opening-authorization-lease"
            ),
            scope=workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope(
                subject.organization_id, settings.environment
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_protected_resident_context_access_authorization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    """Authorize the IMP-216 inventory through its dedicated workflow read grant."""

    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_AUTHORIZATION_READ,
            resource_type="resource.workflow.protected-resident-context-access-authorization",
            scope=workflow_protected_resident_context_access_authorization_scope(
                subject.organization_id, settings.environment
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_protected_resident_context_access_consumption_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    """Authorize the ADR-167 minimized inventory with a dedicated human grant."""

    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PROTECTED_RESIDENT_CONTEXT_ACCESS_CONSUMPTION_READ,
            resource_type="resource.workflow.protected-resident-context-access-consumption",
            scope=workflow_protected_resident_context_access_consumption_scope(
                subject.organization_id, settings.environment
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_protected_runtime_context_injection_authorization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    """Authorize the ADR-168 minimized inventory for a normal human session."""

    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_AUTHORIZATION_READ,
            resource_type=("resource.workflow.protected-runtime-context-injection-authorization"),
            scope=workflow_protected_runtime_context_injection_authorization_scope(
                subject.organization_id, settings.environment
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_protected_runtime_context_injection_consumption_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    """Authorize the ADR-169 minimized inventory for a normal human session."""

    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PROTECTED_RUNTIME_CONTEXT_INJECTION_CONSUMPTION_READ,
            resource_type=("resource.workflow.protected-runtime-context-injection-consumption"),
            scope=workflow_protected_runtime_context_injection_consumption_scope(
                subject.organization_id, settings.environment
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_target_context_capsule_opening_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="human_identity_required",
            title="Human identity required",
            detail="This read-only inventory is available only to an authenticated human.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_CAPSULE_OPENING_READ,
            resource_type=("resource.workflow.physical-transport-target-context-capsule-opening"),
            scope=workflow_physical_transport_target_context_capsule_opening_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workflow_physical_transport_target_context_binding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ,
            resource_type="resource.workflow.physical-transport-target-context-binding",
            scope=workflow_physical_transport_target_context_binding_scope(
                subject.organization_id,
                settings.environment,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_investigation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=INVESTIGATION_CREATE,
            resource_type="resource.investigation",
            scope=investigation_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_rca_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RCA_CREATE,
            resource_type="resource.rca",
            scope=rca_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_recommendation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RECOMMENDATION_CREATE,
            resource_type="resource.recommendation",
            scope=recommendation_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_approval(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.approval",
            scope=approval_scope(subject.organization_id, settings.environment, capability_class),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The approval operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_approval_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_approval_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_approval_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_report_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=REPORT_CREATE,
            resource_type="resource.report",
            scope=report_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_report_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=REPORT_READ,
            resource_type="resource.report",
            scope=report_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized to read this report.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_itsm_handoff_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_handoff_review(
        request,
        subject,
        permission_id=ITSM_HANDOFF_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_itsm_handoff_review_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_itsm_handoff_review(
        request,
        subject,
        permission_id=ITSM_HANDOFF_REVIEW_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_itsm_handoff_review(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.report.itsm-handoff-review",
            scope=itsm_handoff_review_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="ITSM handoff human review is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_security_export(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.security-export",
            scope=security_export_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_security_export_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_security_export(
        request, subject, permission_id=SECURITY_EXPORT_OVERVIEW_READ
    )


async def authorize_security_export_test_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_security_export(
        request, subject, permission_id=SECURITY_EXPORT_TEST_CREATE
    )


async def _authorize_audit_export(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    scope = audit_export_scope(
        subject.organization_id,
        settings.environment,
        capability_class,
    )
    requested_at = datetime.now(UTC)
    if (
        subject.kind is not SubjectKind.HUMAN
        or subject.authentication_method is AuthenticationMethod.DEVELOPMENT
    ):
        await request.app.state.audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.audit.access.denied",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=requested_at,
                correlation_id=str(request.state.correlation_id),
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.audit.events",
                scope_reference=scope.reference,
                decision_id=None,
                outcome="denied",
                result_code="enterprise_human_browser_required",
            )
        )
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.audit.events",
            scope=scope,
            correlation_id=str(request.state.correlation_id),
            requested_at=requested_at,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_audit_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_audit_export(
        request,
        subject,
        permission_id=AUDIT_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_audit_export(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_audit_export(
        request,
        subject,
        permission_id=AUDIT_EXPORT,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_mcp_builder(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.mcp-builder.project",
            scope=mcp_builder_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The MCP Builder operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_mcp_builder_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_PROJECT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_PROJECT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_design_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DESIGN_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_design_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DESIGN_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_generation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_GENERATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_generation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_GENERATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_domain_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DOMAIN_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_domain_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DOMAIN_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_security_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_SECURITY_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_security_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_SECURITY_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_lab_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_LAB_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_lab_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_LAB_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_candidate_handoff_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_candidate_handoff_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_candidate_handoff_download(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_acquisition(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-acquisition",
            scope=connector_package_acquisition_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package acquisition operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_acquire(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_acquisition(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_ACQUIRE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_acquisition_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_acquisition(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_ACQUISITION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-validation",
            scope=connector_package_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package validation operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_supply_chain_inventory(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-supply-chain-inventory",
            scope=connector_package_supply_chain_inventory_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package supply-chain inventory operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_supply_chain_inventory_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_supply_chain_inventory(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_supply_chain_inventory_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_supply_chain_inventory(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SUPPLY_CHAIN_INVENTORY_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_content_policy_scan(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-content-policy-scan",
            scope=connector_package_content_policy_scan_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package content-policy scan operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_content_policy_scan_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_content_policy_scan(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_content_policy_scan_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_content_policy_scan(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_CONTENT_POLICY_SCAN_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_schema_semantics_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-schema-semantics-validation",
            scope=connector_package_schema_semantics_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package schema semantics operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_schema_semantics_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_schema_semantics_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_schema_semantics_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_schema_semantics_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SCHEMA_SEMANTICS_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_authority_behavior_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-authority-behavior-validation",
            scope=connector_package_authority_behavior_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package authority behavior operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_authority_behavior_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_authority_behavior_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_authority_behavior_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_authority_behavior_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_AUTHORITY_BEHAVIOR_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_static_dependency_analysis(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-static-dependency-analysis",
            scope=connector_package_static_dependency_analysis_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package static dependency operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_static_dependency_analysis_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_static_dependency_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_static_dependency_analysis_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_static_dependency_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_STATIC_DEPENDENCY_ANALYSIS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_vulnerability_analysis(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-vulnerability-analysis",
            scope=connector_package_vulnerability_analysis_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package vulnerability operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_vulnerability_analysis_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_vulnerability_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_vulnerability_analysis_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_vulnerability_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VULNERABILITY_ANALYSIS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_malware_analysis(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-malware-analysis",
            scope=connector_package_malware_analysis_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package malware operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_malware_analysis_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_malware_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_MALWARE_ANALYSIS_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_malware_analysis_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_malware_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_MALWARE_ANALYSIS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_license_analysis(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-license-analysis",
            scope=connector_package_license_analysis_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package license operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_license_analysis_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_license_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_LICENSE_ANALYSIS_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_license_analysis_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_license_analysis(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_LICENSE_ANALYSIS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_contract_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-contract-validation",
            scope=connector_package_contract_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package contract operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_contract_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_contract_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_CONTRACT_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_contract_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_contract_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_CONTRACT_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_runner_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-runner-validation",
            scope=connector_package_runner_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package runner operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_runner_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_runner_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_RUNNER_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_runner_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_runner_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_RUNNER_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_lab_self_test(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-lab-self-test",
            scope=connector_package_lab_self_test_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package lab self-test operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_lab_self_test_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_lab_self_test(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_LAB_SELF_TEST_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_lab_self_test_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_lab_self_test(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_LAB_SELF_TEST_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_final_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-final-validation",
            scope=connector_package_final_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package final-validation operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_final_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_final_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_FINAL_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_final_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_final_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_FINAL_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_approval(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-approval-request",
            scope=connector_package_approval_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package approval operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_approval_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_approval(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_APPROVAL_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_approval_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_approval(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_APPROVAL_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_package_approval_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_approval(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_APPROVAL_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_connector_publisher_attestation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.publisher-attestation",
            scope=connector_publisher_attestation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector publisher attestation operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_publisher_attestation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_publisher_attestation(
        request,
        subject,
        permission_id=CONNECTOR_PUBLISHER_ATTESTATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_publisher_attestation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_publisher_attestation(
        request,
        subject,
        permission_id=CONNECTOR_PUBLISHER_ATTESTATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_signing(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-signing-receipt",
            scope=connector_package_signing_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package signing operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_signing_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_signing(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SIGNING_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_signing_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_signing(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_SIGNING_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_registry_publication(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.registry-publication-receipt",
            scope=connector_registry_publication_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector registry publication operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_registry_publication_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_registry_publication(
        request,
        subject,
        permission_id=CONNECTOR_REGISTRY_PUBLICATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_registry_publication_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_registry_publication(
        request,
        subject,
        permission_id=CONNECTOR_REGISTRY_PUBLICATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_registration(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-registration-record",
            scope=connector_package_registration_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package registration operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_registration_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_registration(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_REGISTRATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_registration_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_registration(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_REGISTRATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_installation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-installation-receipt",
            scope=connector_package_installation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector package installation operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_installation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_installation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_INSTALLATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_package_installation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_installation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_INSTALLATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_instance(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.instance",
            scope=connector_instance_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector instance operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_instance_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_INSTANCE_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_instance_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_INSTANCE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_instance_retire(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_INSTANCE_RETIRE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_upgrade_approval_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_APPROVAL_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_upgrade_approval_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_APPROVAL_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_approval_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_APPROVAL_DECIDE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_upgrade_approval_revalidation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_upgrade_approval_revalidation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_APPROVAL_REVALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_handoff_readiness_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_HANDOFF_READINESS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_evidence_receipt_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_upgrade_evidence_receipt_verify(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_EVIDENCE_RECEIPT_VERIFY,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_upgrade_signed_evidence_receipt_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_upgrade_signed_evidence_receipt_verify(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNED_EVIDENCE_RECEIPT_VERIFY,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_upgrade_signing_key_trust_inventory_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_trust_read_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNING_KEY_TRUST_INVENTORY_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_signing_provider_conformance_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_conformance_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_upgrade_signing_provider_conformance_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_conformance_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_CONFORMANCE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_signing_provider_onboarding_readiness_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_trust_read_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_READINESS_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_signing_provider_onboarding_policy_provenance_diagnostic_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_trust_read_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=(
            CONNECTOR_UPGRADE_SIGNING_PROVIDER_ONBOARDING_POLICY_PROVENANCE_DIAGNOSTIC_READ
        ),
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_connector_upgrade_change_context_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_CHANGE_CONTEXT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_upgrade_change_context_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_instance(
        request,
        subject,
        permission_id=CONNECTOR_UPGRADE_CHANGE_CONTEXT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_target_configuration(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.target-configuration-binding",
            scope=connector_target_configuration_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector target configuration operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_target_configuration_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_target_configuration(
        request,
        subject,
        permission_id=CONNECTOR_TARGET_CONFIGURATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_target_configuration_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_target_configuration(
        request,
        subject,
        permission_id=CONNECTOR_TARGET_CONFIGURATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_credential_assignment(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.credential-assignment",
            scope=connector_credential_assignment_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The requested connector credential assignment is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_credential_assignment_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_credential_assignment(
        request,
        subject,
        permission_id=CONNECTOR_CREDENTIAL_ASSIGNMENT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_credential_assignment_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_credential_assignment(
        request,
        subject,
        permission_id=CONNECTOR_CREDENTIAL_ASSIGNMENT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_configuration_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.configuration-validation",
            scope=connector_configuration_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector configuration validation is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_configuration_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_configuration_validation(
        request,
        subject,
        permission_id=CONNECTOR_CONFIGURATION_VALIDATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_configuration_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_configuration_validation(
        request,
        subject,
        permission_id=CONNECTOR_CONFIGURATION_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_capability_enablement(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.capability-enablement",
            scope=connector_capability_enablement_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector capability enablement is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_capability_enablement_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_capability_enablement(
        request,
        subject,
        permission_id=CONNECTOR_CAPABILITY_ENABLEMENT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_capability_enablement_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_capability_enablement(
        request,
        subject,
        permission_id=CONNECTOR_CAPABILITY_ENABLEMENT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_runtime_trust(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.runtime-trust-grant",
            scope=connector_runtime_trust_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector runtime trust grant is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_runtime_trust_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_runtime_trust(
        request,
        subject,
        permission_id=CONNECTOR_RUNTIME_TRUST_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_runtime_trust_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_runtime_trust(
        request,
        subject,
        permission_id=CONNECTOR_RUNTIME_TRUST_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_secret_brokerage(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.secret-brokerage-authorization",
            scope=connector_secret_brokerage_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector secret brokerage authorization is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_secret_brokerage_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_secret_brokerage(
        request,
        subject,
        permission_id=CONNECTOR_SECRET_BROKERAGE_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_secret_brokerage_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_secret_brokerage(
        request,
        subject,
        permission_id=CONNECTOR_SECRET_BROKERAGE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_runtime_activation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.runtime-activation",
            scope=connector_runtime_activation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector runtime activation is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_runtime_activation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_runtime_activation(
        request,
        subject,
        permission_id=CONNECTOR_RUNTIME_ACTIVATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_runtime_activation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_runtime_activation(
        request,
        subject,
        permission_id=CONNECTOR_RUNTIME_ACTIVATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_target_session(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.target-session-verification",
            scope=connector_target_session_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector target session verification is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_target_session_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_target_session(
        request,
        subject,
        permission_id=CONNECTOR_TARGET_SESSION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_target_session_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_target_session(
        request,
        subject,
        permission_id=CONNECTOR_TARGET_SESSION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_invocation_authorization(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.invocation-authorization",
            scope=connector_invocation_authorization_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The connector invocation authorization is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_invocation_authorization_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_invocation_authorization(
        request,
        subject,
        permission_id=CONNECTOR_INVOCATION_AUTHORIZATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_invocation_authorization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_invocation_authorization(
        request,
        subject,
        permission_id=CONNECTOR_INVOCATION_AUTHORIZATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_bounded_invocation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.bounded-invocation",
            scope=connector_bounded_invocation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The bounded connector invocation is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_bounded_invocation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_bounded_invocation(
        request,
        subject,
        permission_id=CONNECTOR_BOUNDED_INVOCATION_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_bounded_invocation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_bounded_invocation(
        request,
        subject,
        permission_id=CONNECTOR_BOUNDED_INVOCATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_invocation_evidence(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.invocation-evidence",
            scope=connector_invocation_evidence_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Connector invocation evidence ingestion is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_invocation_evidence_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_invocation_evidence(
        request,
        subject,
        permission_id=CONNECTOR_INVOCATION_EVIDENCE_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_connector_invocation_evidence_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_invocation_evidence(
        request,
        subject,
        permission_id=CONNECTOR_INVOCATION_EVIDENCE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_operational_evidence_knowledge_draft(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-evidence-drafts",
            scope=operational_evidence_knowledge_draft_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational evidence knowledge draft access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_evidence_knowledge_draft_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_evidence_knowledge_draft(
        request,
        subject,
        permission_id=KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_operational_evidence_knowledge_draft_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_evidence_knowledge_draft(
        request,
        subject,
        permission_id=KNOWLEDGE_EVIDENCE_DRAFT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_operational_knowledge_review_request(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-review-requests",
            scope=operational_knowledge_review_request_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge review request access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_review_request_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_review_request(
        request,
        subject,
        permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_operational_knowledge_review_request_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_review_request(
        request,
        subject,
        permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_operational_knowledge_reviewer_assignment(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-reviewer-assignments",
            scope=operational_knowledge_reviewer_assignment_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge reviewer assignment access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_reviewer_assignment_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_reviewer_assignment(
        request,
        subject,
        permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_operational_knowledge_reviewer_assignment_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_reviewer_assignment(
        request,
        subject,
        permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_operational_knowledge_protected_inspection(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-protected-inspections",
            scope=operational_knowledge_protected_inspection_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge protected inspection access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_protected_inspection_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_inspection(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_operational_knowledge_protected_inspection_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_inspection(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_operational_knowledge_protected_content(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-protected-content",
            scope=operational_knowledge_protected_content_scope(
                subject.organization_id, settings.environment, CapabilityClass.C2_DIAGNOSTIC
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge protected content access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_protected_content_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_content(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
    )


async def authorize_operational_knowledge_protected_content_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_content(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
    )


async def _authorize_operational_knowledge_review_finding(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-review-findings",
            scope=operational_knowledge_review_finding_scope(
                subject.organization_id, settings.environment, CapabilityClass.C2_DIAGNOSTIC
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge review finding access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_review_finding_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_review_finding(
        request,
        subject,
        permission_id=KNOWLEDGE_REVIEW_FINDING_CREATE,
    )


async def authorize_operational_knowledge_review_finding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_review_finding(
        request,
        subject,
        permission_id=KNOWLEDGE_REVIEW_FINDING_READ,
    )


async def _authorize_operational_knowledge_finding_presentation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-finding-presentations",
            scope=operational_knowledge_finding_presentation_scope(
                subject.organization_id, settings.environment, CapabilityClass.C2_DIAGNOSTIC
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge finding presentation access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_finding_presentation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_finding_presentation(
        request,
        subject,
        permission_id=KNOWLEDGE_FINDING_PRESENTATION_CREATE,
    )


async def authorize_operational_knowledge_finding_presentation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_finding_presentation(
        request,
        subject,
        permission_id=KNOWLEDGE_FINDING_PRESENTATION_READ,
    )


async def _authorize_operational_knowledge_track_review_decision(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-track-review-decisions",
            scope=operational_knowledge_track_review_decision_scope(
                subject.organization_id, settings.environment, CapabilityClass.C2_DIAGNOSTIC
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge track review decision access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_track_review_decision_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_track_review_decision(
        request,
        subject,
        permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
    )


async def authorize_operational_knowledge_track_review_decision_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_track_review_decision(
        request,
        subject,
        permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
    )


async def _authorize_operational_knowledge_correction(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-corrections",
            scope=operational_knowledge_correction_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge correction access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_correction_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_correction(
        request,
        subject,
        permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
    )


async def authorize_operational_knowledge_correction_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_correction(
        request,
        subject,
        permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
    )


async def _authorize_operational_knowledge_final_resolution(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_FINAL_RESOLUTION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-final-resolutions",
            scope=operational_knowledge_final_resolution_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge final resolution access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_final_resolution_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_final_resolution(
        request,
        subject,
        permission_id=KNOWLEDGE_FINAL_RESOLUTION_CREATE,
    )


async def authorize_operational_knowledge_final_resolution_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_final_resolution(
        request,
        subject,
        permission_id=KNOWLEDGE_FINAL_RESOLUTION_READ,
    )


async def _authorize_operational_knowledge_publication_preparation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_PUBLICATION_PREPARATION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-publication-preparations",
            scope=operational_knowledge_publication_preparation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="Operational knowledge publication preparation access is not permitted.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_publication_preparation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_publication_preparation(
        request,
        subject,
        permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
    )


async def authorize_operational_knowledge_publication_preparation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_publication_preparation(
        request,
        subject,
        permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_READ,
    )


async def _authorize_operational_knowledge_source_materialization(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-source-materializations",
            scope=operational_knowledge_source_materialization_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The requested protected source materialization scope is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_source_materialization_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_source_materialization(
        request,
        subject,
        permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
    )


async def authorize_operational_knowledge_source_materialization_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_source_materialization(
        request,
        subject,
        permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
    )


async def _authorize_operational_knowledge_deterministic_chunking(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-deterministic-chunking",
            scope=operational_knowledge_deterministic_chunking_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The deterministic knowledge chunking operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_deterministic_chunking_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_deterministic_chunking(
        request,
        subject,
        permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
    )


async def authorize_operational_knowledge_deterministic_chunking_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_deterministic_chunking(
        request,
        subject,
        permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
    )


async def _authorize_operational_knowledge_embedding_generation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_EMBEDDING_GENERATION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-embedding-generation",
            scope=operational_knowledge_embedding_generation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The protected knowledge embedding operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_embedding_generation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_embedding_generation(
        request,
        subject,
        permission_id=KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
    )


async def authorize_operational_knowledge_embedding_generation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_embedding_generation(
        request,
        subject,
        permission_id=KNOWLEDGE_EMBEDDING_GENERATION_READ,
    )


async def _authorize_operational_knowledge_index_staging(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_INDEX_STAGING_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-index-staging",
            scope=operational_knowledge_index_staging_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The protected knowledge index-staging operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_operational_knowledge_index_staging_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_index_staging(
        request,
        subject,
        permission_id=KNOWLEDGE_INDEX_STAGING_CREATE,
    )


async def authorize_operational_knowledge_index_staging_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_index_staging(
        request,
        subject,
        permission_id=KNOWLEDGE_INDEX_STAGING_READ,
    )


async def _authorize_operational_knowledge_retrieval_publication(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    capability_class = (
        CapabilityClass.C2_DIAGNOSTIC
        if permission_id == KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE
        else CapabilityClass.C1_READ_ONLY
    )
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-retrieval-publication",
            scope=operational_knowledge_retrieval_publication_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot publish protected retrieval indexes.",
        )
    return decision


async def authorize_operational_knowledge_retrieval_publication_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_retrieval_publication(
        request,
        subject,
        permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
    )


async def authorize_operational_knowledge_retrieval_publication_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_retrieval_publication(
        request,
        subject,
        permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
    )


async def _authorize_operational_knowledge_protected_retrieval(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.knowledge.operational-protected-retrieval",
            scope=operational_knowledge_protected_retrieval_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot retrieve protected operational knowledge.",
        )
    return decision


async def authorize_operational_knowledge_protected_retrieval_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_retrieval(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
    )


async def authorize_operational_knowledge_protected_retrieval_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_operational_knowledge_protected_retrieval(
        request,
        subject,
        permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
    )


async def _authorize_protected_model_context(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-model-context",
            scope=ai_protected_model_context_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot assemble protected model context.",
        )
    return decision


async def authorize_protected_model_context_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_model_context(
        request,
        subject,
        permission_id=AI_PROTECTED_MODEL_CONTEXT_CREATE,
    )


async def authorize_protected_model_context_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_model_context(
        request,
        subject,
        permission_id=AI_PROTECTED_MODEL_CONTEXT_READ,
    )


async def _authorize_protected_model_invocation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-model-invocation",
            scope=ai_protected_model_invocation_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot invoke a protected model context.",
        )
    return decision


async def authorize_protected_model_invocation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_model_invocation(
        request,
        subject,
        permission_id=AI_PROTECTED_MODEL_INVOCATION_CREATE,
    )


async def authorize_protected_model_invocation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_model_invocation(
        request,
        subject,
        permission_id=AI_PROTECTED_MODEL_INVOCATION_READ,
    )


async def _authorize_protected_draft_adjudication(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-draft-adjudication",
            scope=ai_protected_draft_adjudication_scope(
                subject.organization_id, settings.environment, CapabilityClass.C1_READ_ONLY
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot adjudicate a protected model draft.",
        )
    return decision


async def authorize_protected_draft_adjudication_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_draft_adjudication(
        request, subject, permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_CREATE
    )


async def authorize_protected_draft_adjudication_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_draft_adjudication(
        request, subject, permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_READ
    )


async def _authorize_protected_answer_presentation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-answer-presentation",
            scope=ai_protected_answer_presentation_scope(
                subject.organization_id, settings.environment, CapabilityClass.C1_READ_ONLY
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot present a protected answer.",
        )
    return decision


async def authorize_protected_answer_presentation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_answer_presentation(
        request, subject, permission_id=AI_PROTECTED_ANSWER_PRESENTATION_CREATE
    )


async def authorize_protected_answer_presentation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_answer_presentation(
        request, subject, permission_id=AI_PROTECTED_ANSWER_PRESENTATION_READ
    )


async def _authorize_protected_recommendation_candidate(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-recommendation-candidate-set",
            scope=ai_protected_recommendation_candidate_scope(
                subject.organization_id, settings.environment, CapabilityClass.C1_READ_ONLY
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot generate protected recommendation candidates.",
        )
    return decision


async def authorize_protected_recommendation_candidate_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_candidate(
        request, subject, permission_id=AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE
    )


async def authorize_protected_recommendation_candidate_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_candidate(
        request, subject, permission_id=AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ
    )


async def _authorize_protected_candidate_impact(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-candidate-impact-analysis",
            scope=ai_protected_candidate_impact_scope(
                subject.organization_id, settings.environment, CapabilityClass.C1_READ_ONLY
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot enrich protected candidate impact.",
        )
    return decision


async def authorize_protected_candidate_impact_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_candidate_impact(
        request, subject, permission_id=AI_PROTECTED_CANDIDATE_IMPACT_CREATE
    )


async def authorize_protected_candidate_impact_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_candidate_impact(
        request, subject, permission_id=AI_PROTECTED_CANDIDATE_IMPACT_READ
    )


async def _authorize_protected_candidate_risk_recovery(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-candidate-risk-recovery-completion",
            scope=ai_protected_candidate_risk_recovery_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail=("The current identity cannot complete protected candidate risk and recovery."),
        )
    return decision


async def authorize_protected_candidate_risk_recovery_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_candidate_risk_recovery(
        request,
        subject,
        permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
    )


async def authorize_protected_candidate_risk_recovery_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_candidate_risk_recovery(
        request,
        subject,
        permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
    )


async def _authorize_protected_recommendation_adjudication(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-recommendation-adjudication",
            scope=ai_protected_recommendation_adjudication_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot adjudicate protected recommendation candidates.",
        )
    return decision


async def authorize_protected_recommendation_adjudication_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_adjudication(
        request,
        subject,
        permission_id=AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
    )


async def authorize_protected_recommendation_adjudication_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_adjudication(
        request,
        subject,
        permission_id=AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
    )


async def _authorize_protected_recommendation_presentation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.ai.protected-recommendation-presentation",
            scope=ai_protected_recommendation_presentation_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot present protected recommendations.",
        )
    return decision


async def authorize_protected_recommendation_presentation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_presentation(
        request,
        subject,
        permission_id=AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
    )


async def authorize_protected_recommendation_presentation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_protected_recommendation_presentation(
        request,
        subject,
        permission_id=AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
    )


async def _authorize_recommendation_promotion(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.promotion",
            scope=recommendation_promotion_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot promote protected recommendations.",
        )
    return decision


async def authorize_recommendation_promotion_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_promotion(
        request, subject, permission_id=RECOMMENDATION_PROMOTION_CREATE
    )


async def authorize_recommendation_promotion_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_promotion(
        request, subject, permission_id=RECOMMENDATION_PROMOTION_READ
    )


async def _authorize_recommendation_readiness(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.review-readiness",
            scope=recommendation_readiness_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail=("The current identity cannot assess recommendation review readiness."),
        )
    return decision


async def authorize_recommendation_readiness_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_readiness(
        request, subject, permission_id=RECOMMENDATION_READINESS_CREATE
    )


async def authorize_recommendation_readiness_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_readiness(
        request, subject, permission_id=RECOMMENDATION_READINESS_READ
    )


async def _authorize_recommendation_review_request(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.human-review-request",
            scope=recommendation_review_request_scope(
                subject.organization_id,
                settings.environment,
                CapabilityClass.C1_READ_ONLY,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail=("The current identity cannot request recommendation human review."),
        )
    return decision


async def authorize_recommendation_review_request_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_review_request(
        request, subject, permission_id=RECOMMENDATION_REVIEW_REQUEST_CREATE
    )


async def authorize_recommendation_review_request_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_review_request(
        request, subject, permission_id=RECOMMENDATION_REVIEW_REQUEST_READ
    )


async def _authorize_recommendation_reviewer_assignment(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.reviewer-assignment",
            scope=recommendation_reviewer_assignment_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot manage recommendation reviewer assignments.",
        )
    return decision


async def authorize_recommendation_reviewer_assignment_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_reviewer_assignment(
        request,
        subject,
        permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
    )


async def authorize_recommendation_reviewer_assignment_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_reviewer_assignment(
        request,
        subject,
        permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_protected_inspection(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.protected-inspection",
            scope=recommendation_protected_inspection_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot access recommendation inspection leases.",
        )
    return decision


async def authorize_recommendation_protected_inspection_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_protected_inspection(
        request,
        subject,
        permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_protected_inspection_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_protected_inspection(
        request,
        subject,
        permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_protected_content(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.protected-content",
            scope=recommendation_protected_content_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot access protected recommendation content.",
        )
    return decision


async def authorize_recommendation_protected_content_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_protected_content(
        request,
        subject,
        permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_protected_content_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_protected_content(
        request,
        subject,
        permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_human_review_finding(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.human-review-findings",
            scope=recommendation_human_review_finding_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot record recommendation review findings.",
        )
    return decision


async def authorize_recommendation_human_review_finding_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_human_review_finding(
        request,
        subject,
        permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_human_review_finding_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_human_review_finding(
        request,
        subject,
        permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_finding_presentation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.finding-presentations",
            scope=recommendation_finding_presentation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot present recommendation review findings.",
        )
    return decision


async def authorize_recommendation_finding_presentation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_finding_presentation(
        request,
        subject,
        permission_id=RECOMMENDATION_FINDING_PRESENTATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_finding_presentation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_finding_presentation(
        request,
        subject,
        permission_id=RECOMMENDATION_FINDING_PRESENTATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_track_review_decision(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.track-review-decisions",
            scope=recommendation_track_review_decision_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot record recommendation track decisions.",
        )
    return decision


async def authorize_recommendation_track_review_decision_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_track_review_decision(
        request,
        subject,
        permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_track_review_decision_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_track_review_decision(
        request,
        subject,
        permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_correction_resubmission(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.correction-resubmissions",
            scope=recommendation_correction_resubmission_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot correct recommendation versions.",
        )
    return decision


async def authorize_recommendation_correction_resubmission_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_correction_resubmission(
        request,
        subject,
        permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_correction_resubmission_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_correction_resubmission(
        request,
        subject,
        permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_recommendation_final_disposition(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.recommendation.final-dispositions",
            scope=recommendation_final_disposition_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Authorization denied",
            detail="The current identity cannot record final recommendation dispositions.",
        )
    return decision


async def authorize_recommendation_final_disposition_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_final_disposition(
        request,
        subject,
        permission_id=RECOMMENDATION_FINAL_DISPOSITION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_recommendation_final_disposition_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_recommendation_final_disposition(
        request,
        subject,
        permission_id=RECOMMENDATION_FINAL_DISPOSITION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )
