# Project Atlas

## MCP Framework

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the MCP framework used by Atlas to integrate infrastructure systems.

## 2. Framework Goals

- Provide modular infrastructure integrations.
- Support vendor-specific and generic connectors.
- Expose capabilities safely and consistently.
- Allow connector installation, removal, upgrade, and configuration.
- Support testing, validation, and audit.

## 3. Connector Responsibilities

- Declare supported capabilities.
- Validate configuration.
- Authenticate securely.
- Execute read-only or approved actions.
- Return structured results.
- Emit audit and execution metadata.
- Handle errors safely.

## 4. Capability Types

- Discovery
- Inventory
- Health check
- Metrics collection
- Event retrieval
- Configuration query
- Diagnostic command
- Report data extraction
- Controlled operational action

## 5. Safety Rules

- Capabilities must be risk-classified.
- Risky actions require policy evaluation.
- Destructive actions are disabled by default.
- Credentials must be scoped by least privilege.
- Connector output must be validated before AI use.

## 6. Open Questions

- What is the first real connector candidate?
- How should connector manifests be structured?
- How should connector compatibility be tested?
