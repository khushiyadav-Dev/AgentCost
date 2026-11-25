"""AgentCost — per-agent LLM cost attribution.

Run:
    pip install -r requirements.txt
    python seed.py                 # optional: demo data so the dashboard is not empty
    uvicorn app:app --reload
    open http://127.0.0.1:8000/dashboard

Every call goes through POST /v1/chat. The gateway tags it with agent / user / task,
prices it, stores it, and the dashboard shows where the money actually goes.
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import db
from pricing import DEFAULT_MODEL, cost_usd, estimate_tokens

BUDGET_USD = float(os.getenv("AGENTCOST_BUDGET", "5.00"))   # daily budget
app = FastAPI(title="AgentCost", version="0.1.0")
db.init_db()


# ----------------------------------------------------------------- models
class ChatRequest(BaseModel):
    prompt: str
    agent: str = "default-agent"
    user_id: str = "anonymous"
    task: str = "general"
    model: str = DEFAULT_MODEL


# ----------------------------------------------------------------- providers
def call_provider(model: str, prompt: str) -> tuple[str, int, int]:
    """Returns (text, prompt_tokens, completion_tokens).

    No API key? A deterministic mock answers, so the whole pipeline is testable
    offline. With GEMINI_API_KEY or OPENAI_API_KEY set, the real model is called.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key and model.startswith("gemini"):
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={gemini_key}")
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return (text,
                int(usage.get("promptTokenCount", estimate_tokens(prompt))),
                int(usage.get("candidatesTokenCount", estimate_tokens(text))))

    if openai_key and model.startswith("gpt"):
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {openai_key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return (text,
                int(usage.get("prompt_tokens", estimate_tokens(prompt))),
                int(usage.get("completion_tokens", estimate_tokens(text))))

    # ---- mock provider (no key needed) ----
    words = prompt.split()
    answer = ("This is a mock response from AgentCost. Your prompt had "
              f"{len(words)} words and was tagged to agent '{'mock'}'.")
    return answer, estimate_tokens(prompt), estimate_tokens(answer)


# ----------------------------------------------------------------- routes
@app.get("/")
def root():
    return RedirectResponse("/dashboard")


@app.post("/v1/chat")
def chat(req: ChatRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is empty")

    started = time.time()
    try:
        text, p_tok, c_tok = call_provider(req.model, req.prompt)
    except Exception as exc:                      # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"provider error: {exc}") from exc
    latency = int((time.time() - started) * 1000)

    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": req.agent, "user_id": req.user_id, "task": req.task,
        "model": req.model, "prompt_tokens": p_tok, "completion_tokens": c_tok,
        "cost_usd": cost_usd(req.model, p_tok, c_tok), "latency_ms": latency,
    }
    db.insert_call(row)

    over_budget = db.totals()["today"] > BUDGET_USD
    return {"response": text, "cost_usd": round(row["cost_usd"], 6),
            "tokens": {"prompt": p_tok, "completion": c_tok},
            "latency_ms": latency, "over_budget": over_budget}


@app.get("/api/stats")
def stats():
    return {"totals": db.totals(), "budget_usd": BUDGET_USD,
            "by_agent": db.breakdown("agent"),
            "by_task": db.breakdown("task"),
            "by_model": db.breakdown("model"),
            "daily": db.daily(),
            "recent": db.recent()}


# ----------------------------------------------------------------- dashboard
CSS = """
:root{--bg:#0b1220;--card:#111a2e;--line:#1e2a44;--ink:#e8eefc;--mut:#8b9bb4;
      --cyan:#22d3ee;--green:#34d399;--amber:#fbbf24;--red:#f87171}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);font-size:14px;margin-bottom:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.card .k{color:var(--mut);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.card .v{font-size:26px;font-weight:700;margin-top:6px}
.bar{height:10px;background:#16213a;border-radius:99px;overflow:hidden;margin-top:10px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#34d399)}
.warn{background:#3a1d1d;border-color:#7f1d1d;color:#fecaca}
h2{font-size:16px;margin:34px 0 10px;color:var(--ink)}
table{width:100%;border-collapse:collapse;background:var(--card);
      border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}
th{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
tr:last-child td{border-bottom:none}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.spark{display:flex;align-items:flex-end;gap:5px;height:90px;
       background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.spark div{flex:1;background:linear-gradient(180deg,#22d3ee,#1d4ed8);border-radius:4px 4px 0 0;min-height:3px}
.tag{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;
     background:#16213a;color:var(--cyan)}
"""


def money(x: float) -> str:
    return f"${x:,.4f}" if x < 1 else f"${x:,.2f}"


def rows_html(items, label):
    if not items:
        return f"<tr><td colspan='4' style='color:#8b9bb4'>No {label} yet</td></tr>"
    out = []
    for it in items:
        out.append(
            f"<tr><td><b>{it['name']}</b></td><td class='n'>{it['calls']}</td>"
            f"<td class='n'>{it['tokens']:,}</td><td class='n'>{money(it['spend'])}</td></tr>")
    return "".join(out)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    t = db.totals()
    agents = db.breakdown("agent")
    tasks = db.breakdown("task")
    models = db.breakdown("model")
    days = db.daily()
    rec = db.recent(10)

    pct = min(100, (t["today"] / BUDGET_USD * 100) if BUDGET_USD else 0)
    over = t["today"] > BUDGET_USD
    peak = max([d["spend"] for d in days], default=0) or 1
    spark = "".join(
        f"<div title='{d['day']}: {money(d['spend'])}' "
        f"style='height:{max(3, d['spend'] / peak * 100):.0f}%'></div>" for d in days)

    recent_rows = "".join(
        f"<tr><td>{r['ts'][11:19]}</td><td>{r['agent']}</td><td>{r['task']}</td>"
        f"<td>{r['model']}</td><td class='n'>{r['prompt_tokens']+r['completion_tokens']:,}</td>"
        f"<td class='n'>{money(r['cost_usd'])}</td></tr>" for r in rec) or \
        "<tr><td colspan='6' style='color:#8b9bb4'>No calls yet — hit POST /v1/chat</td></tr>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AgentCost — dashboard</title><style>{CSS}</style></head><body><div class="wrap">
<h1>AgentCost</h1>
<div class="sub">Where your LLM bill actually goes — per agent, per task, per user.</div>

<div class="cards">
  <div class="card"><div class="k">Total spend</div><div class="v">{money(t['spend'])}</div></div>
  <div class="card {'warn' if over else ''}"><div class="k">Today</div>
      <div class="v">{money(t['today'])}</div>
      <div class="bar"><i style="width:{pct:.0f}%"></i></div>
      <div class="k" style="margin-top:6px">budget {money(BUDGET_USD)} / day</div></div>
  <div class="card"><div class="k">Calls</div><div class="v">{t['calls']:,}</div></div>
  <div class="card"><div class="k">Tokens</div><div class="v">{t['tokens']:,}</div></div>
</div>

<h2>Daily spend</h2>
<div class="spark">{spark or '<div></div>'}</div>

<h2>Spend by agent</h2>
<table><tr><th>Agent</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Spend</th></tr>
{rows_html(agents, 'agents')}</table>

<h2>Spend by task</h2>
<table><tr><th>Task</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Spend</th></tr>
{rows_html(tasks, 'tasks')}</table>

<h2>Spend by model</h2>
<table><tr><th>Model</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Spend</th></tr>
{rows_html(models, 'models')}</table>

<h2>Recent calls</h2>
<table><tr><th>Time</th><th>Agent</th><th>Task</th><th>Model</th>
<th class="n">Tokens</th><th class="n">Cost</th></tr>{recent_rows}</table>

<p class="sub" style="margin-top:26px">Try it:
<code>POST /v1/chat {{"prompt": "hello", "agent": "support-bot", "task": "triage"}}</code>
&nbsp;·&nbsp; <span class="tag">/api/stats</span></p>
</div></body></html>"""
