"""Compliance Analyst agent: searches the bidder's evidence, judges each requirement and records gaps."""

from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from ..llm import tool_call
from ..ontology.models import (
    Assessment,
    Category,
    Evidence,
    Gap,
    Mitigation,
    MitigationType,
    Requirement,
    RequirementStatus,
    Severity,
)
from ..retrieval import EvidenceIndex
from ..retrieval.embeddings import Embedder
from ..trace import Tracer
from .common import response_tool, run_agent, tool_results
from .schemas import AssessmentDraft, ComplianceOutput, GapDraft

SYSTEM = """You are the Compliance Analyst on a bid team for {bidder}. For each requirement, decide whether the
bidder meets it, using only evidence from the bidder's capability library. Each requirement comes with the top
passages from a first search. When they don't settle the question, call search_evidence with a better query.

Status:
- met: the evidence clearly shows the bidder satisfies the whole requirement.
- partial: the evidence covers part of it, or a weaker version (for example a different framework).
- not_met: the evidence shows the bidder does not satisfy it (look for explicit statements such as "have not").
- no_evidence: nothing in the library addresses it. Use this for submission steps the bid team simply
  performs (forms, copies, deadlines) unless the library records them, such as a meeting attendance record.

Rules:
- Cite evidence ids exactly as given. Met and partial need at least one citation.
- Most requirements need no extra search. When some do, make all those searches together in one turn (at most
  {searches} in total), then answer. Every extra turn re-sends the whole conversation, so keep turns few. Pass a
  category to search_evidence to focus on matching documents. Answer for all requirements in one response.
- confidence is your certainty from 0 to 1.
- For every requirement that is partial, not_met or no_evidence and not a pure submission step, add a gap with
  severity (critical for pass/fail requirements) and a mitigation: teaming_partner, clarification_question,
  exception or remediation."""

_NEGATIVE = re.compile(r"\b(have not|has not|not completed|no staff|not yet|limited to)\b", re.I)


