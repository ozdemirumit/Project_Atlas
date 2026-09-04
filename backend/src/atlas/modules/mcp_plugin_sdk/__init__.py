"""ATLAS-021 MCP Plugin SDK: developer-facing contracts for authoring, testing, packaging, and
validating Atlas MCP connectors.

This module models the SDK's authoring-time contract surface -- what a connector author (human or
ATLAS-022's MCP Builder) codes against -- reusing `atlas.modules.connectors.domain.models` (the
runtime registry a built connector ultimately becomes) wherever a concept already exists there
(`CapabilityManifest`, `ConnectorPackageManifest`, `ConnectorHealth`, `ConnectorValidationReport`,
`ValidationFinding`) rather than duplicating it, and adding only what the SDK itself introduces:
configuration/secret field declarations, the invocation context and safe client contracts, the
result/error taxonomy, telemetry/health/test-harness contracts, and the package/documentation/
compatibility surface.
"""
