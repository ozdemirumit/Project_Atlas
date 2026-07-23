# Project Atlas

## Runbook Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas should use operational runbooks.

## 2. Goals

- Ingest internal runbooks.
- Retrieve relevant procedures during incidents.
- Convert runbooks into structured steps where appropriate.
- Identify prerequisites, risks, approvals, and rollback.
- Support runbook improvement from incident learning.

## 3. Runbook Metadata

- Title
- Owner
- Version
- System scope
- Vendor scope
- Risk class
- Required role
- Preconditions
- Steps
- Rollback
- Last review date

## 4. AI Usage

AI may summarize and interpret runbooks, but it must not treat ambiguous steps as approved automation.

## 5. Open Questions

- Which runbook format should be supported first?
- Should runbooks require approval before AI use?
- How should outdated runbooks be detected?
