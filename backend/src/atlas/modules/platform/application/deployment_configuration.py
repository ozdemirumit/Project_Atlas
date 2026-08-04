from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.domain.deployment_configuration import (
    ConfigurationState,
    ConfigurationValidation,
    ConfigurationValueSource,
    DeploymentConfigurationOverlay,
    DeploymentConfigurationPreview,
    DeploymentConfigurationRequest,
    EffectiveConfigurationField,
    NamedBooleanValue,
    NamedStringValue,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

IMMUTABLE_REFERENCE = re.compile(r"^[a-z0-9][a-z0-9./:-]*@sha256:[a-f0-9]{64}$")


class DeploymentConfigurationScopeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _EffectiveConfiguration:
    api_bind: str
    public_url: str
    cors_origins: tuple[str, ...]
    component_references: tuple[NamedStringValue, ...]
    feature_flags: tuple[NamedBooleanValue, ...]
    integration_endpoints: tuple[NamedStringValue, ...]
    resource_names: tuple[str, ...]
    secret_references: tuple[NamedStringValue, ...]


class DeploymentConfigurationService:
    def __init__(
        self,
        *,
        release_id: str,
        environment_id: str,
        site_id: str,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._release_id = release_id
        self._environment_id = environment_id
        self._site_id = site_id
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def preview(
        self,
        *,
        actor: AuthenticatedSubject,
        request: DeploymentConfigurationRequest,
        correlation_id: str,
    ) -> DeploymentConfigurationPreview:
        if (
            request.organization_id != actor.organization_id
            or request.environment_id != self._environment_id
            or request.site_id != self._site_id
        ):
            await self._audit_denial(actor, request, correlation_id)
            raise DeploymentConfigurationScopeError("configuration scope does not match actor")

        defaults = self._defaults(request.profile)
        effective, sources = self._render(defaults, request.overlay)
        validations = self._validate(request, effective)
        state = (
            ConfigurationState.FAILED
            if any(item.state is ConfigurationState.FAILED for item in validations)
            else ConfigurationState.PASSED
        )
        digest = sha256(self._canonical_payload(request, effective)).hexdigest()
        preview = DeploymentConfigurationPreview(
            preview_id=f"configuration-preview.{uuid4().hex}",
            schema_version="atlas.deployment-configuration-preview.v1",
            release_id=request.release_id,
            profile=request.profile,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            site_id=request.site_id,
            state=state,
            configuration_digest=digest,
            fields=self._safe_fields(effective, sources),
            validations=validations,
            generated_at=self._clock(),
            correlation_id=correlation_id,
        )
        await self._audit_success(actor, preview)
        return preview

    def _defaults(self, profile: DeploymentProfile) -> _EffectiveConfiguration:
        developer = profile is DeploymentProfile.DEVELOPER
        return _EffectiveConfiguration(
            api_bind="127.0.0.1",
            public_url="http://localhost:5173" if developer else "https://atlas.lab.local",
            cors_origins=(
                ("http://localhost:5173",) if developer else ("https://atlas.lab.local",)
            ),
            component_references=(
                NamedStringValue(
                    "component.backend",
                    "registry.synthetic.atlas/backend@sha256:" + "1" * 64,
                ),
                NamedStringValue(
                    "component.frontend",
                    "registry.synthetic.atlas/frontend@sha256:" + "2" * 64,
                ),
            ),
            feature_flags=(NamedBooleanValue("feature.autonomous-execution", False),),
            integration_endpoints=(
                NamedStringValue("integration.model", "https://model.synthetic.atlas/v1"),
            ),
            resource_names=("atlas-api", "atlas-web"),
            secret_references=(
                NamedStringValue("secret.database", "secret.database.atlas"),
                NamedStringValue("secret.model-reader", "secret.model.local-reader"),
            ),
        )

    @staticmethod
    def _render(
        defaults: _EffectiveConfiguration, overlay: DeploymentConfigurationOverlay
    ) -> tuple[_EffectiveConfiguration, dict[str, ConfigurationValueSource]]:
        values: dict[str, object] = {}
        sources: dict[str, ConfigurationValueSource] = {}
        for field in (
            "api_bind",
            "public_url",
            "cors_origins",
            "component_references",
            "feature_flags",
            "integration_endpoints",
            "resource_names",
            "secret_references",
        ):
            override = getattr(overlay, field)
            values[field] = getattr(defaults, field) if override is None else override
            sources[field] = (
                ConfigurationValueSource.RELEASE_DEFAULT
                if override is None
                else ConfigurationValueSource.OVERLAY
            )
        return _EffectiveConfiguration(**values), sources  # type: ignore[arg-type]

    def _validate(
        self, request: DeploymentConfigurationRequest, effective: _EffectiveConfiguration
    ) -> tuple[ConfigurationValidation, ...]:
        release_valid = request.release_id == self._release_id
        bind_valid = self._private_bind(effective.api_bind)
        public_valid = self._url_valid(
            effective.public_url,
            allow_local_http=request.profile is DeploymentProfile.DEVELOPER,
        )
        origins_valid = (
            bool(effective.cors_origins)
            and len(effective.cors_origins) == len(set(effective.cors_origins))
            and all(
                self._url_valid(
                    item, allow_local_http=request.profile is DeploymentProfile.DEVELOPER
                )
                for item in effective.cors_origins
            )
        )
        components_valid = self._named_unique(effective.component_references) and all(
            IMMUTABLE_REFERENCE.fullmatch(item.value) for item in effective.component_references
        )
        integrations_valid = self._named_unique(effective.integration_endpoints) and all(
            self._url_valid(item.value, allow_local_http=False)
            for item in effective.integration_endpoints
        )
        resources_valid = (
            bool(effective.resource_names)
            and len(effective.resource_names) == len(set(effective.resource_names))
            and all(
                re.fullmatch(r"[a-z][a-z0-9-]{2,62}", item) for item in effective.resource_names
            )
        )
        secrets_valid = self._named_unique(effective.secret_references) and all(
            item.value.startswith("secret.")
            and re.fullmatch(r"[a-z][a-z0-9_.-]{2,127}", item.value)
            for item in effective.secret_references
        )
        flags_valid = self._boolean_unique(effective.feature_flags) and not any(
            item.name == "feature.autonomous-execution" and item.value
            for item in effective.feature_flags
        )
        return (
            self._check(
                "configuration.release.matches", release_valid, "Release identity matches."
            ),
            self._check("configuration.bind.private", bind_valid, "API bind is private."),
            self._check("configuration.public-url.safe", public_valid, "Public URL is safe."),
            self._check(
                "configuration.cors.safe", origins_valid, "CORS origins are unique and safe."
            ),
            self._check(
                "configuration.components.immutable",
                components_valid,
                "Component references are unique and immutable.",
            ),
            self._check(
                "configuration.integrations.safe",
                integrations_valid,
                "Integration endpoints are unique and use approved URL forms.",
            ),
            self._check(
                "configuration.resources.unique",
                resources_valid,
                "Resource names are unique and bounded.",
            ),
            self._check(
                "configuration.secrets.references-only",
                secrets_valid,
                "Secrets use opaque references only.",
            ),
            self._check(
                "configuration.features.safe",
                flags_valid,
                "Feature flags preserve the no-autonomous-execution boundary.",
            ),
        )

    @staticmethod
    def _canonical_payload(
        request: DeploymentConfigurationRequest, effective: _EffectiveConfiguration
    ) -> bytes:
        payload = {
            "schema_version": "atlas.deployment-configuration.v1",
            "release_id": request.release_id,
            "profile": request.profile.value,
            "organization_id": request.organization_id,
            "environment_id": request.environment_id,
            "site_id": request.site_id,
            "api_bind": effective.api_bind,
            "public_url": DeploymentConfigurationService._safe_url(effective.public_url),
            "cors_origins": sorted(
                DeploymentConfigurationService._safe_url(item) for item in effective.cors_origins
            ),
            "component_references": sorted(
                (item.name, item.value) for item in effective.component_references
            ),
            "feature_flags": sorted((item.name, item.value) for item in effective.feature_flags),
            "integration_endpoints": sorted(
                (item.name, DeploymentConfigurationService._safe_url(item.value))
                for item in effective.integration_endpoints
            ),
            "resource_names": sorted(effective.resource_names),
            "secret_references": sorted(
                (
                    item.name,
                    item.value
                    if item.value.startswith("secret.")
                    else "<invalid-secret-reference>",
                )
                for item in effective.secret_references
            ),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def _safe_fields(
        self,
        effective: _EffectiveConfiguration,
        sources: dict[str, ConfigurationValueSource],
    ) -> tuple[EffectiveConfigurationField, ...]:
        fields = [
            EffectiveConfigurationField("api.bind", effective.api_bind, sources["api_bind"]),
            EffectiveConfigurationField(
                "api.public_url", self._safe_url(effective.public_url), sources["public_url"]
            ),
            EffectiveConfigurationField(
                "api.cors_origins",
                f"{len(effective.cors_origins)} configured",
                sources["cors_origins"],
            ),
            EffectiveConfigurationField(
                "components",
                f"{len(effective.component_references)} immutable references",
                sources["component_references"],
            ),
            EffectiveConfigurationField(
                "feature_flags",
                f"{len(effective.feature_flags)} explicit flags",
                sources["feature_flags"],
            ),
            EffectiveConfigurationField(
                "integration_endpoints",
                f"{len(effective.integration_endpoints)} configured",
                sources["integration_endpoints"],
            ),
            EffectiveConfigurationField(
                "resource_names",
                f"{len(effective.resource_names)} resources",
                sources["resource_names"],
            ),
            EffectiveConfigurationField(
                "secret_references",
                f"{len(effective.secret_references)} opaque references",
                sources["secret_references"],
                sensitive=True,
            ),
        ]
        return tuple(fields)

    @staticmethod
    def _url_valid(value: str, *, allow_local_http: bool) -> bool:
        try:
            parsed = urlsplit(value)
            port = parsed.port
            if (
                not 1 <= len(value) <= 2048
                or any(ord(item) < 32 for item in value)
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or not parsed.hostname
                or (port is not None and not 1 <= port <= 65535)
            ):
                return False
            if parsed.scheme == "https":
                return True
            return (
                allow_local_http
                and parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1"}
            )
        except ValueError:
            return False

    @staticmethod
    def _private_bind(value: str) -> bool:
        try:
            address = ip_address(value)
        except ValueError:
            return False
        return (address.is_private or address.is_loopback) and not (
            address.is_unspecified or address.is_multicast
        )

    @classmethod
    def _safe_url(cls, value: str) -> str:
        if not cls._url_valid(value, allow_local_http=True):
            return "<invalid-url>"
        parsed = urlsplit(value)
        port = f":{parsed.port}" if parsed.port is not None else ""
        return f"{parsed.scheme}://{parsed.hostname}{port}{parsed.path}"

    @staticmethod
    def _named_unique(items: tuple[NamedStringValue, ...]) -> bool:
        names = [item.name for item in items]
        return bool(items) and len(names) == len(set(names))

    @staticmethod
    def _boolean_unique(items: tuple[NamedBooleanValue, ...]) -> bool:
        names = [item.name for item in items]
        return bool(items) and len(names) == len(set(names))

    @staticmethod
    def _check(code: str, passed: bool, success: str) -> ConfigurationValidation:
        return ConfigurationValidation(
            code=code,
            state=ConfigurationState.PASSED if passed else ConfigurationState.FAILED,
            summary=success if passed else "Configuration requirement is not satisfied.",
            evidence="validated" if passed else "rejected",
            remediation=None if passed else "Correct the bounded input and generate a new preview.",
        )

    async def _audit_success(
        self, actor: AuthenticatedSubject, preview: DeploymentConfigurationPreview
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.deployment-configuration.preview",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=preview.generated_at,
                correlation_id=preview.correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.deployment-configuration.preview",
                resource_type="resource.platform.deployment-configuration",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.deployment-configuration/C0"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=f"deployment_configuration_{preview.state.value}",
                target_metadata=(
                    ("release_id", preview.release_id),
                    ("profile", preview.profile.value),
                    ("configuration_digest", preview.configuration_digest),
                    ("validation_count", str(len(preview.validations))),
                ),
            )
        )

    async def _audit_denial(
        self,
        actor: AuthenticatedSubject,
        request: DeploymentConfigurationRequest,
        correlation_id: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.deployment-configuration.preview",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.deployment-configuration.preview",
                resource_type="resource.platform.deployment-configuration",
                scope_reference="scope.redacted",
                decision_id=None,
                outcome="denied",
                result_code="configuration_scope_mismatch",
                target_metadata=(("profile", request.profile.value),),
            )
        )
