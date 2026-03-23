import asyncio
import base64
from pathlib import Path

import httpx
import structlog

from app.exceptions import Bitrix24APIError
from app.models.qa_schemas import QAResponse

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

    async def find_company_by_phone(
        self, phone: str, extra_fields: list[str] | None = None,
    ) -> dict | None:
        """Find company by phone number. Returns first match or None."""
        masked = _mask_phone(phone)
        select = ["ID", "TITLE", "ASSIGNED_BY_ID"]
        if extra_fields:
            select.extend(extra_fields)
        result = await self._call(
            "crm.company.list",
            {
                "filter": {"PHONE": phone},
                "select": select,
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

    async def get_user_name(self, user_id: int) -> str | None:
        """Get user full name by ID. Returns None on failure."""
        try:
            result = await self._call("user.get", {"ID": user_id})
        except Bitrix24APIError:
            logger.warning("user_get_failed", user_id=user_id)
            return None
        users = result.get("result", [])
        if not users:
            return None
        u = users[0]
        name = f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip()
        return name or None

    async def resolve_enum_value(
        self, entity: str, field_name: str, enum_id: str | int,
    ) -> str | None:
        """Resolve enumeration field ID to display value."""
        method = f"crm.{entity}.fields"
        result = await self._call(method, {})
        field_def = result.get("result", {}).get(field_name, {})
        for item in field_def.get("items", []):
            if str(item.get("ID")) == str(enum_id):
                return item.get("VALUE")
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
        *,
        entity_type_id: int | None = None,
    ) -> None:
        """Add timeline comment with optional audio attachment.

        For standard entities (deal, company) use entity_type string.
        For smart processes pass entity_type_id (numeric).
        """
        fields: dict = {
            "ENTITY_ID": entity_id,
            "COMMENT": comment,
        }
        if entity_type_id:
            fields["ENTITY_TYPE_ID"] = entity_type_id
        else:
            fields["ENTITY_TYPE"] = entity_type
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

    async def add_qa_item(
        self,
        qa: QAResponse,
        entity_type_id: int,
        field_map: dict[str, str],
        deal_id: int | None = None,
        call_date: str | None = None,
        audio_path: Path | None = None,
        manager_name: str | None = None,
        segment: str | None = None,
    ) -> int:
        """Create QA smart process item in Bitrix24. Returns item ID."""
        mgr = manager_name or qa.manager_name or "Неизвестен"
        date = call_date or ""
        title = f"Оценка {qa.total_score}/10 — {mgr} — {date}"

        fields: dict = {"title": title}

        # Map QA fields to Bitrix custom field codes
        stage_map = {
            "exit_to_dm_score": qa.stage_scores.exit_to_dm.score,
            "opening_score": qa.stage_scores.opening.score,
            "development_score": qa.stage_scores.development.score,
            "closing_score": qa.stage_scores.closing.score,
            "objection_score": qa.stage_scores.objection_handling.score,
        }
        string_map = {
            "product_detected": qa.product_detected,
            "segment_detected": segment or qa.segment_detected,
            "manager_name": mgr,
            "summary": qa.summary,
            "critical_errors": "\n".join(qa.critical_errors),
            "strengths": "\n".join(qa.strengths),
            "improvements": "\n".join(qa.improvements),
        }

        for key, value in {**string_map, **stage_map, "total_score": qa.total_score}.items():
            bitrix_field = field_map.get(key)
            if bitrix_field and value is not None:
                fields[bitrix_field] = value

        if deal_id:
            fields["parentId2"] = deal_id

        result = await self._call(
            "crm.item.add",
            {"entityTypeId": entity_type_id, "fields": fields},
        )
        if "error" in result:
            raise Bitrix24APIError(
                f"Bitrix24 QA item failed: {result['error']} - "
                f"{result.get('error_description', '')}"
            )
        item_id = result.get("result", {}).get("item", {}).get("id")
        if not item_id:
            raise Bitrix24APIError("Bitrix24 QA item created but no ID returned")
        logger.info("qa_item_created", item_id=item_id, total_score=qa.total_score)

        # Attach audio recording to QA item timeline
        if audio_path and audio_path.exists():
            try:
                await self.add_timeline_comment(
                    "", item_id, "Запись звонка",
                    audio_path=audio_path,
                    entity_type_id=entity_type_id,
                )
                logger.info("qa_audio_attached", item_id=item_id)
            except Bitrix24APIError as exc:
                logger.error("qa_audio_attach_failed", item_id=item_id, error=repr(exc))

        return item_id

    async def update_qa_item_deal(
        self, entity_type_id: int, item_id: int, deal_id: int,
    ) -> None:
        """Link existing QA smart process item to a deal."""
        result = await self._call(
            "crm.item.update",
            {
                "entityTypeId": entity_type_id,
                "id": item_id,
                "fields": {"parentId2": deal_id},
            },
        )
        if "error" in result:
            raise Bitrix24APIError(
                f"Bitrix24 QA item update failed: {result['error']} - "
                f"{result.get('error_description', '')}"
            )
        logger.info("qa_item_deal_linked", item_id=item_id, deal_id=deal_id)

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
