import json

import httpx
import pytest
from openai import AuthenticationError, PermissionDeniedError, RateLimitError

from app.repositories.ai.chatgpt_repository import (
    ChatGptAuthenticationError,
    ChatGptGenerationError,
    ChatGptRepository,
)
from app.repositories.ai.dto import PromptContext

_GOOD_JSON = json.dumps({"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}]})


def _fake_response(status_code: int) -> httpx.Response:
    # AuthenticationError/PermissionDeniedError/RateLimitError all require a
    # real httpx.Response to construct (confirmed via
    # tmp_samples/investigate_sdk_exceptions.py run in Docker -- see
    # dev-log for the exact signature).
    return httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, behavior) -> None:
        self._behavior = behavior
        self.call_count = 0

    def create(self, model, messages, response_format, temperature):
        self.call_count += 1
        return self._behavior(self.call_count)


class _FakeChat:
    def __init__(self, behavior) -> None:
        self.completions = _FakeCompletions(behavior)


class _FakeClient:
    def __init__(self, behavior) -> None:
        self.chat = _FakeChat(behavior)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.repositories.ai.chatgpt_repository.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    return sleep_calls


class TestGenerateCardsSuccess:
    def test_returns_card_content_on_first_success(
        self, _no_real_sleep: list[float]
    ) -> None:
        client = _FakeClient(lambda call_count: _FakeCompletionResponse(_GOOD_JSON))
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert len(result.items) == 1
        assert result.items[0].title == "A"
        assert client.chat.completions.call_count == 1
        assert _no_real_sleep == []


class TestAuthenticationErrors:
    def test_fails_immediately_without_retrying(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise AuthenticationError(
                "invalid api key", response=_fake_response(401), body=None
            )

        client = _FakeClient(behavior)
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client
        )

        with pytest.raises(ChatGptAuthenticationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.chat.completions.call_count == 1
        assert _no_real_sleep == []

    def test_permission_denied_also_fails_immediately(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise PermissionDeniedError(
                "forbidden", response=_fake_response(403), body=None
            )

        client = _FakeClient(behavior)
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client
        )

        with pytest.raises(ChatGptAuthenticationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.chat.completions.call_count == 1


class TestRateLimitRetries:
    def test_retries_with_exponential_backoff_then_succeeds(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            if call_count < 3:
                raise RateLimitError(
                    "rate limited", response=_fake_response(429), body=None
                )
            return _FakeCompletionResponse(_GOOD_JSON)

        client = _FakeClient(behavior)
        repository = ChatGptRepository(
            model_name="gpt-5.5",
            api_key="fake",
            client=client,
            base_delay_seconds=10.0,
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert result.items[0].title == "A"
        assert client.chat.completions.call_count == 3
        assert _no_real_sleep == [10.0 * (2**0) + 5, 10.0 * (2**1) + 5]


class TestUnclassifiedErrorRetries:
    def test_exhausts_retries_with_flat_delay_then_raises(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client, max_retries=3
        )

        with pytest.raises(ChatGptGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.chat.completions.call_count == 3
        # No sleep after the final (3rd) attempt -- only between attempts.
        assert _no_real_sleep == [5, 5]

    def test_is_not_misclassified_as_an_authentication_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client, max_retries=1
        )

        with pytest.raises(ChatGptGenerationError) as exc_info:
            repository.generate_cards("本文", PromptContext(section_title="01節"))
        assert not isinstance(exc_info.value, ChatGptAuthenticationError)


class TestInvalidJsonRetries:
    def test_unparseable_response_is_retried_like_any_other_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        # Structured Outputs (strict=True) guarantees schema-conformant
        # JSON in practice, but this defends against an unexpected
        # truncated/malformed response the same way Gemini's equivalent
        # test does for its (looser) response_mime_type contract.
        client = _FakeClient(lambda call_count: _FakeCompletionResponse("not json at all"))
        repository = ChatGptRepository(
            model_name="gpt-5.5", api_key="fake", client=client, max_retries=2
        )

        with pytest.raises(ChatGptGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.chat.completions.call_count == 2
