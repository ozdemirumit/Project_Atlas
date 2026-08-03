# Project Atlas Agent Instructions

This file defines how AI coding agents must work in this repository. It applies to Codex, Claude Code, and any similar AI-assisted development tool.

## 1. Product Identity

Project Atlas is an enterprise-grade AI Infrastructure Operations Platform.

Atlas is a decision-support system. It helps engineers understand infrastructure, analyze problems, assess risk, and prepare recommendations. It must not act as an autonomous infrastructure operator.

## 2. Mandatory Reading Before Work

Before making changes, every agent must read:

- `README.md`
- `docs/README.md`
- `docs/001_Product_Vision.md`
- `docs/002_Product_Requirements.md`
- `docs/003_Project_Principles.md`
- `docs/060_Master_Prompt.md`
- `docs/governance/DOCUMENT_GOVERNANCE.md`
- `AGENTS.md`

When working on a specialized area, the agent must also read the relevant document under `docs/` before editing files in that area.

## 3. Immutable Principles

Agents must preserve these principles:

- AI assists. Humans decide.
- Explainability comes before intelligence.
- Enterprise requirements come first.
- Security is the default.
- The platform is vendor agnostic.
- The architecture is modular by design.
- Risky or infrastructure-changing actions require explicit human approval and policy control.
- Everything required to build, test, validate, and deploy should be reproducible from the repository.

## 4. Scope Control

Agents must keep changes limited to the assigned task.

Agents must not:

- Start implementation during documentation-only tasks.
- Add backend, frontend, MCP, agent, infrastructure, or test code unless explicitly requested.
- Introduce architectural decisions that conflict with accepted documents.
- Rewrite foundational documents unnecessarily.
- Remove user-authored content without a clear reason.
- Add secrets, credentials, IP addresses, customer names, or real infrastructure details.

## 5. Documentation Rules

Documentation must be clear enough for product owners, architects, engineers, security reviewers, and future AI agents.

Documentation changes should:

- Preserve the existing intent.
- Follow the document lifecycle, metadata, versioning, approval, and traceability rules in `docs/governance/DOCUMENT_GOVERNANCE.md`.
- Use `docs/templates/DOCUMENT_TEMPLATE.md` for new governed documents.
- Use consistent terminology.
- Prefer enterprise-grade wording.
- Identify open questions explicitly.
- Distinguish MVP scope from long-term vision.
- Capture operational risk, approval, audit, and security implications.

## 6. Engineering Rules

When implementation begins in a future phase, agents must:

- Follow the accepted architecture documents.
- Prefer simple, testable, maintainable designs.
- Use configuration instead of hard-coded environment details.
- Keep connectors, agents, workflows, policies, and knowledge sources modular.
- Include audit and observability considerations for operational behavior.
- Treat generated MCP connectors as untrusted until reviewed and tested.

## 7. Safety and Governance

Atlas must never blindly automate infrastructure operations.

Any recommendation involving operational change must include:

- Summary
- Evidence
- Confidence level
- Risk level
- Expected impact
- Estimated duration
- Service interruption risk
- Preconditions
- Required approvals
- Rollback plan
- Alternatives

Read-only diagnostics may be automated only when policy allows it. Service-impacting and destructive actions must require explicit human approval.

## 8. Commit Expectations

Commits should be small, focused, and clearly named.

Use conventional commit style when possible, for example:

- `docs: improve product vision`
- `docs: add architecture principles`
- `chore: add repository bootstrap structure`

Before committing, agents should check the working tree and verify that no unrelated files are included.

## 9. Current Repository Phase

Current phase: Approved Documentation Baseline.

All 47 planned governed documents exist at version `1.0.0` with `Approved` status. Agents may begin implementation only when explicitly requested and must treat the approved documents as binding contracts. Material architectural changes require a new governed review cycle.
