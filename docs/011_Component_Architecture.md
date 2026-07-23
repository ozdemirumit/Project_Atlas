# Project Atlas

## Component Architecture

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the initial component model for Atlas.

## 2. Core Components

- Web UI
- API gateway or backend API
- Identity service
- RBAC service
- Audit service
- Connector registry
- MCP runtime
- Inventory service
- Graph service
- Knowledge service
- Vector retrieval service
- Agent orchestration service
- Workflow service
- Decision engine
- Policy engine
- Reporting service
- Notification and integration service

## 3. Component Principles

- Components must have clear ownership and boundaries.
- Shared contracts must be versioned.
- Security-sensitive components must emit audit events.
- Long-running workflows must be observable and resumable.
- Connector failures must not compromise the platform.

## 4. Initial Integration Boundaries

- UI communicates with backend APIs only.
- Backend controls access to connectors and knowledge sources.
- AI agents request capabilities through controlled services.
- Policy engine evaluates action risk before execution or approval.
- Audit service receives events from all sensitive paths.

## 5. Open Questions

- Which components should be separate services in MVP?
- Which components can start as modules in a single backend process?
- Which contracts require formal schema definitions first?