def assess_batch(
    requirements: list[Requirement],
    index: EvidenceIndex,
    embedder: Embedder,
    bidder: str,
    tracer: Tracer,
) -> tuple[list[Assessment], list[Gap], list[Evidence]]:
    retrieved: dict[str, Evidence] = {}

    @tool
    def search_evidence(query: str, category: str | None = None) -> str:
        """Hybrid search of the bidder's capability library. Returns passages with evidence ids."""
        cats = [Category(category)] if category in Category.__members__ else None
        results = index.search(query, embedder, cats, k=5)
        for r in results:
            retrieved[r.id] = r
        return json.dumps(
            [
                {"id": r.id, "document": r.doc_title, "section": r.section, "text": r.text[:700]}
                for r in results
            ]
        )

    @tool
    def get_passage(evidence_id: str) -> str:
        """Full text of one evidence passage by id."""
        found = index.get(evidence_id)
        if found:
            retrieved[found.id] = found
        return found.text if found else "unknown evidence id"

    # First-pass retrieval in code: the top passages for every requirement go into the prompt, so the agent
    # spends model turns only on the requirements that need a better search.
    first_pass: dict[str, list[str]] = {}
    for req in requirements:
        hits = index.search(req.quote, embedder, [req.category], k=3)
        first_pass[req.id] = [h.id for h in hits]
        for h in hits:
            retrieved[h.id] = h
    tracer.add(
        "compliance_analyst",
        "tool_call",
        name="first_pass_search",
        detail=f"{len(requirements)} requirements, {len(retrieved)} passages",
    )
    listing = json.dumps(
        [
            {
                "id": r.id,
                "quote": r.quote,
                "category": r.category,
                "critical": r.critical,
                "passages": first_pass[r.id],
            }
            for r in requirements
        ],
        indent=1,
    )
    passages = json.dumps(
        [
            {"id": e.id, "document": e.doc_title, "section": e.section, "text": e.text[:700]}
            for e in retrieved.values()
        ],
        indent=1,
    )
    searches = max(3, len(requirements) // 2)
    output = run_agent(
        name="compliance_analyst",
        kind="pro",
        system_prompt=SYSTEM.format(bidder=bidder, searches=searches),
        tools=[search_evidence, get_passage],
        prompt=f"Assess these requirements:\n<rfp>\n{listing}\n</rfp>\n\nPassages:\n<evidence>\n{passages}\n</evidence>",
        schema=ComplianceOutput,
        tracer=tracer,
        stub=_stub(requirements, index, embedder),
        # Searches beyond the cap are refused and the model answers; 4 turns is search, search, answer, retry.
        tool_calls=searches,
        model_calls=4,
    )
    return _validate(requirements, output, retrieved, tracer)


def _validate(
    requirements: list[Requirement], output: ComplianceOutput, retrieved: dict[str, Evidence], tracer: Tracer
) -> tuple[list[Assessment], list[Gap], list[Evidence]]:
    by_id = {a.requirement_id: a for a in output.assessments}
    assessments: list[Assessment] = []
    for req in requirements:
        draft = by_id.get(req.id)
        if draft is None:
            tracer.add("compliance_analyst", "validation", name="missing_assessment", detail=req.id)
            draft = AssessmentDraft(
                requirement_id=req.id,
                status="no_evidence",
                rationale="Not assessed by the agent.",
                confidence=0.0,
            )
        cited = [e for e in draft.evidence_ids if e in retrieved]
        if len(cited) < len(draft.evidence_ids):
            tracer.add(
                "compliance_analyst",
                "validation",
                name="citation_rejected",
                detail=f"{req.id}: dropped {sorted(set(draft.evidence_ids) - set(cited))}",
            )
        status = draft.status
        if status in (RequirementStatus.met, RequirementStatus.partial) and not cited:
            tracer.add(
                "compliance_analyst",
                "validation",
                name="status_downgraded",
                detail=f"{req.id}: no valid evidence",
            )
            status = RequirementStatus.no_evidence
        assessments.append(
            Assessment(
                requirement_id=req.id,
                status=status,
                evidence_ids=cited,
                rationale=draft.rationale,
                confidence=draft.confidence,
            )
        )
    known = {r.id for r in requirements}
    gaps = [
        Gap(
            id=f"GAP-{g.requirement_id}",
            requirement_id=g.requirement_id,
            severity=g.severity,
            knock_out=next((r.critical for r in requirements if r.id == g.requirement_id), False),
            description=g.description,
            mitigation=Mitigation(type=g.mitigation_type, description=g.mitigation or "")
            if g.mitigation_type
            else None,
        )
        for g in output.gaps
        if g.requirement_id in known
    ]
    cited_ids = {e for a in assessments for e in a.evidence_ids}
    evidence = [e for eid, e in retrieved.items() if eid in cited_ids]
    return assessments, gaps, evidence


# --- offline stub -------------------------------------------------------------------------------


def _stub(requirements: list[Requirement], index: EvidenceIndex, embedder: Embedder):
    def script(messages, tool_names):
        if not tool_results(messages):  # like the real agent: one follow-up search, then answer
            req = requirements[0]
            return AIMessage(
                "", tool_calls=[tool_call("search_evidence", {"query": req.quote, "category": req.category})]
            )
        assessments, gaps = [], []
        for req in requirements:
            top = index.search(req.quote, embedder, [req.category], k=2)
            text = " ".join(e.text for e in top)
            if req.category == Category.submission and not any(e.doc_id == "CH-SITE" for e in top):
                status = RequirementStatus.no_evidence
            elif _NEGATIVE.search(text) and req.category == Category.security_compliance:
                status = RequirementStatus.not_met
            elif top and top[0].score > 0.03:
                status = RequirementStatus.met
            else:
                status = RequirementStatus.no_evidence
            ids = [e.id for e in top] if status != RequirementStatus.no_evidence else []
            assessments.append(
                {
                    "requirement_id": req.id,
                    "status": status,
                    "evidence_ids": ids,
                    "rationale": f"Stub judgement from {len(top)} passages.",
                    "confidence": 0.5,
                }
            )
            if status == RequirementStatus.not_met:
                gaps.append(
                    {
                        "requirement_id": req.id,
                        "severity": Severity.critical if req.critical else Severity.medium,
                        "description": f"Bidder evidence does not satisfy: {req.summary}",
                        "mitigation_type": MitigationType.teaming_partner,
                        "mitigation": "Team with a qualified partner.",
                    }
                )
        payload = {"assessments": assessments, "gaps": gaps}
        return AIMessage("", tool_calls=[tool_call(response_tool(ComplianceOutput, tool_names), payload)])

    return script


__all__ = ["assess_batch", "GapDraft"]
