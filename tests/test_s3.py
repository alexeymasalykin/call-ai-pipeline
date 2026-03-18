from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.exceptions import UploadError
from app.stt.s3 import S3Client


def _make_client_error(msg: str = "fail") -> ClientError:
    return ClientError(
        {"Error": {"Code": "500", "Message": msg}},
        "TestOperation",
    )


@pytest.fixture
def s3_client():
    with patch("app.stt.s3.boto3") as mock_boto:
        client = S3Client(
            bucket="test-bucket", access_key="ak",
            secret_key="sk", endpoint="https://storage.test",
        )
        yield client


class TestS3Upload:
    @pytest.mark.asyncio
    async def test_upload_success(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        uri = await s3_client.upload(mp3, "test.mp3")
        assert uri == "https://storage.test/test-bucket/test.mp3"

    @pytest.mark.asyncio
    async def test_upload_retries_on_failure(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        s3_client._s3.upload_file.side_effect = [
            _make_client_error(), _make_client_error(), None,
        ]
        uri = await s3_client.upload(mp3, "test.mp3")
        assert uri == "https://storage.test/test-bucket/test.mp3"

    @pytest.mark.asyncio
    async def test_upload_raises_after_exhaustion(self, s3_client, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"data")
        s3_client._s3.upload_file.side_effect = _make_client_error("permanent")
        with pytest.raises(UploadError):
            await s3_client.upload(mp3, "test.mp3")


class TestS3Delete:
    @pytest.mark.asyncio
    async def test_delete_success(self, s3_client):
        await s3_client.delete("test.mp3")
        s3_client._s3.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_failure_does_not_raise(self, s3_client):
        s3_client._s3.delete_object.side_effect = _make_client_error()
        await s3_client.delete("test.mp3")
