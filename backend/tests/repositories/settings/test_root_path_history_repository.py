from pathlib import Path

from app.repositories.settings.root_path_history_repository import (
    RootPathHistoryRepository,
)


class TestRootPathHistoryRepository:
    def test_load_returns_empty_list_when_file_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )

        assert repository.load() == []

    def test_add_or_update_adds_new_entry_at_front(self, tmp_path: Path) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )

        repository.add_or_update("公認会計士試験::企業法")
        repository.add_or_update("公認会計士試験::財務会計論")

        paths = [entry.path for entry in repository.load()]
        assert paths == ["公認会計士試験::財務会計論", "公認会計士試験::企業法"]

    def test_add_or_update_moves_existing_entry_to_front_without_duplicating(
        self, tmp_path: Path
    ) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )

        repository.add_or_update("公認会計士試験::企業法")
        repository.add_or_update("公認会計士試験::財務会計論")
        repository.add_or_update("公認会計士試験::企業法")

        paths = [entry.path for entry in repository.load()]
        assert paths == ["公認会計士試験::企業法", "公認会計士試験::財務会計論"]

    def test_add_or_update_caps_at_five_entries_dropping_oldest(
        self, tmp_path: Path
    ) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )

        for index in range(6):
            repository.add_or_update(f"Root::{index}")

        paths = [entry.path for entry in repository.load()]
        assert paths == ["Root::5", "Root::4", "Root::3", "Root::2", "Root::1"]
        assert "Root::0" not in paths

    def test_add_or_update_creates_missing_parent_directories(
        self, tmp_path: Path
    ) -> None:
        nested_path = tmp_path / "nested" / "dir" / "root_path_history.json"
        repository = RootPathHistoryRepository(history_path=nested_path)

        repository.add_or_update("Root")

        assert nested_path.exists()

    def test_entries_have_a_last_used_at_timestamp(self, tmp_path: Path) -> None:
        repository = RootPathHistoryRepository(
            history_path=tmp_path / "root_path_history.json"
        )

        repository.add_or_update("Root")

        entry = repository.load()[0]
        assert entry.last_used_at != ""
