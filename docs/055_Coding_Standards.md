# Project Atlas

## Coding Standards

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines coding standards for future Atlas implementation.

## 2. General Standards

- Keep changes small and focused.
- Prefer readable code over clever code.
- Use explicit contracts and schemas.
- Validate inputs.
- Handle errors predictably.
- Avoid hard-coded customer or environment details.
- Include audit and observability where behavior is operationally relevant.

## 3. Security Standards

- Never commit secrets.
- Do not log credentials or sensitive tokens.
- Use least privilege.
- Validate external input.
- Treat connector and AI-generated output as untrusted until validated.

## 4. Documentation Standards

- Update relevant documentation when behavior changes.
- Document architecture decisions through ADRs when choices are significant.
- Keep public examples generic and sanitized.

## 5. Open Questions

- Which linters and formatters are required?
- Which branch and PR rules should be enforced?
- Which languages are officially supported in MVP?
