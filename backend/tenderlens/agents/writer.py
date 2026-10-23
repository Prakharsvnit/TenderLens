"""Proposal Writer agent: drafts the response as atomic, cited claims, and rewrites claims the Verifier flags."""

from __future__ import annotations

import json
from collections import defaultdict

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from ..llm import tool_call
from ..ontology.models import (
    Assessment,
    Category,
    Claim,
    ClaimVerdict,
    DraftSection,
    Evidence,
    Requirement,
    RequirementStatus,
)
from ..trace import Tracer
from .common import response_tool, run_agent
from .schemas import ClaimDraft, RewriteOutput, SectionDraft, WriterOutput

SYSTEM = """You are the Proposal Writer for {bidder}. Write the proposal response as a list of sections, each
made of atomic factual claims: one sentence per claim, in the bidder's voice ("Cobalt Harbor ..." or "We ...").

Rules:
- Every claim cites the evidence_ids that state its facts. Use only facts found in the evidence provided;
  never invent numbers, certifications, names or commitments.
- Do not claim the bidder meets a requirement assessed as not_met or no_evidence. For those, add an SME
  placeholder describing what a subject expert must supply or decide.
- Order sections to follow the RFP's own response structure where it gives one; otherwise use: approach and
  services, service levels and support, security and compliance, staffing and experience, insurance and legal,
  commercial.
- Tag each claim with the requirement_ids it answers.
- Call get_evidence when you need the full text of a passage."""

REWRITE_SYSTEM = """You are the Proposal Writer for {bidder}. The Claim Verifier flagged claims that their cited
evidence does not support. For each one choose: revise (rewrite it so the evidence fully supports it, citing the
right evidence_ids), sme (turn it into a placeholder for a subject expert) or drop (remove it). Never keep an
unsupported fact."""

SECTION_ORDER = [
    Category.technical,
    Category.service_levels,
    Category.security_compliance,
    Category.staffing,
    Category.insurance_legal,
    Category.commercial,
]


def _context(requirements, assessments, evidence) -> str:
    by_req = {a.requirement_id: a for a in assessments}
    reqs = [
        {
            "id": r.id,
            "category": r.category,
            "requirement": r.quote,
            "status": by_req[r.id].status if r.id in by_req else "no_evidence",
            "evidence_ids": by_req[r.id].evidence_ids if r.id in by_req else [],
        }
        for r in requirements
        if r.category != Category.submission
    ]
    passages = [{"id": e.id, "document": e.doc_title, "text": e.text[:900]} for e in evidence]
    return f"<rfp>\n{json.dumps(reqs, indent=1)}\n</rfp>\n<evidence>\n{json.dumps(passages, indent=1)}\n</evidence>"


def draft(
    requirements: list[Requirement],
    assessments: list[Assessment],
    evidence: list[Evidence],
    bidder: str,
    tracer: Tracer,
) -> list[DraftSection]:
    passages = {e.id: e for e in evidence}

    @tool
    def get_evidence(evidence_id: str) -> str:
        """Full text of one evidence passage."""
        found = passages.get(evidence_id)
        return found.text if found else "unknown evidence id"

    output = run_agent(
        name="proposal_writer",
        kind="pro",
        system_prompt=SYSTEM.format(bidder=bidder),
        tools=[get_evidence],
        prompt=f"Draft the proposal response.\n\n{_context(requirements, assessments, evidence)}",
        schema=WriterOutput,
        tracer=tracer,
        stub=_stub(requirements, assessments, passages),
    )
    return _to_sections(output.sections, passages, tracer)


def _to_sections(
    drafts: list[SectionDraft], passages: dict[str, Evidence], tracer: Tracer
) -> list[DraftSection]:
    sections: list[DraftSection] = []
    n = 0
    for s_index, sd in enumerate(drafts, start=1):
        section_id = f"S{s_index:02d}"
        claims, placeholders = [], list(sd.sme_placeholders)
        for cd in sd.claims:
            cited = [e for e in cd.evidence_ids if e in passages]
            if not cited:
                tracer.add("proposal_writer", "validation", name="claim_to_sme", detail=cd.text[:120])
                placeholders.append(f"Provide evidence for: {cd.text}")
                continue
            n += 1
            claims.append(
                Claim(
                    id=f"C{n:03d}",
                    section_id=section_id,
                    text=cd.text.strip(),
                    requirement_ids=cd.requirement_ids,
                    evidence_ids=cited,
                )
            )
        sections.append(
            DraftSection(
                id=section_id,
                title=sd.title,
                rfp_reference=sd.rfp_reference,
                text=render(claims),
                claims=claims,
                sme_placeholders=placeholders,
            )
        )
    return sections


