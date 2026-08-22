from __future__ import annotations

import logging
import time

import anthropic

from app.domain.card import CardContent
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.card_content_mapper import to_card_content_item
from app.repositories.ai.dto import PromptContext
from app.repositories.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# Claude's structured-output mechanism: force a single tool call whose
# input_schema mirrors CardContentItem's fields, so the SDK hands back an
# already-parsed dict via tool_use.input -- unlike Gemini, there is no raw
# JSON string to repair here (see gemini_repository.py's use of
# json_repair.extract_cards_from_json for the contrast).
_RECORD_CARDS_TOOL_NAME = "record_cards"
_CARD_FIELD_NAMES = (
    "TITLE",
    "QUESTION",
    "RONSHO_BODY",
    "KAISETSU_BODY",
    "YO_SURUNI_BODY",
    "RYUI_BODY",
    "RANK_TANTO",
    "RANK_RONBUN",
    "PAGE_CODE",
    "TAGS",
)
_RECORD_CARDS_TOOL = {
    "name": _RECORD_CARDS_TOOL_NAME,
    "description": "生成したAnkiカードの一覧を記録する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "TITLE": {"type": "string"},
                        "QUESTION": {"type": "string"},
                        "RONSHO_BODY": {"type": "string"},
                        "KAISETSU_BODY": {"type": "string"},
                        "YO_SURUNI_BODY": {"type": "string"},
                        "RYUI_BODY": {"type": "string"},
                        "RANK_TANTO": {"type": "string"},
                        "RANK_RONBUN": {"type": "string"},
                        "PAGE_CODE": {"type": "string"},
                        "TAGS": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": list(_CARD_FIELD_NAMES),
                },
            },
        },
        "required": ["cards"],
    },
}


class ClaudeGenerationError(Exception):
    """Raised when Claude generation fails after exhausting all retries."""


class ClaudeAuthenticationError(ClaudeGenerationError):
    """Raised immediately (no retry) when the API key is invalid or unauthorized.

    Mirrors GeminiAuthenticationError's reasoning: a single-key setup with
    no fallback gains nothing from retrying an auth failure.
    """


class ClaudeRepository(AiCardGeneratorRepository):
    def __init__(
        self,
        model_name: str,
        api_key: str,
        prompt_builder: PromptBuilder | None = None,
        client: anthropic.Anthropic | None = None,
        max_retries: int = 3,
        base_delay_seconds: float = 10.0,
        max_tokens: int = 8192,
    ) -> None:
        self._model_name = model_name
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._max_tokens = max_tokens

    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> CardContent:
        prompt = self._prompt_builder.build(section_text, prompt_context)

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            logger.info(
                "Claude API呼び出し試行 %d/%d（model=%s）",
                attempt + 1,
                self._max_retries,
                self._model_name,
            )
            call_started_at = time.monotonic()
            try:
                response = self._client.messages.create(
                    model=self._model_name,
                    max_tokens=self._max_tokens,
                    tools=[_RECORD_CARDS_TOOL],
                    tool_choice={"type": "tool", "name": _RECORD_CARDS_TOOL_NAME},
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(
                    "Claude API呼び出し成功（試行 %d/%d、%.1f秒）",
                    attempt + 1,
                    self._max_retries,
                    time.monotonic() - call_started_at,
                )
                raw_cards = self._extract_raw_cards(response)
                return CardContent(
                    items=tuple(to_card_content_item(card) for card in raw_cards)
                )
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
                raise ClaudeAuthenticationError(
                    f"Claude APIの認証・権限エラーです（リトライしません）: {exc}"
                ) from exc
            except Exception as exc:  # noqa: BLE001 - classified below
                call_elapsed = time.monotonic() - call_started_at
                last_error = exc
                is_last_attempt = attempt >= self._max_retries - 1
                if is_last_attempt:
                    logger.warning(
                        "Claude API呼び出し失敗（試行 %d/%d、%.1f秒、リトライ上限到達）: %s",
                        attempt + 1,
                        self._max_retries,
                        call_elapsed,
                        exc,
                    )
                    break
                delay = (
                    self._base_delay_seconds * (2**attempt) + 5
                    if isinstance(exc, anthropic.RateLimitError)
                    else 5
                )
                logger.warning(
                    "Claude API呼び出し失敗（試行 %d/%d、%.1f秒）: %s。%.0f秒後にリトライします",
                    attempt + 1,
                    self._max_retries,
                    call_elapsed,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise ClaudeGenerationError(
            f"Claude APIによるカード生成に失敗しました: {last_error}"
        ) from last_error

    def _extract_raw_cards(self, response: anthropic.types.Message) -> list[dict]:
        tool_use_block = next(
            block for block in response.content if block.type == "tool_use"
        )
        return tool_use_block.input["cards"]
