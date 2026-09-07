"""ATLAS-033 Logging: the logging pipeline layer.

`atlas.core.structured_logging` holds the pure record schema (SS4/SS6/SS7/SS8/SS9) with no
dependency on `atlas.modules.*` -- the same foundation-layer placement as `atlas.core.audit`. This
module holds everything else the doc specifies that legitimately depends on another module
(principally Guardrails' secret detector for SS11/SS12's content and redaction rules): content
rules, redaction, per-source logging requirements, the collection/routing/sampling/retention
pipeline, support bundles, failure behavior, and observability-of-logging.
"""
