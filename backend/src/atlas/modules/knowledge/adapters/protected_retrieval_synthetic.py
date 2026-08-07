from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.protected_retrieval_ports import (
    OperationalKnowledgeRetrievalError,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeEvidencePackage,
    OperationalKnowledgeEvidenceResult,
    OperationalKnowledgeRetrievalInstruction,
    OperationalKnowledgeRetrievalReceipt,
    OperationalKnowledgeRetrievalRecord,
)


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            _normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def _canonical_digest(
    value: OperationalKnowledgeEvidencePackage | OperationalKnowledgeRetrievalReceipt,
) -> str:
    payload = asdict(value)
    payload.pop("canonical_digest", None)
    return _digest(payload)


class SyntheticOperationalKnowledgeTrustedRetriever:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._vault: dict[str, tuple[OperationalKnowledgeEvidencePackage, str, str]] = {}
        self.calls: list[OperationalKnowledgeRetrievalInstruction] = []

    async def retrieve(
        self, instruction: OperationalKnowledgeRetrievalInstruction
    ) -> tuple[OperationalKnowledgeRetrievalReceipt, OperationalKnowledgeEvidencePackage]:
        self.calls.append(instruction)
        now = self._clock()
        excerpt = (
            "The approved synthetic knowledge item reports a controller warning and requires "
            "correlation with current read-only hardware and event evidence before a cause or "
            "service impact can be established."
        )[: instruction.maximum_excerpt_characters]
        evidence = OperationalKnowledgeEvidenceResult(
            evidence_reference_id=(
                f"evidence-reference.{instruction.retrieval_id.rsplit('.', 1)[-1]}"
            ),
            source_title="Approved storage controller investigation guidance",
            source_class="source-class.approved-operational-knowledge",
            excerpt=excerpt,
            citation_location="Synthetic knowledge item, section Investigation boundary",
            applicability="Hitachi storage controller warning investigations in the lab profile",
            lifecycle_state="lifecycle.published",
            freshness_state="freshness.current",
            conflict_state="conflict.none-observed",
            safety_state="safety.untrusted-instructions-isolated",
            rank_band="rank-band.high",
        )
        results = (evidence,)[: instruction.maximum_results]
        package = OperationalKnowledgeEvidencePackage(
            retrieval_id=instruction.retrieval_id,
            query=instruction.query,
            results=results,
            outcome=(
                "retrieval-outcome.evidence-available"
                if results
                else "retrieval-outcome.insufficient-evidence"
            ),
            generated_at=now,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        package = replace(package, canonical_digest=_canonical_digest(package))
        artifact_reference = (
            f"protected-retrieval-artifact.{instruction.retrieval_id.rsplit('.', 1)[-1]}"
        )
        artifact_digest = _digest(asdict(package))
        self._vault[artifact_reference] = (
            package,
            instruction.authorization_context_digest,
            artifact_digest,
        )
        receipt = OperationalKnowledgeRetrievalReceipt(
            retrieval_id=instruction.retrieval_id,
            schema_version="atlas.operational-knowledge-retrieval-receipt.v1",
            version=1,
            retriever_id="operational-knowledge-trusted-retriever.synthetic",
            attested_by="subject.operational-knowledge-trusted-retriever-attestor",
            publication_id=instruction.publication_id,
            publication_digest=instruction.publication_digest,
            consumer_subject_digest=instruction.consumer_subject_digest,
            query_digest=instruction.query_digest,
            authorization_context_digest=instruction.authorization_context_digest,
            evidence_package_digest=package.canonical_digest,
            protected_artifact_reference=artifact_reference,
            protected_artifact_digest=artifact_digest,
            result_count=len(results),
            outcome=package.outcome,
            authorization_filter_digest=_digest(
                [
                    instruction.authorization_profile_digest,
                    instruction.access_policy_id,
                    "before-scoring",
                ]
            ),
            ranking_digest=_digest([instruction.ranking_profile_digest, len(results)]),
            citation_validation_digest=_digest(
                [instruction.evidence_profile_digest, evidence.evidence_reference_id]
            ),
            safety_validation_digest=_digest([instruction.evidence_profile_digest, "isolated"]),
            retrieved_at=now,
            expires_at=instruction.expires_at,
            authorization_filtered_before_scoring=True,
            citations_validated=True,
            protected_vault_write_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=_canonical_digest(receipt))
        return receipt, package

    async def rehydrate(
        self,
        *,
        record: OperationalKnowledgeRetrievalRecord,
        authorization_context_digest: str,
    ) -> OperationalKnowledgeEvidencePackage:
        stored = self._vault.get(record.protected_artifact_reference)
        if (
            stored is None
            or stored[1] != authorization_context_digest
            or stored[2] != record.protected_artifact_digest
            or stored[0].canonical_digest != record.evidence_package_digest
            or self._clock() >= record.expires_at
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_protected_artifact_unavailable"
            )
        return stored[0]


class UnavailableOperationalKnowledgeTrustedRetriever:
    async def retrieve(
        self, instruction: OperationalKnowledgeRetrievalInstruction
    ) -> tuple[OperationalKnowledgeRetrievalReceipt, OperationalKnowledgeEvidencePackage]:
        del instruction
        raise OperationalKnowledgeRetrievalError(
            "operational_knowledge_trusted_retriever_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: OperationalKnowledgeRetrievalRecord,
        authorization_context_digest: str,
    ) -> OperationalKnowledgeEvidencePackage:
        del record, authorization_context_digest
        raise OperationalKnowledgeRetrievalError(
            "operational_knowledge_retrieval_protected_artifact_unavailable"
        )
