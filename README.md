# 000_tools

Google Colaboratory上で実行可能な各種ツールのノートブックを提供するリポジトリです。

## お知らせ

### NDLOCRノートブックの提供終了

NDLOCRおよびNDL古典籍OCRに関するノートブックは、今後更新されません。

それぞれ、デスクトップアプリケーションおよびコマンドラインツールとして簡易に利用可能なLite版が公開されています。今後は、こちらをお使いいただけますと幸いです。

- NDLOCR-Lite: https://github.com/ndl-lab/ndlocr-lite
- NDL古典籍OCR-Lite: https://github.com/ndl-lab/ndlkotenocr-lite

## ノートブック一覧

| ノートブック | 説明 | 状態 |
|---|---|---|
| [iiif_image_downloader](iiif_image_downloader.ipynb) | IIIFマニフェストからの画像一括ダウンロード（Presentation API 2.x / 3.0） | - |
| [NDLOCR_v2の実行例](NDLOCR_v2の実行例.ipynb) | NDLOCR（ver.2.1）を用いたOCR処理 | 提供終了 |
| [NDL古典籍OCR_v2の実行例](NDL古典籍OCR_v2の実行例.ipynb) | NDL古典籍OCR（ver.2）を用いたOCR処理 | 提供終了 |
| [ndlocr_v2_simple](ndlocr_v2_simple.ipynb) | NDLOCR（ver.2.1）のシンプル版 | 提供終了 |
| [NDLTSR](NDLTSR.ipynb) | NDL表構造認識 | - |
| [IIIFマニフェストv3から検索可能なPDFを作成する](IIIFマニフェストv3から検索可能なPDFを作成する.ipynb) | IIIFマニフェストからPDFを生成 | - |
| [IIIFマニフェストファイルからTEI_XMLファイルを作成するプログラム](IIIFマニフェストファイルからTEI_XMLファイルを作成するプログラム.ipynb) | IIIFマニフェストからTEI/XMLを生成 | - |
| [ocr_iiif_toolsのデモ](ocr_iiif_toolsのデモ.ipynb) | ocr_iiif_toolsライブラリのデモ | - |
| [TEIでタグの使用頻度を分析するチュートリアル](TEIでタグの使用頻度を分析するチュートリアル.ipynb) | TEI/XMLのタグ分析 | - |
| [pyvipsの使い方とPyramid_Tiled_Tiffファイルの作り方](pyvipsの使い方とPyramid_Tiled_Tiffファイルの作り方.ipynb) | pyvipsによるTiff画像処理 | - |
| [lora_ndc_demo](lora_ndc_demo.ipynb) | LoRAによる日本十進分類法（NDC）分類のデモ | - |
| [その他](.) | LlamaIndex+GPT4、バリデーション、アノテーション変換など | - |

## パッケージ

ノートブックから呼び出す処理のうち、再利用性の高いものは `packages/` 以下に Python パッケージとして切り出しています。Colab の外（ローカルやサーバ）でも、コマンドラインやライブラリとして同じ処理を実行できます。

| パッケージ | 説明 |
|---|---|
| [iiif-image-downloader](packages/iiif-image-downloader) | IIIFマニフェストからの画像一括ダウンロード。Presentation API 2.x / 3.0、Collectionの展開に対応 |

```bash
pip install "git+https://github.com/nakamura196/000_tools.git#subdirectory=packages/iiif-image-downloader"
iiif-image-download -n 3 https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json
```

## ご利用にあたって

外部の画像やデータを取得するノートブックでは、提供機関に配慮してご利用ください。マニフェストや画像に付された利用条件を確認のうえ、リクエスト間隔に余裕を持たせることをおすすめします。

## ライセンス

MIT License（[LICENSE](LICENSE) を参照）
