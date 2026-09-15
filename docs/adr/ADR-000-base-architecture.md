# ADR-000: Base architecture for PO Copilot

## Status

Accepted — 2026-09-14

Supersedes: none. Superseded by: none.

## Context

PO Copilot is a RAG-powered assistant for Product Owners and Product Managers. It generates user stories with Gherkin acceptance criteria, synthesizes raw customer feedback into ranked themes, and suggests RICE scores for backlog items.

The architecture is shaped less by the problem domain than by four hard constraints:

1. **Single developer, ~100 hours total.** Roughly 6-15h/week over 7 weeks, alongside two jobs. Any choice that costs a week of learning must return more than a week of value.
2. **Budget of ~US$100/month**, covering the Anthropic API and all hosting. Every managed service is weighed against a free tier or a self-hosted equivalent.
3. **The project is evidence, not a product.** Its primary reader is a hiring manager evaluating engineering judgment. Decisions must be legible and defensible in an interview, not merely functional.
4. **Four capabilities must be demonstrably exercised**, not merely mentioned: retrieval-augmented generation, LLMOps (observability, cost control, guardrails), model fine-tuning and distillation, and end-to-end project leadership.

The fourth constraint is unusual and worth stating plainly: this project deliberately chooses the path that *builds and shows* a capability over the path that would ship fastest. A managed vector database would be faster to adopt; it would also hide the mechanism this project exists to demonstrate.

**Why this product.**
At Climb4B I structure the backlog with Domain-Driven Design: epics as domains, features and PBIs as their subdomains. That framing is what gave me an honest read on the size of the MVP, and it let me write every PBI with a user story, acceptance criteria and rules that held together across the whole backlog.

Then the MVP hit heavy turnover on the engineering team — and the backlog turned out to be doing a second job nobody had planned for it. A backlog detailed and consistent enough to be read cold absorbed a good part of the cost of people rotating in and out.

That is the observation this product is built on. A backlog's value is not only in planning what to build; it is in carrying context when the people change. What makes it work is consistency — and consistency at that level is slow, manual, and depends entirely on the PO having the time.

## Decision

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript + Tailwind CSS |
| Backend | Python 3.13 + FastAPI + Pydantic |
| LLM | Claude 3.5 Sonnet via the Anthropic API |
| Retrieval | LangChain + pgvector |
| Database | PostgreSQL (Neon) |
| Repository | Monorepo — `apps/web`, `apps/api`, `docs` |
| Hosting | Vercel (frontend) + Railway (backend) |
| Observability | PostHog (product analytics) + Sentry (errors) + a custom cost dashboard |
| CI | GitHub Actions — `tsc`, `eslint`, `ruff`, `pytest` on every pull request |

### Rationale on the decisions that had a real alternative

**Python + FastAPI for the backend, rather than Next.js API routes.**
Keeping everything in TypeScript would unify the language, remove a deployment target, and halve the CI configuration. It was rejected because the retrieval and fine-tuning ecosystem — LangChain, pgvector clients, `transformers`, the Hugging Face toolchain — is native to Python. Forcing M2 and M4 through TypeScript ports would cost more later than the second runtime costs now. Accepted price: two runtimes, two deploy targets, and one developer maintaining both.

**pgvector on Postgres, rather than Pinecone or another managed vector store.**
A managed store would remove operational work and index tuning. It was rejected on two grounds: it adds a paid dependency to a US$100/month budget, and it abstracts away exactly the mechanism — embedding storage, similarity search, chunk retrieval — that this project needs to demonstrate. pgvector also keeps vectors and application data in a single Postgres instance, so there is no second system to keep consistent. This decision gets its own record in ADR-001 once the implementation confirms the trade-off holds.

**Monorepo, rather than separate repositories.**
For a single developer, two repositories double the ceremony of every cross-cutting change and split the commit history that is itself part of the portfolio. Vercel and Railway both support a root-directory setting, so independent deploys survive the monorepo. Accepted price: CI must be path-filtered as the project grows, or every PR runs both jobs unnecessarily.

**Claude 3.5 Sonnet via the Anthropic API, rather than another provider.**
Two honest reasons, in the order they actually weighed. First, familiarity: I use Claude Code daily, so the API's behaviour, its failure modes and its tooling are things I already know — on a project with roughly 100 hours of a solo developer's time, that is a real engineering factor, not a preference. Second, prompt caching, which is what keeps the M3 usage inside a US$100/month budget.

