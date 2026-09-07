"""ATLAS-033 SS22/SS23: search/operational experience and support bundles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class SearchDimension(StrEnum):
    """SS22: "authorized operators can search by" these thirteen dimensions."""

    TIME = "time"
    SERVICE = "service"
    VERSION = "version"
    ENVIRONMENT = "environment"
    LEVEL = "level"
    EVENT_NAME = "event_name"
    ERROR_CODE = "error_code"
    CORRELATION = "correlation"
    TRACE = "trace"
    WORKFLOW = "workflow"
    CONNECTOR = "connector"
    CAPABILITY = "capability"
    SAFE_TARGET_REFERENCE = "safe_target_reference"


class DefaultViewFocus(StrEnum):
    """SS22's seven default-view emphases."""

    CURRENT_PLATFORM_HEALTH_AND_CRITICAL_FAILURES = "current_platform_health_and_critical_failures"
    RECENT_DEPLOYMENT_UPGRADE_AND_CONFIGURATION_CHANGES = (
        "recent_deployment_upgrade_and_configuration_changes"
    )
    FAILED_AND_SLOW_DEPENDENCIES = "failed_and_slow_dependencies"
    CONNECTOR_AND_WORKFLOW_ERRORS = "connector_and_workflow_errors"
    AUTHENTICATION_AND_AUTHORIZATION_DEGRADATION = "authentication_and_authorization_degradation"
    AI_RAG_AND_MODEL_ENDPOINT_HEALTH = "ai_rag_and_model_endpoint_health"
    LOGGING_PIPELINE_LAG_LOSS_RISK_AND_STORAGE_FORECAST = (
        "logging_pipeline_lag_loss_risk_and_storage_forecast"
    )


@dataclass(frozen=True, slots=True)
class SearchQuery:
    dimensions: tuple[tuple[SearchDimension, str], ...]
    requesting_operator_id: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.requesting_operator_id, "requesting_operator_id")
        if not self.dimensions:
            raise ValueError("a search query requires at least one dimension")
        used = [dimension for dimension, _ in self.dimensions]
        if len(set(used)) != len(used):
            raise ValueError("a search query must not repeat a dimension")


def support_bundle_includes_audit_data_by_default() -> bool:
    """SS23: "audit data is excluded unless separately authorized.\""""
    return False


@dataclass(frozen=True, slots=True)
class SupportBundleOptInCategory:
    """SS23: "customer topology, documents, prompts, and raw connector results are opt-in and
    clearly listed." `disclosed_to_requester` must be `True` to construct at all."""

    category: str
    opted_in: bool
    disclosed_to_requester: bool

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("a support bundle opt-in category requires a name")
        if not self.disclosed_to_requester:
            raise ValueError("SS23: opt-in categories must be clearly listed to the requester")


@dataclass(frozen=True, slots=True)
class SupportBundleManifest:
    """SS23: "the bundle has a manifest, checksums, creation identity, expiry, and
    classification.\""""

    bundle_id: str
    included_time_range_start: datetime
    included_time_range_end: datetime
    included_components: tuple[str, ...]
    checksums: tuple[tuple[str, str], ...]
    creation_identity: str
    expires_at: datetime
    classification: DataClassification
    opt_in_categories: tuple[SupportBundleOptInCategory, ...]
    audit_data_included: bool
    audit_data_separately_authorized: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.bundle_id, "bundle_id")
        for field_name, value in (
            ("included_time_range_start", self.included_time_range_start),
            ("included_time_range_end", self.included_time_range_end),
            ("expires_at", self.expires_at),
        ):
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.included_time_range_end < self.included_time_range_start:
            raise ValueError("included_time_range_end must not precede included_time_range_start")
        if not self.included_components:
            raise ValueError("a support bundle manifest requires included components")
        if not self.checksums:
            raise ValueError("a support bundle manifest requires checksums")
        if not self.creation_identity.strip():
            raise ValueError("a support bundle manifest requires a creation identity")
        if self.audit_data_included and not self.audit_data_separately_authorized:
            raise ValueError("SS23: audit data is excluded unless separately authorized")


@dataclass(frozen=True, slots=True)
class SupportBundlePreview:
    """SS23: "preview shows included categories and size before export.\""""

    included_categories: tuple[str, ...]
    estimated_size_bytes: int

    def __post_init__(self) -> None:
        if not self.included_categories:
            raise ValueError("a support bundle preview requires included categories")
        if self.estimated_size_bytes < 0:
            raise ValueError("estimated_size_bytes must not be negative")


@dataclass(frozen=True, slots=True)
class OfflineTransferMetadata:
    """`encrypted` must be `True` to construct at all -- SS23: "offline transfer supports
    encryption and chain-of-custody metadata.\""""

    encrypted: bool
    chain_of_custody_reference: str

    def __post_init__(self) -> None:
        if not self.encrypted:
            raise ValueError("SS23: offline transfer of a support bundle must be encrypted")
        if not self.chain_of_custody_reference.strip():
            raise ValueError("offline transfer metadata requires a chain-of-custody reference")
