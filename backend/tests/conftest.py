import os
from pathlib import Path

import pytest

os.environ.setdefault("TL_LLM_MODE", "stub")
os.environ.setdefault("TL_EMBEDDER", "hash")

REPO = Path(__file__).resolve().parents[2]
BELLE_ISLE = REPO / "data" / "rfps" / "belle-isle-rfp-2026-04.pdf"


@pytest.fixture(scope="session")
def belle_isle_pdf() -> Path:
    if not BELLE_ISLE.exists():
        pytest.skip("run scripts/fetch_rfps.py to download the demo RFPs")
    return BELLE_ISLE


@pytest.fixture(scope="session")
def library_dir() -> Path:
    return REPO / "data" / "library"
