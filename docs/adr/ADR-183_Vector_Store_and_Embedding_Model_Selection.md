# ADR-183: Vector store and embedding model selection

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-27 |
| Decision Owner | Umit Ozdemir, acting Architecture Owner |
| Related Documents | ATLAS-003, ATLAS-013, ATLAS-015, ATLAS-027, ATLAS-053, ATLAS-054, ADR-001, ADR-054, ADR-055, ADR-056, ADR-057, ADR-058 |
| Supersedes | None |

## Context

`docs/054_VectorDB.md` (§6, §9, §34) and `docs/015_RAG_Architecture.md` (§2, §36) both approve the RAG data contracts but explicitly defer the vector-store technology and embedding-model selection to a dedicated ADR. `ADR-001` reserves this same decision: "A future service, graph, vector, workflow, or model technology requires its own ADR."

Because no ADR has made this choice, every stage of `atlas.modules.knowledge`'s RAG pipeline (`deterministic_chunking`, `embedding_generation`, `index_staging_validation`, `retrieval_index_publication`, `protected_retrieval`) is wired in `api/app.py` to a `Synthetic...` adapter in development and an `Unavailable...` adapter (fails closed) in production, exactly as ADR-054 through ADR-058 specify while this decision remains open. This ADR unblocks real implementation of those stages.

The companion project `AI-IT-OPS` (same author, same restricted-network enterprise-operations problem space) already solved local embedding for an equivalent requirement by standardizing on `fastembed` specifically to avoid an external inference service and a heavy `torch` dependency, and by adding offline-cache and corporate-TLS-proxy CA bundle support for the one-time model download. This decision follows that precedent for consistency and because the reasoning transfers directly.

## Decision

| Area | Selection |
| --- | --- |
| Vector store | PostgreSQL 18 with the `pgvector` extension (`vector` SQL type), in the same database already selected by ADR-001 |
| Vector store Python integration | `pgvector` Python package (SQLAlchemy `Vector` column type, works with the existing Psycopg 3 driver) |
| Embedding library | `fastembed` (ONNX Runtime based, no `torch` dependency, runs fully local with no network calls at inference time) |
| Initial approved embedding model | `BAAI/bge-small-en-v1.5` (fastembed's default text model) |
| Vector dimension | 384 |
| Distance metric | Cosine |
| Model registration mechanism | `OperationalKnowledgeEmbeddingPolicySnapshot` (`atlas.modules.knowledge.domain.embedding_generation`), per ADR-055 — `model_profile_id="fastembed.bge-small-en-v1.5"`, `vector_dimension=384`, `distance_metric_id="cosine"` |

`docs/054_VectorDB.md` §6's two named candidates were PostgreSQL-with-vector-extension ("operationally consolidated MVP option") or a dedicated Qdrant service. PostgreSQL + `pgvector` is selected because it requires no new deployable service, no new network boundary, and no new backup/HA story beyond the PostgreSQL instance ADR-001 already approved — consistent with `ATLAS-013`'s modular-monolith-first posture and the "MVP proves one bounded slice" principle in `ATLAS-002`.

`fastembed` is selected over `sentence-transformers` because it has no `torch` dependency (materially smaller install and attack surface), is ONNX-based (single well-defined offline artifact per model rather than an arbitrary Python model-loading path), and is the exact library already proven for this same restricted-network requirement in `AI-IT-OPS`.

## Consequences

- `backend/pyproject.toml` gains two new runtime dependencies: `pgvector` and `fastembed`.
- A new PostgreSQL migration is required to `CREATE EXTENSION IF NOT EXISTS vector` and add the vector-bearing table(s) for retrieval-index staging and publication (ADR-056, ADR-057); this does not change any existing table.
- `fastembed` downloads the `BAAI/bge-small-en-v1.5` ONNX artifact from Hugging Face on first use unless a local cache is pre-populated. This satisfies `ATLAS-054` §22 ("signed offline artifacts; no model download... over public network") only for developer and mirrored-network profiles where the one-time download is explicitly permitted; a fully offline/restricted-network production profile requires a follow-up task to pre-stage the cached model artifact through an approved internal mirror, mirroring the CA-bundle and offline-cache handling already built in `AI-IT-OPS`. This ADR does not close that follow-up; it is tracked as a known gap.
- A model or distance-metric change is a new `model_profile_id`/index version per `ATLAS-054` §15 and §9; it never mutates vectors written under the prior profile in place.
- Domain code (`atlas.modules.knowledge.domain.*`) must not import `pgvector` or `fastembed` types directly; those belong only in the new `_pgvector`/`_fastembed` adapter modules behind the existing `OperationalKnowledgeEmbedder`, `OperationalKnowledgeIndexer`, `OperationalKnowledgeRetrievalPublisher`, and `OperationalKnowledgeTrustedRetriever` ports.
- Real vector content must still never enter ordinary application persistence or audit payloads outside the new isolated vector-store boundary, per the ADR-055 through ADR-058 governance envelope this ADR does not alter.

## Rejected Alternatives

- Qdrant: rejected for the first real increment because it introduces a new deployable service, network boundary, and backup/HA surface before any real pipeline stage exists yet; the data model (`ATLAS-054` §8) is not Qdrant-specific, so revisiting this remains possible under a superseding ADR if PostgreSQL's vector performance becomes a measured bottleneck.
- `sentence-transformers`: rejected as the default due to its `torch` dependency's size, restricted-network install complexity, and lack of a single-file offline artifact model compared to `fastembed`'s ONNX approach.
- An external embedding API (e.g., a hosted OpenAI-compatible embeddings endpoint): rejected because it would route document content to a network boundary outside the deployment, conflicting with `ATLAS-003` PRN-018 (enterprise data boundaries) and `ATLAS-013`'s restricted-network requirement.

## Validation

- `uv add pgvector fastembed` resolves and locks cleanly; `uv sync --system-certs` installs both offline-capable of running without further network access after the one-time model cache.
- A new Alembic migration creating the `vector` extension and the staging/publication vector columns applies and downgrades cleanly against PostgreSQL 18, following the same upgrade/downgrade round-trip convention used by every prior migration in this repository.
- A real `fastembed`-backed `OperationalKnowledgeEmbedder` produces a 384-dimension vector for a fixed input and the same vector (bit-for-bit, since inference is deterministic for a pinned model and normalized input) on repeated runs, satisfying ADR-055's reproducibility expectation.
- A real `pgvector`-backed retrieval query returns results ordered by cosine distance and respects the mandatory pre-scoring authorization/classification filter required by `ATLAS-015` §13 and ADR-058.
