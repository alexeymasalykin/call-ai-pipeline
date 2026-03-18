"""Test: upload MP3 to S3 → SpeechKit transcription → LLM analysis."""
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


async def main():
    mp3_path = Path("2026-03-17_17-40-44.328396_from_79240778262_to_0100481_session_334179093_talk.mp3")
    call_id = "334179093"
    caller_number = "79240778262"
    duration = 305

    print(f"=== Full pipeline test: {mp3_path.name} ===\n")

    # 1. Upload to S3
    print("[1/4] Uploading to S3...")
    from app.stt.s3 import S3Client
    s3 = S3Client(
        bucket=os.environ["YANDEX_S3_BUCKET"],
        access_key=os.environ["YANDEX_S3_ACCESS_KEY"],
        secret_key=os.environ["YANDEX_S3_SECRET_KEY"],
        endpoint=os.environ["YANDEX_S3_ENDPOINT"],
    )
    s3_key = f"test/{call_id}.mp3"
    s3_uri = await s3.upload(mp3_path, s3_key)
    print(f"  Uploaded: {s3_uri}")

    # 2. Transcribe
    print("\n[2/4] Transcribing via SpeechKit...")
    from app.stt.speechkit import SpeechKitClient
    stt = SpeechKitClient(
        folder_id=os.environ["YANDEX_CLOUD_FOLDER_ID"],
        sa_key_file=os.environ.get("YANDEX_CLOUD_SA_KEY_FILE", "service_account_key.json"),
    )
    segments = await stt.transcribe(s3_uri, call_id)
    transcript = stt.segments_to_text(segments)
    print(f"  Segments: {len(segments)}")
    print(f"  Transcript:\n{transcript}\n")

    # 3. Analyze via LLM
    print("[3/4] Analyzing via LLM...")
    from app.llm.proxyapi_client import ProxyAPIClient
    llm = ProxyAPIClient(
        api_key=os.environ["PROXYAPI_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    )
    analysis = await llm.analyze_call(transcript, caller_number, duration)
    print(f"  Result:")
    print(json.dumps(analysis.model_dump(mode="json"), indent=2, ensure_ascii=False))

    # 4. Cleanup
    print("\n[4/4] Cleanup S3...")
    await s3.delete(s3_key)
    await stt.close()
    await llm.close()

    print("\n=== Pipeline test complete! ===")


if __name__ == "__main__":
    asyncio.run(main())
