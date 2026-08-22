import httpx
import pytest
from anthropic import AuthenticationError, PermissionDeniedError, RateLimitError

from app.repositories.ai.claude_repository import (
    ClaudeAuthenticationError,
    ClaudeGenerationError,
    ClaudeRepository,
)
from app.repositories.ai.dto import PromptContext

_GOOD_CARDS_INPUT = {"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}]}


def _fake_response(status_code: int) -> httpx.Response:
    # AuthenticationError/PermissionDeniedError/RateLimitError all require a
    # real httpx.Response to construct (confirmed via
    # tmp_samples/investigate_sdk_exceptions.py run in Docker -- see
    # dev-log for the exact signature).
    return httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", "https://example.invalid/v1/messages"),
    )


class _FakeToolUseBlock:
    def __init__(self, input_data: dict) -> None:
        self.type = "tool_use"
        self.input = input_data


class _FakeMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class _FakeMessages:
    def __init__(self, behavior) -> None:
        self._behavior = behavior
        self.call_count = 0

    def create(self, model, max_tokens, tools, tool_choice, messages):
        self.call_count += 1
        return self._behavior(self.call_count)


class _FakeClient:
    def __init__(self, behavior) -> None:
        self.messages = _FakeMessages(behavior)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.repositories.ai.claude_repository.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    return sleep_calls


class TestGenerateCardsSuccess:
    def test_returns_card_content_on_first_success(
        self, _no_real_sleep: list[float]
    ) -> None:
        client = _FakeClient(
            lambda call_count: _FakeMessage([_FakeToolUseBlock(_GOOD_CARDS_INPUT)])
        )
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert len(result.items) == 1
        assert result.items[0].title == "A"
        assert client.messages.call_count == 1
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
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client
        )

        with pytest.raises(ClaudeAuthenticationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.messages.call_count == 1
        assert _no_real_sleep == []

    def test_permission_denied_also_fails_immediately(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise PermissionDeniedError(
                "forbidden", response=_fake_response(403), body=None
            )

        client = _FakeClient(behavior)
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client
        )

        with pytest.raises(ClaudeAuthenticationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.messages.call_count == 1


class TestRateLimitRetries:
    def test_retries_with_exponential_backoff_then_succeeds(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            if call_count < 3:
                raise RateLimitError(
                    "rate limited", response=_fake_response(429), body=None
                )
            return _FakeMessage([_FakeToolUseBlock(_GOOD_CARDS_INPUT)])

        client = _FakeClient(behavior)
        repository = ClaudeRepository(
            model_name="claude-opus-5",
            api_key="fake",
            client=client,
            base_delay_seconds=10.0,
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert result.items[0].title == "A"
        assert client.messages.call_count == 3
        assert _no_real_sleep == [10.0 * (2**0) + 5, 10.0 * (2**1) + 5]


class TestUnclassifiedErrorRetries:
    def test_exhausts_retries_with_flat_delay_then_raises(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client, max_retries=3
        )

        with pytest.raises(ClaudeGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.messages.call_count == 3
        # No sleep after the final (3rd) attempt -- only between attempts.
        assert _no_real_sleep == [5, 5]

    def test_is_not_misclassified_as_an_authentication_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int):
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client, max_retries=1
        )

        with pytest.raises(ClaudeGenerationError) as exc_info:
            repository.generate_cards("本文", PromptContext(section_title="01節"))
        assert not isinstance(exc_info.value, ClaudeAuthenticationError)


class TestMissingToolUseBlockRetries:
    def test_response_without_tool_use_block_is_retried_like_any_other_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        # Defensive case: tool_choice forces the tool call, but if Claude
        # somehow returns no tool_use block (e.g. a refusal), treat it the
        # same as any other transient failure rather than crashing outright.
        client = _FakeClient(lambda call_count: _FakeMessage([]))
        repository = ClaudeRepository(
            model_name="claude-opus-5", api_key="fake", client=client, max_retries=2
        )

        with pytest.raises(ClaudeGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.messages.call_count == 2
