from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptContext:
    section_title: str
    additional_prompt: str = ""
    block_index: int | None = None
    block_count: int | None = None

    def __post_init__(self) -> None:
        if not self.section_title.strip():
            raise ValueError("section_title must not be empty")
        if (self.block_index is None) != (self.block_count is None):
            raise ValueError("block_index and block_count must be set together")
        if self.block_count is not None and self.block_count < 1:
            raise ValueError(f"block_count must be >= 1, got {self.block_count}")
        if self.block_index is not None and not (
            1 <= self.block_index <= self.block_count  # type: ignore[operator]
        ):
            raise ValueError(
                f"block_index ({self.block_index}) must be between 1 and "
                f"block_count ({self.block_count})"
            )
