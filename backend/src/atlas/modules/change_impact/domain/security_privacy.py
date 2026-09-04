"""ATLAS-044 SS28: security and privacy.

Most of SS28's seven bullets already have a structural home elsewhere in this subsystem, noted
here rather than duplicated:

- "analysis is bounded by target and evidence permissions" and "hidden topology and business
  service names are not exposed" -- the access control `graph.domain.models.GraphEntity`/
  `GraphObservation` already carry (`allowed_principals`) constrains every entity this subsystem's
  types reference, as already documented in `data_protection_service.ServiceImpactRecord`.
- "change details and impact reports carry classification and retention" -- `result.ImpactResult`
  now carries `classification`/`retention_note`.
- "external model use follows configured data boundaries" -- a platform data-boundary
  configuration concern, not a per-object invariant this module's types can enforce; genuinely out
  of scope here, same as ATLAS-041's safety slice left "generated queries and checks are
  schema-validated and capability-limited" to the layer that actually has a schema to validate.
- "prompt injection cannot change policy, target scope, or graph authority" is already Guardrails'
  `InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT`/`can_override` -- the same reuse Runbook
  Engine, Reasoning, and Decision Engine's own security slices already established, needing no new
  code here.

What remains is given a concrete home below: secret exclusion, and generated content's
untrusted-until-validated status.
"""

from __future__ import annotations

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns


def contains_secret(text: str) -> bool:
    """SS28: "secrets and credential values are excluded." A thin, named wrapper over Guardrails'
    detector for this subsystem's own free-text fields (rationale, notes, descriptions) to check
    before they are persisted or rendered."""
    return bool(detect_secret_patterns(text))


def generated_graph_edges_simulations_and_plans_are_trusted_before_validation() -> bool:
    """SS28: "generated graph edges, simulations, and plans are treated as untrusted until
    validated." Validation itself is `validation_freshness.ValidationReport`; this is the
    structural default the report exists to overturn."""
    return False
