"""Embedders: Titan Text Embeddings V2 on Bedrock, and a deterministic hashing embedder for offline runs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Protocol

from ..aws import bedrock_runtime

TOKEN = re.compile(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Feature-hashed bag of words and bigrams. No network, stable across runs; used for tests."""

    name = "hash-512"

    def __init__(self, dims: int = 512):
        self.dims = dims

    def embed(self, text: str) -> list[float]:
        tokens = tokenize(text)
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        vector = [0.0] * self.dims
        for gram in grams:
            digest = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            vector[digest % self.dims] += 1.0 if digest & 1 else -1.0
        return unit(vector)


class TitanEmbedder:
    def __init__(self, model_id: str, dims: int = 512):
        self.model_id = model_id
        self.dims = dims
        self.name = f"{model_id}-{dims}"

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text[:20000], "dimensions": self.dims, "normalize": True})
        response = bedrock_runtime().invoke_model(modelId=self.model_id, body=body)
        return json.loads(response["body"].read())["embedding"]


def get_embedder(kind: str, model_id: str) -> Embedder:
    return TitanEmbedder(model_id) if kind == "bedrock" else HashEmbedder()
