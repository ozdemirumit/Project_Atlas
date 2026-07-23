# Project Atlas

## Microservice Architecture

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the target microservice direction while allowing the MVP to start simpler if needed.

## 2. Guiding Position

Atlas should be designed with service boundaries in mind, but the first MVP may start as a modular backend to reduce operational complexity.

## 3. Candidate Services

- Identity and access service
- Audit service
- Connector registry service
- MCP runtime service
- Inventory service
- Graph service
- Knowledge ingestion service
- Retrieval service
- Agent orchestration service
- Workflow service
- Policy service
- Reporting service

## 4. Service Boundary Rules

- Services must communicate through explicit APIs or events.
- No service should access another service database directly.
- Security and audit behavior must be consistent across services.
- Cross-service calls must include correlation IDs.
- Service contracts must be documented before implementation.

## 5. MVP Strategy

The MVP may implement these boundaries as modules first, then split into services when scaling, deployment, or ownership requires it.

## 6. Open Questions

- Which service should be extracted first?
- Which message bus or event backbone should be used?
- What is the minimum HA target for the first enterprise deployment?
