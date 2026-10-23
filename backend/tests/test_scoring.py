"""Scoring against the hand-labelled Belle Isle gold set: the decision logic must land where the design says."""

from pathlib import Path

import yaml

from tenderlens.ontology.models import (
    Assessment,
    Decision,
    EvaluationCriterion,
    KnockOutOutcome,
    Requirement,
    RequirementStatus,
)
from tenderlens.scoring import decide, load_policy, what_if

REPO = Path(__file__).resolve().parents[2]


def _gold():
    gold = yaml.safe_load((REPO / "evals" / "gold" / "belle-isle.yaml").read_text(encoding="utf-8"))
    reqs, assessments = [], []
    for g in gold["requirements"]:
        reqs.append(
            Requirement(
                id=g["id"],
                section_id=f"P{g['page']:02d}",
                page=g["page"],
                quote=g["quote"],
                summary=g["quote"][:60],
                obligation=g["obligation"],
                category=g["category"],
                critical=g["critical"],
                criterion=g.get("criterion"),
            )
        )
        status = RequirementStatus((g["expected_status"] or ["no_evidence"])[0])
        evidence = ["E1"] if status in (RequirementStatus.met, RequirementStatus.partial) else []
        assessments.append(
            Assessment(
                requirement_id=g["id"], status=status, evidence_ids=evidence, rationale="gold", confidence=1.0
            )
        )
    criteria = [EvaluationCriterion(**c) for c in gold["evaluation_criteria"]]
    return gold, reqs, assessments, criteria


def test_gold_decision_is_bid_with_conditions():
    gold, reqs, assessments, criteria = _gold()
    policy = load_policy(REPO / "data" / "policy" / "bid_policy.json")
    result = decide(reqs, assessments, [], criteria, policy)
    assert result.decision == Decision(gold["expected_decision"])
    assert result.max_score == 75
    assert 0.55 <= result.score_pct < 0.70
    outcomes = {k.rule_id: k.outcome for k in result.knock_outs}
    assert outcomes["KO-MEETING"] == KnockOutOutcome.met
    assert outcomes["KO-DEBARMENT"] == KnockOutOutcome.met
    assert outcomes["KO-SECURITY"] == KnockOutOutcome.fixable
    assert outcomes["KO-INSURANCE"] == KnockOutOutcome.fixable
    cjis = next(line for line in result.score_lines if line.criterion.startswith("CJIS"))
    assert cjis.earned == 0


def test_cjis_partner_what_if_raises_score():
    _, reqs, assessments, criteria = _gold()
    policy = load_policy(REPO / "data" / "policy" / "bid_policy.json")
    base = decide(reqs, assessments, [], criteria, policy)
    fixed = what_if("Add a CJIS partner", ["G06", "G23", "G24"], reqs, assessments, [], criteria, policy)
    assert fixed.score_pct > base.score_pct + 0.1


def test_missing_mandatory_meeting_is_fatal():
    _, reqs, assessments, criteria = _gold()
    policy = load_policy(REPO / "data" / "policy" / "bid_policy.json")
    result = decide(reqs, assessments, [], criteria, policy, {"G01": RequirementStatus.not_met})
    assert result.decision == Decision.no_bid
