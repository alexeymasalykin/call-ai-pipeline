import hmac
import json
from contextlib import asynccontextmanager

import structlog
from arq.connections import create_pool, RedisSettings
from redis.exceptions import RedisError
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import ValidationError
from redis.asyncio import Redis

from app.config import Settings
from app.novofon.webhook import WebhookIgnored, parse_webhook

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
    app = FastAPI(title="Call AI Pipeline", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/health")
    async def health():
        try:
            await app.state.redis.ping()
            return {"status": "ok"}
        except RedisError:
            raise HTTPException(503, detail="Redis unavailable")

    @app.post("/webhook")
    async def webhook(request: Request, x_webhook_secret: str = Header()):
        settings: Settings = app.state.settings
        if not hmac.compare_digest(x_webhook_secret, settings.WEBHOOK_SECRET):
            raise HTTPException(403, detail="Invalid webhook secret")

        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON")

        try:
            call_data = parse_webhook(payload, settings.MIN_CALL_DURATION)
        except WebhookIgnored as exc:
            logger.info("webhook_ignored", reason=str(exc))
            return {"status": "ignored", "reason": str(exc)}
        except (KeyError, ValidationError) as exc:
            raise HTTPException(400, detail=f"Invalid payload: {exc}")

        try:
            await app.state.arq.enqueue_job(
                "handle_call",
                call_data.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.error("enqueue_failed", call_id=call_data.call_id, error=repr(exc))
            raise HTTPException(503, detail="Failed to enqueue call processing")

        logger.info("call_enqueued", call_id=call_data.call_id)
        return {"status": "enqueued", "call_id": call_data.call_id}

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
            except (json.JSONDecodeError, ValueError):
                result.append({"raw": item.decode() if isinstance(item, bytes) else str(item)})
        return result

    @app.post("/admin/retry/{call_id}", dependencies=[Depends(_verify_admin)])
    async def retry_failed(call_id: str):
        items = await app.state.redis.lrange("failed_calls", 0, -1)
        for item in items:
            try:
                data = json.loads(item)
            except (json.JSONDecodeError, ValueError):
                continue
            if data.get("call_id") == call_id:
                has_call_data = "call_data" in data
                if has_call_data:
                    try:
                        await app.state.arq.enqueue_job(
                            "handle_call", data["call_data"],
                        )
                    except Exception as exc:
                        logger.error("retry_enqueue_failed", call_id=call_id, error=repr(exc))
                        raise HTTPException(503, detail="Failed to re-enqueue call")
                await app.state.redis.lrem("failed_calls", 1, item)
                status = "re-enqueued" if has_call_data else "removed_from_dlq"
                return {"status": status, "call_id": call_id}
        raise HTTPException(404, detail=f"Call {call_id} not found in DLQ")

    return app


app = create_app()
