"""Seed the database with realistic demo traffic so the dashboard is not empty.

    python seed.py            # 14 days of demo calls
    python seed.py --wipe     # delete the DB first
"""

import random
import sys
from datetime import datetime, timedelta, timezone

import db
from pricing import cost_usd

AGENTS = [("support-bot", 0.34), ("research-agent", 0.22), ("code-reviewer", 0.18),
          ("summariser", 0.16), ("onboarding-agent", 0.10)]
TASKS = [("ticket-triage", 0.30), ("doc-summary", 0.22), ("code-review", 0.18),
         ("lead-scoring", 0.16), ("onboarding-qa", 0.14)]
MODELS = [("gpt-4o-mini", 0.45), ("gemini-2.0-flash", 0.35), ("gpt-4o", 0.12),
          ("claude-haiku", 0.08)]
USERS = ["u_101", "u_102", "u_103", "u_104", "u_105", "u_106", "u_107", "u_108"]


def pick(pairs):
    names = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(names, weights=weights, k=1)[0]


def main():
    if "--wipe" in sys.argv:
        import os
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
    db.init_db()
    random.seed(7)

    now = datetime.now(timezone.utc)
    total = 0
    for day in range(13, -1, -1):
        calls = random.randint(28, 75)
        for _ in range(calls):
            model = pick(MODELS)
            agent = pick(AGENTS)
            task = pick(TASKS)
            # heavier models on the research agent, like real life
            base = 900 if agent == "research-agent" else 320
            p_tok = int(random.gauss(base, base * 0.35)) + 60
            c_tok = int(random.gauss(p_tok * 0.7, p_tok * 0.25)) + 30
            p_tok, c_tok = max(20, p_tok), max(10, c_tok)
            ts = (now - timedelta(days=day,
                                  hours=random.randint(0, 23),
                                  minutes=random.randint(0, 59)))
            db.insert_call({
                "ts": ts.isoformat(timespec="seconds"),
                "agent": agent, "user_id": random.choice(USERS), "task": task,
                "model": model, "prompt_tokens": p_tok, "completion_tokens": c_tok,
                "cost_usd": cost_usd(model, p_tok, c_tok),
                "latency_ms": random.randint(380, 3200),
            })
            total += 1
    t = db.totals()
    print(f"Seeded {total} calls · total spend ${t['spend']:.2f} · today ${t['today']:.2f}")


if __name__ == "__main__":
    main()
