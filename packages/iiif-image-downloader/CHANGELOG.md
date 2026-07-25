# Changelog

## 1.0.0 (2026-07-26)

Google Colab のノートブックに直書きされていた処理を、テスト付きの Python パッケージとして切り出しました。

### 追加

- IIIF Presentation API 3.0 に対応（Canvas → AnnotationPage → Annotation → body の走査、`Choice` ボディ、言語マップのラベル）
- Collection を指定すると、含まれる Manifest を再帰的に展開（深さは `--max-collection-depth` で制御）
- Image API のバージョンに応じた size の自動選択（Image API 3 は `max`、1.x/2.x は `full`）
- `--size` / `--region` / `--rotation` / `--quality` / `--format` による Image API パラメータの指定
- コマンドラインツール `iiif-image-download`（`--dry-run`、`--from-file`、`--overwrite`、`--use-label`、`--flat` など）
- Python API（`download()` / `load_manifest()` / `parse_manifest()` / `image_url()`）と実行結果レポート
- 429・5xx に対する指数バックオフ付き再試行、および説明的な User-Agent の送出
- ユニットテスト 55 件（ネットワークアクセスなし）と GitHub Actions による CI

### 変更

- 1 枚の取得失敗で全体が止まらないよう、失敗は記録して継続する方式に変更（`--fail-fast` で従来の挙動）
- 出力フォルダ名を、マニフェスト URI の `/` を `_` に置換した長い名前から `{ホスト名}_{識別子}` に変更
- 画像は `*.part` に書いてから移動するため、中断しても壊れたファイルが残らない
- 既定の待機秒数を 5 秒から 1 秒に変更（再試行とタイムアウトを実装したため）

### 修正

- Presentation API 2.x で `sequences` を持たないマニフェスト、painting アノテーションを持たない Canvas で停止していた問題
- 拡張子を常に `.jpg` としていた問題（URL とマニフェストの `format` から判定するように変更）

## 0.1.0（Colab ノートブック版, 2022-03-04）

- Presentation API 2.x のマニフェストからの一括ダウンロード
- 2022-03-05: リクエスト間の待機処理を追加
- 2022-03-06: Image API 非対応のマニフェストに対応
