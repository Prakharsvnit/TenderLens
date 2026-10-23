"""End-to-end run of the nine workflow steps with the offline stub models."""

from tenderlens.ontology.models import (
    AssessmentBatch,
    BidRecommendation,
    ClaimVerdicts,
    DraftMessage,
    RequirementSet,
)
from tenderlens.pipeline import local
from tenderlens.store import LocalStore, set_store


def test_full_run_offline(belle_isle_pdf, tmp_path):
    store = LocalStore(tmp_path)
    set_store(store)
    result = local.run(belle_isle_pdf, run_id="t1")
    run = store.get_run("t1")
    assert run["status"] == "complete"
    for cls in (RequirementSet, AssessmentBatch, DraftMessage, ClaimVerdicts, BidRecommendation):
        assert store.get_message("t1", cls).run_id == "t1"  # every hand-off passes its schema on read
    assert store.get_bytes("runs/t1/matrix.xlsx")[:2] == b"PK"
    assert store.get_bytes("runs/t1/draft.docx")[:2] == b"PK"
    agents = {e["agent"] for e in store.get_trace("t1")}
    assert {
        "rfp_analyst",
        "compliance_analyst",
        "proposal_writer",
        "claim_verifier",
        "bid_strategist",
    } <= agents
    tools = {e["name"] for e in store.get_trace("t1") if e["kind"] == "tool_call"}
    assert {"scan_modal_verbs", "search_evidence", "list_gaps", "compute_score"} <= tools
    kpis = result["kpis"]
    assert 0 < kpis["requirement_coverage"] <= 1
    assert kpis["evidence_backed_claim_rate"] > 0.5
    assert len(store.get_json("runs/t1/audit.json")) == 2  # both human checkpoints logged
