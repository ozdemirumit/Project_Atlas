# Project Atlas

## Event Architecture

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas should model and process events across infrastructure, workflows, audit, and AI analysis.

## 2. Event Types

- User action events
- Authentication events
- Authorization events
- Connector execution events
- Health check events
- Infrastructure discovery events
- Alert and incident events
- Workflow lifecycle events
- Approval events
- AI recommendation events
- Audit events
- System health events

## 3. Event Principles

- Events must include correlation IDs.
- Security-relevant events must be auditable.
- Events should be structured and machine-readable.
- Event schemas should be versioned.
- Long-running workflows must emit lifecycle events.

## 4. Event Consumers

- Audit service
- Workflow engine
- Reporting service
- Notification integrations
- AI analysis services
- SIEM integration

## 5. Open Questions

- Which event bus should be used first?
- Which event schemas are required for MVP?
- What retention policy applies to each event type?
