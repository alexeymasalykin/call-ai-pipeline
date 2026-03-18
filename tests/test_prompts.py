from app.llm.prompts import SYSTEM_PROMPT, PROMPT_VERSION, build_user_prompt


class TestPrompts:
    def test_system_prompt_is_nonempty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_mentions_json(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_prompt_version_is_v2(self):
        assert PROMPT_VERSION == "2.0"

    def test_system_prompt_has_direction_qualifications(self):
        assert "ИСХОДЯЩИХ" in SYSTEM_PROMPT
        assert "ВХОДЯЩИХ" in SYSTEM_PROMPT
        assert "rejected" in SYSTEM_PROMPT

    def test_build_user_prompt_incoming(self):
        result = build_user_prompt(
            transcript="Спикер 1: Здравствуйте.\nСпикер 2: Добрый день.",
            phone_number="79001234567",
            duration=30,
            direction="incoming",
        )
        assert "79001234567" in result
        assert "30" in result
        assert "Входящий" in result
        assert "Менеджер: Здравствуйте." in result
        assert "Клиент: Добрый день." in result
        assert "Спикер" not in result

    def test_build_user_prompt_outgoing(self):
        result = build_user_prompt(
            transcript="Спикер 1: Алло.\nСпикер 2: Здравствуйте, меня зовут Софья.",
            phone_number="79851234567",
            duration=180,
            direction="outgoing",
        )
        assert "Исходящий" in result
        assert "Клиент: Алло." in result
        assert "Менеджер: Здравствуйте, меня зовут Софья." in result
        assert "Спикер" not in result

    def test_build_user_prompt_has_new_fields(self):
        result = build_user_prompt(
            transcript="test", phone_number="79001234567",
            duration=10, direction="incoming",
        )
        assert "client_name" in result
        assert "client_request" in result
        assert "our_offer" in result
        assert "objections" in result
        assert "pain_points" in result
        assert "decision_maker" in result
        assert "manager_name" in result
        assert "call_direction" in result
        assert "qualification" in result
        assert "summary" in result
