from __future__ import annotations

from typing import Protocol

from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.domain.design_review import McpBuilderDesignCheckpoint
from atlas.modules.mcp_builder.domain.generation import BuilderGeneratedFile, McpBuilderGeneration
from atlas.modules.mcp_builder.domain.models import McpBuilderProject
from atlas.modules.mcp_builder.domain.validation import McpBuilderValidation


class McpBuilderError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class McpBuilderArtifactError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class McpBuilderProjectRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, owner_id: str, idempotency_key: str) -> McpBuilderProject | None: ...

    async def get_by_id(self, *, owner_id: str, project_id: str) -> McpBuilderProject | None: ...

    async def get_by_id_for_scope(self, *, project_id: str) -> McpBuilderProject | None: ...

    async def add(self, project: McpBuilderProject) -> bool: ...

    async def close(self) -> None: ...


class McpBuilderDesignCheckpointRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, checkpoint_id: str) -> McpBuilderDesignCheckpoint | None: ...

    async def get_by_project(self, *, project_id: str) -> McpBuilderDesignCheckpoint | None: ...

    async def get_by_create_key(
        self, *, reviewer_id: str, idempotency_key: str
    ) -> McpBuilderDesignCheckpoint | None: ...

    async def add(self, checkpoint: McpBuilderDesignCheckpoint) -> bool: ...

    async def close(self) -> None: ...


class McpBuilderGenerationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, generation_id: str) -> McpBuilderGeneration | None: ...

    async def get_by_project(self, *, project_id: str) -> McpBuilderGeneration | None: ...

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> McpBuilderGeneration | None: ...

    async def add(self, generation: McpBuilderGeneration) -> bool: ...

    async def close(self) -> None: ...


class McpBuilderArtifactPublisher(Protocol):
    async def publish(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        files: tuple[BuilderGeneratedContent, ...],
    ) -> bool: ...

    async def read(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        inventory: tuple[BuilderGeneratedFile, ...],
        relative_path: str,
    ) -> str: ...


class McpBuilderValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, validation_id: str) -> McpBuilderValidation | None: ...

    async def get_by_project(self, *, project_id: str) -> McpBuilderValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> McpBuilderValidation | None: ...

    async def add(self, validation: McpBuilderValidation) -> bool: ...

    async def close(self) -> None: ...
