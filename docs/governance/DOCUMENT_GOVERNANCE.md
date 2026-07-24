# Project Atlas Documentation Governance

## 1. Purpose

This standard defines how Project Atlas documents are identified, authored, reviewed, approved, versioned, traced, and retired. It applies to product, architecture, security, AI, operations, and development documentation under `docs/`.

Documentation is part of the product contract. An implementation decision is not accepted merely because it appears in code or discussion; it must be reflected in the appropriate governed document and, when necessary, an Architecture Decision Record (ADR).

## 2. Document Identification and Filenames

Every governed document has a permanent identifier in the form:

```text
ATLAS-NNN
```

- `NNN` is the existing three-digit document number.
- Existing filenames remain unchanged. For example, `001_Product_Vision.md` has document ID `ATLAS-001`.
- A document ID is never reused, even after a document is deprecated.
- Renaming an existing numbered file requires reviewer approval and correction of all inbound references.
- New documents must reserve an unused number in `docs/README.md` before or as part of their creation.
- Supporting files that are not product contracts, such as directory indexes and templates, do not require an `ATLAS-NNN` identifier.

The canonical filename format is:

```text
NNN_Descriptive_Title.md
```

## 3. Required Document Metadata

Every governed document must include the following metadata immediately after its title:

```markdown
| Field | Value |
| --- | --- |
| Document ID | ATLAS-NNN |
| Version | 0.1.0 |
| Status | Draft |
| Document Owner | Role or named owner |
| Reviewers | Roles or names, or `TBD` |
| Approver | Role or name, or `TBD` |
| Approval Date | YYYY-MM-DD or `Not approved` |
| Last Updated | YYYY-MM-DD |
| Related Documents | Linked IDs or `None` |
| Supersedes | Document ID/version or `None` |
```

Owners maintain document accuracy. Reviewers assess technical and cross-functional quality. Approvers authorize the document as an implementation contract. The author must not record approval without evidence from the designated approver.

Existing documents may adopt this metadata incrementally when they are next materially revised. Until migrated, their current headers remain valid and their lifecycle status is interpreted as `Draft`.

## 4. Document Lifecycle

### Draft

The document is being authored or materially revised.

- Content may contain open questions.
- It is not an implementation contract.
- The owner may update it without formal approval.
- New documents start in this state.

### Review

The document is complete enough for structured stakeholder review.

- Scope, assumptions, risks, and unresolved decisions must be explicit.
- Required reviewers must be named.
- Review feedback must be resolved or recorded as an accepted exception.
- Material edits return the document to `Draft` or restart review.

### Approved

The designated approver has accepted the document.

- The approval date and approver must be recorded.
- The document becomes a binding reference for downstream architecture and implementation.
- Material changes require a new version and a new review cycle.
- Editorial corrections that do not change meaning may use a patch version without repeating approval, but must retain the existing approval record and be described in history.

### Deprecated

The document is no longer authoritative.

- It remains in the repository for history and traceability.
- The metadata must identify the replacement document when one exists.
- Links should point readers to the replacement.
- Deprecated document IDs and numbers must not be reused.

The normal lifecycle is:

```text
Draft -> Review -> Approved -> Deprecated
  ^        |
  +--------+
```

## 5. Review and Approval

The document owner opens or updates the document and identifies reviewers appropriate to its scope.

Minimum review expectations:

- Product requirements: Product Owner and Architecture Owner
- Architecture: Architecture Owner plus affected domain and security reviewers
- Security and governance: Security reviewer plus Architecture Owner
- Operations and deployment: Operations reviewer plus Security reviewer
- AI behavior and guardrails: AI Architecture, Security, and affected domain reviewers

Review is performed through a pull request whenever possible. The pull request must:

- Identify affected document IDs.
- Summarize the purpose and material changes.
- List unresolved questions and risks.
- State whether the change is breaking for approved downstream decisions.
- Identify related requirements, ADRs, implementation items, and tests when applicable.

Approval is recorded only after required feedback is resolved. Repository merge permission does not by itself confer document approval authority.

## 6. Versioning Policy

Governed documents use semantic versions: `MAJOR.MINOR.PATCH`.

- `MAJOR`: incompatible change to approved scope, principles, requirements, interfaces, or decisions
- `MINOR`: material backward-compatible addition or clarification
- `PATCH`: editorial correction with no change in meaning

Examples:

- `0.1.0`: initial draft
- `0.2.0`: substantial draft revision
- `1.0.0`: first approved baseline
- `1.1.0`: approved backward-compatible extension
- `2.0.0`: approved breaking revision

Versions below `1.0.0` are pre-approval drafts. Moving to `1.0.0` requires formal approval. Every material change must update `Last Updated` and add an entry to the document's change history.

Recommended change history:

```markdown
## Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | YYYY-MM-DD | Owner | Initial draft |
```

Git history supports, but does not replace, document version metadata.

## 7. Traceability

Project Atlas maintains bidirectional traceability where applicable:

```text
Vision -> Requirement -> Architecture -> ADR -> Implementation -> Test -> Operations
```

References must use stable identifiers rather than titles alone:

- Documents: `ATLAS-NNN`
- Functional requirements: `FR-NNN`
- Non-functional requirements: `NFR-NNN`
- Architecture decisions: `ADR-NNN`
- Issues or work items: repository issue number
- Tests: stable test ID or test path

A downstream artifact must reference its governing upstream requirement or decision. When an approved upstream document changes, its owner must identify and review affected downstream artifacts. Broken, ambiguous, or obsolete links must be corrected as part of the same change or tracked explicitly.

Traceability may initially be maintained in document sections and pull requests. A dedicated requirements traceability matrix may be introduced when stable requirement IDs are available.

## 8. Document Quality Requirements

Before entering `Review`, a document must:

- Use Project Atlas terminology consistently.
- Separate current scope, MVP scope, and future scope.
- State assumptions, dependencies, risks, and open questions.
- Address security, audit, approval, and operational impact where relevant.
- Link related documents with relative repository links.
- Avoid secrets, credentials, customer data, and real infrastructure details.
- Contain no unresolved placeholder text except explicitly listed open items.
- Follow the template in `docs/templates/DOCUMENT_TEMPLATE.md`.

## 9. Governance Changes

Changes to this standard require review by the Product Owner and Architecture Owner. Changes affecting security, compliance, or approval rules also require a security reviewer.
