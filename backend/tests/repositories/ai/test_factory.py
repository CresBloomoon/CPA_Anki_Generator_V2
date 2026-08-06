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
        factory = AiCardGeneratorFactory()
        settings = AiProviderSettings(provider="chatgpt", model_name="gpt-5")

        with pytest.raises(UnsupportedProviderError):
            factory.create(settings)
