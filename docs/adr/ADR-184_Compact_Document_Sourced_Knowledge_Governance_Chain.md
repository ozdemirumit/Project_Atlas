# ADR-184: Compact document-sourced knowledge governance chain

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-27 |
| Decision Owner | Umit Ozdemir, acting Architecture Owner |
| Related Documents | ATLAS-003, ATLAS-015, ATLAS-027, ATLAS-037, ATLAS-047, ATLAS-054, ADR-042, ADR-043, ADR-046, ADR-052, ADR-053, ADR-183 |
| Supersedes | None |

## Context

The existing `atlas.modules.knowledge` review-to-publication pipeline (ADR-042 through ADR-052) governs exactly one knowledge source type: operational evidence produced by a connector invocation (ADR-040/041). Its first record, `OperationalEvidenceKnowledgeDraftRecord` (`domain/evidence_draft.py`), hard-validates `draft_domain == "domain.operational"` and requires connector-specific fields (`connector_id`, `instance_id`, `capability_id`, `evidence_package_id`, `source_authority == "source-authority.system-generated"`). Every downstream Protocol in the chain — `OperationalKnowledgeReviewRequestSource.review_request_source()`, and ultimately `OperationalKnowledgePublicationPreparationSource.publication_preparation_source()` — is statically typed to this same `OperationalEvidenceKnowledgeDraftRecord` lineage all the way to the handoff into the RAG pipeline. This is not incidental: it is Python-level type binding, confirmed by direct inspection of `application/draft_review_request_ports.py` and `application/publication_preparation_ports.py`.

`docs/027_Knowledge_Engine.md` §4 defines eight knowledge domains (Vendor, Architecture, Runbook, Incident/Problem, Change, Operational, Connector, Generated); only "Operational" has a built implementation. A human-uploaded document (the source type this ADR addresses) belongs to the Vendor or Architecture domain and cannot honestly satisfy the Operational lineage's validation — faking connector/evidence fields for an uploaded PDF would violate `ATLAS-003` PRN-005 (evidence precedes recommendation) and PRN-011 (knowledge must be traceable) by recording a false provenance.

Separately, `atlas.modules.knowledge.application.source_materialization_ports.OperationalKnowledgeSourceMaterializer` (ADR-053, the first stage of the RAG pipeline proper) and everything downstream of it (chunking, embedding, index staging/publication, retrieval — ADR-054 through ADR-058) do **not** hard-validate a domain value anywhere in their `__post_init__` methods (confirmed by direct inspection). Only the *upstream* review-to-approval chain is Operational-specific; the RAG pipeline itself is already domain-agnostic in its data contracts, but its single existing `Source` Protocol is typed to expect `OperationalKnowledgePublicationPreparationRecord` specifically, which is the one remaining seam this ADR must generalize.

Mirroring the full eleven-stage Operational pattern (draft curation, review request, reviewer assignment, protected inspection lease, protected content presentation, review finding, finding presentation, track review decision, correction/resubmission, final resolution, publication preparation) for a second source type was considered and explicitly rejected as disproportionate for a first real increment: eleven stages exist for the operational-evidence workflow's own reasons (matching the same lease/capsule governance style used throughout this codebase's protected-runtime ADR chain), not because a human document-review workflow structurally requires eleven separate governed HTTP round-trips.

## Decision

A new, compact, four-stage governed chain for document-sourced knowledge, preserving every safety property of the Operational chain (immutable claim → trusted-boundary work → signed digest-only receipt, human review, enforced separation of duties, encrypted-at-rest content, full audit) at lower stage count:

