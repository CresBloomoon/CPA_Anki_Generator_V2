# Phase5-15: インタラクティブ要素のサイズ拡大+共通スタイル定数の導入

## 何を実装したか

- `frontend/src/styles.ts`（新規）
  - ボタン・入力欄・チェックボックスの「サイズ・余白・角丸・disabled時の見た目」を集約した共有クラス文字列定数：`primaryButtonClasses`（主要ボタン：スキャン開始／生成開始／ダウンロード）、`secondaryButtonClasses`（副次ボタン：行を追加／リセット）、`iconButtonClasses`（削除アイコンボタン）、`textInputClasses`（単体のテキスト入力欄）、`tableFieldClasses`（テーブルセル内の入力欄・セレクト）、`checkboxClasses`（チェックボックス）。
  - 色（`bg-blue-600`／`bg-green-600`等）や幅指定（`w-48`等）は用途ごとに意味が異なる（青＝主要操作、緑＝ダウンロード完了、等）ため各呼び出し側に残し、サイズ関連のみをここに集約した。

- `frontend/src/components/UploadPanel.tsx`（修正）：スキャン開始ボタン、ルートパス入力欄に適用。
- `frontend/src/components/SectionTable.tsx`（修正）：行チェックボックス、全選択チェックボックス（Phase5-14で追加）、節タイトル／開始ページ／終了ページ／出力デッキ名の入力欄、ソースファイルselect、削除アイコンボタン、「行を追加」ボタンに適用。
- `frontend/src/components/GenerationProgress.tsx`（修正）：生成開始ボタンに適用。
- `frontend/src/components/DownloadButton.tsx`（修正）：ダウンロードボタンに適用。
- `frontend/src/App.tsx`（修正）：リセットボタンに適用。

フォントサイズ（`text-sm`等）自体は変更していない。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **共通スタイル定数を新設した**：まーくんの明示的な要望による。今後もサイズ調整が発生しうるため、各コンポーネントに直接Tailwindクラスを書く方式ではなく、ソースコードレベルで一箇所に集約されている方が保守しやすいと判断された。
- **色・幅指定は共通定数に含めず各呼び出し側に残した**：色は用途ごとに意味が異なり（青＝主要操作、緑＝ダウンロード完了、灰枠＝副次操作）、無理に1つの定数にまとめると個々の意味が失われるため、サイズ関連の階層とは分離した。

## ADR

今回はADRを書くレベルの設計判断はなし。
