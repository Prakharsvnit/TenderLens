"""Run the whole workflow locally, auto-approving both human checkpoints.

TL_LLM_MODE=stub python -m tenderlens.pipeline.local ../data/rfps/belle-isle-rfp-2026-04.pdf
TL_AWS_PROFILE=tenderlens python -m tenderlens.pipeline.local ../data/rfps/belle-isle-rfp-2026-04.pdf
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from ..ontology.models import Approval, Decision
from ..store import get_store
from . import steps


def run(pdf: Path, run_id: str | None = None, owner: str = "local") -> dict:
    store = get_store()
    run_id = run_id or uuid.uuid4().hex[:12]
    key = f"uploads/{run_id}/rfp.pdf"
    store.put_bytes(key, pdf.read_bytes())
    store.update_run(run_id, owner=owner, rfp_name=pdf.name, status="queued", pdf_key=key, mode="live")
    steps.parse({"run_id": run_id, "pdf_key": key})
    steps.extract({"run_id": run_id})
    steps.record_confirmation(run_id, owner)
    plan = steps.plan_assess({"run_id": run_id})
    for batch in plan["batches"]:
        steps.assess(batch)
    state = steps.merge_assess({"run_id": run_id})
    while True:
        steps.draft(state)
        state = steps.verify(state)
        if not state["rewrite"]:
            break
    decision = steps.decide({"run_id": run_id})["decision"]
    steps.record_approval(run_id, Approval(approver=owner, accepted=True, final_decision=Decision(decision)))
    return steps.publish({"run_id": run_id})


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    result = run(args.pdf, args.run_id)
    run_record = get_store().get_run(result["run_id"])
    print(
        json.dumps(
            {
                k: run_record.get(k)
                for k in (
                    "run_id",
                    "rfp_title",
                    "requirement_count",
                    "critical_count",
                    "possible_misses",
                    "status_counts",
                    "claims",
                    "unsupported_claims",
                    "decision",
                    "score_pct",
                    "kpis",
                )
            },
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
