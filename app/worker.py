import json
from datetime import datetime, timezone

import httpx
import structlog
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.config import Settings
from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import PipelineError, RetryableError
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData
from app.novofon.api import NovofonAPI
from app.pipeline import process_call
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()

_IDEMPOTENCY_TTL = 604800  # 7 days — prevents duplicate processing if webhook resends


async def _is_processed(redis: Redis, call_id: str) -> bool:
    return bool(await redis.exists(f"processed:{call_id}"))


async def _mark_processed(redis: Redis, call_id: str) -> None:
    await redis.set(f"processed:{call_id}", "1", ex=_IDEMPOTENCY_TTL)


async def _add_to_dlq(
    redis: Redis, call_id: str, error: str, alert_url: str,
    call_data_raw: dict | None = None,
) -> None:
    entry = {
        "call_id": call_id,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_data": call_data_raw,
    }
    await redis.rpush("failed_calls", json.dumps(entry))
    logger.error("dlq_entry", call_id=call_id, error=error)

    if alert_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(alert_url, json=entry, timeout=10)
        except httpx.HTTPError as exc:
            logger.error("alert_failed", call_id=call_id, error=repr(exc))


def _novofon_direction(raw: str) -> str:
    """Convert Novofon direction ('in'/'out') to our format."""
    return "outgoing" if raw == "out" else "incoming"


def _build_call_data(call_info: dict) -> CallData:
    """Build CallData from Novofon API response."""
    direction = _novofon_direction(call_info.get("direction", "in"))
    if direction == "outgoing":
        caller_number = call_info["virtual_phone_number"]
        called_number = call_info["contact_phone_number"]
    else:
        caller_number = call_info["contact_phone_number"]
        called_number = call_info["virtual_phone_number"]

    start_time = call_info.get("start_time", "")
    try:
        timestamp = datetime.fromisoformat(start_time)
    except (ValueError, TypeError):
        timestamp = datetime.now(timezone.utc)

    # Build recording URL from call_records hash
    # Format: https://app.novofon.ru/system/media/talk/{call_id}/{record_hash}/
    call_id = str(call_info["id"])
    records = call_info.get("call_records") or []
    recording_url: str | None = None
    if records and isinstance(records[0], str):
        recording_url = f"https://app.novofon.ru/system/media/talk/{call_id}/{records[0]}/"

    return CallData(
        call_id=call_id,
        caller_number=caller_number,
        called_number=called_number,
        duration=int(call_info.get("talk_duration", 0)),
        direction=direction,
        timestamp=timestamp,
        recording_url=recording_url,
    )


async def handle_call(ctx: dict, pbx_call_id: str) -> None:
    """arq task handler: fetches call data from Novofon API, runs pipeline.

    RetryableError → re-raised for arq retry unless max_tries exhausted (then DLQ).
    Other PipelineError (LLMAnalysisError etc.) → DLQ immediately.
    Unexpected Exception → DLQ + re-raise so arq records the failure.
    """
    settings: Settings = ctx["settings"]
    redis: Redis = ctx["redis"]
    novofon: NovofonAPI = ctx["novofon"]
    log = logger.bind(call_id=pbx_call_id)

    if await _is_processed(redis, pbx_call_id):
        log.info("call_already_processed")
        return

    # Fetch full call data from Novofon API
    try:
        call_info = await novofon.get_call_info(pbx_call_id)
    except Exception as exc:
        log.error("novofon_fetch_failed", error=repr(exc))
        await _add_to_dlq(redis, pbx_call_id, f"Failed to fetch call info: {exc}", settings.ALERT_WEBHOOK_URL)
        return

    try:
        call_data = _build_call_data(call_info)
    except (KeyError, ValueError) as exc:
        await _add_to_dlq(
            redis, pbx_call_id, f"Invalid call data: {exc}",
            settings.ALERT_WEBHOOK_URL, call_info,
        )
        return

    log = log.bind(direction=call_data.direction, duration=call_data.duration)

    # Skip short calls
    if call_data.duration < settings.MIN_CALL_DURATION:
        log.info("call_too_short", min_duration=settings.MIN_CALL_DURATION)
        return

    job_try = ctx.get("job_try", 1)
    max_tries = WorkerSettings.max_tries

    try:
        await process_call(
            call_data,
            novofon=novofon,
            s3=ctx["s3"],
            stt=ctx["stt"],
            llm=ctx["llm"],
            bitrix=ctx["bitrix"],
            qa_entity_type_id=settings.BITRIX24_QA_ENTITY_TYPE_ID,
            qa_field_map=ctx["qa_field_map"],
        )
        await _mark_processed(redis, call_data.call_id)
        log.info("call_processed")
    except RetryableError as exc:
        if job_try >= max_tries:
            await _add_to_dlq(
                redis, call_data.call_id, str(exc),
                settings.ALERT_WEBHOOK_URL, call_info,
            )
        else:
            raise
    except PipelineError as exc:
        log.error("terminal_pipeline_error", error=repr(exc))
        await _add_to_dlq(
            redis, call_data.call_id, repr(exc),
            settings.ALERT_WEBHOOK_URL, call_info,
        )
    except Exception as exc:
        log.error("unexpected_error", error=repr(exc), exc_info=True)
        await _add_to_dlq(
            redis, call_data.call_id, repr(exc),
            settings.ALERT_WEBHOOK_URL, call_info,
        )
        raise


async def startup(ctx: dict) -> None:
    """Initialize shared resources for arq worker."""
    settings = Settings()
    ctx["settings"] = settings
    ctx["redis"] = Redis.from_url(settings.REDIS_URL)
    ctx["novofon"] = NovofonAPI(
        login=settings.NOVOFON_LOGIN,
        password=settings.NOVOFON_PASSWORD,
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
    ctx["qa_field_map"] = json.loads(settings.BITRIX24_QA_FIELD_MAP) if settings.BITRIX24_QA_FIELD_MAP else {}
    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    """Cleanup shared resources: close all clients, then Redis."""
    for name in ("bitrix", "llm", "novofon", "s3", "stt"):
        client = ctx.get(name)
        if client and hasattr(client, "close"):
            try:
                await client.close()
            except Exception as exc:
                logger.error("shutdown_close_failed", client=name, error=repr(exc))
    redis = ctx.get("redis")
    if redis:
        try:
            await redis.aclose()
        except Exception as exc:
            logger.error("shutdown_close_failed", client="redis", error=repr(exc))
    logger.info("worker_stopped")


class WorkerSettings:
    functions = [handle_call]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="redis", port=6379, database=0)
    max_tries = 2
    retry_delay = 120
    max_jobs = 3
    health_check_interval = 30
