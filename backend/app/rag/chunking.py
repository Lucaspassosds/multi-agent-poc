"""Chunking — split long markdown into retrieval-sized pieces.

RecursiveCharacterTextSplitter tries the separators in order (headings → blank
lines → lines → sentences → words), so it keeps semantically-related text together
and only makes finer cuts when a piece is still too big. ~800 chars with ~100 overlap
keeps each chunk focused while preserving a little cross-boundary context.

This is a text *utility* from langchain — NOT the agent framework (per spec 00 non-goals).
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
)


def chunk_markdown(md: str) -> list[str]:
    return [c.strip() for c in _splitter.split_text(md) if c.strip()]
