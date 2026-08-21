# Phase6-1: Docker Compose全体起動確認（CORS配線は見送り）

## 何を実装したか

- コード変更なし。現状の`backend/app/main.py`／`docker-compose.yml`／
  `frontend/vite.config.ts`を調査し、`docker compose up`のみで両コンテナが立ち上がり
  フロントエンドからバックエンドAPIに疎通する、という依頼書のDone条件を現状の構成が
  既に満たしていることを確認した。
- `docs/specs/cpa-anki-generator-v2-phase-plan.md`のPhase6-1の記述を更新し、実装物から
  「backend側CORSMiddleware設定」を外して「compose上でのポート・ネットワーク疎通確認」の
  みに縮小した。

## 実装中に発見したバグ・問題点

なし（コード変更を伴わない調査Phaseのため）。

## 大きな判断とその理由

- **CORSMiddlewareは実装しないことにした**：当初計画（Phase6-1）ではbackend側に
  `CORSMiddleware`を設定する想定だったが、現状の構成を調査した結果、以下の理由から
  不要と判断した。
  - `frontend`コンテナは`vite build`によるビルド成果物をnginx等で配信する構成ではなく、
    `npm run dev`でVite開発サーバーを常時稼働させる構成になっている
    （`frontend/Dockerfile`のCMD参照）。
  - `frontend/vite.config.ts`の`server.proxy`が、`/pdfs`・`/scan`・`/generation-jobs`・
    `/settings`・`/root-path-history`といったAPIパスをコンテナ内部で`http://backend:8000`
    へ転送する構成になっている。ブラウザから見ると、リクエストは常にフロントエンドと
    同一オリジン（Viteのdevサーバー）宛てであり、バックエンドへのクロスオリジンリクエストは
    そもそも一度も発生しない。
  - CORSの制約が問題になるのは、ブラウザがbackendを直接（別オリジンとして）叩く構成——
    典型的には`vite build`した静的ファイルをnginx等で配信し、フロントとバックエンドが
    別ポート／別オリジンになるケース——に限られる。本アプリはCLAUDE.mdの通り単一ユーザーの
    Tailnet運用が前提であり、そのような本番ビルド構成へ移行する計画は現時点でない。
  - 以上より、今存在しない構成のためにCORSMiddlewareを先回りで実装するのは過剰と判断し、
    見送ることにした。将来的に`vite build`＋静的配信構成へ移行する場合は、その時点で
    `CORSMiddleware`を数行追加するだけで対応できる（取り消しコストが低い判断）。
- **ADRは起票しないことにした**：既存の`docs/adr/0001-...md`は、実データ調査によって
  ドメインモデル・複数レイヤーにまたがる仕様変更が生じたケースに対して起票されている。
  今回の判断はドメインモデルやAPI契約に変更がなく、影響範囲もbackendの起動設定1点に
  閉じており、後から数行追加するだけで撤回できる可逆性の高い判断であるため、ADRの
  基準には満たないと判断した。判断の経緯自体はこのdev-logと計画書の更新で追跡可能にした。

## ADR

起票なし（理由は上記の通り）。

## 実機確認手順（まーくんに依頼）

1. リポジトリルートで以下を実行し、backend/frontend両方のイメージを再ビルドしてから
   起動する（Docker確認の運用ルール通り、必ずビルドを挟む）。
   ```
   docker compose build
   docker compose up
   ```
2. 両コンテナが起動し、ログにエラーが出ていないことを確認する
   （backend側は`Uvicorn running on http://0.0.0.0:8000`、frontend側は
   `VITE ... ready in ... ms`のようなログが出るはず）。
3. ブラウザで`http://homepi:5173`（または該当のTailscaleホスト名）を開き、以下を確認する。
   - ページが正しく表示される（フロントエンドの疎通）。
   - PDFを1つアップロード→ルートパスを入力してスキャンを実行し、セクション一覧が
     正しく返ってくることを確認する（`/pdfs`・`/scan`経由でのバックエンド疎通）。
   - ルートパス欄をクリックし、過去の履歴がdatalistの候補として表示されることも
     合わせて確認する（`/root-path-history`経由の疎通、Phase5-11の回帰確認を兼ねる）。
4. ブラウザのDevTools（ネットワークタブ／コンソール）で、CORSエラー
   （`Access-Control-Allow-Origin`関連のエラー）が出ていないことを確認する
   （現在の構成ではそもそもクロスオリジンリクエストが発生しないため、出ないはずである
   ことの確認）。
5. 上記が全て問題なければ、Phase6-1のDone条件（`docker compose up`のみでの疎通）を
   満たしたと判断する。
