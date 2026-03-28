from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import RetryableError, LLMAnalysisError, PipelineError
from app.worker import handle_call, shutdown


NOVOFON_CALL_INFO = {
    "id": 123,
    "direction": "in",
    "virtual_phone_number": "74951234567",
    "contact_phone_number": "79001234567",
    "talk_duration": 45,
    "start_time": "2026-03-12 10:00:00",
    "call_records": ["abc123hash"],
}


def _make_ctx(settings=None, redis=None, job_try=1):
    """Create a minimal arq worker context."""
    if settings is None:
        settings = AsyncMock()
        settings.ALERT_WEBHOOK_URL = ""
        settings.MIN_CALL_DURATION = 15
        settings.BITRIX24_QA_ENTITY_TYPE_ID = 1040
        settings.BITRIX24_COMPANY_SEGMENT_FIELD = ""
    if redis is None:
        redis = AsyncMock()
        redis.exists.return_value = 0
    novofon = AsyncMock()
    novofon.get_call_info.return_value = NOVOFON_CALL_INFO
    return {
        "settings": settings,
        "redis": redis,
        "novofon": novofon,
        "s3": AsyncMock(),
        "stt": AsyncMock(),
        "llm": AsyncMock(),
        "bitrix": AsyncMock(),
        "qa_field_map": {},
        "arq": AsyncMock(),
        "job_try": job_try,
    }


class TestHandleCall:
    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_successful_processing(self, mock_process):
        mock_process.return_value = None
        ctx = _make_ctx()
        await handle_call(ctx, "123")

        mock_process.assert_called_once()
        ctx["redis"].set.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_skips_already_processed(self, mock_process):
        ctx = _make_ctx()
        ctx["redis"].exists.return_value = 1

        await handle_call(ctx, "123")

        mock_process.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_retryable_error_first_try_reraises(self, mock_process):
        mock_process.side_effect = RetryableError("fail")
        ctx = _make_ctx(job_try=1)

        with pytest.raises(RetryableError):
            await handle_call(ctx, "123")

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_retryable_error_last_try_sends_to_dlq(self, mock_dlq, mock_process):
        mock_process.side_effect = RetryableError("fail")
        ctx = _make_ctx(job_try=2)

        await handle_call(ctx, "123")

        mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_unexpected_error_sends_to_dlq_and_reraises(self, mock_dlq, mock_process):
        mock_process.side_effect = RuntimeError("unexpected")
        ctx = _make_ctx(job_try=1)

        with pytest.raises(RuntimeError):
            await handle_call(ctx, "123")

        mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_novofon_fetch_failure_sends_to_dlq(self, mock_dlq):
        ctx = _make_ctx()
        ctx["novofon"].get_call_info.side_effect = Exception("API down")

        await handle_call(ctx, "123")

        mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    @patch("app.worker._add_to_dlq", new_callable=AsyncMock)
    async def test_pipeline_error_sends_to_dlq_no_reraise(self, mock_dlq, mock_process):
        mock_process.side_effect = LLMAnalysisError("bad json")
        ctx = _make_ctx(job_try=1)

        await handle_call(ctx, "123")

        mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.process_call", new_callable=AsyncMock)
    async def test_short_call_skipped(self, mock_process):
        ctx = _make_ctx()
        short_call = {**NOVOFON_CALL_INFO, "talk_duration": 5}
        ctx["novofon"].get_call_info.return_value = short_call

        await handle_call(ctx, "123")

        mock_process.assert_not_called()


class TestShutdown:
    @pytest.mark.asyncio
    async def test_closes_all_clients(self):
        ctx = {
            "bitrix": AsyncMock(),
            "llm": AsyncMock(),
            "novofon": AsyncMock(),
            "s3": AsyncMock(),
            "stt": AsyncMock(),
            "arq": AsyncMock(),
            "redis": AsyncMock(),
        }
        await shutdown(ctx)

        for name in ("bitrix", "llm", "novofon", "s3", "stt"):
            ctx[name].close.assert_called_once()
        ctx["arq"].aclose.assert_called_once()
        ctx["redis"].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_on_client_close_error(self):
        ctx = {
            "bitrix": AsyncMock(),
            "llm": AsyncMock(),
            "novofon": AsyncMock(),
            "s3": AsyncMock(),
            "stt": AsyncMock(),
            "arq": AsyncMock(),
            "redis": AsyncMock(),
        }
        ctx["bitrix"].close.side_effect = RuntimeError("close failed")

        await shutdown(ctx)

        ctx["llm"].close.assert_called_once()
        ctx["redis"].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_clients(self):
        ctx = {"redis": AsyncMock()}

        await shutdown(ctx)

        ctx["redis"].aclose.assert_called_once()
