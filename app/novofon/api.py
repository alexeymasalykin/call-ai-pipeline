import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import structlog

from app.exceptions import DownloadError

logger = structlog.get_logger()

_DOWNLOAD_RETRY_DELAYS = (5, 10, 20)
_TOKEN_REFRESH_MARGIN = 300  # refresh 5 min before expiry
_DATA_API_URL = "https://dataapi-jsonrpc.novofon.ru/v2.0"


class NovofonAPI:
    """Novofon Data API 2.0 client (JSON-RPC)."""

    def __init__(self, login: str, password: str, data_dir: str) -> None:
        self._login = login
        self._password = password
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._access_token: str | None = None
        self._client = httpx.AsyncClient(timeout=30)

    async def _ensure_token(self) -> str:
        """Login and get access token (refreshed on each pipeline run)."""
        if self._access_token:
            return self._access_token

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "login.user",
            "params": {"login": self._login, "password": self._password},
        }
        resp = await self._client.post(
            _DATA_API_URL,
            json=payload,
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise DownloadError(f"Novofon login failed: {data['error']['message']}")

        self._access_token = data["result"]["data"]["access_token"]
        logger.info("novofon_authenticated")
        return self._access_token

    async def _rpc_call(self, method: str, params: dict | None = None) -> dict:
        """Make a JSON-RPC call to Data API 2.0."""
        token = await self._ensure_token()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": {"access_token": token, **(params or {})},
        }
        resp = await self._client.post(
            _DATA_API_URL,
            json=payload,
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            err = data["error"]
            # Token expired — re-login once
            if err.get("data", {}).get("mnemonic") == "auth_error":
                self._access_token = None
                return await self._rpc_call(method, params)
            raise DownloadError(f"Novofon API error: {err['message']}")

        return data["result"]

    async def get_call_info(self, call_id: str) -> dict:
        """Fetch full call details from calls report by communication_id.

        Returns raw call dict with fields like direction, talk_duration,
        contact_phone_number, virtual_phone_number, call_records, etc.
        Raises DownloadError if call not found.
        """
        # Novofon API doesn't support filtering by call ID,
        # so we fetch today's report and search by id
        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        date_till = (now + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        result = await self._rpc_call("get.calls_report", {
            "date_from": date_from,
            "date_till": date_till,
        })
        calls = result.get("data", [])
        target_id = str(call_id)
        for call in calls:
            if str(call.get("id")) == target_id:
                return call
        raise DownloadError(f"Call {call_id} not found in Novofon API")

    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording download URL by communication_id.

        Returns full URL or None if no recording.
        """
        try:
            call_info = await self.get_call_info(call_id)
        except DownloadError:
            return None
        records = call_info.get("call_records") or []
        if records and isinstance(records[0], str):
            return f"https://app.novofon.ru/system/media/talk/{call_id}/{records[0]}/"
        return None

    async def download_recording(self, call_id: str, recording_url: str | None = None) -> Path:
        """Download call recording. Uses recording_url if provided, otherwise fetches from API."""
        if not recording_url:
            recording_url = await self.get_recording_url(call_id)
            if not recording_url:
                raise DownloadError(f"No recording found for call {call_id}")

        return await self._download_file(call_id, recording_url)

    async def _download_file(self, call_id: str, url: str) -> Path:
        """Download file with retries."""
        dest = self._data_dir / f"{call_id}.mp3"
        for attempt, delay in enumerate((*_DOWNLOAD_RETRY_DELAYS, None), start=1):
            try:
                resp = await self._client.get(url, timeout=60)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                logger.info("recording_downloaded", call_id=call_id, attempt=attempt)
                return dest
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning("download_retry", call_id=call_id, attempt=attempt, error=str(exc))
                if delay is not None:
                    await asyncio.sleep(delay)
        raise DownloadError(f"Failed to download recording for call {call_id}")

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
