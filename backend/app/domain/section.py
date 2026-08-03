from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageRange:
    start_page: int
    end_page: int | None = None

    def __post_init__(self) -> None:
        if self.start_page < 1:
            raise ValueError(f"start_page must be >= 1, got {self.start_page}")
        if self.end_page is not None and self.end_page <= self.start_page:
            raise ValueError(
                f"end_page ({self.end_page}) must be greater than "
                f"start_page ({self.start_page})"
            )

    def page_count(self) -> int:
        if self.end_page is None:
            raise ValueError("page_count requires a known end_page")
        return self.end_page - self.start_page


@dataclass(frozen=True)
class DeckPath:
    segments: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("DeckPath must have at least one segment")
        for segment in self.segments:
            if not segment.strip():
                raise ValueError("DeckPath segments must not be empty")
            if "::" in segment:
                raise ValueError(
                    f"DeckPath segment must not contain '::', got {segment!r}"
                )

    @classmethod
    def from_string(cls, path: str) -> DeckPath:
        return cls(tuple(path.split("::")))

    def child(self, segment: str) -> DeckPath:
        return DeckPath((*self.segments, segment))

    def joined(self) -> str:
        return "::".join(self.segments)


@dataclass(frozen=True)
class Section:
    title: str
    chapter_title: str
    page_range: PageRange
    deck_path: DeckPath
    min_card_count: int
    source_file: str

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.chapter_title.strip():
            raise ValueError("chapter_title must not be empty")
        if self.min_card_count < 0:
            raise ValueError(
                f"min_card_count must be >= 0, got {self.min_card_count}"
            )
        if not self.source_file.strip():
            raise ValueError("source_file must not be empty")
