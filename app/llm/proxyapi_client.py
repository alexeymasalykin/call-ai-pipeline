import json

import structlog
from openai import AsyncOpenAI

from app.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.models.schemas import LLMResponse

logger = structlog.get_logger()

_FALLBACK = LLMResponse(
    summary="Ошибка анализа",
    qualification="cold",
    sentiment="neutral",
    tags=[],
)


class ProxyAPIClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def analyze_call(
        self, transcript: str, caller_number: str, duration: int
    ) -> LLMResponse:
        user_prompt = build_user_prompt(transcript, caller_number, duration)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(2):
            raw = await self._call_llm(messages)
            result = self._parse_response(raw)
            if result is not None:
                return result
            logger.warning(
                "llm_invalid_json",
                attempt=attempt + 1,
                prompt_version=PROMPT_VERSION,
                raw_response=raw[:200],
            )
        logger.error("llm_fallback", prompt_version=PROMPT_VERSION)
        return _FALLBACK

    async def _call_llm(self, messages: list[dict]) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_response(raw: str) -> LLMResponse | None:
        try:
            data = json.loads(raw)
            return LLMResponse.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return None
