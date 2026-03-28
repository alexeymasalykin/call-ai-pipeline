"""Call processing statistics stored in Redis hashes.

Keys: stats:{YYYY-MM-DD} (hash per day, TTL 90 days)
Fields: total, incoming, outgoing, short, no_transcript,
        analyzed, qa_assessed, errors, duration_sum,
        qual:hot, qual:warm, qual:cold, qual:rejected, qual:spam
"""

from datetime import date, timedelta

from redis.asyncio import Redis

_KEY_PREFIX = "stats"
_TTL_SECONDS = 90 * 86400


def _key(d: date) -> str:
    return f"{_KEY_PREFIX}:{d.isoformat()}"


async def increment(redis: Redis, d: date, field: str, amount: int = 1) -> None:
    """Increment a counter field for the given date."""
    key = _key(d)
    await redis.hincrby(key, field, amount)
    await redis.expire(key, _TTL_SECONDS)


async def get_range(redis: Redis, days: int = 30) -> dict[str, dict[str, int]]:
    """Get counters for the last N days."""
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(days)]
    pipe = redis.pipeline()
    for d in dates:
        pipe.hgetall(_key(d))
    responses = await pipe.execute()
    result: dict[str, dict[str, int]] = {}
    for d, raw in zip(dates, responses):
        if raw:
            result[d.isoformat()] = {k.decode(): int(v) for k, v in raw.items()}
    return result
