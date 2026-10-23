"""The nine workflow steps. Each takes and returns a small JSON-able dict (the Step Functions state) and
exchanges typed messages with the other agents through the blackboard store."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import cache

from ..agents import analyst, compliance, strategist, verifier, writer
from ..config import get_settings
from ..exports import draft_docx, matrix_xlsx
from ..guardrails import screen_text
from ..ontology.models import (
    RFP,
    Approval,
    AssessmentBatch,
    BidRecommendation,
    Category,
    ClaimVerdictLabel,
    ClaimVerdicts,
    DraftMessage,
    RequirementSet,
    RequirementStatus,
)
from ..parsing import parse_pdf
from ..retrieval import EvidenceIndex, build_index
from ..retrieval.embeddings import get_embedder
from ..scoring import load_policy
from ..store import Store, get_store
from ..trace import Tracer

BIDDER = os.environ.get("TL_BIDDER_NAME", "Cobalt Harbor IT Services")
INDEX_KEY = "library/index.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@cache
def _index() -> EvidenceIndex:
    settings = get_settings()
    store = get_store()
    if settings.store == "aws" and store.exists(INDEX_KEY):
        return EvidenceIndex.from_json(store.get_bytes(INDEX_KEY).decode())
    if settings.index_path.exists():
        index = EvidenceIndex.from_json(settings.index_path.read_text(encoding="utf-8"))
        if index.embedder_name.startswith("hash") == (settings.embedder == "hash"):
            return index
    return build_index(settings.library_dir, get_embedder(settings.embedder, settings.embed_model))


def _embedder():
    settings = get_settings()
    return get_embedder(
        "hash" if _index().embedder_name.startswith("hash") else "bedrock", settings.embed_model
    )


def _policy():
    settings = get_settings()
    store = get_store()
    if settings.store == "aws" and store.exists("policy/bid_policy.json"):
        from ..ontology.models import BidPolicy

        return BidPolicy.model_validate_json(store.get_bytes("policy/bid_policy.json"))
    return load_policy(settings.policy_path)


class _Step:
    """Context manager: a tracer bound to the run, flushed with token and cost totals at the end."""

    def __init__(self, run_id: str, step: str, store: Store | None = None):
        self.store = store or get_store()
        self.run_id = run_id
        run = self.store.get_run(run_id)
        self.cost_before = float(run.get("cost_usd", 0))
        self.tracer = Tracer(run_id, step, int(run.get("tokens_used", 0)))

    def __enter__(self) -> Tracer:
        self.store.update_run(self.run_id, step=self.tracer.step)
        return self.tracer

    def __exit__(self, exc_type, exc, tb):
        self.store.append_trace(self.tracer.events)
        fields = {
            "tokens_used": self.tracer.tokens_used,
            "cost_usd": round(self.cost_before + self.tracer.cost_usd, 6),
        }
        if exc:
            fields.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:500])
        self.store.update_run(self.run_id, **fields)
        return False


# 1. Parse and screen ------------------------------------------------------------------------------
def parse(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    store.update_run(run_id, status="running", started_at=event.get("started_at") or _now())
    with _Step(run_id, "parse") as tracer:
        rfp = parse_pdf(store.get_bytes(event["pdf_key"]), rfp_id=run_id)
        flagged = []
        for section in rfp.sections:
            result = screen_text(section.text)
            if result.flagged:
                flagged.append(section.page_start)
                tracer.add(
                    "guardrails",
                    "validation",
                    name="prompt_attack",
                    detail=f"page {section.page_start}: {result.detail}",
                )
                section.text = "[Page withheld: Guardrails flagged possible injected instructions.]"
        tracer.add(
            "guardrails",
            "validation",
            name="screened",
            detail=f"{len(rfp.sections)} pages, {len(flagged)} flagged",
        )
        store.put_json(f"runs/{run_id}/rfp.json", rfp)
        store.update_run(
            run_id, rfp_title=rfp.title, buyer=rfp.buyer.name, pages=rfp.page_count, flagged_pages=flagged
        )
    return {"run_id": run_id, "pages": rfp.page_count}


# 2. Extract --------------------------------------------------------------------------------------
def extract(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    with _Step(run_id, "extract") as tracer:
        rfp = RFP.model_validate(store.get_json(f"runs/{run_id}/rfp.json"))
        criteria = analyst.find_criteria(rfp, tracer)
        rfp.evaluation_criteria = criteria
        requirements, misses = analyst.extract_requirements(rfp, criteria, tracer)
        store.put_message(
            RequirementSet(
                run_id=run_id,
                produced_by="rfp_analyst",
                rfp=rfp,
                requirements=requirements,
                possible_misses=misses,
            )
        )
        store.update_run(
            run_id,
            status="awaiting_confirmation",
            requirement_count=len(requirements),
            critical_count=sum(r.critical for r in requirements),
            possible_misses=len(misses),
            criteria_count=len(criteria),
            confirm_requested_at=_now(),
        )
    return {"run_id": run_id, "requirements": len(requirements)}


# 3. Confirm (human) is a Step Functions task-token wait; see api.handler.confirm_requirements.


def record_confirmation(run_id: str, actor: str, edits: list[dict] | None = None) -> None:
    """Apply the bid manager's corrections (category, critical, obligation, removal) and log them."""
    store = get_store()
    reqs = store.get_message(run_id, RequirementSet)
    by_id = {r.id: r for r in reqs.requirements}
    removed = set()
    for edit in edits or []:
        req = by_id.get(edit.get("id", ""))
        if not req:
            continue
        if edit.get("remove"):
            removed.add(req.id)
        for field in ("category", "critical", "obligation"):
            if field in edit:
                setattr(req, field, edit[field])
    reqs.requirements = [r for r in reqs.requirements if r.id not in removed]
    store.put_message(RequirementSet.model_validate(reqs.model_dump()))
    store.append_audit(run_id, actor, "confirm_requirements", {"edits": edits or []})
    run = store.get_run(run_id)
    waited = 0.0
    if run.get("confirm_requested_at"):
        waited = (datetime.now(UTC) - datetime.fromisoformat(run["confirm_requested_at"])).total_seconds()
    store.update_run(run_id, status="running", confirmed_by=actor, confirm_wait_s=round(waited, 1))


