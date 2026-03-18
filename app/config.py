from typing import Literal

from pydantic import Field
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

    REDIS_URL: str = "redis://redis:6379/0"

    MIN_CALL_DURATION: int = Field(default=15, gt=0)
    WEBHOOK_SECRET: str
    ALERT_WEBHOOK_URL: str = ""
    ADMIN_TOKEN: str
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
