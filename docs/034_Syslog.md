# Project Atlas

## Syslog

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines Syslog forwarding requirements for Atlas.

## 2. Goals

- Forward security and audit events to enterprise logging systems.
- Support common Syslog deployment patterns.
- Preserve structured context where possible.
- Avoid exposing sensitive data in forwarded logs.

## 3. Required Capabilities

- Syslog server configuration
- Protocol and port configuration
- Facility and severity mapping
- Message formatting
- Connectivity validation
- Retry and failure handling
- Filtering by event type

## 4. Event Categories

- Authentication events
- Authorization events
- Audit events
- Policy changes
- Connector execution events
- Approval decisions
- System health events

## 5. Open Questions

- Should RFC 5424 be required?
- Should TLS Syslog be supported in MVP?
- How should forwarding failures be surfaced?
