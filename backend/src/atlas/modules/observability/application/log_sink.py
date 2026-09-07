"""ATLAS-033: the structured logging sink port, completing the ATLAS-033 domain model.

Mirrors `atlas.core.audit.AuditSink`/`LoggingAuditSink` exactly -- a `Protocol` a caller emits
through, plus one concrete adapter onto the stdlib `logging` module. `_LEVEL_TO_STDLIB` maps
`LogLevel` (SS9) onto stdlib's numeric levels; `TRACE` has no stdlib equivalent, so it uses the
conventional custom level `5`, below `DEBUG`'s `10`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Protocol

from atlas.core.structured_logging import LogLevel, StructuredLogRecord

_LEVEL_TO_STDLIB: dict[LogLevel, int] = {
    LogLevel.TRACE: 5,
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARN: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}


class StructuredLogSink(Protocol):
    async def emit(self, record: StructuredLogRecord) -> None: ...


class StandardLoggingSink:
    """Adapts a stdlib `logging.Logger` into a `StructuredLogSink`."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def emit(self, record: StructuredLogRecord) -> None:
        self._logger.log(
            _LEVEL_TO_STDLIB[record.identity.level],
            record.identity.message,
            extra={"atlas_log": asdict(record)},
        )
