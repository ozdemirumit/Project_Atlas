"""Self-built connector-credential vault: metadata about a stored secret, never its value.

The actual encrypted material lives behind `atlas.core.protected_content` (ADR-184) -- this
module only describes which `secret_reference_id` (the same identifier already collected by the
"Credential reference ID" field in the bundled-connector UI) currently has a value set, and when.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

SECRET_REFERENCE_ID_PATTERN = re.compile(r"^secret\.[a-z0-9_.:-]{2,120}$")


@dataclass(frozen=True, slots=True)
class ConnectorVaultSecretReference:
    """Vault contents metadata surfaced to operators -- deliberately excludes the secret value
    and the `protected_content_blobs` digest it resolves to, neither of which any HTTP response
    should ever carry."""

    secret_reference_id: str
    updated_at: datetime
    set_by_subject_digest: str

    def __post_init__(self) -> None:
        if not SECRET_REFERENCE_ID_PATTERN.fullmatch(self.secret_reference_id):
            raise ValueError("secret_reference_id has an invalid format")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
