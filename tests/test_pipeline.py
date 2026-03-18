from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import Bitrix24APIError, DownloadError, EmptyTranscriptionError
from app.models.schemas import CallData, LLMResponse
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
    bitrix.find_lead_by_phone.return_value = {"ID": 42, "STATUS_ID": "NEW"}

    return {
        "novofon": novofon,
        "s3": s3,
        "stt": stt,
        "llm": llm,
        "bitrix": bitrix,
    }


class TestProcessCall:
    @pytest.mark.asyncio
    async def test_full_pipeline_update_existing_lead(self, sample_call_data, mock_deps):
        await process_call(sample_call_data, **mock_deps)

        mock_deps["novofon"].download_recording.assert_called_once()
        mock_deps["s3"].upload.assert_called_once()
        mock_deps["stt"].transcribe.assert_called_once()
        mock_deps["llm"].analyze_call.assert_called_once()
        mock_deps["bitrix"].find_lead_by_phone.assert_called_once_with("79001234567")
        mock_deps["bitrix"].update_lead.assert_called_once()
        mock_deps["bitrix"].add_timeline_comment.assert_called_once()
        mock_deps["s3"].delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_call_receives_direction(self, sample_call_data, mock_deps):
        await process_call(sample_call_data, **mock_deps)

        call_kwargs = mock_deps["llm"].analyze_call.call_args
        assert call_kwargs.kwargs["direction"] == "incoming"

    @pytest.mark.asyncio
    async def test_creates_lead_when_not_found(self, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_lead_by_phone.return_value = None
        mock_deps["bitrix"].create_lead.return_value = 99

        await process_call(sample_call_data, **mock_deps)

        mock_deps["bitrix"].create_lead.assert_called_once()
        mock_deps["bitrix"].add_timeline_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_transcription_skips_llm(self, sample_call_data, mock_deps):
        mock_deps["stt"].transcribe.side_effect = EmptyTranscriptionError("empty")

        await process_call(sample_call_data, **mock_deps)

        mock_deps["llm"].analyze_call.assert_not_called()
        mock_deps["bitrix"].find_lead_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_spam_skipped_when_configured(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Спам звонок.",
            qualification="spam",
            sentiment="neutral",
        )

        await process_call(sample_call_data, skip_spam=True, **mock_deps)

        mock_deps["bitrix"].find_lead_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_spam_processed_when_not_skipped(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Спам звонок.",
            qualification="spam",
            sentiment="neutral",
        )

        await process_call(sample_call_data, skip_spam=False, **mock_deps)

        mock_deps["bitrix"].find_lead_by_phone.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejected_always_skipped(self, sample_call_data, mock_deps):
        mock_deps["llm"].analyze_call.return_value = LLMResponse(
            summary="Клиент отказал.",
            qualification="rejected",
            sentiment="negative",
        )

        await process_call(sample_call_data, skip_spam=False, **mock_deps)

        mock_deps["bitrix"].find_lead_by_phone.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_error_propagates(self, sample_call_data, mock_deps):
        mock_deps["novofon"].download_recording.side_effect = DownloadError("fail")

        with pytest.raises(DownloadError):
            await process_call(sample_call_data, **mock_deps)

    @pytest.mark.asyncio
    @patch("app.pipeline._save_failed_crm_result")
    async def test_bitrix_failure_saves_to_json(self, mock_save, sample_call_data, mock_deps):
        mock_deps["bitrix"].find_lead_by_phone.side_effect = Bitrix24APIError("B24 down")

        await process_call(sample_call_data, **mock_deps)

        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_transcription_still_deletes_s3(self, sample_call_data, mock_deps):
        mock_deps["stt"].transcribe.side_effect = EmptyTranscriptionError("empty")

        await process_call(sample_call_data, **mock_deps)

        mock_deps["s3"].delete.assert_called_once()
