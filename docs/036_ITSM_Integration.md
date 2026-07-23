# Project Atlas

## ITSM Integration

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines ITSM integration requirements for Atlas.

## 2. Goals

- Connect Atlas analysis to incident, problem, and change processes.
- Allow recommendations to reference tickets and change records.
- Support approval workflows tied to enterprise change management.
- Preserve evidence for audit and post-incident review.

## 3. Candidate Capabilities

- Create incident summary
- Attach evidence to incident
- Link recommendation to change request
- Read change window metadata
- Retrieve incident history
- Retrieve problem records
- Update ticket with analysis summary
- Export change impact report

## 4. Safety Requirements

- Ticket updates must be auditable.
- AI-generated ticket content must be labeled.
- Sensitive evidence must respect permissions.
- ITSM actions must follow policy and role controls.

## 5. Open Questions

- Which ITSM platform should be targeted first?
- Should ticket creation be MVP scope?
- How should approval status be synchronized?
