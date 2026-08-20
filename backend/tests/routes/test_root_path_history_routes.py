from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_root_path_history_repository
from app.main import app
from app.repositories.settings.root_path_history_repository import (
    RootPathHistoryRepository,
)


@pytest.fixture()
def client(tmp_path: Path):
    test_repository = RootPathHistoryRepository(
        history_path=tmp_path / "root_path_history.json"
    )
    app.dependency_overrides[get_root_path_history_repository] = (
        lambda: test_repository
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestGetRootPathHistory:
    def test_returns_empty_list_when_nothing_saved_yet(
        self, client: TestClient
    ) -> None:
        response = client.get("/root-path-history")

        assert response.status_code == 200
        assert response.json() == {"entries": []}

    def test_returns_saved_entries_most_recent_first(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )
        repository.add_or_update("公認会計士試験::企業法")
        repository.add_or_update("公認会計士試験::財務会計論")

        response = client.get("/root-path-history")

        assert response.status_code == 200
        paths = [entry["path"] for entry in response.json()["entries"]]
        assert paths == ["公認会計士試験::財務会計論", "公認会計士試験::企業法"]
