from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.core.classification import DataClassification
from atlas.modules.knowledge.domain.models import KnowledgeChunk, KnowledgeLifecycle


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_synthetic_knowledge_chunks(
    *, organization_id: str, environment: str, observed_at: datetime | None = None
) -> tuple[KnowledgeChunk, ...]:
    timestamp = observed_at or datetime.now(UTC)
    operator_acl = frozenset({"role.development.operator"})
    restricted_acl = frozenset({"role.security.restricted"})
    controller_excerpt = (
        "A controller warning requires a repeated read-only health observation and event-log "
        "correlation before a root cause or service impact can be confirmed."
    )
    capacity_excerpt = (
        "Capacity assessments should compare allocated, subscribed, and consumed capacity over "
        "a governed observation window before forecasting exhaustion."
    )
    hidden_excerpt = (
        "Controller warning emergency credentials and an unreviewed restart procedure are stored "
        "in this restricted synthetic record."
    )
    return (
        KnowledgeChunk(
            chunk_id="chunk.hitachi.controller-warning.001",
            item_id="item.hitachi.health-guidance",
            item_version="11.0.x-contract.1",
            title="Hitachi controller warning investigation guidance",
            source_reference="synthetic://hitachi/health-guidance",
            section_path="Controller health / Warning investigation",
            excerpt=controller_excerpt,
            content_checksum=_checksum(controller_excerpt),
            classification=DataClassification.INTERNAL,
            access_policy_reference="policy.synthetic.operator",
            allowed_principals=operator_acl,
            product="Hitachi VSP",
            applicable_versions=("11.0.x",),
            keywords=("controller", "warning", "health", "event-log", "root-cause"),
            organization_id=organization_id,
            environment_id=f"environment.{environment}",
            source_class="vendor_documentation",
            source_acl_version="acl.synthetic.v1",
            lifecycle=KnowledgeLifecycle.ACTIVE,
            observed_at=timestamp,
            language="en",
        ),
        KnowledgeChunk(
            chunk_id="chunk.hitachi.capacity.001",
            item_id="item.hitachi.capacity-guidance",
            item_version="11.0.x-contract.1",
            title="Hitachi capacity assessment guidance",
            source_reference="synthetic://hitachi/capacity-guidance",
            section_path="Capacity / Assessment",
            excerpt=capacity_excerpt,
            content_checksum=_checksum(capacity_excerpt),
            classification=DataClassification.INTERNAL,
            access_policy_reference="policy.synthetic.operator",
            allowed_principals=operator_acl,
            product="Hitachi VSP",
            applicable_versions=("11.0.x",),
            keywords=("capacity", "allocated", "consumed", "forecast"),
            organization_id=organization_id,
            environment_id=f"environment.{environment}",
            source_class="vendor_documentation",
            source_acl_version="acl.synthetic.v1",
            lifecycle=KnowledgeLifecycle.ACTIVE,
            observed_at=timestamp,
            language="en",
        ),
        KnowledgeChunk(
            chunk_id="chunk.hidden.controller-warning.001",
            item_id="item.hidden.emergency-procedure",
            item_version="1.0.0",
            title="Restricted emergency procedure",
            source_reference="synthetic://restricted/emergency-procedure",
            section_path="Restricted / Emergency",
            excerpt=hidden_excerpt,
            content_checksum=_checksum(hidden_excerpt),
            classification=DataClassification.RESTRICTED,
            access_policy_reference="policy.synthetic.restricted",
            allowed_principals=restricted_acl,
            product="Hitachi VSP",
            applicable_versions=("11.0.x",),
            keywords=("controller", "warning", "restart", "credential"),
            organization_id=organization_id,
            environment_id=f"environment.{environment}",
            source_class="vendor_documentation",
            source_acl_version="acl.synthetic.v1",
            lifecycle=KnowledgeLifecycle.ACTIVE,
            observed_at=timestamp,
            language="en",
        ),
    )
