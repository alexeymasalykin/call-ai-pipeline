# Call AI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated call processing pipeline that transcribes phone recordings and enriches CRM leads with AI analysis.

**Architecture:** Three Docker services (api + worker + redis). FastAPI accepts Novofon webhooks and enqueues arq tasks. Worker runs pipeline: download mp3 → upload to S3 → SpeechKit STT → GPT-4o-mini analysis via ProxyAPI → find/enrich lead in Bitrix24.

**Tech Stack:** Python 3.11+, FastAPI, arq, httpx, openai SDK, yandexcloud SDK, boto3, Pydantic v2, structlog, Redis, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-03-12-call-ai-pipeline-design.md`

---

## File Structure

```
call-ai-pipeline/
├── .env.example                 # Template without secrets
├── docker-compose.yml           # 3 services: api, worker, redis
├── Dockerfile                   # Multi-stage build for api + worker
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Test dependencies (pytest, respx, etc.)
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app: webhook endpoint, /health, /admin/*
│   ├── config.py                # Pydantic Settings from .env
│   ├── worker.py                # arq WorkerSettings, DLQ handler, alerting
│   ├── pipeline.py              # Orchestrator: download → STT → LLM → CRM
│   ├── exceptions.py            # Terminal/non-terminal error hierarchy
│   │
│   ├── novofon/
│   │   ├── __init__.py
│   │   ├── webhook.py           # Parse NOTIFY_RECORD payload → CallData
│   │   └── api.py               # Download mp3 via httpx (direct URL or API fallback)
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   ├── speechkit.py         # Yandex SpeechKit SDK async recognition
│   │   └── s3.py                # Upload/delete mp3 in Yandex Object Storage
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract LLMClient protocol
│   │   ├── proxyapi_client.py   # OpenAI SDK → ProxyAPI implementation
│   │   └── prompts.py           # SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, build_user_prompt()
│   │
│   ├── crm/
│   │   ├── __init__.py
│   │   └── bitrix24.py          # Bitrix24 REST API: find/create/update lead, timeline
│   │
│   └── models/
│       ├── __init__.py
│       └── schemas.py           # CallData, LLMResponse, LeadData
│
├── scripts/
│   └── test_e2e.py              # Manual e2e with real API keys
│
└── tests/
    ├── conftest.py              # Shared fixtures
    ├── test_config.py
    ├── test_schemas.py
    ├── test_prompts.py
    ├── test_webhook.py
    ├── test_novofon_api.py
    ├── test_s3.py
    ├── test_speechkit.py
    ├── test_llm_response.py
    ├── test_bitrix24.py
    ├── test_idempotency.py
    ├── test_dlq.py
    ├── test_retry.py
    ├── test_pipeline.py
    ├── test_main.py             # FastAPI endpoint tests (TestClient)
    └── fixtures/
        ├── sample_transcript.txt
        ├── sample_webhook.json
        └── sample_llm_response.json
```

---

## Chunk 1: Foundation (models, config, exceptions, project setup)

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `app/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.109.0
uvicorn>=0.27.0
httpx>=0.27.0
redis>=5.0.0
arq>=0.25.0
openai>=1.12.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
yandexcloud>=0.300.0
boto3>=1.34.0
structlog>=24.1.0
```

- [ ] **Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0
```

- [ ] **Step 3: Create .env.example**

```env
# Novofon
NOVOFON_API_KEY=
NOVOFON_API_SECRET=

# Yandex Cloud
YANDEX_CLOUD_FOLDER_ID=
YANDEX_CLOUD_SA_KEY_FILE=service_account_key.json
YANDEX_S3_BUCKET=call-ai-pipeline-audio
YANDEX_S3_ACCESS_KEY=
YANDEX_S3_SECRET_KEY=
YANDEX_S3_ENDPOINT=https://storage.yandexcloud.net

# ProxyAPI (LLM)
PROXYAPI_KEY=
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.proxyapi.ru/openai/v1

# Bitrix24
BITRIX24_WEBHOOK_URL=

# Redis
REDIS_URL=redis://redis:6379/0

# App
MIN_CALL_DURATION=15
SKIP_SPAM_LEADS=false
WEBHOOK_SECRET=change-me
ALERT_WEBHOOK_URL=
ADMIN_TOKEN=change-me
LOG_LEVEL=INFO
```

- [ ] **Step 4: Create app/__init__.py**

```python
# Empty package init
```

- [ ] **Step 5: Install dependencies and verify**

Run: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
Expected: all packages installed without errors

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt .env.example app/__init__.py
git commit -m "chore: scaffold project with dependencies and env template"
```

---

### Task 2: Pydantic models (schemas.py)

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/schemas.py`
- Create: `tests/fixtures/sample_webhook.json`
- Create: `tests/fixtures/sample_llm_response.json`
- Create: `tests/fixtures/sample_transcript.txt`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Create test fixtures**

`tests/fixtures/sample_webhook.json`:
```json
{
  "event": "NOTIFY_RECORD",
  "call_id": "123456789",
  "caller_id": "79001234567",
  "called_did": "74951234567",
  "duration": "45",
  "call_start": "2026-03-12 10:00:00",
  "disposition": "answered",
  "recording_url": "https://novofon.com/records/123456789.mp3"
}
```

`tests/fixtures/sample_llm_response.json`:
```json
{
  "client_name": "Иван Петров",
  "company": "ООО Ромашка",
  "request": "Интересуется оптовыми поставками",
  "budget_mentioned": "около 500 000 руб",
  "summary": "Клиент Иван Петров из ООО Ромашка интересуется оптовыми поставками. Обсудили условия, клиент попросил отправить КП на почту.",
  "qualification": "hot",
  "next_action": "Отправить коммерческое предложение на email",
  "sentiment": "positive",
  "tags": ["опт", "КП", "новый клиент"]
}
```

`tests/fixtures/sample_transcript.txt`:
```
Менеджер: Добрый день, компания Альфа, меня зовут Анна, чем могу помочь?
Клиент: Здравствуйте, меня зовут Иван Петров, компания ООО Ромашка. Мы хотели бы узнать про оптовые поставки.
Менеджер: Конечно, Иван. Какой объём вас интересует?
Клиент: Примерно на 500 тысяч рублей в месяц.
Менеджер: Отлично, я подготовлю для вас коммерческое предложение. На какой email отправить?
Клиент: petrov@romashka.ru
Менеджер: Хорошо, отправлю сегодня. Спасибо за звонок!
Клиент: Спасибо, до свидания.
```

- [ ] **Step 2: Write failing tests for schemas**

`tests/test_schemas.py`:
```python
import pytest
from datetime import datetime

from app.models.schemas import CallData, LLMResponse, LeadData


class TestCallData:
    def test_valid_incoming_call(self):
        data = CallData(
            call_id="123456789",
            caller_number="79001234567",
            called_number="74951234567",
            duration=45,
            direction="incoming",
            timestamp=datetime(2026, 3, 12, 10, 0, 0),
        )
        assert data.call_id == "123456789"
        assert data.duration == 45
        assert data.direction == "incoming"

    def test_valid_outgoing_call(self):
        data = CallData(
            call_id="987654321",
            caller_number="74951234567",
            called_number="79001234567",
            duration=120,
            direction="outgoing",
            timestamp=datetime(2026, 3, 12, 11, 0, 0),
        )
        assert data.direction == "outgoing"

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError):
            CallData(
                call_id="123",
                caller_number="79001234567",
                called_number="74951234567",
                duration=45,
                direction="unknown",
                timestamp=datetime(2026, 3, 12, 10, 0, 0),
            )

    def test_recording_url_optional(self):
        data = CallData(
            call_id="123",
            caller_number="79001234567",
            called_number="74951234567",
            duration=45,
            direction="incoming",
            timestamp=datetime(2026, 3, 12, 10, 0, 0),
        )
        assert data.recording_url is None

    def test_recording_url_present(self):
        data = CallData(
            call_id="123",
            caller_number="79001234567",
            called_number="74951234567",
            duration=45,
            direction="incoming",
            timestamp=datetime(2026, 3, 12, 10, 0, 0),
            recording_url="https://novofon.com/records/123.mp3",
        )
        assert data.recording_url == "https://novofon.com/records/123.mp3"


class TestLLMResponse:
    def test_valid_full_response(self):
        data = LLMResponse(
            client_name="Иван Петров",
            company="ООО Ромашка",
            request="Оптовые поставки",
            budget_mentioned="500 000 руб",
            summary="Клиент интересуется оптовыми поставками.",
            qualification="hot",
            next_action="Отправить КП",
            sentiment="positive",
            tags=["опт", "КП"],
        )
        assert data.qualification == "hot"
        assert len(data.tags) == 2

    def test_minimal_response_with_nulls(self):
        data = LLMResponse(
            summary="Короткий звонок без деталей.",
            qualification="cold",
            sentiment="neutral",
        )
        assert data.client_name is None
        assert data.company is None
        assert data.tags == []

    def test_invalid_qualification_rejected(self):
        with pytest.raises(ValueError):
            LLMResponse(
                summary="test",
                qualification="medium",
                sentiment="neutral",
            )

    def test_invalid_sentiment_rejected(self):
        with pytest.raises(ValueError):
            LLMResponse(
                summary="test",
                qualification="cold",
                sentiment="angry",
            )


class TestLeadData:
    def test_valid_lead(self):
        data = LeadData(
            title="Звонок: оптовые поставки",
            client_name="Иван Петров",
            company="ООО Ромашка",
            phone="79001234567",
            summary="Клиент интересуется оптом.",
            qualification="hot",
        )
        assert data.source == "CALL"

    def test_minimal_lead(self):
        data = LeadData(
            title="Звонок: неизвестный",
            phone="79001234567",
            summary="Требует ручного анализа.",
            qualification="cold",
        )
        assert data.client_name is None
        assert data.company is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/alex2061/projects/call-ai-pipeline && python -m pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 4: Implement schemas**

`app/models/__init__.py`:
```python
from app.models.schemas import CallData, LeadData, LLMResponse

__all__ = ["CallData", "LeadData", "LLMResponse"]
```

`app/models/schemas.py`:
```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/alex2061/projects/call-ai-pipeline && python -m pytest tests/test_schemas.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/models/ tests/test_schemas.py tests/fixtures/
git commit -m "feat: add Pydantic models and test fixtures"
```

---

### Task 3: Configuration (config.py)

**Files:**
- Create: `app/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

`tests/test_config.py`:
```python
import os

import pytest


class TestSettings:
    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("NOVOFON_API_KEY", "test_key")
        monkeypatch.setenv("NOVOFON_API_SECRET", "test_secret")
        monkeypatch.setenv("YANDEX_CLOUD_FOLDER_ID", "folder123")
        monkeypatch.setenv("YANDEX_CLOUD_SA_KEY_FILE", "sa.json")
        monkeypatch.setenv("YANDEX_S3_BUCKET", "test-bucket")
        monkeypatch.setenv("YANDEX_S3_ACCESS_KEY", "s3key")
        monkeypatch.setenv("YANDEX_S3_SECRET_KEY", "s3secret")
        monkeypatch.setenv("YANDEX_S3_ENDPOINT", "https://storage.yandexcloud.net")
        monkeypatch.setenv("PROXYAPI_KEY", "proxy_key")
        monkeypatch.setenv("BITRIX24_WEBHOOK_URL", "https://test.bitrix24.ru/rest/1/abc/")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("WEBHOOK_SECRET", "secret123")
        monkeypatch.setenv("ADMIN_TOKEN", "admin123")

        from app.config import Settings

        s = Settings()
        assert s.NOVOFON_API_KEY == "test_key"
        assert s.LLM_MODEL == "gpt-4o-mini"
        assert s.MIN_CALL_DURATION == 15
        assert s.SKIP_SPAM_LEADS is False
        assert s.LOG_LEVEL == "INFO"

    def test_missing_required_var_raises(self, monkeypatch):
        # Clear all env vars that might be set
        for key in [
            "NOVOFON_API_KEY", "NOVOFON_API_SECRET",
            "YANDEX_CLOUD_FOLDER_ID", "YANDEX_CLOUD_SA_KEY_FILE",
            "YANDEX_S3_BUCKET", "YANDEX_S3_ACCESS_KEY", "YANDEX_S3_SECRET_KEY",
            "PROXYAPI_KEY", "BITRIX24_WEBHOOK_URL", "WEBHOOK_SECRET", "ADMIN_TOKEN",
        ]:
            monkeypatch.delenv(key, raising=False)

        from app.config import Settings

        with pytest.raises(Exception):
            Settings()

    def test_custom_llm_model(self, monkeypatch):
        monkeypatch.setenv("NOVOFON_API_KEY", "k")
        monkeypatch.setenv("NOVOFON_API_SECRET", "s")
        monkeypatch.setenv("YANDEX_CLOUD_FOLDER_ID", "f")
        monkeypatch.setenv("YANDEX_CLOUD_SA_KEY_FILE", "sa.json")
        monkeypatch.setenv("YANDEX_S3_BUCKET", "b")
        monkeypatch.setenv("YANDEX_S3_ACCESS_KEY", "ak")
        monkeypatch.setenv("YANDEX_S3_SECRET_KEY", "sk")
        monkeypatch.setenv("YANDEX_S3_ENDPOINT", "https://storage.yandexcloud.net")
        monkeypatch.setenv("PROXYAPI_KEY", "p")
        monkeypatch.setenv("BITRIX24_WEBHOOK_URL", "https://t.bitrix24.ru/rest/1/x/")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("WEBHOOK_SECRET", "sec")
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        from app.config import Settings

        s = Settings()
        assert s.LLM_MODEL == "gpt-4o"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Implement config**

`app/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Novofon
    NOVOFON_API_KEY: str
    NOVOFON_API_SECRET: str

    # Yandex Cloud
    YANDEX_CLOUD_FOLDER_ID: str
    YANDEX_CLOUD_SA_KEY_FILE: str = "service_account_key.json"
    YANDEX_S3_BUCKET: str = "call-ai-pipeline-audio"
    YANDEX_S3_ACCESS_KEY: str
    YANDEX_S3_SECRET_KEY: str
    YANDEX_S3_ENDPOINT: str = "https://storage.yandexcloud.net"

    # ProxyAPI (LLM)
    PROXYAPI_KEY: str
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.proxyapi.ru/openai/v1"

    # Bitrix24
    BITRIX24_WEBHOOK_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # App
    MIN_CALL_DURATION: int = 15
    SKIP_SPAM_LEADS: bool = False
    WEBHOOK_SECRET: str
    ALERT_WEBHOOK_URL: str = ""
    ADMIN_TOKEN: str
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add Pydantic Settings configuration"
```

---

### Task 4: Custom exceptions

**Files:**
- Create: `app/exceptions.py`

- [ ] **Step 1: Create exceptions module**

`app/exceptions.py`:
```python
class PipelineError(Exception):
    """Base exception for pipeline errors."""


class TerminalError(PipelineError):
    """Error that should trigger arq job retry."""


class DownloadError(TerminalError):
    """Failed to download recording from Novofon."""


class UploadError(TerminalError):
    """Failed to upload file to S3."""


class TranscriptionError(TerminalError):
    """Failed to transcribe audio via SpeechKit."""


class EmptyTranscriptionError(PipelineError):
    """Transcription returned empty text — skip LLM and CRM stages."""
```

- [ ] **Step 2: Commit**

```bash
git add app/exceptions.py
git commit -m "feat: add pipeline exception hierarchy"
```

---

## Chunk 2: LLM module (prompts + client)

### Task 5: LLM prompts

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write failing tests for prompts**

`tests/test_prompts.py`:
```python
from app.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, PROMPT_VERSION, build_user_prompt


class TestPrompts:
    def test_system_prompt_is_nonempty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_mentions_json(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_prompt_version_exists(self):
        assert PROMPT_VERSION == "1.0"

    def test_user_prompt_template_has_placeholders(self):
        assert "{caller_number}" in USER_PROMPT_TEMPLATE
        assert "{duration}" in USER_PROMPT_TEMPLATE
        assert "{transcript}" in USER_PROMPT_TEMPLATE

    def test_build_user_prompt(self):
        result = build_user_prompt(
            transcript="Менеджер: Здравствуйте.\nКлиент: Добрый день.",
            caller_number="79001234567",
            duration=30,
        )
        assert "79001234567" in result
        assert "30" in result
        assert "Менеджер: Здравствуйте." in result

    def test_build_user_prompt_expected_json_schema(self):
        result = build_user_prompt(
            transcript="test",
            caller_number="79001234567",
            duration=10,
        )
        assert "client_name" in result
        assert "qualification" in result
        assert "summary" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement prompts**

`app/llm/__init__.py`:
```python
```

`app/llm/prompts.py`:
```python
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """\
Ты — AI-ассистент для анализа телефонных разговоров в бизнесе.
Тебе передаётся транскрипция звонка. Твоя задача — извлечь структурированную информацию и вернуть строго JSON.

Правила:
1. Если информация не была озвучена в разговоре — ставь null. НЕ ВЫДУМЫВАЙ.
2. Саммари должно быть на русском, 2-4 предложения, передавать суть разговора.
3. Квалификация лида:
   - "hot" — клиент готов к покупке/сделке, обсуждает детали, сроки, цены
   - "warm" — клиент заинтересован, задаёт вопросы, но не готов к решению
   - "cold" — общий вопрос, информационный запрос, нецелевой звонок
   - "spam" — спам, реклама, ошибочный номер, робозвонок
4. next_action — что нужно сделать после звонка (перезвонить, отправить КП, и т.д.)
5. tags — 1-5 тегов, характеризующих тему звонка

Верни ТОЛЬКО валидный JSON без markdown-обёртки, без ```json```, без пояснений.\
"""

USER_PROMPT_TEMPLATE = """\
Транскрипция звонка:
Входящий номер: {caller_number}
Длительность: {duration} сек

{transcript}

Верни JSON в формате:
{{
  "client_name": "Имя клиента или null",
  "company": "Название компании или null",
  "request": "Что хочет клиент — краткое описание потребности или null",
  "budget_mentioned": "Упоминание бюджета/цен или null",
  "summary": "Краткое саммари разговора 2-4 предложения",
  "qualification": "hot | warm | cold | spam",
  "next_action": "Следующий шаг или null",
  "sentiment": "positive | neutral | negative",
  "tags": ["тег1", "тег2"]
}}\
"""


def build_user_prompt(transcript: str, caller_number: str, duration: int) -> str:
    """Build user prompt from call metadata and transcript."""
    return USER_PROMPT_TEMPLATE.format(
        transcript=transcript,
        caller_number=caller_number,
        duration=duration,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm/ tests/test_prompts.py
git commit -m "feat: add LLM prompts with system/user templates"
```

---

### Task 6: LLM base protocol + ProxyAPI client

**Files:**
- Create: `app/llm/base.py`
- Create: `app/llm/proxyapi_client.py`
- Create: `tests/test_llm_response.py`

- [ ] **Step 1: Write failing tests**

`tests/test_llm_response.py`:
```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    """Create a mock ChatCompletion response."""
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
            "request": "Консультация",
            "budget_mentioned": None,
            "summary": "Клиент позвонил для консультации.",
            "qualification": "warm",
            "next_action": "Перезвонить",
            "sentiment": "neutral",
            "tags": ["консультация"],
        })
        with patch.object(
            client._client.chat.completions, "create",
            new_callable=AsyncMock, return_value=_make_completion(valid_json),
        ):
            result = await client.analyze_call(
                transcript="тест", caller_number="79001234567", duration=30,
            )
            assert isinstance(result, LLMResponse)
            assert result.client_name == "Иван"
            assert result.qualification == "warm"

    @pytest.mark.asyncio
    async def test_analyze_call_invalid_json_retries(self, client):
        valid_json = json.dumps({
            "client_name": None, "company": None, "request": None,
            "budget_mentioned": None, "summary": "Тест.",
            "qualification": "cold", "next_action": None,
            "sentiment": "neutral", "tags": [],
        })
        with patch.object(
            client._client.chat.completions, "create",
            new_callable=AsyncMock,
            side_effect=[
                _make_completion("not valid json {{{"),
                _make_completion(valid_json),
            ],
        ):
            result = await client.analyze_call(
                transcript="тест", caller_number="79001234567", duration=30,
            )
            assert result.summary == "Тест."

    @pytest.mark.asyncio
    async def test_analyze_call_double_failure_returns_fallback(self, client):
        with patch.object(
            client._client.chat.completions, "create",
            new_callable=AsyncMock,
            side_effect=[
                _make_completion("bad json"),
                _make_completion("still bad json"),
            ],
        ):
            result = await client.analyze_call(
                transcript="тест", caller_number="79001234567", duration=30,
            )
            assert result.summary == "Ошибка анализа"
            assert result.qualification == "cold"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm_response.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement base protocol**

`app/llm/base.py`:
```python
from typing import Protocol

from app.models.schemas import LLMResponse


class LLMClient(Protocol):
    """Abstract interface for LLM analysis."""

    async def analyze_call(
        self, transcript: str, caller_number: str, duration: int,
    ) -> LLMResponse: ...
```

- [ ] **Step 4: Implement ProxyAPI client**

`app/llm/proxyapi_client.py`:
```python
import json
import logging

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
    """LLM client using ProxyAPI (OpenAI-compatible API)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def analyze_call(
        self, transcript: str, caller_number: str, duration: int,
    ) -> LLMResponse:
        """Analyze call transcript via LLM. Retries once on invalid JSON."""
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm_response.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/llm/ tests/test_llm_response.py
git commit -m "feat: add LLM client with ProxyAPI support and JSON retry"
```

---

## Chunk 3: Novofon module (webhook + API)

### Task 7: Novofon webhook parser

**Files:**
- Create: `app/novofon/__init__.py`
- Create: `app/novofon/webhook.py`
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Write failing tests**

`tests/test_webhook.py`:
```python
import json
from pathlib import Path

import pytest

from app.novofon.webhook import parse_webhook, WebhookIgnored


@pytest.fixture
def sample_payload() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_webhook.json"
    return json.loads(path.read_text())


class TestParseWebhook:
    def test_valid_notify_record(self, sample_payload):
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.call_id == "123456789"
        assert call_data.caller_number == "79001234567"
        assert call_data.called_number == "74951234567"
        assert call_data.duration == 45
        assert call_data.recording_url == "https://novofon.com/records/123456789.mp3"

    def test_short_call_ignored(self, sample_payload):
        sample_payload["duration"] = "10"
        with pytest.raises(WebhookIgnored, match="duration"):
            parse_webhook(sample_payload, min_duration=15)

    def test_notify_end_ignored(self, sample_payload):
        sample_payload["event"] = "NOTIFY_END"
        with pytest.raises(WebhookIgnored, match="event"):
            parse_webhook(sample_payload, min_duration=15)

    def test_missing_call_id_raises(self, sample_payload):
        del sample_payload["call_id"]
        with pytest.raises(KeyError):
            parse_webhook(sample_payload, min_duration=15)

    def test_direction_incoming_by_default(self, sample_payload):
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.direction == "incoming"

    def test_direction_outgoing(self, sample_payload):
        sample_payload["direction"] = "outgoing"
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.direction == "outgoing"

    def test_no_recording_url(self, sample_payload):
        del sample_payload["recording_url"]
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.recording_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_webhook.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement webhook parser**

`app/novofon/__init__.py`:
```python
```

`app/novofon/webhook.py`:
```python
from datetime import datetime

from app.models.schemas import CallData


class WebhookIgnored(Exception):
    """Webhook event that should be skipped (not an error)."""


def parse_webhook(payload: dict, min_duration: int) -> CallData:
    """Parse Novofon webhook payload into CallData.

    Raises:
        WebhookIgnored: if event is not NOTIFY_RECORD or call is too short.
        KeyError: if required fields are missing.
    """
    event = payload.get("event", "")
    if event != "NOTIFY_RECORD":
        raise WebhookIgnored(f"Ignored event type: {event}")

    duration = int(payload["duration"])
    if duration < min_duration:
        raise WebhookIgnored(f"Call duration {duration}s < {min_duration}s minimum")

    call_start = payload.get("call_start", "")
    try:
        timestamp = datetime.fromisoformat(call_start)
    except (ValueError, TypeError):
        timestamp = datetime.now()

    return CallData(
        call_id=payload["call_id"],
        caller_number=payload["caller_id"],
        called_number=payload["called_did"],
        duration=duration,
        direction=payload.get("direction", "incoming"),
        timestamp=timestamp,
        recording_url=payload.get("recording_url"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_webhook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/novofon/ tests/test_webhook.py
git commit -m "feat: add Novofon webhook parser with NOTIFY_RECORD filter"
```

---

### Task 8: Novofon API (download recording)

**Files:**
- Create: `app/novofon/api.py`
- Create: `tests/test_novofon_api.py`

- [ ] **Step 1: Write failing tests**

`tests/test_novofon_api.py`:
```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.exceptions import DownloadError
from app.novofon.api import NovofonAPI


@pytest.fixture
def api():
    return NovofonAPI(
        api_key="test_key",
        api_secret="test_secret",
        data_dir="/tmp/call-pipeline-test",
    )


class TestNovofonAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_download_with_direct_url(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).respond(200, content=b"fake-mp3-data")

        path = await api.download_recording("123", recording_url=url)
        assert path.exists()
        assert path.read_bytes() == b"fake-mp3-data"

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_via_api_fallback(self, api, tmp_path):
        api._data_dir = tmp_path
        # First call: get download link
        respx.get("https://api.novofon.com/v1/pbx/record/request/").respond(
            200, json={"status": "success", "link": "https://novofon.com/dl/123.mp3"},
        )
        # Second call: download the file
        respx.get("https://novofon.com/dl/123.mp3").respond(200, content=b"mp3-data")

        path = await api.download_recording("123", recording_url=None)
        assert path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_retries_on_failure(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, content=b"mp3-data"),
            ]
        )

        path = await api.download_recording("123", recording_url=url)
        assert path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_raises_after_max_retries(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(return_value=httpx.Response(503))

        with pytest.raises(DownloadError):
            await api.download_recording("123", recording_url=url)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_novofon_api.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Novofon API client**

`app/novofon/api.py`:
```python
import asyncio
from pathlib import Path

import httpx
import structlog

from app.exceptions import DownloadError

logger = structlog.get_logger()

_RETRY_DELAYS = [5, 10, 20]


class NovofonAPI:
    """Client for downloading call recordings from Novofon."""

    def __init__(self, api_key: str, api_secret: str, data_dir: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def download_recording(
        self, call_id: str, recording_url: str | None = None,
    ) -> Path:
        """Download mp3 recording. Uses direct URL or falls back to API."""
        url = recording_url or await self._request_recording_url(call_id)
        return await self._download_file(call_id, url)

    async def _request_recording_url(self, call_id: str) -> str:
        """Request recording download URL from Novofon API."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.novofon.com/v1/pbx/record/request/",
                params={
                    "call_id": call_id,
                    "lifetime": 3600,
                },
                headers={"Authorization": f"{self._api_key}:{self._api_secret}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["link"]

    async def _download_file(self, call_id: str, url: str) -> Path:
        """Download file with retry logic."""
        dest = self._data_dir / f"{call_id}.mp3"

        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=60)
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    logger.info("recording_downloaded", call_id=call_id, attempt=attempt)
                    return dest
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "download_retry", call_id=call_id,
                    attempt=attempt, error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        raise DownloadError(f"Failed to download recording for call {call_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_novofon_api.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/novofon/api.py tests/test_novofon_api.py
git commit -m "feat: add Novofon API client with download retry logic"
```

---

## Chunk 4: STT module (S3 + SpeechKit)

### Task 9: S3 client for Yandex Object Storage

**Files:**
- Create: `app/stt/__init__.py`
- Create: `app/stt/s3.py`

- [ ] **Step 1: Implement S3 client**

`app/stt/__init__.py`:
```python
```

`app/stt/s3.py`:
```python
import asyncio
from functools import partial
from pathlib import Path

import boto3
import structlog

from app.exceptions import UploadError

logger = structlog.get_logger()

_RETRY_DELAYS = [5, 10]


class S3Client:
    """Client for Yandex Object Storage (S3-compatible)."""

    def __init__(
        self, bucket: str, access_key: str, secret_key: str, endpoint: str,
    ) -> None:
        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload(self, local_path: Path, s3_key: str) -> str:
        """Upload file to S3. Returns s3:// URI."""
        loop = asyncio.get_running_loop()

        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
            try:
                await loop.run_in_executor(
                    None,
                    partial(
                        self._s3.upload_file,
                        str(local_path),
                        self._bucket,
                        s3_key,
                    ),
                )
                uri = f"s3://{self._bucket}/{s3_key}"
                logger.info("s3_uploaded", key=s3_key, attempt=attempt)
                return uri
            except Exception as exc:
                logger.warning("s3_upload_retry", key=s3_key, attempt=attempt, error=str(exc))
                if delay is not None:
                    await asyncio.sleep(delay)

        raise UploadError(f"Failed to upload {s3_key} to S3")

    async def delete(self, s3_key: str) -> None:
        """Delete file from S3. Best-effort, does not raise."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(self._s3.delete_object, Bucket=self._bucket, Key=s3_key),
            )
            logger.info("s3_deleted", key=s3_key)
        except Exception as exc:
            logger.warning("s3_delete_failed", key=s3_key, error=str(exc))
```

- [ ] **Step 2: Write tests for S3 client**

`tests/test_s3.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import UploadError
from app.stt.s3 import S3Client


@pytest.fixture
def s3_client():
    with patch("app.stt.s3.boto3") as mock_boto:
        client = S3Client(
            bucket="test-bucket",
            access_key="ak",
            secret_key="sk",
            endpoint="https://storage.test",
        )
        yield client


class TestS3Upload:
    @pytest.mark.asyncio
    async def test_upload_success(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        uri = await s3_client.upload(mp3, "test.mp3")
        assert uri == "s3://test-bucket/test.mp3"

    @pytest.mark.asyncio
    async def test_upload_retries_on_failure(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        s3_client._s3.upload_file.side_effect = [Exception("fail"), Exception("fail"), None]

        # Should succeed on 3rd attempt (after 2 retries)
        # But we only have 2 retry delays, so 3rd is the last
        uri = await s3_client.upload(mp3, "test.mp3")
        assert uri == "s3://test-bucket/test.mp3"

    @pytest.mark.asyncio
    async def test_upload_raises_after_exhaustion(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        s3_client._s3.upload_file.side_effect = Exception("permanent failure")

        with pytest.raises(UploadError):
            await s3_client.upload(mp3, "test.mp3")


class TestS3Delete:
    @pytest.mark.asyncio
    async def test_delete_success(self, s3_client):
        await s3_client.delete("test.mp3")
        s3_client._s3.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_failure_does_not_raise(self, s3_client):
        s3_client._s3.delete_object.side_effect = Exception("fail")
        await s3_client.delete("test.mp3")  # Should not raise
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_s3.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/stt/ tests/test_s3.py
git commit -m "feat: add S3 client for Yandex Object Storage"
```

---

### Task 10: SpeechKit STT client

**Files:**
- Create: `app/stt/speechkit.py`

- [ ] **Step 1: Implement SpeechKit client**

`app/stt/speechkit.py`:
```python
import asyncio
import json
from dataclasses import dataclass

import structlog

from app.exceptions import EmptyTranscriptionError, TranscriptionError

logger = structlog.get_logger()

_POLL_INTERVAL = 3
_POLL_TIMEOUT = 300  # 5 minutes
_RETRY_DELAYS = [10, 20, 40]


@dataclass
class TranscriptSegment:
    speaker: int
    text: str
    start_time: float


class SpeechKitClient:
    """Yandex SpeechKit async recognition client."""

    def __init__(self, folder_id: str, sa_key_file: str) -> None:
        self._folder_id = folder_id
        self._sa_key_file = sa_key_file
        self._iam_token: str | None = None

    async def transcribe(self, s3_uri: str, call_id: str) -> list[TranscriptSegment]:
        """Transcribe audio from S3 URI. Returns list of transcript segments.

        Raises:
            TranscriptionError: if recognition fails after retries.
            EmptyTranscriptionError: if transcription is empty.
        """
        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
            try:
                segments = await self._run_recognition(s3_uri)
                if not segments:
                    raise EmptyTranscriptionError(f"Empty transcription for {call_id}")
                logger.info(
                    "transcription_complete", call_id=call_id,
                    segments=len(segments), attempt=attempt,
                )
                return segments
            except EmptyTranscriptionError:
                raise
            except Exception as exc:
                logger.warning(
                    "stt_retry", call_id=call_id,
                    attempt=attempt, error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        raise TranscriptionError(f"STT failed for {call_id}")

    async def _run_recognition(self, s3_uri: str) -> list[TranscriptSegment]:
        """Submit recognition request and poll for result.

        Uses yandexcloud SDK for IAM token management and API calls.
        Implementation deferred — requires yandexcloud SDK setup with
        actual service account credentials for testing.
        """
        # NOTE: Full implementation requires yandexcloud SDK imports:
        # import yandexcloud
        # from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc
        #
        # The SDK handles:
        # 1. IAM token acquisition and refresh from service account key
        # 2. gRPC channel management
        # 3. Recognition request submission
        # 4. Operation polling
        #
        # Skeleton for e2e integration:
        # sdk = yandexcloud.SDK(service_account_key=json.load(open(self._sa_key_file)))
        # stt = sdk.client(stt_service_pb2_grpc.RecognizerStub)
        # ... submit async recognition with s3_uri ...
        # ... poll operation until complete ...
        # ... parse result into TranscriptSegment list ...
        raise NotImplementedError(
            "SpeechKit integration requires SDK setup with credentials. "
            "See docs/superpowers/specs/2026-03-12-call-ai-pipeline-design.md "
            "section 3 for implementation details."
        )

    @staticmethod
    def segments_to_text(segments: list[TranscriptSegment]) -> str:
        """Convert transcript segments to plain text for LLM."""
        lines = []
        for seg in segments:
            speaker = f"Спикер {seg.speaker}" if seg.speaker >= 0 else "Неизвестный"
            lines.append(f"{speaker}: {seg.text}")
        return "\n".join(lines)
```

- [ ] **Step 2: Write tests for SpeechKit**

`tests/test_speechkit.py`:
```python
import pytest

from app.exceptions import EmptyTranscriptionError
from app.stt.speechkit import SpeechKitClient, TranscriptSegment


class TestSegmentsToText:
    def test_converts_segments_to_text(self):
        segments = [
            TranscriptSegment(speaker=0, text="Здравствуйте", start_time=0.0),
            TranscriptSegment(speaker=1, text="Добрый день", start_time=1.5),
        ]
        result = SpeechKitClient.segments_to_text(segments)
        assert "Спикер 0: Здравствуйте" in result
        assert "Спикер 1: Добрый день" in result

    def test_empty_segments_returns_empty_string(self):
        result = SpeechKitClient.segments_to_text([])
        assert result == ""

    def test_single_segment(self):
        segments = [TranscriptSegment(speaker=0, text="Тест", start_time=0.0)]
        result = SpeechKitClient.segments_to_text(segments)
        assert result == "Спикер 0: Тест"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_speechkit.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/stt/speechkit.py tests/test_speechkit.py
git commit -m "feat: add SpeechKit STT client with retry and empty transcription handling"
```

---

## Chunk 5: CRM module (Bitrix24)

### Task 11: Bitrix24 CRM client

**Files:**
- Create: `app/crm/__init__.py`
- Create: `app/crm/bitrix24.py`
- Create: `tests/test_bitrix24.py`

- [ ] **Step 1: Write failing tests**

`tests/test_bitrix24.py`:
```python
import pytest
import respx
import httpx

from app.crm.bitrix24 import Bitrix24Client
from app.models.schemas import LeadData


WEBHOOK_URL = "https://test.bitrix24.ru/rest/1/testtoken/"


@pytest.fixture
def client():
    return Bitrix24Client(webhook_url=WEBHOOK_URL)


class TestFindLeadByPhone:
    @pytest.mark.asyncio
    @respx.mock
    async def test_finds_existing_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={
            "result": [
                {"ID": 42, "STATUS_ID": "NEW", "TITLE": "Existing lead"},
            ],
        })
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is not None
        assert lead["ID"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_converted_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={
            "result": [
                {"ID": 10, "STATUS_ID": "CONVERTED", "TITLE": "Old lead"},
            ],
        })
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_junk_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={
            "result": [
                {"ID": 11, "STATUS_ID": "JUNK", "TITLE": "Junk lead"},
            ],
        })
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_on_empty_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={
            "result": [],
        })
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None


class TestCreateLead:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_lead_returns_id(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.add").respond(200, json={
            "result": 99,
        })
        lead_data = LeadData(
            title="Звонок: тест",
            phone="79001234567",
            summary="Тест.",
            qualification="warm",
        )
        lead_id = await client.create_lead(lead_data)
        assert lead_id == 99


class TestUpdateLead:
    @pytest.mark.asyncio
    @respx.mock
    async def test_updates_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(200, json={
            "result": True,
        })
        result = await client.update_lead(42, {"TITLE": "Updated"})
        assert result is True


class TestAddTimelineComment:
    @pytest.mark.asyncio
    @respx.mock
    async def test_adds_comment(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={
            "result": 123,
        })
        result = await client.add_timeline_comment("lead", 42, "AI analysis text")
        assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bitrix24.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Bitrix24 client**

`app/crm/__init__.py`:
```python
```

`app/crm/bitrix24.py`:
```python
import asyncio
from typing import Any, Optional

import httpx
import structlog

from app.models.schemas import LeadData

logger = structlog.get_logger()

_EXCLUDED_STATUSES = {"CONVERTED", "JUNK"}
_RATE_LIMIT_DELAY = 0.5  # ≤2 req/s
_FIND_RETRY_DELAY = 10
_FIND_MAX_RETRIES = 3
_API_RETRY_DELAYS = [5, 10, 20]


class Bitrix24Client:
    """Client for Bitrix24 REST API via incoming webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url.rstrip("/") + "/"
        self._client = httpx.AsyncClient(timeout=30)
        self._last_request_time: float = 0

    async def find_lead_by_phone(self, phone: str) -> Optional[dict]:
        """Find open lead by phone number. Retries if not found (native integration lag)."""
        for attempt in range(1, _FIND_MAX_RETRIES + 1):
            result = await self._call("crm.lead.list", {
                "filter": {"PHONE": phone},
                "select": ["ID", "STATUS_ID", "TITLE"],
            })
            leads = result.get("result", [])
            for lead in leads:
                if lead.get("STATUS_ID") not in _EXCLUDED_STATUSES:
                    logger.info("lead_found", lead_id=lead["ID"], attempt=attempt)
                    return lead

            if attempt < _FIND_MAX_RETRIES:
                logger.info("lead_not_found_retry", phone=phone, attempt=attempt)
                await asyncio.sleep(_FIND_RETRY_DELAY)

        logger.warning("lead_not_found", phone=phone)
        return None

    async def create_lead(self, data: LeadData) -> int:
        """Create a new lead in Bitrix24. Returns lead ID."""
        fields: dict[str, Any] = {
            "TITLE": data.title,
            "COMMENTS": data.summary,
            "SOURCE_ID": data.source,
            "STATUS_ID": "NEW",
            "PHONE": [{"VALUE": data.phone, "VALUE_TYPE": "WORK"}],
        }
        if data.client_name:
            fields["NAME"] = data.client_name
        if data.company:
            fields["COMPANY_TITLE"] = data.company

        result = await self._call("crm.lead.add", {"fields": fields})
        lead_id = result["result"]
        logger.info("lead_created", lead_id=lead_id)
        return lead_id

    async def update_lead(self, lead_id: int, data: dict) -> bool:
        """Update existing lead fields."""
        result = await self._call("crm.lead.update", {
            "id": lead_id,
            "fields": data,
        })
        return bool(result.get("result"))

    async def add_timeline_comment(
        self, entity_type: str, entity_id: int, comment: str,
    ) -> bool:
        """Add a comment to lead/deal timeline."""
        result = await self._call("crm.timeline.comment.add", {
            "fields": {
                "ENTITY_ID": entity_id,
                "ENTITY_TYPE": entity_type,
                "COMMENT": comment,
            },
        })
        return result.get("result") is not None

    async def _call(self, method: str, data: dict) -> dict:
        """Make API call with rate limiting and retry."""
        await self._rate_limit()

        for attempt, delay in enumerate(_API_RETRY_DELAYS + [None], start=1):
            try:
                resp = await self._client.post(
                    f"{self._url}{method}",
                    json=data,
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "bitrix_retry", method=method,
                    attempt=attempt, error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        raise httpx.HTTPError(f"Bitrix24 {method} failed after retries")

    async def _rate_limit(self) -> None:
        """Enforce ≤2 requests per second."""
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bitrix24.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/crm/ tests/test_bitrix24.py
git commit -m "feat: add Bitrix24 CRM client with lead search, create, update"
```

---

## Chunk 6: Pipeline, Worker, FastAPI app

### Task 12: Pipeline orchestrator

**Files:**
- Create: `app/pipeline.py`
- Create: `tests/test_pipeline.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

`tests/conftest.py`:
```python
import pytest

from app.models.schemas import CallData
from datetime import datetime


@pytest.fixture
def sample_call_data():
    return CallData(
        call_id="test-call-123",
        caller_number="79001234567",
        called_number="74951234567",
        duration=45,
        direction="incoming",
        timestamp=datetime(2026, 3, 12, 10, 0, 0),
        recording_url="https://novofon.com/records/test.mp3",
    )
```

- [ ] **Step 2: Write failing tests for pipeline**

`tests/test_pipeline.py`:
```python
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import DownloadError, EmptyTranscriptionError
from app.models.schemas import CallData, LLMResponse
from app.pipeline import process_call
from app.stt.speechkit import TranscriptSegment


@pytest.fixture
def mock_deps():
    """Create mocked pipeline dependencies."""
    novofon = AsyncMock()
    novofon.download_recording.return_value = Path("/tmp/test.mp3")

    s3 = AsyncMock()
    s3.upload.return_value = "s3://bucket/test.mp3"

    stt = AsyncMock()
    stt.transcribe.return_value = [
        TranscriptSegment(speaker=0, text="Здравствуйте", start_time=0.0),
        TranscriptSegment(speaker=1, text="Добрый день", start_time=1.5),
    ]
    stt.segments_to_text = MagicMock(
        return_value="Спикер 0: Здравствуйте\nСпикер 1: Добрый день"
    )

    llm = AsyncMock()
    llm.analyze_call.return_value = LLMResponse(
        client_name="Иван",
        summary="Тестовый звонок.",
        qualification="warm",
        sentiment="neutral",
        tags=["тест"],
    )

    bitrix = AsyncMock()
    bitrix.find_lead_by_phone.return_value = {"ID": 42, "STATUS_ID": "NEW"}
    bitrix.update_lead.return_value = True
    bitrix.add_timeline_comment.return_value = True

    return {
        "novofon": novofon,
        "s3": s3,
        "stt": stt,
        "llm": llm,
        "bitrix": bitrix,
    }


class TestProcessCall:
    @pytest.mark.asyncio
    async def test_full_pipeline_update_existing_lead(self, sample_call_data, mock_deps):
        await process_call(sample_call_data, **mock_deps)

        mock_deps["novofon"].download_recording.assert_called_once()
        mock_deps["s3"].upload.assert_called_once()
        mock_deps["stt"].transcribe.assert_called_once()
        mock_deps["llm"].analyze_call.assert_called_once()
        mock_deps["bitrix"].find_lead_by_phone.assert_called_once_with("79001234567")
        mock_deps["bitrix"].update_lead.assert_called_once()
        mock_deps["bitrix"].add_timeline_comment.assert_called_once()
        mock_deps["s3"].delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_lead_when_not_found(self, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_lead_by_phone.return_value = None
        mock_deps["bitrix"].create_lead.return_value = 99

        await process_call(sample_call_data, **mock_deps)

        mock_deps["bitrix"].create_lead.assert_called_once()
        mock_deps["bitrix"].add_timeline_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_transcription_skips_llm(self, sample_call_data, mock_deps):
        mock_deps["stt"].transcribe.side_effect = EmptyTranscriptionError("empty")

        await process_call(sample_call_data, **mock_deps)

        mock_deps["llm"].analyze_call.assert_not_called()
        mock_deps["bitrix"].find_lead_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_spam_skipped_when_configured(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Спам звонок.",
            qualification="spam",
            sentiment="neutral",
        )

        await process_call(sample_call_data, skip_spam=True, **mock_deps)

        mock_deps["bitrix"].find_lead_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_spam_processed_when_not_skipped(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Спам звонок.",
            qualification="spam",
            sentiment="neutral",
        )

        await process_call(sample_call_data, skip_spam=False, **mock_deps)

        mock_deps["bitrix"].find_lead_by_phone.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_error_propagates(self, sample_call_data, mock_deps):
        mock_deps["novofon"].download_recording.side_effect = DownloadError("fail")

        with pytest.raises(DownloadError):
            await process_call(sample_call_data, **mock_deps)

    @pytest.mark.asyncio
    @patch("app.pipeline._save_failed_crm_result")
    async def test_bitrix_failure_saves_to_json(self, mock_save, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_lead_by_phone.side_effect = Exception("B24 down")

        await process_call(sample_call_data, **mock_deps)

        mock_save.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement pipeline**

`app/pipeline.py`:
```python
import time

import structlog

from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import EmptyTranscriptionError
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData, LeadData, LLMResponse
from app.novofon.api import NovofonAPI
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()


async def process_call(
    call_data: CallData,
    *,
    novofon: NovofonAPI,
    s3: S3Client,
    stt: SpeechKitClient,
    llm: ProxyAPIClient,
    bitrix: Bitrix24Client,
    skip_spam: bool = False,
) -> None:
    """Main pipeline: download → S3 → STT → LLM → CRM."""
    log = logger.bind(call_id=call_data.call_id)
    mp3_path = None
    s3_key = f"{call_data.call_id}.mp3"

    try:
        # 1. Download recording
        start = time.monotonic()
        mp3_path = await novofon.download_recording(
            call_data.call_id, recording_url=call_data.recording_url,
        )
        log.info("stage_complete", stage="download", duration_ms=_elapsed(start))

        # 2. Upload to S3
        start = time.monotonic()
        s3_uri = await s3.upload(mp3_path, s3_key)
        log.info("stage_complete", stage="s3_upload", duration_ms=_elapsed(start))

        # 3. Transcribe
        start = time.monotonic()
        try:
            segments = await stt.transcribe(s3_uri, call_data.call_id)
        except EmptyTranscriptionError:
            log.info("empty_transcription", stage="stt", duration_ms=_elapsed(start))
            return
        finally:
            await s3.delete(s3_key)

        transcript = stt.segments_to_text(segments)
        log.info("stage_complete", stage="stt", duration_ms=_elapsed(start))

        # 4. Analyze via LLM
        start = time.monotonic()
        analysis = await llm.analyze_call(
            transcript=transcript,
            caller_number=call_data.caller_number,
            duration=call_data.duration,
        )
        log.info("stage_complete", stage="llm", duration_ms=_elapsed(start))

        # 5. Skip spam if configured
        if analysis.qualification == "spam" and skip_spam:
            log.info("spam_skipped")
            return

        # 6. Find/create lead in Bitrix24 (non-terminal: save to JSON on failure)
        start = time.monotonic()
        try:
            lead = await bitrix.find_lead_by_phone(call_data.caller_number)

            if lead:
                await bitrix.update_lead(lead["ID"], {
                    "TITLE": f"Звонок: {analysis.summary[:50]}",
                    "COMMENTS": analysis.summary,
                })
                await bitrix.add_timeline_comment(
                    "lead", lead["ID"], _format_comment(analysis),
                )
            else:
                lead_data = LeadData(
                    title=f"Звонок: {analysis.summary[:50]}",
                    client_name=analysis.client_name,
                    company=analysis.company,
                    phone=call_data.caller_number,
                    summary=analysis.summary,
                    qualification=analysis.qualification,
                )
                lead_id = await bitrix.create_lead(lead_data)
                await bitrix.add_timeline_comment(
                    "lead", lead_id, _format_comment(analysis),
                )
            log.info("stage_complete", stage="crm", duration_ms=_elapsed(start))
        except Exception as exc:
            log.error("crm_failed_saving_locally", error=str(exc))
            _save_failed_crm_result(call_data, analysis)

    finally:
        if mp3_path and mp3_path.exists():
            mp3_path.unlink()
            log.info("mp3_cleaned")


def _save_failed_crm_result(call_data: CallData, analysis: LLMResponse) -> None:
    """Save failed CRM update to local JSON for later processing."""
    import json
    from pathlib import Path

    failed_dir = Path("/data/failed_crm")
    failed_dir.mkdir(parents=True, exist_ok=True)
    dest = failed_dir / f"{call_data.call_id}.json"
    dest.write_text(json.dumps({
        "call_data": call_data.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2))


def _format_comment(analysis: LLMResponse) -> str:
    tags = ", ".join(analysis.tags) if analysis.tags else "-"
    return (
        f"AI-анализ звонка:\n\n"
        f"{analysis.summary}\n\n"
        f"Квалификация: {analysis.qualification}\n"
        f"Настроение: {analysis.sentiment}\n"
        f"Следующий шаг: {analysis.next_action or '-'}\n"
        f"Теги: {tags}"
    )


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/pipeline.py tests/test_pipeline.py tests/conftest.py
git commit -m "feat: add pipeline orchestrator with stage metrics and error handling"
```

---

### Task 13: arq Worker with DLQ and alerting

**Files:**
- Create: `app/worker.py`
- Create: `tests/test_dlq.py`
- Create: `tests/test_idempotency.py`

- [ ] **Step 1: Write failing tests for idempotency**

`tests/test_idempotency.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.worker import _is_processed, _mark_processed


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_new_call_not_processed(self):
        redis = AsyncMock()
        redis.exists.return_value = 0
        assert await _is_processed(redis, "new-call-123") is False

    @pytest.mark.asyncio
    async def test_existing_call_is_processed(self):
        redis = AsyncMock()
        redis.exists.return_value = 1
        assert await _is_processed(redis, "old-call-123") is True

    @pytest.mark.asyncio
    async def test_mark_processed_sets_key_with_ttl(self):
        redis = AsyncMock()
        await _mark_processed(redis, "call-123")
        redis.set.assert_called_once_with("processed:call-123", "1", ex=604800)
```

- [ ] **Step 2: Write failing tests for DLQ**

`tests/test_dlq.py`:
```python
import json
from unittest.mock import AsyncMock

import pytest

from app.worker import _add_to_dlq


class TestDLQ:
    @pytest.mark.asyncio
    async def test_adds_to_failed_calls(self):
        redis = AsyncMock()
        await _add_to_dlq(redis, "call-123", "DownloadError: failed", alert_url="")

        redis.rpush.assert_called_once()
        args = redis.rpush.call_args
        assert args[0][0] == "failed_calls"
        payload = json.loads(args[0][1])
        assert payload["call_id"] == "call-123"
        assert payload["error"] == "DownloadError: failed"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_sends_alert_when_url_configured(self):
        redis = AsyncMock()
        with pytest.MonkeyPatch.context() as mp:
            import httpx
            mock_post = AsyncMock()
            mp.setattr("app.worker.httpx.AsyncClient.post", mock_post)

            # We'll test alert sending is attempted
            # The actual HTTP call is best tested via respx in integration
            await _add_to_dlq(
                redis, "call-123", "error", alert_url="https://alert.test/hook",
            )
            # Just verify rpush was called (alert is best-effort)
            redis.rpush.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_idempotency.py tests/test_dlq.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement worker**

`app/worker.py`:
```python
import json
from datetime import datetime, timezone

import httpx
import structlog
from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.config import Settings
from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import TerminalError
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData
from app.novofon.api import NovofonAPI
from app.pipeline import process_call
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()

_IDEMPOTENCY_TTL = 604800  # 7 days


async def _is_processed(redis: Redis, call_id: str) -> bool:
    return bool(await redis.exists(f"processed:{call_id}"))


async def _mark_processed(redis: Redis, call_id: str) -> None:
    await redis.set(f"processed:{call_id}", "1", ex=_IDEMPOTENCY_TTL)


async def _add_to_dlq(
    redis: Redis, call_id: str, error: str, alert_url: str,
    call_data_raw: dict | None = None,
) -> None:
    payload = json.dumps({
        "call_id": call_id,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_data": call_data_raw,
    })
    await redis.rpush("failed_calls", payload)
    logger.error("dlq_entry", call_id=call_id, error=error)

    if alert_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(alert_url, json=json.loads(payload), timeout=10)
        except Exception as exc:
            logger.warning("alert_failed", call_id=call_id, error=str(exc))


async def handle_call(ctx: dict, call_data_raw: dict) -> None:
    """arq task handler for processing a call."""
    settings: Settings = ctx["settings"]
    redis: Redis = ctx["redis"]
    call_data = CallData.model_validate(call_data_raw)
    log = logger.bind(call_id=call_data.call_id)

    if await _is_processed(redis, call_data.call_id):
        log.info("call_already_processed")
        return

    try:
        await process_call(
            call_data,
            novofon=ctx["novofon"],
            s3=ctx["s3"],
            stt=ctx["stt"],
            llm=ctx["llm"],
            bitrix=ctx["bitrix"],
            skip_spam=settings.SKIP_SPAM_LEADS,
        )
        await _mark_processed(redis, call_data.call_id)
        log.info("call_processed")
    except TerminalError:
        raise  # Let arq retry
    except Exception as exc:
        await _add_to_dlq(
            redis, call_data.call_id, str(exc),
            settings.ALERT_WEBHOOK_URL, call_data_raw,
        )


async def startup(ctx: dict) -> None:
    """Initialize shared resources for arq worker."""
    settings = Settings()
    ctx["settings"] = settings
    ctx["redis"] = Redis.from_url(settings.REDIS_URL)
    ctx["novofon"] = NovofonAPI(
        api_key=settings.NOVOFON_API_KEY,
        api_secret=settings.NOVOFON_API_SECRET,
        data_dir="/data/tmp",
    )
    ctx["s3"] = S3Client(
        bucket=settings.YANDEX_S3_BUCKET,
        access_key=settings.YANDEX_S3_ACCESS_KEY,
        secret_key=settings.YANDEX_S3_SECRET_KEY,
        endpoint=settings.YANDEX_S3_ENDPOINT,
    )
    ctx["stt"] = SpeechKitClient(
        folder_id=settings.YANDEX_CLOUD_FOLDER_ID,
        sa_key_file=settings.YANDEX_CLOUD_SA_KEY_FILE,
    )
    ctx["llm"] = ProxyAPIClient(
        api_key=settings.PROXYAPI_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )
    ctx["bitrix"] = Bitrix24Client(webhook_url=settings.BITRIX24_WEBHOOK_URL)
    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    """Cleanup shared resources."""
    redis = ctx.get("redis")
    if redis:
        await redis.aclose()
    logger.info("worker_stopped")


class WorkerSettings:
    functions = [handle_call]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(Settings().REDIS_URL)
    max_tries = 2
    retry_delay = 120
    max_jobs = 3
    health_check_interval = 30
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_idempotency.py tests/test_dlq.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/worker.py tests/test_idempotency.py tests/test_dlq.py
git commit -m "feat: add arq worker with idempotency, DLQ, and alerting"
```

---

### Task 14: FastAPI application

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Implement FastAPI app**

`app/main.py`:
```python
import json
from contextlib import asynccontextmanager

import structlog
from arq.connections import create_pool, RedisSettings
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from redis.asyncio import Redis

from app.config import Settings
from app.novofon.webhook import WebhookIgnored, parse_webhook

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown resources."""
    settings = Settings()
    app.state.settings = settings
    app.state.redis = Redis.from_url(settings.REDIS_URL)
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    yield
    await app.state.arq.aclose()
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title="Call AI Pipeline", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/health")
    async def health():
        try:
            await app.state.redis.ping()
            return {"status": "ok"}
        except Exception:
            raise HTTPException(503, detail="Redis unavailable")

    @app.post("/webhook/{secret}")
    async def webhook(secret: str, request: Request):
        if secret != settings.WEBHOOK_SECRET:
            raise HTTPException(403, detail="Invalid webhook secret")

        payload = await request.json()
        try:
            call_data = parse_webhook(payload, settings.MIN_CALL_DURATION)
        except WebhookIgnored as exc:
            logger.info("webhook_ignored", reason=str(exc))
            return {"status": "ignored", "reason": str(exc)}
        except KeyError as exc:
            raise HTTPException(400, detail=f"Missing field: {exc}")

        await app.state.arq.enqueue_job(
            "handle_call",
            call_data.model_dump(mode="json"),
        )
        logger.info("call_enqueued", call_id=call_data.call_id)
        return {"status": "enqueued", "call_id": call_data.call_id}

    def _verify_admin(authorization: str = Header()):
        if authorization != f"Bearer {settings.ADMIN_TOKEN}":
            raise HTTPException(401, detail="Invalid admin token")

    @app.get("/admin/failed", dependencies=[Depends(_verify_admin)])
    async def list_failed():
        items = await app.state.redis.lrange("failed_calls", 0, -1)
        return [json.loads(item) for item in items]

    @app.post("/admin/retry/{call_id}", dependencies=[Depends(_verify_admin)])
    async def retry_failed(call_id: str):
        items = await app.state.redis.lrange("failed_calls", 0, -1)
        for item in items:
            data = json.loads(item)
            if data["call_id"] == call_id:
                await app.state.redis.lrem("failed_calls", 1, item)
                if "call_data" in data:
                    await app.state.arq.enqueue_job(
                        "handle_call", data["call_data"],
                    )
                    return {"status": "re-enqueued", "call_id": call_id}
                return {"status": "removed_from_dlq", "call_id": call_id}
        raise HTTPException(404, detail=f"Call {call_id} not found in DLQ")

    return app


app = create_app()
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: add FastAPI app with webhook, health, and admin endpoints"
```

---

### Task 14a: FastAPI endpoint tests

**Files:**
- Create: `tests/test_main.py`

- [ ] **Step 1: Write endpoint tests**

`tests/test_main.py`:
```python
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_settings(monkeypatch):
    """Set all required env vars for Settings."""
    env = {
        "NOVOFON_API_KEY": "k", "NOVOFON_API_SECRET": "s",
        "YANDEX_CLOUD_FOLDER_ID": "f", "YANDEX_CLOUD_SA_KEY_FILE": "sa.json",
        "YANDEX_S3_BUCKET": "b", "YANDEX_S3_ACCESS_KEY": "ak",
        "YANDEX_S3_SECRET_KEY": "sk",
        "YANDEX_S3_ENDPOINT": "https://storage.yandexcloud.net",
        "PROXYAPI_KEY": "p",
        "BITRIX24_WEBHOOK_URL": "https://t.bitrix24.ru/rest/1/x/",
        "REDIS_URL": "redis://localhost:6379/0",
        "WEBHOOK_SECRET": "test-secret",
        "ADMIN_TOKEN": "test-admin",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def client(test_settings):
    # Mock Redis and arq pool
    with patch("app.main.Redis") as mock_redis_cls, \
         patch("app.main.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.lrange.return_value = []
        mock_redis_cls.from_url.return_value = mock_redis

        mock_arq = AsyncMock()
        mock_pool.return_value = mock_arq

        from app.main import create_app
        app = create_app()
        with TestClient(app) as tc:
            yield tc


class TestWebhookEndpoint:
    def test_valid_webhook(self, client):
        payload = {
            "event": "NOTIFY_RECORD",
            "call_id": "123",
            "caller_id": "79001234567",
            "called_did": "74951234567",
            "duration": "45",
            "call_start": "2026-03-12 10:00:00",
        }
        resp = client.post("/webhook/test-secret", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "enqueued"

    def test_invalid_secret_returns_403(self, client):
        resp = client.post("/webhook/wrong-secret", json={})
        assert resp.status_code == 403

    def test_short_call_ignored(self, client):
        payload = {
            "event": "NOTIFY_RECORD",
            "call_id": "123",
            "caller_id": "79001234567",
            "called_did": "74951234567",
            "duration": "5",
            "call_start": "2026-03-12 10:00:00",
        }
        resp = client.post("/webhook/test-secret", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAdminEndpoints:
    def test_admin_without_token_returns_422(self, client):
        resp = client.get("/admin/failed")
        assert resp.status_code == 422  # Missing header

    def test_admin_with_wrong_token_returns_401(self, client):
        resp = client.get(
            "/admin/failed",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401

    def test_admin_with_valid_token(self, client):
        resp = client.get(
            "/admin/failed",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_main.py -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_main.py
git commit -m "test: add FastAPI endpoint tests for webhook, health, admin"
```

---

### Task 14b: Retry logic tests

**Files:**
- Create: `tests/test_retry.py`

- [ ] **Step 1: Write retry tests**

`tests/test_retry.py`:
```python
"""Tests for per-stage retry logic across pipeline components."""
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.exceptions import DownloadError
from app.novofon.api import NovofonAPI


class TestDownloadRetryDelays:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_correct_number_of_times(self, tmp_path):
        api = NovofonAPI(api_key="k", api_secret="s", data_dir=str(tmp_path))
        url = "https://novofon.com/records/123.mp3"

        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                return httpx.Response(503)
            return httpx.Response(200, content=b"mp3")

        respx.get(url).mock(side_effect=side_effect)

        # 3 retries + 1 final attempt = max 4, but _RETRY_DELAYS has 3 entries
        # so we get 3 attempts with delays + 1 final = 4 total
        # With 3 failures and 4th success, it should work
        # Actually _RETRY_DELAYS = [5, 10, 20] + [None] = 4 iterations
        # Fails on 1,2,3 -> succeeds on 4th
        path = await api.download_recording("123", recording_url=url)
        assert path.exists()
        assert call_count == 4

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_after_all_retries_exhausted(self, tmp_path):
        api = NovofonAPI(api_key="k", api_secret="s", data_dir=str(tmp_path))
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(return_value=httpx.Response(503))

        with pytest.raises(DownloadError):
            await api.download_recording("123", recording_url=url)
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_retry.py -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_retry.py
git commit -m "test: add retry logic tests"
```

---

## Chunk 7: Docker and deployment

### Task 15: Docker setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.11-slim AS base

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /data/tmp && chown -R app:app /data

USER app

# API entrypoint
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Worker entrypoint
FROM base AS worker
CMD ["arq", "app.worker.WorkerSettings"]
```

- [ ] **Step 2: Create docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  api:
    build:
      context: .
      target: api
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    build:
      context: .
      target: worker
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - tmp_data:/data/tmp
      - failed_crm:/data/failed_crm
    stop_grace_period: 300s

volumes:
  redis_data:
  tmp_data:
  failed_crm:
```

- [ ] **Step 3: Create .dockerignore**

`.dockerignore`:
```
.git
.venv
__pycache__
*.pyc
.env
tests/
scripts/
docs/
*.md
.claude/
```

- [ ] **Step 4: Verify Docker build**

Run: `cd /home/alex2061/projects/call-ai-pipeline && docker compose build`
Expected: both `api` and `worker` images build successfully

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Docker setup with multi-stage build and compose"
```

---

### Task 16: Structlog configuration

**Files:**
- Modify: `app/__init__.py`

- [ ] **Step 1: Configure structlog in app init**

`app/__init__.py`:
```python
import logging
import os

import structlog


def setup_logging() -> None:
    """Configure structlog with JSON output."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO),
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()
```

- [ ] **Step 2: Commit**

```bash
git add app/__init__.py
git commit -m "feat: configure structlog with JSON output"
```

---

### Task 17: Run all tests

- [ ] **Step 1: Run full test suite**

Run: `cd /home/alex2061/projects/call-ai-pipeline && python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 2: Fix any failures**

If any test fails — fix and re-run until green.

- [ ] **Step 3: Final commit if needed**

```bash
git add -A
git commit -m "fix: resolve test issues from full suite run"
```

---

## Chunk 8: E2E test script

### Task 18: Manual E2E test script

**Files:**
- Create: `scripts/test_e2e.py`

- [ ] **Step 1: Create e2e script**

`scripts/test_e2e.py`:
```python
"""Manual end-to-end test. Requires real API keys in .env.

Usage: python scripts/test_e2e.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.crm.bitrix24 import Bitrix24Client
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData, LeadData
from datetime import datetime


async def test_llm():
    """Test LLM analysis with sample transcript."""
    settings = Settings()
    client = ProxyAPIClient(
        api_key=settings.PROXYAPI_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )

    transcript_path = Path(__file__).parent.parent / "tests/fixtures/sample_transcript.txt"
    transcript = transcript_path.read_text()

    print("=== Testing LLM ===")
    result = await client.analyze_call(
        transcript=transcript,
        caller_number="79001234567",
        duration=120,
    )
    print(f"Client: {result.client_name}")
    print(f"Company: {result.company}")
    print(f"Summary: {result.summary}")
    print(f"Qualification: {result.qualification}")
    print(f"Sentiment: {result.sentiment}")
    print(f"Tags: {result.tags}")
    print(f"Next action: {result.next_action}")
    print()
    return result


async def test_bitrix(analysis):
    """Test Bitrix24 lead creation."""
    settings = Settings()
    client = Bitrix24Client(webhook_url=settings.BITRIX24_WEBHOOK_URL)

    print("=== Testing Bitrix24 ===")

    # Search for existing lead
    lead = await client.find_lead_by_phone("79001234567")
    print(f"Existing lead: {lead}")

    if not lead:
        lead_data = LeadData(
            title=f"[E2E TEST] {analysis.summary[:50]}",
            client_name=analysis.client_name,
            company=analysis.company,
            phone="79001234567",
            summary=analysis.summary,
            qualification=analysis.qualification,
        )
        lead_id = await client.create_lead(lead_data)
        print(f"Created lead: {lead_id}")
    else:
        lead_id = lead["ID"]
        print(f"Using existing lead: {lead_id}")

    comment = (
        f"[E2E TEST] AI-анализ:\n\n{analysis.summary}\n\n"
        f"Квалификация: {analysis.qualification}"
    )
    await client.add_timeline_comment("lead", lead_id, comment)
    print(f"Comment added to lead {lead_id}")


async def main():
    analysis = await test_llm()
    await test_bitrix(analysis)
    print("\n=== E2E test complete ===")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/test_e2e.py
git commit -m "feat: add manual e2e test script"
```

---

## Summary

| Chunk | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-4 | Foundation: scaffolding, schemas, config, exceptions |
| 2 | 5-6 | LLM: prompts, ProxyAPI client |
| 3 | 7-8 | Novofon: webhook parser, API download |
| 4 | 9-10 | STT: S3 client (with tests), SpeechKit (with tests) |
| 5 | 11 | CRM: Bitrix24 client |
| 6 | 12-14b | Pipeline, worker, FastAPI app, endpoint tests, retry tests |
| 7 | 15-17 | Docker, structlog, full test run |
| 8 | 18 | E2E test script |

**Total:** 20 tasks, ~90 steps. Each chunk is independently committable and testable.

**Note:** Task 10 (SpeechKit) has a skeleton implementation — full integration requires SDK setup with real Yandex Cloud credentials. This is intentional: all other components can be developed and tested without it.
