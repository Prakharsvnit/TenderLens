"""Turn an RFP PDF into page-aware sections, so every requirement and citation keeps its page number."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pdfplumber

from ..ontology.models import RFP, Buyer, Section

_HEADING = re.compile(r"^(?:[A-Z]\.|\d+\.)?\s*[A-Z][A-Z0-9 ,&/()'’\-–:]{5,80}$")
_FOOTER = re.compile(r"^Page \|? ?\d+ of \d+.*$", re.IGNORECASE)


def normalize(text: str) -> str:
    """Whitespace-, quote- and case-insensitive form used to match quotes against the source."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"-\s*\n\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _heading_for(lines: list[str], fallback: str) -> str:
    for line in lines[:12]:
        stripped = line.strip()
        if _HEADING.match(stripped) and not _FOOTER.match(stripped):
            return stripped.title() if stripped.isupper() else stripped
    return fallback


def parse_pdf(source: str | Path | bytes, rfp_id: str | None = None) -> RFP:
    """Parse a text-based PDF into an RFP with one section per page.

    Pages are the unit of citation, so each section is a page with the first heading found on it.
    """
    stream = io.BytesIO(source) if isinstance(source, bytes) else source
    sections: list[Section] = []
    with pdfplumber.open(stream) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = [ln for ln in text.splitlines() if ln.strip() and not _FOOTER.match(ln.strip())]
            body = "\n".join(lines)
            sections.append(
                Section(
                    id=f"P{number:02d}",
                    heading=_heading_for(lines, f"Page {number}"),
                    page_start=number,
                    page_end=number,
                    text=body,
                )
            )
    first_lines = [ln for s in sections[:1] for ln in s.text.splitlines()[:8]]
    buyer = first_lines[0].strip() if first_lines else "Unknown buyer"
    title = next(
        (ln.strip() for ln in first_lines if "request for proposal" in ln.lower() or "rfp" in ln.lower()),
        first_lines[1].strip() if len(first_lines) > 1 else "RFP",
    )
    if rfp_id is None:
        rfp_id = Path(source).stem if isinstance(source, (str, Path)) else "upload"
    return RFP(
        id=rfp_id,
        title=title,
        buyer=Buyer(name=buyer),
        page_count=max(len(sections), 1),
        sections=sections,
    )
