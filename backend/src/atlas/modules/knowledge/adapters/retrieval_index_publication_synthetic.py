from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.retrieval_index_publication_ports import (
    OperationalKnowledgeRetrievalPublicationError,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationInstruction,
    OperationalKnowledgeRetrievalPublicationReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
        ).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeRetrievalPublisher:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeRetrievalPublicationInstruction] = []

    async def publish(
        self, instruction: OperationalKnowledgeRetrievalPublicationInstruction
    ) -> OperationalKnowledgeRetrievalPublicationReceipt:
        self.calls.append(instruction)
        route_generation = _digest(
            [
                instruction.index_staging_digest,
                instruction.projection_manifest_digest,
                instruction.publication_profile_digest,
                instruction.retrieval_route_profile_digest,
                "active-generation-v1",
            ]
        )
        receipt = OperationalKnowledgeRetrievalPublicationReceipt(
            publication_id=instruction.publication_id,
            schema_version="atlas.operational-knowledge-retrieval-publication-receipt.v1",
            version=1,
            publisher_id="operational-knowledge-retrieval-publisher.synthetic",
            published_by="subject.operational-knowledge-retrieval-publisher",
            instruction_digest=_digest(asdict(instruction)),
            index_staging_digest=instruction.index_staging_digest,
            projection_manifest_digest=instruction.projection_manifest_digest,
            publication_profile_digest=instruction.publication_profile_digest,
            retrieval_route_profile_digest=instruction.retrieval_route_profile_digest,
            route_generation_digest=route_generation,
            activation_digest=_digest([route_generation, "atomic", "active"]),
            route_verification_digest=_digest(
                [route_generation, instruction.organization_id, "verified"]
            ),
            authorization_enforcement_digest=_digest(
                [
                    instruction.authorization_metadata_validation_digest,
                    instruction.access_policy_id,
                    instruction.classification,
                    "enforced",
                ]
            ),
            lifecycle_filter_digest=_digest(
                [instruction.knowledge_item_id, instruction.retention_policy_id, "published"]
            ),
            rollback_metadata_digest=_digest([route_generation, "governed-reference-only"]),
            atomic_activation=True,
            published_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeRetrievalPublisher:
    async def publish(
        self, instruction: OperationalKnowledgeRetrievalPublicationInstruction
    ) -> OperationalKnowledgeRetrievalPublicationReceipt:
        del instruction
        raise OperationalKnowledgeRetrievalPublicationError(
            "operational_knowledge_retrieval_publisher_unavailable"
        )
