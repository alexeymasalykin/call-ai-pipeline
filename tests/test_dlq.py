import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.worker import _add_to_dlq


class TestDLQ:
    @pytest.mark.asyncio
    async def test_adds_to_failed_calls(self):
        redis = AsyncMock()
        await _add_to_dlq(redis, "call-123", "DownloadError: failed", alert_url="")

        redis.rpush.assert_called_once()
        args = redis.rpush.call_args
        assert args[0][0] == "failed_calls"
        payload = json.loads(args[0][1])
        assert payload["call_id"] == "call-123"
        assert payload["error"] == "DownloadError: failed"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_sends_alert_when_url_configured(self):
        redis = AsyncMock()
        mock_post = AsyncMock()
        with patch("app.worker.httpx.AsyncClient.post", mock_post):
            await _add_to_dlq(
                redis, "call-123", "error",
                alert_url="https://alert.test/hook",
            )
            redis.rpush.assert_called_once()
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["json"]["call_id"] == "call-123"

    @pytest.mark.asyncio
    async def test_alert_failure_does_not_raise(self):
        redis = AsyncMock()
        mock_post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        with patch("app.worker.httpx.AsyncClient.post", mock_post):
            await _add_to_dlq(
                redis, "call-123", "error",
                alert_url="https://alert.test/hook",
            )
            redis.rpush.assert_called_once()
