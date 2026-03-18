import asyncio
import json
import time
from dataclasses import dataclass

import httpx
import jwt
import structlog

from app.exceptions import EmptyTranscriptionError, TranscriptionError

logger = structlog.get_logger()

_POLL_INTERVAL = 3
_POLL_TIMEOUT = 300  # 5 minutes
_RETRY_DELAYS = (10, 20, 40)
_IAM_REFRESH_MARGIN = 600  # refresh 10 min before expiry
_STT_URL = "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize"
_OPERATION_URL = "https://operation.api.cloud.yandex.net/operations"


@dataclass
class TranscriptSegment:
    speaker: int
    text: str
    start_time: float


class SpeechKitClient:
    """Yandex SpeechKit async recognition client (REST API v2)."""

    def __init__(self, folder_id: str, sa_key_file: str) -> None:
        self._folder_id = folder_id
        self._sa_key_file = sa_key_file
        self._iam_token: str | None = None
        self._iam_expires_at: float = 0
        self._client = httpx.AsyncClient(timeout=30)

    async def _ensure_iam_token(self) -> str:
        """Get or refresh IAM token from service account key."""
        if self._iam_token and time.time() < self._iam_expires_at - _IAM_REFRESH_MARGIN:
            return self._iam_token

        with open(self._sa_key_file) as f:
            sa_key = json.load(f)

        now = int(time.time())
        payload = {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": sa_key["service_account_id"],
            "iat": now,
            "exp": now + 3600,
        }
        encoded = jwt.encode(
            payload, sa_key["private_key"],
            algorithm="PS256", headers={"kid": sa_key["id"]},
        )
        resp = await self._client.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"jwt": encoded},
        )
        resp.raise_for_status()
        self._iam_token = resp.json()["iamToken"]
        self._iam_expires_at = now + 3600
        logger.info("iam_token_refreshed")
        return self._iam_token

    async def transcribe(self, s3_uri: str, call_id: str) -> list[TranscriptSegment]:
        """Transcribe audio from S3 URI. Returns list of transcript segments.

        Raises:
            TranscriptionError: if recognition fails after retries.
            EmptyTranscriptionError: if transcription is empty.
        """
        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
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
        """Submit async recognition and poll for result."""
        token = await self._ensure_iam_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Submit recognition request
        body = {
            "config": {
                "specification": {
                    "languageCode": "ru-RU",
                    "model": "general",
                    "audioEncoding": "MP3",
                    "profanityFilter": False,
                    "literature_text": True,
                    "audioChannelCount": 2,
                },
                "folderId": self._folder_id,
            },
            "audio": {"uri": s3_uri},
        }
        resp = await self._client.post(_STT_URL, json=body, headers=headers)
        resp.raise_for_status()
        operation = resp.json()
        operation_id = operation["id"]
        logger.info("stt_operation_started", operation_id=operation_id)

        # Poll for completion
        deadline = time.time() + _POLL_TIMEOUT
        while time.time() < deadline:
            await asyncio.sleep(_POLL_INTERVAL)
            resp = await self._client.get(
                f"{_OPERATION_URL}/{operation_id}", headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()

            if result.get("error"):
                raise TranscriptionError(
                    f"STT operation failed: {result['error'].get('message', result['error'])}"
                )

            if result.get("done"):
                return self._parse_response(result)

        raise TranscriptionError(f"STT operation {operation_id} timed out after {_POLL_TIMEOUT}s")

    @staticmethod
    def _parse_response(result: dict) -> list[TranscriptSegment]:
        """Parse SpeechKit response into TranscriptSegment list."""
        segments: list[TranscriptSegment] = []
        chunks = result.get("response", {}).get("chunks", [])
        for chunk in chunks:
            channel = int(chunk.get("channelTag", "0"))
            for alt in chunk.get("alternatives", []):
                text = alt.get("text", "").strip()
                if not text:
                    continue
                words = alt.get("words", [])
                start = 0.0
                if words:
                    start_str = words[0].get("startTime", "0s")
                    start = float(start_str.rstrip("s"))
                segments.append(TranscriptSegment(
                    speaker=channel,
                    text=text,
                    start_time=start,
                ))
        segments.sort(key=lambda s: s.start_time)
        return segments

    @staticmethod
    def segments_to_text(segments: list[TranscriptSegment]) -> str:
        """Convert transcript segments to plain text for LLM."""
        lines = []
        for seg in segments:
            speaker = f"Спикер {seg.speaker}" if seg.speaker >= 0 else "Неизвестный"
            lines.append(f"{speaker}: {seg.text}")
        return "\n".join(lines)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