# 4. Assess (Map) ---------------------------------------------------------------------------------
def plan_assess(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    reqs = store.get_message(run_id, RequirementSet)
    size = get_settings().assess_batch_size
    ids = [r.id for r in reqs.requirements]
    batches = [
        {"run_id": run_id, "batch": n, "ids": ids[i : i + size]}
        for n, i in enumerate(range(0, len(ids), size))
    ]
    store.update_run(run_id, status="running", assess_batches=len(batches))
    return {"run_id": run_id, "batches": batches}


def assess(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    with _Step(run_id, f"assess-{event['batch']}") as tracer:
        reqs = store.get_message(run_id, RequirementSet)
        batch = [r for r in reqs.requirements if r.id in set(event["ids"])]
        assessments, gaps, evidence = compliance.assess_batch(batch, _index(), _embedder(), BIDDER, tracer)
        part = AssessmentBatch(
            run_id=run_id,
            produced_by="compliance_analyst",
            assessments=assessments,
            gaps=gaps,
            evidence=evidence,
        )
        store.put_json(f"runs/{run_id}/assess/batch-{event['batch']:03d}.json", part)
    return {"run_id": run_id, "batch": event["batch"]}


def merge_assess(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    run = store.get_run(run_id)
    parts = [
        AssessmentBatch.model_validate(store.get_json(f"runs/{run_id}/assess/batch-{n:03d}.json"))
        for n in range(int(run["assess_batches"]))
    ]
    evidence = {e.id: e for p in parts for e in p.evidence}
    merged = AssessmentBatch(
        run_id=run_id,
        produced_by="compliance_analyst",
        assessments=[a for p in parts for a in p.assessments],
        gaps=[g for p in parts for g in p.gaps],
        evidence=list(evidence.values()),
    )
    store.put_message(merged)
    counts = {s.value: sum(a.status == s for a in merged.assessments) for s in RequirementStatus}
    store.update_run(run_id, status_counts=counts, gap_count=len(merged.gaps))
    return {"run_id": run_id, "round": 0}


# 5. Draft and 6. Verify (loop) -------------------------------------------------------------------
def draft(event: dict) -> dict:
    run_id, store, rnd = event["run_id"], get_store(), int(event.get("round", 0))
    with _Step(run_id, f"draft-{rnd}") as tracer:
        reqs = store.get_message(run_id, RequirementSet)
        assessed = store.get_message(run_id, AssessmentBatch)
        if rnd == 0:
            sections = writer.draft(
                reqs.requirements, assessed.assessments, assessed.evidence, BIDDER, tracer
            )
        else:
            previous = store.get_message(run_id, DraftMessage)
            verdicts = store.get_message(run_id, ClaimVerdicts)
            flagged = [v for v in verdicts.verdicts if v.verdict != ClaimVerdictLabel.supported]
            sections = writer.rewrite(previous.sections, flagged, assessed.evidence, BIDDER, tracer)
        store.put_message(
            DraftMessage(run_id=run_id, produced_by="proposal_writer", sections=sections, round=rnd)
        )
    return {"run_id": run_id, "round": rnd}


def verify(event: dict) -> dict:
    run_id, store, rnd = event["run_id"], get_store(), int(event.get("round", 0))
    with _Step(run_id, f"verify-{rnd}") as tracer:
        reqs = store.get_message(run_id, RequirementSet)
        assessed = store.get_message(run_id, AssessmentBatch)
        current = store.get_message(run_id, DraftMessage)
        previous = store.get_message(run_id, ClaimVerdicts).verdicts if rnd > 0 else []
        kept = {v.claim_id: v for v in previous if v.verdict == ClaimVerdictLabel.supported}
        claims_now = {c.id for s in current.sections for c in s.claims}
        to_check = [
            s.model_copy(update={"claims": [c for c in s.claims if c.id not in kept]})
            for s in current.sections
        ]
        new = verifier.verify(to_check, assessed.evidence, reqs.requirements, tracer)
        verdicts = [v for v in kept.values() if v.claim_id in claims_now] + new
        store.put_message(
            ClaimVerdicts(run_id=run_id, produced_by="claim_verifier", verdicts=verdicts, round=rnd)
        )
        unsupported = sum(v.verdict != ClaimVerdictLabel.supported for v in verdicts)
        rewrite = unsupported > 0 and rnd < get_settings().max_rewrite_rounds
        fields = {"claims": len(verdicts), "unsupported_claims": unsupported, "rewrite_rounds": rnd}
        if not rewrite:
            fields["draft_ready_at"] = _now()
        store.update_run(run_id, **fields)
    return {
        "run_id": run_id,
        "round": rnd + 1 if rewrite else rnd,
        "rewrite": rewrite,
        "unsupported": unsupported,
    }


# 7. Decide ---------------------------------------------------------------------------------------
def decide(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    with _Step(run_id, "decide") as tracer:
        reqs = store.get_message(run_id, RequirementSet)
        assessed = store.get_message(run_id, AssessmentBatch)
        decision = strategist.strategize(
            reqs.requirements,
            assessed.assessments,
            assessed.gaps,
            reqs.rfp.evaluation_criteria,
            _policy(),
            BIDDER,
            tracer,
        )
        store.put_message(BidRecommendation(run_id=run_id, produced_by="bid_strategist", decision=decision))
        store.update_run(
            run_id,
            status="awaiting_approval",
            decision=decision.decision.value,
            score_pct=decision.score_pct,
            approval_requested_at=_now(),
        )
    return {"run_id": run_id, "decision": decision.decision.value}


# 8. Approve (human) is a Step Functions task-token wait; see api.handler.approve.


def record_approval(run_id: str, approval: Approval) -> None:
    store = get_store()
    store.put_json(f"runs/{run_id}/approval.json", approval)
    store.append_audit(
        run_id,
        approval.approver,
        "approve" if approval.accepted else "override",
        approval.model_dump(mode="json"),
    )
    store.update_run(run_id, final_decision=approval.final_decision.value, approved_by=approval.approver)


# 9. Publish ---------------------------------------------------------------------------------------
def publish(event: dict) -> dict:
    run_id, store = event["run_id"], get_store()
    with _Step(run_id, "publish"):
        reqs = store.get_message(run_id, RequirementSet)
        assessed = store.get_message(run_id, AssessmentBatch)
        draft_msg = store.get_message(run_id, DraftMessage)
        verdicts = store.get_message(run_id, ClaimVerdicts)
        rec = store.get_message(run_id, BidRecommendation)
        store.put_bytes(f"runs/{run_id}/matrix.xlsx", matrix_xlsx(reqs, assessed, rec))
        store.put_bytes(f"runs/{run_id}/draft.docx", draft_docx(reqs, draft_msg, verdicts, BIDDER))
        kpis = compute_kpis(store.get_run(run_id), reqs, verdicts, draft_msg)
        store.update_run(run_id, status="complete", completed_at=_now(), kpis=kpis)
    return {"run_id": run_id, "kpis": kpis}


def compute_kpis(run: dict, reqs: RequirementSet, verdicts: ClaimVerdicts, draft_msg: DraftMessage) -> dict:
    supported = {v.claim_id for v in verdicts.verdicts if v.verdict == ClaimVerdictLabel.supported}
    answered = {
        r for s in draft_msg.sections for c in s.claims if c.id in supported for r in c.requirement_ids
    }
    eligible = [r for r in reqs.requirements if r.category != Category.submission]
    mandatory = [r for r in eligible if r.obligation == "mandatory"]
    started = datetime.fromisoformat(run.get("started_at", run["created_at"]))
    ready = datetime.fromisoformat(run.get("draft_ready_at", _now()))
    ttfd = (ready - started).total_seconds() - float(run.get("confirm_wait_s", 0))
    total_claims = len(verdicts.verdicts)
    return {
        "time_to_first_draft_s": round(max(ttfd, 0), 1),
        "requirement_coverage": round(
            len([r for r in eligible if r.id in answered]) / max(len(eligible), 1), 3
        ),
        "mandatory_coverage": round(
            len([r for r in mandatory if r.id in answered]) / max(len(mandatory), 1), 3
        ),
        "evidence_backed_claim_rate": round(len(supported) / max(total_claims, 1), 3),
        "critical_requirements": sum(r.critical for r in reqs.requirements),
        "possible_misses": len(reqs.possible_misses),
        "cost_usd": round(float(run.get("cost_usd", 0)), 4),
        "tokens": int(run.get("tokens_used", 0)),
    }
