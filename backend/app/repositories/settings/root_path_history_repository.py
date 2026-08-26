from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "root_path_history.json"
)
_MAX_ENTRIES = 5


@dataclass(frozen=True)
class RootPathHistoryEntry:
    path: str
    # ISO 8601 (UTC), informational only for display -- list order (not
    # this timestamp) is what determines MRU order, so nothing here ever
    # parses it back into a datetime.
    last_used_at: str


class RootPathHistoryRepository:
    def __init__(self, history_path: Path = _DEFAULT_HISTORY_PATH) -> None:
        self._history_path = history_path

    def load(self) -> list[RootPathHistoryEntry]:
        if not self._history_path.exists():
            return []

        data = json.loads(self._history_path.read_text(encoding="utf-8"))
        return [
            RootPathHistoryEntry(
                path=entry["path"], last_used_at=entry["last_used_at"]
            )
            for entry in data.get("entries", [])
        ]

    def add_or_update(self, root_path: str) -> None:
        # MRU: drop any existing entry for this path, then reinsert it at
        # the front with a fresh timestamp -- so re-using a path moves it
        # to the top instead of leaving a stale duplicate further down.
        entries = [entry for entry in self.load() if entry.path != root_path]
        entries.insert(
            0,
            RootPathHistoryEntry(
                path=root_path,
                last_used_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._save(entries[:_MAX_ENTRIES])

    def _save(self, entries: list[RootPathHistoryEntry]) -> None:
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        self._history_path.write_text(
            json.dumps(
                {"entries": [asdict(entry) for entry in entries]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
