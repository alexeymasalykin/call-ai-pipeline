from unittest.mock import AsyncMock, MagicMock

import pytest

from app.worker import _is_processed, _mark_processed


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_new_call_not_processed(self):
        redis = AsyncMock()
        redis.exists.return_value = 0
        assert await _is_processed(redis, "new-call-123") is False

    @pytest.mark.asyncio
    async def test_existing_call_is_processed(self):
        redis = AsyncMock()
        redis.exists.return_value = 1
        assert await _is_processed(redis, "old-call-123") is True

    @pytest.mark.asyncio
    async def test_mark_processed_sets_key_with_ttl(self):
        redis = AsyncMock()
        await _mark_processed(redis, "call-123")
        redis.set.assert_called_once_with("processed:call-123", "1", ex=604800)
