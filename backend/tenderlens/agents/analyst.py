"""RFP Analyst agent: extracts atomic requirements and the evaluation criteria from the RFP."""

from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from ..ontology import category_definitions
from ..ontology.models import RFP, Category, EvaluationCriterion, Obligation, Requirement
from ..parsing import ScanHit, normalize, scan_modal_verbs
from ..trace import Tracer
from .common import human_text, response_tool, run_agent, tool_results
from .schemas import AnalystOutput, CriteriaOutput, ExtractedRequirement

PAGES_PER_BATCH = 3

SYSTEM = """You are the RFP Analyst on a bid team. You read pages of a public RFP and extract every atomic
requirement that the bidder (called Contractor, Proposer, Vendor, Respondent or Bidder) must satisfy or
address in its proposal.

Rules:
- quote: copy the requirement word for word from the page, one sentence or clause of 8 to 300 characters.
  Never paraphrase a quote; it is checked character by character against the PDF.
- One requirement per obligation. Split a sentence that contains several distinct obligations.
- Skip the buyer's own obligations, background narrative and boilerplate that asks nothing of the bidder.
- obligation: mandatory for shall, must, required or will be expected; desirable for should, may or requested.
- critical: true only when failing it disqualifies the bid or voids the contract (pass/fail): mandatory
  meetings, submission deadlines, required certifications or security clearances, minimum insurance,
  debarment, licences.
- category: one of these
{categories}
- criterion: the exact name of the evaluation criterion the requirement feeds, or null. Criteria: {criteria}
- Before answering, call scan_modal_verbs for each page to check you have not missed a shall/must statement."""

CRITERIA_SYSTEM = """You read the evaluation section of an RFP and list every scored evaluation criterion with
its maximum points, exactly as the RFP names them. Return an empty list if the RFP gives no points."""


def _batches(rfp: RFP) -> list[list]:
    pages = [s for s in rfp.sections if len(s.text) > 40]
    return [pages[i : i + PAGES_PER_BATCH] for i in range(0, len(pages), PAGES_PER_BATCH)]


# --- offline stub -------------------------------------------------------------------------------

_CATEGORY_HINTS = [
    (
        Category.submission,
        r"proposal|submi|bids? |sealed|deadline|attachment|form|copies|pages|walk-through|pre-bid|lobb",
    ),
    (Category.insurance_legal, r"insurance|indemn|liabil|licen|statute|confidential|terminat|debar|records"),
    (Category.security_compliance, r"cjis|secur|nist|penetration|antivirus|background|siem|encrypt|phishing"),
    (Category.commercial, r"fee|pric|cost|rate|budget|purchas|bundle|charges"),
    (Category.service_levels, r"24/7|24x7|response time|help desk|after hours|onsite|on-site|sla|toll-free"),
    (Category.staffing, r"staff|personnel|employee|skills|references|qualif"),
]
_CRITICAL = re.compile(
    r"mandatory to qualify|will not be accepted|not be considered|cjis|not be less than|debarment|disqualified",
    re.IGNORECASE,
)


def _stub_criterion(sentence: str, criteria: list[EvaluationCriterion]) -> str | None:
    words = set(re.findall(r"[a-z0-9]{4,}", sentence.lower()))
    best = max(
        criteria, key=lambda c: len(words & set(re.findall(r"[a-z0-9]{4,}", c.name.lower()))), default=None
    )
    if best and words & set(re.findall(r"[a-z0-9]{4,}", best.name.lower())):
        return best.name
    return None


def _stub_requirement(hit: ScanHit, criteria: list[EvaluationCriterion]) -> dict:
    sentence = hit.sentence[:290]
    category = next((c for c, rx in _CATEGORY_HINTS if re.search(rx, sentence, re.I)), Category.technical)
    obligation = Obligation.desirable if hit.modal in ("should", "may") else Obligation.mandatory
    return ExtractedRequirement(
        section_id=hit.section_id,
        page=hit.page,
        quote=sentence,
        summary=sentence[:80],
        obligation=obligation,
        category=category,
        critical=bool(_CRITICAL.search(sentence)),
        criterion=_stub_criterion(sentence, criteria),
    ).model_dump(mode="json")


def _analyst_stub(rfp: RFP, batch: list, criteria: list[EvaluationCriterion]):
    def script(messages, tool_names):
        if not tool_results(messages):
            return AIMessage("", tool_calls=[_call("scan_modal_verbs", {"section_id": s.id}) for s in batch])
        hits = scan_modal_verbs(batch)
        payload = {"requirements": [_stub_requirement(h, criteria) for h in hits]}
        return AIMessage("", tool_calls=[_call(response_tool(AnalystOutput, tool_names), payload)])

    return script


def _criteria_stub(messages, tool_names):
    found = []
    for line in human_text(messages).splitlines():
        match = re.match(r"^\s*([A-Z][A-Za-z&/,()' \-]{5,80}?)\s+(\d{1,3})\s*$", line)
        if match and "total" not in match.group(1).lower():
            found.append({"name": match.group(1).strip(), "points": float(match.group(2))})
    return AIMessage("", tool_calls=[_call(response_tool(CriteriaOutput, tool_names), {"criteria": found})])


