from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import Bitrix24APIError, DownloadError, EmptyTranscriptionError
from app.models.schemas import LLMResponse
from app.pipeline import process_call
from app.stt.speechkit import TranscriptSegment


@pytest.fixture
def mock_deps():
    """Create mocked pipeline dependencies."""
    novofon = AsyncMock()
    novofon.download_recording.return_value = Path("/tmp/test.mp3")

    s3 = AsyncMock()
    s3.upload.return_value = "https://storage.yandexcloud.net/bucket/test.mp3"

    stt = AsyncMock()
    stt.transcribe.return_value = [
        TranscriptSegment(speaker=0, text="Здравствуйте", start_time=0.0),
        TranscriptSegment(speaker=1, text="Добрый день", start_time=1.5),
    ]
    stt.segments_to_text = MagicMock(
        return_value="Спикер 0: Здравствуйте\nСпикер 1: Добрый день"
    )

    llm = AsyncMock()
    llm.analyze_call.return_value = LLMResponse(
        client_name="Иван",
        summary="Тестовый звонок.",
        qualification="warm",
        sentiment="neutral",
        tags=["тест"],
    )

    bitrix = AsyncMock()
    bitrix.find_company_by_phone.return_value = {"ID": "10", "TITLE": "ООО Ромашка"}
    bitrix.find_open_deal.return_value = {"ID": "55", "TITLE": "Сделка", "STAGE_ID": "NEW"}

    return {
        "novofon": novofon,
        "s3": s3,
        "stt": stt,
        "llm": llm,
        "bitrix": bitrix,
    }


class TestProcessCall:
    @pytest.mark.asyncio
    async def test_full_pipeline_comment_on_deal(self, sample_call_data, mock_deps):
        await process_call(sample_call_data, **mock_deps)

        mock_deps["novofon"].download_recording.assert_called_once()
        mock_deps["s3"].upload.assert_called_once()
        mock_deps["stt"].transcribe.assert_called_once()
        mock_deps["llm"].analyze_call.assert_called_once()
        mock_deps["bitrix"].find_company_by_phone.assert_called_once()
        mock_deps["bitrix"].find_open_deal.assert_called_once_with(10)
        mock_deps["bitrix"].add_timeline_comment.assert_called_once()
        # Incoming call — search by caller_number
        assert mock_deps["bitrix"].find_company_by_phone.call_args[0][0] == "79001234567"
        # Comment on deal
        assert mock_deps["bitrix"].add_timeline_comment.call_args[0][0] == "deal"
        assert mock_deps["bitrix"].add_timeline_comment.call_args[0][1] == 55

    @pytest.mark.asyncio
    async def test_outgoing_call_searches_by_called_number(self, mock_deps):
        from datetime import datetime
        from app.models.schemas import CallData

        outgoing_call = CallData(
            call_id="out-123", caller_number="74951234567",
            called_number="79001234567", duration=60,
            direction="outgoing", timestamp=datetime(2026, 3, 18, 10, 0, 0),
        )
        await process_call(outgoing_call, **mock_deps)

        mock_deps["bitrix"].find_company_by_phone.assert_called_once_with("79001234567")

    @pytest.mark.asyncio
    async def test_no_deal_comments_on_company(self, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_open_deal.return_value = None

        await process_call(sample_call_data, **mock_deps)

        mock_deps["bitrix"].add_timeline_comment.assert_called_once()
        assert mock_deps["bitrix"].add_timeline_comment.call_args[0][0] == "company"
        assert mock_deps["bitrix"].add_timeline_comment.call_args[0][1] == 10

    @pytest.mark.asyncio
    @patch("app.pipeline._save_failed_crm_result")
    async def test_company_not_found_saves_locally(self, mock_save, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_company_by_phone.return_value = None

        await process_call(sample_call_data, **mock_deps)

        mock_save.assert_called_once()
        mock_deps["bitrix"].find_open_deal.assert_not_called()
        mock_deps["bitrix"].add_timeline_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_call_receives_direction(self, sample_call_data, mock_deps):
        await process_call(sample_call_data, **mock_deps)

        call_kwargs = mock_deps["llm"].analyze_call.call_args.kwargs
        assert call_kwargs["direction"] == "incoming"

    @pytest.mark.asyncio
    async def test_empty_transcription_skips_llm(self, sample_call_data, mock_deps):
        mock_deps["stt"].transcribe.side_effect = EmptyTranscriptionError("empty")

        await process_call(sample_call_data, **mock_deps)

        mock_deps["llm"].analyze_call.assert_not_called()
        mock_deps["bitrix"].find_company_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_spam_skipped(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Спам звонок.",
            qualification="spam",
            sentiment="neutral",
        )

        await process_call(sample_call_data, **mock_deps)

        mock_deps["bitrix"].find_company_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejected_skipped(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Клиент отказал.",
            qualification="rejected",
            sentiment="negative",
        )

        await process_call(sample_call_data, **mock_deps)

        mock_deps["bitrix"].find_company_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_error_propagates(self, sample_call_data, mock_deps):
        mock_deps["novofon"].download_recording.side_effect = DownloadError("fail")

        with pytest.raises(DownloadError):
            await process_call(sample_call_data, **mock_deps)

    @pytest.mark.asyncio
    @patch("app.pipeline._save_failed_crm_result")
    async def test_bitrix_failure_saves_to_json(self, mock_save, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_company_by_phone.side_effect = Bitrix24APIError("B24 down")

        await process_call(sample_call_data, **mock_deps)

        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_transcription_still_deletes_s3(self, sample_call_data, mock_deps):
        mock_deps["stt"].transcribe.side_effect = EmptyTranscriptionError("empty")

        await process_call(sample_call_data, **mock_deps)

        mock_deps["s3"].delete.assert_called_once()
