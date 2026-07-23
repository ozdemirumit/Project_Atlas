# Project Atlas

## AI Agents

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the planned AI agent model for Atlas.

## 2. Candidate Agents

- Chat orchestration agent
- Health analysis agent
- Troubleshooting agent
- Root cause analysis agent
- Change impact agent
- Recommendation agent
- Documentation retrieval agent
- Runbook agent
- MCP Builder agent
- Security review agent
- Audit explanation agent

## 3. Agent Rules

- Agents must use evidence.
- Agents must expose assumptions.
- Agents must respect RBAC and policy controls.
- Agents must not directly execute risky actions.
- Agent outputs must be auditable.
- Agent prompts and behavior should be versioned.

## 4. Agent Output Requirements

- Summary
- Evidence
- Reasoning summary
- Confidence
- Risk
- Unknowns
- Recommended next steps

## 5. Open Questions

- Which agents are required for MVP?
- Should agents be separate services or logical roles?
- How should agent evaluations be tested?
