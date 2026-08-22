from app.repositories.settings.available_models import AVAILABLE_MODELS_BY_PROVIDER


class TestAvailableModelsByProvider:
    def test_contains_exactly_the_three_supported_providers(self) -> None:
        assert set(AVAILABLE_MODELS_BY_PROVIDER) == {"gemini", "claude", "openai"}

    def test_each_provider_has_at_least_one_model(self) -> None:
        for models in AVAILABLE_MODELS_BY_PROVIDER.values():
            assert len(models) > 0
