from __future__ import annotations

import asyncio
from dataclasses import replace
from hashlib import sha256

from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError
from atlas.modules.mcp_builder.domain.generation import BuilderGeneratedFile, McpBuilderGeneration


class InMemoryMcpBuilderGenerationRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, McpBuilderGeneration] = {}
        self._by_project: dict[str, McpBuilderGeneration] = {}
        self._by_create_key: dict[tuple[str, str], McpBuilderGeneration] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, generation_id: str) -> McpBuilderGeneration | None:
        return self._copy(self._by_id.get(generation_id))

    async def get_by_project(self, *, project_id: str) -> McpBuilderGeneration | None:
        return self._copy(self._by_project.get(project_id))

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> McpBuilderGeneration | None:
        return self._copy(self._by_create_key.get((requested_by, idempotency_key)))

    async def add(self, generation: McpBuilderGeneration) -> bool:
        async with self._lock:
            create_key = (generation.requested_by, generation.idempotency_key)
            if (
                generation.generation_id in self._by_id
                or generation.project_id in self._by_project
                or create_key in self._by_create_key
            ):
                return False
            stored = replace(generation, reused=False)
            self._by_id[stored.generation_id] = stored
            self._by_project[stored.project_id] = stored
            self._by_create_key[create_key] = stored
            return True

    async def close(self) -> None:
        return None

    @staticmethod
    def _copy(value: McpBuilderGeneration | None) -> McpBuilderGeneration | None:
        return replace(value) if value is not None else None


class InMemoryMcpBuilderArtifactPublisher:
    def __init__(self) -> None:
        self._artifacts: dict[tuple[str, str], dict[str, str]] = {}
        self._lock = asyncio.Lock()

    async def publish(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        files: tuple[BuilderGeneratedContent, ...],
    ) -> bool:
        key = (generation_id, artifact_digest)
        proposed = {item.relative_path: item.content for item in files}
        async with self._lock:
            existing = self._artifacts.get(key)
            if existing is not None:
                if existing != proposed:
                    raise McpBuilderArtifactError("builder_generation_artifact_conflict")
                return False
            self._artifacts[key] = proposed
            return True

    async def read(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        inventory: tuple[BuilderGeneratedFile, ...],
        relative_path: str,
    ) -> str:
        content = self._artifacts.get((generation_id, artifact_digest), {}).get(relative_path)
        expected = next((item for item in inventory if item.relative_path == relative_path), None)
        if content is None or expected is None:
            raise McpBuilderArtifactError("builder_generation_file_not_found")
        encoded = content.encode("utf-8")
        if len(encoded) != expected.size_bytes or sha256(encoded).hexdigest() != expected.sha256:
            raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
        return content
