class PipelineError(Exception):
    """Base exception for pipeline errors."""


class TerminalError(PipelineError):
    """Error that should trigger arq job retry."""


class DownloadError(TerminalError):
    """Failed to download recording from Novofon."""


class UploadError(TerminalError):
    """Failed to upload file to S3."""


class TranscriptionError(TerminalError):
    """Failed to transcribe audio via SpeechKit."""


class EmptyTranscriptionError(PipelineError):
    """Transcription returned empty text — skip LLM and CRM stages."""
