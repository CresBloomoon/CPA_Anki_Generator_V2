from pathlib import Path

import pytest
from fastapi import HTTPException

from app.dependencies import _build_ai_repository, get_ai_card_generator_repository
from app.repositories.settings.settings_repository import (
    AiProviderSettings,
    SettingsRepository,
)


class TestBuildAiRepository:
    def test_missing_api_key_raises_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        settings = AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro")

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

    # There is no "unsupported provider" case to test here anymore:
    # AiProviderSettings.__post_init__ (Phase4-5) now rejects an unknown
    # provider at construction time, so _build_ai_repository() can never
    # actually receive one -- any AiProviderSettings instance that exists
    # is guaranteed to have a known provider. The equivalent real-world
    # failure mode (a stale settings.json on disk still naming an
    # unrecognized provider) is covered below, at the point where that
    # file is actually parsed.


class TestGetAiCardGeneratorRepository:
    def test_settings_file_with_unknown_provider_raises_500(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulates a settings.json left over from before Phase4-5's
        # provider validation existed (or hand-edited), rather than
        # constructing an AiProviderSettings directly -- that path is no
        # longer reachable, see the comment above.
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            '{"provider": "chatgpt", "model_name": "gpt-5.5"}', encoding="utf-8"
        )
        monkeypatch.setattr(
            "app.dependencies.SettingsRepository",
            lambda: SettingsRepository(settings_path=settings_path),
        )

        with pytest.raises(HTTPException) as exc_info:
            get_ai_card_generator_repository()

        assert exc_info.value.status_code == 500
