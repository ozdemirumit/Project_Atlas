from __future__ import annotations

import io
import zipfile
from hashlib import sha256

import pytest

from atlas.modules.mcp_builder.adapters.candidate_archive_filesystem import (
    FileSystemMcpBuilderCandidateArchivePublisher,
)
from atlas.modules.mcp_builder.application.candidate_archive import (
    HANDOFF_ENVELOPE_PATH,
    DeterministicCandidateArchiveBuilder,
)
from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError


def generated_file(path: str, content: str) -> BuilderGeneratedContent:
    return BuilderGeneratedContent(
        relative_path=path,
        media_type="text/plain",
        content=content,
        source_candidate_ids=("candidate.storage.read",),
    )


def test_candidate_archive_is_deterministic_bounded_and_quarantined() -> None:
    builder = DeterministicCandidateArchiveBuilder()
    files = (
        generated_file("src/connector.py", "QUARANTINED = True\n"),
        generated_file("README.md", "# Candidate\n"),
    )
    envelope = {
        "schema_version": "atlas.mcp-builder-candidate-handoff-envelope.v1",
        "state": "candidate_quarantined",
        "signature_state": "unsigned",
        "connector_registered": False,
        "runtime_trust_granted": False,
        "execution_authorized": False,
    }

    first = builder.build(files=files, envelope=envelope)
    second = builder.build(files=tuple(reversed(files)), envelope=envelope)

    assert first == second
    assert first.digest == sha256(first.content).hexdigest()
    assert first.entry_count == 3
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        assert archive.namelist() == sorted(
            [HANDOFF_ENVELOPE_PATH, "README.md", "src/connector.py"]
        )
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        assert all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist())
        assert all((item.external_attr >> 16) & 0o777 == 0o600 for item in archive.infolist())
        assert b'"signature_state":"unsigned"' in archive.read(HANDOFF_ENVELOPE_PATH)


@pytest.mark.asyncio
async def test_candidate_archive_publisher_is_immutable_and_detects_corruption(tmp_path) -> None:
    publisher = FileSystemMcpBuilderCandidateArchivePublisher(root=tmp_path / "candidates")
    content = b"deterministic-candidate"
    digest = sha256(content).hexdigest()

    assert await publisher.publish(package_digest=digest, content=content) is True
    assert await publisher.publish(package_digest=digest, content=content) is False
    assert await publisher.read(package_digest=digest, size_bytes=len(content)) == content

    path = tmp_path / "candidates" / digest[:2] / f"{digest}.zip"
    path.write_bytes(b"changed")
    with pytest.raises(McpBuilderArtifactError, match="builder_candidate_archive_integrity_failed"):
        await publisher.read(package_digest=digest, size_bytes=len(content))
