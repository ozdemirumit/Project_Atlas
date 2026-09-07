from __future__ import annotations

import pytest

from atlas.modules.security_export.domain.baseline_detections import (
    BASELINE_DETECTION_CATALOG,
    detection_by_id,
)
from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId


def test_catalog_has_exactly_ten_entries() -> None:
    assert len(BASELINE_DETECTION_CATALOG) == 10


def test_catalog_covers_every_use_case_exactly_once() -> None:
    ids = [contract.detection_id for contract in BASELINE_DETECTION_CATALOG]
    assert set(ids) == set(DetectionUseCaseId)
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("detection_id", list(DetectionUseCaseId))
def test_detection_by_id_returns_matching_contract(detection_id: DetectionUseCaseId) -> None:
    contract = detection_by_id(detection_id)
    assert contract.detection_id is detection_id


def test_detection_by_id_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        detection_by_id("SIEM-UC-999")  # type: ignore[arg-type]


def test_every_contract_has_all_five_fixture_kinds() -> None:
    for contract in BASELINE_DETECTION_CATALOG:
        kinds = {fixture.kind for fixture in contract.test_fixtures}
        assert len(kinds) == 5


def test_every_contract_declares_a_positive_severity() -> None:
    for contract in BASELINE_DETECTION_CATALOG:
        assert contract.severity is not None
