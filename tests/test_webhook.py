import pytest
from app.novofon.webhook import parse_webhook, WebhookIgnored


class TestParseWebhook:
    def test_valid_notify_record(self):
        payload = {"event": "NOTIFY_RECORD", "pbx_call_id": "123456789"}
        result = parse_webhook(payload)
        assert result == "123456789"

    def test_non_record_event_ignored(self):
        payload = {"event": "NOTIFY_END", "pbx_call_id": "123"}
        with pytest.raises(WebhookIgnored, match="event"):
            parse_webhook(payload)

    def test_missing_pbx_call_id_raises(self):
        payload = {"event": "NOTIFY_RECORD"}
        with pytest.raises(KeyError, match="pbx_call_id"):
            parse_webhook(payload)

    def test_empty_event_ignored(self):
        payload = {"pbx_call_id": "123"}
        with pytest.raises(WebhookIgnored):
            parse_webhook(payload)

    def test_pbx_call_id_converted_to_str(self):
        payload = {"event": "NOTIFY_RECORD", "pbx_call_id": 999}
        result = parse_webhook(payload)
        assert result == "999"
