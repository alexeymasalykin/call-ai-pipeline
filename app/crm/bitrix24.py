import asyncio
from typing import Any, Optional
import httpx
import structlog
from app.models.schemas import LeadData

logger = structlog.get_logger()
_EXCLUDED_STATUSES = {"CONVERTED", "JUNK"}
_RATE_LIMIT_DELAY = 0.5
_FIND_RETRY_DELAY = 10
_FIND_MAX_RETRIES = 3
_API_RETRY_DELAYS = [5, 10, 20]


class Bitrix24Client:
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url.rstrip("/") + "/"
        self._client = httpx.AsyncClient(timeout=30)
        self._last_request_time: float = 0

    async def find_lead_by_phone(self, phone: str) -> Optional[dict]:
        for attempt in range(1, _FIND_MAX_RETRIES + 1):
            result = await self._call(
                "crm.lead.list",
                {"filter": {"PHONE": phone}, "select": ["ID", "STATUS_ID", "TITLE"]},
            )
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
        result = await self._call("crm.lead.update", {"id": lead_id, "fields": data})
        return bool(result.get("result"))

    async def add_timeline_comment(
        self, entity_type: str, entity_id: int, comment: str
    ) -> bool:
        result = await self._call(
            "crm.timeline.comment.add",
            {
                "fields": {
                    "ENTITY_ID": entity_id,
                    "ENTITY_TYPE": entity_type,
                    "COMMENT": comment,
                }
            },
        )
        return result.get("result") is not None

    async def _call(self, method: str, data: dict) -> dict:
        await self._rate_limit()
        for attempt, delay in enumerate(_API_RETRY_DELAYS + [None], start=1):
            try:
                resp = await self._client.post(f"{self._url}{method}", json=data)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "bitrix_retry", method=method, attempt=attempt, error=str(exc)
                )
                if delay is not None:
                    await asyncio.sleep(delay)
        raise httpx.HTTPError(f"Bitrix24 {method} failed after retries")

    async def _rate_limit(self) -> None:
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()
