# Project Atlas

## MCP Plugin SDK

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the planned SDK for building Atlas MCP connectors.

## 2. SDK Goals

- Make connector development consistent.
- Reduce repeated boilerplate.
- Enforce security and audit requirements.
- Support automated tests and validation.
- Support generated and manually written connectors.

## 3. Expected SDK Features

- Connector manifest schema
- Configuration schema
- Credential handling contract
- Capability declaration
- Risk classification metadata
- Structured result model
- Error model
- Test harness
- Mock infrastructure support
- Documentation generator

## 4. Connector Lifecycle

1. Create connector manifest.
2. Define configuration and credentials.
3. Declare capabilities.
4. Implement capability handlers.
5. Add tests and mock responses.
6. Run validation.
7. Submit for review.
8. Approve for environment use.

## 5. Open Questions

- Should SDK be Python-first?
- How should CLI-based connectors be isolated?
- How will SDK version compatibility be enforced?
