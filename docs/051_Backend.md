# Project Atlas

## Backend

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines backend implementation direction for Atlas.

## 2. Backend Responsibilities

- API serving
- Authentication integration
- Authorization enforcement
- Connector orchestration
- Workflow orchestration
- AI orchestration
- Audit event generation
- Configuration management
- Reporting support

## 3. Backend Principles

- Enforce policy before risky actions.
- Keep domain logic separate from transport logic.
- Use structured errors.
- Include correlation IDs.
- Avoid hard-coded infrastructure details.
- Keep implementation testable.

## 4. Candidate Technology Direction

The initial backend may use Python and FastAPI, but this must be confirmed through an architecture decision record before implementation.

## 5. Open Questions

- Should the MVP backend be modular monolith first?
- Which async task system should be used?
- Which database access pattern should be selected?
