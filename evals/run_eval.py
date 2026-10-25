"""Score a TenderLens run against the hand-labelled gold set: quality metrics plus team-level orchestration metrics.

    cd backend
    uv run python ../evals/run_eval.py --pdf ../data/rfps/belle-isle-rfp-2026-04.pdf   # fresh local run, then score
    uv run python ../evals/run_eval.py --run-id <id>                                    # score an existing local run
    uv run python ../evals/run_eval.py --latest                                         # score the newest complete run

Writes evals/reports/<run_id>.md and .json. Each fresh run calls the models, so run it on demand, not in CI.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from tenderlens.ontology.models import (
    AssessmentBatch,
    BidRecommendation,
    ClaimVerdictLabel,
    ClaimVerdicts,
    DraftMessage,
    RequirementSet,
)
from tenderlens.parsing import normalize
from tenderlens.store import get_store

ROOT = Path(__file__).resolve().parent
TARGETS = {
    "extraction_recall": 0.95,
    "critical_recall": 1.0,
    "extraction_precision": 0.90,
    "status_accuracy": 0.85,
    "citation_validity": 1.0,
    "evidence_backed_claim_rate": 0.95,
    "task_completion": 1.0,
    "handoff_validity": 1.0,
    "redundant_tool_call_rate": 0.05,
}


def _matches(gold_quote: str, extracted_quote: str) -> bool:
    g, e = normalize(gold_quote), normalize(extracted_quote)
    if g in e or e in g:
        return True
    gw, ew = set(g.split()), set(e.split())
    return len(gw & ew) / max(len(gw), 1) >= 0.6


def evaluate(run_id: str, gold_path: Path) -> dict:
    store = get_store()
    gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    run = store.get_run(run_id)

    messages, handoff_errors = {}, []
    for cls in (RequirementSet, AssessmentBatch, DraftMessage, ClaimVerdicts, BidRecommendation):
        try:
            messages[cls.__name__] = store.get_message(run_id, cls)  # schema-checked on read
        except Exception as exc:  # noqa: BLE001 - a missing or invalid hand-off is what we measure
            handoff_errors.append(f"{cls.__name__}: {type(exc).__name__}")
    reqs = messages.get("RequirementSet")
    assessed = messages.get("AssessmentBatch")
    verdicts = messages.get("ClaimVerdicts")
    draft = messages.get("DraftMessage")
    rec = messages.get("BidRecommendation")

    extracted = reqs.requirements if reqs else []
    status = {a.requirement_id: a.status for a in (assessed.assessments if assessed else [])}
    matched: dict[str, str] = {}
    for g in gold["requirements"]:
        hit = next((r for r in extracted if _matches(g["quote"], r.quote)), None)
        if hit:
            matched[g["id"]] = hit.id
    critical = [g for g in gold["requirements"] if g["critical"]]
    scored = [g for g in gold["requirements"] if g["expected_status"] and g["id"] in matched]
    correct = [g for g in scored if status.get(matched[g["id"]]) in g["expected_status"]]
    valid = [g["quote"] for g in gold["requirements"]] + gold.get("also_valid", [])
    precise = [r for r in extracted if any(_matches(q, r.quote) for q in valid)]

    evidence_ok, evidence_total = 0, 0
    known = {e.id for e in assessed.evidence} if assessed else set()
    for a in assessed.assessments if assessed else []:
        evidence_total += len(a.evidence_ids)
        evidence_ok += sum(e in known for e in a.evidence_ids)
    for section in draft.sections if draft else []:
        for claim in section.claims:
            evidence_total += len(claim.evidence_ids)
            evidence_ok += sum(e in known for e in claim.evidence_ids)
    supported = sum(v.verdict == ClaimVerdictLabel.supported for v in (verdicts.verdicts if verdicts else []))

    trace = store.get_trace(run_id)
    # A repeat is the same tool called with the same arguments by the same agent in the same step. Runs traced
    # before arguments were recorded fall back to comparing outputs.
    tool_calls = [
        (e["step"], e["agent"], e["name"], e.get("args") or e["detail"])
        for e in trace
        if e["kind"] == "tool_call" and not str(e["detail"]).startswith("Returning structured response")
    ]
    duplicates = sum(n - 1 for n in Counter(tool_calls).values() if n > 1)
    per_agent: dict[str, dict] = defaultdict(lambda: {"model_calls": 0, "tool_calls": 0, "tokens": 0, "cost_usd": 0.0,
                                                     "seconds": 0.0, "validations": 0})
    for e in trace:
        s = per_agent[e["agent"]]
        if e["kind"] == "model_call":
            s["model_calls"] += 1
            s["tokens"] += e["tokens_in"] + e["tokens_out"]
            s["cost_usd"] += e["cost_usd"]
        elif e["kind"] == "tool_call":
            s["tool_calls"] += 1
        elif e["kind"] == "validation":
            s["validations"] += 1
        elif e["kind"] == "agent_end":
            s["seconds"] += e["latency_ms"] / 1000

    metrics = {
        "extraction_recall": len(matched) / len(gold["requirements"]),
        "critical_recall": sum(g["id"] in matched for g in critical) / max(len(critical), 1),
        "extraction_precision": len(precise) / max(len(extracted), 1),
        "status_accuracy": len(correct) / max(len(scored), 1),
        "citation_validity": evidence_ok / max(evidence_total, 1),
        "evidence_backed_claim_rate": supported / max(len(verdicts.verdicts) if verdicts else 0, 1),
        "task_completion": 1.0 if run.get("status") == "complete" and not handoff_errors else 0.0,
        "handoff_validity": (5 - len(handoff_errors)) / 5,
        "redundant_tool_call_rate": duplicates / max(len(tool_calls), 1),
    }
    return {
        "run_id": run_id,
        "rfp": gold["rfp"],
        "metrics": {k: round(v, 3) for k, v in metrics.items()},
        "rewrite_rounds": run.get("rewrite_rounds", 0),
        "decision": rec.decision.decision.value if rec else None,
        "expected_decision": gold.get("expected_decision"),
        "score_pct": rec.decision.score_pct if rec else None,
        "missed_critical": [g["id"] for g in critical if g["id"] not in matched],
        "missed": [{"gold": g["id"], "page": g.get("page"), "quote": g["quote"]}
                   for g in gold["requirements"] if g["id"] not in matched],
        "not_in_gold": [{"id": r.id, "page": r.page, "quote": r.quote}
                        for r in extracted if r not in precise],
        "wrong_status": [
            {"gold": g["id"], "got": status.get(matched[g["id"]]), "expected": g["expected_status"]}
            for g in scored if g not in correct
        ],
        "handoff_errors": handoff_errors,
        "per_agent": {k: {**v, "cost_usd": round(v["cost_usd"], 5), "seconds": round(v["seconds"], 1)}
                      for k, v in per_agent.items()},
        "kpis": run.get("kpis"),
        "llm_mode": run.get("llm_mode"),
    }


def to_markdown(report: dict) -> str:
    def mark(name: str, value: float) -> str:
        target = TARGETS[name]
        ok = value <= target if name == "redundant_tool_call_rate" else value >= target
        return "pass" if ok else "below target"

    lines = [
        f"# Eval report: run `{report['run_id']}` on {report['rfp']}",
        "",
        f"Decision: **{report['decision']}** (expected {report['expected_decision']}), "
        f"score {report['score_pct']:.0%}." if report["score_pct"] is not None else "No decision.",
        "",
        "| Metric | Value | Target | Result |",
        "| --- | --- | --- | --- |",
    ]
    for name, value in report["metrics"].items():
        sign = "≤" if name == "redundant_tool_call_rate" else "≥"
        lines.append(f"| {name.replace('_', ' ')} | {value:.0%} | {sign} {TARGETS[name]:.0%} | {mark(name, value)} |")
    lines += ["", f"Rewrite rounds: {report['rewrite_rounds']}", "", "## Per agent", "",
              "| Agent | Model calls | Tool calls | Validations | Tokens | Cost (USD) | Time (s) |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for agent, s in report["per_agent"].items():
        lines.append(f"| {agent} | {s['model_calls']} | {s['tool_calls']} | {s['validations']} | {s['tokens']:,} | "
                     f"{s['cost_usd']:.4f} | {s['seconds']} |")
    if report["missed_critical"]:
        lines += ["", f"Missed critical requirements: {', '.join(report['missed_critical'])}"]
    if report.get("missed"):
        lines += ["", "## Missed gold requirements", ""]
        lines += [f"- {m['gold']} (p{m['page']}): {m['quote'][:110]}" for m in report["missed"]]
    if report.get("not_in_gold"):
        lines += ["", "## Extracted but not a valid requirement in the gold set", ""]
        lines += [f"- {r['id']} (p{r['page']}): {r['quote'][:110]}" for r in report["not_in_gold"]]
    if report["wrong_status"]:
        lines += ["", "## Status mismatches", ""]
        lines += [f"- {w['gold']}: got `{w['got']}`, expected {w['expected']}" for w in report["wrong_status"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id")
    group.add_argument("--pdf", type=Path)
    group.add_argument("--latest", action="store_true", help="score the newest complete run")
    parser.add_argument("--gold", type=Path, default=ROOT / "gold" / "belle-isle.yaml")
    args = parser.parse_args()
    run_id = args.run_id
    if args.latest:
        complete = [r for r in get_store().list_runs() if r.get("status") == "complete"]
        if not complete:
            raise SystemExit("no complete runs found")
        run_id = complete[0]["run_id"]
    if args.pdf:
        from tenderlens.config import get_settings
        from tenderlens.pipeline import local

        run_id = local.run(args.pdf, owner="eval")["run_id"]
        get_store().update_run(run_id, llm_mode=get_settings().llm_mode)
    report = evaluate(run_id, args.gold)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"{run_id}.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    (out / f"{run_id}.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))


if __name__ == "__main__":
    main()
