import httpx
import pytest
import respx
from unittest.mock import patch

from app.crm.bitrix24 import Bitrix24Client, _mask_phone
from app.exceptions import Bitrix24APIError

WEBHOOK_URL = "https://test.bitrix24.ru/rest/1/testtoken/"


@pytest.fixture
def client():
    return Bitrix24Client(webhook_url=WEBHOOK_URL)


class TestFindCompanyByPhone:
    @pytest.mark.asyncio
    @respx.mock
    async def test_finds_existing_company(self, client):
        respx.post(f"{WEBHOOK_URL}crm.company.list").respond(
            200, json={"result": [{"ID": "10", "TITLE": "ООО Ромашка"}]},
        )
        company = await client.find_company_by_phone("79001234567")
        assert company is not None
        assert company["ID"] == "10"

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_on_empty_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.company.list").respond(200, json={"result": []})
        company = await client.find_company_by_phone("79001234567")
        assert company is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_api_error(self, client):
        respx.post(f"{WEBHOOK_URL}crm.company.list").respond(
            200, json={"error": "QUERY_LIMIT_EXCEEDED", "error_description": "Too many"},
        )
        with pytest.raises(Bitrix24APIError, match="QUERY_LIMIT_EXCEEDED"):
            await client.find_company_by_phone("79001234567")


class TestFindOpenDeal:
    @pytest.mark.asyncio
    @respx.mock
    @patch("app.crm.bitrix24._DEAL_RETRY_DELAY", 0)
    async def test_finds_open_deal(self, client):
        respx.post(f"{WEBHOOK_URL}crm.deal.list").respond(
            200, json={"result": [{"ID": "55", "TITLE": "Сделка", "STAGE_ID": "NEW"}]},
        )
        deal = await client.find_open_deal(10)
        assert deal is not None
        assert deal["ID"] == "55"

    @pytest.mark.asyncio
    @respx.mock
    @patch("app.crm.bitrix24._DEAL_RETRY_DELAY", 0)
    async def test_returns_none_after_retries(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.deal.list")
        route.respond(200, json={"result": []})
        deal = await client.find_open_deal(10)
        assert deal is None
        assert route.call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    @respx.mock
    @patch("app.crm.bitrix24._DEAL_RETRY_DELAY", 0)
    async def test_finds_deal_on_retry(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.deal.list")
        route.side_effect = [
            httpx.Response(200, json={"result": []}),
            httpx.Response(200, json={"result": [{"ID": "77", "TITLE": "New deal", "STAGE_ID": "NEW"}]}),
        ]
        deal = await client.find_open_deal(10)
        assert deal is not None
        assert deal["ID"] == "77"
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    @patch("app.crm.bitrix24._DEAL_RETRY_DELAY", 0)
    async def test_raises_on_api_error(self, client):
        respx.post(f"{WEBHOOK_URL}crm.deal.list").respond(
            200, json={"error": "ACCESS_DENIED", "error_description": "No access"},
        )
        with pytest.raises(Bitrix24APIError, match="ACCESS_DENIED"):
            await client.find_open_deal(10)


class TestAddTimelineComment:
    @pytest.mark.asyncio
    @respx.mock
    async def test_adds_comment_to_deal(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": 123})
        await client.add_timeline_comment("deal", 55, "AI analysis text")

    @pytest.mark.asyncio
    @respx.mock
    async def test_adds_comment_to_company(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": 456})
        await client.add_timeline_comment("company", 10, "AI analysis text")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_null_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": None})
        with pytest.raises(Bitrix24APIError, match="timeline comment failed"):
            await client.add_timeline_comment("deal", 55, "text")


class TestCallRetryLogic:
    """Tests for _call() retry behavior via public methods."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_on_5xx_then_succeeds(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add")
        route.side_effect = [
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json={"result": 123}),
        ]
        await client.add_timeline_comment("deal", 55, "text")
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_immediately_on_4xx(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(403, text="Forbidden")
        with pytest.raises(Bitrix24APIError, match="client error: 403"):
            await client.add_timeline_comment("deal", 55, "text")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_after_exhausted_retries(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(500, text="Error")
        with pytest.raises(Bitrix24APIError, match="failed after"):
            await client.add_timeline_comment("deal", 55, "text")

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_on_transport_error_then_succeeds(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add")
        route.side_effect = [
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json={"result": 123}),
        ]
        await client.add_timeline_comment("deal", 55, "text")
        assert route.call_count == 2


class TestMaskPhone:
    def test_long_phone_masked(self):
        assert _mask_phone("79001234567") == "79001****"

    def test_exactly_six_chars_masked(self):
        assert _mask_phone("790012") == "79001****"

    def test_short_phone_fully_masked(self):
        assert _mask_phone("7900") == "****"

    def test_empty_phone_fully_masked(self):
        assert _mask_phone("") == "****"
