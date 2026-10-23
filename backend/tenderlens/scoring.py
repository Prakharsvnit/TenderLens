"""Bid/no-bid scoring in code: knock-outs first, then a score weighted by the RFP's own evaluation points.

The model never makes the call; the Bid Strategist agent only explores what-ifs and explains the result.
"""

from __future__ import annotations

import json
from pathlib import Path

from .ontology.models import (
    Assessment,
    BidDecision,
    BidPolicy,
    Category,
    Decision,
    EvaluationCriterion,
    Gap,
    KnockOutCheck,
    KnockOutOutcome,
    Requirement,
    RequirementStatus,
    ScoreLine,
    WhatIf,
)
from .parsing import normalize


def load_policy(path: Path) -> BidPolicy:
    return BidPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _fallback_criteria(requirements: list[Requirement]) -> list[EvaluationCriterion]:
    cats = sorted({r.category for r in requirements if r.category != Category.submission})
    return [EvaluationCriterion(name=c.value.replace("_", " ").title(), points=10) for c in cats]


def _criterion_members(
    criteria: list[EvaluationCriterion], requirements: list[Requirement], used_fallback: bool
) -> dict[str, list[Requirement]]:
    members: dict[str, list[Requirement]] = {c.name: [] for c in criteria}
    for r in requirements:
        if r.category == Category.submission:
            continue
        name = r.criterion if not used_fallback else r.category.value.replace("_", " ").title()
        if name in members:
            members[name].append(r)
    return members


def _bucket(credit: float) -> RequirementStatus:
    if credit >= 0.99:
        return RequirementStatus.met
    if credit <= 0.01:
        return RequirementStatus.not_met
    return RequirementStatus.partial


def decide(
    requirements: list[Requirement],
    assessments: list[Assessment],
    gaps: list[Gap],
    criteria: list[EvaluationCriterion],
    policy: BidPolicy,
    overrides: dict[str, RequirementStatus] | None = None,
) -> BidDecision:
    status = {a.requirement_id: a.status for a in assessments}
    status.update(overrides or {})
    evidence = {a.requirement_id: a.evidence_ids for a in assessments}
    gap_by_req = {g.requirement_id: g for g in gaps}

    # 1. Knock-outs.
    checks: list[KnockOutCheck] = []
    for rule in policy.knock_outs:
        terms = [normalize(t) for t in rule.match_terms]
        matched = [
            r
            for r in requirements
            if (r.critical or r.obligation == "mandatory") and any(t in normalize(r.quote) for t in terms)
        ]
        if not matched:
            continue
        failing = [r for r in matched if status.get(r.id) != RequirementStatus.met]
        if not failing:
            outcome, fix = KnockOutOutcome.met, ""
        elif rule.fixable_by:
            outcome = KnockOutOutcome.fixable
            gap = next(
                (gap_by_req[r.id] for r in failing if r.id in gap_by_req and gap_by_req[r.id].mitigation),
                None,
            )
            fix = (
                gap.mitigation.description
                if gap and gap.mitigation and gap.mitigation.description
                else (f"{rule.fixable_by.value.replace('_', ' ').capitalize()} for: {failing[0].summary}")
            )
        else:
            outcome, fix = KnockOutOutcome.fatal, "Cannot be fixed before submission."
        anchor = failing[0] if failing else matched[0]
        checks.append(
            KnockOutCheck(
                rule_id=rule.id,
                requirement_id=anchor.id,
                description=rule.description,
                outcome=outcome,
                evidence_ids=list(dict.fromkeys(e for r in matched for e in evidence.get(r.id, [])))[:5],
                fix=fix,
            )
        )

    # 2. Score weighted by evaluation points.
    used_fallback = not criteria
    criteria = criteria or _fallback_criteria(requirements)
    members = _criterion_members(criteria, requirements, used_fallback)
    lines: list[ScoreLine] = []
    for c in criteria:
        reqs = members[c.name]
        if reqs:
            credit = sum(
                policy.status_credit[status.get(r.id, RequirementStatus.no_evidence)] for r in reqs
            ) / len(reqs)
            line_status = _bucket(credit)
        else:
            credit, line_status = (
                policy.status_credit[RequirementStatus.no_evidence],
                RequirementStatus.no_evidence,
            )
        lines.append(
            ScoreLine(
                criterion=c.name, points=c.points, status=line_status, earned=round(c.points * credit, 2)
            )
        )
    score = round(sum(line.earned for line in lines), 2)
    max_score = round(sum(c.points for c in criteria), 2)
    pct = round(score / max_score, 4) if max_score else 0.0

    # 3. Decision.
    fixable = [c for c in checks if c.outcome == KnockOutOutcome.fixable]
    if any(c.outcome == KnockOutOutcome.fatal for c in checks) or pct < policy.conditional_threshold:
        decision = Decision.no_bid
    elif pct >= policy.bid_threshold and not fixable:
        decision = Decision.bid
    else:
        decision = Decision.bid_with_conditions
    return BidDecision(
        decision=decision,
        score=score,
        max_score=max_score,
        score_pct=pct,
        knock_outs=checks,
        score_lines=lines,
        conditions=[c.fix for c in fixable],
    )


def what_if(
    change: str,
    fix_requirement_ids: list[str],
    requirements: list[Requirement],
    assessments: list[Assessment],
    gaps: list[Gap],
    criteria: list[EvaluationCriterion],
    policy: BidPolicy,
) -> WhatIf:
    overrides = {rid: RequirementStatus.met for rid in fix_requirement_ids}
    result = decide(requirements, assessments, gaps, criteria, policy, overrides)
    return WhatIf(change=change, score_pct=result.score_pct, decision=result.decision)
