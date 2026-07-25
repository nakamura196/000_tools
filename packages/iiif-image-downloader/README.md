# iiif-image-downloader

IIIF マニフェストに記述された画像を一括ダウンロードする Python パッケージです。IIIF Presentation API **2.x と 3.0 の両方**、および Collection の展開に対応しています。

Google Colab から使う場合は、リポジトリ直下の [`iiif_image_downloader.ipynb`](../../iiif_image_downloader.ipynb) をご利用ください。

> **ご利用にあたって**
> 画像の提供機関に配慮してご利用ください。マニフェストや画像に付された利用条件（`rights` / `attribution` / `requiredStatement` など）を確認し、大量取得の前には提供機関の方針をご確認ください。既定では 1 画像ごとに 1 秒待機します。

## インストール

```bash
pip install "git+https://github.com/nakamura196/000_tools.git#subdirectory=packages/iiif-image-downloader"
```

ローカルで開発する場合:

```bash
git clone https://github.com/nakamura196/000_tools.git
cd 000_tools/packages/iiif-image-downloader
pip install -e ".[dev]"
pytest
```

Python 3.9 以上が必要です。依存は `requests` と `tqdm` のみです。

## コマンドラインでの利用

```bash
# 先頭 3 画像だけ試す
iiif-image-download -n 3 https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json

# 実際にダウンロードせず、取得予定の URL と保存先を確認する
iiif-image-download --dry-run https://example.org/iiif/manifest.json

# Collection を指定すると、含まれる Manifest をすべて展開する
iiif-image-download -o data https://example.org/iiif/collection.json

# 長辺 1024px 以内に縮小して取得し、リクエスト間隔を 3 秒にする
iiif-image-download --size '!1024,1024' -s 3 https://example.org/iiif/manifest.json

# URL をファイルから読み込む（1 行 1 URL、# 以降はコメント）
iiif-image-download --from-file manifests.txt
```

### 主なオプション

| オプション | 既定値 | 説明 |
|---|---|---|
| `-o, --output-dir` | `data` | 出力先ディレクトリ |
| `-n, --limit` | `-1` | マニフェストあたりの最大取得枚数（`-1` ですべて） |
| `--size` | 自動 | Image API の size。Image API 3 は `max`、1.x/2.x は `full` を自動選択 |
| `--region` / `--rotation` / `--quality` / `--format` | `full` / `0` / `default` / `jpg` | Image API の各パラメータ |
| `-s, --sleep` | `1.0` | 各画像リクエストの前に待機する秒数 |
| `--timeout` / `--retries` | `30` / `3` | HTTP タイムアウトと、429・5xx に対する再試行回数 |
| `--overwrite` | off | 既存ファイルを再取得する（既定では存在すればスキップ） |
| `--use-label` | off | ファイル名に Canvas のラベルを付ける |
| `--flat` | off | マニフェストごとのフォルダを作らず、出力先直下に保存する |
| `--dry-run` | off | ダウンロードせず、URL と保存先だけを出力する |
| `--fail-fast` | off | 最初の失敗で中断する（既定は記録して継続） |
| `--max-collection-depth` | `2` | 入れ子になった Collection を展開する深さ |

`--dry-run` の出力は `URL<TAB>保存先パス` の TSV なので、そのまま別のツールに渡せます。

## Python API

```python
from iiif_image_downloader import DownloadOptions, download

report = download(
    ["https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json"],
    DownloadOptions(output_dir="data", limit=3, sleep=1.0),
)
print(report.summary())  # manifests=1 downloaded=3 skipped=0 failed=0

for manifest_report in report.manifests:
    for result in manifest_report.results:
        print(result.status, result.path)
```

マニフェストの解析だけを行うこともできます。ネットワークアクセスを伴わないため、手元の JSON に対しても使えます。

```python
from iiif_image_downloader import load_manifest, parse_manifest, image_url

manifest = load_manifest("https://iiif.io/api/cookbook/recipe/0009-book-1/manifest.json")
print(manifest.presentation_version)  # 3
print(len(manifest))  # 5

for image in manifest.images[:2]:
    print(image.label, image_url(image, size="400,"))
```

