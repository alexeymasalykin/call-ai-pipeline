import asyncio
from functools import partial
from pathlib import Path

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from app.exceptions import UploadError

logger = structlog.get_logger()
_RETRY_DELAYS = (5, 10)
_RETRY_SCHEDULE = (*_RETRY_DELAYS, None)  # None = no sleep after final attempt


class S3Client:
    def __init__(self, bucket: str, access_key: str, secret_key: str, endpoint: str) -> None:
        self._bucket = bucket
        self._endpoint = endpoint
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload(self, local_path: Path, s3_key: str) -> str:
        loop = asyncio.get_running_loop()
        for attempt, delay in enumerate(_RETRY_SCHEDULE, start=1):
            try:
                await loop.run_in_executor(
                    None,
                    partial(self._s3.upload_file, str(local_path), self._bucket, s3_key),
                )
                uri = f"{self._endpoint}/{self._bucket}/{s3_key}"
                logger.info("s3_uploaded", key=s3_key, attempt=attempt)
                return uri
            except (ClientError, BotoCoreError) as exc:
                logger.warning("s3_upload_retry", key=s3_key, attempt=attempt, error=str(exc))
                if delay is not None:
                    await asyncio.sleep(delay)
        raise UploadError(f"Failed to upload {s3_key} to S3")

    async def delete(self, s3_key: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(self._s3.delete_object, Bucket=self._bucket, Key=s3_key),
            )
            logger.info("s3_deleted", key=s3_key)
        except (ClientError, BotoCoreError) as exc:
            logger.error("s3_delete_failed", key=s3_key, error=str(exc))
