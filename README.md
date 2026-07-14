# CreatorForge OS

### The Agentic Operating System for Creator Businesses

CreatorForge OS is an AI-powered operating system that runs the operational spine of a creator business. Four autonomous AI agents work together to analyze brand deals, draft content, manage finances, and learn from outcomes — all with real LLM reasoning and a human approval gate.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [The Four Agents](#the-four-agents)
4. [LLM Provider System](#llm-provider-system)
5. [API Reference](#api-reference)
6. [Database Schema](#database-schema)
7. [Frontend](#frontend)
8. [Deployment](#deployment)
9. [Local Development](#local-development)
10. [Screenshots & Demo Flow](#screenshots--demo-flow)

---

## Overview

### What problem does it solve?

Content creators (YouTubers, Instagram influencers, TikTokers, etc.) receive brand deals, need to produce content, manage invoices, and make strategic decisions — all manually. This is tedious, error-prone, and doesn't scale.

CreatorForge OS automates this with 4 specialized AI agents:
- **Deal Agent** — analyzes inbound brand offers, scores brand fit, benchmarks pricing, and negotiates counter-offers
- **Content Agent** — takes content briefs and generates full platform-optimized drafts (captions, hashtags, scripts)
- **Finance Agent** — auto-generates invoices from approved deals, tracks payment status
- **Memory Agent** — mines historical data for patterns (which brands fit best, what price ranges work, what content performs)

### Key Features

- **Real AI reasoning** — every agent decision uses actual LLM calls with domain-specific system prompts
- **Live agent thinking** — users see step-by-step what each agent is thinking (data gathering → analysis → AI call → result)
- **Human approval gate** — nothing goes out without the creator's sign-off (deals, content, invoices)
- **Multi-provider LLM failover** — supports 6 AI providers with automatic chain failover; always works even with zero API keys
- **Onboarding system** — new users set up their workspace with their real company data (no fake demo data)
- **Pattern learning** — the Memory Agent extracts insights from past deals/content and feeds them back into future agent decisions

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Caddy Reverse Proxy               │
│              (HTTPS, /forge/ and /api/)               │
└──────────────┬──────────────────┬────────────────────┘
               │                  │
       ┌───────▼───────┐  ┌──────▼───────┐
       │  Frontend     │  │   Backend    │
       │  Next.js      │  │   FastAPI    │
       │  Port 9001    │  │   Port 9000  │
       │  (SSR)        │  │   (uvicorn)  │
       └───────────────┘  └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐
              │  SQLite   │ │ LLM Engine│ │  Agents     │
              │  Database │ │ (failover)│ │  (4 agents) │
              └───────────┘ └─────┬─────┘ └──────┬──────┘
                                   │              │
                          ┌────────▼──────────────▼──────┐
                          │     External LLM APIs         │
                          │  Groq, Gemini, OpenRouter,    │
                          │  Cerebras, Mistral, LLM7.io   │
                          └──────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), React, TypeScript, Tailwind CSS v4 |
| Backend | Python 3.12, FastAPI, uvicorn |
| Database | SQLite (WAL mode) |
| LLM Engine | httpx async HTTP client, OpenAI-compatible API |
| Reverse Proxy | Caddy (automatic HTTPS) |
| Process Manager | systemd |

---

## The Four Agents

Each agent follows the same pattern:
1. **Gather context** — reads creator profile, deal/content data, and historical memory patterns
2. **Log thinking steps** — inserts step-by-step reasoning into `agent_thinking` table (visible to user in real-time)
3. **Call LLM** — sends a domain-specific prompt with context to the AI provider chain
4. **Parse response** — extracts structured JSON from the LLM output
5. **Update database** — saves results to the relevant table
6. **Route to approval** — creates an entry in the approval queue if human sign-off is needed

### 1. Deal Agent (`deal_agent`)

**Purpose**: Analyze inbound brand deals and negotiate terms.

**Input**: A deal record (brand name, type, offer amount, description) + creator profile + memory patterns

**Thinking steps logged**:
- `data_gathering` — reads deal details and creator profile
- `context_loading` — loads historical memory patterns
- `ai_analysis` — sends to AI for brand fit + price benchmarking + negotiation
- `ai_calling` — waits for AI response
- `result` — saves analysis results

**Output**: 
- `fit_score` (0.0–1.0) — how well the brand aligns with the creator
- `fit_reasoning` — detailed explanation
- `recommendation` — `strong_fit` | `moderate_fit` | `off_brand`
- `price_assessment` — `above market` | `fair market value` | `below market`
- `benchmark_price` — industry benchmark for the creator's follower count
- `negotiated_amount` — counter-offer price
- `negotiated_terms` — specific deliverables and conditions

**Price benchmarks used**:
- 10K–50K followers: $200–$800 per post
- 50K–200K followers: $800–$3,000 per post
- 200K–500K followers: $3,000–$8,000 per post
- 500K–1M followers: $8,000–$20,000 per post
- 1M+ followers: $20,000+ per post

### 2. Content Agent (`content_agent`)

**Purpose**: Draft platform-optimized content from briefs.

**Input**: A content item (title, content type, brief, platform) + creator profile + memory patterns

**Thinking steps logged**:
- `data_gathering` — reads content brief and creator profile
- `context_loading` — loads content performance patterns from memory
- `ai_writing` — sends to AI for content generation
- `ai_calling` — waits for AI response
- `result` — saves draft

**Output**:
- `draft` — full content draft (caption/script/text optimized for the platform)
- `agent_reasoning` — explanation of the agent's creative choices

**Supported platforms**: Instagram, YouTube, TikTok, Twitter/X, LinkedIn, Blog
**Supported content types**: Post, Video, Reel, Story, Carousel

### 3. Finance Agent (`finance_agent`)

**Purpose**: Generate invoices and track payments.

**Input**: An invoice record or an approved deal (auto-generates invoice)

**What it does**:
- Auto-generates invoices when a deal is approved
- Adds agent notes with payment terms and due date recommendations
- Tracks payment status (draft → sent → paid)

### 4. Memory Agent (`memory_agent`)

**Purpose**: Learn from historical data to improve future decisions.

**Input**: All deals, content items, and existing patterns for the creator

**What it does**:
- Mines deal history for patterns (which brand types fit best, average deal sizes)
- Analyzes content performance (which platforms/content types work)
- Stores patterns with confidence scores and sample counts
- These patterns are injected into the Deal Agent and Content Agent prompts for future decisions

**Pattern types**:
- `deal_acceptance` — what deal characteristics lead to approval
- `deal_revenue` — revenue patterns by brand type
- `content_performance` — which content types/platforms perform best
- `brand_fit` — which brand types score highest for this creator

---

## LLM Provider System

The LLM engine (`backend/llm_engine.py`) provides automatic failover across 6 AI providers. All providers use the OpenAI-compatible chat completions API.

### Provider Chain (in priority order)

| Priority | Provider | Models | Needs Key? | Free Tier |
|----------|----------|--------|------------|-----------|
| 1 | Groq | llama-3.3-70b-versatile, llama-4-maverick-17b, kimi-k2-instruct | Yes | 30 RPM, no credit card |
| 2 | Google Gemini | gemini-2.5-flash, gemini-2.0-flash | Yes | 15 RPM, no credit card |
| 3 | OpenRouter | hy3:free, nemotron-3-ultra:free, llama-3.3-70b:free, deepseek-r1:free | Yes | Free models available |
| 4 | Cerebras | llama3.1-70b, gpt-oss-120b | Yes | 30 RPM, no credit card |
| 5 | Mistral | mistral-medium-3.5-128b, open-mixtral-8x7b | Yes | Free tier |
| 6 | LLM7.io | gemma3:27b, codestral-latest | **No** | Always available |

### How Failover Works

1. When a user adds an API key (e.g., Groq), that provider becomes the first choice
2. The engine tries each model in the provider's model list
3. If a model returns **429 (rate limit)**, the provider is cooled down for 60 seconds and the next provider is tried
4. If a model returns **401/404/500**, the next model in the same provider is tried
5. If all models in a provider fail, the next provider is tried
6. **LLM7.io is always last** — no key needed, always available
7. If ALL providers fail (network down), agents fall back to **rule-based reasoning** (`backend/llm.py`) — the system never breaks

### Key Storage

API keys are stored in `backend/.llm_keys` (gitignored, chmod 600):
```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-or-...
```

### JSON Mode

For agents that need structured output, the engine supports `json_mode=True` which sends `response_format: {"type": "json_object"}` to providers that support it (Groq, OpenRouter, Gemini, Cerebras). The response is then parsed with a robust JSON extractor that handles:
- Direct JSON
- JSON in markdown code blocks
- JSON embedded in prose

---

## API Reference

Base URL: `https://essay-own-cradle-novel.2n6.me/api/` (or `http://localhost:9000/api/` locally)

### Onboarding & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/onboard` | Onboard a new creator (wipes existing data, starts fresh). Body: `{company_name, handle, industry, bio, followers, monthly_revenue}` |
| `POST` | `/reset` | Reset everything back to onboarding screen |
| `GET` | `/dashboard` | Get full dashboard data (creator, stats, deals, content, approvals, activities, patterns, thinking). Returns `{needs_onboarding: true}` if no creator exists. |
| `GET` | `/system/status` | System health check |
| `GET` | `/agents/status` | Get status of all 4 agents |

### Creator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/creator` | Get creator profile |
| `PUT` | `/creator` | Update creator profile |

### Products (Storefront)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/products` | List all products |
| `POST` | `/products` | Add a product. Body: `{title, description, price, category, image_emoji}` |
| `DELETE` | `/products/{id}` | Delete a product |

### Deals

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/deals` | List all deals |
| `POST` | `/deals` | Add a deal. Body: `{brand_name, brand_type, deal_type, offer_amount, description}` |
| `DELETE` | `/deals/{id}` | Delete a deal |
| `POST` | `/agents/deal/analyze/{id}` | **Run Deal Agent** on a deal — analyzes fit, benchmarks price, generates counter-offer |

### Content

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/content` | List all content items |
| `POST` | `/content` | Add a content item. Body: `{title, content_type, brief, platform}` |
| `DELETE` | `/content/{id}` | Delete a content item |
| `POST` | `/agents/content/draft/{id}` | **Run Content Agent** on a content item — generates a full draft |

### Invoices

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/invoices` | List all invoices |
| `POST` | `/invoices` | Create an invoice |
| `POST` | `/agents/finance/invoice/{id}` | **Run Finance Agent** on an invoice — adds notes and terms |
| `POST` | `/invoices/{id}/mark-paid` | Mark an invoice as paid |

### Approvals

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/approvals` | List pending approvals |
| `POST` | `/approvals/{id}/resolve` | Resolve an approval. Query: `?decision=approved` or `?decision=declined` |

### Memory

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/memory` | List all memory patterns |
| `POST` | `/agents/memory/learn` | **Run Memory Agent** — mines patterns from deal/content history |

### Agent Thinking (Live Reasoning)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/thinking/recent?limit=20` | Get recent thinking steps across all agents |
| `GET` | `/thinking/activity/{id}` | Get thinking steps for a specific activity |

### LLM Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/llm/providers` | Get status of all providers + active provider |
| `POST` | `/llm/providers/key` | Add a provider key. Body: `{provider, api_key}` |
| `DELETE` | `/llm/providers/{provider}` | Remove a provider key |
| `POST` | `/llm/providers/reload` | Reload provider configuration |

---

## Database Schema

Database: SQLite at `backend/creatorforge.db` (WAL mode for concurrent reads)

### Tables

```
creators
├── id (PK)
├── name, handle, bio, niche
├── followers, monthly_revenue, cleared_revenue
├── avatar
└── created_at

products
├── id (PK)
├── creator_id (FK → creators)
├── title, description, price
├── sales_count, category, image_emoji
└── created_at

deals
├── id (PK)
├── creator_id (FK → creators)
├── brand_name, brand_type, deal_type
├── offer_amount, description
├── status (pending_analysis | analyzed | approved | declined | negotiating | closed)
├── fit_score, fit_reasoning
├── negotiated_amount, negotiated_terms
├── agent_analysis
├── needs_approval
└── created_at, updated_at, closed_at

content_items
├── id (PK)
├── creator_id (FK → creators)
├── title, content_type (post | video | story | reel)
├── brief, draft
├── status (brief | drafting | draft_ready | approved | published | declined)
├── platform (instagram | youtube | tiktok | twitter | linkedin | blog)
├── agent_reasoning, needs_approval
├── scheduled_for
└── created_at, updated_at, published_at

invoices
├── id (PK)
├── creator_id (FK → creators)
├── deal_id (FK → deals)
├── client_name, amount
├── status (draft | pending_approval | approved | sent | paid)
├── items (JSON), agent_notes
├── needs_approval, due_date
└── created_at, paid_at

agent_activities
├── id (PK)
├── agent_name (deal_agent | content_agent | finance_agent | memory_agent)
├── action, entity_type, entity_id
├── summary, details (JSON)
├── status (started | completed | awaiting_approval | approved | declined)
└── created_at

agent_thinking
├── id (PK)
├── activity_id (FK → agent_activities)
├── agent_name
├── step_number, phase
├── thought
└── created_at

memory_patterns
├── id (PK)
├── creator_id (FK → creators)
├── pattern_type (deal_acceptance | deal_revenue | content_performance | brand_fit)
├── pattern_key, pattern_value
├── confidence, sample_count, insight
└── created_at, updated_at

approval_queue
├── id (PK)
├── entity_type (deal | content | invoice)
├── entity_id, agent_name
├── title, summary
├── status (pending | approved | declined)
└── created_at, resolved_at
```

### Key Design Decisions

- **SQLite WAL mode** — allows concurrent reads while writing (no lock contention)
- **`agent_thinking` table** — separate from `agent_activities` to store multiple reasoning steps per action
- **`needs_approval` flag** — every agent output requires human approval before being finalized
- **Memory injection** — patterns from `memory_patterns` are injected into agent prompts as context

---

## Frontend

### Tech Stack
- Next.js 15 with App Router
- TypeScript
- Tailwind CSS v4 (via `@import "tailwindcss"`)
- Custom fonts: Space Grotesk (display), DM Sans (body), JetBrains Mono (mono)

### Structure
```
frontend/src/
├── app/
│   ├── layout.tsx          # Root layout with fonts
│   ├── page.tsx            # Main dashboard (all tabs + onboarding)
│   └── globals.css         # Theme variables + animations
├── components/ui/
│   ├── badge.tsx           # Badge component
│   ├── button.tsx          # Button component
│   ├── card.tsx            # Card component
│   └── tabs.tsx            # Tabs component
└── lib/
    ├── api.ts              # fetchAPI helper
    └── utils.ts            # Utility functions
```

### Tabs

| Tab | Description |
|-----|-------------|
| **Overview** | Creator profile, stats grid, live agent thinking panel, approval queue, activity feed |
| **Deals** | Add deal form, pending deals, analyzed deals with fit scores and negotiated amounts |
| **Content** | Add content form, content pipeline with drafts, run content agent |
| **Storefront** | Add product form, product grid with prices and sales |
| **Memory** | Run memory agent, display learned patterns with confidence scores |
| **Agents** | Agent cards, "How It Works" section, live thinking process, activity feed |
| **AI Providers** | Add/remove API keys, provider status, failover explanation |

### Key UI Features

- **Onboarding screen** — appears when no creator exists; explains the app and collects company info
- **Live agent thinking** — collapsible panel showing step-by-step agent reasoning with phase icons
- **Auto-refresh** — dashboard polls every 3 seconds for real-time updates
- **Empty states** — every tab has a helpful empty state with a call-to-action
- **Reset button** — in the header, wipes all data and returns to onboarding

### Build

```bash
cd frontend
npm install
npx next build --webpack    # MUST use --webpack, NOT turbopack (chunk emission bug)
npx next start -p 9001
```

> ⚠️ **Important**: Use `npx next build --webpack` — the default turbopack build has a chunk emission bug that breaks the production build.

---

## Deployment

### Prerequisites
- Debian 12 (or similar Linux)
- Python 3.12+
- Node.js 20+
- Caddy (for HTTPS reverse proxy)

### Backend (systemd)

```ini
# /etc/systemd/system/creatorforge-backend.service
[Unit]
Description=CreatorForge OS Backend (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/baal-agent/workspace/creatorforge/backend
ExecStart=/usr/bin/python3 -c "import uvicorn; from main import app; uvicorn.run(app, host='127.0.0.1', port=9000)"
Restart=always
RestartSec=5
Environment=CREATORFORGE_DB=/opt/baal-agent/workspace/creatorforge/backend/creatorforge.db

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now creatorforge-backend
```

### Frontend (systemd)

```ini
# /etc/systemd/system/creatorforge-frontend.service
[Unit]
Description=CreatorForge OS Frontend (Next.js)
After=network.target creatorforge-backend.service

[Service]
Type=simple
WorkingDirectory=/opt/baal-agent/workspace/creatorforge/frontend
ExecStart=/usr/bin/npx next start -p 9001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now creatorforge-frontend
```

### Caddy Reverse Proxy

```caddy
# /etc/caddy/conf.d/creatorforge.caddy
handle_path /forge/* {
    reverse_proxy localhost:9001
}

handle /_next/* {
    reverse_proxy localhost:9001
}

handle /api/* {
    reverse_proxy localhost:9000
}
```

```bash
systemctl reload caddy
```

### URLs

| Service | URL |
|---------|-----|
| Frontend | `https://essay-own-cradle-novel.2n6.me/forge/` |
| API | `https://essay-own-cradle-novel.2n6.me/api/` |
| Backend (direct) | `http://localhost:9000` |
| Frontend (direct) | `http://localhost:9001` |

---

## Local Development

### Backend

```bash
cd backend
pip install fastapi uvicorn httpx pydantic
python3 -c "from models import init_db; init_db()"   # Create database
uvicorn main:app --reload --port 9000                  # Start dev server
```

### Frontend

```bash
cd frontend
npm install
npx next dev -p 9001     # Dev server with hot reload
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CREATORFORGE_DB` | `backend/creatorforge.db` | SQLite database path |
| `GROQ_API_KEY` | — | Groq API key (optional) |
| `GEMINI_API_KEY` | — | Gemini API key (optional) |
| `OPENROUTER_API_KEY` | — | OpenRouter API key (optional) |
| `CEREBRAS_API_KEY` | — | Cerebras API key (optional) |
| `MISTRAL_API_KEY` | — | Mistral API key (optional) |

> All LLM keys are optional. The system works out-of-the-box with the free LLM7.io provider.

---

## Screenshots & Demo Flow

### Step 1: Onboarding
When you first open the app, you see a welcome screen explaining what CreatorForge OS is and what the 4 agents do. Enter your company name, handle, industry, bio, follower count, and monthly revenue.

### Step 2: Dashboard
After onboarding, the Overview tab shows your creator profile, stats grid (followers, revenue, active deals, content, patterns, pending approvals), and an activity feed.

### Step 3: Add a Deal
Go to the Deals tab, click "+ Add Deal", enter brand details (e.g., Notion offers $5,000 for a sponsorship). The deal appears in "Pending Analysis".

### Step 4: Run the Deal Agent
Click "Run Deal Agent →" on the pending deal. The agent:
1. Reads the deal details
2. Loads memory patterns
3. Sends to AI for brand fit analysis + price benchmarking + negotiation
4. Returns a fit score, recommendation, and counter-offer

Watch the "Agent Thinking Process" panel on the Overview tab to see each step in real-time.

### Step 5: Add Content
Go to the Content tab, click "+ Add Content", enter a title and brief. Click "Run Content Agent →" to generate a full draft.

### Step 6: Run the Memory Agent
Go to the Memory tab, click "Run Memory Agent". The agent mines your deal and content history for patterns and stores them for future use.

### Step 7: Configure AI Providers (Optional)
Go to the AI Providers tab to add API keys for Groq, Gemini, OpenRouter, etc. The system works without any keys (using free LLM7.io), but adding keys makes the AI faster and more capable.

---

## File Structure

```
creatorforge/
├── backend/
│   ├── main.py              # FastAPI app — all API endpoints
│   ├── models.py            # SQLite schema + Pydantic models
│   ├── agents.py            # 4 AI agents with thinking steps
│   ├── agent_prompts.py     # System prompts for each agent
│   ├── llm_engine.py        # Multi-provider LLM engine with failover
│   ├── llm.py               # Rule-based fallback logic
│   ├── seed.py              # Demo data seeder (legacy)
│   └── .llm_keys            # API keys (gitignored)
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx   # Root layout
│   │   │   ├── page.tsx     # Main dashboard (all tabs)
│   │   │   └── globals.css  # Theme + animations
│   │   ├── components/ui/   # Reusable UI components
│   │   └── lib/
│   │       ├── api.ts       # API client
│   │       └── utils.ts     # Utilities
│   ├── package.json
│   ├── next.config.ts
│   └── tsconfig.json
├── design/
│   └── DESIGN.md            # Design spec
└── .gitignore
```

---

## License

This project is built as a demonstration of the Creator OS vision.

---

## Security Note

- API keys are stored in `backend/.llm_keys` with `chmod 600` (gitignored)
- The SQLite database is gitignored
- No authentication is implemented (single-user demo)
- All agent outputs require human approval before being finalized
