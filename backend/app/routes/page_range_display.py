from __future__ import annotations

# PageRange.end_page (see app/domain/section.py and
# PdfStructureRepository._finalize) is an *exclusive* boundary internally:
# it holds the next section's start_page, which is what extract_text_from_range
# needs to avoid double-extracting the boundary page. Shown to a human as-is,
# it looks like the section's own last page -- which makes two adjacent
# sections appear to share a page (e.g. "終了:62" / "開始:62"). These two
# functions are the single place where the +1/-1 conversion between that
# internal representation and the human-facing "this section's own last
# page" (inclusive) happens, so it is defined and tested in exactly one
# place rather than duplicated at each call site.


def to_display_end_page(internal_end_page: int | None) -> int | None:
    if internal_end_page is None:
        return None
    return internal_end_page - 1


def to_internal_end_page(display_end_page: int | None) -> int | None:
    if display_end_page is None:
        return None
    return display_end_page + 1
