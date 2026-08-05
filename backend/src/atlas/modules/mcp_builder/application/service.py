from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.capabilities import CapabilityClass
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
    McpBuilderDesignCheckpointRepository,
    McpBuilderError,
    McpBuilderProjectRepository,
)
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
    McpBuilderDesignCheckpoint,
)
from atlas.modules.mcp_builder.domain.models import BuilderProjectState, McpBuilderProject

PROJECT_SCHEMA = "atlas.mcp-builder-project.v1"
CREATE_PERMISSION = "mcp-builder.project.create"
READ_PERMISSION = "mcp-builder.project.read"
DESIGN_CREATE_PERMISSION = "mcp-builder.design.create"
DESIGN_READ_PERMISSION = "mcp-builder.design.read"
DESIGN_SCHEMA = "atlas.mcp-builder-design-checkpoint.v1"


class McpBuilderService:
    def __init__(
        self,
        *,
        repository: McpBuilderProjectRepository,
        design_repository: McpBuilderDesignCheckpointRepository,
        audit_sink: AuditSink,
        environment_id: str,
        analyzer: OpenApiSourceAnalyzer | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._design_repository = design_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._analyzer = analyzer or OpenApiSourceAnalyzer()
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> McpBuilderProjectRepository:
        return self._repository

    async def close(self) -> None:
        await self._design_repository.close()
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

    async def create_design_checkpoint(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        connector_boundary: str,
        target_products: tuple[str, ...],
        network_destinations: tuple[str, ...],
        configuration_keys: tuple[str, ...],
        secret_reference_ids: tuple[str, ...],
        entity_mappings: tuple[BuilderEntityMapping, ...],
        capability_decisions: tuple[BuilderCapabilityDecision, ...],
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderDesignCheckpoint:
        self._require_enterprise_human(actor)
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_design_idempotency_key_invalid")
        project = await self._project_for_design(actor=actor, project_id=project_id)
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
        ):
            raise McpBuilderError("builder_design_project_stale")

        boundary = self._validated_text(connector_boundary, "design_boundary", 1000)
        products = self._validated_design_texts(
            target_products, field_name="target_products", maximum_items=20, maximum_length=200
        )
        if project.product.casefold() not in {item.casefold() for item in products}:
            raise McpBuilderError("builder_design_target_product_mismatch")
        destinations = self._validated_destinations(network_destinations, project)
        config_keys = self._validated_identifiers(
            configuration_keys, "configuration_keys", maximum_items=50
        )
        secret_refs = self._validated_identifiers(
            secret_reference_ids, "secret_references", maximum_items=50
        )
        mappings = self._validated_entity_mappings(entity_mappings)
        decisions = self._validated_capability_decisions(capability_decisions, project)

        payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "reviewer_id": actor.subject_id,
            "connector_boundary": boundary,
            "target_products": products,
            "network_destinations": destinations,
            "configuration_keys": config_keys,
            "secret_reference_ids": secret_refs,
            "entity_mappings": [
                (item.source_entity, item.atlas_entity) for item in mappings
            ],
            "capability_decisions": [
                (
                    item.candidate_id,
                    item.decision.value,
                    item.analyzed_class.value,
                    item.confirmed_class.value,
                    item.required_permission,
                    item.rationale,
                    item.generation_eligible,
                )
                for item in decisions
            ],
        }
        fingerprint = self._digest({**payload, "idempotency_key": idempotency_key})
        prior = await self._design_repository.get_by_create_key(
            reviewer_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_checkpoint(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_design_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._design_repository.get_by_project(project_id=project.project_id)
        if existing is not None:
            self._verify_checkpoint(existing)
            raise McpBuilderError("builder_design_checkpoint_exists")

        canonical_digest = self._digest(payload)
        checkpoint = McpBuilderDesignCheckpoint(
            checkpoint_id=f"mcp-builder-design.{canonical_digest[:24]}",
            schema_version=DESIGN_SCHEMA,
            version=1,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            reviewer_id=actor.subject_id,
            connector_boundary=boundary,
            target_products=products,
            network_destinations=destinations,
            configuration_keys=config_keys,
            secret_reference_ids=secret_refs,
            entity_mappings=mappings,
            capability_decisions=decisions,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
        )
        await self._audit_design(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=DESIGN_CREATE_PERMISSION,
            result_code="mcp_builder_design_confirmed",
            checkpoint=checkpoint,
        )
        if not await self._design_repository.add(checkpoint):
            raced = await self._design_repository.get_by_create_key(
                reviewer_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_design_idempotency_conflict")
            self._verify_checkpoint(raced)
            return replace(raced, reused=True)
        return checkpoint

    async def get_design_checkpoint(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderDesignCheckpoint:
        self._require_enterprise_human(actor)
        checkpoint = await self._design_repository.get_by_project(project_id=project_id)
        if (
            checkpoint is None
            or checkpoint.organization_id != actor.organization_id
            or checkpoint.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_design_checkpoint_not_found")
        project = await self._project_for_design(actor=actor, project_id=project_id)
        if (
            checkpoint.project_version != project.version
            or checkpoint.project_digest != project.canonical_digest
            or checkpoint.source_digest != project.source_digest
        ):
            raise McpBuilderError("builder_design_project_stale")
        self._verify_checkpoint(checkpoint)
        await self._audit_design(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=DESIGN_READ_PERMISSION,
            result_code="mcp_builder_design_read",
            checkpoint=checkpoint,
        )
        return checkpoint

    async def _project_for_design(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderProject:
        project = await self._repository.get_by_id_for_scope(project_id=project_id)
        if (
            project is None
            or project.organization_id != actor.organization_id
            or project.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_project_not_found")
        self._verify_stored(project)
        return project

    @staticmethod
    def _validated_design_texts(
        values: tuple[str, ...], *, field_name: str, maximum_items: int, maximum_length: int
    ) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values)
        if (
            not 1 <= len(normalized) <= maximum_items
            or len(normalized) != len(set(normalized))
            or any(not item or len(item) > maximum_length for item in normalized)
        ):
            raise McpBuilderError(f"builder_design_{field_name}_invalid")
        return normalized

    @staticmethod
    def _validated_identifiers(
        values: tuple[str, ...], field_name: str, *, maximum_items: int
    ) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values)
        if len(normalized) > maximum_items or len(normalized) != len(set(normalized)):
            raise McpBuilderError(f"builder_design_{field_name}_invalid")
        pattern = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
        if any(pattern.fullmatch(item) is None for item in normalized):
            raise McpBuilderError(f"builder_design_{field_name}_invalid")
        return normalized

    def _validated_destinations(
        self, values: tuple[str, ...], project: McpBuilderProject
    ) -> tuple[str, ...]:
        if len(values) > 20:
            raise McpBuilderError("builder_design_network_destinations_invalid")
        normalized = tuple(self._normalize_destination(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise McpBuilderError("builder_design_network_destinations_invalid")
        declared = {self._normalize_destination(value) for value in project.declared_servers}
        if not set(normalized).issubset(declared):
            raise McpBuilderError("builder_design_network_destination_unapproved")
        return normalized

    @staticmethod
    def _normalize_destination(value: str) -> str:
        stripped = value.strip()
        parsed = urlsplit(stripped)
        try:
            parsed_port = parsed.port
        except ValueError as error:
            raise McpBuilderError("builder_design_network_destinations_invalid") from error
        if (
            len(stripped) > 500
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise McpBuilderError("builder_design_network_destinations_invalid")
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        port = f":{parsed_port}" if parsed_port is not None else ""
        path = parsed.path.rstrip("/")
        return urlunsplit((parsed.scheme.lower(), f"{host}{port}", path, "", ""))

    @staticmethod
    def _validated_entity_mappings(
        mappings: tuple[BuilderEntityMapping, ...],
    ) -> tuple[BuilderEntityMapping, ...]:
        if not 1 <= len(mappings) <= 100:
            raise McpBuilderError("builder_design_entity_mappings_invalid")
        source_entities = [item.source_entity for item in mappings]
        if len(source_entities) != len(set(source_entities)):
            raise McpBuilderError("builder_design_entity_mappings_invalid")
        return mappings

    @staticmethod
    def _validated_capability_decisions(
        decisions: tuple[BuilderCapabilityDecision, ...], project: McpBuilderProject
    ) -> tuple[BuilderCapabilityDecision, ...]:
        candidates = {item.candidate_id: item for item in project.capability_candidates}
        if {item.candidate_id for item in decisions} != set(candidates):
            raise McpBuilderError("builder_design_candidate_set_mismatch")
        included = 0
        broad_permissions = {"*", "admin", "administrator", "all", "root", "superuser"}
        for decision in decisions:
            candidate = candidates[decision.candidate_id]
            if (
                decision.analyzed_class is not candidate.proposed_capability_class
                or decision.confirmed_class is not candidate.proposed_capability_class
            ):
                raise McpBuilderError("builder_design_risk_class_mismatch")
            permission_tokens = {
                token
                for token in re.split(r"[^a-z0-9*]+", decision.required_permission.lower())
                if token
            }
            if permission_tokens & broad_permissions:
                raise McpBuilderError("builder_design_broad_permission_rejected")
            if decision.decision is BuilderCapabilityDecisionKind.INCLUDE:
                if candidate.generation_blocked or candidate.proposed_capability_class not in {
                    CapabilityClass.C0_INFORMATIONAL,
                    CapabilityClass.C1_READ_ONLY,
                }:
                    raise McpBuilderError("builder_design_blocked_candidate_included")
                included += 1
        if included == 0:
            raise McpBuilderError("builder_design_eligible_candidate_required")
        return decisions

    @classmethod
    def _verify_checkpoint(cls, checkpoint: McpBuilderDesignCheckpoint) -> None:
        payload = {
            "project_id": checkpoint.project_id,
            "project_version": checkpoint.project_version,
            "project_digest": checkpoint.project_digest,
            "source_digest": checkpoint.source_digest,
            "organization_id": checkpoint.organization_id,
            "environment_id": checkpoint.environment_id,
            "reviewer_id": checkpoint.reviewer_id,
            "connector_boundary": checkpoint.connector_boundary,
            "target_products": checkpoint.target_products,
            "network_destinations": checkpoint.network_destinations,
            "configuration_keys": checkpoint.configuration_keys,
            "secret_reference_ids": checkpoint.secret_reference_ids,
            "entity_mappings": [
                (item.source_entity, item.atlas_entity) for item in checkpoint.entity_mappings
            ],
            "capability_decisions": [
                (
                    item.candidate_id,
                    item.decision.value,
                    item.analyzed_class.value,
                    item.confirmed_class.value,
                    item.required_permission,
                    item.rationale,
                    item.generation_eligible,
                )
                for item in checkpoint.capability_decisions
            ],
        }
        if (
            cls._digest(payload) != checkpoint.canonical_digest
            or cls._digest({**payload, "idempotency_key": checkpoint.idempotency_key})
            != checkpoint.request_fingerprint
        ):
            raise McpBuilderError("builder_design_integrity_failed")

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

    @classmethod
    def _verify_stored(cls, project: McpBuilderProject) -> None:
        try:
            canonical = json.loads(project.canonical_source_json)
        except json.JSONDecodeError as error:
            raise McpBuilderError("builder_stored_source_integrity_failed") from error
        normalized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        metadata = {
            "vendor": project.vendor,
            "product": project.product,
            "intended_product_versions": project.intended_product_versions,
            "target_environment": project.target_environment,
            "sdk_profile": project.sdk_profile,
            "source_id": project.source_id,
            "source_authority": project.source_authority,
            "source_owner": project.source_owner,
            "documentation_version": project.documentation_version,
            "license_id": project.license_id,
        }
        canonical_payload = {
            **metadata,
            "organization_id": project.organization_id,
            "environment_id": project.environment_id,
            "owner_id": project.owner_id,
            "publication_date": project.publication_date.isoformat(),
            "redistribution_allowed": project.redistribution_allowed,
            "classification": project.classification.value,
            "source_digest": project.source_digest,
            "openapi_version": project.openapi_version,
            "servers": project.declared_servers,
            "auth": [item.scheme_id for item in project.authentication_schemes],
            "candidates": [
                (
                    item.candidate_id,
                    item.proposed_capability_class.value,
                    item.clarification_codes,
                )
                for item in project.capability_candidates
            ],
            "findings": [(item.code, item.location) for item in project.findings],
        }
        fingerprint_payload = {
            **metadata,
            "publication_date": project.publication_date.isoformat(),
            "redistribution_allowed": project.redistribution_allowed,
            "classification": project.classification.value,
            "source_digest": project.source_digest,
            "confirmed_synthetic_or_lab_only": project.synthetic_or_lab_only,
        }
        if (
            normalized != project.canonical_source_json
            or sha256(normalized.encode("ascii")).hexdigest() != project.source_digest
            or cls._digest(canonical_payload) != project.canonical_digest
            or cls._digest(fingerprint_payload) != project.request_fingerprint
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

    async def _audit_design(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        checkpoint: McpBuilderDesignCheckpoint,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.design-checkpoint",
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
                resource_type="resource.mcp-builder.design-checkpoint",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=checkpoint.idempotency_key,
                target_metadata=(
                    ("checkpoint_id", checkpoint.checkpoint_id),
                    ("project_id", checkpoint.project_id),
                    ("canonical_digest", checkpoint.canonical_digest),
                    ("source_digest", checkpoint.source_digest),
                ),
            )
        )
