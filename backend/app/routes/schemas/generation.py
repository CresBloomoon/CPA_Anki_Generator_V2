from __future__ import annotations

from pydantic import BaseModel, Field


class SectionInput(BaseModel):
    title: str
    start_page: int = Field(ge=1)
    end_page: int | None = None
    deck_path: str
    source_file: str


class StartGenerationRequest(BaseModel):
    sections: list[SectionInput]
    additional_prompt: str = ""
    # The deck path prefix used at scan time, stored on the GenerationJob
    # purely for history-list display (see Phase7-2's dev-log). Not sent by
    # the frontend yet -- that wiring is a separate, later Phase -- so this
    # defaults to "" until then.
    root_path: str = ""


class StartGenerationJobResponse(BaseModel):
    job_id: str


# 暫定案：Phase5でフロントエンドと実際に繋ぎ、情報の過不足が見つかった
# 場合はこの形に縛られず変更する前提（まーくんとの合意事項）。
class SectionJobStatusResponse(BaseModel):
    title: str
    status: str
    card_count: int
    error_message: str | None
    elapsed_seconds: int | None


class GenerationJobStatusResponse(BaseModel):
    job_id: str
    is_complete: bool
    section_jobs: list[SectionJobStatusResponse]
