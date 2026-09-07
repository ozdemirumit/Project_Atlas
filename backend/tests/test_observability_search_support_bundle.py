from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.observability.domain.search_support_bundle import (
    DefaultViewFocus,
    OfflineTransferMetadata,
    SearchDimension,
    SearchQuery,
    SupportBundleManifest,
    SupportBundleOptInCategory,
    SupportBundlePreview,
    support_bundle_includes_audit_data_by_default,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_search_dimension_has_thirteen_members() -> None:
    assert len(SearchDimension) == 13


def test_default_view_focus_has_seven_members() -> None:
    assert len(DefaultViewFocus) == 7


def test_search_query_requires_at_least_one_dimension() -> None:
    with pytest.raises(ValueError, match="at least one dimension"):
        SearchQuery(dimensions=(), requesting_operator_id="operator.example")


def test_search_query_rejects_duplicate_dimension() -> None:
    with pytest.raises(ValueError, match="must not repeat a dimension"):
        SearchQuery(
            dimensions=(
                (SearchDimension.SERVICE, "atlas-backend"),
                (SearchDimension.SERVICE, "atlas-frontend"),
            ),
            requesting_operator_id="operator.example",
        )


def test_support_bundle_never_includes_audit_data_by_default() -> None:
    assert support_bundle_includes_audit_data_by_default() is False


def test_opt_in_category_requires_disclosure() -> None:
    with pytest.raises(ValueError, match="clearly listed to the requester"):
        SupportBundleOptInCategory(
            category="raw_connector_results", opted_in=True, disclosed_to_requester=False
        )


def manifest(**overrides: object) -> SupportBundleManifest:
    defaults: dict[str, object] = {
        "bundle_id": "support-bundle.example",
        "included_time_range_start": NOW - timedelta(hours=2),
        "included_time_range_end": NOW,
        "included_components": ("workflows", "connectors"),
        "checksums": (("bundle.tar.gz", "a" * 64),),
        "creation_identity": "subject.support-engineer",
        "expires_at": NOW + timedelta(days=7),
        "classification": DataClassification.INTERNAL,
        "opt_in_categories": (),
        "audit_data_included": False,
        "audit_data_separately_authorized": False,
    }
    defaults.update(overrides)
    return SupportBundleManifest(**defaults)  # type: ignore[arg-type]


def test_manifest_accepts_valid_state() -> None:
    assert manifest().bundle_id == "support-bundle.example"


def test_manifest_rejects_inverted_time_range() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        manifest(included_time_range_start=NOW, included_time_range_end=NOW - timedelta(hours=1))


def test_manifest_rejects_audit_data_without_authorization() -> None:
    with pytest.raises(ValueError, match="excluded unless separately authorized"):
        manifest(audit_data_included=True, audit_data_separately_authorized=False)


def test_manifest_accepts_authorized_audit_data() -> None:
    result = manifest(audit_data_included=True, audit_data_separately_authorized=True)
    assert result.audit_data_included is True


def test_support_bundle_preview_requires_categories() -> None:
    with pytest.raises(ValueError, match="requires included categories"):
        SupportBundlePreview(included_categories=(), estimated_size_bytes=1000)


def test_offline_transfer_metadata_requires_encryption() -> None:
    with pytest.raises(ValueError, match="must be encrypted"):
        OfflineTransferMetadata(encrypted=False, chain_of_custody_reference="custody.example")
