"""The HTTP API end to end on the local orchestrator: create, upload, start, both checkpoints, exports, governance."""

import json
import time
from types import SimpleNamespace

import pytest

from tenderlens import orchestrator
from tenderlens.api import handler
from tenderlens.store import LocalStore, set_store

USER = "bid.manager@example.com"


def call(method: str, path: str, body: dict | None = None, user: str = USER) -> tuple[int, dict]:
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": method, "path": path, "sourceIp": "127.0.0.1"},
            "authorizer": {"jwt": {"claims": {"email": user}, "scopes": []}},
            "stage": "$default",
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }
    result = handler.app.resolve(event, SimpleNamespace(function_name="test", aws_request_id="t"))
    return result["statusCode"], json.loads(result["body"] or "{}")


def wait_for(run_id: str, status: str, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, view = call("GET", f"/runs/{run_id}")
        if view["run"]["status"] == status:
            return view
        assert view["run"]["status"] != "failed", view["run"].get("error")
        time.sleep(0.5)
    raise AssertionError(f"run {run_id} never reached {status}")


@pytest.fixture
def store(tmp_path, monkeypatch):
    local = LocalStore(tmp_path)
    set_store(local)
    monkeypatch.setattr(orchestrator, "_orchestrator", orchestrator.LocalOrchestrator())
    return local


def start_run(store, pdf) -> str:
    status, created = call("POST", "/runs", {"filename": "belle-isle.pdf"})
    assert status == 200, created
    key = created["upload_url"].split("/dev/upload/")[1]
    store.put_bytes(key, pdf.read_bytes())
    status, started = call("POST", f"/runs/{created['run_id']}/start", {})
    assert status == 200 and started["status"] == "queued"
    return created["run_id"]


def test_full_run_through_both_checkpoints(store, belle_isle_pdf):
    run_id = start_run(store, belle_isle_pdf)
    view = wait_for(run_id, "awaiting_confirmation")
    assert "confirm_token" not in view["run"]  # task tokens never leave the API
    first = view["RequirementSet"]["requirements"][0]["id"]
    status, _ = call("POST", f"/runs/{run_id}/confirm", {"edits": [{"id": first, "critical": True}]})
    assert status == 200

    view = wait_for(run_id, "awaiting_approval")
    assert view["RequirementSet"]["requirements"][0]["critical"] is True  # the correction was applied
    status, error = call("POST", f"/runs/{run_id}/approve", {"accepted": False, "final_decision": "no_bid"})
    assert status == 400 and "reason" in error["message"]  # an override needs a reason
    status, _ = call(
        "POST",
        f"/runs/{run_id}/approve",
        {"accepted": False, "final_decision": "no_bid", "reason": "Partner not available"},
    )
    assert status == 200

    view = wait_for(run_id, "complete")
    assert view["run"]["final_decision"] == "no_bid"
    assert view["approval"]["reason"] == "Partner not available"
    for kind in ("matrix", "draft"):
        status, export = call("GET", f"/runs/{run_id}/exports/{kind}")
        assert status == 200 and export["url"].endswith((".xlsx", ".docx"))
    status, audit = call("GET", f"/runs/{run_id}/audit")
    assert [e["action"] for e in audit["events"]] == ["confirm_requirements", "override"]
    _, trace = call("GET", f"/runs/{run_id}/trace")
    assert {e["agent"] for e in trace["events"]} >= {"rfp_analyst", "compliance_analyst", "bid_strategist"}


def test_runs_are_private_to_their_owner(store):
    run_id = call("POST", "/runs", {"filename": "belle-isle.pdf"})[1]["run_id"]
    assert call("GET", f"/runs/{run_id}")[0] == 200
    status, _ = call("GET", f"/runs/{run_id}", user="someone.else@example.com")
    assert status == 404
    _, listing = call("GET", "/runs", user="someone.else@example.com")
    assert listing["runs"] == []
    store.update_run(run_id, shared=True)
    status, _ = call("GET", f"/runs/{run_id}", user="someone.else@example.com")
    assert status == 200


def test_daily_cap_and_live_switch(store, monkeypatch):
    for _ in range(handler.DAILY_CAP):
        assert call("POST", "/runs", {"filename": "x.pdf"})[0] == 200
    status, error = call("POST", "/runs", {"filename": "x.pdf"})
    assert status == 400 and "daily limit" in error["message"]

    monkeypatch.setenv("TL_LIVE_RUNS", "off")
    status, error = call("POST", "/runs", {"filename": "x.pdf"})
    assert status == 400 and "switched off" in error["message"]
    _, config = call("GET", "/config")
    assert config["live_runs"] is False


def test_confirm_checkpoint_times_out_and_continues(store, belle_isle_pdf, monkeypatch):
    monkeypatch.setattr(orchestrator, "CONFIRM_TIMEOUT_S", 1)
    monkeypatch.setattr(orchestrator, "APPROVE_TIMEOUT_S", 1)
    run_id = start_run(store, belle_isle_pdf)
    wait_for(run_id, "complete")
    _, audit = call("GET", f"/runs/{run_id}/audit")
    assert [e["actor"] for e in audit["events"]] == ["auto-continue (timeout)", "auto (timeout)"]
