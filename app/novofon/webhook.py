from datetime import datetime, timezone

import structlog

from app.models.schemas import CallData

logger = structlog.get_logger()


class WebhookIgnored(Exception):
    """Webhook event that should be skipped (not an error)."""


def parse_webhook(payload: dict, min_duration: int) -> CallData:
    event = payload.get("event", "")
    if event != "NOTIFY_RECORD":
        raise WebhookIgnored(f"Ignored event type: {event}")
    duration = int(payload["duration"])
    if duration < min_duration:
        raise WebhookIgnored(f"Call duration {duration}s < {min_duration}s minimum")
    call_start = payload.get("call_start", "")
    try:
        timestamp = datetime.fromisoformat(call_start)
    except (ValueError, TypeError):
        logger.warning(
            "invalid_call_start",
            call_start=call_start,
            call_id=payload.get("call_id"),
        )
        timestamp = datetime.now(timezone.utc)
    return CallData(
        call_id=payload["call_id"],
        caller_number=payload["caller_id"],
        called_number=payload["called_did"],
        duration=duration,
        direction=payload.get("direction", "incoming"),
        timestamp=timestamp,
        recording_url=payload.get("recording_url"),
    )
