"""Testes do User Story Generator com o provider mockado: custo zero, sem rede."""

import json
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from app.providers.anthropic_provider import AnthropicProvider, Completion
from app.user_story import (
    USER_STORY_SCHEMA,
    InvalidUserStoryError,
    generate_user_story,
    load_prompt,
    parse_user_story,
)

FIXTURE = Path(__file__).parent / "fixtures" / "user_story_valid.json"


def completion(text: str, stop_reason: str = "end_turn") -> Completion:
    return Completion(
        text=text,
        model="claude-sonnet-5",
        input_tokens=812,
        output_tokens=433,
        latency_ms=5210,
        stop_reason=stop_reason,
    )


@pytest.fixture
def valid_json() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def provider(valid_json: str) -> AnthropicProvider:
    mock = create_autospec(AnthropicProvider, instance=True)
    mock.complete.return_value = completion(valid_json)
    return mock


def test_load_prompt_reads_the_versioned_file() -> None:
    prompt = load_prompt()

    assert prompt.version == "user_story_v1"
    assert "Gherkin" in prompt.text


def test_parse_valid_response(valid_json: str) -> None:
    story = parse_user_story(valid_json)

    assert story.statement == (
        "As a sales manager, I want to export the filtered sales report as a CSV file, "
        "so that I can share the numbers with finance without rebuilding them in a spreadsheet"
    )
    assert len(story.acceptance_criteria) == 3
    assert story.acceptance_criteria[0].then == [
        "a CSV file downloads",
        "it contains only the Q3 rows",
    ]


def test_generate_sends_prompt_and_schema(provider: AnthropicProvider) -> None:
    generate_user_story("Sales managers rebuild the report by hand for finance.", provider)

    kwargs = provider.complete.call_args.kwargs
    assert kwargs["system"] == load_prompt().text
    assert kwargs["messages"] == [
        {"role": "user", "content": "Sales managers rebuild the report by hand for finance."}
    ]
    assert kwargs["output_schema"] == USER_STORY_SCHEMA


def test_generate_records_prompt_version_and_metadata(provider: AnthropicProvider) -> None:
    result = generate_user_story("any description", provider)

    assert result.prompt_version == "user_story_v1"
    assert result.completion.input_tokens == 812
    assert result.completion.output_tokens == 433
    assert result.story.title == "Export filtered report as CSV"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda d: d.pop("so_that"), "campo obrigatorio ausente"),
        (lambda d: d.update(acceptance_criteria=d["acceptance_criteria"][:2]), "menos de 3 AC"),
        (lambda d: d["acceptance_criteria"].extend(d["acceptance_criteria"]), "mais de 5 AC"),
        (lambda d: d["acceptance_criteria"][0].update(then=[]), "cenario sem Then"),
        (lambda d: d.update(priority="high"), "campo fora do schema"),
    ],
)
def test_parse_rejects_response_outside_schema(valid_json: str, mutation, reason: str) -> None:
    data = json.loads(valid_json)
    mutation(data)

    with pytest.raises(InvalidUserStoryError):
        parse_user_story(json.dumps(data))


def test_parse_rejects_non_json() -> None:
    with pytest.raises(InvalidUserStoryError):
        parse_user_story("Here is your user story: As a PO...")


def test_generate_raises_when_output_was_cut(provider: AnthropicProvider) -> None:
    provider.complete.return_value = completion('{"title": "Exp', stop_reason="max_tokens")

    with pytest.raises(InvalidUserStoryError, match="max_tokens"):
        generate_user_story("any description", provider)
