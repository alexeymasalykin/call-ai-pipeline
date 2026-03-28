import hmac
import json
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

import structlog
from arq.connections import create_pool, RedisSettings
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import Settings
from app.novofon.webhook import WebhookIgnored, parse_webhook
from app.stats import get_range

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Settings, Redis, and arq pool; close on shutdown."""
    settings = Settings()
    app.state.settings = settings
    app.state.redis = Redis.from_url(settings.REDIS_URL)
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    yield
    await app.state.arq.aclose()
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Call AI Pipeline", docs_url=None, redoc_url=None, lifespan=lifespan)
    settings = Settings()
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] if settings.CORS_ORIGINS else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        try:
            await app.state.redis.ping()
            return {"status": "ok"}
        except RedisError:
            raise HTTPException(503, detail="Redis unavailable")

    @app.post("/webhook")
    async def webhook(request: Request, secret: str = ""):
        settings: Settings = app.state.settings
        if not secret or not hmac.compare_digest(secret, settings.WEBHOOK_SECRET):
            raise HTTPException(403, detail="Invalid webhook secret")

        content_type = request.headers.get("content-type", "")
        try:
            body = await request.body()
            logger.info("webhook_raw_body", content_type=content_type, body=body.decode(errors="replace")[:500])
            if "application/json" in content_type:
                payload = json.loads(body)
            else:
                # Parse URL-encoded form data from raw bytes
                parsed = parse_qs(body.decode(), keep_blank_values=True)
                payload = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        except Exception as exc:
            logger.error("webhook_parse_error", error=repr(exc), content_type=content_type)
            raise HTTPException(400, detail="Invalid request body")

        logger.info("webhook_received", payload=payload)

        try:
            pbx_call_id = parse_webhook(payload)
        except WebhookIgnored as exc:
            logger.info("webhook_ignored", reason=str(exc))
            return {"status": "ignored", "reason": str(exc)}
        except KeyError as exc:
            raise HTTPException(400, detail=f"Invalid payload: {exc}")

        try:
            await app.state.arq.enqueue_job(
                "handle_call",
                pbx_call_id,
            )
        except Exception as exc:
            logger.error("enqueue_failed", call_id=pbx_call_id, error=repr(exc))
            raise HTTPException(503, detail="Failed to enqueue call processing")

        logger.info("call_enqueued", call_id=pbx_call_id)
        return {"status": "enqueued", "call_id": pbx_call_id}

    @app.get("/api/stats")
    async def get_stats(days: int = 30):
        if days < 1 or days > 365:
            raise HTTPException(400, detail="days must be between 1 and 365")
        daily = await get_range(app.state.redis, days)
        totals: dict[str, int] = {}
        for day_stats in daily.values():
            for field, value in day_stats.items():
                totals[field] = totals.get(field, 0) + value
        return {"days": days, "daily": daily, "totals": totals}

    def _verify_admin(authorization: str = Header()):
        settings: Settings = app.state.settings
        if not hmac.compare_digest(authorization, f"Bearer {settings.ADMIN_TOKEN}"):
            raise HTTPException(401, detail="Invalid admin token")

    @app.get("/admin/failed", dependencies=[Depends(_verify_admin)])
    async def list_failed():
        items = await app.state.redis.lrange("failed_calls", 0, -1)
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                result.append({"raw": item.decode() if isinstance(item, bytes) else str(item), "parse_error": True})
        return result

    @app.post("/admin/retry/{call_id}", dependencies=[Depends(_verify_admin)])
    async def retry_failed(call_id: str):
        items = await app.state.redis.lrange("failed_calls", 0, -1)
        for item in items:
            try:
                data = json.loads(item)
            except json.JSONDecodeError:
                logger.warning("dlq_corrupt_entry", raw=item[:200])
                continue
            if data.get("call_id") == call_id:
                await app.state.redis.lrem("failed_calls", 1, item)
                try:
                    await app.state.arq.enqueue_job("handle_call", call_id)
                except Exception as exc:
                    logger.error("retry_enqueue_failed", call_id=call_id, error=repr(exc))
                    raise HTTPException(503, detail="Failed to re-enqueue call")
                return {"status": "re-enqueued", "call_id": call_id}
        raise HTTPException(404, detail=f"Call {call_id} not found in DLQ")

    return app


app = create_app()
