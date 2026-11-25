"""Tests for AgentCost — cost math, the gateway contract, and the dashboard."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
import db
import pricing


@pytest.fixture(scope="session")
def client():
    db.init_db()
    return TestClient(app_module.app)


# ------------------------------------------------------------------ cost math
def test_cost_of_a_million_prompt_tokens():
    # gpt-4o is $2.50 per 1M prompt tokens
    assert pricing.cost_usd("gpt-4o", 1_000_000, 0) == pytest.approx(2.50)


def test_cost_counts_prompt_and_completion_separately():
    # gpt-4o-mini: $0.15 in / $0.60 out per 1M
    assert pricing.cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_cheap_model_is_cheaper_than_expensive_one():
    cheap = pricing.cost_usd("gpt-4o-mini", 10_000, 2_000)
    pricey = pricing.cost_usd("gpt-4o", 10_000, 2_000)
    assert pricey > cheap * 10


def test_unknown_model_falls_back_to_default():
    assert pricing.cost_usd("some-future-model", 1_000, 1_000) == 0.0


def test_estimate_tokens_is_roughly_chars_over_four():
    assert pricing.estimate_tokens("a" * 400) == 100
    assert pricing.estimate_tokens("") == 1


# ------------------------------------------------------------------- gateway
def test_chat_returns_a_response_and_logs_the_call(client):
    before = db.totals()["calls"]
    r = client.post("/v1/chat", json={
        "prompt": "Summarise this support ticket",
        "agent": "support-bot", "user_id": "u_101", "task": "ticket-triage",
    })
    assert r.status_code == 200
    body = r.json()
    assert "response" in body and body["tokens"]["prompt"] > 0
    assert db.totals()["calls"] == before + 1


def test_chat_rejects_empty_prompt(client):
    r = client.post("/v1/chat", json={"prompt": "   "})
    assert r.status_code == 400


def test_chat_tags_are_stored_and_aggregated(client):
    client.post("/v1/chat", json={
        "prompt": "hello there", "agent": "test-agent-xyz",
        "user_id": "u_999", "task": "unit-test",
    })
    agents = {a["name"] for a in db.breakdown("agent")}
    tasks = {t["name"] for t in db.breakdown("task")}
    assert "test-agent-xyz" in agents
    assert "unit-test" in tasks


def test_budget_flag_appears_when_spend_is_over_limit(client, monkeypatch):
    monkeypatch.setattr(app_module, "BUDGET_USD", -1.0)   # force "over budget"
    r = client.post("/v1/chat", json={"prompt": "hi", "agent": "a", "task": "t"})
    assert r.json()["over_budget"] is True


# ------------------------------------------------------------------- reporting
def test_stats_endpoint_shape(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("totals", "budget_usd", "by_agent", "by_task", "by_model", "daily", "recent"):
        assert key in data


def test_dashboard_renders(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "AgentCost" in r.text
    assert "Spend by agent" in r.text


def test_root_redirects_to_dashboard(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/dashboard"