No comparative benchmark was run. Claiming a measured advantage over another model would be a claim this project cannot support, and the decision is deliberately reversible: every model call goes through an internal Provider interface, so swapping or adding a provider is a configuration change rather than a rewrite. If the structured-output quality proves insufficient for Gherkin and RICE JSON, that interface is where the comparison gets made — with measurements, at that point.

**Python 3.13 rather than 3.11.**
The original plan named 3.11; the development machine has 3.13 and no 3.11 alongside it. Installing a second interpreter on Windows was rejected: it is a known source of the wrong `venv`, an ambiguous PATH, and hours lost to an error that is not in the code. Nothing in this stack requires 3.11 — FastAPI and Pydantic v2 both support 3.13. Accepted risk: an ML dependency without a 3.13 wheel. That risk lands almost entirely on the M4 fine-tuning work, which runs in Google Colab rather than locally, so the local interpreter version does not constrain it. If a dependency does refuse 3.13, the fix is to pin that one step to a container, not to re-version the whole project.

**A Provider abstraction over the LLM call.**
All model calls go through one internal interface rather than calling the Anthropic SDK from feature code. This costs perhaps two hours in M1 and buys the ability to swap or add a provider without touching feature logic — the mitigation for R-04 (pricing changes) and a prerequisite for the M4 comparison, where a fine-tuned DistilBERT classifier must be swappable against an LLM classifier behind the same call site.

**Next.js 16 runs `next dev` on Turbopack.**
A fact of the version rather than a decision of ours: from Next 16, `next dev` uses Turbopack by default regardless of flags — `create-next-app --no-turbopack` does not opt out of it. Recorded so the development bundler is not read as something this project chose, or as something a flag can revert.

## Non-goals

Recorded because they are decisions, not oversights:

- **No authentication and no multi-tenancy.** This is a public demo. Abuse is handled by IP rate limiting. Adding auth would roughly triple the scope for no gain against the project's actual goal.
- **No custom domain in M0.** Vercel and Railway subdomains are sufficient until M3.
- **No UI component library or design system.** Tailwind alone covers the surface area this product has.
- **No internationalization.** The interface is English-only.
- **No real customer data, ever.** All feedback corpora used for development and demos are synthetic, generated by an LLM. This is absolute: production data from the author's employer must never enter this repository, its database, or any fine-tuning dataset.

## Consequences

**Positive**

- Each milestone deploys independently; the project has a public URL from week one.
- Vectors live in the same Postgres instance as application data — one system to back up, one to reason about.
- The Provider abstraction makes the M4 model comparison a configuration change rather than a rewrite.
- Every layer has a free or near-free tier, so the budget is consumed almost entirely by API tokens, where it is measurable per feature.

**Negative**

- Two runtimes mean two dependency trees, two CI jobs, and two ways for a deploy to fail — carried by one developer.
- pgvector requires manual index and chunking decisions that a managed store would make automatically. This is the intended cost, but it is a real one and it lands in M2, the longest milestone.
- LangChain adds a fast-moving dependency with a history of breaking changes. Mitigation: pin versions, and keep retrieval logic thin enough that a direct HTTP fallback stays viable (risk R-03).
- Cost is unbounded by default. Until the M3 dashboard exists, the only guardrail is the spend limit configured in the Anthropic Console. That limit is set before the first API call, not after.

**Accepted trade-offs**

- Learning depth is preferred over delivery speed wherever the two conflict. This is deliberate: an unfinished project that demonstrates RAG is worth more here than a finished one that calls an API.
- Operational maturity is deferred rather than skipped. There are no guardrails, retries, or observability before M3 — recorded here so their absence in M0-M2 reads as sequencing rather than neglect.

## Revisit this ADR when

- Monthly API spend exceeds US$50 for two consecutive weeks → revisit the model choice and the caching strategy.
- M2 retrieval quality proves unacceptable after chunking and index tuning → revisit pgvector in a superseding ADR.
- The project outgrows demo status and needs real users → revisit the non-goals on auth and multi-tenancy first.

## Related

- ADR-001 — pgvector vs. Pinecone (planned, M2)
- ADR-002 — LLMOps: observability, guardrails, cost control (planned, M3)
- ADR-003 — Fine-tuned classifier vs. LLM classification (planned, M4)

---

*Format: [Michael Nygard's ADR template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). ADRs are immutable — when a decision changes, a new ADR supersedes this one rather than editing it.*
