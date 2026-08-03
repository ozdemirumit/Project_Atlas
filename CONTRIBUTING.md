# Contributing to Project Atlas

Project Atlas has an Approved Documentation Baseline. All 47 planned governed documents are at version `1.0.0` with `Approved` status. Implementation contributions require an explicit task and must conform to the approved contracts; material contract changes require a new review and approval cycle.

## Before Contributing

Read:

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- `docs/001_Product_Vision.md`
- `docs/002_Product_Requirements.md`
- `docs/003_Project_Principles.md`
- `docs/060_Master_Prompt.md`
- `docs/governance/DOCUMENT_GOVERNANCE.md`

Do not commit secrets, credentials, customer names, IP addresses, or real infrastructure details.

## Documentation Workflow

1. Confirm the document ID and filename in `docs/README.md`.
2. Create new governed documents from `docs/templates/DOCUMENT_TEMPLATE.md`.
3. Set the initial lifecycle status to `Draft` and version to `0.1.0`.
4. Identify the owner, reviewers, approver, related documents, and traceability references.
5. Keep changes focused and update the document change history.
6. When content is ready, change the status to `Review` and open a pull request.
7. Resolve review findings or record accepted exceptions.
8. Record the approver and approval date before changing status to `Approved`.
9. Use version `1.0.0` for the first approved baseline.
10. When retiring a document, mark it `Deprecated`, preserve it, and link its replacement.

The full lifecycle, versioning, approval, and traceability rules are defined in `docs/governance/DOCUMENT_GOVERNANCE.md`.

## Pull Request Expectations

Documentation pull requests should include:

- Affected document IDs
- Purpose and material changes
- Lifecycle and version changes
- Reviewers and required approver
- Open questions and accepted risks
- Related requirements, ADRs, issues, implementation, and tests
- Compatibility impact on approved downstream documents

Do not combine unrelated changes. Do not rewrite foundational documents unless the task requires it.

## Commit Style

Use focused conventional commits, for example:

```text
docs: clarify approval workflow
docs: add security architecture draft
```

Before committing, verify that no unrelated files are staged.
