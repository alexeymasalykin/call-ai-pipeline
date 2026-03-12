import asyncio
from pathlib import Path
import httpx
import structlog
from app.exceptions import DownloadError

logger = structlog.get_logger()
_RETRY_DELAYS = [5, 10, 20]


class NovofonAPI:
    def __init__(self, api_key: str, api_secret: str, data_dir: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def download_recording(self, call_id: str, recording_url: str | None = None) -> Path:
        url = recording_url or await self._request_recording_url(call_id)
        return await self._download_file(call_id, url)

    async def _request_recording_url(self, call_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.novofon.com/v1/pbx/record/request/",
                params={"call_id": call_id, "lifetime": 3600},
                headers={"Authorization": f"{self._api_key}:{self._api_secret}"},
            )
            resp.raise_for_status()
            return resp.json()["link"]

    async def _download_file(self, call_id: str, url: str) -> Path:
        dest = self._data_dir / f"{call_id}.mp3"
        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=60)
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    logger.info("recording_downloaded", call_id=call_id, attempt=attempt)
                    return dest
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning("download_retry", call_id=call_id, attempt=attempt, error=str(exc))
                if delay is not None:
                    await asyncio.sleep(delay)
        raise DownloadError(f"Failed to download recording for call {call_id}")
