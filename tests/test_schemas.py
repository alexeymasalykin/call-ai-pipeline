import pytest
from datetime import datetime
from app.models.schemas import CallData, LLMResponse, LeadData

class TestCallData:
    def test_valid_incoming_call(self):
        data = CallData(call_id="123456789", caller_number="79001234567", called_number="74951234567", duration=45, direction="incoming", timestamp=datetime(2026, 3, 12, 10, 0, 0))
        assert data.call_id == "123456789"
        assert data.duration == 45
        assert data.direction == "incoming"

    def test_valid_outgoing_call(self):
        data = CallData(call_id="987654321", caller_number="74951234567", called_number="79001234567", duration=120, direction="outgoing", timestamp=datetime(2026, 3, 12, 11, 0, 0))
        assert data.direction == "outgoing"

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError):
            CallData(call_id="123", caller_number="79001234567", called_number="74951234567", duration=45, direction="unknown", timestamp=datetime(2026, 3, 12, 10, 0, 0))

    def test_recording_url_optional(self):
        data = CallData(call_id="123", caller_number="79001234567", called_number="74951234567", duration=45, direction="incoming", timestamp=datetime(2026, 3, 12, 10, 0, 0))
        assert data.recording_url is None

    def test_recording_url_present(self):
        data = CallData(call_id="123", caller_number="79001234567", called_number="74951234567", duration=45, direction="incoming", timestamp=datetime(2026, 3, 12, 10, 0, 0), recording_url="https://novofon.com/records/123.mp3")
        assert data.recording_url == "https://novofon.com/records/123.mp3"

class TestLLMResponse:
    def test_valid_full_response(self):
        data = LLMResponse(client_name="Иван Петров", company="ООО Ромашка", request="Оптовые поставки", budget_mentioned="500 000 руб", summary="Клиент интересуется оптовыми поставками.", qualification="hot", next_action="Отправить КП", sentiment="positive", tags=["опт", "КП"])
        assert data.qualification == "hot"
        assert len(data.tags) == 2

    def test_minimal_response_with_nulls(self):
        data = LLMResponse(summary="Короткий звонок без деталей.", qualification="cold", sentiment="neutral")
        assert data.client_name is None
        assert data.company is None
        assert data.tags == []

    def test_invalid_qualification_rejected(self):
        with pytest.raises(ValueError):
            LLMResponse(summary="test", qualification="medium", sentiment="neutral")

    def test_invalid_sentiment_rejected(self):
        with pytest.raises(ValueError):
            LLMResponse(summary="test", qualification="cold", sentiment="angry")

class TestLeadData:
    def test_valid_lead(self):
        data = LeadData(title="Звонок: оптовые поставки", client_name="Иван Петров", company="ООО Ромашка", phone="79001234567", summary="Клиент интересуется оптом.", qualification="hot")
        assert data.source == "CALL"

    def test_minimal_lead(self):
        data = LeadData(title="Звонок: неизвестный", phone="79001234567", summary="Требует ручного анализа.", qualification="cold")
        assert data.client_name is None
        assert data.company is None
