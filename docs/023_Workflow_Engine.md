# Project Atlas

## Workflow Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas should model and execute operational workflows.

## 2. Workflow Types

- Health check workflow
- Incident investigation workflow
- Root cause analysis workflow
- Change impact analysis workflow
- Report generation workflow
- Approval workflow
- Connector validation workflow
- Knowledge ingestion workflow

## 3. Workflow Requirements

- Workflows must be versioned.
- Workflows must be auditable.
- Long-running workflows must expose status.
- Failed workflows must preserve diagnostic context.
- Risky workflow steps must require policy evaluation.
- Human approval must be supported where required.

## 4. Workflow State

Common states:

- Draft
- Scheduled
- Running
- Waiting for approval
- Completed
- Failed
- Cancelled
- Rolled back

## 5. Open Questions

- Should workflows be defined in YAML, JSON, database records, or code?
- Which workflow engine should be used in MVP?
- How should workflow retries be controlled?
