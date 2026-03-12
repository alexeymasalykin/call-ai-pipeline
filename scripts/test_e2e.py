"""Manual end-to-end test. Requires real API keys in .env.

Usage: python scripts/test_e2e.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.crm.bitrix24 import Bitrix24Client
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData, LeadData
from datetime import datetime


async def test_llm():
    """Test LLM analysis with sample transcript."""
    settings = Settings()
    client = ProxyAPIClient(
        api_key=settings.PROXYAPI_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )

    transcript_path = Path(__file__).parent.parent / "tests/fixtures/sample_transcript.txt"
    transcript = transcript_path.read_text()

    print("=== Testing LLM ===")
    result = await client.analyze_call(
        transcript=transcript,
        caller_number="79001234567",
        duration=120,
    )
    print(f"Client: {result.client_name}")
    print(f"Company: {result.company}")
    print(f"Summary: {result.summary}")
    print(f"Qualification: {result.qualification}")
    print(f"Sentiment: {result.sentiment}")
    print(f"Tags: {result.tags}")
    print(f"Next action: {result.next_action}")
    print()
    return result


async def test_bitrix(analysis):
    """Test Bitrix24 lead creation."""
    settings = Settings()
    client = Bitrix24Client(webhook_url=settings.BITRIX24_WEBHOOK_URL)

    print("=== Testing Bitrix24 ===")

    # Search for existing lead
    lead = await client.find_lead_by_phone("79001234567")
    print(f"Existing lead: {lead}")

    if not lead:
        lead_data = LeadData(
            title=f"[E2E TEST] {analysis.summary[:50]}",
            client_name=analysis.client_name,
            company=analysis.company,
            phone="79001234567",
            summary=analysis.summary,
            qualification=analysis.qualification,
        )
        lead_id = await client.create_lead(lead_data)
        print(f"Created lead: {lead_id}")
    else:
        lead_id = lead["ID"]
        print(f"Using existing lead: {lead_id}")

    comment = (
        f"[E2E TEST] AI-анализ:\n\n{analysis.summary}\n\n"
        f"Квалификация: {analysis.qualification}"
    )
    await client.add_timeline_comment("lead", lead_id, comment)
    print(f"Comment added to lead {lead_id}")


async def main():
    analysis = await test_llm()
    await test_bitrix(analysis)
    print("\n=== E2E test complete ===")


if __name__ == "__main__":
    asyncio.run(main())
