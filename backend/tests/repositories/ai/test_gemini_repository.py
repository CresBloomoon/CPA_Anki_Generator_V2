import json

import pytest

from app.repositories.ai.dto import PromptContext
from app.repositories.ai.gemini_repository import (
    GeminiAuthenticationError,
    GeminiGenerationError,
    GeminiRepository,
)

_GOOD_JSON = json.dumps({"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}]})


class _FakeUsageMetadata:
    def __init__(self, prompt_token_count: int, total_token_count: int) -> None:
        self.prompt_token_count = prompt_token_count
        self.total_token_count = total_token_count


class _FakeResponse:
    def __init__(
        self,
        text: str,
        prompt_token_count: int = 16,
        total_token_count: int = 119,
    ) -> None:
        self.text = text
        # Defaults mirror an actual verified gemini-2.5-flash call (see the
        # token-usage-display feature's dev-log): prompt=16,
        # candidates=11, thoughts=92, total=119.
        self.usage_metadata = _FakeUsageMetadata(prompt_token_count, total_token_count)


class _FakeModels:
    def __init__(self, behavior) -> None:
        self._behavior = behavior
        self.call_count = 0

    def generate_content(self, model, contents, config):
        self.call_count += 1
        return self._behavior(self.call_count)


class _FakeClient:
    def __init__(self, behavior) -> None:
        self.models = _FakeModels(behavior)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    # Every test in this file exercises retry/backoff paths; none of them
    # should actually wait in the test suite.
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.repositories.ai.gemini_repository.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    return sleep_calls


class TestGenerateCardsSuccess:
    def test_returns_card_content_on_first_success(
        self, _no_real_sleep: list[float]
    ) -> None:
        client = _FakeClient(lambda call_count: _FakeResponse(_GOOD_JSON))
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert len(result.card_content.items) == 1
        assert result.card_content.items[0].title == "A"
        assert client.models.call_count == 1
        assert _no_real_sleep == []


class TestGenerateCardsTokenUsage:
    def test_output_tokens_is_total_minus_prompt_not_candidates_alone(
        self, _no_real_sleep: list[float]
    ) -> None:
        # Verified against a real gemini-2.5-flash call (see the
        # token-usage-display feature's dev-log): thinking-capable models
        # report a thoughts_token_count that dwarfs candidates_token_count
        # (92 vs 11 tokens in that call) but isn't broken out as its own
        # field on the response -- only folded into total_token_count.
        # Reading candidates_token_count alone as "output" would therefore
        # significantly undercount actual billed usage.
        client = _FakeClient(
            lambda call_count: _FakeResponse(
                _GOOD_JSON, prompt_token_count=16, total_token_count=119
            )
        )
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert result.token_usage.input_tokens == 16
        assert result.token_usage.output_tokens == 103
        assert result.token_usage.total_tokens == 119


class TestAuthenticationErrors:
    def test_fails_immediately_without_retrying(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int) -> _FakeResponse:
            raise RuntimeError("403 PERMISSION_DENIED: API key not valid")

        client = _FakeClient(behavior)
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client
        )

        with pytest.raises(GeminiAuthenticationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.models.call_count == 1
        assert _no_real_sleep == []


class TestRateLimitRetries:
    def test_retries_with_exponential_backoff_then_succeeds(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int) -> _FakeResponse:
            if call_count < 3:
                raise RuntimeError("429 RESOURCE_EXHAUSTED: rate limit hit")
            return _FakeResponse(_GOOD_JSON)

        client = _FakeClient(behavior)
        repository = GeminiRepository(
            model_name="gemini-2.5-pro",
            api_key="fake",
            client=client,
            base_delay_seconds=10.0,
        )

        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )

        assert result.card_content.items[0].title == "A"
        assert client.models.call_count == 3
        assert _no_real_sleep == [10.0 * (2**0) + 5, 10.0 * (2**1) + 5]


class TestUnclassifiedErrorRetries:
    def test_exhausts_retries_with_flat_delay_then_raises(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int) -> _FakeResponse:
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client, max_retries=3
        )

        with pytest.raises(GeminiGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.models.call_count == 3
        # No sleep after the final (3rd) attempt -- only between attempts.
        assert _no_real_sleep == [5, 5]

    def test_is_not_misclassified_as_an_authentication_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        def behavior(call_count: int) -> _FakeResponse:
            raise RuntimeError("connection reset by peer")

        client = _FakeClient(behavior)
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client, max_retries=1
        )

        with pytest.raises(GeminiGenerationError) as exc_info:
            repository.generate_cards("本文", PromptContext(section_title="01節"))
        assert not isinstance(exc_info.value, GeminiAuthenticationError)


class TestJsonRepairFailureRetries:
    def test_unparseable_response_is_retried_like_any_other_error(
        self, _no_real_sleep: list[float]
    ) -> None:
        client = _FakeClient(lambda call_count: _FakeResponse("not json at all"))
        repository = GeminiRepository(
            model_name="gemini-2.5-pro", api_key="fake", client=client, max_retries=2
        )

        with pytest.raises(GeminiGenerationError):
            repository.generate_cards("本文", PromptContext(section_title="01節"))

        assert client.models.call_count == 2
