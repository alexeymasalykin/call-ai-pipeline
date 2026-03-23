import json

import structlog
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.exceptions import LLMAnalysisError
from app.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.llm.qa_prompts import QA_SYSTEM_PROMPT, build_qa_user_prompt
from app.models.qa_schemas import QAResponse
from app.models.schemas import LLMResponse

logger = structlog.get_logger()


_MAX_PARSE_ATTEMPTS = 2


class ProxyAPIClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def close(self) -> None:
        await self._client.close()

    async def analyze_call(
        self,
        transcript: str,
        caller_number: str,
        duration: int,
        direction: str,
    ) -> LLMResponse:
        user_prompt = build_user_prompt(
            transcript, caller_number, duration, direction,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(_MAX_PARSE_ATTEMPTS):
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
        raise LLMAnalysisError(
            f"LLM returned invalid JSON after {_MAX_PARSE_ATTEMPTS} attempts "
            f"(prompt_version={PROMPT_VERSION})"
        )

    async def analyze_qa(
        self,
        transcript: str,
        manager_name: str | None,
        duration: int,
    ) -> QAResponse:
        user_prompt = build_qa_user_prompt(transcript, manager_name, duration)
        messages = [
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(_MAX_PARSE_ATTEMPTS):
            raw = await self._call_llm(messages)
            result = self._parse_qa_response(raw)
            if result is not None:
                return result
            logger.warning(
                "qa_invalid_json", attempt=attempt + 1, raw_response=raw[:200],
            )
        raise LLMAnalysisError(
            f"QA LLM returned invalid JSON after {_MAX_PARSE_ATTEMPTS} attempts"
        )

    async def _call_llm(self, messages: list[dict]) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        if not response.choices:
            raise LLMAnalysisError("LLM returned response with no choices")
        choice = response.choices[0]
        if not choice.message.content:
            raise LLMAnalysisError(
                f"LLM returned empty content "
                f"(finish_reason={choice.finish_reason})"
            )
        return choice.message.content

    @staticmethod
    def _parse_response(raw: str) -> LLMResponse | None:
        try:
            data = json.loads(raw)
            return LLMResponse.model_validate(data)
        except json.JSONDecodeError as exc:
            logger.warning("llm_json_decode_error", error=str(exc))
            return None
        except ValidationError as exc:
            logger.warning("llm_validation_error", errors=exc.errors())
            return None

    @staticmethod
    def _parse_qa_response(raw: str) -> QAResponse | None:
        try:
            data = json.loads(raw)
            # LLM may return null for entire stage blocks — normalize to empty dict
            stages = data.get("stage_scores")
            if isinstance(stages, dict):
                for key in ("exit_to_dm", "opening", "development", "closing", "objection_handling"):
                    if stages.get(key) is None:
                        stages[key] = {}
            return QAResponse.model_validate(data)
        except json.JSONDecodeError as exc:
            logger.warning("qa_json_decode_error", error=str(exc))
            return None
        except ValidationError as exc:
            logger.warning("qa_validation_error", errors=exc.errors())
            return None
