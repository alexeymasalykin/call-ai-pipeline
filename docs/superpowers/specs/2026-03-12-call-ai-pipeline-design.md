# Call AI Pipeline — Design Spec

## Overview

Automated call processing pipeline:
Novofon (PBX) → transcription (Yandex SpeechKit) → AI analysis (GPT-4o-mini via ProxyAPI) → lead enrichment in Bitrix24.

The system enriches leads already created by Novofon's native Bitrix24 integration (not creates new ones, unless fallback).

## Architecture

### Services (docker-compose)

| Service | Role | Entrypoint |
|---------|------|------------|
| **api** | FastAPI, accepts Novofon webhooks, enqueues tasks | `uvicorn app.main:app` |
| **worker** | arq worker, processes pipeline tasks | `arq app.worker.WorkerSettings` |
| **redis** | Task broker + idempotency store + IAM token cache | `redis:alpine` |

### Data Flow

```
Novofon webhook POST → api (validate, filter <15s, idempotency check)
    → Redis queue (arq)
        → worker picks up task:
            1. Download mp3 (Novofon API, httpx)
            2. Transcribe (Yandex SpeechKit SDK, async recognition)
            3. Analyze (OpenAI SDK → ProxyAPI, GPT-4o-mini)
            4. Find lead in Bitrix24 by phone number (httpx)
            5. Update lead + add timeline comment (or create if not found)
            6. Cleanup mp3
```

### Two Parallel Data Streams

```
Stream 1 (native integration, instant):
  Call → Novofon ↔ B24 app → lead created, recording attached

Stream 2 (AI pipeline, 1-3 min after call):
  Call ended → webhook → STT → LLM →
  → find lead by phone → add summary, qualification, tags
```

## Tech Stack (fixed decisions)

