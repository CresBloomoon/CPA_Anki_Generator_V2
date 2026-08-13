import pytest
from fastapi import HTTPException

from app.dependencies import _build_ai_repository
from app.repositories.settings.settings_repository import AiProviderSettings


class TestBuildAiRepository:
    def test_missing_api_key_raises_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

        with pytest.raises(HTTPException) as exc_info:
            _build_ai_repository(settings)

        assert exc_info.value.status_code == 500

    def test_unsupported_provider_raises_500(self) -> None:
        settings = AiProviderSettings(provider="unknown-provider", model_name="x")

        with pytest.raises(HTTPException) as exc_info:
            _build_ai_repository(settings)

        assert exc_info.value.status_code == 500

    def test_known_provider_with_api_key_set_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-for-test")
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

        repository = _build_ai_repository(settings)

        assert repository is not None
