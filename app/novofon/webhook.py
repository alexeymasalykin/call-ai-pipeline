from datetime import datetime
from app.models.schemas import CallData


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
        timestamp = datetime.now()
    return CallData(
        call_id=payload["call_id"],
        caller_number=payload["caller_id"],
        called_number=payload["called_did"],
        duration=duration,
        direction=payload.get("direction", "incoming"),
        timestamp=timestamp,
        recording_url=payload.get("recording_url"),
    )
