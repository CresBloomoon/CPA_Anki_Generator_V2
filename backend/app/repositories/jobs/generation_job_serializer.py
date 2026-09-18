from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import GenerationJob, SectionJob, SectionJobStatus
from app.domain.section import DeckPath, PageRange, Section

# Converts the GenerationJob object graph to/from plain JSON-safe dicts for
# GenerationJobRepository. Kept separate from the domain module (rather than
# adding to_dict/from_dict methods onto the dataclasses themselves) so the
# domain layer stays free of persistence-format concerns -- this module is
# the only place that knows what the on-disk JSON looks like.
#
# dataclasses.asdict() can't be used as-is: SectionJobStatus is an Enum
# (needs .name / SectionJobStatus[name]), started_at/finished_at are
# datetimes (need .isoformat() / datetime.fromisoformat()), and
# DeckPath.segments is a tuple (needs list() / tuple() at the JSON
# boundary). Every field is therefore mapped explicitly.


def job_to_dict(job: GenerationJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "additional_prompt": job.additional_prompt,
        "idempotency_key": job.idempotency_key,
        "root_path": job.root_path,
        "created_at": job.created_at.isoformat(),
        "section_jobs": [_section_job_to_dict(sj) for sj in job.section_jobs],
    }


def job_from_dict(data: dict[str, Any]) -> GenerationJob:
    return GenerationJob(
        job_id=data["job_id"],
        section_jobs=[_section_job_from_dict(sj) for sj in data["section_jobs"]],
        additional_prompt=data["additional_prompt"],
        idempotency_key=data["idempotency_key"],
        root_path=data["root_path"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )


def _section_job_to_dict(section_job: SectionJob) -> dict[str, Any]:
    return {
        "section": _section_to_dict(section_job.section),
        "status": section_job.status.name,
        "cards": [_card_to_dict(card) for card in section_job.cards],
        "error_message": section_job.error_message,
        "started_at": _datetime_to_iso(section_job.started_at),
        "finished_at": _datetime_to_iso(section_job.finished_at),
    }


def _section_job_from_dict(data: dict[str, Any]) -> SectionJob:
    return SectionJob(
        section=_section_from_dict(data["section"]),
        status=SectionJobStatus[data["status"]],
        cards=[_card_from_dict(card) for card in data["cards"]],
        error_message=data["error_message"],
        started_at=_iso_to_datetime(data["started_at"]),
        finished_at=_iso_to_datetime(data["finished_at"]),
    )


def _section_to_dict(section: Section) -> dict[str, Any]:
    return {
        "title": section.title,
        "start_page": section.page_range.start_page,
        "end_page": section.page_range.end_page,
        "deck_path": list(section.deck_path.segments),
        "source_file": section.source_file,
    }


def _section_from_dict(data: dict[str, Any]) -> Section:
    return Section(
        title=data["title"],
        page_range=PageRange(start_page=data["start_page"], end_page=data["end_page"]),
        deck_path=DeckPath(tuple(data["deck_path"])),
        source_file=data["source_file"],
    )


def _card_to_dict(card: Card) -> dict[str, Any]:
    return {
        "section_title": card.section_title,
        "deck_path": list(card.deck_path.segments),
        "content": _card_content_item_to_dict(card.content),
    }


def _card_from_dict(data: dict[str, Any]) -> Card:
    return Card(
        content=_card_content_item_from_dict(data["content"]),
        section_title=data["section_title"],
        deck_path=DeckPath(tuple(data["deck_path"])),
    )


def _card_content_item_to_dict(item: CardContentItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "question": item.question,
        "ronsho_body": item.ronsho_body,
        "kaisetsu_body": item.kaisetsu_body,
        "yo_suruni_body": item.yo_suruni_body,
        "ryui_body": item.ryui_body,
        "rank_tanto": item.rank_tanto,
        "rank_ronbun": item.rank_ronbun,
        "page_code": item.page_code,
        "tags": list(item.tags),
    }


def _card_content_item_from_dict(data: dict[str, Any]) -> CardContentItem:
    return CardContentItem(
        title=data["title"],
        question=data["question"],
        ronsho_body=data["ronsho_body"],
        kaisetsu_body=data["kaisetsu_body"],
        yo_suruni_body=data["yo_suruni_body"],
        ryui_body=data["ryui_body"],
        rank_tanto=data["rank_tanto"],
        rank_ronbun=data["rank_ronbun"],
        page_code=data["page_code"],
        tags=tuple(data["tags"]),
    )


def _datetime_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _iso_to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
