from __future__ import annotations

import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_WHITESPACE = re.compile(r"\s+")


class ParagraphBoundedChunker:
    """Real, deterministic chunker: splits on paragraph boundaries, then merges or
    splits to stay within [1, maximum_chunk_characters], never producing an empty
    or whitespace-only chunk."""

    def __init__(self, *, maximum_chunk_characters: int = 1000) -> None:
        if maximum_chunk_characters < 1:
            raise ValueError("maximum_chunk_characters must be positive")
        self._maximum_chunk_characters = maximum_chunk_characters

    def chunk(self, text: str) -> list[str]:
        paragraphs = [
            _WHITESPACE.sub(" ", paragraph).strip()
            for paragraph in _PARAGRAPH_SPLIT.split(text)
            if paragraph.strip()
        ]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > self._maximum_chunk_characters:
                if current:
                    chunks.append(current)
                    current = ""
                for start in range(0, len(paragraph), self._maximum_chunk_characters):
                    chunks.append(paragraph[start : start + self._maximum_chunk_characters])
                continue
            candidate = f"{current} {paragraph}".strip() if current else paragraph
            if len(candidate) > self._maximum_chunk_characters:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks
