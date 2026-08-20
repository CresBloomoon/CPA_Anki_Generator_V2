// Visual-only pre-checks for SectionTable, mirroring what the backend
// actually rejects when a generation job is started -- see:
//   - backend/app/domain/section.py
//     PageRange.__post_init__ (start_page, end_page vs start_page)
//     DeckPath.__post_init__ / DeckPath.from_string (segment normalization)
//     Section.__post_init__ (title)
//   - backend/app/routes/schemas/generation.py
//     SectionInput.start_page (Field(ge=1))
// If those rules change, revisit the functions below. This module never
// blocks submission -- the server-side 422 (Phase4-3) remains the actual
// gate; these are only for showing a warning before the user finds out
// the hard way.

export function getStartPageError(startPage: number | ''): string | null {
  // '' represents "field cleared, still mid-edit" (see SectionTable's
  // start_page onChange) -- Number('') is 0, not NaN, so without this
  // dedicated branch a cleared field would silently become 0 rather than
  // showing as empty. Flagged as an error like any other invalid value.
  if (startPage === '') {
    return '開始ページを入力してください'
  }
  return startPage < 1 ? '開始ページは1以上にしてください' : null
}

export function getEndPageError(
  startPage: number | '',
  endPage: number | null,
): string | null {
  // While start_page is still mid-edit ('') there's nothing meaningful to
  // compare end_page against yet -- defer to getStartPageError for that
  // field instead of cascading a confusing end_page warning from it.
  if (startPage === '') {
    return null
  }
  // end_page is the display (inclusive) value here. The backend converts
  // it to an internal exclusive boundary (+1) before checking
  // internal_end_page >= start_page, so end_page === start_page - 1 is a
  // legitimate zero-page section, not an error -- only end_page <
  // start_page - 1 is actually rejected. See page_range_display.py.
  if (endPage !== null && endPage < startPage - 1) {
    return '終了ページが開始ページより前になっています'
  }
  return null
}

export function getTitleError(title: string): string | null {
  return title.trim() === '' ? '節タイトルを入力してください' : null
}

export function getDeckPathError(deckPath: string): string | null {
  // Mirrors DeckPath.from_string's normalization: strip the whole string,
  // split on "::", strip each segment, drop empties. Only a result of
  // zero segments is actually rejected by the backend -- a merely "messy"
  // path (doubled "::", stray whitespace) gets silently cleaned up there,
  // so it isn't flagged as an error here either.
  const segments = deckPath
    .trim()
    .split('::')
    .map((segment) => segment.trim())
    .filter((segment) => segment !== '')
  return segments.length === 0 ? '出力デッキ名を入力してください' : null
}
