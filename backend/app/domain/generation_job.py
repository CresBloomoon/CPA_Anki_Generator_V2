from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class SectionJob:
    section: Section
    status: SectionJobStatus = SectionJobStatus.PENDING
    cards: list[Card] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class GenerationJob:
    job_id: str
    section_jobs: list[SectionJob]
    additional_prompt: str = ""

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if not self.section_jobs:
            raise ValueError("section_jobs must not be empty")

    def mark_running(self, index: int) -> None:
        section_job = self._require_status(index, SectionJobStatus.PENDING, "start")
        section_job.status = SectionJobStatus.RUNNING

    def mark_done(self, index: int, cards: list[Card]) -> None:
        section_job = self._require_status(index, SectionJobStatus.RUNNING, "complete")
        section_job.status = SectionJobStatus.DONE
        section_job.cards = list(cards)

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
