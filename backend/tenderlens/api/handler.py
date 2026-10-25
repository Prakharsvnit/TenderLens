"""HTTP API behind API Gateway (Cognito JWT authorizer). Starts runs, serves results and resumes checkpoints."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, date, datetime

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)

from ..config import get_settings
from ..evaluation import evaluate, gold_for
from ..ontology.models import (
    Approval,
    AssessmentBatch,
    BidRecommendation,
    ClaimVerdicts,
    Decision,
    DraftMessage,
    RequirementSet,
)
from ..orchestrator import get_orchestrator
from ..pipeline import steps
from ..store import get_store

logger = Logger(service="tenderlens-api")
cors = CORSConfig(
    allow_origin=os.environ.get("TL_WEB_ORIGIN", "*"), allow_headers=["Authorization", "Content-Type"]
)
app = APIGatewayHttpResolver(cors=cors)

DAILY_CAP = int(os.environ.get("TL_DAILY_RUN_CAP", "3"))
DEV_BASE_URL = os.environ.get("TL_DEV_BASE_URL", "http://localhost:8787")
MESSAGES = (RequirementSet, AssessmentBatch, DraftMessage, ClaimVerdicts, BidRecommendation)


def _local() -> bool:
    return get_settings().store != "aws"


def _user() -> str:
    claims = app.current_event.request_context.authorizer.jwt_claim or {}
    user = claims.get("email") or claims.get("cognito:username") or claims.get("sub")
    if not user:
        raise UnauthorizedError("not signed in")
    return user


def _viewer() -> bool:
    """Members of the Cognito "viewers" group can open shared runs but not start or act on runs."""
    claims = app.current_event.request_context.authorizer.jwt_claim or {}
    return "viewers" in str(claims.get("cognito:groups", ""))


def _owned(run_id: str) -> dict:
    run = _run(run_id)
    if run.get("owner") != _user():
        raise ForbiddenError("only the person who started this run can act on it")
    return run


def _param(name: str, default: str) -> str:
    if _local():
        return os.environ.get(name.replace("/tenderlens/", "TL_").replace("-", "_").upper(), default)
    from .. import aws

    try:
        return aws.ssm().get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:  # noqa: BLE001 - a missing parameter means the default applies
        return default


def _live_status() -> dict:
    enabled = _param("/tenderlens/live-runs", "on").lower() == "on"
    until = _param("/tenderlens/live-until", "none").strip().lower()
    if until not in ("", "none", "-"):
        enabled = enabled and date.today() <= date.fromisoformat(until)
    return {
        "live_runs": enabled,
        "live_until": None if until in ("", "none", "-") else until,
        "daily_cap": DAILY_CAP,
    }


def _url(method: str, key: str) -> str:
    if _local():
        return f"{DEV_BASE_URL}/dev/{'upload' if method == 'put_object' else 'files'}/{key}"
    from .. import aws

    params = {"Bucket": get_settings().bucket, "Key": key}
    if method == "put_object":
        params["ContentType"] = "application/pdf"
    return aws.s3().generate_presigned_url(method, Params=params, ExpiresIn=900)


def _run(run_id: str) -> dict:
    try:
        run = get_store().get_run(run_id)
    except (KeyError, FileNotFoundError) as exc:
        raise NotFoundError(f"run {run_id} not found") from exc
    if run.get("owner") != _user() and not run.get("shared"):
        raise NotFoundError(f"run {run_id} not found")
    return run


def _public(run: dict) -> dict:
    return {k: v for k, v in run.items() if not k.endswith("_token")}


@app.get("/config")
def config():
    status = _live_status()
    if _viewer():
        status["live_runs"] = False
    return {**status, "user": _user(), "viewer": _viewer()}


@app.get("/runs")
def list_runs():
    user = _user()
    runs = [r for r in get_store().list_runs() if r.get("owner") == user or r.get("shared")]
    return {"runs": [_public(r) for r in runs if not str(r.get("run_id", "")).startswith("_")]}


@app.post("/runs")
def create_run():
    body = app.current_event.json_body or {}
    if _viewer():
        raise ForbiddenError("This login can view shared runs but not start new ones.")
    if not _live_status()["live_runs"]:
        raise BadRequestError("Live runs are switched off. Past runs are still available.")
    store = get_store()
    used = store.increment_quota(datetime.now(UTC).date().isoformat())
    if used > DAILY_CAP:
        raise BadRequestError(f"The daily limit of {DAILY_CAP} live runs is reached. Try again tomorrow.")
    run_id = uuid.uuid4().hex[:12]
    key = f"uploads/{run_id}/rfp.pdf"
    store.update_run(
        run_id,
        owner=_user(),
        rfp_name=body.get("filename", "rfp.pdf"),
        status="uploading",
        pdf_key=key,
        mode="live",
        shared=False,
    )
    return {"run_id": run_id, "upload_url": _url("put_object", key)}


@app.post("/runs/<run_id>/start")
def start_run(run_id: str):
    run = _owned(run_id)
    if run.get("status") != "uploading":
        raise BadRequestError("run already started")
    started = datetime.now(UTC).isoformat()
    get_store().update_run(run_id, status="queued", started_at=started)
    get_orchestrator().start(run_id, run["pdf_key"], started)
    return {"run_id": run_id, "status": "queued"}


def _view(run: dict) -> dict:
    """Everything the run page shows: the run record, the agents' messages, approval, audit and eval."""
    run_id, store = run["run_id"], get_store()
    settings = get_settings()
    limits = {
        "run_token_budget": settings.run_token_budget,
        "grounding_threshold": settings.grounding_threshold,
    }
    view: dict = {"run": _public(run), "limits": limits}
    for cls in MESSAGES:
        key = f"runs/{run_id}/{cls.__name__}.json"
        if store.exists(key):
            view[cls.__name__] = json.loads(store.get_bytes(key))
    for name in ("approval", "audit", "eval"):
        key = f"runs/{run_id}/{name}.json"
        if store.exists(key):
            view[name] = store.get_json(key)
    return view


