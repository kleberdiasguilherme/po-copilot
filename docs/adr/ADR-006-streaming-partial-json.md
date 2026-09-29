# ADR-006: Stream the user story as partial JSON snapshots, parsed on the server

## Status

Accepted — 2026-09-29

Supersedes: none. Superseded by: none. Amends: ADR-005 (one consequence, below).

## Context

US-006 asks for the User Story Generator to stream its answer: text appears token by token over SSE, and the first chunk shows up in under 3 seconds. A generation takes around 14 seconds, and until now the screen showed a spinner for all of them.

ADR-005 made the output structured JSON, validated by Pydantic. JSON only validates once it is complete, and a stream delivers it in pieces. That left three ways to fill the ~14 seconds:

1. **Show the raw JSON as it arrives.** Honest, but it is not a user story on screen. It is braces and quoted keys.
2. **Keep the spinner.** It needs no streaming at all, and it is exactly the static screen the story exists to remove.
3. **Parse the incomplete JSON and render the fields as they grow.** The only option that shows readable content early.

Within option 3 there were two more choices.

- **Closed fields only, or open strings too.** Showing a field only once its closing quote arrives contradicts the AC ("token by token"). A Gherkin scenario also takes several seconds to close, so the screen would sit still again. Open strings are shown as they grow.
- **Where to parse.** In the browser, it would take a partial JSON library and a test runner that `apps/web` does not have, only to cover one test item. On the server, `pydantic_core.from_json(text, allow_partial="trailing-strings")` already ships with the Pydantic the API uses, and it is covered by the existing pytest suite.

## Decision

Parse on the server and stream snapshots.

- `AnthropicProvider.stream()` sits next to `complete()` in the same file (ADR-000). It yields text chunks and then one `Completion` with the same metadata as `complete()` (tokens in and out, model, total latency, stop reason), so the cost data that US-018 depends on is not lost when streaming.
- `stream_user_story()` accumulates the text, parses it with `allow_partial="trailing-strings"`, and emits a snapshot of the object parsed so far **at most every 100 ms**. That limit is part of the design, not a later optimisation. One snapshot per text chunk would mean hundreds of messages per generation, each one carrying the whole object.
- `POST /api/user-story/stream` sends Server-Sent Events:
  - `partial`: the object so far, **not validated**, repeated as it grows. The last `partial` is always the complete text.
  - `done`: `{"story": ...}`, the story validated by Pydantic, which replaces the partial one.
  - `error`: `{"detail": ...}`, when validation fails, the model stops early or the provider fails.
- Rate limiting, input validation and a missing API key answer 429 / 422 / 503 **before the stream opens**, as plain JSON: FastAPI dependencies run before the first byte. The streaming and non-streaming endpoints share one rate limit, so using both does not double anyone's quota.
- The screen treats a stream that ends without `done` or `error` as a dropped connection, and it aborts after 20 seconds without any new byte.

A separate path, rather than a parameter on `/api/user-story`, because the two have different response types (`text/event-stream` versus a JSON `UserStory`), and a query parameter that changes the response format would make the OpenAPI contract and the error handling ambiguous. `EventSource` only does GET, so the browser reads the POST body with `fetch` and parses the events itself.

## What changes from ADR-005

ADR-005 guaranteed that the screen only showed a story that had passed validation. **That no longer holds while the stream runs.** The rule "3 to 5 acceptance criteria" lives in Pydantic, not in the schema the API decodes against, so a user can watch a sixth scenario arrive and only then receive a validation error.

The mitigation is in the UI, not in the parser:

- While the stream runs, the content sits inside a frame marked "Generating — not final until it finishes", so the reader knows beforehand that it is not definitive.
- On `done`, the validated story replaces the partial one.
- On `error`, or on a dropped connection, the partial content **stays on screen**, marked "Incomplete — this is not a valid story", next to the error message. Removing it would hide what the error is about.

Pydantic is still the only source of truth for what counts as a valid story. The partial render only shows content before that check runs.

## Consequences

- The screen shows readable content while the model is still writing, and the output format stays exactly the one ADR-005 defined.
- Each `partial` carries the whole object so far. That is a few KB per event at a few events per second, which is acceptable for a story of about 3 KB. Sending diffs instead would have to be measured first.
- The order in which fields appear depends on the order the model writes the keys. In the one live run (2026-09-29) it matched the schema: `title, as_a, i_want, so_that, acceptance_criteria, definition_of_done, edge_cases`. The parser does not depend on that order. Only the time to first readable content does.
- **The AC "first chunk in under 3 s" was not met in that run.** From the click on Generate to the first readable content painted on screen took 4230 ms (Sonnet 5, 1552 input tokens, 1003 output tokens, 14.0 s in total). One run does not show where those 4.2 s go (network, time to first token, schema processing), because the server does not yet record when the first token arrives.
- The measurement stays in the code: a `first-content` entry in the browser Performance timeline, logged to the console in development.

## Related

- ADR-000 — every model call goes out from one file; `stream()` lives next to `complete()`.
- ADR-005 — structured outputs; this record amends its guarantee about what the screen shows.
- US-006 (#18), US-018 (cost dashboard, M3).
