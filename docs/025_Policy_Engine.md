# Project Atlas

## Policy Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas evaluates whether an operation is allowed, blocked, or requires approval.

## 2. Policy Goals

- Prevent unauthorized or unsafe operations.
- Enforce role-based permissions.
- Enforce risk classification.
- Require approvals for risky actions.
- Support enterprise governance and compliance.

## 3. Risk Classes

- Read-only
- Low-risk diagnostic
- Controlled operational
- Service-impacting
- Destructive

## 4. Policy Inputs

- User identity
- User role
- Group membership
- Requested capability
- Target system
- Connector risk metadata
- Environment
- Approval state
- Change window
- Business service impact

## 5. Policy Outputs

- Allow
- Deny
- Require approval
- Require additional evidence
- Require elevated role
- Require change record

## 6. Open Questions

- Which policy language should be used?
- How should policies be tested?
- Which default policies ship with Atlas?
