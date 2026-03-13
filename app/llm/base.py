from typing import Protocol

from app.models.schemas import LLMResponse


class LLMClient(Protocol):
    async def analyze_call(
        self, transcript: str, caller_number: str, duration: int
    ) -> LLMResponse: ...

    async def close(self) -> None: ...
