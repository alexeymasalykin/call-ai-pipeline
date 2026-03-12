from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest
import respx
from app.exceptions import DownloadError
from app.novofon.api import NovofonAPI

@pytest.fixture
def api():
    return NovofonAPI(api_key="test_key", api_secret="test_secret", data_dir="/tmp/call-pipeline-test")

class TestNovofonAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_download_with_direct_url(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).respond(200, content=b"fake-mp3-data")
        path = await api.download_recording("123", recording_url=url)
        assert path.exists()
        assert path.read_bytes() == b"fake-mp3-data"

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_via_api_fallback(self, api, tmp_path):
        api._data_dir = tmp_path
        respx.get("https://api.novofon.com/v1/pbx/record/request/").respond(200, json={"status": "success", "link": "https://novofon.com/dl/123.mp3"})
        respx.get("https://novofon.com/dl/123.mp3").respond(200, content=b"mp3-data")
        path = await api.download_recording("123", recording_url=None)
        assert path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_retries_on_failure(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, content=b"mp3-data")])
        path = await api.download_recording("123", recording_url=url)
        assert path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_raises_after_max_retries(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(return_value=httpx.Response(503))
        with pytest.raises(DownloadError):
            await api.download_recording("123", recording_url=url)
