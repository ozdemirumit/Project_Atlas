from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any
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
from atlas.modules.mcp_builder.application.candidate_archive import (
    DeterministicCandidateArchiveBuilder,
)
from atlas.modules.mcp_builder.application.generator import (
    LANGUAGE_PROFILE,
    BuilderGeneratedContent,
    BuilderGenerationError,
    PythonScaffoldGenerator,
)
from atlas.modules.mcp_builder.application.ports import (
    McpBuilderArtifactError,
    McpBuilderArtifactPublisher,
    McpBuilderCandidateArchivePublisher,
    McpBuilderCandidateHandoffRepository,
    McpBuilderDesignCheckpointRepository,
    McpBuilderDomainReviewRepository,
    McpBuilderError,
    McpBuilderGenerationRepository,
    McpBuilderLabRunner,
    McpBuilderLabValidationRepository,
    McpBuilderProjectRepository,
    McpBuilderSecurityReviewRepository,
    McpBuilderValidationRepository,
)
from atlas.modules.mcp_builder.application.validator import (
    VALIDATION_PROFILE,
    VALIDATOR_VERSION,
    PythonScaffoldStaticValidator,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import (
    CandidateCapabilityEvidence,
    CandidateHandoffState,
    CandidateSignatureState,
    McpBuilderCandidateHandoff,
)
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
    McpBuilderDesignCheckpoint,
)
from atlas.modules.mcp_builder.domain.domain_review import (
    BuilderDomainCapabilityDecision,
    BuilderDomainCapabilityDecisionKind,
    BuilderDomainReviewState,
    McpBuilderDomainReview,
)
from atlas.modules.mcp_builder.domain.generation import (
    BuilderGeneratedFile,
    BuilderGenerationState,
    McpBuilderGeneration,
)
from atlas.modules.mcp_builder.domain.lab_validation import (
    BuilderLabCheck,
    BuilderLabCheckCode,
    BuilderLabCheckSeverity,
    BuilderLabCheckState,
    BuilderLabRunnerResult,
    BuilderLabValidationState,
    McpBuilderLabValidation,
)
from atlas.modules.mcp_builder.domain.models import BuilderProjectState, McpBuilderProject
from atlas.modules.mcp_builder.domain.security_review import (
    BuilderSecurityControl,
    BuilderSecurityControlAssessment,
    BuilderSecurityControlDecisionKind,
    BuilderSecurityReviewState,
    McpBuilderSecurityReview,
)
from atlas.modules.mcp_builder.domain.validation import (
    BuilderValidationCheckState,
    BuilderValidationState,
    McpBuilderValidation,
)

PROJECT_SCHEMA = "atlas.mcp-builder-project.v1"
CREATE_PERMISSION = "mcp-builder.project.create"
READ_PERMISSION = "mcp-builder.project.read"
DESIGN_CREATE_PERMISSION = "mcp-builder.design.create"
DESIGN_READ_PERMISSION = "mcp-builder.design.read"
DESIGN_SCHEMA = "atlas.mcp-builder-design-checkpoint.v1"
GENERATION_CREATE_PERMISSION = "mcp-builder.generation.create"
GENERATION_READ_PERMISSION = "mcp-builder.generation.read"
GENERATION_SCHEMA = "atlas.mcp-builder-generation.v1"
VALIDATION_CREATE_PERMISSION = "mcp-builder.validation.create"
VALIDATION_READ_PERMISSION = "mcp-builder.validation.read"
VALIDATION_SCHEMA = "atlas.mcp-builder-validation.v1"
DOMAIN_REVIEW_CREATE_PERMISSION = "mcp-builder.domain-review.create"
DOMAIN_REVIEW_READ_PERMISSION = "mcp-builder.domain-review.read"
DOMAIN_REVIEW_SCHEMA = "atlas.mcp-builder-domain-review.v1"
DOMAIN_REVIEW_PROFILE = "atlas.domain-review.connector.v1"
DOMAIN_REVIEWER_CONTRACT_VERSION = "mcp-builder-domain-review.v1"
DOMAIN_REVIEW_LIMITATIONS = (
    "Human domain review does not prove vendor runtime behavior.",
    "Security review, lab validation, and candidate package approval remain required.",
)
SECURITY_REVIEW_CREATE_PERMISSION = "mcp-builder.security-review.create"
SECURITY_REVIEW_READ_PERMISSION = "mcp-builder.security-review.read"
SECURITY_REVIEW_SCHEMA = "atlas.mcp-builder-security-review.v1"
SECURITY_REVIEW_PROFILE = "atlas.security-review.connector.v1"
SECURITY_REVIEWER_CONTRACT_VERSION = "mcp-builder-security-review.v1"
SECURITY_REVIEW_LIMITATIONS = (
    "Security review covers the exact quarantined scaffold and declared evidence only.",
    "Dynamic scanning, lab validation, and candidate package approval remain required.",
)
LAB_VALIDATION_CREATE_PERMISSION = "mcp-builder.lab-validation.create"
LAB_VALIDATION_READ_PERMISSION = "mcp-builder.lab-validation.read"
LAB_VALIDATION_SCHEMA = "atlas.mcp-builder-lab-validation.v1"
LAB_VALIDATION_PROFILE = "atlas.lab-validation.python312.v1"
LAB_RUNNER_CONTRACT_VERSION = "mcp-builder-isolated-runner.v1"
LAB_VALIDATION_LIMITATIONS = (
    "This result covers only the exact deterministic quarantined scaffold in a local "
    "isolated synthetic runner.",
    "No vendor target, credential, dependency resolution, vulnerability scan, malware "
    "scan, package, signature, installation, registration, enablement, or runtime trust "
    "was exercised or granted.",
)
CANDIDATE_HANDOFF_CREATE_PERMISSION = "mcp-builder.candidate-handoff.create"
CANDIDATE_HANDOFF_READ_PERMISSION = "mcp-builder.candidate-handoff.read"
CANDIDATE_HANDOFF_DOWNLOAD_PERMISSION = "mcp-builder.candidate-handoff.download"
CANDIDATE_HANDOFF_SCHEMA = "atlas.mcp-builder-candidate-handoff.v1"
CANDIDATE_HANDOFF_PROFILE = "atlas.candidate-handoff.python312.v1"
CANDIDATE_ARCHIVE_CONTRACT_VERSION = "mcp-builder-candidate-zip.v1"
CANDIDATE_HANDOFF_LIMITATIONS = (
    "This unsigned archive contains the exact deterministic quarantined scaffold and "
    "bounded evidence only.",
    "ATLAS-020 acquisition, package validation, signing, registration, installation, "
    "enablement, and runtime approval remain required.",
)
CANDIDATE_UNSUPPORTED_BEHAVIOR = (
    "Manual changes are unsupported by the first candidate handoff profile.",
    "Vendor target compatibility and successful capability execution have not been proven.",
)


