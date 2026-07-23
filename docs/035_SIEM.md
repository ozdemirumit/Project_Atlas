# Project Atlas

## SIEM Integration

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines integration requirements for enterprise SIEM platforms.

## 2. SIEM Goals

- Make Atlas security and operational events visible to security teams.
- Support compliance monitoring.
- Enable correlation with enterprise infrastructure events.
- Preserve useful context without leaking sensitive data.

## 3. Integration Patterns

- Syslog forwarding
- Structured log export
- API-based export
- File-based export for restricted environments
- Future vendor-specific SIEM connectors

## 4. Event Types

- Authentication and authorization
- Administrative changes
- Policy changes
- Approval decisions
- Connector execution
- Risky recommendation generation
- Failed safety checks
- System health changes

## 5. Open Questions

- Which SIEM platform should be validated first?
- Which event schema should be used?
- Should MITRE or other classification metadata be added later?
