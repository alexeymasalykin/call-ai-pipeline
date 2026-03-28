"""Backfill Redis call stats from Novofon call history.

Usage: python -m scripts.backfill_stats [--days 30]
"""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from collections import defaultdict

import redis
from app.config import Settings
from app.novofon.api import NovofonAPI


async def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    settings = Settings()
    novofon = NovofonAPI(
        login=settings.NOVOFON_LOGIN,
        password=settings.NOVOFON_PASSWORD,
        data_dir="/tmp",
    )
    redis_url = settings.REDIS_URL.replace("redis://redis:", "redis://127.0.0.1:")
    r = redis.Redis.from_url(redis_url)

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    date_till = (now + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    print(f"Fetching calls from {date_from} to {date_till}...")

    result = await novofon._rpc_call("get.calls_report", {
        "date_from": date_from,
        "date_till": date_till,
    })

    calls = result.get("data", [])
    print(f"Got {len(calls)} calls")

    # Aggregate by date
    daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    min_date = date(2026, 3, 11)

    for call in calls:
        start_time = call.get("start_time", "")
        try:
            dt = datetime.fromisoformat(start_time)
            call_date = dt.date()
        except (ValueError, TypeError):
            continue

        if call_date < min_date:
            continue

        raw_dir = call.get("direction", "in")
        if raw_dir != "out":
            continue

        d = call_date.isoformat()
        duration = int(call.get("talk_duration", 0))

        daily[d]["total"] += 1
        daily[d]["outgoing"] += 1
        daily[d]["duration_sum"] += duration

        if duration < settings.MIN_CALL_DURATION:
            daily[d]["short"] += 1

    # Write to Redis
    for d, fields in sorted(daily.items()):
        key = f"stats:{d}"
        # Don't overwrite pipeline-generated stats, merge instead
        existing = r.hgetall(key)
        if existing:
            print(f"  {d}: already has data, skipping")
            continue
        r.hset(key, mapping=fields)
        r.expire(key, 90 * 86400)
        total = fields["total"]
        short = fields.get("short", 0)
        inc = fields.get("incoming", 0)
        out = fields.get("outgoing", 0)
        print(f"  {d}: {total} calls ({out} out / {inc} in, {short} short)")

    await novofon.close()
    r.close()
    print("Done")


async def backfill_if_empty(redis_client: "redis.Redis", settings: "Settings | None" = None) -> None:
    """Run backfill only if Redis has fewer than 3 stats keys.

    Called from worker startup to auto-recover after data loss.
    """
    existing = redis_client.keys("stats:*")
    if len(existing) >= 3:
        return

    print("Stats empty or incomplete, backfilling from Novofon...")
    if settings is None:
        settings = Settings()
    await _backfill_from_novofon(settings, redis_client, days=30)


async def _backfill_from_novofon(
    settings: "Settings", r: "redis.Redis", days: int = 30,
) -> None:
    novofon = NovofonAPI(
        login=settings.NOVOFON_LOGIN,
        password=settings.NOVOFON_PASSWORD,
        data_dir="/tmp",
    )
    try:
        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        date_till = (now + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

        result = await novofon._rpc_call("get.calls_report", {
            "date_from": date_from,
            "date_till": date_till,
        })
        calls = result.get("data", [])

        daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for call in calls:
            start_time = call.get("start_time", "")
            try:
                dt = datetime.fromisoformat(start_time)
                d = dt.date().isoformat()
            except (ValueError, TypeError):
                continue
            duration = int(call.get("talk_duration", 0))
            raw_dir = call.get("direction", "in")
            direction = "outgoing" if raw_dir == "out" else "incoming"

            daily[d]["total"] += 1
            daily[d][direction] += 1
            daily[d]["duration_sum"] += duration
            if duration < settings.MIN_CALL_DURATION:
                daily[d]["short"] += 1

        for d, fields in sorted(daily.items()):
            key = f"stats:{d}"
            if r.exists(key):
                continue
            r.hset(key, mapping=fields)
            r.expire(key, 90 * 86400)
            print(f"  {d}: {fields.get('total', 0)} calls")

        print(f"Backfilled {len(daily)} days from {len(calls)} calls")
    finally:
        await novofon.close()


if __name__ == "__main__":
    asyncio.run(main())
