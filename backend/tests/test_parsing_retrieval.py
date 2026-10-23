from tenderlens.ontology.models import Category
from tenderlens.parsing import normalize, parse_pdf, scan_modal_verbs
from tenderlens.retrieval import EvidenceIndex, build_index, load_library
from tenderlens.retrieval.embeddings import HashEmbedder


def test_parse_belle_isle(belle_isle_pdf):
    rfp = parse_pdf(belle_isle_pdf)
    assert rfp.page_count == 26
    assert rfp.buyer.name == "City of Belle Isle"
    assert all(s.page_start == int(s.id[1:]) for s in rfp.sections)
    full = normalize(" ".join(s.text for s in rfp.sections))
    assert "attendance at the walk-through is mandatory to qualify to bid" in full
    assert "page | 3 of 26" not in full  # footers removed


def test_scanner_finds_obligations(belle_isle_pdf):
    hits = scan_modal_verbs(parse_pdf(belle_isle_pdf).sections)
    text = " ".join(normalize(h.sentence) for h in hits)
    assert "walk-through is mandatory" in text
    assert "cyber liability and network security insurance" in text
    assert len(hits) > 40


def test_library_chunks(library_dir):
    chunks = load_library(library_dir)
    assert {c.doc_id for c in chunks} >= {"CH-SEC", "CH-INS", "CH-SITE", "CH-PROF"}
    assert all(c.text and not c.text.startswith(">") for c in chunks)


def _top_docs(index, query, categories=None, k=3):
    return [e.doc_id for e in index.search(query, HashEmbedder(), categories, k=k)]


def test_hybrid_search_finds_planted_facts(library_dir):
    index = build_index(library_dir)
    assert "CH-SEC" in _top_docs(
        index, "CJIS Level 4 certification for technicians", [Category.security_compliance]
    )
    assert "CH-INS" in _top_docs(index, "cyber liability insurance $1,000,000 per occurrence")
    assert "CH-SITE" in _top_docs(index, "attendance at the mandatory pre-bid walk-through")
    assert "CH-PRC" in _top_docs(index, "hourly rates and fixed monthly fee schedule", [Category.commercial])


def test_index_round_trip(library_dir):
    index = build_index(library_dir)
    again = EvidenceIndex.from_json(index.to_json())
    assert len(again.chunks) == len(index.chunks)
    assert again.get(index.chunks[0].id).text == index.chunks[0].text
