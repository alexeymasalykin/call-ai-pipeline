import httpx
import pytest
import respx
from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import Bitrix24APIError
from app.models.schemas import LeadData

WEBHOOK_URL = "https://test.bitrix24.ru/rest/1/testtoken/"


@pytest.fixture
def client():
    return Bitrix24Client(webhook_url=WEBHOOK_URL)


class TestFindLeadByPhone:
    @pytest.mark.asyncio
    @respx.mock
    async def test_finds_existing_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(
            200, json={"result": [{"ID": 42, "STATUS_ID": "NEW", "TITLE": "Existing lead"}]},
        )
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is not None
        assert lead["ID"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_converted_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(
            200, json={"result": [{"ID": 10, "STATUS_ID": "CONVERTED", "TITLE": "Old lead"}]},
        )
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_junk_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(
            200, json={"result": [{"ID": 11, "STATUS_ID": "JUNK", "TITLE": "Junk lead"}]},
        )
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_on_empty_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={"result": []})
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_api_error(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(
            200, json={"error": "QUERY_LIMIT_EXCEEDED", "error_description": "Too many requests"},
        )
        with pytest.raises(Bitrix24APIError, match="QUERY_LIMIT_EXCEEDED"):
            await client.find_lead_by_phone("79001234567")


class TestCreateLead:
    @pytest.fixture
    def lead_data(self):
        return LeadData(
            title="Звонок: тест", phone="79001234567",
            summary="Тест.", qualification="warm",
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_lead_returns_id(self, client, lead_data):
        respx.post(f"{WEBHOOK_URL}crm.lead.add").respond(200, json={"result": 99})
        lead_id = await client.create_lead(lead_data)
        assert lead_id == 99

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_missing_result(self, client, lead_data):
        respx.post(f"{WEBHOOK_URL}crm.lead.add").respond(
            200, json={"error": "ACCESS_DENIED", "error_description": "No access"},
        )
        with pytest.raises(Bitrix24APIError, match="unexpected response"):
            await client.create_lead(lead_data)


class TestUpdateLead:
    @pytest.mark.asyncio
    @respx.mock
    async def test_updates_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(200, json={"result": True})
        await client.update_lead(42, {"TITLE": "Updated"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_falsy_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(200, json={"result": False})
        with pytest.raises(Bitrix24APIError, match="falsy result"):
            await client.update_lead(42, {"TITLE": "Updated"})


class TestAddTimelineComment:
    @pytest.mark.asyncio
    @respx.mock
    async def test_adds_comment(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": 123})
        await client.add_timeline_comment("lead", 42, "AI analysis text")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_null_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": None})
        with pytest.raises(Bitrix24APIError, match="timeline comment failed"):
            await client.add_timeline_comment("lead", 42, "text")


class TestCallRetryLogic:
    """Tests for _call() retry behavior via public methods."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_on_5xx_then_succeeds(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.lead.update")
        route.side_effect = [
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json={"result": True}),
        ]
        await client.update_lead(42, {"TITLE": "Test"})
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_immediately_on_4xx(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(403, text="Forbidden")
        with pytest.raises(Bitrix24APIError, match="client error: 403"):
            await client.update_lead(42, {"TITLE": "Test"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_after_exhausted_retries(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(500, text="Error")
        with pytest.raises(Bitrix24APIError, match="failed after"):
            await client.update_lead(42, {"TITLE": "Test"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_on_transport_error_then_succeeds(self, client):
        route = respx.post(f"{WEBHOOK_URL}crm.lead.update")
        route.side_effect = [
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json={"result": True}),
        ]
        await client.update_lead(42, {"TITLE": "Test"})
        assert route.call_count == 2
