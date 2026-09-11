"""Add lexical (full-text) search support for document-sourced knowledge hybrid
retrieval (docs/054_VectorDB.md Sec.15, Sec.31 MVP scope).

Adds a nullable `lexical_search_vector` TSVECTOR column to the existing
`document_knowledge_vectors` table (the same governed row as the embedding,
gated by the same `classification` column -- not a new table, not a new store)
plus a GIN index for `ts_rank`/`ts_rank_cd` lexical ranking. The column is
populated server-side from `to_tsvector('english', ...)` over a governance-safe,
non-reversible token set derived at indexing time -- see
atlas.modules.knowledge.domain.document_retrieval.tokenize_for_lexical_search.
Existing rows are left NULL (backfilling would require the original chunk text,
which this migration must not touch or reconstruct); a NULL lexical_search_vector
simply does not participate in lexical ranking and remains fully searchable via
the pre-existing vector-only path.

Revision ID: 20260911_0171
Revises: 20260907_0170
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "20260911_0171"
down_revision: str | None = "20260907_0170"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: existing rows have no chunk text available to this migration to
    # derive lexemes from, and must keep working via vector-only search.
    op.add_column(
        "document_knowledge_vectors",
        sa.Column("lexical_search_vector", TSVECTOR(), nullable=True),
    )
    # CREATE INDEX ix_document_knowledge_vectors_lexical_search_vector
    #   ON document_knowledge_vectors USING GIN (lexical_search_vector)
    op.create_index(
        "ix_document_knowledge_vectors_lexical_search_vector",
        "document_knowledge_vectors",
        ["lexical_search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_knowledge_vectors_lexical_search_vector",
        table_name="document_knowledge_vectors",
    )
    op.drop_column("document_knowledge_vectors", "lexical_search_vector")
