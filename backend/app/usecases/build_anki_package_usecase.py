from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.card import Card
from app.domain.generation_job import GenerationJob


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


class BuildAnkiPackageUsecase:
    def __init__(self, anki_package_repository: SupportsBuildPackage) -> None:
        self._anki_package_repository = anki_package_repository

    def execute(self, job: GenerationJob) -> AnkiPackageResult:
        cards = job.collect_generated_cards()
        apkg_bytes = self._anki_package_repository.build_package(cards)
        return AnkiPackageResult(apkg_bytes=apkg_bytes, is_complete=job.is_complete())
