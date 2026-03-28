# Call AI Pipeline

[![CI](https://github.com/alexeymasalykin/call-ai-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/alexeymasalykin/call-ai-pipeline/actions/workflows/ci.yml)

Автоматический пайплайн обработки телефонных звонков: скачивание записи → транскрибация → анализ LLM → отправка в CRM.

## Архитектура

```
Novofon Webhook → FastAPI → Redis Queue → arq Worker → Pipeline
                                                         │
                                          ┌──────────────┼──────────────┐
                                          ▼              ▼              ▼
                                     Скачивание    Транскрибация     Анализ
                                     (Novofon)    (Yandex STT)    (LLM API)
                                          │              │              │
                                          ▼              ▼              ▼
                                    Загрузка S3   Сохранение текста  CRM-обновление
                                                                    (Bitrix24)
                                                                        │
                                                                        ▼
                                                                   QA-оценка
                                                                (smart process)
```

### Этапы пайплайна

1. **Webhook** — получение события завершения звонка от АТС Novofon
2. **Скачивание** — загрузка MP3-записи через Novofon Data API 2.0
3. **Загрузка в S3** — сохранение записи в Yandex Object Storage
4. **Транскрибация** — распознавание речи через Yandex SpeechKit (асинхронное)
5. **Анализ** — LLM извлекает резюме, квалификацию, продукт и оценки качества разговора
6. **CRM** — создание/обновление компании, сделки и комментария в таймлайне Bitrix24
7. **QA** — создание элемента оценки качества в смарт-процессе Bitrix24 с оценками по этапам

### Ключевые возможности

- **Идемпотентная обработка** — дедупликация через Redis-ключи (TTL 7 дней)
- **Retry с backoff** — транзиентные ошибки повторяются через arq, постоянные → DLQ
- **Отложенная привязка сделки** — если сделки нет в момент обработки, повторная попытка по расписанию
- **Rate limiting** — встроенный лимитер Bitrix24 API с обработкой HTTP 429
- **Структурированные логи** — JSON через structlog
- **Graceful shutdown** — все HTTP-клиенты корректно закрываются по SIGTERM
- **Дашборд** — аналитическая панель на Vue 3 + Chart.js с рейтингом менеджеров и статистикой звонков

## Дашборд

Аналитическая панель на Vue 3 + Chart.js.

![Статистика обработки и воронка звонков](screenshots/dashboard-stats.png)

<details>
<summary>Ещё скриншоты</summary>

![Тепловая карта оценок и сводка по менеджерам](screenshots/dashboard-heatmap.png)

![Радар-чарт и распределение оценок](screenshots/dashboard-qa.png)

![Список звонков с результатами LLM-анализа](screenshots/dashboard-calls.png)

</details>

## Стек технологий

- **API:** FastAPI + uvicorn
- **Воркер:** arq (асинхронная очередь задач на Redis)
- **STT:** Yandex SpeechKit (асинхронное пакетное распознавание)
- **LLM:** OpenAI-совместимый API (через ProxyAPI)
- **CRM:** Bitrix24 REST API
- **АТС:** Novofon Data API 2.0
- **Хранилище:** Yandex Object Storage (S3-совместимое)
- **Очередь/кэш:** Redis 7
- **Дашборд:** Vue 3, Chart.js, Vite
- **Инфра:** Docker, Docker Compose, multi-stage builds

## Быстрый старт

```bash
# 1. Клонировать и настроить
cp .env.example .env
# Заполнить все обязательные переменные в .env

# 2. Положить ключ сервисного аккаунта Yandex Cloud
# Скачать из консоли IAM → сохранить как service_account_key.json

# 3. Запустить
docker-compose up -d

# 4. Проверить
curl http://localhost:8010/health
```

## Структура проекта

```
app/
├── main.py            # FastAPI: webhook, health, admin, stats endpoints
├── worker.py          # arq worker: обработчики задач, жизненный цикл
├── pipeline.py        # Оркестратор основного пайплайна
├── config.py          # Pydantic settings (конфигурация через env)
├── stats.py           # Дневная статистика звонков в Redis
├── exceptions.py      # Иерархия исключений
├── crm/
│   └── bitrix24.py    # Клиент Bitrix24 REST API
├── llm/
│   ├── base.py        # Абстрактный интерфейс LLM-клиента
│   └── proxyapi_client.py  # OpenAI-совместимый LLM-клиент
├── models/
│   ├── schemas.py     # Модели данных (CallData, LLMResponse и др.)
│   └── qa_schemas.py  # Модели QA-оценки
├── novofon/
│   ├── api.py         # Клиент Novofon Data API 2.0
│   └── webhook.py     # Парсер webhook-payload
└── stt/
    ├── s3.py          # S3-совместимый клиент хранилища
    └── speechkit.py   # Yandex SpeechKit асинхронное распознавание

dashboard/             # Аналитический дашборд на Vue 3
scripts/               # Утилиты (backfill статистики)
tests/                 # Тесты (pytest)
```

## API Endpoints

| Метод | Путь | Авторизация | Описание |
|-------|------|-------------|----------|
| GET | `/health` | — | Health check (пинг Redis) |
| POST | `/webhook` | `?secret=` | Приём webhook от Novofon |
| GET | `/api/stats?days=30` | — | Статистика звонков (по дням + итого) |
| GET | `/admin/failed` | Bearer token | Список записей из DLQ |
| POST | `/admin/retry/{call_id}` | Bearer token | Повторная обработка звонка из DLQ |

## Лицензия

MIT
