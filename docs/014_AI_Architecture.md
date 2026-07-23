# Project Atlas

## AI Architecture

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how AI is used inside Atlas and how AI behavior is constrained.

## 2. AI Role

AI in Atlas is an advisory layer. It assists with analysis, correlation, summarization, reasoning, recommendation, documentation retrieval, and planning.

AI must not bypass authorization, policy, workflow, or approval controls.

## 3. AI Capabilities

- Chat-based infrastructure query
- Evidence-grounded answer generation
- Root cause analysis support
- Change impact analysis support
- Recommendation generation
- Runbook interpretation
- Vendor documentation retrieval
- Health check interpretation
- Report drafting
- MCP connector generation assistance

## 4. Model Strategy

Atlas should support OpenAI-compatible model endpoints through configuration. The architecture must allow local LLM usage and future model provider changes.

## 5. Guardrails

- Require retrieved evidence for operational conclusions.
- Show uncertainty and assumptions.
- Do not present confidence as certainty.
- Classify operational risk before suggesting actions.
- Require approval for risky actions.
- Keep AI outputs auditable.

## 6. Open Questions

- Which model endpoint will be used in the first development environment?
- Which tasks require smaller specialized models versus a general model?
- How should prompts and agent policies be versioned?