- **PBX:** Novofon (ex-Zadarma)
- **CRM:** Bitrix24 Cloud (REST API)
- **STT:** Yandex SpeechKit SDK (async recognition, diarization, 0.6 rub/min)
- **LLM:** GPT-4o-mini via ProxyAPI (https://api.proxyapi.ru/openai/v1)
- **Queue:** arq (async task queue on Redis)
- **Framework:** Python 3.11+ / FastAPI / httpx
- **Deploy:** Docker Compose on VPS (Ubuntu)

## Project Structure

```
call-ai-pipeline/
├── .env
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, webhook endpoint, /health
│   ├── config.py             # Pydantic Settings from .env
│   ├── worker.py             # arq worker settings + task definitions
│   ├── pipeline.py           # Orchestrator: STT → LLM → CRM
│   │
│   ├── novofon/
│   │   ├── __init__.py
│   │   ├── webhook.py        # Parse incoming Novofon webhooks
│   │   └── api.py            # Download recordings via Novofon API (httpx)
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   └── speechkit.py      # Yandex SpeechKit SDK async recognition
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract LLM interface
│   │   ├── proxyapi_client.py  # ProxyAPI client (OpenAI SDK, custom base_url)
│   │   └── prompts.py        # System prompt + user prompt template
│   │
│   ├── crm/
│   │   ├── __init__.py
│   │   └── bitrix24.py       # Bitrix24 REST API: leads, timeline
│   │
│   └── models/
│       ├── __init__.py
│       └── schemas.py        # Pydantic models: CallData, LeadData, LLMResponse
│
├── scripts/
│   └── test_e2e.py           # Manual e2e test with real API keys
│
└── tests/
    ├── test_config.py
    ├── test_schemas.py
    ├── test_prompts.py
    ├── test_webhook.py
    ├── test_llm_response.py
    ├── test_bitrix24.py
    ├── test_idempotency.py
    ├── test_dlq.py
    ├── test_retry.py
    ├── test_pipeline.py
    └── fixtures/
        ├── sample_transcript.txt
        ├── sample_webhook.json
        └── sample_llm_response.json
```

## Components

### 1. Novofon Webhook (`app/novofon/webhook.py`)

- Accepts POST from Novofon
- **Event handling strategy:** enqueue task only on `NOTIFY_RECORD` event (recording is ready). Ignore `NOTIFY_END` — it arrives before recording is available. Idempotency by `call_id` protects against duplicate webhooks.
- Extracts: `call_id`, `caller_number`, `called_number`, `duration`, `direction`, `recording_url` (if present in payload)
- Filters: skip calls shorter than `MIN_CALL_DURATION` (default 15s)
- Webhook security: validate signature if supported by Novofon; fallback — secret token in URL path (`/webhook/{secret_token}`)
- Returns `CallData` to arq queue

### 2. Novofon API (`app/novofon/api.py`)

- Downloads mp3 recording via httpx
- **Primary:** use `recording_url` from `NOTIFY_RECORD` webhook payload (direct link)
- **Fallback:** if URL missing, request via `GET /v1/pbx/record/request/` with `call_id` and `lifetime`
- Retry: 3 attempts with backoff (5, 10, 20s) — since we trigger on `NOTIFY_RECORD`, recording should be ready
- Saves to docker volume `/data/tmp/{call_id}.mp3` (not /tmp — avoids tmpfs RAM issues)

### 3. SpeechKit STT (`app/stt/speechkit.py`)

- Uses `yandexcloud` SDK for async recognition
- **Audio upload flow:**
  1. Upload mp3 to Yandex Object Storage (S3-compatible) bucket `call-ai-pipeline-audio`
  2. Pass `s3://call-ai-pipeline-audio/{call_id}.mp3` URI to recognition request
  3. After transcription completes — delete file from Object Storage
  4. Requires: `YANDEX_S3_BUCKET`, `YANDEX_S3_ACCESS_KEY`, `YANDEX_S3_SECRET_KEY` in config
- Config: `ru-RU`, `general:rc` model, MP3, 8000Hz, mono
- `literature_text=True` (text normalization), `profanity_filter=False`
- IAM token: managed by SDK automatically (service account)
- Polling: every 3s, timeout 5 min
- Returns: `list[{speaker: int, text: str, start_time: float}]`
- If diarization unavailable — returns single text block
- **Empty transcription handling:** if result is empty or contains only silence markers — skip LLM stage, log as `empty_transcription`, do not update lead

### 4. LLM Client (`app/llm/proxyapi_client.py`)

- OpenAI SDK with `base_url="https://api.proxyapi.ru/openai/v1"`
- Model: configurable via `LLM_MODEL` env var (default `gpt-4o-mini`)
- `temperature=0.1`, `max_tokens=1000` (REQUIRED for ProxyAPI — otherwise reserves full context cost)
- `response_format={"type": "json_object"}` — forces structured JSON output, reduces parse errors
- Parses JSON response → validates via `LLMResponse` Pydantic model
- On invalid JSON: 1 retry with same prompt
- On second failure: fallback with `summary="Ошибка анализа"`

### 5. LLM Prompts (`app/llm/prompts.py`)

- `SYSTEM_PROMPT`: role, rules, output format
- `USER_PROMPT_TEMPLATE`: transcript + metadata → expected JSON schema
- `PROMPT_VERSION = "1.0"` — logged with each LLM call for traceability
- `build_user_prompt(transcript, caller_number, duration) -> str`

### 6. Bitrix24 CRM (`app/crm/bitrix24.py`)

- httpx client with incoming webhook auth (`https://{domain}.bitrix24.ru/rest/{user_id}/{token}/`)
- Rate limiting: ≤2 requests/second (B24 cloud limit)
- Key methods:
  - `find_lead_by_phone(phone)` — search via `crm.lead.list` with phone filter. Returns last open lead (STATUS_ID != CONVERTED, != JUNK). If not found — retry 3 times with 10s delay (lead may not have been created yet by native integration). After 3 retries — fallback to `create_lead()`.
  - `create_lead(data)` — fallback only. Returns `lead_id`.
  - `update_lead(lead_id, data)` — enrich with AI analysis results.
  - `add_timeline_comment(entity_type, entity_id, comment)` — add AI summary to lead timeline.

### 7. Pipeline (`app/pipeline.py`)

- Orchestrator: download → S3 upload → transcribe → S3 cleanup → analyze → find/update lead → local cleanup
- Each stage wrapped with retry logic and `call_id` context logging
- Stage duration metrics logged (`duration_ms` per stage)
- **SKIP_SPAM_LEADS logic:** if `qualification == "spam"` and `SKIP_SPAM_LEADS=true` — skip B24 update entirely, just log and mark as processed
- **Empty transcription:** if STT returns empty text — skip LLM and B24 stages, log `empty_transcription`
- mp3 cleanup in `finally` block (even on error); S3 object cleanup after transcription

### 8. Worker (`app/worker.py`)

- arq WorkerSettings with `max_tries=2`, `retry_delay=120`, `max_jobs=3` (limit concurrency to avoid rate limits on ProxyAPI/B24)
- Graceful shutdown: `health_check_interval` + `stop_timeout` in docker-compose
- DLQ: tasks that exhaust all retries go to `failed_calls` Redis list
- Alert: on DLQ entry, POST to `ALERT_WEBHOOK_URL` (configurable)

## Pydantic Models

```python
class CallData(BaseModel):
    call_id: str
    caller_number: str
    called_number: str
    duration: int              # seconds
    direction: Literal["incoming", "outgoing"]
    timestamp: datetime

class LLMResponse(BaseModel):
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
    title: str
    client_name: Optional[str] = None
    company: Optional[str] = None
    phone: str
    summary: str
    qualification: str
    source: str = "CALL"
```

## Reliability

### Idempotency

Before processing, check Redis key `processed:{call_id}`. If exists — skip. Each key has TTL 7 days (individual keys, not a single SET — avoids unbounded memory growth).

### Retry Strategy (two levels)

**Level 1: Per-stage retry (inside pipeline).** Handles transient errors (network, 429, 503):

| Stage | Retries | Backoff | On exhaustion |
|-------|---------|---------|---------------|
| Download mp3 | 3 | 5, 10, 20s | Raise `DownloadError` (terminal) |
| S3 upload | 2 | 5, 10s | Raise `UploadError` (terminal) |
| SpeechKit | 3 | 10, 20, 40s | Raise `TranscriptionError` (terminal) |
| LLM (ProxyAPI) | 2 | 5, 10s | Fallback: create lead with "requires manual analysis" (non-terminal) |
| Bitrix24 | 3 | 5, 10, 20s | Save result to local JSON file (non-terminal) |

**Level 2: arq job retry.** If pipeline raises a terminal error, arq retries the entire job (`max_tries=2`, delay 120s). This covers cases where stage-level retry exhausted but the issue was temporary (e.g., Novofon outage resolved after 2 min).

**Total worst case:** stage retries × arq retries. E.g., download: 3 × 2 = 6 attempts.

**Terminal vs non-terminal errors:**
- Terminal (retryable by arq): `DownloadError`, `UploadError`, `TranscriptionError`
- Non-terminal (handled within pipeline, no arq retry): LLM fallback, B24 save-to-JSON

### Dead Letter Queue (DLQ)

Tasks that exhaust all arq retries land in `failed_calls` Redis list. Contains: `call_id`, failure reason, timestamp, last error.

Admin endpoints (protected by `ADMIN_TOKEN` bearer auth):
- `GET /admin/failed` — list failed tasks
- `POST /admin/retry/{call_id}` — manual retry

### Alerting

On DLQ entry, POST to `ALERT_WEBHOOK_URL` with JSON payload: `{call_id, error, timestamp}`. Can be connected to Telegram bot or Bitrix24 chat.

### Graceful Shutdown

arq worker finishes current task before stopping on SIGTERM. Docker-compose `stop_grace_period: 300s` (5 min — max SpeechKit polling time).

### Stage Duration Metrics

Every pipeline stage logs `duration_ms`:
```json
{"call_id": "abc123", "stage": "stt", "status": "ok", "duration_ms": 45200}
```

## Logging

- **structlog** with JSON output
- Every log entry includes `call_id` as context
- Full transcript text is NEVER logged (PII/PD compliance)
- Only `call_id` + stage status
- Levels: INFO for success, ERROR with full traceback on failure

## Webhook Security

- Validate Novofon signature if supported
- Fallback: secret token in webhook URL path (`/webhook/{secret_token}`)
- Secret token configured via `WEBHOOK_SECRET` in `.env`

## Health Check

- `GET /health` — checks Redis connectivity
- Docker healthcheck for auto-restart

## Configuration (.env)

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
WEBHOOK_SECRET=
ALERT_WEBHOOK_URL=
ADMIN_TOKEN=
LOG_LEVEL=INFO
```

## Testing

### Unit Tests
- `test_config.py` — validation of .env, missing required vars → clear error
- `test_schemas.py` — Pydantic model validation: valid/invalid/edge cases
- `test_prompts.py` — `build_user_prompt()` generates correct text
- `test_webhook.py` — webhook payload parsing, short call filtering
- `test_llm_response.py` — JSON parsing from LLM, fallback on invalid JSON
- `test_bitrix24.py` — lead search logic, update vs create decision
- `test_idempotency.py` — duplicate `call_id` skipped
- `test_dlq.py` — exhausted retries → DLQ, alert webhook called
- `test_retry.py` — retry logic with correct delays

### Integration Test
- `test_pipeline.py` — full pipeline on fixtures, external services mocked via `respx` (httpx) and `unittest.mock` (SDK)

### Fixtures
- `tests/fixtures/sample_transcript.txt`
- `tests/fixtures/sample_webhook.json`
- `tests/fixtures/sample_llm_response.json`

### Manual E2E
- `scripts/test_e2e.py` — real mp3 from Novofon → full pipeline → test lead in B24

## Dependencies

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
boto3>=1.34.0            # Yandex Object Storage (S3-compatible) upload
structlog>=24.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0
```
