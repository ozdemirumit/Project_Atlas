from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.guardrails.domain.instruction_hierarchy import InstructionSource, can_override
from atlas.modules.runbook_engine.domain.ingestion_and_security import (
    CommandTrustStatus,
    ExportedArtifact,
    ParseLineage,
    SourceRegistration,
    SourceRegistrationState,
    can_begin_parsing,
    is_secret_reference_safe,
    source_update_target_state,
    target_selector_within_authorized_scope,
)
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (SourceRegistrationState.REGISTERED, False),
        (SourceRegistrationState.CLASSIFIED, True),
        (SourceRegistrationState.PARSING, False),
        (SourceRegistrationState.PARSED, False),
        (SourceRegistrationState.QUARANTINED, False),
    ],
)
def test_can_begin_parsing(state: SourceRegistrationState, expected: bool) -> None:
    assert can_begin_parsing(state) is expected


def test_source_registration_constructs_cleanly() -> None:
    example = SourceRegistration(
        source_id="runbook-source.example",
        classification=DataClassification.INTERNAL,
        state=SourceRegistrationState.CLASSIFIED,
        registered_at=NOW,
    )
    assert example.state is SourceRegistrationState.CLASSIFIED


def test_source_registration_rejects_naive_registered_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceRegistration(
            source_id="runbook-source.example",
            classification=DataClassification.INTERNAL,
            state=SourceRegistrationState.REGISTERED,
            registered_at=NOW.replace(tzinfo=None),
        )


def lineage(**overrides: object) -> ParseLineage:
    defaults: dict[str, object] = {
        "source_id": "runbook-source.example",
        "original_artifact_digest": DIGEST,
        "extracted_text_digest": DIGEST,
        "parser_version": "runbook-parser.v1",
    }
    defaults.update(overrides)
    return ParseLineage(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_lineage_constructs_cleanly() -> None:
    example = lineage()
    assert example.parser_version == "runbook-parser.v1"


def test_lineage_requires_a_parser_version() -> None:
    with pytest.raises(ValueError, match="parser version"):
        lineage(parser_version="   ")


def test_lineage_requires_sha256_digests() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        lineage(original_artifact_digest="not-a-digest")


def test_source_update_target_state_is_always_draft() -> None:
    assert source_update_target_state() is RunbookLifecycleState.DRAFT


def test_secret_reference_is_safe() -> None:
    assert is_secret_reference_safe("secret://vault/storage-controller-credentials") is True


def test_a_raw_secret_value_is_not_a_safe_reference() -> None:
    assert is_secret_reference_safe("api_key=NOTAREALSECRETPLACEHOLDERVALUE0000") is False


def test_target_selector_within_authorized_scope() -> None:
    assert (
        target_selector_within_authorized_scope(
            selector_scope=frozenset({"target.example"}),
            authorized_scope=frozenset({"target.example", "target.other"}),
        )
        is True
    )


def test_target_selector_exceeding_authorized_scope() -> None:
    assert (
        target_selector_within_authorized_scope(
            selector_scope=frozenset({"target.example", "target.unauthorized"}),
            authorized_scope=frozenset({"target.example"}),
        )
        is False
    )


def test_command_trust_status_requires_both_reviewed_and_tested() -> None:
    assert CommandTrustStatus(reviewed=True, tested=False).is_trusted is False
    assert CommandTrustStatus(reviewed=False, tested=True).is_trusted is False
    assert CommandTrustStatus(reviewed=True, tested=True).is_trusted is True


def test_exported_artifact_requires_redaction() -> None:
    with pytest.raises(ValueError, match="redacted"):
        ExportedArtifact(
            artifact_id="runbook-export.example",
            classification=DataClassification.CONFIDENTIAL,
            redacted=False,
        )


def test_exported_artifact_constructs_when_redacted() -> None:
    example = ExportedArtifact(
        artifact_id="runbook-export.example",
        classification=DataClassification.CONFIDENTIAL,
        redacted=True,
    )
    assert example.redacted is True


def test_retrieved_runbook_text_can_never_override_platform_instructions() -> None:
    """SS28: "retrieved text cannot override platform instructions, policy, or guardrails" --
    reusing Guardrails' own instruction hierarchy (SS9) directly."""
    assert (
        can_override(
            acting_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
            target_source=InstructionSource.PLATFORM_INVARIANT,
        )
        is False
    )
    assert InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT.is_data_only is True
