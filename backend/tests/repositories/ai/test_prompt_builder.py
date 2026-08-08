from app.repositories.ai.dto import PromptContext
from app.repositories.ai.prompt_builder import PromptBuilder


class TestPromptBuilder:
    def test_build_includes_all_components_in_order(self) -> None:
        builder = PromptBuilder()
        context = PromptContext(section_title="01節 会計の意義")

        prompt = builder.build("これは節の本文テキストです。", context)

        constitution_index = prompt.find("CPA-Anki-Factory")
        front_index = prompt.find("CPA Anki Front Card Template")
        back_index = prompt.find("CPA Anki Back Card Template")
        text_chunk_index = prompt.find("これは節の本文テキストです。")
        output_format_index = prompt.find("必須出力フォーマット")

        assert -1 not in (
            constitution_index,
            front_index,
            back_index,
            text_chunk_index,
            output_format_index,
        )
        assert (
            constitution_index
            < front_index
            < back_index
            < output_format_index
            < text_chunk_index
        )

    def test_additional_prompt_is_appended_when_present(self) -> None:
        builder = PromptBuilder()
        context = PromptContext(
            section_title="01節 会計の意義",
            additional_prompt="この節は簡潔にまとめてください。",
        )

        prompt = builder.build("本文", context)

        assert "ユーザーからの今回限定の追加指示" in prompt
        assert "この節は簡潔にまとめてください。" in prompt

    def test_additional_prompt_is_omitted_when_empty(self) -> None:
        builder = PromptBuilder()
        context = PromptContext(section_title="01節 会計の意義")

        prompt = builder.build("本文", context)

        assert "ユーザーからの今回限定の追加指示" not in prompt

    def test_section_title_is_included_when_not_split_into_blocks(self) -> None:
        builder = PromptBuilder()
        context = PromptContext(section_title="01節 会計の意義")

        prompt = builder.build("本文", context)

        assert "「01節 会計の意義」という節の全文です" in prompt

    def test_block_position_is_included_when_split_into_blocks(self) -> None:
        builder = PromptBuilder()
        context = PromptContext(
            section_title="01節 会計の意義", block_index=2, block_count=3
        )

        prompt = builder.build("本文", context)

        assert "「01節 会計の意義」という節のうち、3分割中の2番目の抜粋です" in prompt
