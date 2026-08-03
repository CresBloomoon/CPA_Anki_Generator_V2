# Phase0-2: フロントエンド最小骨格

## 実装したもの

- `frontend/`（`npm create vite@latest frontend -- --template react-ts`で生成したVite+React+TS雛形）
- Tailwind CSS v4を`@tailwindcss/vite`プラグイン方式で導入。`tailwind.config.js`／
  `postcss.config.js`は不要で、`src/index.css`に`@import "tailwindcss";`を1行書くのみ。
  `vite.config.ts`に`tailwindcss()`プラグインを追加。
- `src/App.tsx`：Vite雛形付属のデモコンテンツ（React/Viteロゴ、hero画像、ドキュメント／SNS
  リンク一覧）を全て削除し、「CPA Anki Generator V2」という見出しのみを中央表示する最小
  プレースホルダに置き換え。あわせて未使用になった`src/App.css`・`src/assets/*`・
  `public/icons.svg`を削除。
- `frontend/Dockerfile`：`node:22-slim`ベース。`package.json`/`package-lock.json`を先に
  コピーして`npm ci`、その後アプリ本体をコピーして`npm run dev -- --host 0.0.0.0 --port 5173`
  で起動。開発用コンテナのため本番ビルド（`vite build`）はまだ組み込んでいない。
- `frontend/.dockerignore`：`node_modules`／`dist`をビルドコンテキストから除外
  （ローカルの`npm install`成果物をコンテナに持ち込まないため）。
- `package.json`の`name`を`cpa-anki-generator-frontend`に、`index.html`の`<title>`を
  `CPA Anki Generator V2`に変更。

## 設計判断

- Tailwindは v3系のPostCSSプラグイン方式ではなくv4系の`@tailwindcss/vite`プラグイン方式を
  採用。設定ファイルが実質不要になり、初心者にも構成が追いやすいため。
- Dockerfileは開発（`vite`のdevサーバー）専用とした。本番相当のビルド＋配信用イメージ
  （`vite build`＋静的配信）は、実際にデプロイの話が出た時点で別途検討する（依頼書のスコープは
  Tailnet経由の単一ユーザー利用であり、現時点で本番配信構成を先取りする必要はないと判断）。

## 動作確認

- 実装時のサンドボックス環境にはnode/npmが存在したため、Docker抜きで以下を直接確認：
  - `npm run build` — Tailwind CSSを含めて正常にビルド成功
  - `npm run dev -- --host 0.0.0.0 --port 5173` を起動し、`curl http://localhost:5173/`で
    `<title>CPA Anki Generator V2</title>`を含むHTMLが返ることを確認
- Dockerはサンドボックスに存在しなかったため`frontend/Dockerfile`自体のビルドは開発者側の
  実機で実施。`docker build`成功、`docker run`後に`curl http://localhost:5173/`で同様のHTMLが
  返ることを確認済み。

## 発見した問題点

特になし。

## ADR

Tailwind v4方式の採用、開発用Dockerfileのみとする判断はいずれも小規模な技術選定であり、
ADRを起票するほどの分岐ではないと判断した。
