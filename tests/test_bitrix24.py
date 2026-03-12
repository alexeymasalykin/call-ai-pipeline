import pytest
import respx
import httpx
from app.crm.bitrix24 import Bitrix24Client
from app.models.schemas import LeadData

WEBHOOK_URL = "https://test.bitrix24.ru/rest/1/testtoken/"

@pytest.fixture
def client():
    return Bitrix24Client(webhook_url=WEBHOOK_URL)

class TestFindLeadByPhone:
    @pytest.mark.asyncio
    @respx.mock
    async def test_finds_existing_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={"result": [{"ID": 42, "STATUS_ID": "NEW", "TITLE": "Existing lead"}]})
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is not None
        assert lead["ID"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_converted_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={"result": [{"ID": 10, "STATUS_ID": "CONVERTED", "TITLE": "Old lead"}]})
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_junk_leads(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={"result": [{"ID": 11, "STATUS_ID": "JUNK", "TITLE": "Junk lead"}]})
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_on_empty_result(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.list").respond(200, json={"result": []})
        lead = await client.find_lead_by_phone("79001234567")
        assert lead is None

class TestCreateLead:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_lead_returns_id(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.add").respond(200, json={"result": 99})
        lead_data = LeadData(title="Звонок: тест", phone="79001234567", summary="Тест.", qualification="warm")
        lead_id = await client.create_lead(lead_data)
        assert lead_id == 99

class TestUpdateLead:
    @pytest.mark.asyncio
    @respx.mock
    async def test_updates_lead(self, client):
        respx.post(f"{WEBHOOK_URL}crm.lead.update").respond(200, json={"result": True})
        result = await client.update_lead(42, {"TITLE": "Updated"})
        assert result is True

class TestAddTimelineComment:
    @pytest.mark.asyncio
    @respx.mock
    async def test_adds_comment(self, client):
        respx.post(f"{WEBHOOK_URL}crm.timeline.comment.add").respond(200, json={"result": 123})
        result = await client.add_timeline_comment("lead", 42, "AI analysis text")
        assert result is True
