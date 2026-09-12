"""Embedding providers.

Voyage AI is used when a key is configured. Otherwise a deterministic local
hashing embedder is used so that retrieval - and therefore the whole RAG path -
works offline, in CI, and in tests with no external dependency.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer that keeps characters common in tech terms (c++, .net)."""
    return _TOKEN_RE.findall(text.lower())


class EmbeddingProvider(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        ...

    def embed_one(self, text: str, input_type: str = "document") -> list[float]:
        return self.embed([text], input_type=input_type)[0]


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashed bag-of-ngrams embedding.

    Not semantic - it captures lexical overlap only - but it is stable, free, and
    good enough to rank resume/job-description chunks by term overlap, which is
    what the retrieval step needs. Signed hashing keeps collisions from
    systematically inflating similarity.
    """

    name = "hashing"

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or settings.embedding_dim

    def _features(self, text: str) -> list[str]:
        tokens = tokenize(text)
        bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        return tokens + bigrams

    def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        counts: dict[str, int] = {}
        for feature in self._features(text):
            counts[feature] = counts.get(feature, 0) + 1

        for feature, count in counts.items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            # Sublinear term frequency damps the effect of repeated words.
            vec[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embeddings (voyage-3.5 returns 1024 dimensions by default)."""

    name = "voyage"
    _URL = "https://api.voyageai.com/v1/embeddings"
    _BATCH = 96

    def __init__(self, api_key: str, model: str, dim: int) -> None:
        self.api_key = api_key
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        vectors: list[list[float]] = []
        with httpx.Client(timeout=60.0) as client:
            for start in range(0, len(texts), self._BATCH):
                batch = texts[start : start + self._BATCH]
                response = client.post(
                    self._URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "input": batch,
                        "input_type": input_type,
                        "output_dimension": self.dim,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                # The API documents that results carry an `index`; sort defensively
                # rather than trusting response order.
                items = sorted(payload["data"], key=lambda d: d.get("index", 0))
                vectors.extend(item["embedding"] for item in items)
        return vectors


class FallbackEmbeddingProvider(EmbeddingProvider):
    """Wraps a remote provider and degrades to hashing when it errors.

    A transient Voyage outage should not make document upload fail outright; the
    document is still searchable, just lexically rather than semantically.
    """

    def __init__(self, primary: EmbeddingProvider, backup: EmbeddingProvider) -> None:
        self.primary = primary
        self.backup = backup
        self.name = primary.name
        self.dim = primary.dim

    def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        try:
            return self.primary.embed(texts, input_type=input_type)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "Embedding provider %s failed (%s); using hashing fallback",
                self.primary.name,
                exc,
            )
            self.name = self.backup.name
            return self.backup.embed(texts, input_type=input_type)


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Resolve the configured embedding provider (memoised)."""
    global _provider
    if _provider is not None:
        return _provider

    hashing = HashingEmbeddingProvider(settings.embedding_dim)
    choice = settings.embedding_provider
    if choice == "hashing":
        _provider = hashing
    elif choice in ("auto", "voyage") and settings.voyage_api_key:
        _provider = FallbackEmbeddingProvider(
            VoyageEmbeddingProvider(
                settings.voyage_api_key, settings.voyage_model, settings.embedding_dim
            ),
            hashing,
        )
    else:
        if choice == "voyage":
            logger.warning("EMBEDDING_PROVIDER=voyage but VOYAGE_API_KEY is unset")
        _provider = hashing

    logger.info("Embedding provider: %s (dim=%d)", _provider.name, _provider.dim)
    return _provider


def reset_embedding_provider() -> None:
    """Clear the memoised provider (used by tests)."""
    global _provider
    _provider = None