### 主なオブジェクト

| 名前 | 説明 |
|---|---|
| `Manifest` | 解析済みマニフェスト。`id` / `label` / `presentation_version` / `images` |
| `CanvasImage` | 1 つの Canvas に対応する画像。`index` / `label` / `image_id` / `service` |
| `ImageService` | Image API サービス。`id` と `version`（1/2/3）を持つ |
| `DownloadOptions` | 取得条件をまとめた設定オブジェクト |
| `DownloadReport` / `ManifestReport` / `DownloadResult` | 実行結果。`downloaded` / `skipped` / `failed` / `ok` |

## 挙動の詳細

### バージョンの判定

`@context` を最優先で見て、無い場合は文書の形（`sequences` があれば 2.x、`items` があれば 3.0、`sc:` 接頭辞付きの `@type` があれば 2.x）から推定します。判定できない場合は `UnsupportedVersionError` を送出します。

### 画像 URL の組み立て

Canvas の painting リソースに Image API サービスがあれば、`{service}/{region}/{size}/{rotation}/{quality}.{format}` を組み立てます。size の既定値はサービスのバージョンによって変わります。

- **Image API 3**: `max`（3.0 で `full` は廃止されました）
- **Image API 1.x / 2.x**: `full`（`max` を実装していないサーバがあるため）

サービスが無い（Image API 非対応の）マニフェストでは、リソースの URL をそのまま取得します。この場合 `--size` などは適用できません。

3.0 の `Choice` ボディ（同一 Canvas に複数の画像が並ぶ表現）は、先頭の項目を採用します。`motivation` が `painting` でない Annotation（本文テキストなど）は無視します。

### 出力先とファイル名

既定では、マニフェストごとに `{出力先}/{ホスト名}_{識別子}/` を作り、その中に `00001.jpg` のような連番で保存します。連番は Canvas の並び順で、5 桁ゼロ埋めです。

- 拡張子は、URL の拡張子 → マニフェストの `format` → `--format` の順に決めます
- `--use-label` を付けると `00001_1丁表.jpg` のようにラベルを併記します（連番は残るので並び順は保たれます）
- 旧バージョン（Colab 初版）はマニフェスト URI の `/` を `_` に置換した長いフォルダ名を使っていましたが、可読性のため上記の形式に変更しています

### 中断・再開

ダウンロードは `*.part` の一時ファイルに書き込み、完了後に本来の名前へ移動します。途中で止めても切れたファイルが残らないため、同じコマンドを再実行すれば未取得分だけが取得されます（既存ファイルはスキップされます）。再取得したい場合は `--overwrite` を使ってください。

### エラー時の扱い

1 枚の失敗は記録して次へ進み、最後にレポートへ集約します（`--fail-fast` で即中断に変更できます）。429 と 5xx に対しては指数バックオフ付きで既定 3 回まで再試行します。マニフェスト自体が取得できない場合も、他のマニフェストの処理は続きます。

## 開発

```bash
pytest          # ユニットテスト（ネットワークアクセスなし）
ruff check .    # Lint
ruff format .   # フォーマット
```

テストはスタブのセッションを注入する形で書かれており、外部ネットワークに接続しません。フィクスチャは `tests/fixtures/` にある Presentation API 2.x / 3.0 のマニフェストと Collection です。

## ライセンス

MIT License（リポジトリ直下の [LICENSE](../../LICENSE) を参照）

---

## English

A Python package to bulk-download the images described by a IIIF manifest. It reads both **Presentation API 2.x and 3.0**, expands Collections, and picks the correct Image API size segment per service version (`max` for Image API 3, `full` for 1.x/2.x).

```bash
pip install "git+https://github.com/nakamura196/000_tools.git#subdirectory=packages/iiif-image-downloader"
iiif-image-download -n 3 https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json
```

```python
from iiif_image_downloader import DownloadOptions, download

report = download(["https://example.org/iiif/manifest.json"], DownloadOptions(limit=3))
print(report.summary())
```

Please respect the terms of use of the institution providing the images, and keep the request interval (`--sleep`, 1 second by default) polite.
