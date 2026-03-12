import pytest

from app.models.schemas import CallData
from datetime import datetime


@pytest.fixture
def sample_call_data():
    return CallData(
        call_id="test-call-123",
        caller_number="79001234567",
        called_number="74951234567",
        duration=45,
        direction="incoming",
        timestamp=datetime(2026, 3, 12, 10, 0, 0),
        recording_url="https://novofon.com/records/test.mp3",
    )
