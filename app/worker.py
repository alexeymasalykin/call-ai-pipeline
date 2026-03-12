import json
from datetime import datetime, timezone

import httpx
import structlog
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
    redis_settings = RedisSettings(host="redis", port=6379, database=0)
    max_tries = 2
    retry_delay = 120
    max_jobs = 3
    health_check_interval = 30
