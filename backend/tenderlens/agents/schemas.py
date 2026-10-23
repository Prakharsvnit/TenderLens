"""Structured outputs the agents return (LangChain ToolStrategy). Lenient on purpose: the pipeline
validates and converts them into ontology types, recording every rejection in the trace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..ontology.models import (
    Category,
    ClaimVerdictLabel,
    EvaluationCriterion,
    MitigationType,
    Obligation,
    RequirementStatus,
    Severity,
)


class ExtractedRequirement(BaseModel):
    section_id: str = Field(description="Section id of the page, e.g. P03")
    page: int
    quote: str = Field(description="The requirement copied word for word from the page")
    summary: str = Field(description="Plain-language restatement, at most 20 words")
    obligation: Obligation
    category: Category
    critical: bool = Field(description="True only if failing it disqualifies the bid or contract")
    criterion: str | None = Field(default=None, description="Exact evaluation criterion name, or null")


class AnalystOutput(BaseModel):
    requirements: list[ExtractedRequirement]


class CriteriaOutput(BaseModel):
    criteria: list[EvaluationCriterion] = Field(description="Evaluation criteria with their maximum points")


class AssessmentDraft(BaseModel):
    requirement_id: str
    status: RequirementStatus
    evidence_ids: list[str] = Field(default_factory=list, description="Ids returned by search_evidence")
    rationale: str = Field(description="One or two sentences explaining the status")
    confidence: float = Field(ge=0, le=1)


class GapDraft(BaseModel):
    requirement_id: str
    severity: Severity
    description: str
    mitigation_type: MitigationType | None = None
    mitigation: str | None = None


class ComplianceOutput(BaseModel):
    assessments: list[AssessmentDraft]
    gaps: list[GapDraft] = Field(default_factory=list)


class ClaimDraft(BaseModel):
    text: str = Field(description="One factual sentence in the bidder's voice")
    requirement_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(description="Evidence ids that state this fact")


class SectionDraft(BaseModel):
    title: str
    rfp_reference: str = Field(default="", description="The RFP item this section answers")
    claims: list[ClaimDraft]
    sme_placeholders: list[str] = Field(default_factory=list, description="Facts a subject expert must add")


class WriterOutput(BaseModel):
    sections: list[SectionDraft]


class RewriteItem(BaseModel):
    claim_id: str
    action: Literal["revise", "drop", "sme"] = Field(
        description="revise: rewrite so the evidence supports it; drop: remove it; sme: turn into a placeholder"
    )
    text: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RewriteOutput(BaseModel):
    rewrites: list[RewriteItem]


class VerdictDraft(BaseModel):
    claim_id: str
    verdict: ClaimVerdictLabel
    note: str = ""


class VerifierOutput(BaseModel):
    verdicts: list[VerdictDraft]


class WhatIfRequest(BaseModel):
    change: str = Field(description="The fix in plain words, e.g. 'Add a CJIS-certified teaming partner'")
    requirement_ids: list[str] = Field(description="Requirements the fix would make Met")


class StrategistOutput(BaseModel):
    rationale: str = Field(description="Three to five sentences explaining the recommendation")
    conditions: list[str] = Field(default_factory=list, description="Fixes required before submitting")
    what_ifs: list[WhatIfRequest] = Field(default_factory=list)
