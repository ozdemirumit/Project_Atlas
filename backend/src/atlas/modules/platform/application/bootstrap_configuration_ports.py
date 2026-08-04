from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingReceipt,
)


class ConfigurationRenderingError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EffectiveConfigurationPublisher(Protocol):
    async def cleanup_attempt(self, execution_id: str) -> None: ...

    async def publish(
        self,
        *,
        execution_id: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        release_id: str,
        configuration_digest: str,
        content: bytes,
    ) -> ConfigurationRenderingReceipt: ...
