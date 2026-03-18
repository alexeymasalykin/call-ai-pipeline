from typing import Protocol

from app.models.qa_schemas import QAResponse
from app.models.schemas import LLMResponse


class LLMClient(Protocol):
    async def analyze_call(
        self,
        transcript: str,
        caller_number: str,
        duration: int,
        direction: str,
    ) -> LLMResponse: ...

    async def analyze_qa(
        self,
        transcript: str,
        manager_name: str | None,
        duration: int,
    ) -> QAResponse: ...

    async def close(self) -> None: ...
