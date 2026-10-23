"""Evidence index over the bidder's capability library: BM25 + embeddings, fused with reciprocal rank.

About 40 pages of documents fit comfortably in Lambda memory, so the whole index is one JSON file in S3
and search runs in-process at zero idle cost. Category filters come from the ontology's taxonomy.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..ontology.models import Category, Evidence
from .embeddings import Embedder, HashEmbedder, tokenize

STOPWORDS = set(
    "a an and are as at be by for from has have in is it its of on or our the their this to was we will with "
    "all any can do does each per such that these those which who".split()
)
RRF_K = 60


def _terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS]


def load_library(library_dir: Path) -> list[Evidence]:
    """Split each Markdown document into chunks at its '## ' headings."""
    chunks: list[Evidence] = []
    for path in sorted(library_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not match:
            continue
        meta, body = yaml.safe_load(match.group(1)), match.group(2)
        categories = [Category(c) for c in meta.get("categories", [])]
        parts = re.split(r"^## ", body, flags=re.M)
        intro, sections = parts[0], parts[1:]
        title = meta["title"]
        for n, part in enumerate(sections, start=1):
            heading, _, text = part.partition("\n")
            text = re.sub(r"^> .*$", "", text, flags=re.M).strip()
            chunks.append(
                Evidence(
                    id=f"{meta['id']}#{n}",
                    doc_id=meta["id"],
                    doc_title=title,
                    section=heading.strip(),
                    text=text,
                    categories=categories,
                )
            )
        if not sections:
            chunks.append(
                Evidence(
                    id=f"{meta['id']}#0",
                    doc_id=meta["id"],
                    doc_title=title,
                    section=title,
                    text=intro.strip(),
                    categories=categories,
                )
            )
    return chunks


@dataclass
class EvidenceIndex:
    chunks: list[Evidence]
    vectors: list[list[float]]
    embedder_name: str
    _df: Counter = field(default_factory=Counter, init=False, repr=False)
    _lengths: list[int] = field(default_factory=list, init=False, repr=False)
    _tfs: list[Counter] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        for chunk in self.chunks:
            terms = _terms(f"{chunk.doc_title} {chunk.section} {chunk.text}")
            tf = Counter(terms)
            self._tfs.append(tf)
            self._lengths.append(len(terms))
            self._df.update(tf.keys())
        self._avg = sum(self._lengths) / max(len(self._lengths), 1)

    def get(self, evidence_id: str) -> Evidence | None:
        return next((c for c in self.chunks if c.id == evidence_id), None)

    def _bm25(self, query: str, k1: float = 1.4, b: float = 0.75) -> list[float]:
        n = len(self.chunks)
        q = _terms(query)
        scores = []
        for tf, length in zip(self._tfs, self._lengths, strict=True):
            score = 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * length / self._avg))
            scores.append(score)
        return scores

    def search(
        self,
        query: str,
        embedder: Embedder,
        categories: list[Category] | None = None,
        k: int = 5,
    ) -> list[Evidence]:
        """Hybrid search; chunks tagged with a requested category get a rank boost, never a hard filter."""
        bm25 = self._bm25(query)
        qv = embedder.embed(query)
        cosine = [sum(a * b for a, b in zip(qv, v, strict=True)) for v in self.vectors]
        rank_bm25 = {i: r for r, i in enumerate(sorted(range(len(bm25)), key=lambda i: -bm25[i]))}
        rank_vec = {i: r for r, i in enumerate(sorted(range(len(cosine)), key=lambda i: -cosine[i]))}
        wanted = set(categories or [])
        fused = []
        for i, chunk in enumerate(self.chunks):
            score = 1 / (RRF_K + rank_bm25[i]) + 1 / (RRF_K + rank_vec[i])
            if wanted and wanted.intersection(chunk.categories):
                score += 1 / (RRF_K + 5)
            if bm25[i] == 0 and cosine[i] <= 0:
                continue
            fused.append((score, i))
        fused.sort(reverse=True)
        return [self.chunks[i].model_copy(update={"score": round(s, 5)}) for s, i in fused[:k]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "embedder": self.embedder_name,
                "chunks": [c.model_dump(mode="json") for c in self.chunks],
                "vectors": [[round(x, 6) for x in v] for v in self.vectors],
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> EvidenceIndex:
        data = json.loads(raw)
        return cls(
            chunks=[Evidence.model_validate(c) for c in data["chunks"]],
            vectors=data["vectors"],
            embedder_name=data["embedder"],
        )


def build_index(library_dir: Path, embedder: Embedder | None = None) -> EvidenceIndex:
    embedder = embedder or HashEmbedder()
    chunks = load_library(library_dir)
    vectors = [embedder.embed(f"{c.doc_title}. {c.section}. {c.text}") for c in chunks]
    return EvidenceIndex(chunks=chunks, vectors=vectors, embedder_name=embedder.name)
