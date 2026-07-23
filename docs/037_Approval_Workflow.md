# Project Atlas

## Approval Workflow

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas handles human approval for operational actions.

## 2. Approval Goals

- Keep humans in control of risky actions.
- Provide clear impact and rollback information before approval.
- Ensure approvers have proper authorization.
- Preserve audit evidence.
- Support ITSM and change-management alignment.

## 3. Approval Packet

Each approval request should include:

- Proposed action
- Reason
- Evidence
- Target systems
- Affected services
- Risk level
- Estimated duration
- Service interruption risk
- Preconditions
- Rollback plan
- Required role
- Related ticket or change record

## 4. Approval Outcomes

- Approved
- Rejected
- Needs more evidence
- Deferred
- Expired
- Cancelled

## 5. Open Questions

- Which actions require approval in MVP?
- Should approvals be single-step or multi-step?
- How should emergency approval be handled?
