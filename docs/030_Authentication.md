# Project Atlas

## Authentication

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines identity and authentication requirements for Atlas.

## 2. Authentication Goals

- Support enterprise identity systems.
- Provide secure local bootstrap administration.
- Support LDAP and Active Directory integration.
- Keep the architecture SSO-ready.
- Ensure sessions are secure and auditable.

## 3. Required Capabilities

- Local administrator bootstrap
- LDAP authentication
- Active Directory integration
- Group mapping
- Session management
- Password policy alignment where applicable
- SSO-ready abstraction
- Authentication audit events

## 4. Security Requirements

- No plaintext credential storage.
- Authentication failures must be logged safely.
- Sensitive logs must not expose passwords or tokens.
- Session lifecycle must be controlled.
- Identity provider outages must fail safely.

## 5. Open Questions

- Should LDAP or Active Directory be first?
- Which SSO protocol should be prioritized?
- How should break-glass access be handled?
