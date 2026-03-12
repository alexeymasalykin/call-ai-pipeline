import asyncio
import json
from dataclasses import dataclass

import structlog

from app.exceptions import EmptyTranscriptionError, TranscriptionError

logger = structlog.get_logger()

_POLL_INTERVAL = 3
_POLL_TIMEOUT = 300  # 5 minutes
_RETRY_DELAYS = [10, 20, 40]


@dataclass
class TranscriptSegment:
    speaker: int
    text: str
    start_time: float


class SpeechKitClient:
    """Yandex SpeechKit async recognition client."""

    def __init__(self, folder_id: str, sa_key_file: str) -> None:
        self._folder_id = folder_id
        self._sa_key_file = sa_key_file
        self._iam_token: str | None = None

    async def transcribe(self, s3_uri: str, call_id: str) -> list[TranscriptSegment]:
        """Transcribe audio from S3 URI. Returns list of transcript segments.

        Raises:
            TranscriptionError: if recognition fails after retries.
            EmptyTranscriptionError: if transcription is empty.
        """
        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
            try:
                segments = await self._run_recognition(s3_uri)
                if not segments:
                    raise EmptyTranscriptionError(f"Empty transcription for {call_id}")
                logger.info(
                    "transcription_complete", call_id=call_id,
                    segments=len(segments), attempt=attempt,
                )
                return segments
            except EmptyTranscriptionError:
                raise
            except Exception as exc:
                logger.warning(
                    "stt_retry", call_id=call_id,
                    attempt=attempt, error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        raise TranscriptionError(f"STT failed for {call_id}")

    async def _run_recognition(self, s3_uri: str) -> list[TranscriptSegment]:
        """Submit recognition request and poll for result.

        Uses yandexcloud SDK for IAM token management and API calls.
        Implementation deferred — requires yandexcloud SDK setup with
        actual service account credentials for testing.
        """
        # NOTE: Full implementation requires yandexcloud SDK imports:
        # import yandexcloud
        # from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc
        #
        # The SDK handles:
        # 1. IAM token acquisition and refresh from service account key
        # 2. gRPC channel management
        # 3. Recognition request submission
        # 4. Operation polling
        #
        # Skeleton for e2e integration:
        # sdk = yandexcloud.SDK(service_account_key=json.load(open(self._sa_key_file)))
        # stt = sdk.client(stt_service_pb2_grpc.RecognizerStub)
        # ... submit async recognition with s3_uri ...
        # ... poll operation until complete ...
        # ... parse result into TranscriptSegment list ...
        raise NotImplementedError(
            "SpeechKit integration requires SDK setup with credentials. "
            "See docs/superpowers/specs/2026-03-12-call-ai-pipeline-design.md "
            "section 3 for implementation details."
        )

    @staticmethod
    def segments_to_text(segments: list[TranscriptSegment]) -> str:
        """Convert transcript segments to plain text for LLM."""
        lines = []
        for seg in segments:
            speaker = f"Спикер {seg.speaker}" if seg.speaker >= 0 else "Неизвестный"
            lines.append(f"{speaker}: {seg.text}")
        return "\n".join(lines)
