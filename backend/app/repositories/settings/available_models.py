from __future__ import annotations

# Hardcoded per Phase4-5's design decision (案A): a new model release means
# a code change + redeploy here, not a settings-UI-only update. Traded off
# against a free-text model_name input (案B) so the frontend's provider ->
# model two-step <select> (Phase5-12) always shows a valid, known-good
# list instead of relying on the user to type an exact model ID correctly.
#
# The keys of this dict are also the single source of truth for which
# provider strings AiProviderSettings accepts -- see
# settings_repository.py's __post_init__.
AVAILABLE_MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "claude": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
    "openai": ["gpt-5.5", "gpt-5-mini"],
}
