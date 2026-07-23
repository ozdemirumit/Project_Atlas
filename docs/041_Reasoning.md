# Project Atlas

## Reasoning

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas should structure AI-assisted reasoning without presenting AI output as unquestionable truth.

## 2. Reasoning Principles

- Reasoning must be evidence-grounded.
- Outputs must separate facts, assumptions, and hypotheses.
- Confidence must be expressed carefully.
- Unknowns must be visible.
- Alternative explanations should be listed for complex problems.
- Policy decisions must not depend only on LLM judgment.

## 3. Reasoning Inputs

- Connector data
- Graph relationships
- Health check results
- Historical incidents
- Retrieved documents
- User-provided context
- Current policy context

## 4. Reasoning Outputs

- Problem summary
- Observed symptoms
- Relevant evidence
- Hypotheses
- Confidence score
- Recommended checks
- Recommended actions
- Risks and impact

## 5. Open Questions

- How should confidence be calibrated?
- Which evaluations are required before production use?
- How should low-confidence answers be handled?
