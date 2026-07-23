# Project Atlas

## Audit

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines audit requirements for Atlas.

## 2. Audit Goals

- Record security-relevant activity.
- Record operationally relevant activity.
- Support compliance review.
- Support investigation of AI recommendations and user actions.
- Export audit data to enterprise systems.

## 3. Mandatory Audit Events

- Login success and failure
- Authorization decisions
- Connector configuration changes
- Connector capability execution
- Health check execution
- AI recommendation generation
- Approval decisions
- Policy changes
- Knowledge source changes
- Audit export actions

## 4. Audit Event Fields

- Event ID
- Timestamp
- User
- Role
- Session metadata
- Source address when available
- Action
- Target
- Connector
- Parameters summary
- Result
- Approval state
- Correlation ID

## 5. Open Questions

- Which audit store should be used first?
- What retention policy is required?
- How will tamper resistance be implemented?
