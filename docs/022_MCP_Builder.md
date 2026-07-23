# Project Atlas

## MCP Builder

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the MCP Builder capability that helps generate MCP connectors from vendor material.

## 2. Input Sources

- REST API documentation
- OpenAPI specifications
- CLI command references
- Vendor manuals
- Example scripts
- Authentication guides
- Error code references

## 3. Builder Workflow

1. Ingest vendor documentation.
2. Extract API or CLI capabilities.
3. Identify authentication model.
4. Generate connector manifest draft.
5. Generate capability definitions.
6. Generate test stubs and sample mocks.
7. Classify action risk.
8. Present output for human review.
9. Validate before production enablement.

## 4. Safety Constraints

- Generated connectors are untrusted until reviewed.
- Risk classification must be human-reviewed.
- Destructive capabilities must be disabled by default.
- Credentials must never be embedded in generated code or documentation.

## 5. Open Questions

- What documentation formats should be supported first?
- Should generated connectors require signed approval?
- How will vendor documentation version changes be detected?
