from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types as genai_types

from app.domain.card import CardContent, CardContentItem
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.dto import PromptContext
from app.repositories.ai.json_repair import extract_cards_from_json
from app.repositories.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

_RATE_LIMIT_MARKERS = ("429", "RESOURCE_EXHAUSTED", "Quota exceeded")
_AUTH_ERROR_MARKERS = (
    "401",
    "403",
    "PERMISSION_DENIED",
    "UNAUTHENTICATED",
    "API_KEY_INVALID",
)


class GeminiGenerationError(Exception):
    """Raised when Gemini generation fails after exhausting all retries."""


class GeminiAuthenticationError(GeminiGenerationError):
    """Raised immediately (no retry) when the API key is invalid or unauthorized.

    Unlike rate limits or transient errors, retrying will never fix an
    invalid/unauthorized API key. The legacy implementation didn't
    distinguish this because it could fall back to rotating API keys; V2
    uses a single key with no fallback, so retrying here would only waste
    time before failing with the same error anyway.
    """


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _RATE_LIMIT_MARKERS)


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _AUTH_ERROR_MARKERS)


def _to_card_content_item(raw_card: dict) -> CardContentItem:
    tags = raw_card.get("TAGS", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    return CardContentItem(
        title=raw_card.get("TITLE", ""),
        question=raw_card.get("QUESTION", ""),
        ronsho_body=raw_card.get("RONSHO_BODY", ""),
        kaisetsu_body=raw_card.get("KAISETSU_BODY", ""),
        yo_suruni_body=raw_card.get("YO_SURUNI_BODY", ""),
        ryui_body=raw_card.get("RYUI_BODY", ""),
        rank_tanto=raw_card.get("RANK_TANTO", ""),
        rank_ronbun=raw_card.get("RANK_RONBUN", ""),
        page_code=raw_card.get("PAGE_CODE", ""),
        tags=tuple(tags),
    )


class GeminiRepository(AiCardGeneratorRepository):
    def __init__(
        self,
        model_name: str,
        api_key: str,
        prompt_builder: PromptBuilder | None = None,
        client: genai.Client | None = None,
        max_retries: int = 3,
        base_delay_seconds: float = 10.0,
    ) -> None:
        self._model_name = model_name
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._client = client or genai.Client(api_key=api_key)
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds

    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> CardContent:
        prompt = self._prompt_builder.build(section_text, prompt_context)

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            logger.info(
                "Gemini API呼び出し試行 %d/%d（model=%s）",
                attempt + 1,
                self._max_retries,
                self._model_name,
            )
            call_started_at = time.monotonic()
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                    ),
                )
                logger.info(
                    "Gemini API呼び出し成功（試行 %d/%d、%.1f秒）",
                    attempt + 1,
                    self._max_retries,
                    time.monotonic() - call_started_at,
                )
                raw_cards = extract_cards_from_json(response.text)
                return CardContent(
                    items=tuple(_to_card_content_item(card) for card in raw_cards)
                )
            except Exception as exc:  # noqa: BLE001 - classified below
                call_elapsed = time.monotonic() - call_started_at
                if _is_auth_error(exc):
                    raise GeminiAuthenticationError(
                        f"Gemini APIの認証・権限エラーです（リトライしません）: {exc}"
                    ) from exc

                last_error = exc
                is_last_attempt = attempt >= self._max_retries - 1
                if is_last_attempt:
                    logger.warning(
                        "Gemini API呼び出し失敗（試行 %d/%d、%.1f秒、リトライ上限到達）: %s",
                        attempt + 1,
                        self._max_retries,
                        call_elapsed,
                        exc,
                    )
                    break
                delay = (
                    self._base_delay_seconds * (2**attempt) + 5
                    if _is_rate_limit_error(exc)
                    else 5
                )
                logger.warning(
                    "Gemini API呼び出し失敗（試行 %d/%d、%.1f秒）: %s。%.0f秒後にリトライします",
                    attempt + 1,
                    self._max_retries,
                    call_elapsed,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise GeminiGenerationError(
            f"Gemini APIによるカード生成に失敗しました: {last_error}"
        ) from last_error
