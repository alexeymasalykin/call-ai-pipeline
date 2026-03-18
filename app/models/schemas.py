from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Qualification(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    REJECTED = "rejected"
    SPAM = "spam"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class CallData(BaseModel, frozen=True):
    """Incoming call data from Novofon webhook."""

    call_id: str = Field(min_length=1)
    caller_number: str = Field(min_length=1)
    called_number: str = Field(min_length=1)
    duration: int = Field(ge=0)
    direction: Literal["incoming", "outgoing"]
    timestamp: datetime
    recording_url: str | None = None


class LLMResponse(BaseModel, frozen=True):
    """Structured analysis from LLM."""

    client_name: str | None = None
    company: str | None = None
    client_request: str | None = None
    our_offer: str | None = None
    budget_mentioned: str | None = None
    summary: str = Field(min_length=1)
    qualification: Qualification
    sentiment: Sentiment
    next_action: str | None = None
    objections: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    decision_maker: bool | None = None
    manager_name: str | None = None
    call_direction: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator(
        "client_name", "company", "client_request", "our_offer",
        "budget_mentioned", "next_action", "manager_name",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
        return v


