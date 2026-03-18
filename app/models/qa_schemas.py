"""QA (quality assessment) response schemas."""

from pydantic import BaseModel, Field


class QAStageScore(BaseModel, frozen=True):
    score: int = Field(ge=0, le=10)
    passed: bool
    comment: str | None = None


class QAStageScores(BaseModel, frozen=True):
    exit_to_dm: QAStageScore
    opening: QAStageScore
    development: QAStageScore
    closing: QAStageScore
    objection_handling: QAStageScore


class QAResponse(BaseModel, frozen=True):
    """Structured QA analysis from LLM."""

    product_detected: str = ""
    segment_detected: str = ""
    stage_scores: QAStageScores
    critical_errors: list[str] = Field(default_factory=list)
    total_score: int = Field(ge=1, le=10)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    manager_name: str | None = None
