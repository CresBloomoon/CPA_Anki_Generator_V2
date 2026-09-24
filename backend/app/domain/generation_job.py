from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto

from app.domain.card import Card
from app.domain.section import Section


class SectionJobStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
    # Reached only via mark_failed() when the section already has some
    # cards recorded (block-level progress was persisted -- see
    # GenerateCardsForSectionUsecase's on_block_generated callback) at the
    # moment a later block fails. Distinct from FAILED (zero cards) so
    # partial results are neither silently discarded nor conflated with a
    # section that produced nothing at all.
    PARTIALLY_DONE = auto()
    FAILED = auto()


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass
class SectionJob:
    section: Section
    status: SectionJobStatus = SectionJobStatus.PENDING
    cards: list[Card] = field(default_factory=list)
    error_message: str | None = None
    # Recorded by mark_running()/mark_done()/mark_failed() (see Phase4-6's
    # dev-log). Both None while PENDING.
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Accumulated block-by-block via StartGenerationJobUsecase.run()'s
    # persist_block callback, the same way `cards` is (see the
    # token-usage-display feature's dev-log). Defaults to zero so a
    # still-PENDING section reports no usage.
    token_usage: TokenUsage = field(default_factory=lambda: TokenUsage(0, 0))

    def elapsed_seconds(self) -> int | None:
        if self.started_at is None:
            return None
        # Still RUNNING -- measure against now so the value keeps advancing
        # across polls (see Phase4-6's dev-log) until finished_at freezes it.
        end = self.finished_at or datetime.now(timezone.utc)
        return int((end - self.started_at).total_seconds())


@dataclass
class GenerationJob:
    job_id: str
    section_jobs: list[SectionJob]
    additional_prompt: str = ""
    # Computed by StartGenerationJobUsecase from the PDF content hash and
    # selected sections (see Phase4-9's dev-log) and used to detect
    # duplicate submissions of the same generation request. Defaults to ""
    # so tests that construct GenerationJob directly (not through the
    # usecase) are unaffected.
    idempotency_key: str = ""
    # The deck path prefix the user typed at scan time (see Phase7-2's
    # dev-log). Not used by generation itself -- each Section's deck_path
    # already has it baked in -- this is purely so the history list can
    # show a job-level heading without guessing it back out of individual
    # sections' deck_paths.
    root_path: str = ""
    # Set once at job creation (see StartGenerationJobUsecase.execute()),
    # used to sort the history list newest-first (see Phase7-2-4's
    # dev-log). Distinct from SectionJob.started_at/finished_at, which are
    # per-section. Defaults to "now" so tests that construct GenerationJob
    # directly are unaffected.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if not self.section_jobs:
            raise ValueError("section_jobs must not be empty")

    def mark_running(self, index: int) -> None:
        section_job = self._require_status(index, SectionJobStatus.PENDING, "start")
        section_job.status = SectionJobStatus.RUNNING
        section_job.started_at = datetime.now(timezone.utc)

    def mark_done(self, index: int, cards: list[Card]) -> None:
        section_job = self._require_status(index, SectionJobStatus.RUNNING, "complete")
        section_job.status = SectionJobStatus.DONE
        section_job.cards = list(cards)
        section_job.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, index: int, error_message: str) -> None:
        # Block-level progress (see GenerateCardsForSectionUsecase's
        # on_block_generated callback) may have already appended cards to
        # this section_job before the failure occurred. If so, the section
        # produced *some* usable output and is PARTIALLY_DONE rather than a
        # total FAILED -- the cards must not be silently dropped.
        section_job = self._require_status(index, SectionJobStatus.RUNNING, "fail")
        section_job.status = (
            SectionJobStatus.PARTIALLY_DONE
            if section_job.cards
            else SectionJobStatus.FAILED
        )
        section_job.error_message = error_message
        section_job.finished_at = datetime.now(timezone.utc)

    def is_complete(self) -> bool:
        return all(
            section_job.status == SectionJobStatus.DONE
            for section_job in self.section_jobs
        )

    def collect_generated_cards(self) -> list[Card]:
        cards: list[Card] = []
        for section_job in self.section_jobs:
            if section_job.status in (
                SectionJobStatus.DONE,
                SectionJobStatus.PARTIALLY_DONE,
            ):
                cards.extend(section_job.cards)
        return cards

    def total_token_usage(self) -> TokenUsage:
        # Unlike collect_generated_cards(), this does NOT filter by status:
        # tokens spent on a FAILED section were still actually billed, so
        # excluding them would understate the job's real cost (see the
        # token-usage-display feature's dev-log).
        total = TokenUsage(0, 0)
        for section_job in self.section_jobs:
            total = total + section_job.token_usage
        return total

    def _require_status(
        self, index: int, expected: SectionJobStatus, action: str
    ) -> SectionJob:
        section_job = self.section_jobs[index]
        if section_job.status != expected:
            raise ValueError(
                f"cannot {action} section_job at index {index} from status "
                f"{section_job.status.name} (expected {expected.name})"
            )
        return section_job
