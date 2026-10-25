"""The public read-only demo routes and the eval action, on a seeded local store (no PDF or models needed)."""

import json
from types import SimpleNamespace

import pytest
from test_api import USER, call

from tenderlens.api import handler
from tenderlens.evaluation import gold_for
from tenderlens.store import LocalStore, set_store


def public_get(path: str) -> tuple[int, dict]:
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {},
        "requestContext": {
            "http": {"method": "GET", "path": path, "sourceIp": "127.0.0.1"},
            "stage": "$default",
        },
        "body": None,
        "isBase64Encoded": False,
    }
    result = handler.app.resolve(event, SimpleNamespace(function_name="test", aws_request_id="t"))
    return result["statusCode"], json.loads(result["body"] or "{}")


@pytest.fixture
def store(tmp_path):
    local = LocalStore(tmp_path)
    set_store(local)
    local.update_run(
        "shared1", owner=USER, approved_by=USER, status="complete", shared=True, buyer="City of Belle Isle"
    )
    local.update_run("private1", owner=USER, status="complete", shared=False)
    local.put_json("runs/shared1/audit.json", [{"actor": USER, "action": "approved"}])
    return local


def test_public_lists_and_opens_only_shared_runs(store):
    status, body = public_get("/public/runs")
    assert status == 200
    assert [r["run_id"] for r in body["runs"]] == ["shared1"]
    assert public_get("/public/runs/private1")[0] == 404
    assert public_get("/public/runs/private1/trace")[0] == 404


def test_public_view_hides_sign_in_emails(store):
    status, view = public_get("/public/runs/shared1")
    assert status == 200
    assert USER not in json.dumps(view)
    assert view["run"]["owner"] == "bid manager"
    assert view["audit"][0]["actor"] == "bid manager"


def test_eval_needs_the_owner_and_a_gold_set(store):
    assert call("POST", "/runs/shared1/eval", {}, user="someone.else@example.com")[0] == 403
    store.update_run("other1", owner=USER, status="complete", shared=False, buyer="Town of Elsewhere")
    status, body = call("POST", "/runs/other1/eval", {})
    assert status == 400 and "gold set" in body["message"]


def test_gold_set_matches_by_buyer():
    assert gold_for({"buyer": "City of Belle Isle"}).name == "belle-isle.yaml"
    assert gold_for({"buyer": "Town of Elsewhere"}) is None
