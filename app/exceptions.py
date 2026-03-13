class PipelineError(Exception):
    """Base exception for pipeline errors."""


class RetryableError(PipelineError):
    """Error in external service that may be transient — arq will retry."""


class DownloadError(RetryableError):
    """Failed to download recording from Novofon."""


class UploadError(RetryableError):
    """Failed to upload file to S3."""


class TranscriptionError(RetryableError):
    """Failed to transcribe audio via SpeechKit."""


class EmptyTranscriptionError(PipelineError):
    """Transcription returned empty text — skip LLM and CRM stages."""


class LLMAnalysisError(PipelineError):
    """LLM returned invalid or unparseable response (internal retries exhausted)."""


class Bitrix24APIError(PipelineError):
    """Bitrix24 API returned an error or unexpected response."""
