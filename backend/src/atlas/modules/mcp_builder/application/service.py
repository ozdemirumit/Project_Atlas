from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.application.analyzer import (
    BuilderSourceError,
    OpenApiSourceAnalyzer,
)
from atlas.modules.mcp_builder.application.ports import (
    McpBuilderError,
    McpBuilderProjectRepository,
)
from atlas.modules.mcp_builder.domain.models import BuilderProjectState, McpBuilderProject

PROJECT_SCHEMA = "atlas.mcp-builder-project.v1"
CREATE_PERMISSION = "mcp-builder.project.create"
READ_PERMISSION = "mcp-builder.project.read"


class McpBuilderService:
    def __init__(
        self,
        *,
        repository: McpBuilderProjectRepository,
        audit_sink: AuditSink,
        environment_id: str,
        analyzer: OpenApiSourceAnalyzer | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._analyzer = analyzer or OpenApiSourceAnalyzer()
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> McpBuilderProjectRepository:
        return self._repository

    async def close(self) -> None:
        await self._repository.close()

    async def create_project(
        self,
        *,
        actor: AuthenticatedSubject,
        vendor: str,
        product: str,
        intended_product_versions: tuple[str, ...],
        target_environment: str,
        sdk_profile: str,
        source_id: str,
        source_authority: str,
        source_owner: str,
        documentation_version: str,
        publication_date: date,
        license_id: str,
        redistribution_allowed: bool,
        classification: DataClassification,
        source_document: str,
        confirmed_synthetic_or_lab_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderProject:
        self._require_enterprise_human(actor)
        if not confirmed_synthetic_or_lab_only:
            raise McpBuilderError("builder_lab_confirmation_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_idempotency_key_invalid")
        vendor = self._validated_text(vendor, "vendor", 200)
        product = self._validated_text(product, "product", 200)
        intended_product_versions = self._validated_versions(intended_product_versions)
        target_environment = self._validated_text(target_environment, "target_environment", 200)
        sdk_profile = self._validated_text(sdk_profile, "sdk_profile", 127)
        source_id = self._validated_text(source_id, "source_id", 127)
        source_authority = self._validated_text(source_authority, "source_authority", 200)
        source_owner = self._validated_text(source_owner, "source_owner", 200)
        documentation_version = self._validated_text(
            documentation_version, "documentation_version", 200
        )
        license_id = self._validated_text(license_id, "license_id", 200)
        metadata = {
            "vendor": vendor,
            "product": product,
            "intended_product_versions": intended_product_versions,
            "target_environment": target_environment,
            "sdk_profile": sdk_profile,
            "source_id": source_id,
            "source_authority": source_authority,
            "source_owner": source_owner,
            "documentation_version": documentation_version,
            "license_id": license_id,
        }
        try:
            analysis = self._analyzer.analyze(source_document)
        except BuilderSourceError as error:
            raise McpBuilderError(error.code) from error
        fingerprint = self._digest(
            {
                **metadata,
                "publication_date": publication_date.isoformat(),
                "redistribution_allowed": redistribution_allowed,
                "classification": classification.value,
                "source_digest": analysis.source_digest,
                "confirmed_synthetic_or_lab_only": confirmed_synthetic_or_lab_only,
            }
        )
        prior = await self._repository.get(
            owner_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_stored(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_idempotency_conflict")
            return replace(prior, reused=True)

        state = (
            BuilderProjectState.NEEDS_CLARIFICATION
            if any(finding.blocking for finding in analysis.findings)
            or any(candidate.generation_blocked for candidate in analysis.capability_candidates)
            or not analysis.capability_candidates
            else BuilderProjectState.ANALYZED
        )
        canonical_digest = self._digest(
            {
                **metadata,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "owner_id": actor.subject_id,
                "publication_date": publication_date.isoformat(),
                "redistribution_allowed": redistribution_allowed,
                "classification": classification.value,
                "source_digest": analysis.source_digest,
                "openapi_version": analysis.openapi_version,
                "servers": analysis.declared_servers,
                "auth": [item.scheme_id for item in analysis.authentication_schemes],
                "candidates": [
                    (
                        item.candidate_id,
                        item.proposed_capability_class.value,
                        item.clarification_codes,
                    )
                    for item in analysis.capability_candidates
                ],
                "findings": [(item.code, item.location) for item in analysis.findings],
            }
        )
        now = self._clock()
        project = McpBuilderProject(
            project_id=f"mcp-builder-project.{canonical_digest[:24]}",
            schema_version=PROJECT_SCHEMA,
            version=1,
            state=state,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            owner_id=actor.subject_id,
            vendor=vendor,
            product=product,
            intended_product_versions=intended_product_versions,
            target_environment=target_environment,
            sdk_profile=sdk_profile,
            source_id=source_id,
            source_authority=source_authority,
            source_owner=source_owner,
            documentation_version=documentation_version,
            publication_date=publication_date,
            license_id=license_id,
            redistribution_allowed=redistribution_allowed,
            classification=classification,
            openapi_version=analysis.openapi_version,
            api_title=analysis.api_title,
            api_version=analysis.api_version,
            source_digest=analysis.source_digest,
            source_size_bytes=analysis.source_size_bytes,
            canonical_source_json=analysis.canonical_source_json,
            declared_servers=analysis.declared_servers,
            authentication_schemes=analysis.authentication_schemes,
            capability_candidates=analysis.capability_candidates,
            findings=analysis.findings,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=now,
            analyzed_at=now,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CREATE_PERMISSION,
            result_code="mcp_builder_source_analyzed",
            project=project,
        )
        if not await self._repository.add(project):
            raced = await self._repository.get(
                owner_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_idempotency_conflict")
            self._verify_stored(raced)
            return replace(raced, reused=True)
        return project

    async def get_project(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderProject:
        self._require_enterprise_human(actor)
        project = await self._repository.get_by_id(owner_id=actor.subject_id, project_id=project_id)
        if (
            project is None
            or project.organization_id != actor.organization_id
            or project.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_project_not_found")
        self._verify_stored(project)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=READ_PERMISSION,
            result_code="mcp_builder_project_read",
            project=project,
        )
        return project

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise McpBuilderError("builder_enterprise_human_mfa_required")

    @staticmethod
    def _validated_text(value: str, field_name: str, maximum: int) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > maximum:
            raise McpBuilderError(f"builder_{field_name}_invalid")
        return normalized

    @staticmethod
    def _validated_versions(values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values)
        if not 1 <= len(normalized) <= 20 or any(not item or len(item) > 80 for item in normalized):
            raise McpBuilderError("builder_product_versions_invalid")
        return normalized

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _verify_stored(project: McpBuilderProject) -> None:
        try:
            canonical = json.loads(project.canonical_source_json)
        except json.JSONDecodeError as error:
            raise McpBuilderError("builder_stored_source_integrity_failed") from error
        normalized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if (
            normalized != project.canonical_source_json
            or sha256(normalized.encode("ascii")).hexdigest() != project.source_digest
        ):
            raise McpBuilderError("builder_stored_source_integrity_failed")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        project: McpBuilderProject,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.project",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.mcp-builder.project",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=project.idempotency_key,
                target_metadata=(
                    ("project_id", project.project_id),
                    ("canonical_digest", project.canonical_digest),
                    ("source_digest", project.source_digest),
                ),
            )
        )