def render(claims: list[Claim]) -> str:
    return " ".join(f"{c.text} [{', '.join(c.evidence_ids)}]" for c in claims)


def rewrite(
    sections: list[DraftSection],
    flagged: list[ClaimVerdict],
    evidence: list[Evidence],
    bidder: str,
    tracer: Tracer,
) -> list[DraftSection]:
    passages = {e.id: e for e in evidence}
    claims = {c.id: c for s in sections for c in s.claims}
    items = [
        {
            "claim_id": v.claim_id,
            "claim": claims[v.claim_id].text,
            "verifier_note": v.note,
            "cited": [
                {"id": e, "text": passages[e].text[:700]}
                for e in claims[v.claim_id].evidence_ids
                if e in passages
            ],
        }
        for v in flagged
        if v.claim_id in claims
    ]
    all_passages = [{"id": e.id, "text": e.text[:500]} for e in evidence]
    output = run_agent(
        name="proposal_writer",
        kind="pro",
        system_prompt=REWRITE_SYSTEM.format(bidder=bidder),
        tools=[],
        prompt=f"Fix these flagged claims.\n<rfp>\n{json.dumps(items, indent=1)}\n</rfp>\n"
        f"<evidence>\n{json.dumps(all_passages)}\n</evidence>",
        schema=RewriteOutput,
        tracer=tracer,
        stub=_rewrite_stub(items),
        model_calls=4,
    )
    decisions = {r.claim_id: r for r in output.rewrites}
    updated = []
    for section in sections:
        new_claims, placeholders = [], list(section.sme_placeholders)
        for claim in section.claims:
            decision = decisions.get(claim.id)
            if decision is None:
                new_claims.append(claim)
            elif (
                decision.action == "revise"
                and decision.text
                and [e for e in decision.evidence_ids if e in passages]
            ):
                cited = [e for e in decision.evidence_ids if e in passages]
                new_claims.append(
                    claim.model_copy(update={"text": decision.text.strip(), "evidence_ids": cited})
                )
            elif decision.action == "drop":
                tracer.add("proposal_writer", "validation", name="claim_dropped", detail=claim.id)
            else:
                placeholders.append(f"Confirm or supply evidence for: {claim.text}")
        updated.append(
            section.model_copy(
                update={"claims": new_claims, "text": render(new_claims), "sme_placeholders": placeholders}
            )
        )
    return updated


# --- offline stubs ----------------------------------------------------------------------------------


def _stub(requirements, assessments, passages):
    def script(messages, tool_names):
        by_req = {a.requirement_id: a for a in assessments}
        grouped: dict[Category, list] = defaultdict(list)
        sme: dict[Category, list] = defaultdict(list)
        for r in requirements:
            a = by_req.get(r.id)
            if r.category == Category.submission or a is None:
                continue
            if a.status in (RequirementStatus.met, RequirementStatus.partial) and a.evidence_ids:
                eid = a.evidence_ids[0]
                sentence = (
                    passages[eid].text.split(". ")[0].strip().rstrip(".") + "." if eid in passages else ""
                )
                grouped[r.category].append(
                    ClaimDraft(text=sentence, requirement_ids=[r.id], evidence_ids=[eid]).model_dump()
                )
            else:
                sme[r.category].append(f"Address: {r.summary}")
        sections = [
            {
                "title": c.value.replace("_", " ").title(),
                "rfp_reference": "",
                "claims": grouped[c],
                "sme_placeholders": sme[c],
            }
            for c in SECTION_ORDER
            if grouped[c] or sme[c]
        ]
        return AIMessage(
            "", tool_calls=[tool_call(response_tool(WriterOutput, tool_names), {"sections": sections})]
        )

    return script


def _rewrite_stub(items):
    def script(messages, tool_names):
        payload = {"rewrites": [{"claim_id": i["claim_id"], "action": "sme"} for i in items]}
        return AIMessage("", tool_calls=[tool_call(response_tool(RewriteOutput, tool_names), payload)])

    return script
