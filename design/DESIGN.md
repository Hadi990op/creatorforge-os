# CreatorForge OS — Agentic Operating System for Creators

## Goal
A working, deployed, multi-agent operating system for creators that implements Kitsune AI's Creator OS vision — but live, real, and one step beyond what they've imagined.

## Architecture

```
creatorforge/
  backend/          # FastAPI + SQLite + Agent orchestration
    main.py         # FastAPI app, all routes
    agents.py       # 4 agents: Deal, Content, Finance, Memory
    models.py       # Pydantic models + SQLite schema
    llm.py          # LLM abstraction (works with or without API key)
    seed.py         # Seed data (Layla Makes demo persona)
  frontend/         # Next.js dashboard
    src/app/        # Pages: dashboard, deals, content, storefront, memory, agents
```

## Components

### 1. Backend (FastAPI)
- **models.py**: SQLite schema, Pydantic schemas for all entities
- **agents.py**: 4 specialized agents, each with reasoning + action + output
- **llm.py**: LLM interface — uses Anthropic Claude if key available, falls back to sophisticated rule-based simulation
- **main.py**: REST API for all CRUD + agent actions + approval gates
- **seed.py**: Seeds a demo creator ("Layla Makes") with products, deals, content, memory

### 2. Agents (4)
1. **Deal Agent** — Captures inbound brand deals, scores fit against creator profile, negotiates terms, routes for approval
2. **Content Agent** — Takes briefs, generates content drafts, manages approval + scheduling
3. **Finance Agent** — Generates invoices, tracks payments, manages payouts
4. **Memory Agent** — Records outcomes, identifies patterns, improves future decisions

### 3. Frontend (Next.js)
- Dashboard — overview: revenue, active deals, agent activity, pending approvals
- Deals — inbound deals, agent analysis, approval/decline gates
- Content — content pipeline, drafts, approval gates
- Storefront — products, sales, revenue
- Memory — learned patterns, performance insights
- Agents — live agent activity feed, agent status

## Key Design Decisions
- **No external API dependency for core function**: LLM module falls back to rule-based if no key. System always works.
- **SQLite**: Zero setup, portable, real persistence
- **REST API**: Frontend decoupled from backend, flexible
- **Human-in-the-loop**: Every agent output has an approval gate
- **Live agent feed**: WebSocket-like polling for agent activity
- **Performance memory**: Pattern learning from deal outcomes

## Data Flow
1. Seed data loads on startup (if DB empty)
2. Frontend loads dashboard from REST API
3. User triggers agent actions (e.g., "analyze new deal")
4. Agent processes → creates activity log → routes to approval gate
5. User approves/declines → outcome recorded in memory
6. Memory agent identifies patterns over time

## Deployment
- Backend: FastAPI on port 9000 (systemd service)
- Frontend: Next.js standalone build on port 9001 (systemd service)
- Caddy: /api/* → backend, /forge/* → frontend
- Public URL: https://essay-own-cradle-novel.2n6.me/forge/
