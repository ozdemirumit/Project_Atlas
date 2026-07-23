# Project Atlas

## RBAC

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines role-based access control requirements for Atlas.

## 2. RBAC Goals

- Enforce least privilege.
- Separate read-only analysis from operational actions.
- Control connector access by role and scope.
- Support group-based mapping from enterprise identity providers.
- Provide auditable authorization decisions.

## 3. Candidate Roles

- Platform administrator
- Security administrator
- Infrastructure architect
- Infrastructure engineer
- Operations analyst
- Auditor
- Read-only viewer

## 4. Permission Areas

- User and role management
- Connector configuration
- Connector execution
- Knowledge source administration
- Workflow management
- Approval authority
- Report access
- Audit log access

## 5. Open Questions

- Which roles are required for MVP?
- Should permissions be resource-scoped by site, vendor, or domain?
- How should temporary elevated access be handled?
