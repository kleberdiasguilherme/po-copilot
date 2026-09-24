# ADR-004: Update the model identifier to Claude Sonnet 5

## Status

Accepted — 2026-09-24

Supersedes: the model identifier in ADR-000 (the "LLM" row). Superseded by: none.

## Context

ADR-000 specifies Claude 3.5 Sonnet. Anthropic retired both of its identifiers (`claude-3-5-sonnet-20241022` and `claude-3-5-sonnet-20240620`) on 2025-10-28, before ADR-000 was written; a call to either now fails. The gap surfaced in M1, at the first real API call.

## Decision

Use `claude-sonnet-5`, the current model of the same family. The original choice of provider (Anthropic) and family (Sonnet), and the reasons for it — familiarity and prompt caching — are kept unchanged. Moving to Haiku or Opus would be a new decision and is not what this record makes.

## Consequences

- ADR-000 remains valid in its rationale; only its version identifier is superseded.
- The identifier lives in one place, `anthropic_model` in `apps/api/app/config.py`, read by the Provider — the next retirement is a one-line change plus a record like this one.
- Sonnet 5 has a newer tokenizer, so token counts and cost baselines are measured on it from the start, not carried over from 3.5 figures.

## Note

This decision was invalidated by an external fact, not by a change of opinion. The distinction matters when reading the history: nothing here reopens the reasoning in ADR-000.
