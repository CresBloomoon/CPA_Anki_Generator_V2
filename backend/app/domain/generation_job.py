from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from app.domain.card import Card
from app.domain.section import Section


class SectionJobStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
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
        section_job = self._require_status(index, SectionJobStatus.RUNNING, "fail")
        section_job.status = SectionJobStatus.FAILED
        section_job.error_message = error_message

    def is_complete(self) -> bool:
        return all(
            section_job.status == SectionJobStatus.DONE
            for section_job in self.section_jobs
        )

    def collect_generated_cards(self) -> list[Card]:
        cards: list[Card] = []
        for section_job in self.section_jobs:
            if section_job.status == SectionJobStatus.DONE:
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
