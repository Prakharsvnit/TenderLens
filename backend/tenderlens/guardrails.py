"""Bedrock Guardrails wrappers: prompt-attack screening of RFP text and contextual grounding of claims.

When no guardrail is configured (offline runs), deterministic fallbacks keep the pipeline working:
a pattern check for injected instructions and a lexical-overlap grounding score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .aws import bedrock_runtime
from .config import get_settings
from .retrieval.embeddings import tokenize

_INJECTION = re.compile(
    r"(ignore (all|any|the) (previous|prior|above) instructions|disregard (the|your) (rules|instructions)|"
    r"you are now|system prompt|act as (an?|the) (assistant|ai))",
    re.IGNORECASE,
)
_STOP = set(
    "the a an and or of to in for on with by is are be will shall must our we its their this that".split()
)


@dataclass(frozen=True)
class ScreenResult:
    flagged: bool
    source: str  # "guardrails" or "pattern"
    detail: str = ""


@dataclass(frozen=True)
class GroundingResult:
    grounding: float
    relevance: float
    source: str


def screen_text(text: str) -> ScreenResult:
    settings = get_settings()
    if settings.guardrail_id:
        response = bedrock_runtime().apply_guardrail(
            guardrailIdentifier=settings.guardrail_id,
            guardrailVersion=settings.guardrail_version,
            source="INPUT",
            content=[{"text": {"text": text[:20000]}}],
        )
        flagged = response.get("action") == "GUARDRAIL_INTERVENED"
        return ScreenResult(
            flagged, "guardrails", str(response.get("assessments", ""))[:300] if flagged else ""
        )
    match = _INJECTION.search(text)
    return ScreenResult(bool(match), "pattern", match.group(0) if match else "")


def _overlap(claim: str, source: str) -> float:
    words = [w for w in tokenize(claim) if w not in _STOP and len(w) > 2]
    if not words:
        return 0.0
    pool = set(tokenize(source))
    return sum(w in pool for w in words) / len(words)


def check_grounding(claim: str, evidence: str, query: str) -> GroundingResult:
    settings = get_settings()
    if settings.guardrail_id:
        response = bedrock_runtime().apply_guardrail(
            guardrailIdentifier=settings.guardrail_id,
            guardrailVersion=settings.guardrail_version,
            source="OUTPUT",
            content=[
                {"text": {"text": evidence[:20000], "qualifiers": ["grounding_source"]}},
                {"text": {"text": query[:1000], "qualifiers": ["query"]}},
                {"text": {"text": claim[:2000], "qualifiers": ["guard_content"]}},
            ],
        )
        scores = {"GROUNDING": 0.0, "RELEVANCE": 0.0}
        for assessment in response.get("assessments", []):
            for f in assessment.get("contextualGroundingPolicy", {}).get("filters", []):
                scores[f["type"]] = float(f.get("score", 0.0))
        return GroundingResult(scores["GROUNDING"], scores["RELEVANCE"], "guardrails")
    return GroundingResult(round(_overlap(claim, evidence), 3), round(_overlap(claim, query), 3), "lexical")
