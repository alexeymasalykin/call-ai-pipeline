"""Verify all external service credentials."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()


async def check_s3() -> bool:
    """Upload and delete a test object in S3."""
    import aioboto3

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=os.environ["YANDEX_S3_ENDPOINT"],
        aws_access_key_id=os.environ["YANDEX_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["YANDEX_S3_SECRET_KEY"],
    ) as s3:
        bucket = os.environ["YANDEX_S3_BUCKET"]
        key = "_test_credentials_check.txt"
        await s3.put_object(Bucket=bucket, Key=key, Body=b"test")
        await s3.delete_object(Bucket=bucket, Key=key)
        print(f"  bucket={bucket}, upload+delete OK")
    return True


async def check_bitrix24() -> bool:
    """Call crm.lead.list with limit=1 (read-only)."""
    import httpx

    url = os.environ["BITRIX24_WEBHOOK_URL"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{url}crm.lead.list", json={"select": ["ID"], "start": 0})
        resp.raise_for_status()
        data = resp.json()
        total = data.get("total", "?")
        print(f"  total leads={total}, API OK")
    return True


async def check_proxyapi() -> bool:
    """Send a minimal LLM request."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.environ["PROXYAPI_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
    )
    resp = await client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Ответь одним словом: работает?"}],
        max_tokens=10,
    )
    text = resp.choices[0].message.content.strip()
    print(f"  model={resp.model}, response=\"{text}\"")
    await client.close()
    return True


async def check_novofon() -> bool:
    """Check Novofon Data API 2.0 — login and get token."""
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "login.user",
        "params": {
            "login": os.environ["NOVOFON_LOGIN"],
            "password": os.environ["NOVOFON_PASSWORD"],
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://dataapi-jsonrpc.novofon.ru/v2.0",
            json=payload,
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "result" in data:
            token = data["result"]["data"]["access_token"]
            print(f"  token={token[:20]}..., Data API 2.0 OK")
        else:
            raise RuntimeError(data["error"]["message"])
    return True


async def check_yc_iam() -> bool:
    """Get IAM token from service account key."""
    import time
    import jwt
    import httpx

    sa_key_file = os.environ.get("YANDEX_CLOUD_SA_KEY_FILE", "service_account_key.json")
    with open(sa_key_file) as f:
        sa_key = json.load(f)

    now = int(time.time())
    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": sa_key["service_account_id"],
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, sa_key["private_key"], algorithm="PS256", headers={"kid": sa_key["id"]})

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"jwt": token},
        )
        resp.raise_for_status()
        iam_token = resp.json()["iamToken"]
        print(f"  IAM token={iam_token[:20]}..., OK")
    return True


async def main() -> None:
    checks = [
        ("S3 (Yandex Object Storage)", check_s3),
        ("Bitrix24 CRM", check_bitrix24),
        ("ProxyAPI (LLM)", check_proxyapi),
        ("Novofon API", check_novofon),
        ("YC IAM Token (SpeechKit)", check_yc_iam),
    ]

    results = []
    for name, fn in checks:
        print(f"\n[{name}]")
        try:
            await fn()
            results.append((name, True, None))
            print(f"  ✓ OK")
        except Exception as exc:
            results.append((name, False, str(exc)))
            print(f"  ✗ FAIL: {exc}")

    print("\n" + "=" * 50)
    ok = sum(1 for _, s, _ in results if s)
    total = len(results)
    print(f"Result: {ok}/{total} services OK")
    if ok < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
