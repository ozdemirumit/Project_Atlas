"""ATLAS-045 SS16/SS28: ingestion/parsing and security/privacy.

Reuses Guardrails' `detect_secret_patterns` (a sixth reuse this session) for SS28's "runbooks
contain secret references, never values," and Guardrails' `instruction_hierarchy.InstructionSource`/
`can_override` (SS9) directly for SS28's "retrieved text cannot override platform instructions,
policy, or guardrails" -- retrieved runbook text is exactly
`InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT`, the lowest-precedence, data-only level
that module already defines, so this module adds no new hierarchy of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState


class SourceRegistrationState(StrEnum):
    """SS16: "sources are registered and classified before parsing.\""""

    REGISTERED = "registered"
    CLASSIFIED = "classified"
    PARSING = "parsing"
    PARSED = "parsed"
    QUARANTINED = "quarantined"


def can_begin_parsing(state: SourceRegistrationState) -> bool:
    """SS16: parsing may only begin once a source has been registered *and* classified."""
    return state is SourceRegistrationState.CLASSIFIED


@dataclass(frozen=True, slots=True)
class SourceRegistration:
    source_id: str
    classification: DataClassification
    state: SourceRegistrationState
    registered_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.source_id, "source_id")
        if self.registered_at.tzinfo is None:
            raise ValueError("registered_at must be timezone-aware")


_DIGEST_CHARS = frozenset("0123456789abcdef")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in _DIGEST_CHARS for character in value)


@dataclass(frozen=True, slots=True)
class ParseLineage:
    """SS16: "original artifact, extracted text, structure, and parser version retain
    lineage.\""""

    source_id: str
    original_artifact_digest: str
    extracted_text_digest: str
    parser_version: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.source_id, "source_id")
        if not self.parser_version.strip():
            raise ValueError("a parse lineage requires a parser version")
        if not _is_sha256(self.original_artifact_digest) or not _is_sha256(
            self.extracted_text_digest
        ):
            raise ValueError("a parse lineage requires SHA-256 digests")


class UntrustedContentKind(StrEnum):
    """SS16: "active content, prompt injection, scripts, macros, and malformed files are treated
    as untrusted.\""""

    ACTIVE_CONTENT = "active_content"
    PROMPT_INJECTION = "prompt_injection"
    SCRIPT = "script"
    MACRO = "macro"
    MALFORMED_FILE = "malformed_file"


class ParseDisposition(StrEnum):
    """SS16: "unsupported or ambiguous constructs are quarantined or routed to review.\""""

    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    ROUTED_TO_REVIEW = "routed_to_review"


def source_update_target_state() -> RunbookLifecycleState:
    """SS16: "source updates create candidate versions; they do not mutate a published runbook."
    A source update always produces a new `DRAFT` version -- never a mutation of whatever state
    the runbook's current version already holds."""
    return RunbookLifecycleState.DRAFT


def is_secret_reference_safe(reference: str) -> bool:
    """SS28: "runbooks contain secret references, never values." A well-formed reference (e.g.
    `secret://vault/path`) should never itself match a raw secret pattern."""
    return not detect_secret_patterns(reference)


def target_selector_within_authorized_scope(
    *, selector_scope: frozenset[str], authorized_scope: frozenset[str]
) -> bool:
    """SS28: "target selectors cannot expand outside authorized scope.\""""
    return selector_scope <= authorized_scope


@dataclass(frozen=True, slots=True)
class CommandTrustStatus:
    """SS28: "commands and scripts are untrusted artifacts until reviewed and tested.\""""

    reviewed: bool
    tested: bool

    @property
    def is_trusted(self) -> bool:
        return self.reviewed and self.tested


@dataclass(frozen=True, slots=True)
class ExportedArtifact:
    """SS28: "exported checklists and evidence packages are classified and redacted.\""""

    artifact_id: str
    classification: DataClassification
    redacted: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if not self.redacted:
            raise ValueError("an exported artifact must be redacted before export")
