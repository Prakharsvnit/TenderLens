"""Starts runs and resumes human checkpoints.

In AWS, Step Functions is the orchestrator. Locally, a thread-based stand-in runs the same nine steps with the
same two task-token checkpoints, so the web app can be developed and demoed without an AWS account.
"""

from __future__ import annotations

import json
import os
import threading
import traceback

from .config import get_settings
from .ontology.models import Approval, Decision
from .store import get_store

CONFIRM_TIMEOUT_S = int(os.environ.get("TL_CONFIRM_TIMEOUT", "120"))
APPROVE_TIMEOUT_S = int(os.environ.get("TL_APPROVE_TIMEOUT", "3600"))


class StepFunctionsOrchestrator:
    def start(self, run_id: str, pdf_key: str, started_at: str) -> None:
        from . import aws

        aws.stepfunctions().start_execution(
            stateMachineArn=os.environ["TL_STATE_MACHINE_ARN"],
            name=f"run-{run_id}",
            input=json.dumps({"run_id": run_id, "pdf_key": pdf_key, "started_at": started_at}),
        )

    def resume(self, token: str, output: dict) -> None:
        from . import aws

        aws.stepfunctions().send_task_success(taskToken=token, output=json.dumps(output))


class LocalOrchestrator:
    def __init__(self) -> None:
        self._waiting: dict[str, threading.Event] = {}

    def start(self, run_id: str, pdf_key: str, started_at: str) -> None:
        threading.Thread(target=self._run, args=(run_id, pdf_key, started_at), daemon=True).start()

    def resume(self, token: str, output: dict) -> None:
        event = self._waiting.get(token)
        if event:
            event.set()

    def _checkpoint(self, run_id: str, kind: str, timeout_s: int) -> None:
        token = f"{run_id}:{kind}"
        self._waiting[token] = threading.Event()
        status = "awaiting_confirmation" if kind == "confirm" else "awaiting_approval"
        get_store().update_run(run_id, **{f"{kind}_token": token, "status": status})
        self._waiting[token].wait(timeout_s)
        self._waiting.pop(token, None)

    def _run(self, run_id: str, pdf_key: str, started_at: str) -> None:
        from .pipeline import steps

        try:
            steps.parse({"run_id": run_id, "pdf_key": pdf_key, "started_at": started_at})
            steps.extract({"run_id": run_id})
            self._checkpoint(run_id, "confirm", CONFIRM_TIMEOUT_S)
            plan = steps.plan_assess({"run_id": run_id})
            for batch in plan["batches"]:
                steps.assess(batch)
            state = steps.merge_assess({"run_id": run_id})
            while True:
                steps.draft(state)
                state = steps.verify(state)
                if not state["rewrite"]:
                    break
            steps.decide({"run_id": run_id})
            self._checkpoint(run_id, "approve", APPROVE_TIMEOUT_S)
            steps.publish({"run_id": run_id})
        except Exception as exc:  # noqa: BLE001 - mirror the state machine's MarkFailed catch
            traceback.print_exc()
            get_store().update_run(run_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:500])


_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StepFunctionsOrchestrator() if get_settings().store == "aws" else LocalOrchestrator()
    return _orchestrator


def auto_approval(decision: str, reason: str = "auto (timeout)") -> Approval:
    return Approval(approver=reason, accepted=True, final_decision=Decision(decision))
