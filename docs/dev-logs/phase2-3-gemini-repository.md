# Phase2-3: Gemini具象実装

## 実装したもの

- `backend/app/repositories/ai/json_repair.py`：`extract_cards_from_json`。旧`ai_client.
  _extract_cards_from_json`の多段階JSON修復ロジック（コードフェンス除去→括弧優先度に
  基づく抽出→打ち切りJSONの補完→2段階目の正規表現による個別オブジェクト抽出）を移植。
  `CardJsonRepairError`を新設し、完全に復旧不能な場合はこれを送出する。
- `backend/app/repositories/ai/gemini_repository.py`：`GeminiRepository`
  （`AiCardGeneratorRepository`の具象実装）。
  - `api_key`はコンストラクタの必須引数とし、`.env`からの読み込みはこのクラスの責務と
    しない（Phase2-4の設定リポジトリ／Phase2-5のFactoryに委ねる）。
  - `client`・`prompt_builder`はコンストラクタ引数として注入可能にし、実SDK・実
    プロンプトファイルを使わずにテストできるようにした。
  - `generate_cards`が返す生カード辞書（`TITLE`等の大文字キー）を、
    Phase1-2の`CardContentItem`（snake_caseフィールド）へ変換する`_to_card_content_item`
    を実装。
- `backend/pyproject.toml`：`google-genai>=1.0`を依存に追加。
- `backend/tests/repositories/ai/test_json_repair.py`（9ケース）・
  `test_gemini_repository.py`（6ケース、`pytest`の`monkeypatch`で`time.sleep`を
  無効化し実際には待機せずリトライ挙動を検証）。

## 実装中に発見したバグ・問題点

### json_repair.py：AIレスポンスが静かにカードを失うバグ

`extract_cards_from_json`の`{`優先の抽出ロジック（`start_brace`を`start_bracket`より
先にチェックする分岐）が、抽出した`{...}`区間が**たまたま単体で valid なJSONオブジェクト
になってしまうケース**を考慮していなかった。この場合`json.loads`は例外を出さずに成功し、
`data.get("cards", [])`が「`cards`キーが無い」ため黙って`[]`を返し、実際には存在した
カードデータが**例外もログも無く**失われていた。

再現条件は以下の2パターン（実測で確認）：
- AIが`{"cards": [...]}`ではなく、単一カードを裸の配列で1件だけ返した場合
  （例：`[{"TITLE": "C", ...}]`）
- 前後にゴミテキストが混ざり、有効なJSONオブジェクトが1個だけ残る場合
  （例：`garbage {"TITLE": "D", ...} more garbage {bad json`）

カードが2件以上残っていれば、この1個抽出が`json.loads`で失敗（複数オブジェクトの
カンマ区切りは単体では invalid JSON）して初めて2段階目の正規表現復旧処理に落ち、
たまたま救済されていた。1件だけのケースでのみ「valid だが`cards`キーが無い」という
中途半端な状態になり、バグが顕在化していた。

このロジックは**旧`ai_client.py`の`_extract_cards_from_json`にもまったく同一の優先順位で
存在しており**、忠実な移植の結果として顕在化した既存のバグである（V2で新規に作り込んだ
ものではない）。

**修正**：`json.loads`が例外を出さずに成功した場合でも、結果が辞書型かつ`"cards"`キーが
存在しない場合は、`JSONDecodeError`時と同じ2段階目の正規表現復旧処理（`_recover_via_flat_
objects`）にフォールバックするようにした。これにより上記2パターンとも正しく1件ずつ復旧
できることを実測で確認済み（`test_bare_array_with_single_card_is_not_silently_lost`／
`test_single_valid_object_buried_in_garbage_is_not_silently_lost`として回帰テスト化）。
なお、AIが意図的に`{"cards": []}`（キーは存在するが空配列）を返した場合はこのフォール
バックの対象外とし、そのまま「0件」として扱う（`test_explicit_empty_cards_list_stays_
empty`で区別を保証）。

## 大きな判断とその理由：例外分類（認証エラーは即失敗、それ以外はリトライ）

`generate_cards`の例外処理は、当初は旧`ai_client.py`をそのまま移植し「レート制限エラー
（指数バックオフでリトライ）」と「それ以外すべて（一律5秒でリトライ、最大3回）」の
2種類にしか分類していなかった。この設計についてレビューを受け、認証・権限エラー
（APIキー不正等、リトライしても絶対に直らない失敗）まで無駄に3回リトライされる点を
指摘された。

調査の結果、旧実装がこの粗い分類で許容できていたのは、**複数APIキーのローテーションが
前提**だったためと判明した。あるキーで認証エラーが起きても「そのキーがダメなだけ」と
割り切って次のキーに切り替えれば良く、無駄なリトライのコストは「次のキーに移る前の
数秒の遅延」程度で済んでいた。

V2は依頼書の方針で**単一キーのみ**（ローテーション廃止）のため、認証エラーのような
恒久的な失敗に対しても、後ろに控えている「次のキー」が無く、ただ無駄に3回×5秒
（+初回試行時間）を浪費してから同じエラーで失敗するだけになる。単一キー構成という
V2固有の設計変更により、「区別しないことのコスト」が旧実装より相対的に大きくなったと
判断し、以下の3分類に変更した。

1. **認証・権限エラー**（`401`／`403`／`PERMISSION_DENIED`／`UNAUTHENTICATED`／
   `API_KEY_INVALID`のいずれかをメッセージに含む）：`GeminiAuthenticationError`を
   即座に送出し、リトライしない。
2. **レート制限エラー**（`429`／`RESOURCE_EXHAUSTED`／`Quota exceeded`）：指数
   バックオフ（`base_delay*(2**attempt)+5`）でリトライ（旧実装と同じ）。
3. **その他未分類のエラー**（ネットワーク断、JSON修復不能な応答等）：一律5秒待って
   リトライ（旧実装と同じ）。最大試行回数（`max_retries`）を使い切った時点で
   `GeminiGenerationError`を送出する。

いずれの分類も、実際の判定はレート制限と同じ「メッセージ文字列に含まれるマーカーで
判定する」軽量な方式に統一した。

## 動作確認

- `json_repair.py`はPyMuPDF等の外部依存が無いため、サンドボックス内で直接実行して
  全ケース確認済み。
- `gemini_repository.py`は`google-genai`が未インストールの環境だったため、SDKを
  スタブ化した上でテストファイルと同一のロジックを手動実行し、認証エラーの即時失敗・
  レート制限の指数バックオフ・その他エラーの一律リトライ・JSON修復失敗のリトライ扱いを
  全て確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`74 passed in 6.13s`を確認済み
  （Phase2-2完了時点の59件＋今回の15件）。`test_gemini_repository.py`（`monkeypatch`を
  使う実ファイル）もこの実行で初めて実際にpytestとして検証され、全件パスした。

## ADR

例外分類の設計変更（3分類化）は、依頼書で明示された「単一APIキー構成」という制約から
論理的に導かれる判断であり、ADRを起票するほどの新たな分岐ではないと判断した。
json_repairのバグ修正も、旧実装からの忠実な移植で顕在化した欠陥の是正であり、同様に
ADR化は不要と判断した。
