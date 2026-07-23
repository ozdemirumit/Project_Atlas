# Project Atlas

## Database

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines database requirements for Atlas.

## 2. Data Domains

- Users and roles
- Connector registry
- Connector configurations
- Inventory entities
- Workflow state
- Health check results
- Recommendations
- Approvals
- Audit events
- Reports
- Knowledge metadata

## 3. Database Principles

- Store structured operational state.
- Protect sensitive configuration.
- Preserve audit integrity.
- Support migrations.
- Support backup and restore.
- Support enterprise retention requirements.

## 4. Candidate Stores

- Relational database for transactional state
- Graph database for infrastructure relationships
- Vector database for retrieval
- Object storage or filesystem for document assets

## 5. Open Questions

- Which relational database is first?
- Which graph database is first?
- Which migration tool should be used?
