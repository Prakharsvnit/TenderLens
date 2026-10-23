"""Bid Strategist agent: explores what-ifs with the scoring tool and explains the code-computed decision."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from ..llm import tool_call
from ..ontology.models import (
    Assessment,
    BidDecision,
    BidPolicy,
    EvaluationCriterion,
    Gap,
    KnockOutOutcome,
    Requirement,
    RequirementStatus,
)
from ..parsing import normalize
from ..scoring import decide, what_if
from ..trace import Tracer
from .common import response_tool, run_agent, tool_results
from .schemas import StrategistOutput

SYSTEM = """You are the Bid Strategist for {bidder}. The bid/no-bid decision has already been computed in code
from knock-out rules and the RFP's evaluation points; you cannot change it. Your job:
1. Call list_gaps and get_bid_policy to understand the position.
2. Use compute_score to test what-ifs: which realistic fixes (for example a teaming partner or raising an
   insurance limit) would change the score or the decision. Test at most three.
3. Return a rationale of three to five plain sentences a sales director can act on, the conditions that must be
   met before submitting, and the what-ifs you tested."""


def strategize(
    requirements: list[Requirement],
    assessments: list[Assessment],
    gaps: list[Gap],
    criteria: list[EvaluationCriterion],
    policy: BidPolicy,
    bidder: str,
    tracer: Tracer,
) -> BidDecision:
    base = decide(requirements, assessments, gaps, criteria, policy)
    status = {a.requirement_id: a.status for a in assessments}
    open_items = [
        {
            "requirement_id": r.id,
            "requirement": r.summary,
            "critical": r.critical,
            "status": status.get(r.id),
            "gap": next((g.description for g in gaps if g.requirement_id == r.id), ""),
        }
        for r in requirements
        if status.get(r.id) in (RequirementStatus.not_met, RequirementStatus.partial)
    ]

    @tool
    def list_gaps() -> str:
        """Requirements the bidder does not fully meet, with their gaps."""
        return json.dumps(open_items)

    @tool
    def get_bid_policy() -> str:
        """The bidder's knock-out rules and decision thresholds."""
        return policy.model_dump_json()

    @tool
    def compute_score(change: str, requirement_ids: list[str]) -> str:
        """Recompute score and decision as if these requirements became Met."""
        result = what_if(change, requirement_ids, requirements, assessments, gaps, criteria, policy)
        return result.model_dump_json()

    summary = {
        "decision": base.decision,
        "score": f"{base.score} of {base.max_score} ({base.score_pct:.0%})",
        "knock_outs": [k.model_dump(mode="json") for k in base.knock_outs],
        "score_lines": [s.model_dump(mode="json") for s in base.score_lines],
    }
    output = run_agent(
        name="bid_strategist",
        kind="pro",
        system_prompt=SYSTEM.format(bidder=bidder),
        tools=[list_gaps, get_bid_policy, compute_score],
        prompt=f"The computed position:\n{json.dumps(summary, indent=1)}",
        schema=StrategistOutput,
        tracer=tracer,
        stub=_stub(base, requirements, status, policy),
        tool_calls=8,
    )
    known = {r.id for r in requirements}
    what_ifs = [
        what_if(
            w.change,
            [r for r in w.requirement_ids if r in known],
            requirements,
            assessments,
            gaps,
            criteria,
            policy,
        )
        for w in output.what_ifs[:3]
    ]
    conditions = list(dict.fromkeys(base.conditions + [c for c in output.conditions if c.strip()]))
    return base.model_copy(
        update={"rationale": output.rationale, "conditions": conditions, "what_ifs": what_ifs}
    )


def _fixable_sets(base: BidDecision, requirements, status, policy) -> list[tuple[str, list[str]]]:
    sets = []
    for check in base.knock_outs:
        if check.outcome != KnockOutOutcome.fixable:
            continue
        rule = next(r for r in policy.knock_outs if r.id == check.rule_id)
        terms = [normalize(t) for t in rule.match_terms]
        ids = [
            r.id
            for r in requirements
            if any(t in normalize(r.quote) for t in terms) and status.get(r.id) != RequirementStatus.met
        ]
        sets.append((check.fix or rule.description, ids))
    return sets


def _stub(base: BidDecision, requirements, status, policy):
    def script(messages, tool_names):
        sets = _fixable_sets(base, requirements, status, policy)
        done = len(tool_results(messages))
        if done == 0:
            return AIMessage("", tool_calls=[tool_call("list_gaps", {})])
        if done - 1 < len(sets[:2]):
            change, ids = sets[done - 1]
            return AIMessage(
                "", tool_calls=[tool_call("compute_score", {"change": change, "requirement_ids": ids})]
            )
        payload = {
            "rationale": (
                f"The computed recommendation is {base.decision.value.replace('_', ' ')} at "
                f"{base.score_pct:.0%} of the available points. "
                + (
                    "Fixable knock-outs must be closed before submission."
                    if sets
                    else "No knock-outs block the bid."
                )
            ),
            "conditions": [],
            "what_ifs": [{"change": c, "requirement_ids": ids} for c, ids in sets[:2]],
        }
        return AIMessage("", tool_calls=[tool_call(response_tool(StrategistOutput, tool_names), payload)])

    return script
