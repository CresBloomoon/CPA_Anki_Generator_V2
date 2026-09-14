from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.card import Card
from app.domain.generation_job import GenerationJob, SectionJobStatus


class SupportsBuildPackage(Protocol):
    """What this usecase needs from an Anki packaging repository.

    Defined as a structural Protocol (rather than importing the concrete
    AnkiPackageRepository class) so this module -- and anything that tests
    it -- has no dependency on genanki.
    """

    def build_package(self, cards: list[Card]) -> bytes: ...


@dataclass(frozen=True)
class AnkiPackageResult:
    apkg_bytes: bytes
    is_complete: bool


class SectionIndexNotFoundError(Exception):
    """Raised when section_index is negative or out of range.

    Checked explicitly rather than relying on list indexing to raise --
    Python lists accept negative indices (e.g. -1 is the last element),
    which would otherwise silently return the wrong section instead of
    erroring (see Phase4-7's dev-log).
    """


class SectionNotDownloadableError(Exception):
    """Raised when the targeted section hasn't reached DONE/PARTIALLY_DONE.

    See Phase5-26's planned UI: the per-row download button is only ever
    enabled for DONE/PARTIALLY_DONE rows, so a well-behaved frontend should
    never trigger this. This guards against a direct URL hit regardless.
    """


class BuildAnkiPackageUsecase:
    def __init__(self, anki_package_repository: SupportsBuildPackage) -> None:
        self._anki_package_repository = anki_package_repository

    def execute(self, job: GenerationJob) -> AnkiPackageResult:
        cards = job.collect_generated_cards()
        apkg_bytes = self._anki_package_repository.build_package(cards)
        return AnkiPackageResult(apkg_bytes=apkg_bytes, is_complete=job.is_complete())

    def execute_for_section(
        self, job: GenerationJob, section_index: int
    ) -> AnkiPackageResult:
        if section_index < 0 or section_index >= len(job.section_jobs):
            raise SectionIndexNotFoundError(
                f"no section at index {section_index!r} for job {job.job_id!r}"
            )

        section_job = job.section_jobs[section_index]
        if section_job.status not in (
            SectionJobStatus.DONE,
            SectionJobStatus.PARTIALLY_DONE,
        ):
            raise SectionNotDownloadableError(
                f"section at index {section_index} is {section_job.status.name}, "
                "not DONE or PARTIALLY_DONE"
            )

        apkg_bytes = self._anki_package_repository.build_package(section_job.cards)
        return AnkiPackageResult(
            apkg_bytes=apkg_bytes,
            is_complete=section_job.status == SectionJobStatus.DONE,
        )