@app.get("/runs/<run_id>")
def get_run(run_id: str):
    return _view(_run(run_id))


@app.get("/runs/<run_id>/trace")
def get_trace(run_id: str):
    _run(run_id)
    return {"events": get_store().get_trace(run_id)}


@app.get("/runs/<run_id>/audit")
def get_audit(run_id: str):
    _run(run_id)
    store = get_store()
    key = f"runs/{run_id}/audit.json"
    return {"events": store.get_json(key) if store.exists(key) else []}


def _token(run: dict, kind: str, status: str) -> str:
    token = run.get(f"{kind}_token")
    if run.get("status") != status or not token:
        raise BadRequestError(f"this run is not waiting for {kind}; refresh and try again")
    return token


def _resume(run: dict, kind: str, token: str) -> None:
    get_store().update_run(run["run_id"], **{f"{kind}_token": ""})
    get_orchestrator().resume(token, {kind: True})


@app.post("/runs/<run_id>/confirm")
def confirm(run_id: str):
    run = _owned(run_id)
    token = _token(run, "confirm", "awaiting_confirmation")
    edits = (app.current_event.json_body or {}).get("edits", [])
    steps.record_confirmation(run_id, _user(), edits)
    _resume(run, "confirm", token)
    return {"ok": True}


@app.post("/runs/<run_id>/approve")
def approve(run_id: str):
    run = _owned(run_id)
    token = _token(run, "approve", "awaiting_approval")
    body = app.current_event.json_body or {}
    try:
        approval = Approval(
            approver=_user(),
            accepted=bool(body.get("accepted", True)),
            final_decision=Decision(body.get("final_decision") or run["decision"]),
            reason=body.get("reason", ""),
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    steps.record_approval(run_id, approval)
    _resume(run, "approve", token)
    return {"ok": True}


@app.post("/runs/<run_id>/eval")
def run_eval(run_id: str):
    """Scores a finished run against the gold set for its RFP and saves the report with the run."""
    run = _owned(run_id)
    if run.get("status") != "complete":
        raise BadRequestError("the run has to finish before it can be evaluated")
    gold = gold_for(run)
    if gold is None:
        raise BadRequestError("there is no gold set for this RFP, so it can't be scored")
    report = evaluate(run_id, gold)
    get_store().put_json(f"runs/{run_id}/eval.json", report)
    return report


@app.get("/runs/<run_id>/exports/<kind>")
def export(run_id: str, kind: str):
    _run(run_id)
    return _export_url(run_id, kind)


def _export_url(run_id: str, kind: str) -> dict:
    names = {"matrix": "matrix.xlsx", "draft": "draft.docx"}
    if kind not in names:
        raise NotFoundError("unknown export")
    return {"url": _url("get_object", f"runs/{run_id}/{names[kind]}")}


# --- Public, read-only demo (no sign-in; API Gateway routes /public/* without the authorizer) ---------------


def _shared(run_id: str) -> dict:
    try:
        run = get_store().get_run(run_id)
    except (KeyError, FileNotFoundError) as exc:
        raise NotFoundError(f"run {run_id} not found") from exc
    if not run.get("shared"):
        raise NotFoundError(f"run {run_id} not found")
    return run


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _redact(data, run: dict):
    """Replaces sign-in emails with role names, and any other email with "bid team", before showing publicly."""
    text = json.dumps(data, default=str)
    for key, role in (("owner", "bid manager"), ("approved_by", "approver")):
        if run.get(key):
            text = text.replace(str(run[key]), role)
    return json.loads(_EMAIL.sub("bid team", text))


@app.get("/public/runs")
def public_runs():
    runs = [
        r for r in get_store().list_runs() if r.get("shared") and not str(r.get("run_id", "")).startswith("_")
    ]
    return {"runs": [_redact(_public(r), r) for r in runs]}


@app.get("/public/runs/<run_id>")
def public_run(run_id: str):
    run = _shared(run_id)
    return _redact(_view(run), run)


@app.get("/public/runs/<run_id>/trace")
def public_trace(run_id: str):
    run = _shared(run_id)
    return _redact({"events": get_store().get_trace(run_id)}, run)


@app.get("/public/runs/<run_id>/exports/<kind>")
def public_export(run_id: str, kind: str):
    _shared(run_id)
    return _export_url(run_id, kind)


@logger.inject_lambda_context(log_event=False)
def handler(event, context):
    return app.resolve(event, context)
