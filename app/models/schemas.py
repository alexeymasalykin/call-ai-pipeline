from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class CallData(BaseModel):
    """Incoming call data from Novofon webhook."""

    call_id: str
    caller_number: str
    called_number: str
    duration: int
    direction: Literal["incoming", "outgoing"]
    timestamp: datetime
    recording_url: Optional[str] = None


class LLMResponse(BaseModel):
    """Structured analysis from LLM."""

    client_name: Optional[str] = None
    company: Optional[str] = None
    request: Optional[str] = None
    budget_mentioned: Optional[str] = None
    summary: str
    qualification: Literal["hot", "warm", "cold", "spam"]
    next_action: Optional[str] = None
    sentiment: Literal["positive", "neutral", "negative"]
    tags: list[str] = []


class LeadData(BaseModel):
    """Data for creating a lead in Bitrix24."""

    title: str
    client_name: Optional[str] = None
    company: Optional[str] = None
    phone: str
    summary: str
    qualification: str
    source: str = "CALL"