| Stage | Purpose | Separation-of-duties requirement |
| --- | --- | --- |
| 1. Document Knowledge Draft Curation | Accepts uploaded document bytes + declared title/classification/access/retention/product-applicability metadata; a trusted materializer stores the real bytes in the new protected-content-at-rest boundary (see below) and returns a digest-only draft receipt, exactly as ADR-042's curator does for evidence. | Curator = the uploading subject. |
| 2. Document Knowledge Review and Decision | A distinct human reviewer claims the draft, is presented the real decrypted content within a bounded browser-bound lease (reusing the ADR-045/046 lease-and-present pattern), and records one or more findings plus a single `passed`/`changes-required`/`rejected` decision. | Reviewer must differ from the curator (enforced by the claim's subject digest). |
| 3. Document Knowledge Final Approval | A distinct accountable approver reviews the recorded decision and findings (via the same presentation pattern) and records `approved`/`rejected`. | Approver must differ from both curator and reviewer. |
| 4. Document Knowledge Publication Preparation | Binds the approved draft to a publication plan (chunking/embedding/index profile digests, mirroring `OperationalKnowledgePublicationPreparationRecord`'s shape) and produces a `PublicationReadyKnowledgeSource` — see below. | Preparer may be the approver or a distinct publication steward per policy; recorded either way. |

New domain/application modules: `atlas.modules.knowledge.domain.document_draft`, `.document_review_decision`, `.document_final_approval`, `.document_publication_preparation`, each following the existing digest-only dataclass pattern (stable IDs validated via `validate_stable_identifier`, all content/binding fields as SHA-256 digests, `frozen=True, slots=True`), and their `application/*_ports.py` Protocol counterparts.

**Materialization boundary generalization**: `atlas.modules.knowledge.application.source_materialization_ports.OperationalKnowledgeSourceMaterializationRecordSource` is changed from a Protocol hard-typed to return `OperationalKnowledgePublicationPreparationRecord` to one typed against a new minimal structural type, `atlas.modules.knowledge.domain.publication_ready_source.PublicationReadyKnowledgeSource` (a frozen dataclass carrying exactly the fields materialization actually consumes today: `knowledge_item_id`, `preparation_id`, `source_content_digest`, `organization_id`, `environment_id`, `classification`, `access_policy_id`, `access_policy_digest`, `retention_policy_id`, `retention_policy_digest`, `encryption_profile_id`, `encryption_profile_digest`, `chunking_profile_digest`, `steward_subject_digest`, `prepared_at`). Both the existing Operational `publication_preparation` adapter and the new Document `publication_preparation` adapter construct and return this same type from their respective repositories' `publication_preparation_source()`/equivalent method — a small adapter-side mapping in each, no change to either chain's own validated record shape. This is the only modification to any existing ADR-042–058 code; it is additive (a narrower Protocol any existing valid record can already satisfy via a thin mapping) and does not change stored data or prior behavior.

## Consequences

- Document ingestion gets its own honestly-labeled provenance (`source-authority.human-provided`, `draft_domain` values like `domain.vendor`/`domain.architecture`) rather than a misrepresented Operational lineage.
- The RAG pipeline (ADR-053–058, now to be made real per this and following tasks) serves both source types through one shared, narrower `PublicationReadyKnowledgeSource` seam — future knowledge domains (Runbook, Incident, Change, Generated) can plug into materialization the same way without a third full pipeline mirror, as long as their own governance chain produces this same structural type.
- Four new governed stages (versus the Operational chain's eleven) means less audit granularity for the human document-review workflow specifically — accepted here because the compact chain still enforces the load-bearing safety properties (distinct curator/reviewer/approver identities, encrypted-at-rest content, immutable digest-bound receipts, full `atlas.*` audit events per stage) that this repository's principles actually require (`ATLAS-003` PRN-016, PRN-017); the eleven-stage split was a stylistic choice in the Operational chain, not itself a named requirement.
- A real protected-content-at-rest boundary must be built (tracked as the first implementation task under this ADR) since none exists anywhere in this codebase today — confirmed by direct inspection of every `protected_content`/`source_materialization` adapter variant.

## Rejected Alternatives

- Mirroring all eleven Operational stages for documents: rejected as disproportionate scope for a first real increment; nothing in `ATLAS-027`'s generic knowledge-item lifecycle (`Draft → Review → Approved → Published`) requires eleven stages specifically.
- Reusing `OperationalEvidenceKnowledgeDraftRecord` directly for uploaded documents by supplying placeholder connector/evidence field values: rejected as a false-provenance violation of `ATLAS-003` PRN-005/PRN-011.
- Leaving `source_materialization`'s Source Protocol hard-typed to `OperationalKnowledgePublicationPreparationRecord` and instead building a second, entirely parallel RAG pipeline (materialization through retrieval) for documents: rejected because the RAG pipeline's own data contracts are already domain-agnostic; duplicating six more stages to work around one Protocol's return type would be pure waste.

## Validation

- Unit tests for each new stage prove: distinct-subject separation of duties is enforced (same-subject claim attempts fail closed), the digest-only invariant holds (no raw content in any `Record`/`Receipt`/`Claim` dataclass), and the protected-content-at-rest boundary round-trips real bytes correctly (write then read returns identical content, and content is not recoverable without going through the boundary's presentation/decryption path).
- An integration test constructs a `PublicationReadyKnowledgeSource` from a completed Document Knowledge Publication Preparation record and confirms the existing `source_materialization` stage accepts it unchanged.
- A parallel test confirms the existing Operational `publication_preparation` → `source_materialization` path is unaffected by the Protocol narrowing (existing Operational tests continue to pass unmodified).
