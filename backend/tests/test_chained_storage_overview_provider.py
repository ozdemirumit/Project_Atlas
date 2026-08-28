from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.storage.adapters.chained import ChainedStorageOverviewProvider
from atlas.modules.storage.domain.models import (
    EvidenceRecord,
    FreshnessState,
    InvestigationState,
    StorageAsset,
    StorageHealthState,
    StorageInvestigation,
    StorageOverview,
    StorageReport,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _overview(*, assets: tuple[StorageAsset, ...], summary: str) -> StorageOverview:
    evidence = (
        EvidenceRecord(
            reference="evidence.test.fixture",
            source="test fixture",
            source_version="1.0.0",
            observed_at=NOW,
            freshness=FreshnessState.CURRENT,
            trust_basis="test fixture",
        ),
    )
    investigation = StorageInvestigation(
        investigation_id="investigation.storage.test",
        title="Test overview",
        state=InvestigationState.PROVISIONAL if assets else InvestigationState.INCONCLUSIVE,
        summary=summary,
        hypotheses=(),
        unknowns=("test unknown",),
        next_checks=(),
        evidence_references=("evidence.test.fixture",),
        updated_at=NOW,
    )
    report = StorageReport(
        report_id="report.storage.test",
        title="Test report",
        generated_at=NOW,
        executive_summary=summary,
        confirmed_facts=(),
        provisional_findings=(),
        unknowns=("test unknown",),
        evidence_references=("evidence.test.fixture",),
        safety_notice="Decision support only.",
    )
    return StorageOverview(
        snapshot_id="snapshot.storage.test",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        target_id="target.test",
        data_profile="configured_test_read_only",
        generated_at=NOW,
        assets=assets,
        findings=(),
        evidence=evidence,
        investigation=investigation,
        report=report,
    )


def _asset(asset_id: str) -> StorageAsset:
    return StorageAsset(
        asset_id=asset_id,
        storage_device_id=asset_id,
        vendor="Test Vendor",
        model="Test Model",
        serial_number="TEST123",
        health=StorageHealthState.HEALTHY,
        observed_at=NOW,
        evidence_references=("evidence.test.fixture",),
    )


class StubProvider:
    def __init__(self, overview: StorageOverview) -> None:
        self._overview = overview
        self.calls = 0

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        del requested_at
        self.calls += 1
        return self._overview


@pytest.mark.asyncio
async def test_returns_the_first_provider_with_real_assets() -> None:
    first = StubProvider(_overview(assets=(_asset("asset.storage.a"),), summary="first"))
    second = StubProvider(_overview(assets=(_asset("asset.storage.b"),), summary="second"))
    provider = ChainedStorageOverviewProvider(providers=(first, second))

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.report.executive_summary == "first"
    assert first.calls == 1
    assert second.calls == 0


@pytest.mark.asyncio
async def test_falls_through_to_the_next_provider_when_the_first_is_unavailable() -> None:
    first = StubProvider(_overview(assets=(), summary="first unavailable"))
    second = StubProvider(_overview(assets=(_asset("asset.storage.b"),), summary="second"))
    provider = ChainedStorageOverviewProvider(providers=(first, second))

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.report.executive_summary == "second"
    assert first.calls == 1
    assert second.calls == 1


@pytest.mark.asyncio
async def test_returns_the_last_unavailable_overview_when_none_have_assets() -> None:
    first = StubProvider(_overview(assets=(), summary="first unavailable"))
    second = StubProvider(_overview(assets=(), summary="second unavailable"))
    provider = ChainedStorageOverviewProvider(providers=(first, second))

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert overview.report.executive_summary == "second unavailable"


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        ChainedStorageOverviewProvider(providers=())
