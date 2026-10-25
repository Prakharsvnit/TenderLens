"""Score a TenderLens run against the hand-labelled gold set: quality metrics plus team-level orchestration metrics.

    cd backend
    uv run python ../evals/run_eval.py --pdf ../data/rfps/belle-isle-rfp-2026-04.pdf   # fresh local run, then score
    uv run python ../evals/run_eval.py --run-id <id>                                    # score an existing local run
    uv run python ../evals/run_eval.py --latest                                         # score the newest complete run

Writes evals/reports/<run_id>.md and .json. Each fresh run calls the models, so run it on demand, not in CI.
The scoring itself lives in tenderlens.evaluation, shared with the app's "Run eval" button.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tenderlens.evaluation import GOLD_DIR, evaluate, to_markdown
from tenderlens.store import get_store

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id")
    group.add_argument("--pdf", type=Path)
    group.add_argument("--latest", action="store_true", help="score the newest complete run")
    parser.add_argument("--gold", type=Path, default=GOLD_DIR / "belle-isle.yaml")
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
