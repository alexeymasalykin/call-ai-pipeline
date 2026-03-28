import json
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    NOVOFON_LOGIN: str
    NOVOFON_PASSWORD: str

    YANDEX_CLOUD_FOLDER_ID: str
    YANDEX_CLOUD_SA_KEY_FILE: str = "service_account_key.json"
    YANDEX_S3_BUCKET: str = "call-ai-pipeline-audio"
    YANDEX_S3_ACCESS_KEY: str
    YANDEX_S3_SECRET_KEY: str
    YANDEX_S3_ENDPOINT: str = "https://storage.yandexcloud.net"

    PROXYAPI_KEY: str
    LLM_MODEL: str = Field(default="gpt-4o-mini", min_length=1)
    LLM_BASE_URL: str = "https://api.proxyapi.ru/openai/v1"

    BITRIX24_WEBHOOK_URL: str
    BITRIX24_QA_ENTITY_TYPE_ID: int = 1040
    BITRIX24_QA_FIELD_MAP: dict[str, str] = Field(default_factory=dict)
    BITRIX24_COMPANY_SEGMENT_FIELD: str = ""

    @field_validator("BITRIX24_QA_FIELD_MAP", mode="before")
    @classmethod
    def parse_qa_field_map(cls, v: str | dict) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        if not v or v.strip() == "{}":
            return {}
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"BITRIX24_QA_FIELD_MAP must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("BITRIX24_QA_FIELD_MAP must be a JSON object")
        return parsed

    REDIS_URL: str = "redis://redis:6379/0"

    CRM_RETRY_DELAY_SECONDS: int = Field(default=1800, gt=0)  # 30 min
    CRM_RETRY_MAX_ATTEMPTS: int = Field(default=3, gt=0)

    MIN_CALL_DURATION: int = Field(default=15, gt=0)
    WEBHOOK_SECRET: str
    ALERT_WEBHOOK_URL: str = ""
    ADMIN_TOKEN: str
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    CORS_ORIGINS: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
