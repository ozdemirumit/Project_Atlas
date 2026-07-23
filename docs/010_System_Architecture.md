# Project Atlas

## System Architecture

**Version:** 0.1 Draft  
**Status:** In Progress  
**Depends on:** `001_Product_Vision.md`, `002_Product_Requirements.md`

## 1. Purpose

This document defines the high-level architecture of Project Atlas and the major system boundaries.

## 2. Architectural Goal

Atlas must provide a secure, modular, enterprise-ready platform that connects to infrastructure systems, builds operational context, retrieves knowledge, runs AI-assisted analysis, and presents explainable recommendations through a web interface.

## 3. Major System Areas

- Web application
- Backend API
- Authentication and authorization
- MCP connector framework
- Connector registry
- Infrastructure inventory
- Infrastructure graph
- Knowledge ingestion and retrieval
- AI agent orchestration
- Decision and policy engine
- Workflow engine
- Audit and logging
- Reporting
- Deployment and bootstrap tooling

## 4. Primary Data Flow

1. User asks a question or starts a workflow.
2. Backend validates identity, role, and requested scope.
3. Relevant connectors, graph data, historical data, and knowledge sources are selected.
4. AI agents analyze the request using retrieved evidence.
5. Decision and policy controls classify risk.
6. Atlas returns an explainable answer, recommendation, or approval-ready plan.
7. All relevant actions and decisions are audited.

## 5. Architectural Constraints

- The AI layer must not bypass policy controls.
- Connectors must expose capabilities through a controlled contract.
- Risky actions require explicit human approval.
- Evidence must be attached to operational recommendations.
- Enterprise logging and audit must be part of the core path.

## 6. Open Questions

- Should the first runtime be a modular monolith or independent services?
- Which graph database should be selected first?
- Which deployment mode should be prioritized for MVP?
