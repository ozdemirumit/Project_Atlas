from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from hashlib import sha256

from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent

HANDOFF_ENVELOPE_PATH = "ATLAS-CANDIDATE-HANDOFF.json"
MAX_ARCHIVE_BYTES = 25_000_000


@dataclass(frozen=True, slots=True)
class CandidateArchive:
    content: bytes
    digest: str
    size_bytes: int
    entry_count: int
    envelope_digest: str


class DeterministicCandidateArchiveBuilder:
    def build(
        self, *, files: tuple[BuilderGeneratedContent, ...], envelope: dict[str, object]
    ) -> CandidateArchive:
        paths = [item.relative_path for item in files]
        if not files or len(files) > 500 or len(paths) != len(set(paths)):
            raise ValueError("candidate archive inventory is invalid")
        envelope_bytes = (
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        ).encode("utf-8")
        envelope_digest = sha256(envelope_bytes).hexdigest()
        entries = [(item.relative_path, item.content.encode("utf-8")) for item in files]
        entries.append((HANDOFF_ENVELOPE_PATH, envelope_bytes))
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for path, content in sorted(entries):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                info.compress_type = zipfile.ZIP_STORED
                info.flag_bits = 0
                archive.writestr(info, content)
        content = output.getvalue()
        if not content or len(content) > MAX_ARCHIVE_BYTES:
            raise ValueError("candidate archive is outside platform bounds")
        return CandidateArchive(
            content=content,
            digest=sha256(content).hexdigest(),
            size_bytes=len(content),
            entry_count=len(entries),
            envelope_digest=envelope_digest,
        )
