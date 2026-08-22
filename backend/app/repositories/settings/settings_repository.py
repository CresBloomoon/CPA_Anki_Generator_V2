from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.repositories.settings.available_models import AVAILABLE_MODELS_BY_PROVIDER

_DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parents[3] / "settings.json"
_DEFAULT_PROVIDER = "gemini"
_DEFAULT_MODEL_NAME = "gemini-2.5-flash"


@dataclass(frozen=True)
class AiProviderSettings:
    provider: str
    model_name: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if self.provider not in AVAILABLE_MODELS_BY_PROVIDER:
            known_providers = sorted(AVAILABLE_MODELS_BY_PROVIDER)
            raise ValueError(
                f"未対応のプロバイダーです: {self.provider!r}"
                f"（対応プロバイダー: {known_providers}）"
            )


class SettingsRepository:
    def __init__(self, settings_path: Path = _DEFAULT_SETTINGS_PATH) -> None:
        self._settings_path = settings_path

    def load(self) -> AiProviderSettings:
        if not self._settings_path.exists():
            return AiProviderSettings(
                provider=_DEFAULT_PROVIDER, model_name=_DEFAULT_MODEL_NAME
            )

        data = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return AiProviderSettings(
            provider=data.get("provider", _DEFAULT_PROVIDER),
            model_name=data.get("model_name", _DEFAULT_MODEL_NAME),
        )

    def save(self, settings: AiProviderSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
