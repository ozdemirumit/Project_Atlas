# Project Atlas

## Testing Strategy

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines testing expectations for Atlas.

## 2. Test Areas

- Unit tests
- Integration tests
- API contract tests
- Connector tests
- Policy tests
- Workflow tests
- RAG retrieval tests
- AI output evaluation
- Security tests
- Audit tests
- Deployment validation tests

## 3. Testing Principles

- Risky behavior requires stronger tests.
- Policy and approval behavior must be deterministic.
- Connector tests must support mock infrastructure.
- AI outputs must be evaluated for evidence, uncertainty, and safety.
- Documentation-only changes should still pass formatting checks when available.

## 4. MVP Testing Scope

- Repository quality checks
- API contract tests when APIs exist
- Mock connector tests
- Policy guardrail tests
- Basic AI response format evaluation

## 5. Open Questions

- Which test framework should be selected first?
- How should AI evaluations be automated?
- Which tests run in restricted environments?
