from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastembed import TextEmbedding

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_PROFILE_ID = "fastembed.bge-small-en-v1.5"
VECTOR_DIMENSION = 384


class FastEmbedDocumentEmbedder:
    """Real local embedding via fastembed (ADR-183). No network access after the
    model is cached; see docs/adr/ADR-183 for the restricted-network follow-up.

    The model loads lazily on first use, not at construction, so constructing this
    class (e.g. during app startup) never pays the model-load cost unless a document
    is actually indexed or a query actually run.
    """

    def __init__(self, *, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None

    def _loaded_model(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(
                model_name=_MODEL_NAME,
                cache_dir=str(self._cache_dir) if self._cache_dir is not None else None,
            )
        return self._model

    def embed_passages(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        model = self._loaded_model()
        return [tuple(float(value) for value in vector) for vector in model.passage_embed(texts)]

    def embed_query(self, text: str) -> tuple[float, ...]:
        (vector,) = list(self._loaded_model().query_embed([text]))
        return tuple(float(value) for value in vector)

    @property
    def model_profile_id(self) -> str:
        return MODEL_PROFILE_ID
