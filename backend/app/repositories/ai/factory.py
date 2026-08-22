from __future__ import annotations

import os

from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.claude_repository import ClaudeRepository
from app.repositories.ai.gemini_repository import GeminiRepository
from app.repositories.settings.settings_repository import AiProviderSettings

# Which .env-provided environment variable holds the API key for each
# provider. Adding a new provider means adding one entry here and one
# branch in create() below.
_PROVIDER_API_KEY_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "claude": "CLAUDE_API_KEY",
}


class UnsupportedProviderError(Exception):
    """Raised when settings.provider does not match any known provider."""


class MissingApiKeyError(Exception):
    """Raised when the selected provider's API key environment variable is unset."""


class AiCardGeneratorFactory:
    def create(self, settings: AiProviderSettings) -> AiCardGeneratorRepository:
        if settings.provider == "gemini":
            api_key = self._require_api_key("gemini")
            return GeminiRepository(model_name=settings.model_name, api_key=api_key)

        if settings.provider == "claude":
            api_key = self._require_api_key("claude")
            return ClaudeRepository(model_name=settings.model_name, api_key=api_key)

        raise UnsupportedProviderError(
            f"未対応のプロバイダーです: {settings.provider!r}"
        )

    def _require_api_key(self, provider: str) -> str:
        env_var_name = _PROVIDER_API_KEY_ENV_VARS[provider]
        api_key = os.environ.get(env_var_name)
        if not api_key:
            raise MissingApiKeyError(
                f"{env_var_name}が設定されていません。.envに設定してください。"
            )
        return api_key
