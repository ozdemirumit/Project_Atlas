"""ATLAS-059 Release Process: versioning, release lifecycle, evidence, approval, publication,
rollout, support, deprecation, and retirement.

Distinct bounded context from `atlas.modules.platform.domain.release_preflight` (ATLAS-038): that
module verifies one already-downloaded artifact set is safe to install/upgrade on one host at
deployment time. This module governs the release *itself* -- how a version is defined, evaluated,
approved, published, and supported across its lifecycle -- upstream of any single deployment.
"""
