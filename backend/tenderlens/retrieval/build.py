"""Build the evidence index file: python -m tenderlens.retrieval.build [--embedder hash|bedrock]."""

from __future__ import annotations

import argparse

from ..config import get_settings
from .embeddings import get_embedder
from .index import build_index


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedder", default=settings.embedder, choices=["hash", "bedrock"])
    parser.add_argument("--out", default=str(settings.index_path))
    args = parser.parse_args()
    index = build_index(settings.library_dir, get_embedder(args.embedder, settings.embed_model))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(index.to_json())
    print(f"indexed {len(index.chunks)} chunks with {index.embedder_name} -> {args.out}")


if __name__ == "__main__":
    main()
