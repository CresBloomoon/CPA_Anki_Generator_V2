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
{anki_instructions}
"""

        if prompt_context.additional_prompt:
            prompt += (
                "\n\n---\n【ユーザーからの今回限定の追加指示】\n"
                "以下の指示も最優先で厳守してください。\n"
                f"{prompt_context.additional_prompt}\n"
            )

        return prompt