class McpBuilderService:
    def __init__(
        self,
        *,
        repository: McpBuilderProjectRepository,
        design_repository: McpBuilderDesignCheckpointRepository,
        generation_repository: McpBuilderGenerationRepository,
        validation_repository: McpBuilderValidationRepository,
        domain_review_repository: McpBuilderDomainReviewRepository,
        security_review_repository: McpBuilderSecurityReviewRepository,
        artifact_publisher: McpBuilderArtifactPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        lab_validation_repository: McpBuilderLabValidationRepository | None = None,
        lab_runner: McpBuilderLabRunner | None = None,
        candidate_handoff_repository: McpBuilderCandidateHandoffRepository | None = None,
        candidate_archive_publisher: McpBuilderCandidateArchivePublisher | None = None,
        candidate_archive_builder: DeterministicCandidateArchiveBuilder | None = None,
        analyzer: OpenApiSourceAnalyzer | None = None,
        generator: PythonScaffoldGenerator | None = None,
        validator: PythonScaffoldStaticValidator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._design_repository = design_repository
        self._generation_repository = generation_repository
        self._validation_repository = validation_repository
        self._domain_review_repository = domain_review_repository
        self._security_review_repository = security_review_repository
        if lab_validation_repository is None or lab_runner is None:
            from atlas.modules.mcp_builder.adapters.lab_runner_subprocess import (
                SubprocessMcpBuilderLabRunner,
            )
            from atlas.modules.mcp_builder.adapters.lab_validation_memory import (
                InMemoryMcpBuilderLabValidationRepository,
            )

            lab_validation_repository = (
                lab_validation_repository or InMemoryMcpBuilderLabValidationRepository()
            )
            lab_runner = lab_runner or SubprocessMcpBuilderLabRunner()
        self._lab_validation_repository = lab_validation_repository
        self._lab_runner = lab_runner
        if candidate_handoff_repository is None or candidate_archive_publisher is None:
            from atlas.modules.mcp_builder.adapters.candidate_archive_memory import (
                InMemoryMcpBuilderCandidateArchivePublisher,
            )
            from atlas.modules.mcp_builder.adapters.candidate_handoff_memory import (
                InMemoryMcpBuilderCandidateHandoffRepository,
            )

            candidate_handoff_repository = (
                candidate_handoff_repository or InMemoryMcpBuilderCandidateHandoffRepository()
            )
            candidate_archive_publisher = (
                candidate_archive_publisher or InMemoryMcpBuilderCandidateArchivePublisher()
            )
        self._candidate_handoff_repository = candidate_handoff_repository
        self._candidate_archive_publisher = candidate_archive_publisher
        self._candidate_archive_builder = (
            candidate_archive_builder or DeterministicCandidateArchiveBuilder()
        )
        self._artifact_publisher = artifact_publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._analyzer = analyzer or OpenApiSourceAnalyzer()
        self._generator = generator or PythonScaffoldGenerator()
        self._validator = validator or PythonScaffoldStaticValidator(self._generator)
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> McpBuilderProjectRepository:
        return self._repository

    async def close(self) -> None:
        await self._candidate_handoff_repository.close()
        await self._lab_validation_repository.close()
        await self._security_review_repository.close()
        await self._domain_review_repository.close()
        await self._validation_repository.close()
        await self._generation_repository.close()
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
            "entity_mappings": [(item.source_entity, item.atlas_entity) for item in mappings],
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

    async def create_generation(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        language_profile: str,
        acknowledged_quarantine: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderGeneration:
        self._require_enterprise_human(actor)
        if not acknowledged_quarantine:
            raise McpBuilderError("builder_generation_quarantine_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_generation_idempotency_key_invalid")
        if language_profile != LANGUAGE_PROFILE:
            raise McpBuilderError("builder_generation_language_profile_unsupported")
        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
            or checkpoint.checkpoint_id != checkpoint_id
            or checkpoint.canonical_digest != checkpoint_digest
        ):
            raise McpBuilderError("builder_generation_source_stale")
        try:
            draft = self._generator.generate(project=project, checkpoint=checkpoint)
        except BuilderGenerationError as error:
            raise McpBuilderError(error.code) from error
        files = draft.metadata
        included_ids = {
            item.candidate_id
            for item in checkpoint.capability_decisions
            if item.generation_eligible
        }
        observed_lineage = {
            candidate_id for item in files for candidate_id in item.source_candidate_ids
        }
        if not observed_lineage.issubset(included_ids) or observed_lineage != included_ids:
            raise McpBuilderError("builder_generation_lineage_incomplete")
        artifact_digest = self._digest(
            [
                (
                    item.relative_path,
                    item.media_type,
                    item.sha256,
                    item.size_bytes,
                    item.source_candidate_ids,
                )
                for item in files
            ]
        )
        payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "requested_by": actor.subject_id,
            "language_profile": draft.language_profile,
            "template_version": draft.template_version,
            "artifact_digest": artifact_digest,
            "files": [
                (
                    item.relative_path,
                    item.media_type,
                    item.sha256,
                    item.size_bytes,
                    item.source_candidate_ids,
                )
                for item in files
            ],
        }
        fingerprint = self._digest(
            {
                **payload,
                "acknowledged_quarantine": acknowledged_quarantine,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._generation_repository.get_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_generation(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_generation_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._generation_repository.get_by_project(project_id=project.project_id)
        if existing is not None:
            self._verify_generation(existing)
            raise McpBuilderError("builder_generation_exists")

        canonical_digest = self._digest(payload)
        generation = McpBuilderGeneration(
            generation_id=f"mcp-builder-generation.{canonical_digest[:24]}",
            schema_version=GENERATION_SCHEMA,
            version=1,
            state=BuilderGenerationState.QUARANTINED,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_digest=checkpoint.canonical_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            requested_by=actor.subject_id,
            language_profile=draft.language_profile,
            template_version=draft.template_version,
            artifact_digest=artifact_digest,
            artifact_size_bytes=sum(item.size_bytes for item in files),
            files=files,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
        )
        await self._audit_generation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=GENERATION_CREATE_PERMISSION,
            result_code="mcp_builder_generation_authorized",
            generation=generation,
        )
        try:
            await self._artifact_publisher.publish(
                generation_id=generation.generation_id,
                artifact_digest=generation.artifact_digest,
                files=draft.files,
            )
        except McpBuilderArtifactError as error:
            raise McpBuilderError(error.code) from error
        if not await self._generation_repository.add(generation):
            raced = await self._generation_repository.get_by_create_key(
                requested_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_generation_idempotency_conflict")
            self._verify_generation(raced)
            return replace(raced, reused=True)
        return generation

    async def get_generation(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderGeneration:
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        await self._audit_generation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=GENERATION_READ_PERMISSION,
            result_code="mcp_builder_generation_read",
            generation=generation,
        )
        return generation

    async def get_generated_file(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        relative_path: str,
        correlation_id: str,
    ) -> tuple[McpBuilderGeneration, BuilderGeneratedFile, str]:
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        metadata = next(
            (item for item in generation.files if item.relative_path == relative_path), None
        )
        if metadata is None:
            raise McpBuilderError("builder_generation_file_not_found")
        try:
            content = await self._artifact_publisher.read(
                generation_id=generation.generation_id,
                artifact_digest=generation.artifact_digest,
                inventory=generation.files,
                relative_path=relative_path,
            )
        except (McpBuilderArtifactError, ValueError) as error:
            code = getattr(error, "code", "builder_generation_file_not_found")
            raise McpBuilderError(code) from error
        await self._audit_generation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=GENERATION_READ_PERMISSION,
            result_code="mcp_builder_generation_file_read",
            generation=generation,
            relative_path=relative_path,
        )
        return generation, metadata, content

    async def create_validation(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        generation_id: str,
        generation_digest: str,
        artifact_digest: str,
        validation_profile: str,
        acknowledged_static_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_static_only:
            raise McpBuilderError("builder_validation_static_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_validation_idempotency_key_invalid")
        if validation_profile != VALIDATION_PROFILE:
            raise McpBuilderError("builder_validation_profile_unsupported")
        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
            or checkpoint.checkpoint_id != checkpoint_id
            or checkpoint.canonical_digest != checkpoint_digest
            or generation.generation_id != generation_id
            or generation.canonical_digest != generation_digest
            or generation.artifact_digest != artifact_digest
        ):
            raise McpBuilderError("builder_validation_source_stale")

        verified_contents: dict[str, str] = {}
        contents: dict[str, str] | None
        artifact_error_code: str | None = None
        for metadata in generation.files:
            try:
                verified_contents[metadata.relative_path] = await self._artifact_publisher.read(
                    generation_id=generation.generation_id,
                    artifact_digest=generation.artifact_digest,
                    inventory=generation.files,
                    relative_path=metadata.relative_path,
                )
            except (McpBuilderArtifactError, ValueError) as error:
                artifact_error_code = getattr(
                    error, "code", "builder_generation_artifact_integrity_failed"
                )
                contents = None
                break
        else:
            contents = verified_contents
        result = self._validator.validate(
            project=project,
            checkpoint=checkpoint,
            generation=generation,
            contents=contents,
            artifact_error_code=artifact_error_code,
        )
        checks_payload = [
            (
                item.code,
                item.state.value,
                item.severity.value,
                item.summary,
                item.evidence_paths,
                item.remediation,
            )
            for item in result.checks
        ]
        payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "generation_id": generation.generation_id,
            "generation_digest": generation.canonical_digest,
            "artifact_digest": generation.artifact_digest,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "validated_by": actor.subject_id,
            "language_profile": generation.language_profile,
            "template_version": generation.template_version,
            "validation_profile": validation_profile,
            "validator_version": VALIDATOR_VERSION,
            "state": result.state.value,
            "checks": checks_payload,
            "limitations": result.limitations,
        }
        fingerprint = self._digest(
            {
                **payload,
                "acknowledged_static_only": acknowledged_static_only,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._validation_repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_validation(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_validation_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._validation_repository.get_by_project(project_id=project.project_id)
        if existing is not None:
            self._verify_validation(existing)
            raise McpBuilderError("builder_validation_exists")

        canonical_digest = self._digest(payload)
        validation = McpBuilderValidation(
            validation_id=f"mcp-builder-validation.{canonical_digest[:24]}",
            schema_version=VALIDATION_SCHEMA,
            version=1,
            state=result.state,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_digest=checkpoint.canonical_digest,
            generation_id=generation.generation_id,
            generation_digest=generation.canonical_digest,
            artifact_digest=generation.artifact_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            validated_by=actor.subject_id,
            language_profile=generation.language_profile,
            template_version=generation.template_version,
            validation_profile=validation_profile,
            validator_version=VALIDATOR_VERSION,
            checks=result.checks,
            passed_count=sum(
                item.state is BuilderValidationCheckState.PASSED for item in result.checks
            ),
            failed_count=sum(
                item.state is BuilderValidationCheckState.FAILED for item in result.checks
            ),
            skipped_count=sum(
                item.state is BuilderValidationCheckState.SKIPPED for item in result.checks
            ),
            limitations=result.limitations,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            completed_at=self._clock(),
            static_validation_passed=result.state is BuilderValidationState.PASSED,
        )
        await self._audit_validation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=VALIDATION_CREATE_PERMISSION,
            result_code=f"mcp_builder_static_validation_{validation.state.value}",
            validation=validation,
        )
        if not await self._validation_repository.add(validation):
            raced = await self._validation_repository.get_by_create_key(
                validated_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_validation_idempotency_conflict")
            self._verify_validation(raced)
            return replace(raced, reused=True)
        return validation

    async def get_validation(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderValidation:
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        await self._audit_validation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=VALIDATION_READ_PERMISSION,
            result_code="mcp_builder_static_validation_read",
            validation=validation,
        )
        return validation

    async def create_domain_review(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        generation_id: str,
        generation_digest: str,
        artifact_digest: str,
        validation_id: str,
        validation_digest: str,
        validation_profile: str,
        validator_version: str,
        review_profile: str,
        acknowledged_human_domain_decision: bool,
        capability_decisions: tuple[BuilderDomainCapabilityDecision, ...],
        summary: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderDomainReview:
        self._require_enterprise_human(actor)
        if not acknowledged_human_domain_decision:
            raise McpBuilderError("builder_domain_review_human_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_domain_review_idempotency_key_invalid")
        if review_profile != DOMAIN_REVIEW_PROFILE:
            raise McpBuilderError("builder_domain_review_profile_unsupported")

        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        if validation.state is not BuilderValidationState.PASSED:
            raise McpBuilderError("builder_domain_review_static_validation_required")
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
            or checkpoint.checkpoint_id != checkpoint_id
            or checkpoint.canonical_digest != checkpoint_digest
            or generation.generation_id != generation_id
            or generation.canonical_digest != generation_digest
            or generation.artifact_digest != artifact_digest
            or validation.validation_id != validation_id
            or validation.canonical_digest != validation_digest
            or validation.validation_profile != validation_profile
            or validation.validator_version != validator_version
        ):
            raise McpBuilderError("builder_domain_review_source_stale")

        decisions = self._validated_domain_decisions(
            capability_decisions,
            project=project,
            checkpoint=checkpoint,
        )
        accepted_count = sum(
            item.decision is BuilderDomainCapabilityDecisionKind.ACCEPTED for item in decisions
        )
        needs_evidence_count = sum(
            item.decision is BuilderDomainCapabilityDecisionKind.NEEDS_EVIDENCE
            for item in decisions
        )
        rejected_count = sum(
            item.decision is BuilderDomainCapabilityDecisionKind.REJECTED for item in decisions
        )
        state = (
            BuilderDomainReviewState.REJECTED
            if rejected_count
            else (
                BuilderDomainReviewState.NEEDS_EVIDENCE
                if needs_evidence_count
                else BuilderDomainReviewState.ACCEPTED
            )
        )
        normalized_summary = self._validated_text(summary, "domain_review_summary", 1500)
        decision_payload = self._domain_decision_payload(decisions)
        payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "generation_id": generation.generation_id,
            "generation_digest": generation.canonical_digest,
            "artifact_digest": generation.artifact_digest,
            "validation_id": validation.validation_id,
            "validation_digest": validation.canonical_digest,
            "validation_profile": validation.validation_profile,
            "validator_version": validation.validator_version,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "reviewed_by": actor.subject_id,
            "review_profile": review_profile,
            "reviewer_contract_version": DOMAIN_REVIEWER_CONTRACT_VERSION,
            "state": state.value,
            "capability_decisions": decision_payload,
            "accepted_count": accepted_count,
            "needs_evidence_count": needs_evidence_count,
            "rejected_count": rejected_count,
            "summary": normalized_summary,
            "limitations": DOMAIN_REVIEW_LIMITATIONS,
        }
        fingerprint = self._digest(
            {
                **payload,
                "acknowledged_human_domain_decision": acknowledged_human_domain_decision,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._domain_review_repository.get_by_create_key(
            reviewed_by=actor.subject_id,
            idempotency_key=idempotency_key,
        )
        if prior is not None:
            self._verify_domain_review(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_domain_review_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._domain_review_repository.get_by_validation(
            validation_id=validation.validation_id
        )
        if existing is not None:
            self._verify_domain_review(existing)
            raise McpBuilderError("builder_domain_review_exists")

        canonical_digest = self._digest(payload)
        review = McpBuilderDomainReview(
            review_id=f"mcp-builder-domain-review.{canonical_digest[:24]}",
            schema_version=DOMAIN_REVIEW_SCHEMA,
            version=1,
            state=state,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_digest=checkpoint.canonical_digest,
            generation_id=generation.generation_id,
            generation_digest=generation.canonical_digest,
            artifact_digest=generation.artifact_digest,
            validation_id=validation.validation_id,
            validation_digest=validation.canonical_digest,
            validation_profile=validation.validation_profile,
            validator_version=validation.validator_version,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            reviewed_by=actor.subject_id,
            review_profile=review_profile,
            reviewer_contract_version=DOMAIN_REVIEWER_CONTRACT_VERSION,
            capability_decisions=decisions,
            accepted_count=accepted_count,
            needs_evidence_count=needs_evidence_count,
            rejected_count=rejected_count,
            summary=normalized_summary,
            limitations=DOMAIN_REVIEW_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            completed_at=self._clock(),
            domain_review_accepted=state is BuilderDomainReviewState.ACCEPTED,
        )
        await self._audit_domain_review(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=DOMAIN_REVIEW_CREATE_PERMISSION,
            result_code=f"mcp_builder_domain_review_{review.state.value}",
            review=review,
        )
        if not await self._domain_review_repository.add(review):
            raced = await self._domain_review_repository.get_by_create_key(
                reviewed_by=actor.subject_id,
                idempotency_key=idempotency_key,
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_domain_review_idempotency_conflict")
            self._verify_domain_review(raced)
            return replace(raced, reused=True)
        return review

    async def get_domain_review(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderDomainReview:
        review = await self._domain_review_for_actor(actor=actor, project_id=project_id)
        await self._audit_domain_review(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=DOMAIN_REVIEW_READ_PERMISSION,
            result_code="mcp_builder_domain_review_read",
            review=review,
        )
        return review

    async def create_security_review(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        generation_id: str,
        generation_digest: str,
        artifact_digest: str,
        validation_id: str,
        validation_digest: str,
        validation_profile: str,
        validator_version: str,
        domain_review_id: str,
        domain_review_digest: str,
        domain_review_profile: str,
        domain_reviewer_contract_version: str,
        review_profile: str,
        acknowledged_independent_security_decision: bool,
        control_assessments: tuple[BuilderSecurityControlAssessment, ...],
        summary: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderSecurityReview:
        self._require_enterprise_human(actor)
        if not acknowledged_independent_security_decision:
            raise McpBuilderError("builder_security_review_human_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_security_review_idempotency_key_invalid")
        if review_profile != SECURITY_REVIEW_PROFILE:
            raise McpBuilderError("builder_security_review_profile_unsupported")

        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        domain_review = await self._domain_review_for_actor(actor=actor, project_id=project_id)
        if domain_review.state is not BuilderDomainReviewState.ACCEPTED:
            raise McpBuilderError("builder_security_review_accepted_domain_review_required")
        if actor.subject_id == domain_review.reviewed_by:
            raise McpBuilderError("builder_security_review_separation_of_duties_required")
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
            or checkpoint.checkpoint_id != checkpoint_id
            or checkpoint.canonical_digest != checkpoint_digest
            or generation.generation_id != generation_id
            or generation.canonical_digest != generation_digest
            or generation.artifact_digest != artifact_digest
            or validation.validation_id != validation_id
            or validation.canonical_digest != validation_digest
            or validation.validation_profile != validation_profile
            or validation.validator_version != validator_version
            or domain_review.review_id != domain_review_id
            or domain_review.canonical_digest != domain_review_digest
            or domain_review.review_profile != domain_review_profile
            or domain_review.reviewer_contract_version != domain_reviewer_contract_version
        ):
            raise McpBuilderError("builder_security_review_source_stale")

        assessments = self._validated_security_assessments(
            control_assessments,
            project=project,
            generation=generation,
            validation=validation,
            domain_review=domain_review,
        )
        accepted_count = sum(
            item.decision is BuilderSecurityControlDecisionKind.ACCEPTED for item in assessments
        )
        needs_remediation_count = sum(
            item.decision is BuilderSecurityControlDecisionKind.NEEDS_REMEDIATION
            for item in assessments
        )
        rejected_count = sum(
            item.decision is BuilderSecurityControlDecisionKind.REJECTED for item in assessments
        )
        state = (
            BuilderSecurityReviewState.REJECTED
            if rejected_count
            else (
                BuilderSecurityReviewState.NEEDS_REMEDIATION
                if needs_remediation_count
                else BuilderSecurityReviewState.ACCEPTED
            )
        )
        normalized_summary = self._validated_text(summary, "security_review_summary", 1800)
        assessment_payload = self._security_assessment_payload(assessments)
        payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "generation_id": generation.generation_id,
            "generation_digest": generation.canonical_digest,
            "artifact_digest": generation.artifact_digest,
            "validation_id": validation.validation_id,
            "validation_digest": validation.canonical_digest,
            "validation_profile": validation.validation_profile,
            "validator_version": validation.validator_version,
            "domain_review_id": domain_review.review_id,
            "domain_review_digest": domain_review.canonical_digest,
            "domain_review_profile": domain_review.review_profile,
            "domain_reviewer_contract_version": domain_review.reviewer_contract_version,
            "domain_reviewed_by": domain_review.reviewed_by,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "reviewed_by": actor.subject_id,
            "review_profile": review_profile,
            "reviewer_contract_version": SECURITY_REVIEWER_CONTRACT_VERSION,
            "state": state.value,
            "control_assessments": assessment_payload,
            "accepted_count": accepted_count,
            "needs_remediation_count": needs_remediation_count,
            "rejected_count": rejected_count,
            "summary": normalized_summary,
            "limitations": SECURITY_REVIEW_LIMITATIONS,
        }
        fingerprint = self._digest(
            {
                **payload,
                "acknowledged_independent_security_decision": (
                    acknowledged_independent_security_decision
                ),
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._security_review_repository.get_by_create_key(
            reviewed_by=actor.subject_id,
            idempotency_key=idempotency_key,
        )
        if prior is not None:
            self._verify_security_review(prior)
            if prior.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_security_review_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._security_review_repository.get_by_domain_review(
            domain_review_id=domain_review.review_id
        )
        if existing is not None:
            self._verify_security_review(existing)
            raise McpBuilderError("builder_security_review_exists")

        canonical_digest = self._digest(payload)
        review = McpBuilderSecurityReview(
            review_id=f"mcp-builder-security-review.{canonical_digest[:24]}",
            schema_version=SECURITY_REVIEW_SCHEMA,
            version=1,
            state=state,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_digest=checkpoint.canonical_digest,
            generation_id=generation.generation_id,
            generation_digest=generation.canonical_digest,
            artifact_digest=generation.artifact_digest,
            validation_id=validation.validation_id,
            validation_digest=validation.canonical_digest,
            validation_profile=validation.validation_profile,
            validator_version=validation.validator_version,
            domain_review_id=domain_review.review_id,
            domain_review_digest=domain_review.canonical_digest,
            domain_review_profile=domain_review.review_profile,
            domain_reviewer_contract_version=domain_review.reviewer_contract_version,
            domain_reviewed_by=domain_review.reviewed_by,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            reviewed_by=actor.subject_id,
            review_profile=review_profile,
            reviewer_contract_version=SECURITY_REVIEWER_CONTRACT_VERSION,
            control_assessments=assessments,
            accepted_count=accepted_count,
            needs_remediation_count=needs_remediation_count,
            rejected_count=rejected_count,
            summary=normalized_summary,
            limitations=SECURITY_REVIEW_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            completed_at=self._clock(),
            security_review_accepted=state is BuilderSecurityReviewState.ACCEPTED,
        )
        await self._audit_security_review(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=SECURITY_REVIEW_CREATE_PERMISSION,
            result_code=f"mcp_builder_security_review_{review.state.value}",
            review=review,
        )
        if not await self._security_review_repository.add(review):
            raced = await self._security_review_repository.get_by_create_key(
                reviewed_by=actor.subject_id,
                idempotency_key=idempotency_key,
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise McpBuilderError("builder_security_review_idempotency_conflict")
            self._verify_security_review(raced)
            return replace(raced, reused=True)
        return review

    async def get_security_review(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderSecurityReview:
        review = await self._security_review_for_actor(actor=actor, project_id=project_id)
        await self._audit_security_review(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=SECURITY_REVIEW_READ_PERMISSION,
            result_code="mcp_builder_security_review_read",
            review=review,
        )
        return review

    async def create_lab_validation(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        generation_id: str,
        generation_digest: str,
        artifact_digest: str,
        validation_id: str,
        validation_digest: str,
        domain_review_id: str,
        domain_review_digest: str,
        security_review_id: str,
        security_review_digest: str,
        lab_profile: str,
        acknowledged_isolated_synthetic_execution: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderLabValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_isolated_synthetic_execution:
            raise McpBuilderError("builder_lab_validation_execution_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_lab_validation_idempotency_key_invalid")
        if lab_profile != LAB_VALIDATION_PROFILE:
            raise McpBuilderError("builder_lab_validation_profile_unsupported")

        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        domain_review = await self._domain_review_for_actor(actor=actor, project_id=project_id)
        security_review = await self._security_review_for_actor(actor=actor, project_id=project_id)
        if security_review.state is not BuilderSecurityReviewState.ACCEPTED:
            raise McpBuilderError("builder_lab_validation_accepted_security_review_required")
        if actor.subject_id in {domain_review.reviewed_by, security_review.reviewed_by}:
            raise McpBuilderError("builder_lab_validation_separation_of_duties_required")
        if (
            project.version != project_version
            or project.canonical_digest != project_digest
            or project.source_digest != source_digest
            or checkpoint.checkpoint_id != checkpoint_id
            or checkpoint.canonical_digest != checkpoint_digest
            or generation.generation_id != generation_id
            or generation.canonical_digest != generation_digest
            or generation.artifact_digest != artifact_digest
            or validation.validation_id != validation_id
            or validation.canonical_digest != validation_digest
            or domain_review.review_id != domain_review_id
            or domain_review.canonical_digest != domain_review_digest
            or security_review.review_id != security_review_id
            or security_review.canonical_digest != security_review_digest
        ):
            raise McpBuilderError("builder_lab_validation_source_stale")

        lineage_payload = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "generation_id": generation.generation_id,
            "generation_digest": generation.canonical_digest,
            "artifact_digest": generation.artifact_digest,
            "validation_id": validation.validation_id,
            "validation_digest": validation.canonical_digest,
            "domain_review_id": domain_review.review_id,
            "domain_review_digest": domain_review.canonical_digest,
            "domain_reviewed_by": domain_review.reviewed_by,
            "security_review_id": security_review.review_id,
            "security_review_digest": security_review.canonical_digest,
            "security_reviewed_by": security_review.reviewed_by,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "operated_by": actor.subject_id,
            "lab_profile": lab_profile,
            "runner_contract_version": LAB_RUNNER_CONTRACT_VERSION,
        }
        request_fingerprint = self._digest(
            {
                **lineage_payload,
                "acknowledged_isolated_synthetic_execution": True,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._lab_validation_repository.get_by_create_key(
            operated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_lab_validation(prior)
            if prior.request_fingerprint != request_fingerprint:
                raise McpBuilderError("builder_lab_validation_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._lab_validation_repository.get_by_security_review(
            security_review_id=security_review.review_id
        )
        if existing is not None:
            self._verify_lab_validation(existing)
            raise McpBuilderError("builder_lab_validation_exists")

        draft = self._generator.generate(project=project, checkpoint=checkpoint)
        runner_result: BuilderLabRunnerResult
        verified_files: list[BuilderGeneratedContent] = []
        artifact_failure: str | None = None
        if (
            draft.language_profile != generation.language_profile
            or draft.metadata != generation.files
        ):
            artifact_failure = (
                "The deterministic scaffold no longer matches its immutable inventory."
            )
        else:
            for expected in draft.files:
                try:
                    content = await self._artifact_publisher.read(
                        generation_id=generation.generation_id,
                        artifact_digest=generation.artifact_digest,
                        inventory=generation.files,
                        relative_path=expected.relative_path,
                    )
                except McpBuilderArtifactError:
                    artifact_failure = (
                        "The published scaffold failed artifact integrity verification."
                    )
                    break
                if content != expected.content:
                    artifact_failure = (
                        "The published scaffold differs from deterministic regeneration."
                    )
                    break
                verified_files.append(expected)
        if artifact_failure is not None or len(verified_files) != len(draft.files):
            runner_result = self._failed_lab_runner_result(
                artifact_failure or "The complete scaffold could not be verified."
            )
        else:
            runner_result = await self._lab_runner.run(
                files=tuple(verified_files), lab_profile=lab_profile
            )
        if not runner_result.workspace_removed:
            raise McpBuilderError("builder_lab_validation_workspace_cleanup_failed")

        passed_count = sum(
            item.state is BuilderLabCheckState.PASSED for item in runner_result.checks
        )
        failed_count = sum(
            item.state is BuilderLabCheckState.FAILED for item in runner_result.checks
        )
        skipped_count = sum(
            item.state is BuilderLabCheckState.SKIPPED for item in runner_result.checks
        )
        state = (
            BuilderLabValidationState.PASSED
            if passed_count == len(BuilderLabCheckCode)
            else BuilderLabValidationState.FAILED
        )
        checks_payload = self._lab_check_payload(runner_result.checks)
        payload = {
            **lineage_payload,
            "runtime_version": runner_result.runtime_version,
            "state": state.value,
            "checks": checks_payload,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "child_started": runner_result.child_started,
            "child_exit_code": runner_result.child_exit_code,
            "duration_ms": runner_result.duration_ms,
            "output_digest": runner_result.output_digest,
            "output_size_bytes": runner_result.output_size_bytes,
            "artifact_file_count": len(generation.files),
            "artifact_size_bytes": sum(item.size_bytes for item in generation.files),
            "workspace_removed": runner_result.workspace_removed,
            "limitations": LAB_VALIDATION_LIMITATIONS,
        }
        canonical_digest = self._digest(payload)
        lab_validation = McpBuilderLabValidation(
            lab_validation_id=f"mcp-builder-lab-validation.{canonical_digest[:24]}",
            schema_version=LAB_VALIDATION_SCHEMA,
            version=1,
            state=state,
            project_id=project.project_id,
            project_version=project.version,
            project_digest=project.canonical_digest,
            source_digest=project.source_digest,
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_digest=checkpoint.canonical_digest,
            generation_id=generation.generation_id,
            generation_digest=generation.canonical_digest,
            artifact_digest=generation.artifact_digest,
            validation_id=validation.validation_id,
            validation_digest=validation.canonical_digest,
            domain_review_id=domain_review.review_id,
            domain_review_digest=domain_review.canonical_digest,
            domain_reviewed_by=domain_review.reviewed_by,
            security_review_id=security_review.review_id,
            security_review_digest=security_review.canonical_digest,
            security_reviewed_by=security_review.reviewed_by,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            operated_by=actor.subject_id,
            lab_profile=lab_profile,
            runner_contract_version=LAB_RUNNER_CONTRACT_VERSION,
            runtime_version=runner_result.runtime_version,
            checks=runner_result.checks,
            passed_count=passed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            child_started=runner_result.child_started,
            child_exit_code=runner_result.child_exit_code,
            duration_ms=runner_result.duration_ms,
            output_digest=runner_result.output_digest,
            output_size_bytes=runner_result.output_size_bytes,
            artifact_file_count=len(generation.files),
            artifact_size_bytes=sum(item.size_bytes for item in generation.files),
            workspace_removed=runner_result.workspace_removed,
            limitations=LAB_VALIDATION_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
            completed_at=self._clock(),
            lab_validation_passed=state is BuilderLabValidationState.PASSED,
            runtime_self_test_performed=runner_result.child_started,
            subprocess_invoked=runner_result.child_started,
            dynamic_code_execution_performed=runner_result.child_started,
        )
        await self._audit_lab_validation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=LAB_VALIDATION_CREATE_PERMISSION,
            result_code=f"mcp_builder_lab_validation_{state.value}",
            validation=lab_validation,
        )
        if not await self._lab_validation_repository.add(lab_validation):
            raced = await self._lab_validation_repository.get_by_create_key(
                operated_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != request_fingerprint:
                raise McpBuilderError("builder_lab_validation_idempotency_conflict")
            self._verify_lab_validation(raced)
            return replace(raced, reused=True)
        return lab_validation

    async def get_lab_validation(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderLabValidation:
        validation = await self._lab_validation_for_actor(actor=actor, project_id=project_id)
        await self._audit_lab_validation(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=LAB_VALIDATION_READ_PERMISSION,
            result_code="mcp_builder_lab_validation_read",
            validation=validation,
        )
        return validation

    async def create_candidate_handoff(
        self,
        *,
        actor: AuthenticatedSubject,
        project_id: str,
        project_version: int,
        project_digest: str,
        source_digest: str,
        checkpoint_id: str,
        checkpoint_digest: str,
        generation_id: str,
        generation_digest: str,
        artifact_digest: str,
        validation_id: str,
        validation_digest: str,
        domain_review_id: str,
        domain_review_digest: str,
        security_review_id: str,
        security_review_digest: str,
        lab_validation_id: str,
        lab_validation_digest: str,
        handoff_profile: str,
        acknowledged_unsigned_quarantined_package: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> McpBuilderCandidateHandoff:
        self._require_enterprise_human(actor)
        if not acknowledged_unsigned_quarantined_package:
            raise McpBuilderError("builder_candidate_handoff_acknowledgement_required")
        if handoff_profile != CANDIDATE_HANDOFF_PROFILE:
            raise McpBuilderError("builder_candidate_handoff_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise McpBuilderError("builder_candidate_handoff_idempotency_key_invalid")
        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        domain_review = await self._domain_review_for_actor(actor=actor, project_id=project_id)
        security_review = await self._security_review_for_actor(actor=actor, project_id=project_id)
        lab = await self._lab_validation_for_actor(actor=actor, project_id=project_id)
        if lab.state is not BuilderLabValidationState.PASSED:
            raise McpBuilderError("builder_candidate_handoff_passed_lab_required")
        if actor.subject_id in {
            domain_review.reviewed_by,
            security_review.reviewed_by,
            lab.operated_by,
        }:
            raise McpBuilderError("builder_candidate_handoff_separation_of_duties_required")
        requested = (
            project_version,
            project_digest,
            source_digest,
            checkpoint_id,
            checkpoint_digest,
            generation_id,
            generation_digest,
            artifact_digest,
            validation_id,
            validation_digest,
            domain_review_id,
            domain_review_digest,
            security_review_id,
            security_review_digest,
            lab_validation_id,
            lab_validation_digest,
        )
        observed = (
            project.version,
            project.canonical_digest,
            project.source_digest,
            checkpoint.checkpoint_id,
            checkpoint.canonical_digest,
            generation.generation_id,
            generation.canonical_digest,
            generation.artifact_digest,
            validation.validation_id,
            validation.canonical_digest,
            domain_review.review_id,
            domain_review.canonical_digest,
            security_review.review_id,
            security_review.canonical_digest,
            lab.lab_validation_id,
            lab.canonical_digest,
        )
        if requested != observed:
            raise McpBuilderError("builder_candidate_handoff_source_stale")

        lineage: dict[str, Any] = {
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_digest": checkpoint.canonical_digest,
            "generation_id": generation.generation_id,
            "generation_digest": generation.canonical_digest,
            "artifact_digest": generation.artifact_digest,
            "validation_id": validation.validation_id,
            "validation_digest": validation.canonical_digest,
            "domain_review_id": domain_review.review_id,
            "domain_review_digest": domain_review.canonical_digest,
            "domain_reviewed_by": domain_review.reviewed_by,
            "security_review_id": security_review.review_id,
            "security_review_digest": security_review.canonical_digest,
            "security_reviewed_by": security_review.reviewed_by,
            "lab_validation_id": lab.lab_validation_id,
            "lab_validation_digest": lab.canonical_digest,
            "lab_operated_by": lab.operated_by,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "custodied_by": actor.subject_id,
            "handoff_profile": handoff_profile,
            "archive_contract_version": CANDIDATE_ARCHIVE_CONTRACT_VERSION,
        }
        request_fingerprint = self._digest(
            {
                **lineage,
                "acknowledged_unsigned_quarantined_package": True,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._candidate_handoff_repository.get_by_create_key(
            custodied_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_candidate_handoff(prior)
            if prior.request_fingerprint != request_fingerprint:
                raise McpBuilderError("builder_candidate_handoff_idempotency_conflict")
            return replace(prior, reused=True)
        existing = await self._candidate_handoff_repository.get_by_lab_validation(
            lab_validation_id=lab.lab_validation_id
        )
        if existing is not None:
            self._verify_candidate_handoff(existing)
            raise McpBuilderError("builder_candidate_handoff_exists")

        draft = self._generator.generate(project=project, checkpoint=checkpoint)
        if (
            draft.language_profile != generation.language_profile
            or draft.metadata != generation.files
        ):
            raise McpBuilderError("builder_candidate_handoff_artifact_stale")
        verified: list[BuilderGeneratedContent] = []
        for expected in draft.files:
            try:
                content = await self._artifact_publisher.read(
                    generation_id=generation.generation_id,
                    artifact_digest=generation.artifact_digest,
                    inventory=generation.files,
                    relative_path=expected.relative_path,
                )
            except McpBuilderArtifactError as error:
                raise McpBuilderError(
                    "builder_candidate_handoff_artifact_integrity_failed"
                ) from error
            if content != expected.content:
                raise McpBuilderError("builder_candidate_handoff_artifact_stale")
            verified.append(expected)
        capabilities = tuple(
            CandidateCapabilityEvidence(
                candidate_id=item.candidate_id,
                capability_class=item.confirmed_class.value,
                required_permission=item.vendor_permission,
                supported_product_versions=item.supported_product_versions,
                source_citations=item.evidence_citations,
            )
            for item in domain_review.capability_decisions
        )
        capability_payload = self._candidate_capability_payload(capabilities)
        envelope = {
            "schema_version": "atlas.mcp-builder-candidate-handoff-envelope.v1",
            **lineage,
            "state": CandidateHandoffState.CANDIDATE_QUARANTINED.value,
            "signature_state": CandidateSignatureState.UNSIGNED.value,
            "capabilities": capability_payload,
            "network_destinations": checkpoint.network_destinations,
            "limitations": CANDIDATE_HANDOFF_LIMITATIONS,
            "unsupported_behavior": CANDIDATE_UNSUPPORTED_BEHAVIOR,
            "generated_file_count": len(generation.files),
            "manual_change_count": 0,
            "package_signed": False,
            "connector_registered": False,
            "connector_installed": False,
            "connector_enabled": False,
            "runtime_trust_granted": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        archive = self._candidate_archive_builder.build(files=tuple(verified), envelope=envelope)
        filename_stem = re.sub(r"[^a-z0-9._-]", "-", project.project_id.lower())
        package_filename = f"{filename_stem}-{generation.artifact_digest[:12]}.zip"
        payload = {
            **lineage,
            "state": CandidateHandoffState.CANDIDATE_QUARANTINED.value,
            "package_filename": package_filename,
            "package_digest": archive.digest,
            "package_size_bytes": archive.size_bytes,
            "package_entry_count": archive.entry_count,
            "generated_file_count": len(generation.files),
            "generated_size_bytes": sum(item.size_bytes for item in generation.files),
            "envelope_digest": archive.envelope_digest,
            "signature_state": CandidateSignatureState.UNSIGNED.value,
            "capabilities": capability_payload,
            "network_destinations": checkpoint.network_destinations,
            "limitations": CANDIDATE_HANDOFF_LIMITATIONS,
            "unsupported_behavior": CANDIDATE_UNSUPPORTED_BEHAVIOR,
            "manual_change_count": 0,
        }
        canonical_digest = self._digest(payload)
        handoff = McpBuilderCandidateHandoff(
            handoff_id=f"mcp-builder-candidate-handoff.{canonical_digest[:24]}",
            schema_version=CANDIDATE_HANDOFF_SCHEMA,
            version=1,
            state=CandidateHandoffState.CANDIDATE_QUARANTINED,
            **lineage,
            package_filename=package_filename,
            package_digest=archive.digest,
            package_size_bytes=archive.size_bytes,
            package_entry_count=archive.entry_count,
            generated_file_count=len(generation.files),
            generated_size_bytes=sum(item.size_bytes for item in generation.files),
            envelope_digest=archive.envelope_digest,
            signature_state=CandidateSignatureState.UNSIGNED,
            capabilities=capabilities,
            network_destinations=checkpoint.network_destinations,
            limitations=CANDIDATE_HANDOFF_LIMITATIONS,
            unsupported_behavior=CANDIDATE_UNSUPPORTED_BEHAVIOR,
            manual_change_count=0,
            canonical_digest=canonical_digest,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
        )
        await self._audit_candidate_handoff(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CANDIDATE_HANDOFF_CREATE_PERMISSION,
            result_code="mcp_builder_candidate_handoff_created",
            handoff=handoff,
        )
        await self._candidate_archive_publisher.publish(
            package_digest=archive.digest, content=archive.content
        )
        if not await self._candidate_handoff_repository.add(handoff):
            raced = await self._candidate_handoff_repository.get_by_create_key(
                custodied_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != request_fingerprint:
                raise McpBuilderError("builder_candidate_handoff_idempotency_conflict")
            self._verify_candidate_handoff(raced)
            return replace(raced, reused=True)
        return handoff

    async def get_candidate_handoff(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> McpBuilderCandidateHandoff:
        handoff = await self._candidate_handoff_for_actor(actor=actor, project_id=project_id)
        await self._audit_candidate_handoff(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CANDIDATE_HANDOFF_READ_PERMISSION,
            result_code="mcp_builder_candidate_handoff_read",
            handoff=handoff,
        )
        return handoff

    async def download_candidate_archive(
        self, *, actor: AuthenticatedSubject, project_id: str, correlation_id: str
    ) -> tuple[McpBuilderCandidateHandoff, bytes]:
        handoff = await self._candidate_handoff_for_actor(actor=actor, project_id=project_id)
        content = await self._candidate_archive_publisher.read(
            package_digest=handoff.package_digest, size_bytes=handoff.package_size_bytes
        )
        await self._audit_candidate_handoff(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CANDIDATE_HANDOFF_DOWNLOAD_PERMISSION,
            result_code="mcp_builder_candidate_archive_downloaded",
            handoff=handoff,
        )
        return handoff, content

    async def _lab_validation_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderLabValidation:
        self._require_enterprise_human(actor)
        validation = await self._lab_validation_repository.get_by_project(project_id=project_id)
        if (
            validation is None
            or validation.organization_id != actor.organization_id
            or validation.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_lab_validation_not_found")
        security_review = await self._security_review_for_actor(actor=actor, project_id=project_id)
        if (
            validation.security_review_id != security_review.review_id
            or validation.security_review_digest != security_review.canonical_digest
            or validation.security_reviewed_by != security_review.reviewed_by
        ):
            raise McpBuilderError("builder_lab_validation_source_stale")
        self._verify_lab_validation(validation)
        return validation

    async def _candidate_handoff_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderCandidateHandoff:
        self._require_enterprise_human(actor)
        handoff = await self._candidate_handoff_repository.get_by_project(project_id=project_id)
        if (
            handoff is None
            or handoff.organization_id != actor.organization_id
            or handoff.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_candidate_handoff_not_found")
        lab = await self._lab_validation_for_actor(actor=actor, project_id=project_id)
        if (
            handoff.lab_validation_id != lab.lab_validation_id
            or handoff.lab_validation_digest != lab.canonical_digest
            or handoff.lab_operated_by != lab.operated_by
        ):
            raise McpBuilderError("builder_candidate_handoff_source_stale")
        self._verify_candidate_handoff(handoff)
        return handoff

    async def _security_review_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderSecurityReview:
        self._require_enterprise_human(actor)
        review = await self._security_review_repository.get_by_project(project_id=project_id)
        if (
            review is None
            or review.organization_id != actor.organization_id
            or review.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_security_review_not_found")
        domain_review = await self._domain_review_for_actor(actor=actor, project_id=project_id)
        if (
            review.domain_review_id != domain_review.review_id
            or review.domain_review_digest != domain_review.canonical_digest
            or review.domain_review_profile != domain_review.review_profile
            or review.domain_reviewer_contract_version != domain_review.reviewer_contract_version
            or review.domain_reviewed_by != domain_review.reviewed_by
        ):
            raise McpBuilderError("builder_security_review_source_stale")
        self._verify_security_review(review)
        return review

    async def _domain_review_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderDomainReview:
        self._require_enterprise_human(actor)
        review = await self._domain_review_repository.get_by_project(project_id=project_id)
        if (
            review is None
            or review.organization_id != actor.organization_id
            or review.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_domain_review_not_found")
        validation = await self._validation_for_actor(actor=actor, project_id=project_id)
        if (
            review.project_version != validation.project_version
            or review.project_digest != validation.project_digest
            or review.source_digest != validation.source_digest
            or review.checkpoint_id != validation.checkpoint_id
            or review.checkpoint_digest != validation.checkpoint_digest
            or review.generation_id != validation.generation_id
            or review.generation_digest != validation.generation_digest
            or review.artifact_digest != validation.artifact_digest
            or review.validation_id != validation.validation_id
            or review.validation_digest != validation.canonical_digest
            or review.validation_profile != validation.validation_profile
            or review.validator_version != validation.validator_version
        ):
            raise McpBuilderError("builder_domain_review_source_stale")
        self._verify_domain_review(review)
        return review

    async def _validation_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderValidation:
        self._require_enterprise_human(actor)
        validation = await self._validation_repository.get_by_project(project_id=project_id)
        if (
            validation is None
            or validation.organization_id != actor.organization_id
            or validation.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_validation_not_found")
        generation = await self._generation_for_actor(actor=actor, project_id=project_id)
        if (
            validation.project_version != generation.project_version
            or validation.project_digest != generation.project_digest
            or validation.source_digest != generation.source_digest
            or validation.checkpoint_id != generation.checkpoint_id
            or validation.checkpoint_digest != generation.checkpoint_digest
            or validation.generation_id != generation.generation_id
            or validation.generation_digest != generation.canonical_digest
            or validation.artifact_digest != generation.artifact_digest
        ):
            raise McpBuilderError("builder_validation_source_stale")
        self._verify_validation(validation)
        return validation

    async def _generation_for_actor(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> McpBuilderGeneration:
        self._require_enterprise_human(actor)
        generation = await self._generation_repository.get_by_project(project_id=project_id)
        if (
            generation is None
            or generation.organization_id != actor.organization_id
            or generation.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_generation_not_found")
        project, checkpoint = await self._generation_context(actor=actor, project_id=project_id)
        if (
            generation.project_version != project.version
            or generation.project_digest != project.canonical_digest
            or generation.source_digest != project.source_digest
            or generation.checkpoint_id != checkpoint.checkpoint_id
            or generation.checkpoint_digest != checkpoint.canonical_digest
        ):
            raise McpBuilderError("builder_generation_source_stale")
        self._verify_generation(generation)
        return generation

    async def _generation_context(
        self, *, actor: AuthenticatedSubject, project_id: str
    ) -> tuple[McpBuilderProject, McpBuilderDesignCheckpoint]:
        project = await self._project_for_design(actor=actor, project_id=project_id)
        checkpoint = await self._design_repository.get_by_project(project_id=project_id)
        if (
            checkpoint is None
            or checkpoint.organization_id != actor.organization_id
            or checkpoint.environment_id != self._environment_id
        ):
            raise McpBuilderError("builder_design_checkpoint_not_found")
        self._verify_checkpoint(checkpoint)
        if (
            checkpoint.project_version != project.version
            or checkpoint.project_digest != project.canonical_digest
            or checkpoint.source_digest != project.source_digest
        ):
            raise McpBuilderError("builder_design_project_stale")
        return project, checkpoint

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

    @staticmethod
    def _validated_domain_decisions(
        decisions: tuple[BuilderDomainCapabilityDecision, ...],
        *,
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
    ) -> tuple[BuilderDomainCapabilityDecision, ...]:
        eligible = {
            item.candidate_id: item
            for item in checkpoint.capability_decisions
            if item.generation_eligible
        }
        if {item.candidate_id for item in decisions} != set(eligible):
            raise McpBuilderError("builder_domain_review_candidate_set_mismatch")
        candidates = {item.candidate_id: item for item in project.capability_candidates}
        intended_versions = set(project.intended_product_versions)
        for decision in decisions:
            checkpoint_decision = eligible[decision.candidate_id]
            candidate = candidates.get(decision.candidate_id)
            if candidate is None:
                raise McpBuilderError("builder_domain_review_candidate_set_mismatch")
            if decision.confirmed_class is not checkpoint_decision.confirmed_class:
                raise McpBuilderError("builder_domain_review_risk_class_mismatch")
            if decision.vendor_permission != checkpoint_decision.required_permission:
                raise McpBuilderError("builder_domain_review_permission_mismatch")
            if not set(decision.supported_product_versions).issubset(intended_versions):
                raise McpBuilderError("builder_domain_review_product_version_mismatch")
            if decision.evidence_citations != (candidate.citation,):
                raise McpBuilderError("builder_domain_review_evidence_lineage_mismatch")
        return tuple(sorted(decisions, key=lambda item: item.candidate_id))

    @staticmethod
    def _domain_decision_payload(
        decisions: tuple[BuilderDomainCapabilityDecision, ...],
    ) -> list[tuple[object, ...]]:
        return [
            (
                item.candidate_id,
                item.confirmed_class.value,
                item.decision.value,
                item.supported_product_versions,
                item.vendor_permission,
                item.authentication_assessment,
                item.side_effect_assessment,
                item.error_behavior_assessment,
                item.health_guidance_assessment,
                item.evidence_citations,
                item.missing_case_codes,
                item.rationale,
            )
            for item in decisions
        ]

    @staticmethod
    def _validated_security_assessments(
        assessments: tuple[BuilderSecurityControlAssessment, ...],
        *,
        project: McpBuilderProject,
        generation: McpBuilderGeneration,
        validation: McpBuilderValidation,
        domain_review: McpBuilderDomainReview,
    ) -> tuple[BuilderSecurityControlAssessment, ...]:
        if {item.control for item in assessments} != set(BuilderSecurityControl):
            raise McpBuilderError("builder_security_review_control_set_mismatch")
        allowed_evidence = {item.citation for item in project.capability_candidates} | {
            item.relative_path for item in generation.files
        }
        allowed_evidence.update(
            path for check in validation.checks for path in check.evidence_paths
        )
        allowed_evidence.update(
            citation
            for decision in domain_review.capability_decisions
            for citation in decision.evidence_citations
        )
        for assessment in assessments:
            if not set(assessment.evidence_references).issubset(allowed_evidence):
                raise McpBuilderError("builder_security_review_evidence_lineage_mismatch")
        return tuple(sorted(assessments, key=lambda item: item.control.value))

    @staticmethod
    def _security_assessment_payload(
        assessments: tuple[BuilderSecurityControlAssessment, ...],
    ) -> list[tuple[object, ...]]:
        return [
            (
                item.control.value,
                item.decision.value,
                item.assessment,
                item.evidence_references,
                item.finding_codes,
                item.required_controls,
            )
            for item in assessments
        ]

    @staticmethod
    def _lab_check_payload(checks: tuple[BuilderLabCheck, ...]) -> list[tuple[object, ...]]:
        return [
            (
                item.code.value,
                item.state.value,
                item.severity.value,
                item.summary,
                item.evidence_paths,
                item.remediation,
            )
            for item in checks
        ]

    @staticmethod
    def _failed_lab_runner_result(summary: str) -> BuilderLabRunnerResult:
        checks = tuple(
            BuilderLabCheck(
                code=code,
                state=(
                    BuilderLabCheckState.FAILED
                    if code is BuilderLabCheckCode.ARTIFACT_INTEGRITY
                    else BuilderLabCheckState.SKIPPED
                ),
                severity=BuilderLabCheckSeverity.ERROR,
                summary=summary,
                evidence_paths=("artifact inventory",),
                remediation=(
                    "Restore the exact immutable scaffold and create a new governed project "
                    "version."
                ),
            )
            for code in BuilderLabCheckCode
        )
        return BuilderLabRunnerResult(
            checks=checks,
            runtime_version=(
                f"python.{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            ),
            child_started=False,
            child_exit_code=None,
            duration_ms=0,
            output_digest=sha256(b"").hexdigest(),
            output_size_bytes=0,
            workspace_removed=True,
        )

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

    @classmethod
    def _verify_generation(cls, generation: McpBuilderGeneration) -> None:
        file_payload = [
            (
                item.relative_path,
                item.media_type,
                item.sha256,
                item.size_bytes,
                item.source_candidate_ids,
            )
            for item in generation.files
        ]
        if cls._digest(file_payload) != generation.artifact_digest:
            raise McpBuilderError("builder_generation_integrity_failed")
        payload = {
            "project_id": generation.project_id,
            "project_version": generation.project_version,
            "project_digest": generation.project_digest,
            "source_digest": generation.source_digest,
            "checkpoint_id": generation.checkpoint_id,
            "checkpoint_digest": generation.checkpoint_digest,
            "organization_id": generation.organization_id,
            "environment_id": generation.environment_id,
            "requested_by": generation.requested_by,
            "language_profile": generation.language_profile,
            "template_version": generation.template_version,
            "artifact_digest": generation.artifact_digest,
            "files": file_payload,
        }
        fingerprint_payload = {
            **payload,
            "acknowledged_quarantine": True,
            "idempotency_key": generation.idempotency_key,
        }
        if (
            cls._digest(payload) != generation.canonical_digest
            or cls._digest(fingerprint_payload) != generation.request_fingerprint
        ):
            raise McpBuilderError("builder_generation_integrity_failed")

    @classmethod
    def _verify_validation(cls, validation: McpBuilderValidation) -> None:
        checks_payload = [
            (
                item.code,
                item.state.value,
                item.severity.value,
                item.summary,
                item.evidence_paths,
                item.remediation,
            )
            for item in validation.checks
        ]
        payload = {
            "project_id": validation.project_id,
            "project_version": validation.project_version,
            "project_digest": validation.project_digest,
            "source_digest": validation.source_digest,
            "checkpoint_id": validation.checkpoint_id,
            "checkpoint_digest": validation.checkpoint_digest,
            "generation_id": validation.generation_id,
            "generation_digest": validation.generation_digest,
            "artifact_digest": validation.artifact_digest,
            "organization_id": validation.organization_id,
            "environment_id": validation.environment_id,
            "validated_by": validation.validated_by,
            "language_profile": validation.language_profile,
            "template_version": validation.template_version,
            "validation_profile": validation.validation_profile,
            "validator_version": validation.validator_version,
            "state": validation.state.value,
            "checks": checks_payload,
            "limitations": validation.limitations,
        }
        fingerprint_payload = {
            **payload,
            "acknowledged_static_only": True,
            "idempotency_key": validation.idempotency_key,
        }
        if (
            cls._digest(payload) != validation.canonical_digest
            or cls._digest(fingerprint_payload) != validation.request_fingerprint
        ):
            raise McpBuilderError("builder_validation_integrity_failed")

    @classmethod
    def _verify_domain_review(cls, review: McpBuilderDomainReview) -> None:
        payload = {
            "project_id": review.project_id,
            "project_version": review.project_version,
            "project_digest": review.project_digest,
            "source_digest": review.source_digest,
            "checkpoint_id": review.checkpoint_id,
            "checkpoint_digest": review.checkpoint_digest,
            "generation_id": review.generation_id,
            "generation_digest": review.generation_digest,
            "artifact_digest": review.artifact_digest,
            "validation_id": review.validation_id,
            "validation_digest": review.validation_digest,
            "validation_profile": review.validation_profile,
            "validator_version": review.validator_version,
            "organization_id": review.organization_id,
            "environment_id": review.environment_id,
            "reviewed_by": review.reviewed_by,
            "review_profile": review.review_profile,
            "reviewer_contract_version": review.reviewer_contract_version,
            "state": review.state.value,
            "capability_decisions": cls._domain_decision_payload(review.capability_decisions),
            "accepted_count": review.accepted_count,
            "needs_evidence_count": review.needs_evidence_count,
            "rejected_count": review.rejected_count,
            "summary": review.summary,
            "limitations": review.limitations,
        }
        fingerprint_payload = {
            **payload,
            "acknowledged_human_domain_decision": True,
            "idempotency_key": review.idempotency_key,
        }
        if (
            cls._digest(payload) != review.canonical_digest
            or cls._digest(fingerprint_payload) != review.request_fingerprint
        ):
            raise McpBuilderError("builder_domain_review_integrity_failed")

    @classmethod
    def _verify_security_review(cls, review: McpBuilderSecurityReview) -> None:
        payload = {
            "project_id": review.project_id,
            "project_version": review.project_version,
            "project_digest": review.project_digest,
            "source_digest": review.source_digest,
            "checkpoint_id": review.checkpoint_id,
            "checkpoint_digest": review.checkpoint_digest,
            "generation_id": review.generation_id,
            "generation_digest": review.generation_digest,
            "artifact_digest": review.artifact_digest,
            "validation_id": review.validation_id,
            "validation_digest": review.validation_digest,
            "validation_profile": review.validation_profile,
            "validator_version": review.validator_version,
            "domain_review_id": review.domain_review_id,
            "domain_review_digest": review.domain_review_digest,
            "domain_review_profile": review.domain_review_profile,
            "domain_reviewer_contract_version": review.domain_reviewer_contract_version,
            "domain_reviewed_by": review.domain_reviewed_by,
            "organization_id": review.organization_id,
            "environment_id": review.environment_id,
            "reviewed_by": review.reviewed_by,
            "review_profile": review.review_profile,
            "reviewer_contract_version": review.reviewer_contract_version,
            "state": review.state.value,
            "control_assessments": cls._security_assessment_payload(review.control_assessments),
            "accepted_count": review.accepted_count,
            "needs_remediation_count": review.needs_remediation_count,
            "rejected_count": review.rejected_count,
            "summary": review.summary,
            "limitations": review.limitations,
        }
        fingerprint_payload = {
            **payload,
            "acknowledged_independent_security_decision": True,
            "idempotency_key": review.idempotency_key,
        }
        if (
            cls._digest(payload) != review.canonical_digest
            or cls._digest(fingerprint_payload) != review.request_fingerprint
        ):
            raise McpBuilderError("builder_security_review_integrity_failed")

    @classmethod
    def _verify_lab_validation(cls, validation: McpBuilderLabValidation) -> None:
        payload = {
            "project_id": validation.project_id,
            "project_version": validation.project_version,
            "project_digest": validation.project_digest,
            "source_digest": validation.source_digest,
            "checkpoint_id": validation.checkpoint_id,
            "checkpoint_digest": validation.checkpoint_digest,
            "generation_id": validation.generation_id,
            "generation_digest": validation.generation_digest,
            "artifact_digest": validation.artifact_digest,
            "validation_id": validation.validation_id,
            "validation_digest": validation.validation_digest,
            "domain_review_id": validation.domain_review_id,
            "domain_review_digest": validation.domain_review_digest,
            "domain_reviewed_by": validation.domain_reviewed_by,
            "security_review_id": validation.security_review_id,
            "security_review_digest": validation.security_review_digest,
            "security_reviewed_by": validation.security_reviewed_by,
            "organization_id": validation.organization_id,
            "environment_id": validation.environment_id,
            "operated_by": validation.operated_by,
            "lab_profile": validation.lab_profile,
            "runner_contract_version": validation.runner_contract_version,
            "runtime_version": validation.runtime_version,
            "state": validation.state.value,
            "checks": cls._lab_check_payload(validation.checks),
            "passed_count": validation.passed_count,
            "failed_count": validation.failed_count,
            "skipped_count": validation.skipped_count,
            "child_started": validation.child_started,
            "child_exit_code": validation.child_exit_code,
            "duration_ms": validation.duration_ms,
            "output_digest": validation.output_digest,
            "output_size_bytes": validation.output_size_bytes,
            "artifact_file_count": validation.artifact_file_count,
            "artifact_size_bytes": validation.artifact_size_bytes,
            "workspace_removed": validation.workspace_removed,
            "limitations": validation.limitations,
        }
        fingerprint = cls._digest(
            {
                **{
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "runtime_version",
                        "state",
                        "checks",
                        "passed_count",
                        "failed_count",
                        "skipped_count",
                        "child_started",
                        "child_exit_code",
                        "duration_ms",
                        "output_digest",
                        "output_size_bytes",
                        "artifact_file_count",
                        "artifact_size_bytes",
                        "workspace_removed",
                        "limitations",
                    }
                },
                "acknowledged_isolated_synthetic_execution": True,
                "idempotency_key": validation.idempotency_key,
            }
        )
        if (
            cls._digest(payload) != validation.canonical_digest
            or fingerprint != validation.request_fingerprint
        ):
            raise McpBuilderError("builder_lab_validation_integrity_failed")

    @staticmethod
    def _candidate_capability_payload(
        capabilities: tuple[CandidateCapabilityEvidence, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "candidate_id": item.candidate_id,
                "capability_class": item.capability_class,
                "required_permission": item.required_permission,
                "supported_product_versions": item.supported_product_versions,
                "source_citations": item.source_citations,
            }
            for item in capabilities
        ]

    @classmethod
    def _verify_candidate_handoff(cls, handoff: McpBuilderCandidateHandoff) -> None:
        payload = {
            "project_id": handoff.project_id,
            "project_version": handoff.project_version,
            "project_digest": handoff.project_digest,
            "source_digest": handoff.source_digest,
            "checkpoint_id": handoff.checkpoint_id,
            "checkpoint_digest": handoff.checkpoint_digest,
            "generation_id": handoff.generation_id,
            "generation_digest": handoff.generation_digest,
            "artifact_digest": handoff.artifact_digest,
            "validation_id": handoff.validation_id,
            "validation_digest": handoff.validation_digest,
            "domain_review_id": handoff.domain_review_id,
            "domain_review_digest": handoff.domain_review_digest,
            "domain_reviewed_by": handoff.domain_reviewed_by,
            "security_review_id": handoff.security_review_id,
            "security_review_digest": handoff.security_review_digest,
            "security_reviewed_by": handoff.security_reviewed_by,
            "lab_validation_id": handoff.lab_validation_id,
            "lab_validation_digest": handoff.lab_validation_digest,
            "lab_operated_by": handoff.lab_operated_by,
            "organization_id": handoff.organization_id,
            "environment_id": handoff.environment_id,
            "custodied_by": handoff.custodied_by,
            "handoff_profile": handoff.handoff_profile,
            "archive_contract_version": handoff.archive_contract_version,
            "state": handoff.state.value,
            "package_filename": handoff.package_filename,
            "package_digest": handoff.package_digest,
            "package_size_bytes": handoff.package_size_bytes,
            "package_entry_count": handoff.package_entry_count,
            "generated_file_count": handoff.generated_file_count,
            "generated_size_bytes": handoff.generated_size_bytes,
            "envelope_digest": handoff.envelope_digest,
            "signature_state": handoff.signature_state.value,
            "capabilities": cls._candidate_capability_payload(handoff.capabilities),
            "network_destinations": handoff.network_destinations,
            "limitations": handoff.limitations,
            "unsupported_behavior": handoff.unsupported_behavior,
            "manual_change_count": handoff.manual_change_count,
        }
        fingerprint = cls._digest(
            {
                **{
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "state",
                        "package_filename",
                        "package_digest",
                        "package_size_bytes",
                        "package_entry_count",
                        "generated_file_count",
                        "generated_size_bytes",
                        "envelope_digest",
                        "signature_state",
                        "capabilities",
                        "network_destinations",
                        "limitations",
                        "unsupported_behavior",
                        "manual_change_count",
                    }
                },
                "acknowledged_unsigned_quarantined_package": True,
                "idempotency_key": handoff.idempotency_key,
            }
        )
        if (
            cls._digest(payload) != handoff.canonical_digest
            or fingerprint != handoff.request_fingerprint
        ):
            raise McpBuilderError("builder_candidate_handoff_integrity_failed")

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

    async def _audit_generation(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        generation: McpBuilderGeneration,
        relative_path: str | None = None,
    ) -> None:
        metadata = [
            ("generation_id", generation.generation_id),
            ("project_id", generation.project_id),
            ("checkpoint_id", generation.checkpoint_id),
            ("artifact_digest", generation.artifact_digest),
        ]
        if relative_path is not None:
            metadata.append(("relative_path", relative_path))
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.generation",
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
                resource_type="resource.mcp-builder.generation",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=generation.idempotency_key,
                target_metadata=tuple(metadata),
            )
        )

    async def _audit_validation(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: McpBuilderValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.validation",
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
                resource_type="resource.mcp-builder.validation",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("project_id", validation.project_id),
                    ("generation_id", validation.generation_id),
                    ("artifact_digest", validation.artifact_digest),
                    ("validation_state", validation.state.value),
                ),
            )
        )

    async def _audit_domain_review(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        review: McpBuilderDomainReview,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.domain-review",
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
                resource_type="resource.mcp-builder.domain-review",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=review.idempotency_key,
                target_metadata=(
                    ("review_id", review.review_id),
                    ("project_id", review.project_id),
                    ("validation_id", review.validation_id),
                    ("artifact_digest", review.artifact_digest),
                    ("review_state", review.state.value),
                    ("reviewed_by", review.reviewed_by),
                ),
            )
        )

    async def _audit_security_review(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        review: McpBuilderSecurityReview,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.security-review",
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
                resource_type="resource.mcp-builder.security-review",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=review.idempotency_key,
                target_metadata=(
                    ("review_id", review.review_id),
                    ("project_id", review.project_id),
                    ("domain_review_id", review.domain_review_id),
                    ("artifact_digest", review.artifact_digest),
                    ("review_state", review.state.value),
                    ("reviewed_by", review.reviewed_by),
                ),
            )
        )

    async def _audit_lab_validation(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: McpBuilderLabValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.lab-validation",
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
                resource_type="resource.mcp-builder.lab-validation",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("lab_validation_id", validation.lab_validation_id),
                    ("project_id", validation.project_id),
                    ("security_review_id", validation.security_review_id),
                    ("artifact_digest", validation.artifact_digest),
                    ("lab_state", validation.state.value),
                    ("operated_by", validation.operated_by),
                ),
            )
        )

    async def _audit_candidate_handoff(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        handoff: McpBuilderCandidateHandoff,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.mcp-builder.candidate-handoff",
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
                resource_type="resource.mcp-builder.candidate-handoff",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.mcp-builder/resource.mcp-builder.projects/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=handoff.idempotency_key,
                target_metadata=(
                    ("handoff_id", handoff.handoff_id),
                    ("project_id", handoff.project_id),
                    ("lab_validation_id", handoff.lab_validation_id),
                    ("package_digest", handoff.package_digest),
                    ("signature_state", handoff.signature_state.value),
                    ("custodied_by", handoff.custodied_by),
                ),
            )
        )
