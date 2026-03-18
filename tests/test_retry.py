"""Tests for per-stage retry logic across pipeline components."""
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.exceptions import DownloadError
from app.novofon.api import NovofonAPI


class TestDownloadRetryDelays:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_correct_number_of_times(self, tmp_path):
        api = NovofonAPI(login="k", password="s", data_dir=str(tmp_path))
        api._access_token = "fake"
        url = "https://novofon.com/records/123.mp3"

        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                return httpx.Response(503)
            return httpx.Response(200, content=b"mp3")

        respx.get(url).mock(side_effect=side_effect)

        path = await api.download_recording("123", recording_url=url)
        assert path.exists()
        assert call_count == 4

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_after_all_retries_exhausted(self, tmp_path):
        api = NovofonAPI(login="k", password="s", data_dir=str(tmp_path))
        api._access_token = "fake"
        url = "https://novofon.com/records/123.mp3"
        respx.get(url).mock(return_value=httpx.Response(503))

        with pytest.raises(DownloadError):
            await api.download_recording("123", recording_url=url)
