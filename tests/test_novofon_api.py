from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest
import respx
from app.exceptions import DownloadError
from app.novofon.api import NovofonAPI


@pytest.fixture
def api():
    client = NovofonAPI(login="test@test.com", password="pass", data_dir="/tmp/call-pipeline-test")
    client._access_token = "fake-token"  # skip login
    return client


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
        respx.post("https://dataapi-jsonrpc.novofon.ru/v2.0").respond(200, json={
            "jsonrpc": "2.0", "id": 1,
            "result": {"data": [{
                "id": 123,
                "call_records": ["https://novofon.com/dl/123.mp3"],
                "wav_call_records": [],
            }], "metadata": {}},
        })
        respx.get("https://novofon.com/dl/123.mp3").respond(200, content=b"mp3-data")
        path = await api.download_recording("123", recording_url=None)
        assert path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_retries_on_failure(self, api, tmp_path):
        api._data_dir = tmp_path
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(side_effect=[
            httpx.Response(503), httpx.Response(503),
            httpx.Response(200, content=b"mp3-data"),
        ])
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

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_recording_raises(self, api):
        respx.post("https://dataapi-jsonrpc.novofon.ru/v2.0").respond(200, json={
            "jsonrpc": "2.0", "id": 1,
            "result": {"data": [{"id": 123, "call_records": [], "wav_call_records": []}], "metadata": {}},
        })
        with pytest.raises(DownloadError, match="No recording found"):
            await api.download_recording("123")

    @pytest.mark.asyncio
    @respx.mock
    async def test_call_not_found_raises(self, api):
        respx.post("https://dataapi-jsonrpc.novofon.ru/v2.0").respond(200, json={
            "jsonrpc": "2.0", "id": 1,
            "result": {"data": [], "metadata": {}},
        })
        with pytest.raises(DownloadError, match="No recording found"):
            await api.download_recording("999")
