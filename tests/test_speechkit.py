import pytest

from app.exceptions import EmptyTranscriptionError
from app.stt.speechkit import SpeechKitClient, TranscriptSegment


class TestSegmentsToText:
    def test_converts_segments_to_text(self):
        segments = [
            TranscriptSegment(speaker=0, text="Здравствуйте", start_time=0.0),
            TranscriptSegment(speaker=1, text="Добрый день", start_time=1.5),
        ]
        result = SpeechKitClient.segments_to_text(segments)
        assert "Спикер 0: Здравствуйте" in result
        assert "Спикер 1: Добрый день" in result

    def test_empty_segments_returns_empty_string(self):
        result = SpeechKitClient.segments_to_text([])
        assert result == ""

    def test_single_segment(self):
        segments = [TranscriptSegment(speaker=0, text="Тест", start_time=0.0)]
        result = SpeechKitClient.segments_to_text(segments)
        assert result == "Спикер 0: Тест"

    def test_negative_speaker_shows_unknown(self):
        segments = [TranscriptSegment(speaker=-1, text="Привет", start_time=0.0)]
        result = SpeechKitClient.segments_to_text(segments)
        assert result == "Неизвестный: Привет"
