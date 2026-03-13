import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_settings(monkeypatch):
    """Set all required env vars for Settings."""
    env = {
        "NOVOFON_API_KEY": "k", "NOVOFON_API_SECRET": "s",
        "YANDEX_CLOUD_FOLDER_ID": "f", "YANDEX_CLOUD_SA_KEY_FILE": "sa.json",
        "YANDEX_S3_BUCKET": "b", "YANDEX_S3_ACCESS_KEY": "ak",
        "YANDEX_S3_SECRET_KEY": "sk",
        "YANDEX_S3_ENDPOINT": "https://storage.yandexcloud.net",
        "PROXYAPI_KEY": "p",
        "BITRIX24_WEBHOOK_URL": "https://t.bitrix24.ru/rest/1/x/",
        "REDIS_URL": "redis://localhost:6379/0",
        "WEBHOOK_SECRET": "test-secret",
        "ADMIN_TOKEN": "test-admin",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def client(test_settings):
    # Mock Redis and arq pool
    with patch("app.main.Redis") as mock_redis_cls, \
         patch("app.main.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.lrange.return_value = []
        mock_redis_cls.from_url.return_value = mock_redis

        mock_arq = AsyncMock()
        mock_pool.return_value = mock_arq

        from app.main import create_app
        app = create_app()
        with TestClient(app) as tc:
            yield tc


class TestWebhookEndpoint:
    def test_valid_webhook(self, client):
        payload = {
            "event": "NOTIFY_RECORD",
            "call_id": "123",
            "caller_id": "79001234567",
            "called_did": "74951234567",
            "duration": "45",
            "call_start": "2026-03-12 10:00:00",
        }
        resp = client.post(
            "/webhook", json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "enqueued"

    def test_invalid_secret_returns_403(self, client):
        resp = client.post(
            "/webhook", json={},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )
        assert resp.status_code == 403

    def test_missing_secret_returns_422(self, client):
        resp = client.post("/webhook", json={})
        assert resp.status_code == 422

    def test_short_call_ignored(self, client):
        payload = {
            "event": "NOTIFY_RECORD",
            "call_id": "123",
            "caller_id": "79001234567",
            "called_did": "74951234567",
            "duration": "5",
            "call_start": "2026-03-12 10:00:00",
        }
        resp = client.post(
            "/webhook", json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            "/webhook",
            content=b"not json",
            headers={
                "X-Webhook-Secret": "test-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAdminEndpoints:
    def test_admin_without_token_returns_422(self, client):
        resp = client.get("/admin/failed")
        assert resp.status_code == 422

    def test_admin_with_wrong_token_returns_401(self, client):
        resp = client.get(
            "/admin/failed",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401

    def test_admin_with_valid_token(self, client):
        resp = client.get(
            "/admin/failed",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert resp.status_code == 200
