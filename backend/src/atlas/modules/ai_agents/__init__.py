"""ATLAS-040 AI Agents: governed agent catalog, orchestration, and contracts.

Sits above `atlas.modules.ai` (ATLAS-014's model-invocation gateway and protected-use-case
services) -- this module governs *which logical agent role* runs, under *what contract*, not how a
model endpoint is actually invoked. `ai.domain.models.ModelEndpointProfile` and the `protected_*`
application services remain the invocation layer this module's agent definitions reference, not
duplicate.
"""
