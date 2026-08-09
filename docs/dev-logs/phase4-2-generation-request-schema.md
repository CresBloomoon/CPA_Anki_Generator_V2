# Phase4-2: 生成リクエストのスキーマ定義

## 何を実装したか

- `backend/app/routes/schemas/generation.py`（新規）
  - `SectionInput`：生成対象として選ばれた1節分の入力契約。`title` / `start_page`（1以上）/ `end_page`（省略可）/ `deck_path`（文字列） / `source_file`。
  - `StartGenerationRequest`：`sections: list[SectionInput]` と `additional_prompt: str = ""` を持つ、生成ジョブ開始APIのリクエストボディ契約。

- `backend/tests/routes/schemas/test_generation.py`（新規）
  - `SectionInput`の正常系、`end_page`省略時に`None`になること、`start_page`が1未満のとき`pydantic.ValidationError`になることを検証。
  - `StartGenerationRequest`の`additional_prompt`デフォルト値（空文字）、複数`SectionInput`の保持を検証。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **`SectionInput`は計画書の初期案（`selected` / `chapter_title` / `min_card_count`込み）から簡略化した**：`chapter_title`・`min_card_count`はADR 0001でドメイン`Section`から既に削除済みのため追随。`selected`（チェックボックス）は含めない設計とした。理由：チェックボックスの状態はUI都合であり、フロントエンドのReact state側でチェック済みの行だけをAPIに送る設計にすることで、ルート層に「selectedを見てフィルタする」ロジックを持たせずに済み、責務がシンプルになるため。
- **`additional_prompt`はスキーマにフィールドのみ用意し、Usecase層への配線は行わなかった**：現状`GenerateCardsForSectionUsecase.execute`・`StartGenerationJobUsecase.execute`はどちらも`additional_prompt`を受け取らず、`PromptContext`は常にデフォルト値（空文字）で組み立てられている。この配線変更はPhase4-2（スキーマ単体）の範囲外と判断し、実際にルートからUsecaseを呼び出す段階であるPhase4-3でまとめて行う方針とした（まーくんとの事前合意事項）。
- **`start_page`のバリデーションのみPydantic側で持たせ、`end_page >= start_page`のようなクロスフィールド検証は追加しなかった**：後者は既にドメイン層の`PageRange.__post_init__`で保証されており、Phase4-3でルートが`SectionInput`から`Section`を組み立てる際に自然に検証される。スキーマ層で重複した検証ロジックを持たせる必要はないと判断した。

## ADR

今回はADRを書くレベルの設計判断はなし（ADR 0001で既に確定した`Section`の項目構成に追随しただけであり、新しいアーキテクチャ上の判断は発生していない）。
