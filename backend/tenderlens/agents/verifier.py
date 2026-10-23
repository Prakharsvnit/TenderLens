"""Claim Verifier agent: checks every claim against its cited evidence with the Guardrails grounding check."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from ..config import get_settings
from ..guardrails import check_grounding
from ..llm import tool_call
from ..ontology.models import Claim, ClaimVerdict, ClaimVerdictLabel, DraftSection, Evidence, Requirement
from ..trace import Tracer
from .common import response_tool, run_agent, tool_results
from .schemas import VerifierOutput

BATCH = 12

SYSTEM = """You are the Claim Verifier on a bid team. You did not write the draft. For each claim, call
check_grounding to get the Bedrock Guardrails grounding score and the cited evidence, then judge:
- supported: the evidence states every fact in the claim.
- contradicted: the evidence says something different (wrong number, certification or commitment).
- unsupported: the evidence does not state the fact, or states only part of it.
Be strict about numbers, certifications, response times and locations. Give a short note for any claim that is
not supported, saying what is missing."""


def verify(
    sections: list[DraftSection],
    evidence: list[Evidence],
    requirements: list[Requirement],
    tracer: Tracer,
) -> list[ClaimVerdict]:
    settings = get_settings()
    passages = {e.id: e for e in evidence}
    reqs = {r.id: r for r in requirements}
    claims = [c for s in sections for c in s.claims]
    scores: dict[str, tuple[float, str]] = {}

    def _score(claim: Claim) -> tuple[float, str]:
        if claim.id not in scores:
            source = "\n".join(passages[e].text for e in claim.evidence_ids if e in passages)
            query = " ".join(reqs[r].quote for r in claim.requirement_ids if r in reqs) or claim.text
            result = check_grounding(claim.text, source, query)
            scores[claim.id] = (result.grounding, source)
            tracer.add(
                "claim_verifier",
                "guardrail",
                name=f"guardrails:{result.source}",
                detail=f"{claim.id} grounding={result.grounding:.2f} relevance={result.relevance:.2f}",
            )
        return scores[claim.id]

    lookup = {c.id: c for c in claims}

    @tool("check_grounding")
    def check_grounding_tool(claim_id: str) -> str:
        """Grounding score (0 to 1) from Bedrock Guardrails plus the evidence the claim cites."""
        claim = lookup.get(claim_id)
        if not claim:
            return "unknown claim id"
        score, source = _score(claim)
        return json.dumps({"claim_id": claim_id, "grounding": score, "evidence": source[:1500]})

    verdicts: list[ClaimVerdict] = []
    for start in range(0, len(claims), BATCH):
        batch = claims[start : start + BATCH]
        listing = json.dumps([{"claim_id": c.id, "claim": c.text} for c in batch], indent=1)
        output = run_agent(
            name="claim_verifier",
            kind="lite",
            system_prompt=SYSTEM,
            tools=[check_grounding_tool],
            prompt=f"Verify these claims:\n<rfp>\n{listing}\n</rfp>",
            schema=VerifierOutput,
            tracer=tracer,
            stub=_stub(batch, _score, settings.grounding_threshold),
            tool_calls=len(batch) + 2,
            model_calls=len(batch) + 3,
        )
        judged = {v.claim_id: v for v in output.verdicts}
        for claim in batch:
            grounding, _ = _score(claim)
            draft = judged.get(claim.id)
            label = (
                draft.verdict
                if draft
                else (
                    ClaimVerdictLabel.supported
                    if grounding >= settings.grounding_threshold
                    else ClaimVerdictLabel.unsupported
                )
            )
            note = draft.note if draft else "Judged from the grounding score only."
            if label == ClaimVerdictLabel.supported and grounding < 0.3:
                tracer.add(
                    "claim_verifier",
                    "validation",
                    name="verdict_overridden",
                    detail=f"{claim.id}: grounding {grounding:.2f} is too low for supported",
                )
                label, note = ClaimVerdictLabel.unsupported, f"Grounding score {grounding:.2f} is below 0.3."
            verdicts.append(
                ClaimVerdict(claim_id=claim.id, verdict=label, grounding_score=round(grounding, 3), note=note)
            )
    return verdicts


def _stub(batch: list[Claim], score, threshold: float):
    def script(messages, tool_names):
        done = len(tool_results(messages))
        if done < len(batch):
            return AIMessage("", tool_calls=[tool_call("check_grounding", {"claim_id": batch[done].id})])
        verdicts = []
        for claim in batch:
            grounding, _ = score(claim)
            ok = grounding >= threshold
            verdicts.append(
                {
                    "claim_id": claim.id,
                    "verdict": "supported" if ok else "unsupported",
                    "note": "" if ok else "Evidence does not state every fact in the claim.",
                }
            )
        return AIMessage(
            "", tool_calls=[tool_call(response_tool(VerifierOutput, tool_names), {"verdicts": verdicts})]
        )

    return script
