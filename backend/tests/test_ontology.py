import pytest
from pydantic import ValidationError

from tenderlens.ontology import category_definitions, load_ontology
from tenderlens.ontology import models as m


def test_categories_match_yaml():
    assert set(load_ontology()["categories"]) == {c.value for c in m.Category}
    assert len(category_definitions()) == 7


def test_enums_match_yaml():
    for name, values in load_ontology()["enums"].items():
        enum = getattr(m, name)
        assert [e.value for e in enum] == values, name


def test_every_class_has_a_model():
    assert set(load_ontology()["classes"]) == set(m.ONTOLOGY_CLASSES)


def test_relations_reference_known_classes():
    classes = set(load_ontology()["classes"])
    for subject, _predicate, obj in load_ontology()["relations"]:
        assert subject in classes and obj in classes


def test_met_status_needs_evidence():
    with pytest.raises(ValidationError):
        m.Assessment(requirement_id="R1", status="met", rationale="x", confidence=0.9)
    ok = m.Assessment(requirement_id="R1", status="not_met", rationale="x", confidence=0.9)
    assert ok.evidence_ids == []


def test_claim_must_cite():
    with pytest.raises(ValidationError):
        m.Claim(id="C1", section_id="S1", text="We are CJIS certified.", evidence_ids=[])


def test_override_needs_reason():
    with pytest.raises(ValidationError):
        m.Approval(approver="a", accepted=False, final_decision="bid")


def test_messages_round_trip():
    msg = m.ClaimVerdicts(
        run_id="run1",
        produced_by="verifier",
        verdicts=[m.ClaimVerdict(claim_id="C1", verdict="supported", grounding_score=0.9)],
    )
    again = m.MESSAGE_TYPES["ClaimVerdicts"].model_validate_json(msg.model_dump_json())
    assert again == msg
