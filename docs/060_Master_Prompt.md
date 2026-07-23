# Project Atlas

## Master Prompt for AI Development Tools

**Version:** 0.1 Draft  
**Status:** In Progress  
**Depends on:** `AGENTS.md`

## 1. Purpose

This document provides a reusable master prompt for AI development tools such as Codex, Work Mode, Claude Code, Cursor, and similar coding agents.

## 2. Master Prompt

```text
You are working on Project Atlas, an enterprise-grade AI Infrastructure Operations Platform.

Before making changes, read README.md, AGENTS.md, docs/README.md, docs/001_Product_Vision.md, and docs/002_Product_Requirements.md.

Atlas is a decision-support platform. AI assists, humans decide. Do not introduce behavior that allows AI to perform operationally risky infrastructure changes without explicit human approval and policy control.

Keep all changes scoped to the assigned task. Preserve enterprise requirements including security, RBAC, audit logging, explainability, policy control, approval workflows, and reproducible deployment.

Before implementation, summarize your understanding, list affected files, identify risks, and describe the validation you will perform.

Do not commit secrets, credentials, IP addresses, customer names, or real infrastructure details.
```

## 3. Usage

Use this prompt at the beginning of a new AI-assisted development session. For specific work, append the task objective, scope, expected files, validation criteria, and commit message.

## 4. Open Questions

- Should specialized prompts exist for documentation, backend, frontend, MCP, and security work?
- Should prompts be versioned together with releases?
- Should agent output be stored as project records?
