import asyncio
import base64
from pathlib import Path

import httpx
import structlog

from app.exceptions import Bitrix24APIError

logger = structlog.get_logger()
_RATE_LIMIT_DELAY = 0.5
_DEAL_RETRY_DELAY = 30
_DEAL_MAX_RETRIES = 3
_API_RETRY_DELAYS = (5, 10, 20)
_API_RETRY_SCHEDULE = (*_API_RETRY_DELAYS, None)


def _mask_phone(phone: str) -> str:
    if len(phone) > 5:
        return phone[:5] + "****"
    return "****"


class Bitrix24Client:
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url.rstrip("/") + "/"
        self._client = httpx.AsyncClient(timeout=30)
        self._last_request_time: float = 0

    async def close(self) -> None:
        await self._client.aclose()

    async def find_company_by_phone(self, phone: str) -> dict | None:
        """Find company by phone number. Returns first match or None."""
        masked = _mask_phone(phone)
        result = await self._call(
            "crm.company.list",
            {
                "filter": {"PHONE": phone},
                "select": ["ID", "TITLE"],
            },
        )
        if "error" in result:
            raise Bitrix24APIError(
                f"Bitrix24 API error: {result['error']} - "
                f"{result.get('error_description', '')}"
            )
        companies = result.get("result", [])
        if companies:
            logger.info("company_found", company_id=companies[0]["ID"], phone=masked)
            return companies[0]
        logger.warning("company_not_found", phone=masked)
        return None

    async def find_open_deal(self, company_id: int) -> dict | None:
        """Find most recent open deal for company. Retries to allow manager creation delay."""
        for attempt in range(1, _DEAL_MAX_RETRIES + 1):
            result = await self._call(
                "crm.deal.list",
                {
                    "filter": {
                        "COMPANY_ID": company_id,
                        "!STAGE_ID": ["WON", "LOSE"],
                    },
                    "select": ["ID", "TITLE", "STAGE_ID"],
                    "order": {"DATE_CREATE": "DESC"},
                },
            )
            if "error" in result:
                raise Bitrix24APIError(
                    f"Bitrix24 API error: {result['error']} - "
                    f"{result.get('error_description', '')}"
                )
            deals = result.get("result", [])
            if deals:
                logger.info(
                    "deal_found", deal_id=deals[0]["ID"],
                    company_id=company_id, attempt=attempt,
                )
                return deals[0]
            if attempt < _DEAL_MAX_RETRIES:
                logger.info(
                    "deal_not_found_retry",
                    company_id=company_id, attempt=attempt,
                )
                await asyncio.sleep(_DEAL_RETRY_DELAY)
        logger.warning("deal_not_found", company_id=company_id)
        return None

    async def add_timeline_comment(
        self, entity_type: str, entity_id: int, comment: str,
        audio_path: Path | None = None,
    ) -> None:
        """Add timeline comment with optional audio attachment."""
        fields: dict = {
            "ENTITY_ID": entity_id,
            "ENTITY_TYPE": entity_type,
            "COMMENT": comment,
        }
        if audio_path and audio_path.exists():
            encoded = base64.b64encode(audio_path.read_bytes()).decode()
            fields["FILES"] = {"fileData": [audio_path.name, encoded]}
        result = await self._call(
            "crm.timeline.comment.add",
            {"fields": fields},
        )
        if result.get("result") is None:
            raise Bitrix24APIError(
                f"Bitrix24 timeline comment failed: "
                f"entity_type={entity_type}, entity_id={entity_id}"
            )

    async def _call(self, method: str, data: dict) -> dict:
        await self._rate_limit()
        last_exc: Exception | None = None
        for attempt, delay in enumerate(_API_RETRY_SCHEDULE, start=1):
            try:
                resp = await self._client.post(f"{self._url}{method}", json=data)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise Bitrix24APIError(
                        f"Bitrix24 {method} client error: {exc.response.status_code}"
                    ) from exc
                last_exc = exc
            except httpx.TransportError as exc:
                last_exc = exc
            logger.warning(
                "bitrix_retry", method=method, attempt=attempt, error=str(last_exc),
            )
            if delay is not None:
                await asyncio.sleep(delay)
        raise Bitrix24APIError(
            f"Bitrix24 {method} failed after {len(_API_RETRY_SCHEDULE)} attempts"
        ) from last_exc

    async def _rate_limit(self) -> None:
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()
