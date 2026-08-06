import json
from pathlib import Path

import pytest

from app.repositories.settings.settings_repository import (
    AiProviderSettings,
    SettingsRepository,
)


class TestAiProviderSettings:
    def test_empty_provider_raises(self) -> None:
        with pytest.raises(ValueError):
            AiProviderSettings(provider="", model_name="gemini-2.5-pro")

    def test_empty_model_name_raises(self) -> None:
        with pytest.raises(ValueError):
            AiProviderSettings(provider="gemini", model_name="")


class TestSettingsRepository:
    def test_load_returns_defaults_when_file_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        repository = SettingsRepository(settings_path=tmp_path / "settings.json")

        settings = repository.load()

        assert settings == AiProviderSettings(
            provider="gemini", model_name="gemini-2.5-pro"
        )

    def test_save_then_load_round_trips(self, tmp_path: Path) -> None:
        repository = SettingsRepository(settings_path=tmp_path / "settings.json")
        saved = AiProviderSettings(provider="claude", model_name="claude-opus-5")

        repository.save(saved)
        loaded = repository.load()

        assert loaded == saved

    def test_save_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        nested_path = tmp_path / "nested" / "dir" / "settings.json"
        repository = SettingsRepository(settings_path=nested_path)

        repository.save(AiProviderSettings(provider="gemini", model_name="gemini-2.5-pro"))

        assert nested_path.exists()

    def test_load_reads_existing_file_written_by_something_else(
        self, tmp_path: Path
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps({"provider": "chatgpt", "model_name": "gpt-5"}),
            encoding="utf-8",
        )
        repository = SettingsRepository(settings_path=settings_path)

        settings = repository.load()

        assert settings == AiProviderSettings(provider="chatgpt", model_name="gpt-5")
