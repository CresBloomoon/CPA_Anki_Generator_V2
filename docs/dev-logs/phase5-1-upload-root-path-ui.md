# Phase5-1: アップロード+ルートパス入力UI

## 何を実装したか

- `frontend/vite.config.ts`（修正）
  - `/pdfs`・`/scan`・`/generation-jobs`・`/settings`を`http://backend:8000`へ中継する開発用プロキシ（`server.proxy`）を追加。ブラウザは常にVite開発サーバー（同一オリジン）にしかアクセスしないため、Phase6-1でCORSを配線するまでの間もブラウザから実際に動作確認できる。
  - `server.allowedHosts: ["homepi"]`を追加。Tailscale経由でマシン名（`homepi`）からアクセスした際、Viteのデフォルト設定（DNS rebinding対策）がホスト名を拒否する事象が実機確認で発生したため、明示的に許可した。

- `frontend/src/api/types.ts`（新規）
  - `backend/app/routes/schemas/pdf.py`に対応するTS型（`UploadPdfResponse`／`SectionScanResult`／`ScanResponse`）。コード生成ツールは使わず手書き。

- `frontend/src/api/client.ts`（新規）
  - `uploadPdf(file)`／`scanPdfs(sourceFiles, rootPath)`：`fetch`の薄いラッパー。`pdf_id`のような別IDは存在せず、バックエンドと同じく`source_file`（アップロード時のファイル名文字列）をそのまま識別子として使う。

- `frontend/src/components/UploadPanel.tsx`（新規）
  - 複数PDF選択（`<input type="file" multiple>`）、ルートパス入力欄、「スキャン開始」ボタン。ボタン押下で選択ファイルを並行アップロードし、得られた`source_file`一覧とルートパスで`/scan`を呼び、結果を`onScanComplete`で親に渡す。
  - ボタンの活性条件は「ファイル選択済み・ルートパス入力済み・スキャン中でない」のみで、過去のスキャン結果の件数には一切依存しない。

- `frontend/src/App.tsx`（修正）
  - `sections`／`warnings`／`hasScanned`の3つの状態を保持し、`UploadPanel`を配置。
  - スキャン結果の暫定的な簡易プレビュー（読み取り専用リスト、Phase5-2で編集可能テーブルに置き換え予定）。
  - `hasScanned && sections.length === 0`のとき、warningsの表示ブロックともUploadPanel内のエラー表示ブロックとも別枠・別スタイル（グレー系）で、「セクションが見つかりませんでした。」という空状態メッセージを表示する。ボタンの無効化など操作を制限するロジックは追加していない。

- `backend/app/repositories/pdf/pdf_structure_repository.py`（修正）
  - `scan()`で、TOC走査の結果（`_build_sections_from_toc`）が空だった場合、`"{source_file} にはTOC（しおり）が見つかりませんでした"`という警告を`ScanResult.warnings`に追加するようにした。

- `backend/tests/repositories/pdf/test_pdf_structure_repository.py`（修正）
  - TOCの無いPDFをスキャンすると、上記の警告がファイル名込みで返ることを検証するテストを追加。

## 実装中に発見したバグ・問題点

- **TOCが無いPDFをスキャンすると`{"sections":[],"warnings":[]}`が返り、ユーザー視点で「ボタンを押しても何も起きていないように見える」事象**：まーくんが実PDF（TOC/しおり未設定のファイル）で手動確認した際に発見。ADR 0001（TOC専用検出）の設計上、セクション0件自体は仕様通りだが、warningsも空のままだと理由が分からず不親切と判断し、上記の通り修正した。
- **`http://homepi:5173`でのアクセスが`Blocked request. This host ("homepi") is not allowed.`で拒否される事象**：まーくんがTailscale経由のマシン名でアクセスした際に発見。Viteのデフォルトの安全機構（DNS rebinding対策）が、`host: true`だけでは`localhost`/IPアドレス以外のホスト名を許可しないための挙動。`server.allowedHosts`に明示的に追加して解消。

## 大きな判断とその理由

- **バックエンドへの接続はViteの開発サーバープロキシ経由とし、CORS配線はPhase6-1のまま据え置いた**：ブラウザは常にVite開発サーバーと同一オリジンでしか通信しないため、開発中はCORS設定なしで実機確認ができる。本番ビルド（静的配信）時のCORS配線は引き続きPhase6-1のスコープとする（まーくんとの事前合意事項）。
- **TOC検出0件時の警告は`PdfStructureRepository.scan()`に持たせ、Usecase層は変更しなかった**：`ScanPdfStructureUsecase`は既に`scan_result.warnings`をそのまま集約する作りだったため、警告メッセージの発生源をリポジトリ層に閉じ込めるだけで済んだ。
- **空状態メッセージは「エラー」でも「警告」でもない、独立した情報提供として扱った**：まーくんとの事前合意通り、赤字のエラー表示（UploadPanel内）や黄色系の警告表示（App内）とは別枠・別スタイルとし、ボタンの無効化などの操作制限も一切加えなかった。TOC検出0件は「詰み」ではなく「人間が0から入力できる状態」につながるべき、という考え方をPhase5-2（セクションテーブルの行追加・削除機能）の設計に引き継ぐ。

## 手動確認の結果

- Docker実機でのpytest：171 passed（新規追加分含めて全件PASS）。
- ブラウザでの手動確認（まーくん実施）：
  - `http://homepi:5173`でのアクセス：確認済み
  - TOCの無い実PDFでのスキャン：バックエンド警告の表示、空状態メッセージの表示、操作制限が無いこと、DevToolsでのレスポンス本体（`{"sections":[],"warnings":["..."]}`）を確認済み
  - TOCのある実PDFでのスキャン：手元に適したPDFが無く**未実施**。TOC検出のメインロジック自体は今回変更していないためリスクは低いと判断し、必要になればPhase5-2着手前に別途確認する運用とした（まーくんとの合意事項）。

## ADR

今回はADRを書くレベルの設計判断はなし。
