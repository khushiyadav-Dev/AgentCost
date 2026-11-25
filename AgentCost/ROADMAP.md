# AgentCost — roadmap

Living document. Tick items as they ship; the README shows the current phase.

## Phase 1 — Local MVP ✅ (done)

- [x] FastAPI gateway: `POST /v1/chat` with agent / user / task / model tags
- [x] Cost engine: per-model price table, cost per call
- [x] SQLite logging: one `calls` table with tokens, cost, latency
- [x] Dashboard: totals, today vs budget, breakdown by agent / task / model, daily sparkline, recent calls
- [x] JSON API: `GET /api/stats`
- [x] Budget alert via `AGENTCOST_BUDGET`
- [x] Offline mock provider so the pipeline runs with zero API keys

## Phase 2 — Containerise + tests ✅ (done)

- [x] `Dockerfile` (python:3.12-slim, non-root data volume, healthcheck)
- [x] `docker-compose.yml` with a named volume for SQLite
- [x] `.env.example` for budget + API keys
- [x] `.dockerignore` so the image stays small
- [x] 12 pytest tests: cost math, gateway contract, tagging, budget flag, stats shape, dashboard render

## Phase 3 — Deploy on AWS ⬜ (next)

- [ ] `infra/` Terraform: ECR repo, ECS Fargate service, ALB, CloudWatch log group
- [ ] Database: RDS Postgres (or SQLite on EFS for a cheaper demo)
- [ ] Secrets: API keys in SSM Parameter Store, not in the image
- [ ] Public URL + screenshot in the README
- [ ] `docker push` to ECR from GitHub Actions

## Phase 4 — Harden ⬜

- [ ] Per-tenant API keys + rate limiting
- [ ] Per-user drilldown page
- [ ] CSV / JSON export
- [ ] Weekly email digest of the biggest cost movers
- [ ] Postgres migration path (SQLite → Postgres in one command)
- [ ] Load test: 1M calls/day story in the README
