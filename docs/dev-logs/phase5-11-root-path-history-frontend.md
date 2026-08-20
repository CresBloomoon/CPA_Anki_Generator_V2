# Phase5-11: ルートパス履歴機能（フロントエンド）

## 何を実装したか

- `frontend/src/api/types.ts`（修正）：`RootPathHistoryEntry`／`RootPathHistoryResponse`を追加。
  `backend/app/routes/schemas/root_path_history.py`をミラーする既存の他型と同じ書き方。
- `frontend/src/api/client.ts`（修正）：`getRootPathHistory()`を追加（`GET /root-path-history`）。
  他のAPI関数と同様、非2xxは`extractErrorMessage`経由で`Error`を投げる。
- `frontend/src/components/UploadPanel.tsx`（修正）
  - マウント時に一度だけ`useEffect`で`getRootPathHistory()`を呼び、結果の`path`一覧を
    `rootPathHistory: string[]`stateに保持する。取得失敗時は`catch`で握りつぶし、何も表示しない
    （履歴はあくまで入力補助であり、これが取れなくてもスキャン自体は問題なく行えるべきという判断——
    詳細は「大きな判断とその理由」を参照）。
  - ルートパス入力の`<input>`に`list="upload-panel-root-path-history-options"`を付与し、対応する
    `<datalist>`で`rootPathHistory`の各パスを`<option>`として列挙する。`SectionTable.tsx`の
    出力デッキ名列で既に使われている`<datalist>`パターン（Phase5-2で導入）をそのまま踏襲した。

## 実装中に発見したバグ・問題点

- **`GET /root-path-history`がバックエンドに届かず、Viteの開発サーバー自身（SPAフォールバック）
  が`index.html`をそのまま返してしまう問題**：実機確認で発見。原因は`frontend/vite.config.ts`の
  `server.proxy`が、転送対象のパスをプレフィックス単位で明示的に列挙する方式になっており
  （`/pdfs`／`/scan`／`/generation-jobs`／`/settings`）、新設した`/root-path-history`をこの一覧に
  追加し忘れていたこと。`fetch()`自体は他のAPI関数と全く同じ相対パスの書き方をしており、
  `client.ts`側のリクエスト組み立てには問題がなかった。`vite.config.ts`の`proxy`に
  `"/root-path-history": "http://backend:8000"`を追加して解消した。

## 大きな判断とその理由

- **履歴の再取得はマウント時の1回のみとした**：`UploadPanel`は`App.tsx`側で`resetKey`によって
  リセットのたびに再マウントされる設計（Phase5-6）になっており、次にこのコンポーネントが
  新規表示されるタイミング（ページ再読み込み・リセット）で自然に最新の履歴が反映される。
  同一セッション内でスキャンした直後にも即座に候補へ反映したい、という選択肢もまーくんに提示したが、
  そのためのAPI呼び出しを追加するコストに見合うほどの実利用上のメリットがないと判断し、シンプルな
  マウント時1回のみの方針で確定した。
- **履歴取得の失敗はサイレントに握りつぶすことにした**：この機能は「よく使うルートパスの入力を
  楽にする」ための補助的な候補表示に過ぎず、取得できなくてもルートパス欄への手入力自体は変わらず
  機能する。ここでエラーメッセージを表示すると、本質的にはブロッキングでない失敗をあたかも
  スキャン全体を止める重大な問題のように見せてしまうため、UI上は何も表示しないことにした。

## ADR

今回はADRを書くレベルの設計判断はなし。
