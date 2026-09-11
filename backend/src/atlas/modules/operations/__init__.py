"""Operation resources for long-running work (docs/050_API.md SS15/SS19/SS20).

A request whose work is expected to outlive the HTTP transaction returns `202` with a real
"operation resource" the caller can poll and, where eligible, explicitly cancel -- instead of
either blocking the request indefinitely or silently discarding the work's outcome. This module
is deliberately generic: it has no opinion about *what* kind of work an operation represents, only
about the resource's own identity, state machine, and lifecycle.

This codebase has no background-task execution infrastructure (no scheduler, no
`asyncio.create_task` convention, no cron) -- see `atlas.api.routes.document_knowledge`'s
`index-operations` route for the one real consumer, which uses FastAPI's own `BackgroundTasks`
dependency (a standard, dependency-free, already-part-of-the-framework "do this after the response
is sent" mechanism) rather than inventing a scheduler.
"""

from __future__ import annotations
