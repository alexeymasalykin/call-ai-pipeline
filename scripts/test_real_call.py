"""Test real call analysis: Novofon → S3 → SpeechKit → LLM (without CRM)."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

async def main():
    call_id = sys.argv[1] if len(sys.argv) > 1 else "334179093"
    print(f"=== Testing call {call_id} ===\n")

    # 1. Download recording from Novofon
    print("[1/5] Downloading recording from Novofon...")
    from app.novofon.api import NovofonAPI
    novofon = NovofonAPI(
        login=os.environ["NOVOFON_LOGIN"],
        password=os.environ["NOVOFON_PASSWORD"],
        data_dir="/tmp/call-test",
    )
    mp3_path = await novofon.download_recording(call_id)
    size_kb = mp3_path.stat().st_size / 1024
    print(f"  Downloaded: {mp3_path} ({size_kb:.0f} KB)")

    # 2. Upload to S3
    print("\n[2/5] Uploading to S3...")
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

    # 3. Transcribe via SpeechKit
    print("\n[3/5] Transcribing via SpeechKit...")
    print("  SKIPPED — SpeechKit _run_recognition not implemented yet")
    print("  Using mock transcript for LLM test...")
    transcript = (
        "Спикер 1: Добрый день, компания ТендерМагнит.\n"
        "Спикер 2: Здравствуйте, меня интересует участие в тендерах.\n"
        "Спикер 1: Да, мы помогаем с подготовкой документации. Какой тендер вас интересует?\n"
        "Спикер 2: Госзакупки по 44-ФЗ, поставка оборудования.\n"
        "Спикер 1: Отлично, мы работаем с этим. Стоимость сопровождения от 15 000 рублей.\n"
        "Спикер 2: Хорошо, отправьте мне коммерческое предложение на почту.\n"
        "Спикер 1: Записал, отправлю в течение часа. Спасибо за звонок!"
    )

    # 4. Analyze via LLM
    print("\n[4/5] Analyzing via LLM...")
    from app.llm.proxyapi_client import ProxyAPIClient
    llm = ProxyAPIClient(
        api_key=os.environ["PROXYAPI_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    )
    analysis = await llm.analyze_call(transcript, "74952110506", 305)
    print(f"  Result:")
    print(json.dumps(analysis.model_dump(mode="json"), indent=2, ensure_ascii=False))

    # 5. Cleanup
    print("\n[5/5] Cleanup...")
    await s3.delete(s3_key)
    mp3_path.unlink(missing_ok=True)
    await novofon.close()
    await llm.close()
    print("  Done!")

    print("\n=== Pipeline test complete ===")

if __name__ == "__main__":
    asyncio.run(main())
