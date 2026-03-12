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
