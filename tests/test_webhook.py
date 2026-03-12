import json
from pathlib import Path
import pytest
from app.novofon.webhook import parse_webhook, WebhookIgnored

@pytest.fixture
def sample_payload() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_webhook.json"
    return json.loads(path.read_text())

class TestParseWebhook:
    def test_valid_notify_record(self, sample_payload):
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.call_id == "123456789"
        assert call_data.caller_number == "79001234567"
        assert call_data.called_number == "74951234567"
        assert call_data.duration == 45
        assert call_data.recording_url == "https://novofon.com/records/123456789.mp3"

    def test_short_call_ignored(self, sample_payload):
        sample_payload["duration"] = "10"
        with pytest.raises(WebhookIgnored, match="duration"):
            parse_webhook(sample_payload, min_duration=15)

    def test_notify_end_ignored(self, sample_payload):
        sample_payload["event"] = "NOTIFY_END"
        with pytest.raises(WebhookIgnored, match="event"):
            parse_webhook(sample_payload, min_duration=15)

    def test_missing_call_id_raises(self, sample_payload):
        del sample_payload["call_id"]
        with pytest.raises(KeyError):
            parse_webhook(sample_payload, min_duration=15)

    def test_direction_incoming_by_default(self, sample_payload):
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.direction == "incoming"

    def test_direction_outgoing(self, sample_payload):
        sample_payload["direction"] = "outgoing"
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.direction == "outgoing"

    def test_no_recording_url(self, sample_payload):
        del sample_payload["recording_url"]
        call_data = parse_webhook(sample_payload, min_duration=15)
        assert call_data.recording_url is None
