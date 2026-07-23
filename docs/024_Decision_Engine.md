# Project Atlas

## Decision Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the decision engine that evaluates findings, recommendations, confidence, and operational context.

## 2. Responsibilities

- Normalize findings from agents and connectors.
- Evaluate evidence strength.
- Assign confidence levels.
- Identify unknowns and assumptions.
- Compare alternative explanations.
- Prepare recommendation candidates.
- Request policy evaluation for action proposals.

## 3. Decision Inputs

- Connector results
- Health check results
- Logs and events
- Infrastructure graph relationships
- Retrieved knowledge
- Historical incidents
- User context
- Policy context

## 4. Decision Output

Decision outputs must include:

- Summary
- Evidence
- Reasoning summary
- Confidence
- Risk
- Impact
- Recommended next steps
- Alternatives
- Unknowns

## 5. Open Questions

- How should confidence be scored?
- Which decisions require deterministic rules instead of LLM reasoning?
- How should conflicting evidence be presented?
