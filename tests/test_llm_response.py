import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import LLMAnalysisError
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import LLMResponse


@pytest.fixture
def client():
    return ProxyAPIClient(
        api_key="test_key",
        base_url="https://api.proxyapi.ru/openai/v1",
        model="gpt-4o-mini",
    )


def _make_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class TestProxyAPIClient:
    @pytest.mark.asyncio
    async def test_analyze_call_valid_json(self, client):
        valid_json = json.dumps({
            "client_name": "Иван",
            "company": None,
            "client_request": "Консультация",
            "our_offer": None,
            "budget_mentioned": None,
            "summary": "Клиент позвонил для консультации.",
            "qualification": "warm",
            "next_action": "Перезвонить",
            "sentiment": "neutral",
            "objections": [],
            "pain_points": [],
            "decision_maker": None,
            "manager_name": None,
            "call_direction": "incoming",
            "tags": ["консультация"],
        })
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=_make_completion(valid_json),
        ):
            result = await client.analyze_call(
                transcript="тест", caller_number="79001234567",
                duration=30, direction="incoming",
            )
            assert isinstance(result, LLMResponse)
            assert result.client_name == "Иван"
            assert result.qualification == "warm"
            assert result.call_direction == "incoming"

    @pytest.mark.asyncio
    async def test_analyze_call_invalid_json_retries(self, client):
        valid_json = json.dumps({
            "client_name": None,
            "company": None,
            "client_request": None,
            "our_offer": None,
            "budget_mentioned": None,
            "summary": "Тест.",
            "qualification": "cold",
            "next_action": None,
            "sentiment": "neutral",
            "objections": [],
            "pain_points": [],
            "decision_maker": None,
            "manager_name": None,
            "call_direction": "incoming",
            "tags": [],
        })
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[
                _make_completion("not valid json {{{"),
                _make_completion(valid_json),
            ],
        ):
            result = await client.analyze_call(
                transcript="тест", caller_number="79001234567",
                duration=30, direction="incoming",
            )
            assert result.summary == "Тест."

    @pytest.mark.asyncio
    async def test_analyze_call_double_failure_raises_error(self, client):
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[
                _make_completion("bad json"),
                _make_completion("still bad json"),
            ],
        ):
            with pytest.raises(LLMAnalysisError, match="invalid JSON after 2 attempts"):
                await client.analyze_call(
                    transcript="тест", caller_number="79001234567",
                    duration=30, direction="incoming",
                )

    @pytest.mark.asyncio
    async def test_analyze_call_empty_content_raises_error(self, client):
        choice = MagicMock()
        choice.message.content = None
        choice.finish_reason = "content_filter"
        response = MagicMock()
        response.choices = [choice]

        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            with pytest.raises(LLMAnalysisError, match="empty content"):
                await client.analyze_call(
                    transcript="тест", caller_number="79001234567",
                    duration=30, direction="incoming",
                )
