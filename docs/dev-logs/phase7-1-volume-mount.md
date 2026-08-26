# Phase7-1: docker-compose.ymlへのvolumeマウント対応

## 背景

APIコスト損失調査（B-1／C-2対応済み）で残されていたA系統（ディスク永続化）を、
「履歴機能」という新要件と合わせてStep7（永続化・履歴機能）として着手することに
なった。その現状把握の過程で、`docker-compose.yml`の`backend`サービスに
volumeマウントが一切設定されていないことが判明した。これは今回のインシデント
（`docker compose build`/`up`によるインメモリジョブの全損）と同じ壊れ方を、
既に稼働している`settings.json`／`root_path_history.json`の永続化にも
及ぼしている状態であり、Step7の他のどのPhaseよりも先に対応すべき前提条件として、
単独のPhase7-1で対応した。

## 何を実装したか

- `backend/app/repositories/settings/settings_repository.py`（修正）
  - `_DEFAULT_SETTINGS_PATH`を`backend/settings.json`から
    `backend/data/settings.json`に変更。
- `backend/app/repositories/settings/root_path_history_repository.py`（修正）
  - `_DEFAULT_HISTORY_PATH`を`backend/root_path_history.json`から
    `backend/data/root_path_history.json`に変更。
- `docker-compose.yml`（修正）
  - `backend`サービスに`./backend/data:/app/data`のbind mountを追加。
    named volumeではなくbind mountを選んだ理由は、まーくんがホスト側の
    フォルダを直接エクスプローラ／エディタで確認できるようにするため。
- `.gitignore`（修正）
  - `backend/settings.json`単体のエントリを`backend/data/`に置き換え。
    これにより、これまで`.gitignore`に登録されていなかった
    `root_path_history.json`もまとめてカバーされるようになった。

## 実装中に発見したバグ・問題点

- 現状把握の過程で、`.gitignore`に`backend/settings.json`は登録されて
  いたが`backend/root_path_history.json`は登録されていないという見落とし
  を発見した。実ファイルがまだ生成されていなかったため実害はまだ顕在化
  していなかったが、今回のパス統一と合わせて解消した。
- `docker compose exec backend cat settings.json`で確認したところ、
  まーくんの環境でも`settings.json`は一度も保存操作されておらず初期値の
  ままだった（保護すべき既存データは実質無かった）。これにより、デフォルト
  パスの変更に伴う既存データの引き継ぎ（マイグレーション）を検討する
  必要が無いことを確認した上で実装を進めた。

## 大きな判断とその理由

- **`settings.json`／`root_path_history.json`も`data/`配下に統一した**：
  Phase7-2（見送り、後述）で導入予定の`data/jobs/`と保存場所の考え方を
  揃えることで、「永続化したいものは全部`data/`配下」という一貫したルール
  にした。まーくんの環境で`settings.json`が実質未使用（初期値のまま）で
  あることを確認できたため、デフォルトパス変更に伴う実害（保存済み設定が
  見えなくなる）が無い状態で実施できた。
- **bind mountを採用し、named volumeは採用しなかった**：このリポジトリに
  volumeの前例が無く、まーくんがDocker管理領域を経由せずホスト側の
  フォルダを直接見られる方が、このプロジェクトの「明示的であることを
  優先する」という方針に合うと判断した。

## 動作確認結果

まーくんの環境で以下を確認済み：
1. `docker compose build backend` → `pytest` で233件パス（既存テストへの
   影響なし）
2. `docker compose up -d` → 設定画面から保存 →
   `backend/data/settings.json`に`{"provider": "gemini", "model_name":
   "gemini-2.5-flash"}`が生成される → `docker compose down` →
   `docker compose up --build -d`（イメージ再ビルドを伴うコンテナ再作成）
   → `docker compose exec backend cat data/settings.json`で同じ内容が
   残っていることを確認

## 保留事項（履歴機能）

Step7の続き（Phase7-2以降）に着手する際の参考として、ここまでの設計議論の
結論を記録する。

- **履歴機能の要件（確定）**：過去に実行したジョブの一覧を、実行日時・
  ルートパス・セクション数・カード数・状態とともに表示する。各履歴から
  生成済みの`.apkg`を再ダウンロードできる。「当時の設定を復元して
  再実行する」機能（再現機能）は含めない。
- **永続化の設計判断（確定）**：
  - 技術選定：ジョブごとに1ファイルのJSON（`SettingsRepository`／
    `RootPathHistoryRepository`と同じ書き方を踏襲）
  - 永続化対象：ジョブのメタ情報（job_id・実行日時・root_path・
    セクション数・状態）、各セクションの生成済みカード（DONE／
    PARTIALLY_DONEの分）、生成された`.apkg`ファイル自体
  - 永続化のタイミング：ブロック完了ごと（`on_block_generated`
    コールバック、B-1と同じ粒度）
  - 再起動後の回収方法：自動検出＋通知ではなく、履歴一覧画面がその役割を
    兼ねる。PENDINGセクションの生成再開は行わない（再現機能を含めない
    ため）
  - PdfStore（PDFバイト列）の永続化：不要（再現機能を含めないため）
- **未解決の論点（Phase7-2以降で検討）**：
  1. バックエンドは現状`root_path`という概念を一切受け取っておらず
     （`StartGenerationRequest`にもフィールドが無い）、各セクションの
     `deck_path`に合成済みの文字列としてしか渡ってこない。履歴一覧に
     「ルートパス」を表示するには、`root_path`をリクエストに新たに
     追加するか、`deck_path`の共通先頭セグメントから推定するかを
     決める必要がある。
  2. `.apkg`はセクションのカード全体から都度ビルドする成果物のため、
     「永続化のタイミング＝ブロック完了ごと」をカードデータ（JSON）と
     同じ粒度で`.apkg`にも適用する（毎ブロック完了ごとに全体を再ビルド）
     のか、それとも区切り（セクション完了時／ジョブ完了時／履歴からの
     再ダウンロード時に遅延ビルド）を設けるのかは別途検討が必要。

## ADR

今回はADRを書くレベルの設計判断はなし。
