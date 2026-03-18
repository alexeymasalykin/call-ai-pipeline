import structlog

logger = structlog.get_logger()


class WebhookIgnored(Exception):
    """Webhook event that should be skipped (not an error)."""


def parse_webhook(payload: dict) -> str:
    """Parse Novofon NOTIFY_RECORD webhook. Returns pbx_call_id.

    Novofon sends minimal data: event, pbx_call_id, call_id_with_rec.
    Full call details are fetched later via Data API in the worker.
    """
    event = payload.get("event", "")
    if event != "NOTIFY_RECORD":
        raise WebhookIgnored(f"Ignored event type: {event}")
    pbx_call_id = payload.get("pbx_call_id")
    if not pbx_call_id:
        raise KeyError("pbx_call_id missing from webhook payload")
    return str(pbx_call_id)
