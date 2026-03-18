import asyncio
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

    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording URL from call report by communication_id.

        Returns first available recording URL or None if no recording.
        """
        result = await self._rpc_call("get.calls_report", {
            "filter": {"id": int(call_id)},
            "date_from": "2020-01-01 00:00:00",
            "date_till": "2030-01-01 00:00:00",
        })
        calls = result.get("data", [])
        if not calls:
            return None

        call = calls[0]
        # call_records contains mp3, wav_call_records contains wav
        records = call.get("call_records") or call.get("wav_call_records") or []
        if records:
            return records[0] if isinstance(records[0], str) else None
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
