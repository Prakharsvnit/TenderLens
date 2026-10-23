"""Pydantic models for the TenderLens ontology (see tenderlens.yaml).

Every agent output, tool input and message between agents is one of these types, so a malformed
hand-off fails at the boundary instead of three steps later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = 1


class Category(StrEnum):
    technical = "technical"
    security_compliance = "security_compliance"
    staffing = "staffing"
    service_levels = "service_levels"
    insurance_legal = "insurance_legal"
    commercial = "commercial"
    submission = "submission"


class Obligation(StrEnum):
    mandatory = "mandatory"
    desirable = "desirable"


class RequirementStatus(StrEnum):
    met = "met"
    partial = "partial"
    not_met = "not_met"
    no_evidence = "no_evidence"


class ClaimVerdictLabel(StrEnum):
    supported = "supported"
    unsupported = "unsupported"
    contradicted = "contradicted"


class Decision(StrEnum):
    bid = "bid"
    bid_with_conditions = "bid_with_conditions"
    no_bid = "no_bid"


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class MitigationType(StrEnum):
    teaming_partner = "teaming_partner"
    clarification_question = "clarification_question"
    exception = "exception"
    remediation = "remediation"


class KnockOutOutcome(StrEnum):
    met = "met"
    fixable = "fixable"
    fatal = "fatal"


def _now() -> datetime:
    return datetime.now(UTC)


# --- Buyer side -------------------------------------------------------------------------------


class Buyer(BaseModel):
    name: str
    kind: str = "public body"


class Section(BaseModel):
    id: str
    heading: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str

    @model_validator(mode="after")
    def _pages_in_order(self) -> Section:
        if self.page_end < self.page_start:
            raise ValueError("page_end must not be before page_start")
        return self


class EvaluationCriterion(BaseModel):
    name: str
    points: float = Field(gt=0)


class RFP(BaseModel):
    id: str
    title: str
    buyer: Buyer
    page_count: int = Field(ge=1)
    due: str | None = None
    sections: list[Section] = Field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterion] = Field(default_factory=list)


class Requirement(BaseModel):
    id: str
    section_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=8, description="The requirement, copied word for word from the RFP.")
    summary: str = Field(description="A short plain-language restatement.")
    obligation: Obligation
    category: Category
    critical: bool = Field(description="True when failing it disqualifies the bid (pass/fail).")
    criterion: str | None = Field(default=None, description="Evaluation criterion this requirement feeds.")


# --- Bidder side ------------------------------------------------------------------------------


class Bidder(BaseModel):
    id: str
    name: str
    fictional: bool = True


class CapabilityDocument(BaseModel):
    id: str
    title: str
    doc_type: str
    categories: list[Category]


class Evidence(BaseModel):
    id: str
    doc_id: str
    doc_title: str
    section: str
    text: str
    score: float = 0.0
    categories: list[Category] = Field(default_factory=list)


class Capability(BaseModel):
    id: str
    name: str
    category: Category
    description: str


# --- Assessment, gaps and the draft -----------------------------------------------------------


class Assessment(BaseModel):
    requirement_id: str
    status: RequirementStatus
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _met_needs_evidence(self) -> Assessment:
        if self.status in (RequirementStatus.met, RequirementStatus.partial) and not self.evidence_ids:
            raise ValueError(f"{self.requirement_id}: a {self.status} status must cite evidence")
        return self


class Mitigation(BaseModel):
    type: MitigationType
    description: str


class Gap(BaseModel):
    id: str
    requirement_id: str
    severity: Severity
    knock_out: bool
    description: str
    mitigation: Mitigation | None = None


class Claim(BaseModel):
    id: str
    section_id: str
    text: str
    requirement_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str]

    @field_validator("evidence_ids")
    @classmethod
    def _must_cite(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("a claim must cite at least one piece of evidence")
        return value


class DraftSection(BaseModel):
    id: str
    title: str
    rfp_reference: str = ""
    text: str
    claims: list[Claim] = Field(default_factory=list)
    sme_placeholders: list[str] = Field(default_factory=list)


class ClaimVerdict(BaseModel):
    claim_id: str
    verdict: ClaimVerdictLabel
    grounding_score: float = Field(ge=0.0, le=1.0)
    note: str = ""


# --- Decision ---------------------------------------------------------------------------------


class KnockOutRule(BaseModel):
    id: str
    description: str
    match_terms: list[str] = Field(description="Words that identify the requirement this rule checks.")
    fixable_by: MitigationType | None = None


class BidPolicy(BaseModel):
    version: int = 1
    bidder_id: str
    knock_outs: list[KnockOutRule]
    status_credit: dict[RequirementStatus, float] = Field(
        default_factory=lambda: {
            RequirementStatus.met: 1.0,
            RequirementStatus.partial: 0.5,
            RequirementStatus.not_met: 0.0,
            RequirementStatus.no_evidence: 0.5,
        }
    )
    bid_threshold: float = 0.70
    conditional_threshold: float = 0.55


class KnockOutCheck(BaseModel):
    rule_id: str
    requirement_id: str | None
    description: str
    outcome: KnockOutOutcome
    evidence_ids: list[str] = Field(default_factory=list)
    fix: str = ""


class ScoreLine(BaseModel):
    criterion: str
    points: float
    status: RequirementStatus
    earned: float


class WhatIf(BaseModel):
    change: str
    score_pct: float
    decision: Decision


class BidDecision(BaseModel):
    decision: Decision
    score: float
    max_score: float
    score_pct: float
    knock_outs: list[KnockOutCheck]
    score_lines: list[ScoreLine]
    conditions: list[str] = Field(default_factory=list)
    what_ifs: list[WhatIf] = Field(default_factory=list)
    rationale: str = ""


class Approval(BaseModel):
    approver: str
    accepted: bool
    final_decision: Decision
    reason: str = ""
    at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _override_needs_reason(self) -> Approval:
        if not self.accepted and not self.reason.strip():
            raise ValueError("an override must give a reason")
        return self


# --- Messages between agents (the blackboard) -------------------------------------------------


class Envelope(BaseModel):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    produced_by: str
    created_at: datetime = Field(default_factory=_now)


class RequirementSet(Envelope):
    rfp: RFP
    requirements: list[Requirement]
    possible_misses: list[str] = Field(default_factory=list)


class AssessmentBatch(Envelope):
    assessments: list[Assessment]
    evidence: list[Evidence]
    gaps: list[Gap] = Field(default_factory=list)


class DraftMessage(Envelope):
    sections: list[DraftSection]
    round: int = 0


class ClaimVerdicts(Envelope):
    verdicts: list[ClaimVerdict]
    round: int = 0


class BidRecommendation(Envelope):
    decision: BidDecision


MESSAGE_TYPES: dict[str, type[Envelope]] = {
    cls.__name__: cls
    for cls in (RequirementSet, AssessmentBatch, DraftMessage, ClaimVerdicts, BidRecommendation)
}

# Ontology class name -> model, used by the sync test.
ONTOLOGY_CLASSES: dict[str, type[BaseModel]] = {
    "Buyer": Buyer,
    "RFP": RFP,
    "Section": Section,
    "Requirement": Requirement,
    "Claim": Claim,
    "Bidder": Bidder,
    "CapabilityDocument": CapabilityDocument,
    "Evidence": Evidence,
    "Capability": Capability,
    "Gap": Gap,
    "Mitigation": Mitigation,
    "BidDecision": BidDecision,
    "BidPolicy": BidPolicy,
    "Approval": Approval,
}
