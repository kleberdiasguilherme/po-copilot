# ADR-005: Guarantee the model's output structure with structured outputs

## Status

Accepted — 2026-09-25

Supersedes: none. Superseded by: none.

Numbered 005 because 001–003 are reserved in ADR-000 for M2–M4 records, and 004 is taken.

## Context

The User Story Generator (US-005, US-008) has to return a `UserStory` the rest of the system can rely on: a title, the three parts of "As a X, I want Y, so that Z" as separate fields, 3 to 5 Gherkin scenarios with `given` / `when` / `then` as lists, a definition of done and edge cases. The UI renders each field on its own, so a missing or misshaped field is a broken screen, not a cosmetic flaw.

There were three ways to get that structure out of the model:

1. **Ask for JSON in the prompt.** It depends on the model following instructions. It can come back with prose around the JSON, a missing field, or JSON that does not parse.
2. **Tool use.** Declare a strict tool whose input is the schema and force it with `tool_choice`. This was the standard workaround and it does guarantee the schema, but it pretends there is a tool call when all we want is a return format. Forced `tool_choice` is also being dropped: newer models (Fable 5.1, Opus 5.5) reject it with a 400. A model change — which ADR-004 has already shown happens — would break the call.
3. **Structured outputs** (`output_config.format` with a JSON schema). The API feature built for this exact job. Decoding is constrained to the schema, so the model cannot produce JSON outside it. It is supported on Sonnet 5.

## Decision

Use structured outputs. `AnthropicProvider.complete()` takes an optional JSON schema and sends it as `output_config.format`; it knows nothing about Pydantic, so the provider stays generic. The schema is generated once from the `UserStory` model with `anthropic.transform_schema`.

Structured outputs does not accept every JSON Schema keyword. In particular it rejects `minItems` / `maxItems`, so the rule "3 to 5 acceptance criteria" cannot live in the schema. `transform_schema` moves that limit into the field's description, where it reaches the model as an instruction, and **Pydantic enforces it again when the response is parsed**. The rule is therefore guaranteed by validation, not by decoding.

## Consequences

- The model cannot return prose, broken JSON, a missing required field or an extra field. Those failure modes are removed at the source, not caught downstream.
- The 3–5 AC limit is not removed at the source. A response with 2 or 6 criteria is valid against the schema the API sees and invalid against the Pydantic model. **The tests for responses outside the schema exist because of this gap, not as generic caution**: `test_parse_rejects_response_outside_schema` covers fewer than 3 and more than 5 AC, and the endpoint turns an `InvalidUserStoryError` into a clear 502 instead of a 500.
- A `stop_reason` of `refusal` or `max_tokens` can still yield output that fails validation (a refusal, or JSON cut mid-object). It is reported as its real cause rather than as a validation error.
- The schema is built from the Pydantic model, so there is one source of truth: a field added to `UserStory` reaches the model, the parser and the tests together.
- Changing model is not blocked by this choice, as long as the new model supports structured outputs. That is worth confirming alongside any record like ADR-004.

## Related

- ADR-000 — the Provider interface this decision is implemented behind.
- ADR-004 — the model change that showed model identifiers do not stay put.
- PR #21 — where the decision was first made and compared.
