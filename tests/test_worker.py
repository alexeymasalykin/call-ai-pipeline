from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import RetryableError, DownloadError, LLMAnalysisError
from app.worker import handle_call, shutdown


def _make_ctx(settings=None, redis=None, job_try=1):
    """Create a minimal arq worker context."""
    if settings is None:
        settings = AsyncMock()
        settings.ALERT_WEBHOOK_URL = ""
    if redis is None:
        redis = AsyncMock()
        redis.exists.return_value = 0
    return {
        "settings": settings,
        "redis": redis,
        "novofon": AsyncMock(),
        "s3": AsyncMock(),
        "stt": AsyncMock(),
        "llm": AsyncMock(),
        "bitrix": AsyncMock(),
        "job_try": job_try,
    }


VALID_CALL_DATA = {
    "call_id": "test-123",
    "caller_number": "79001234567",
    "called_number": "74951234567",
    "duration": 45,
    "direction": "incoming",
    "timestamp": "2026-03-12T10:00:00",
}


class TestHandleCall:
    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_successful_processing(self, mock_process):
        ctx = _make_ctx()
        await handle_call(ctx, VALID_CALL_DATA)

        mock_process.assert_called_once()
        ctx["redis"].set.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_skips_already_processed(self, mock_process):
        ctx = _make_ctx()
        ctx["redis"].exists.return_value = 1

        await handle_call(ctx, VALID_CALL_DATA)

        mock_process.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_retryable_error_first_try_reraises(self, mock_process):
        mock_process.side_effect = DownloadError("fail")
        ctx = _make_ctx(job_try=1)

        with pytest.raises(DownloadError):
            await handle_call(ctx, VALID_CALL_DATA)

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_retryable_error_last_try_sends_to_dlq(self, mock_dlq, mock_process):
        mock_process.side_effect = DownloadError("fail")
        ctx = _make_ctx(job_try=2)

        await handle_call(ctx, VALID_CALL_DATA)

        mock_dlq.assert_called_once()
        assert "fail" in mock_dlq.call_args[0][2]

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_non_retryable_error_sends_to_dlq_and_reraises(self, mock_dlq, mock_process):
        mock_process.side_effect = RuntimeError("unexpected")
        ctx = _make_ctx(job_try=1)

        with pytest.raises(RuntimeError):
            await handle_call(ctx, VALID_CALL_DATA)

        mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_invalid_call_data_sends_to_dlq(self, mock_dlq):
        ctx = _make_ctx()
        invalid_data = {"call_id": "bad", "missing": "fields"}

        await handle_call(ctx, invalid_data)

        mock_dlq.assert_called_once()
        assert "bad" in mock_dlq.call_args[0][1]
        assert "Invalid call data" in mock_dlq.call_args[0][2]

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_pipeline_error_sends_to_dlq_no_reraise(self, mock_dlq, mock_process):
        mock_process.side_effect = LLMAnalysisError("bad json")
        ctx = _make_ctx(job_try=1)

        await handle_call(ctx, VALID_CALL_DATA)

        mock_dlq.assert_called_once()



class TestShutdown:
    @pytest.mark.asyncio
    async def test_closes_all_clients(self):
        ctx = {
            "bitrix": AsyncMock(),
            "llm": AsyncMock(),
            "novofon": AsyncMock(),
            "s3": AsyncMock(),
            "stt": AsyncMock(),
            "redis": AsyncMock(),
        }
        await shutdown(ctx)

        for name in ("bitrix", "llm", "novofon", "s3", "stt"):
            ctx[name].close.assert_called_once()
        ctx["redis"].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_on_client_close_error(self):
        ctx = {
            "bitrix": AsyncMock(),
            "llm": AsyncMock(),
            "novofon": AsyncMock(),
            "s3": AsyncMock(),
            "stt": AsyncMock(),
            "redis": AsyncMock(),
        }
        ctx["bitrix"].close.side_effect = RuntimeError("close failed")

        await shutdown(ctx)

        # Other clients still closed despite bitrix failure
        ctx["llm"].close.assert_called_once()
        ctx["redis"].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_clients(self):
        ctx = {"redis": AsyncMock()}

        await shutdown(ctx)

        ctx["redis"].aclose.assert_called_once()
