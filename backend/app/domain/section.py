from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageRange:
    start_page: int
    end_page: int | None = None

    def __post_init__(self) -> None:
        if self.start_page < 1:
            raise ValueError(f"start_page must be >= 1, got {self.start_page}")
        # A zero-length range (end_page == start_page) is allowed: a TOC
        # entry can legitimately share its start page with the very next
        # entry (e.g. a part heading and its first chapter on the same
        # page), in which case it has no page range of its own. Only a
        # genuinely negative-length range is rejected.
        if self.end_page is not None and self.end_page < self.start_page:
            raise ValueError(
                f"end_page ({self.end_page}) must not be less than "
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
        # The only entry point for raw, human-typed text (a root path
        # input, or an edited deck_path cell), as opposed to __post_init__
        # and child(), which enforce the strict invariant for paths already
        # assembled from known-good pieces. Trailing/leading/doubled "::"
        # and stray whitespace are common typing accidents, not meaningful
        # input, so they are normalized away here before the strict
        # constructor runs. If nothing survives (e.g. "", "::", "   "),
        # __post_init__'s "at least one segment" check raises as usual.
        segments = tuple(
            segment.strip()
            for segment in path.strip().split("::")
            if segment.strip()
        )
        return cls(segments)

    def child(self, segment: str) -> DeckPath:
        return DeckPath((*self.segments, segment))

    def joined(self) -> str:
        return "::".join(self.segments)


@dataclass(frozen=True)
class Section:
    title: str
    page_range: PageRange
    deck_path: DeckPath
    source_file: str

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.source_file.strip():
            raise ValueError("source_file must not be empty")
