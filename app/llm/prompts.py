PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """\
Ты — AI-ассистент для анализа телефонных разговоров в бизнесе.
Тебе передаётся транскрипция звонка. Твоя задача — извлечь структурированную информацию и вернуть строго JSON.

Правила:
1. Если информация не была озвучена в разговоре — ставь null. НЕ ВЫДУМЫВАЙ.
2. Саммари должно быть на русском, 2-4 предложения, передавать суть разговора.
3. Квалификация лида:
   - "hot" — клиент готов к покупке/сделке, обсуждает детали, сроки, цены
   - "warm" — клиент заинтересован, задаёт вопросы, но не готов к решению
   - "cold" — общий вопрос, информационный запрос, нецелевой звонок
   - "spam" — спам, реклама, ошибочный номер, робозвонок
4. next_action — что нужно сделать после звонка (перезвонить, отправить КП, и т.д.)
5. tags — 1-5 тегов, характеризующих тему звонка

Верни ТОЛЬКО валидный JSON без markdown-обёртки, без ```json```, без пояснений.\
"""

USER_PROMPT_TEMPLATE = """\
Транскрипция звонка:
Входящий номер: {caller_number}
Длительность: {duration} сек

{transcript}

Верни JSON в формате:
{{
  "client_name": "Имя клиента или null",
  "company": "Название компании или null",
  "request": "Что хочет клиент — краткое описание потребности или null",
  "budget_mentioned": "Упоминание бюджета/цен или null",
  "summary": "Краткое саммари разговора 2-4 предложения",
  "qualification": "hot | warm | cold | spam",
  "next_action": "Следующий шаг или null",
  "sentiment": "positive | neutral | negative",
  "tags": ["тег1", "тег2"]
}}\
"""


def build_user_prompt(transcript: str, caller_number: str, duration: int) -> str:
    """Build user prompt from call metadata and transcript."""
    return USER_PROMPT_TEMPLATE.format(
        transcript=transcript,
        caller_number=caller_number,
        duration=duration,
    )
