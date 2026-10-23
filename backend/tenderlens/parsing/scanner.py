"""Rule-based shall/must scanner: a recall safety net under the RFP Analyst agent.

It finds sentences that impose an obligation on the bidder. Any hit that no extracted requirement
covers becomes a "possible miss" for the bid manager to review at the confirm checkpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..ontology.models import Section

_MODAL = re.compile(
    r"\b(shall|must|is required|are required|will be required|mandatory|required to|will be expected to)\b",
    re.IGNORECASE,
)
_BIDDER = re.compile(
    r"\b(contractor|vendor|proposer|respondent|bidder|firm|company|consultant|proposals?|bids?|submittals?|"
    r"each submission|attendance)\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9•(])|\n(?=[•\-]|\d+\.|[A-Z]\.)")


@dataclass(frozen=True)
class ScanHit:
    page: int
    section_id: str
    sentence: str
    modal: str


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"-\s*\n\s*", "-", text)
    parts = _SPLIT.split(flat)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p and len(p.strip()) > 20]


def scan_modal_verbs(sections: list[Section]) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for section in sections:
        for sentence in _sentences(section.text):
            modal = _MODAL.search(sentence)
            if modal and _BIDDER.search(sentence):
                hits.append(ScanHit(section.page_start, section.id, sentence, modal.group(1).lower()))
    return hits
