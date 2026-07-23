"""Embedding client — turns text into 384-dim vectors via the TEI service.

TEI's POST /embed accepts a batch (`inputs` may be a list) and returns one vector
per input. We batch to stay well within TEI's per-request limits.
"""
import httpx

from app.config import settings

_BATCH = 32


async def embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for i in range(0, len(texts), _BATCH):
            batch = texts[i : i + _BATCH]
            resp = await client.post(f"{settings.tei_url}/embed", json={"inputs": batch})
            resp.raise_for_status()
            vectors.extend(resp.json())
    return vectors


async def embed_one(text: str) -> list[float]:
    [vec] = await embed([text])
    return vec
