from __future__ import annotations

from atlas.modules.platform.domain.bootstrap_integration_validation import (
    CoreIntegrationRegistration,
    IntegrationActivationState,
    IntegrationCheckState,
    IntegrationValidationCheck,
    ModelEndpointRegistration,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class SyntheticBootstrapIntegrationCatalog:
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[
        str,
        str,
        ModelEndpointRegistration,
        tuple[CoreIntegrationRegistration, ...],
        tuple[IntegrationValidationCheck, ...],
    ]:
        if profile not in {DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB}:
            raise ValueError("synthetic integration validation requires a non-production profile")
        if environment_id != "environment.test":
            raise ValueError("synthetic integration validation requires the test environment")
        model = ModelEndpointRegistration(
            endpoint_id="endpoint.model-gateway.local",
            owner_id="owner.platform-ai",
            provider_type="provider-type.openai-compatible",
            service_reference_id="service-reference.model-gateway.local",
            credential_reference_id="secret.model.local-reader",
            model_id="model.atlas-local.synthetic",
            context_limit=32768,
            output_limit=4096,
            data_classification_ceiling="classification.internal",
            residency_boundary_id="residency.local-enterprise",
            timeout_seconds=30,
            max_retries=1,
            rate_limit_per_minute=60,
            concurrency_limit=4,
            telemetry_classification="telemetry.metadata-only",
            approved_task_class_ids=(
                "task-class.evidence-summary",
                "task-class.bounded-investigation",
            ),
        )
        integrations = (
            self._integration(
                "integration.model-gateway.local",
                "integration-type.model-gateway",
                "owner.platform-ai",
                "purpose.model-validation",
                "endpoint-reference.model-gateway.local",
                "trust-reference.model-gateway.synthetic",
                "secret.model.local-reader",
                "scope.model-gateway.synthetic",
                "operation.model-gateway.contract.read",
                "mapping-preview.model-gateway.contract",
                "data-flow.model-gateway.metadata-only",
                60,
            ),
            self._integration(
                "integration.enterprise-identity.metadata",
                "integration-type.enterprise-identity",
                "owner.identity-security",
                "purpose.identity-metadata-validation",
                "endpoint-reference.enterprise-identity.ldaps",
                "trust-reference.enterprise-identity.public",
                None,
                "scope.enterprise-identity.metadata-only",
                "operation.enterprise-identity.metadata.read",
                "mapping-preview.enterprise-identity.groups",
                "data-flow.enterprise-identity.metadata-only",
                30,
            ),
            self._integration(
                "integration.security-export.metadata",
                "integration-type.security-export",
                "owner.security-operations",
                "purpose.security-export-validation",
                "endpoint-reference.security-export.synthetic-tls",
                "trust-reference.security-export.public",
                None,
                "scope.security-export.metadata-only",
                "operation.security-export.mapping.read",
                "mapping-preview.security-export.rfc5424",
                "data-flow.security-export.synthetic-only",
                30,
            ),
            self._integration(
                "integration.storage-connector.readonly",
                "integration-type.storage-connector",
                "owner.infrastructure-operations",
                "purpose.storage-contract-validation",
                "endpoint-reference.hitachi-opscenter.synthetic",
                "trust-reference.hitachi-opscenter.synthetic",
                "secret-reference.hitachi-opscenter.reader",
                "scope.storage-connector.synthetic-readonly",
                "operation.storage-connector.inventory.read",
                "mapping-preview.storage-connector.inventory",
                "data-flow.storage-connector.synthetic-readonly",
                60,
            ),
        )
        model_check_ids = (
            "check.model.request-contract",
            "check.model.identity",
            "check.model.structured-output",
            "check.model.tool-proposal",
            "check.model.streaming",
            "check.model.limits",
            "check.model.data-boundary",
            "check.model.synthetic-inference",
        )
        checks = tuple(
            IntegrationValidationCheck(
                check_id=check_id,
                subject_id=model.endpoint_id,
                state=IntegrationCheckState.PASSED,
                result_code="bootstrap.integration-check.passed",
                mandatory=True,
            )
            for check_id in model_check_ids
        ) + tuple(
            IntegrationValidationCheck(
                check_id=f"check.integration.{item.integration_id.removeprefix('integration.')}",
                subject_id=item.integration_id,
                state=IntegrationCheckState.PASSED,
                result_code="bootstrap.integration-check.passed",
                mandatory=True,
            )
            for item in integrations
        )
        return (
            "target.atlas-synthetic-integrations.primary",
            "target-kind.synthetic-file-integrations",
            model,
            integrations,
            checks,
        )

    @staticmethod
    def _integration(
        integration_id: str,
        integration_type: str,
        owner_id: str,
        purpose_id: str,
        endpoint_reference_id: str,
        trust_reference_id: str,
        credential_reference_id: str | None,
        scope_id: str,
        validation_operation_id: str,
        mapping_preview_id: str,
        data_flow_id: str,
        rate_limit_per_minute: int,
    ) -> CoreIntegrationRegistration:
        return CoreIntegrationRegistration(
            integration_id=integration_id,
            integration_type=integration_type,
            owner_id=owner_id,
            purpose_id=purpose_id,
            classification="classification.internal",
            endpoint_reference_id=endpoint_reference_id,
            trust_reference_id=trust_reference_id,
            credential_reference_id=credential_reference_id,
            scope_id=scope_id,
            rate_limit_per_minute=rate_limit_per_minute,
            validation_operation_id=validation_operation_id,
            mapping_preview_id=mapping_preview_id,
            data_flow_id=data_flow_id,
            activation_state=IntegrationActivationState.INACTIVE,
        )
