from app.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, PROMPT_VERSION, build_user_prompt


class TestPrompts:
    def test_system_prompt_is_nonempty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_mentions_json(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_prompt_version_exists(self):
        assert PROMPT_VERSION == "1.0"

    def test_user_prompt_template_has_placeholders(self):
        assert "{caller_number}" in USER_PROMPT_TEMPLATE
        assert "{duration}" in USER_PROMPT_TEMPLATE
        assert "{transcript}" in USER_PROMPT_TEMPLATE

    def test_build_user_prompt(self):
        result = build_user_prompt(
            transcript="Менеджер: Здравствуйте.\nКлиент: Добрый день.",
            caller_number="79001234567",
            duration=30,
        )
        assert "79001234567" in result
        assert "30" in result
        assert "Менеджер: Здравствуйте." in result

    def test_build_user_prompt_expected_json_schema(self):
        result = build_user_prompt(transcript="test", caller_number="79001234567", duration=10)
        assert "client_name" in result
        assert "qualification" in result
        assert "summary" in result
