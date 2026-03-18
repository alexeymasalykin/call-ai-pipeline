import os
import pytest


class TestSettings:
    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("NOVOFON_LOGIN", "test_key")
        monkeypatch.setenv("NOVOFON_PASSWORD", "test_secret")
        monkeypatch.setenv("YANDEX_CLOUD_FOLDER_ID", "folder123")
        monkeypatch.setenv("YANDEX_CLOUD_SA_KEY_FILE", "sa.json")
        monkeypatch.setenv("YANDEX_S3_BUCKET", "test-bucket")
        monkeypatch.setenv("YANDEX_S3_ACCESS_KEY", "s3key")
        monkeypatch.setenv("YANDEX_S3_SECRET_KEY", "s3secret")
        monkeypatch.setenv("YANDEX_S3_ENDPOINT", "https://storage.yandexcloud.net")
        monkeypatch.setenv("PROXYAPI_KEY", "proxy_key")
        monkeypatch.setenv("BITRIX24_WEBHOOK_URL", "https://test.bitrix24.ru/rest/1/abc/")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("WEBHOOK_SECRET", "secret123")
        monkeypatch.setenv("ADMIN_TOKEN", "admin123")
        from app.config import Settings
        s = Settings()
        assert s.NOVOFON_LOGIN == "test_key"
        assert s.LLM_MODEL == "gpt-4o-mini"
        assert s.MIN_CALL_DURATION == 15
        assert s.LOG_LEVEL == "INFO"

    def test_missing_required_var_raises(self, monkeypatch):
        for key in ["NOVOFON_LOGIN", "NOVOFON_PASSWORD", "YANDEX_CLOUD_FOLDER_ID",
                     "YANDEX_CLOUD_SA_KEY_FILE", "YANDEX_S3_BUCKET", "YANDEX_S3_ACCESS_KEY",
                     "YANDEX_S3_SECRET_KEY", "PROXYAPI_KEY", "BITRIX24_WEBHOOK_URL",
                     "WEBHOOK_SECRET", "ADMIN_TOKEN"]:
            monkeypatch.delenv(key, raising=False)
        from app.config import Settings
        with pytest.raises(Exception):
            Settings(_env_file=None)

    def test_custom_llm_model(self, monkeypatch):
        monkeypatch.setenv("NOVOFON_LOGIN", "k")
        monkeypatch.setenv("NOVOFON_PASSWORD", "s")
        monkeypatch.setenv("YANDEX_CLOUD_FOLDER_ID", "f")
        monkeypatch.setenv("YANDEX_CLOUD_SA_KEY_FILE", "sa.json")
        monkeypatch.setenv("YANDEX_S3_BUCKET", "b")
        monkeypatch.setenv("YANDEX_S3_ACCESS_KEY", "ak")
        monkeypatch.setenv("YANDEX_S3_SECRET_KEY", "sk")
        monkeypatch.setenv("YANDEX_S3_ENDPOINT", "https://storage.yandexcloud.net")
        monkeypatch.setenv("PROXYAPI_KEY", "p")
        monkeypatch.setenv("BITRIX24_WEBHOOK_URL", "https://t.bitrix24.ru/rest/1/x/")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("WEBHOOK_SECRET", "sec")
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        from app.config import Settings
        s = Settings()
        assert s.LLM_MODEL == "gpt-4o"
