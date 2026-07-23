# Project Atlas

## Logging

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines application and operational logging requirements for Atlas.

## 2. Logging Goals

- Provide operational visibility into Atlas.
- Support troubleshooting and supportability.
- Enable correlation across components.
- Avoid leaking sensitive data.
- Support forwarding to external logging platforms.

## 3. Log Types

- Application logs
- Security logs
- Audit logs
- Connector logs
- Workflow logs
- AI orchestration logs
- System health logs

## 4. Required Fields

- Timestamp
- Severity
- Component
- Event name
- Correlation ID
- Request ID
- User context where safe
- Target context where safe
- Error details where safe

## 5. Open Questions

- Which structured log format should be used?
- What log levels are enabled by default?
- Which logs must be forwarded to Syslog or SIEM?
