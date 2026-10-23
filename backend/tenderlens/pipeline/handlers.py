"""Lambda entry points: one function per workflow step, wired together by the Step Functions state machine."""

from __future__ import annotations

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from ..store import get_store
from . import steps

logger = Logger(service="tenderlens")
tracer = Tracer(service="tenderlens")
metrics = Metrics(namespace="TenderLens", service="pipeline")


def _wrap(step):
    @tracer.capture_lambda_handler
    @logger.inject_lambda_context(log_event=False)
    def handler(event, context):
        logger.append_keys(run_id=event.get("run_id"))
        logger.info(f"step {step.__name__} started")
        return step(event)

    handler.__name__ = step.__name__
    return handler


parse = _wrap(steps.parse)
extract = _wrap(steps.extract)
plan_assess = _wrap(steps.plan_assess)
assess = _wrap(steps.assess)
merge_assess = _wrap(steps.merge_assess)
draft = _wrap(steps.draft)
verify = _wrap(steps.verify)
decide = _wrap(steps.decide)


@_wrap
def checkpoint(event):
    """Stores a Step Functions task token so the API can resume the run after a person acts."""
    kind = event["kind"]  # "confirm" or "approve"
    status = "awaiting_confirmation" if kind == "confirm" else "awaiting_approval"
    get_store().update_run(event["run_id"], **{f"{kind}_token": event["token"], "status": status})
    return {"ok": True}


@metrics.log_metrics
@_wrap
def publish(event):
    result = steps.publish(event)
    kpis = result["kpis"]
    metrics.add_metric("TimeToFirstDraft", MetricUnit.Seconds, kpis["time_to_first_draft_s"])
    metrics.add_metric("RequirementCoverage", MetricUnit.Percent, kpis["requirement_coverage"] * 100)
    metrics.add_metric(
        "EvidenceBackedClaimRate", MetricUnit.Percent, kpis["evidence_backed_claim_rate"] * 100
    )
    metrics.add_metric("RunCostUSD", MetricUnit.Count, kpis["cost_usd"])
    return result


@_wrap
def mark_failed(event):
    error = event.get("error", {})
    get_store().update_run(
        event["run_id"], status="failed", error=f"{error.get('Error', '')}: {error.get('Cause', '')}"[:500]
    )
    return {"run_id": event["run_id"], "status": "failed"}
