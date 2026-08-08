from __future__ import annotations

from pathlib import Path
from string import Template

from app.repositories.ai.dto import PromptContext

_APP_DIR = Path(__file__).resolve().parents[2]
_PROMPTS_DIR = _APP_DIR / "prompts"
_CARD_TEMPLATES_DIR = _APP_DIR / "card_templates"


class PromptBuilder:
    def __init__(
        self,
        prompts_dir: Path = _PROMPTS_DIR,
        card_templates_dir: Path = _CARD_TEMPLATES_DIR,
    ) -> None:
        self._constitution = (prompts_dir / "project_constitution.md").read_text(
            encoding="utf-8"
        )
        self._anki_generation_template = (
            prompts_dir / "anki_generation.md"
        ).read_text(encoding="utf-8")
        self._front_html = (
            card_templates_dir / "anki_front_card_template.html"
        ).read_text(encoding="utf-8")
        self._back_html = (
            card_templates_dir / "anki_back_card_template.html"
        ).read_text(encoding="utf-8")

    def build(self, section_text: str, prompt_context: PromptContext) -> str:
        anki_instructions = Template(self._anki_generation_template).substitute(
            text_chunk=section_text
        )

        prompt = f"""{self._constitution}

---
【HTMLテンプレート構造】
以下が使用するAnkiカードのHTMLテンプレートです。
上記憲法の指示に従い、指定されたフィールドの役割を理解し、的確なデータを入れてください。

[Front Template]
{self._front_html}

[Back Template]
{self._back_html}

---
{self._build_section_context_line(prompt_context)}
{anki_instructions}
"""

        if prompt_context.additional_prompt:
            prompt += (
                "\n\n---\n【ユーザーからの今回限定の追加指示】\n"
                "以下の指示も最優先で厳守してください。\n"
                f"{prompt_context.additional_prompt}\n"
            )

        return prompt

    def _build_section_context_line(self, prompt_context: PromptContext) -> str:
        # Lets the AI know which section (and, when the section was split
        # into blocks by sub-shredding, which block of how many) it is
        # looking at. Kept out of anki_generation.md itself so that file
        # stays exactly as ported from the legacy prompt contract.
        if prompt_context.block_count is not None and prompt_context.block_count > 1:
            return (
                f"【節の情報】このテキストは「{prompt_context.section_title}」という節のうち、"
                f"{prompt_context.block_count}分割中の{prompt_context.block_index}番目の抜粋です。"
            )
        return f"【節の情報】このテキストは「{prompt_context.section_title}」という節の全文です。"
