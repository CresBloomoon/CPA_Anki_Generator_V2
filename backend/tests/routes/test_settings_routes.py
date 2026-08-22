from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_settings_repository
from app.main import app
from app.repositories.settings.settings_repository import SettingsRepository


@pytest.fixture()
def client(tmp_path: Path):
    test_settings_repository = SettingsRepository(
        settings_path=tmp_path / "settings.json"
    )
    app.dependency_overrides[get_settings_repository] = lambda: test_settings_repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestGetSettings:
    def test_returns_defaults_when_nothing_saved_yet(self, client: TestClient) -> None:
        response = client.get("/settings")

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "gemini"
        assert body["model_name"] == "gemini-2.5-flash"


class TestUpdateSettings:
    def test_put_then_get_round_trips(self, client: TestClient) -> None:
        put_response = client.put(
            "/settings",
            json={"provider": "claude", "model_name": "claude-opus-5"},
        )

        assert put_response.status_code == 200
        assert put_response.json() == {
            "provider": "claude",
            "model_name": "claude-opus-5",
        }

        get_response = client.get("/settings")
        assert get_response.json() == {
            "provider": "claude",
            "model_name": "claude-opus-5",
        }

    def test_empty_provider_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/settings",
            json={"provider": "", "model_name": "gemini-2.5-pro"},
        )

        assert response.status_code == 422

    def test_empty_model_name_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/settings",
            json={"provider": "gemini", "model_name": ""},
        )

        assert response.status_code == 422

    def test_unknown_provider_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/settings",
            json={"provider": "chatgpt", "model_name": "gpt-5.5"},
        )

        assert response.status_code == 422


class TestGetAvailableModels:
    def test_returns_all_three_providers_with_at_least_one_model_each(
        self, client: TestClient
    ) -> None:
        response = client.get("/settings/available-models")

        assert response.status_code == 200
        models = response.json()["models"]
        assert set(models) == {"gemini", "claude", "openai"}
        for provider_models in models.values():
            assert len(provider_models) > 0