def _call(name: str, args: dict) -> dict:
    from ..llm import tool_call

    return tool_call(name, args)


# --- agent runs -----------------------------------------------------------------------------------


def find_criteria(rfp: RFP, tracer: Tracer) -> list[EvaluationCriterion]:
    pages = [s for s in rfp.sections if re.search(r"points|weight|scor", s.text, re.I)]
    pages = [s for s in pages if re.search(r"criteri|evaluat", s.text, re.I)][:3]
    if not pages:
        return []
    text = "\n".join(f'<rfp page="{s.page_start}">\n{s.text}\n</rfp>' for s in pages)
    output = run_agent(
        name="rfp_analyst",
        kind="lite",
        system_prompt=CRITERIA_SYSTEM,
        tools=[],
        prompt=f"List the evaluation criteria and points.\n\n{text}",
        schema=CriteriaOutput,
        tracer=tracer,
        stub=_criteria_stub,
        model_calls=3,
    )
    return [c for c in output.criteria if c.points > 0]


def extract_requirements(
    rfp: RFP, criteria: list[EvaluationCriterion], tracer: Tracer
) -> tuple[list[Requirement], list[str]]:
    """Returns the validated requirements and the scanner hits no requirement covers ("possible misses")."""
    pages = {s.id: s for s in rfp.sections}
    categories = "\n".join(f"  - {c.value}: {d}" for c, d in category_definitions().items())
    names = json.dumps([c.name for c in criteria]) if criteria else "none"
    system = SYSTEM.format(categories=categories, criteria=names)

    @tool
    def scan_modal_verbs(section_id: str) -> str:
        """Rule-based scan of one page for shall/must/required statements aimed at the bidder."""
        section = pages.get(section_id)
        if not section:
            return "unknown section"
        return json.dumps([h.sentence for h in scan_modal_verbs_impl([section])])

    @tool
    def get_section(section_id: str) -> str:
        """Full text of one page, e.g. to read context from a neighbouring page."""
        section = pages.get(section_id)
        return section.text if section else "unknown section"

    extracted: list[ExtractedRequirement] = []
    for batch in _batches(rfp):
        text = "\n\n".join(f'<rfp section="{s.id}" page="{s.page_start}">\n{s.text}\n</rfp>' for s in batch)
        output = run_agent(
            name="rfp_analyst",
            kind="pro",
            system_prompt=system,
            tools=[scan_modal_verbs, get_section],
            prompt=f"Extract every bidder requirement from these pages.\n\n{text}",
            schema=AnalystOutput,
            tracer=tracer,
            stub=_analyst_stub(rfp, batch, criteria),
        )
        extracted.extend(output.requirements)
    return _validate(rfp, extracted, criteria, tracer)


scan_modal_verbs_impl = scan_modal_verbs


def _covers(a: str, b: str) -> bool:
    if a in b or b in a:
        return True
    wa, wb = set(a.split()), set(b.split())
    return len(wa & wb) / max(min(len(wa), len(wb)), 1) >= 0.7


def _match_criterion(name: str | None, criteria: list[EvaluationCriterion]) -> str | None:
    if not name:
        return None
    key = normalize(name)
    for c in criteria:
        if normalize(c.name) == key or key in normalize(c.name) or normalize(c.name) in key:
            return c.name
    return None


def _validate(
    rfp: RFP, extracted: list[ExtractedRequirement], criteria: list[EvaluationCriterion], tracer: Tracer
) -> tuple[list[Requirement], list[str]]:
    page_text = {s.page_start: normalize(s.text) for s in rfp.sections}
    full = " ".join(page_text.values())
    kept: list[Requirement] = []
    seen: list[str] = []
    for item in extracted:
        quote = normalize(item.quote)
        page = item.page
        if quote not in page_text.get(page, ""):
            page = next((p for p, t in page_text.items() if quote in t), None)
            if page is None:
                status = "spans pages" if quote in full else "not in source"
                tracer.add(
                    "rfp_analyst", "validation", name="quote_rejected", detail=f"{status}: {item.quote[:120]}"
                )
                if quote not in full:
                    continue
                page = item.page
        if any(_covers(quote, s) for s in seen):
            continue
        seen.append(quote)
        kept.append(
            Requirement(
                id=f"R{len(kept) + 1:03d}",
                section_id=f"P{page:02d}",
                page=page,
                quote=item.quote.strip(),
                summary=item.summary.strip() or item.quote[:80],
                obligation=item.obligation,
                category=item.category,
                critical=item.critical,
                criterion=_match_criterion(item.criterion, criteria),
            )
        )
    hits = scan_modal_verbs_impl(rfp.sections)
    misses = [h.sentence for h in hits if not any(_covers(normalize(h.sentence), s) for s in seen)]
    tracer.add(
        "rfp_analyst",
        "validation",
        name="extraction",
        detail=f"{len(kept)} requirements kept of {len(extracted)}; {len(misses)} possible misses",
    )
    return kept, misses
