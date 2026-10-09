# ADR-007: Host the API on Render's free plan, guarded by in-memory cost limits

## Status

Accepted — 2026-10-05

Supersedes: the backend hosting row of ADR-000 ("Railway"). ADR-000 itself is not edited. Superseded by: none.

## Context

Until US-034 the whole of M1 was invisible. The landing page linked to a generator whose form was disabled, because the backend had never been published.

Two questions looked separate and are not:

- **Where to host the API.**
- **How to keep a public demo from spending the Anthropic balance.**

The rate limit that existed was per IP and in memory. In-memory state only holds on a single process: on serverless platforms each instance keeps its own counter, so the limit stops limiting. The hosting choice therefore decides whether the cost guard works.

**The force that settled it: zero additional spend.** No card, no subscription, no paid service. The only money committed is the prepaid US$5 Anthropic balance, and that balance is the physical ceiling. Surveyed on 2026-10-05, with sources:

| Option | Why it is out, or in |
|---|---|
| Railway | Requires a card: "Railway requires the use of a post-paid card" ([plans](https://docs.railway.com/reference/pricing/plans)). Hobby is US$5/month. Out. |
| Fly.io | No free tier; the trial ends after 2 hours of machine runtime or 7 days, then a card ([pricing](https://docs.fly.io/about/pricing)). Out. |
| Vercel Functions (Hobby) | Free, no card, and Python streams. But instances scale out automatically ([compute](https://vercel.com/docs/fundamentals/what-is-compute)), so the in-memory limits would break. Keeping them needs Redis (an external service, ruled out) or the WAF rate limit rule, which is per IP with a fixed window of at most 10 minutes and cannot express a daily quota. Plan B. |
| **Render (free)** | No card: "No credit card is required" ([Render, 2026-04-23](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)). **One instance only**: free web services do not support "Scaling beyond a single instance" ([free](https://render.com/docs/free)). 0.1 CPU and 512 MB ([compute plans](https://render.com/docs/compute-plans)); the API measured ~83 MB locally. **Chosen.** |

## Decision

**Hosting: Render, free plan, one web service, region `virginia`, described in `render.yaml`.**

The single instance is what keeps the existing in-memory limits valid. The guard needs no Redis, no database, and no rewrite.

**Cost guards, all at zero spend:**

| Guard | What it limits | Where |
|---|---|---|
| `max_tokens` = 3000 | What one generation can cost | provider |
| Daily global quota: 20 generations, all visitors together | How many generations per day | memory |
| Per-IP limit: 3 per hour | Availability for other visitors | memory |
| Prepaid US$5 balance | The absolute ceiling | Anthropic Console |

- **`max_tokens` is the guard with the best return.** At 16000 the worst case was ~US$0.16 per generation on Sonnet 5 (US$2 input / US$10 output per million tokens). At 3000 it is ~US$0.033. A typical generation uses ~1000 output tokens and a five-scenario one ~1700. 3000 rather than 2000 because the model's adaptive thinking counts against the same ceiling, and a cut generation fails after the visitor has waited ~20 seconds.
- **Global quota and per-IP limit do different jobs.** The global quota protects the money: no number of IPs gets past it. Worst case is 20 × US$0.033 ≈ US$0.66 per day. A global quota alone would fail the visitor who matters most, though. One person could use up the day and a recruiter would arrive to "quota reached". The per-IP limit is what stops that.
- **The global quota is counted only for requests that would reach the model.** A request with an invalid description or no API key configured is rejected before the quota is touched.
- **Both counters reset when the process restarts.** Render "might restart a Free web service at any time" ([free](https://render.com/docs/free)). That costs at most one extra day's quota, and the prepaid balance stands behind it.
- **The exhausted balance is an explicit state, not a 500.** The API answers 402 `billing_error`, or historically 400 with "credit balance is too low". Both become a readable message: the demo has used up its prepaid credit and generation is paused. One day this is how the demo ends, and it should fail legibly.

**The cold start is shown, not hidden.**

- Render spins a free service down after 15 minutes without traffic, and spinning up "takes about one minute" ([free](https://render.com/docs/free)).
- The landing page's API status badge calls `/health` on load. It now has a second job: it wakes the server while the visitor reads the page, so the generator is usually up by the time they click.
- When the generator does find the server asleep, it says so: "Waking the demo server", with the reason and an elapsed counter. The wake-up runs outside the generation's 20-second idle timeout.
- While waking, Render may answer with its own loading page. Only the real `/health` JSON counts as awake.

**Client IP.**

- The per-IP limit keys on `CF-Connecting-IP`, not on `X-Forwarded-For`. Render serves through Cloudflare, and the measurement below shows that `X-Forwarded-For` starts with whatever the client sent.
- uvicorn runs without `--proxy-headers`. With them and `--forwarded-allow-ips='*'`, uvicorn took the leftmost `X-Forwarded-For` entry, which the client controls.
- Without `CF-Connecting-IP` (running locally, or if traffic ever stops going through Cloudflare), the key falls back to the connection's IP. Behind a proxy that is the same for everyone, so the limit gets stricter, never bypassable.
- **Both limits count only requests that reach the model.** They run inside the endpoint, after the input validates and the key exists. A 422 spends nothing, so it costs nothing: neither the visitor's hourly slots nor the day's quota. A request stopped by the daily quota gives its per-IP slot back.
- Even with a forgeable key, the global quota still bounds the spend. Forging an IP could only use up the day's quota, not the balance.

## Consequences

- The User Story Generator is public at zero added cost. The landing badge turns "Live" when the build has `NEXT_PUBLIC_API_URL`.
- The first visit after 15 idle minutes waits about a minute. This is the price of the free plan, and it is stated on screen.
- 750 free instance hours per month ([free](https://render.com/docs/free)) cover one always-on service (at most 744 hours); sleeping only lowers the use. If they ran out, Render would suspend the service until the next month.
- Moving to more than one instance, on any platform, breaks both limits silently. That move needs an external store first.
- `apps/api/railway.json` is removed. The Railway runbook in `docs/deploy.md` is replaced by the Render one.

## Revisit this ADR when

- The budget constraint changes. With a card, an always-on container removes the cold start.
- The prepaid balance runs out faster than the quota predicts. Check the logs for generations near `max_tokens`.
- A second instance becomes necessary for any reason.

## Client IP behind Render's proxy (measured after deploy)

Measured on 2026-10-09 with a temporary endpoint that echoed the headers, removed before merge.

| Request | `X-Forwarded-For` as received | `CF-Connecting-IP` |
|---|---|---|
| Nothing forged | `<client>, <Cloudflare edge>, <Render internal 10.x>` | `<client>` |
| `X-Forwarded-For: 198.51.100.7` | `198.51.100.7,<client>, <edge>, <internal>` | `<client>` |
| `X-Forwarded-For: 1.1.1.1, 2.2.2.2` | `1.1.1.1, 2.2.2.2,<client>, <edge>, <internal>` | `<client>` |
| `CF-Connecting-IP: 198.51.100.9` | — | Cloudflare refuses: 403, error 1000 |
| `True-Client-IP: 198.51.100.8` | `<client>, <edge>, <internal>` | `<client>` (forged value overwritten) |

- **Render appends; it does not overwrite.** A forged value stays at the front of the list.
- **The real IP is neither the first entry nor the last.** The first is the client's own text. The last is Render's internal proxy, and the one before it is a Cloudflare edge that changes between requests.
- Before the fix, the published API keyed on the forged value: with one fixed forged IP, the fourth request got 429; with a new forged IP, the counter started over.
- `CF-Connecting-IP` cannot be forged from outside, so it is the key.

## Related

- ADR-000 — the original stack; its "Railway (backend)" row is superseded here.
- ADR-006 — streaming; the `X-Accel-Buffering: no` header keeps the proxy from holding events.
- US-034 (#12).
