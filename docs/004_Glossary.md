# Project Atlas

## Glossary

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This glossary standardizes product, infrastructure, AI, and governance terminology used across Project Atlas documentation.

## 2. Terms

**Agent**  
An AI-controlled logical worker responsible for a specific task such as troubleshooting, recommendation, documentation retrieval, or change impact analysis.

**Approval Workflow**  
A controlled process where a user or authorized role approves a proposed action before execution.

**Audit Log**  
A tamper-resistant record of security-relevant and operationally relevant activity.

**Connector**  
A modular integration component that allows Atlas to communicate with an infrastructure system, API, CLI, or platform.

**Digital Twin**  
A modeled representation of infrastructure state used to reason about impact and risk before real-world changes occur.

**Evidence**  
The observable data, retrieved documents, logs, events, metrics, or topology relationships supporting an AI conclusion.

**Health Check**  
A scheduled or on-demand assessment of infrastructure condition using connector capabilities and policy-defined checks.

**Infrastructure Graph**  
A relationship model showing how infrastructure components depend on each other.

**MCP**  
Model Context Protocol. In Atlas, MCP is the integration model used to expose infrastructure capabilities safely and modularly.

**MCP Builder**  
A capability that helps generate MCP connectors from vendor API documentation, CLI references, examples, and schemas.

**Policy Engine**  
The component that evaluates whether an action is allowed, requires approval, or must be blocked.

**RAG**  
Retrieval-Augmented Generation. A pattern where the AI retrieves trusted documents and context before generating an answer.

**Recommendation**  
An AI-generated proposed action or plan that includes evidence, risk, impact, duration, approvals, and rollback guidance.

**Runbook**  
A documented operational procedure for diagnosis, maintenance, incident handling, or change execution.

## 3. Open Questions

- Which internal enterprise terms should be added later?
- Should vendor-specific terms be stored here or in vendor-specific knowledge packs?
