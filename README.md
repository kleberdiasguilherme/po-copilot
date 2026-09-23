# PO Copilot

> RAG-powered assistant for Product Owners and Product Managers.
> Built with Claude, LangChain, pgvector, Next.js, and FastAPI.

**Status:** M0 (foundation) complete — the landing page is live; the backend and the three features are not published yet (backend ships in M1).
**Live demo:** https://po-copilot-lilac.vercel.app
**Author:** Kleber Dias Guilherme — [LinkedIn](https://www.linkedin.com/in/kleberdiasguilherme/)

---

## Why this exists

As a Product Owner shipping a financial planning SaaS, I hit three recurring pains:

1. Writing user stories and acceptance criteria at scale slows down discovery.
2. Synthesizing customer feedback across tickets, NPS, and reviews takes days.
3. Prioritizing a backlog objectively — not by loudest voice — requires structured thinking every sprint.

PO Copilot takes those three loops and makes them repeatable, turning raw inputs into structured PM/PO artifacts.

It is also a deliberate learning project. Three of its four capabilities — retrieval-augmented generation, LLMOps, and model distillation — are things I had never implemented before starting. The architecture decisions are documented as ADRs precisely so the reasoning is auditable, including where I chose the harder path on purpose.

## What it will do

| # | Feature | Status |
|---|---|---|
| 1 | User Story Generator | 🔨 Planned — M1 |
| 2 | Feedback Synthesizer (RAG) | 🔨 Planned — M2 |
| 3 | Backlog Prioritizer (RICE) | 🔨 Planned — M3 |
| 4 | Feedback Classifier (fine-tuned) | 🧊 Optional — M4 |

Status legend: ✅ live · 🚧 in progress · 🔨 planned · 🧊 optional

### 1. User Story Generator — planned (M1)

Give it a problem statement, get a user story with acceptance criteria in Gherkin syntax, a definition of done, and edge cases surfaced by the model.

### 2. Feedback Synthesizer — planned (M2)

Upload a dump of feedback (CSV, JSON, or raw text — tickets, NPS comments, store reviews). It embeds the content, retrieves the most relevant chunks per query, and returns emerging themes, representative quotes, and product opportunities ranked by frequency and severity. Every quote traces back to its source row.

### 3. Backlog Prioritizer — planned (M3)

Feed it a backlog and, optionally, historical feedback. It returns a suggested RICE score per item with a written rationale — you approve or override, and the score recalculates live.

### 4. Feedback Classifier — optional (M4)

A distilled BERT model classifies feedback into bug / feature request / praise / churn signal, benchmarked against LLM classification on accuracy, latency, and cost.

## Tech stack

| Layer | Tech | Why |
|---|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript + Tailwind | Fast to ship, familiar from prior work |
| Backend | Python 3.13 + FastAPI + Pydantic | The retrieval and fine-tuning ecosystem is native to Python |
| LLM | Claude 3.5 Sonnet via Anthropic API | Daily working familiarity, and prompt caching to keep the project inside a US$100/month budget |
| RAG | LangChain + pgvector (on Neon) | Low cost and full control over chunking, indexing, and retrieval |
| Storage | PostgreSQL | Vectors and application data in one system to reason about |
| Deploy | Vercel (front, live) + backend host chosen in M1 | Vercel Hobby is free; the backend is not published until it has a feature — Railway (~US$1–5/month) vs. Vercel Python Functions is decided in M1 |
| Observability | PostHog (product) + Sentry (errors) + custom Anthropic cost dashboard | LLMOps discipline |
| Fine-tuning (M4) | Hugging Face + Google Colab + DistilBERT | Cost-effective for a classification task |

## Architecture

```
┌──────────────┐        ┌──────────────┐        ┌─────────────────┐
│  Next.js UI  │ ──▶    │   FastAPI    │ ──▶    │   Claude API    │
│  (Vercel)    │        │  (Railway)   │        │  (Anthropic)    │
└──────────────┘        └───┬──────────┘        └─────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ pgvector on   │
                    │ PostgreSQL    │
                    │ (Neon)        │
                    └───────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ PostHog +    │
                    │ Sentry       │
                    └──────────────┘
```

Architecture decisions are documented in `docs/adr/`:

- **ADR-000** — Base architecture *(written)*
- **ADR-001** — pgvector vs. Pinecone for retrieval *(planned, M2)*
- **ADR-002** — LLMOps: observability, guardrails, cost control *(planned, M3)*
- **ADR-003** — Fine-tuned classifier vs. LLM classification *(planned, M4)*

## Running locally

First time, install both apps:

```bash
# Backend — Python 3.13
cd apps/api
python -m venv .venv
source .venv/Scripts/activate    # Git Bash / Windows; elsewhere: source .venv/bin/activate
pip install -r requirements-dev.txt    # runtime + ruff e pytest
cp .env.example .env             # add ANTHROPIC_API_KEY (and DATABASE_URL from M2 on)

# Frontend
cd ../web
npm install
cp .env.local.example .env.local # points at the API on :8000
```

Then, from the repository root, one command starts both:

```bash
./dev.ps1        # Windows PowerShell
make dev         # Git Bash with make, WSL, macOS, Linux
```

Backend on `:8000`, frontend on `:3000`. `GET /health` returns `{"status": "ok", "version": "0.1.0", "environment": "development"}`.

To run each one on its own:

```bash
cd apps/api && fastapi dev app/main.py    # :8000
cd apps/web && npm run dev                # :3000
```

API tests:

```bash
cd apps/api && python -m pytest tests
```

## Deployment

Today only the frontend is published: Vercel, root directory `apps/web`, no environment
variables, redeploying on every push to `main`. The backend ships in M1, once it serves
more than `/health`; its runbook (including the ordering trap between the two services)
is kept in [`docs/deploy.md`](docs/deploy.md).

Environment variables for when the backend is published — none are set today, and none are committed:

| Service | Variable | Purpose |
|---|---|---|
| Railway | `ENVIRONMENT` | `production`; echoed back by `/health` |
| Railway | `CORS_ORIGINS` | comma-separated origins allowed to call the API |
| Railway | `ANTHROPIC_API_KEY` | empty until M1 |
| Vercel | `NEXT_PUBLIC_API_URL` | API base URL, inlined at build time; while unset, the footer API badge is hidden |

## Non-goals

Recorded because they are decisions, not omissions:

- **No authentication and no multi-tenancy.** This is a public demo; abuse is handled by IP rate limiting.
- **No real customer data, ever.** All feedback corpora used in development and demos are synthetic, generated by an LLM.
- **No UI component library.** Tailwind alone covers the surface this product has.

## What comes next

The current scope treats PO Copilot as a set of tools: each feature assumes you already know the task. A natural next direction inverts that — a guided track that reads your product's signals, tells you which maturity stage you are in, and recommends the next step with at most two or three paths, as a decision tree with finite, testable states.

It is deliberately out of scope for V1, and the reason is the interesting part: a track has to remember where you left off, which means per-user state, which means authentication — reopening a non-goal declared in ADR-000. It is tracked in the backlog as M5.

## Roadmap

Five milestones over seven weeks at 6–15h/week. See the roadmap document for the milestone breakdown, the 27 user stories with Gherkin acceptance criteria, and the risk register.

## License

MIT — fork, adapt, or use it in your own PM workflow.

## Acknowledgements

- Anthropic, for Claude and Claude Code
- The LangChain and pgvector communities
- The product team I work with, for the real-world problems that inspired this
