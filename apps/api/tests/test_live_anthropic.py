"""Teste de integracao contra a API real. Excluido por padrao: pytest -m live.

Existe para provar que a integracao funciona, nao para exercitar o produto —
cada execucao gasta credito.
"""

import pytest

from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.user_story import generate_user_story

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not settings.anthropic_api_key, reason="ANTHROPIC_API_KEY ausente"),
]


def test_generate_user_story_against_real_api() -> None:
    result = generate_user_story(
        "Our sales managers rebuild the monthly report in a spreadsheet by hand every "
        "time finance asks for the numbers.",
        AnthropicProvider(),
    )

    assert 3 <= len(result.story.acceptance_criteria) <= 5
    assert result.prompt_version == "user_story_v1"
    assert result.completion.input_tokens > 0
    assert result.completion.output_tokens > 0
    print(f"\n{result.completion}\n{result.story.model_dump_json(indent=2)}")
