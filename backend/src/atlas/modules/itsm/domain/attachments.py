"""ATLAS-036 SS17: attachments and evidence.

This module was, until now, entirely missing: no attachment upload/download, no active-content
check, no classification/permission validation, no evidence manifest/checksum packaging, no
secret-exclusion default, no expiring re-authorized links, and no audit coverage anywhere in
`atlas.modules.itsm`. It follows two real precedents closely rather than inventing a new shape:

- `connectors/domain/content_policy_scan.py`'s honest split between real, deterministic checks
  (a `bool = True`-by-default completion flag a constructor can actually justify) and anything
  that would need infrastructure this codebase does not have (a flag that structurally stays
  `False`). `guardrails/domain/input_guardrails.py`'s own module docstring already states this
  codebase's position plainly: it does not attempt malware/active-content scanning that would
  need a real scanner engine. What *is* real and built here: a strict allowlisted
  media-type/extension check, a bounded size check, deterministic active-content *signature*
  detection for well-known dangerous byte patterns and script markup, and reuse of
  `guardrails.domain.input_guardrails.detect_secret_patterns` for text-decodable content. None of
  that is a substitute for a signature-database antivirus engine, so `malware_signature_scan_
  completed` stays structurally `False` -- the constructor rejects any attempt to set it `True`.
- `support/domain/support_bundle.py`'s `SupportBundlePreview`/`SupportBundleExport` shape for the
  evidence package's manifest/checksum/expiry and window-ordering validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_MEDIA_TYPE = re.compile(r"^[a-z]+/[a-z0-9.+-]+$")

#: SS17: "Attachments use allowlisted types and bounded size." Deliberately excludes every
#: executable, macro-enabled Office, archive, and HTML/script-bearing type -- the allowlist
#: itself is the first line of active-content defense, not just the signature check below.
ALLOWED_ATTACHMENT_MEDIA_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "text/plain",
        "text/csv",
        "application/json",
        "text/markdown",
    }
)

#: SS17: "bounded size." Matches the bound this codebase already uses for a comparable untrusted
#: transfer (`ConnectorPackageContentPolicyScan.package_size_bytes`), scaled down for a single
#: attachment rather than a whole connector package.
MAX_ATTACHMENT_SIZE_BYTES = 10_000_000

#: Which allowlisted media types this module treats as text and therefore runs
#: `detect_secret_patterns` and script-markup detection over. The binary types (pdf/png/jpeg) are
#: never decoded as text.
_TEXT_DECODABLE_MEDIA_TYPES = frozenset(
    {"text/plain", "text/csv", "application/json", "text/markdown"}
)

#: Well-known magic-byte prefixes for executables and archives (including Office Open XML, which
#: is a zip). Checked against the first bytes of *every* upload regardless of its claimed
#: media type, so a mislabeled dangerous file cannot slip through on the media-type check alone.
_DANGEROUS_SIGNATURES: tuple[bytes, ...] = (
    b"MZ",  # Windows PE executable
    b"\x7fELF",  # ELF executable
    b"PK\x03\x04",  # zip / Office Open XML / jar archive
    b"\xca\xfe\xba\xbe",  # Mach-O / Java class fat binary
    b"#!/",  # shebang script
)

_SCRIPT_MARKUP = re.compile(r"<script|<iframe|javascript:", re.IGNORECASE)


def active_content_signature_detected(content: bytes) -> bool:
    """SS17: "Malware and active-content checks occur before transfer or ingestion." The
    deterministic half of that requirement this codebase can actually perform -- see the module
    docstring for what is deliberately *not* claimed here."""
    head = content[:8]
    return any(head.startswith(signature) for signature in _DANGEROUS_SIGNATURES)


def embedded_script_markup_detected(text: str) -> bool:
    """Active-content detection for the text-decodable allowlisted types: a pasted-in
    `<script>`/`<iframe>`/`javascript:` fragment inside an otherwise plain-text or markdown
    attachment."""
    return _SCRIPT_MARKUP.search(text) is not None


def attachment_content_is_text_decodable(media_type: str) -> bool:
    return media_type in _TEXT_DECODABLE_MEDIA_TYPES


class ItsmAttachmentScanState(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ItsmAttachment:
    attachment_id: str
    external_ticket_id: str
    organization_id: str
    environment_id: str
    filename: str
    media_type: str
    size_bytes: int
    content_digest: str
    classification: str
    uploaded_by: str
    uploaded_at: datetime
    allowlist_check_completed: bool
    size_check_completed: bool
    active_content_policy_scan_completed: bool
    secret_pattern_scan_completed: bool
    scan_state: ItsmAttachmentScanState
    rejection_reason: str | None
    #: Deliberately stays `False` always -- see the module docstring. Distinct from the four
    #: `*_completed` flags above, which are real and can honestly justify a `PASSED` scan_state.
    malware_signature_scan_completed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.attachment_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.uploaded_by,
        ):
            validate_stable_identifier(value, "ITSM attachment identifier")
        if not self.external_ticket_id.strip():
            raise ValueError("an ITSM attachment requires the target ticket's external id")
        if (
            not self.filename.strip()
            or "/" in self.filename
            or "\\" in self.filename
            or len(self.filename) > 255
        ):
            raise ValueError("an ITSM attachment filename is invalid")
        if (
            _MEDIA_TYPE.fullmatch(self.media_type) is None
            or self.media_type not in ALLOWED_ATTACHMENT_MEDIA_TYPES
        ):
            raise ValueError("an ITSM attachment media type is not allowlisted")
        if not 1 <= self.size_bytes <= MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError("an ITSM attachment size is outside the bounded allowance")
        if _DIGEST.fullmatch(self.content_digest) is None:
            raise ValueError("an ITSM attachment content digest is invalid")
        if self.uploaded_at.tzinfo is None:
            raise ValueError("an ITSM attachment upload time must be timezone-aware")
        if self.malware_signature_scan_completed:
            raise ValueError(
                "an ITSM attachment cannot claim a malware signature scan this codebase has no "
                "real scanner engine to perform"
            )
        if self.scan_state is ItsmAttachmentScanState.PASSED:
            if self.rejection_reason is not None:
                raise ValueError("a passed ITSM attachment cannot carry a rejection reason")
            if not (
                self.allowlist_check_completed
                and self.size_check_completed
                and self.active_content_policy_scan_completed
                and self.secret_pattern_scan_completed
            ):
                raise ValueError(
                    "an ITSM attachment cannot be marked passed without every real check "
                    "actually completing"
                )
        elif self.scan_state is ItsmAttachmentScanState.REJECTED:
            if self.rejection_reason is None or not self.rejection_reason.strip():
                raise ValueError("a rejected ITSM attachment requires a rejection reason")
        elif self.rejection_reason is not None:
            raise ValueError("a pending ITSM attachment cannot carry a rejection reason")

    @property
    def transferable(self) -> bool:
        """SS17's allowlist/size/active-content/secret gate an attachment must clear before it
        may be transferred, packaged into evidence, or downloaded. Never true for a rejected or
        still-pending attachment, and -- honestly -- never backed by a real malware signature
        scan, because this codebase has no scanner engine to run one."""
        return self.scan_state is ItsmAttachmentScanState.PASSED


@dataclass(frozen=True, slots=True)
class ItsmEvidencePackage:
    """SS17: "Evidence packages include manifest, checksum, artifact versions, creation time, and
    expiry where appropriate." Mirrors `support_bundle.SupportBundleExport`'s digest/expiry shape.
    """

    package_id: str
    organization_id: str
    environment_id: str
    external_ticket_id: str
    attachment_ids: tuple[str, ...]
    manifest_digest: str
    artifact_versions: tuple[str, ...]
    classification: str
    custodied_by: str
    created_by: str
    created_at: datetime
    expires_at: datetime | None

    def __post_init__(self) -> None:
        for value in (
            self.package_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.custodied_by,
            self.created_by,
        ):
            validate_stable_identifier(value, "ITSM evidence package identifier")
        if not self.external_ticket_id.strip():
            raise ValueError("an ITSM evidence package requires the target ticket's external id")
        if (
            not self.attachment_ids
            or len(self.attachment_ids) > 50
            or len(self.attachment_ids) != len(set(self.attachment_ids))
        ):
            raise ValueError("an ITSM evidence package requires 1-50 distinct attachments")
        for value in self.attachment_ids:
            validate_stable_identifier(value, "ITSM evidence package attachment identifier")
        if _DIGEST.fullmatch(self.manifest_digest) is None:
            raise ValueError("an ITSM evidence package manifest digest is invalid")
        if not self.artifact_versions or len(self.artifact_versions) > 50:
            raise ValueError("an ITSM evidence package requires 1-50 artifact versions")
        for value in self.artifact_versions:
            validate_stable_identifier(value, "ITSM evidence package artifact version")
        if self.created_at.tzinfo is None:
            raise ValueError("an ITSM evidence package creation time must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("an ITSM evidence package expiry must be timezone-aware")
            if self.expires_at <= self.created_at:
                raise ValueError("an ITSM evidence package cannot expire before it is created")


@dataclass(frozen=True, slots=True)
class ItsmAttachmentDownloadLink:
    """SS17: "Links re-authorize access in Atlas and can expire." The link record itself carries
    no authority -- `active_at` is a structural, timestamp-only check; the actual re-authorization
    (RBAC permission plus classification ceiling) happens in the application service at the
    moment of consumption, not here. See `application/attachments.py`'s `consume_download_link`.
    """

    link_id: str
    attachment_id: str
    issued_to_subject_id: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None

    def __post_init__(self) -> None:
        for value in (self.link_id, self.attachment_id, self.issued_to_subject_id):
            validate_stable_identifier(value, "ITSM attachment download link identifier")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("an ITSM attachment download link's times must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("an ITSM attachment download link must expire after it is issued")
        if self.consumed_at is not None:
            if self.consumed_at.tzinfo is None:
                raise ValueError(
                    "an ITSM attachment download link consumption time must be timezone-aware"
                )
            if self.consumed_at < self.issued_at or self.consumed_at > self.expires_at:
                raise ValueError(
                    "an ITSM attachment download link cannot be consumed outside its validity "
                    "window"
                )

    @property
    def consumed(self) -> bool:
        return self.consumed_at is not None

    def active_at(self, moment: datetime) -> bool:
        """A link past its `expires_at`, or already consumed, is structurally no longer usable --
        independent of, and in addition to, the RBAC/classification re-check the service performs
        at consumption time."""
        return self.consumed_at is None and moment < self.expires_at
