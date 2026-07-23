# Project Atlas

## Guardrails

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines safety guardrails for AI and automation behavior in Atlas.

## 2. Mandatory Guardrails

- AI must not execute infrastructure-changing actions by default.
- Risky actions require explicit approval.
- Destructive actions are blocked unless specifically enabled by policy.
- Every recommendation must include evidence.
- Connector credentials must use least privilege.
- Audit logging cannot be disabled for sensitive actions.
- Generated MCP connectors must be reviewed before production use.
- AI confidence must not be presented as certainty.

## 3. Risk Handling

When an action may cause service impact, Atlas must show:

- Affected components
- Affected services
- Estimated interruption risk
- Estimated duration
- Preconditions
- Rollback plan
- Required approvals

## 4. Failure Behavior

When Atlas is uncertain, missing evidence, or unable to verify safety, it must pause and ask for review rather than continue.

## 5. Open Questions

- Which guardrails can be automatically tested?
- Which policy controls are mandatory in MVP?
- How should emergency overrides be governed?
