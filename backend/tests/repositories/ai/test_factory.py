import pytest

from app.repositories.ai.factory import (
    AiCardGeneratorFactory,
    MissingApiKeyError,
    UnsupportedProviderError,
)
from app.repositories.ai.gemini_repository import GeminiRepository
from app.repositories.settings.settings_repository import AiProviderSettings


class TestAiCardGeneratorFactory:
    def test_create_dispatches_gemini_settings_to_gemini_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        class _FakeGeminiRepository:
            def __init__(self, model_name: str, api_key: str) -> None:
                captured["model_name"] = model_name
                captured["api_key"] = api_key

        monkeypatch.setattr(
            "app.repositories.ai.factory.GeminiRepository", _FakeGeminiRepository
        )
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

        repository = factory.create(settings)

        assert isinstance(repository, _FakeGeminiRepository)
        assert captured == {"model_name": "gemini-2.5-pro", "api_key": "test-key-123"}

    def test_create_returns_a_real_gemini_repository_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

        repository = factory.create(settings)

        assert isinstance(repository, GeminiRepository)

    def test_missing_api_key_env_var_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

        with pytest.raises(MissingApiKeyError):
            factory.create(settings)

    def test_unsupported_provider_raises(self) -> None:
        # "chatgpt" (the consumer product name) is deliberately not the
        # internal provider identifier -- only "openai" is recognized (see
        # factory.py's _PROVIDER_API_KEY_ENV_VARS / OPENAI_API_KEY).
        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="chatgpt", model_name="gpt-5.5")

        with pytest.raises(UnsupportedProviderError):
            factory.create(settings)

    def test_create_dispatches_claude_settings_to_claude_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        class _FakeClaudeRepository:
            def __init__(self, model_name: str, api_key: str) -> None:
                captured["model_name"] = model_name
                captured["api_key"] = api_key

        monkeypatch.setattr(
            "app.repositories.ai.factory.ClaudeRepository", _FakeClaudeRepository
        )
        monkeypatch.setenv("CLAUDE_API_KEY", "test-key-456")

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="claude", model_name="claude-opus-5")

        repository = factory.create(settings)

        assert isinstance(repository, _FakeClaudeRepository)
        assert captured == {"model_name": "claude-opus-5", "api_key": "test-key-456"}

    def test_missing_claude_api_key_env_var_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="claude", model_name="claude-opus-5")

        with pytest.raises(MissingApiKeyError):
            factory.create(settings)

    def test_create_dispatches_openai_settings_to_chatgpt_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        class _FakeChatGptRepository:
            def __init__(self, model_name: str, api_key: str) -> None:
                captured["model_name"] = model_name
                captured["api_key"] = api_key

        monkeypatch.setattr(
            "app.repositories.ai.factory.ChatGptRepository", _FakeChatGptRepository
        )
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-789")

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="openai", model_name="gpt-5.5")

        repository = factory.create(settings)

        assert isinstance(repository, _FakeChatGptRepository)
        assert captured == {"model_name": "gpt-5.5", "api_key": "test-key-789"}

    def test_missing_openai_api_key_env_var_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="openai", model_name="gpt-5.5")

        with pytest.raises(MissingApiKeyError):
            factory.create(settings)
