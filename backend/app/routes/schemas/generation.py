from __future__ import annotations

from datetime import datetime

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


# 履歴一覧（GET /generation-jobs）専用の軽量スキーマ。GenerationJobStatus
# Responseとは異なり、セクションごとの詳細（status/card_count/error_message
# 等）は持たない -- 一覧表示に必要な最小限の情報のみ（Phase7-2-4の
# dev-log参照）。
class GenerationJobSummaryResponse(BaseModel):
    job_id: str
    root_path: str
    created_at: datetime
    is_complete: bool
    section_count: int
    # DONE + PARTIALLY_DONE の合計（フロントの既存doneCountと同じ、
    # 「今ダウンロードできる節がいくつあるか」という観点の集計。is_complete
    # がDONEのみを完了とみなすのとは異なる集計軸）。
    done_section_count: int


class GenerationJobListResponse(BaseModel):
    jobs: list[GenerationJobSummaryResponse]
